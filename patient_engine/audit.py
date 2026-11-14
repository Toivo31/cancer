"""Library audit (G4): does a library of cards look like the catalogue says patients look?

    from patient_engine.audit import audit_library, load_tolerances, write_audit
    report = audit_library(library, catalogue, load_tolerances("catalogue/lung-primary-care/audit_tolerances.yaml"))
    report["passed"]            # True when no check failed
    write_audit(report, "runs/libraries/L1")        # audit.json and audit.md

Every number is measured from the cards and compared with what the catalogue's reference leaves give for
that very card (the leaf resolved with the card's own background, attributes and earlier findings), so a
library whose patients are older or sicker than average is not blamed for it. For a group of cards the
expected share is the mean of the per-card expectations and its sampling spread is that of independent draws
with those probabilities (a binomial at the mean probability). A cell fails when the observed share is outside the
exact binomial interval for the group size (tails at the normal tail of ``z``) **and** more than
``pp`` percentage points from the expectation. ``z`` is set for the whole report (about 750 cells), not per cell:
at a per-cell 99% an exact library failed by chance on every seed tried. A tolerance in percentage points alone
would ignore how small a group is.
A group with fewer than ``min_n`` cards or attempts is reported as ``skipped`` (never as a pass).

Checks (ids in the report)::

    findings.<condition>      share of cards with each binary finding true, each level of a categorical one,
                              and for measured findings the share below the reference median and p90
                              (primary condition only, no co-existing illness, state ``all_active``)
    accuracy.<test>           realised sensitivity and specificity of each binary output, accuracy of each
                              categorical output, from observations against the same state's findings, per
                              state group (``all_active`` and ``resolved``: every resolved state pooled)
    non_diagnostic            share of non-diagnostic attempts per test against the catalogue's rate
    state_consistency         resolved states: no symptom appears that was not there at first contact, and
                              no cause that is resolved
    presenting                presenting complaints that are not true symptoms of that state
    diversity                 cards with identical background and findings to an earlier card
    leak                      share of notes that the validator's leak rule (``card_reveals_condition``) flags

Not audited, and why (also written into the report): measurement error of continuous outputs; frequencies of
findings in resolved states and on cards with a co-existing illness (the reference value there is a mixture
of causes that the catalogue gives no single number for; the accuracy and consistency checks do cover those
cards and states); the content of free text.

Hidden-side code: it reads whole cards (invariant I1). Standard library and PyYAML.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml

from pathway_sim.dists import sample

from .card import INITIAL_STATE, Card, card_to_json
from .states import resolved_in_state

__all__ = ["AuditError", "audit_library", "load_tolerances", "write_audit", "render_markdown", "AUDIT_FORMAT",
           "TOLERANCES_FILE", "DEFAULT_TOLERANCES"]

AUDIT_FORMAT = "audit/1"
TOLERANCES_FILE = "audit_tolerances.yaml"
TOLERANCES_FORMAT = "audit_tolerances/1"
RESOLVED = "resolved"
_GRID = 100          # quantile points used to read a card's reference distribution

#: tolerance keys each check family needs
_KEYS = {
    "findings": ("pp", "min_n"), "continuous": ("pp", "min_n"), "accuracy": ("pp", "min_n"),
    "non_diagnostic": ("pp", "min_n"), "state_consistency": ("max_share",), "presenting": ("max_share",),
    "diversity": ("max_share",), "leak": ("max_share",),
}
DEFAULT_TOLERANCES: dict[str, Any] = {
    "z": 4.2,
    "checks": {
        "findings": {"pp": 5.0, "min_n": 20}, "continuous": {"pp": 7.5, "min_n": 20},
        "accuracy": {"pp": 5.0, "min_n": 20}, "non_diagnostic": {"pp": 2.0, "min_n": 20},
        "state_consistency": {"max_share": 0.0}, "presenting": {"max_share": 0.0},
        "diversity": {"max_share": 0.02}, "leak": {"max_share": 0.02},
    },
}


class AuditError(ValueError):
    """The audit cannot run: unreadable tolerances, a library that does not belong to the catalogue."""


# ============================================================================ tolerances

def load_tolerances(path: str | Path | None = None) -> dict[str, Any]:
    """Read ``audit_tolerances.yaml`` (``None``: the built-in defaults). Every check family must give its
    numbers and a ``reason``; a missing number is an error, not a silent default."""
    if path is None:
        return json.loads(json.dumps(DEFAULT_TOLERANCES))
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as e:
        raise AuditError(f"cannot read tolerances {path}: {e}") from None
    if not isinstance(data, dict) or data.get("format") != TOLERANCES_FORMAT:
        raise AuditError(f"{path}: not a {TOLERANCES_FORMAT} file")
    z = data.get("z")
    if not isinstance(z, (int, float)) or z <= 0:
        raise AuditError(f"{path}: z must be a positive number")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        raise AuditError(f"{path}: checks must be a mapping")
    for fam, keys in _KEYS.items():
        entry = checks.get(fam)
        if not isinstance(entry, dict):
            raise AuditError(f"{path}: checks.{fam} is missing")
        for k in keys:
            if not isinstance(entry.get(k), (int, float)) or entry[k] < 0:
                raise AuditError(f"{path}: checks.{fam}.{k} must be a non-negative number")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            raise AuditError(f"{path}: checks.{fam}.reason is required (why this tolerance)")
    return {"z": float(z), "checks": {k: dict(v) for k, v in checks.items()}}


# ============================================================================ statistics

class _Cell:
    """Expected and observed successes of one group: ``n`` trials with probabilities ``p_i`` (their sum and
    variance are kept) and ``k`` observed successes."""
    __slots__ = ("n", "sp", "var", "k")

    def __init__(self) -> None:
        self.n, self.sp, self.var, self.k = 0, 0.0, 0.0, 0.0

    def add(self, p: float, hit: float) -> None:
        self.n += 1
        self.sp += p
        self.var += p * (1.0 - p)
        self.k += hit


def _binom_interval(n: int, p: float, z: float) -> tuple[int, int]:
    """Exact two-sided interval of counts for ``Binomial(n, p)`` with each tail at most the normal tail of ``z``."""
    if p <= 0.0:
        return 0, 0
    if p >= 1.0:
        return n, n
    tail = 0.5 * math.erfc(z / math.sqrt(2.0))
    lp, lq = math.log(p), math.log1p(-p)
    pmf = [math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * lp + (n - k) * lq)
           for k in range(n + 1)]
    cum, lo = 0.0, 0
    for k in range(n + 1):
        cum += pmf[k]
        if cum > tail:
            lo = k
            break
    cum, hi = 0.0, n
    for k in range(n, -1, -1):
        cum += pmf[k]
        if cum > tail:
            hi = k
            break
    return lo, hi


def _judge(cid: str, kind: str, c: _Cell, z: float, pp: float, min_n: int, **extra: Any) -> dict[str, Any]:
    """Binomial interval for ``n`` trials at the mean expected probability (a Poisson-binomial with the same mean
    has a narrower spread, so this is the safe side); fail when outside it and more than ``pp`` points off."""
    cell: dict[str, Any] = {"id": cid, "kind": kind, "n": c.n, **extra}
    if c.n < min_n:
        return {**cell, "status": "skipped", "note": f"fewer than {min_n} cases"}
    exp, obs = c.sp / c.n, c.k / c.n
    lo_k, hi_k = _binom_interval(c.n, exp, z)
    lo, hi = lo_k / c.n, hi_k / c.n
    fail = (obs < lo - 1e-12 or obs > hi + 1e-12) and abs(obs - exp) * 100.0 > pp
    return {**cell, "expected": round(exp, 4), "observed": round(obs, 4), "lo": round(lo, 4), "hi": round(hi, 4),
            "off_pp": round(obs * 100 - exp * 100, 2), "status": "fail" if fail else "pass"}


def _share_check(cid: str, title: str, bad: int, total: int, max_share: float, unit: str, **extra: Any) -> dict[str, Any]:
    share = bad / total if total else 0.0
    ok = share <= max_share + 1e-12
    return {"id": cid, "title": title, "status": "pass" if ok else "fail", "n_cells": 1, "n_fail": 0 if ok else 1,
            "n_skipped": 0, "summary": f"{bad} of {total} {unit} ({share:.2%}); limit {max_share:.2%}",
            "cells": [{"id": cid, "kind": "share", "n": total, "bad": bad, "share": round(share, 5),
                       "max_share": max_share, "status": "pass" if ok else "fail", **extra}]}


def _group(cid: str, title: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
    fails = [c for c in cells if c["status"] == "fail"]
    skipped = [c for c in cells if c["status"] == "skipped"]
    ran = len(cells) - len(skipped)
    status = "fail" if fails else ("skipped" if cells and not ran else "pass")
    summary = f"{ran - len(fails)} of {ran} cells within tolerance" + (f", {len(skipped)} skipped (too few cases)" if skipped else "")
    return {"id": cid, "title": title, "status": status, "n_cells": len(cells), "n_fail": len(fails),
            "n_skipped": len(skipped), "summary": summary, "cells": cells}


# ============================================================================ reference numbers per card

def _facts(card: Card, state: str) -> dict[str, Any]:
    """Background, attributes of every condition and the non-null findings of ``state``: what a ``by:`` in the
    catalogue may read (the reference generator's ``common_facts``)."""
    attrs: dict[str, Any] = {}
    for c in reversed(card.hidden.conditions):                  # primary last, so its attributes win a clash
        attrs.update(c.attributes)
    f = {k: x.value for k, x in card.hidden.findings[state].items() if x.value is not None}
    return {**card.background, **attrs, **f}


def _active(card: Card, catalogue, state: str) -> tuple[str, ...]:
    ids = tuple(c.id for c in card.hidden.conditions)
    ill = tuple(c for c in ids if catalogue.conditions[c].cls == "other_illness")
    resolved = resolved_in_state(state, ill)
    active = tuple(c for c in ids if c not in resolved)
    if active:
        return active
    return (next((c for c, x in catalogue.conditions.items() if x.cls == "healthy"), "none"),)


def _worst(leaf, conditions, facts, default: float, how) -> float:
    if leaf is None:
        return default
    return how(float(leaf.resolve({**facts, "condition": c})) for c in conditions)


def _state_group(state: str) -> str:
    return INITIAL_STATE if state == INITIAL_STATE else RESOLVED


# ============================================================================ the checks

def _clamp_round(x: float, v) -> float:
    lo, hi = v.range
    if v.type == "size_mm" and lo is None:
        lo = 0.0
    if lo is not None:
        x = max(x, lo)
    if hi is not None:
        x = min(x, hi)
    return round(x, 1)


def _findings_cells(cards, catalogue, tol, z) -> list[dict[str, Any]]:
    """Per primary condition: frequencies of findings of single-illness cards in ``all_active``."""
    binary: dict[tuple, _Cell] = defaultdict(_Cell)
    levels: dict[tuple, _Cell] = defaultdict(_Cell)
    quant: dict[tuple, _Cell] = defaultdict(_Cell)
    cond_n: dict[str, int] = defaultdict(int)
    for card in cards:
        if len(card.hidden.conditions) != 1:
            continue
        prim = card.primary_condition
        cond_n[prim] += 1
        facts = _facts(card, INITIAL_STATE)
        for vid, v in catalogue.variables.items():
            f = card.hidden.findings[INITIAL_STATE].get(vid)
            if f is None or f.value is None:
                continue
            leaf = v.given_for(prim)
            spec = leaf.resolve({**facts, "condition": prim})
            if v.type == "binary":
                binary[(prim, vid)].add(float(spec), 1.0 if f.value is True else 0.0)
            elif v.type == "categorical":
                tot = sum(spec.values()) or 1.0
                for lvl in (v.values or tuple(spec)):
                    levels[(prim, vid, lvl)].add(spec.get(lvl, 0.0) / tot, 1.0 if f.value == lvl else 0.0)
            elif isinstance(f.value, (int, float)) and not isinstance(f.value, bool):
                x = float(f.value)
                grid = [_clamp_round(sample(spec, (j + 0.5) / _GRID), v) for j in range(_GRID)]
                for name, q in (("median", 0.5), ("p90", 0.9)):
                    ref = _clamp_round(sample(spec, q), v)                # the generator rounds and clamps its values
                    # the chance that a draw from this card's own reference lands below the reference quantile
                    # (ties count half): 0.5 / 0.9 for a smooth distribution, other for a discrete or clamped one
                    p = sum(1.0 if g < ref else 0.5 if g == ref else 0.0 for g in grid) / _GRID
                    quant[(prim, vid, name)].add(p, 1.0 if x < ref else 0.5 if x == ref else 0.0)
    cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tf, tc = tol["checks"]["findings"], tol["checks"]["continuous"]
    for (prim, vid), c in binary.items():
        cells[prim].append(_judge(f"{prim}.{vid}", "binary finding true", c, z, tf["pp"], tf["min_n"]))
    for (prim, vid, lvl), c in levels.items():
        cells[prim].append(_judge(f"{prim}.{vid}={lvl}", "categorical level", c, z, tf["pp"], tf["min_n"]))
    for (prim, vid, name), c in quant.items():
        cells[prim].append(_judge(f"{prim}.{vid}<{name}", f"share below reference {name}", c, z, tc["pp"], tc["min_n"]))
    out = []
    for prim in sorted(cond_n):
        out.append(_group(f"findings.{prim}", f"Findings of {prim} cards ({cond_n[prim]} single-illness cards) against the catalogue", cells[prim]))
    return out


def _accuracy_and_nondiagnostic(cards, catalogue, tol, z) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sens: dict[tuple, _Cell] = defaultdict(_Cell)
    spec: dict[tuple, _Cell] = defaultdict(_Cell)
    cat_acc: dict[tuple, _Cell] = defaultdict(_Cell)
    nd: dict[tuple, _Cell] = defaultdict(_Cell)
    for card in cards:
        for state in card.states:
            grp = _state_group(state)
            facts = _facts(card, state)
            act = _active(card, catalogue, state)
            findings = card.hidden.findings[state]
            for t in catalogue.tests.values():
                atts = card.observations[state].get(t.id, ())
                p_nd = _worst(t.nondiagnostic, act, facts, 0.0, max)
                for a in atts:
                    nd[(t.id, grp)].add(p_nd, 1.0 if a.status == "non_diagnostic" else 0.0)
                    if a.status != "ok":
                        continue
                    for o in t.outputs:
                        fnd = findings.get(o.measures)
                        truth, got = (fnd.value if fnd else None), a.values.get(o.id)
                        if truth is None or got is None:
                            continue
                        if o.type == "binary" and isinstance(truth, bool) and isinstance(got, bool):
                            if truth:
                                sens[(t.id, o.id, grp)].add(_worst(o.sensitivity, act, facts, 1.0, min), 1.0 if got else 0.0)
                            else:
                                spec[(t.id, o.id, grp)].add(_worst(o.specificity, act, facts, 1.0, min), 0.0 if got else 1.0)
                        elif o.type == "categorical":
                            cat_acc[(t.id, o.id, grp)].add(_worst(o.accuracy, act, facts, 1.0, min), 1.0 if got == truth else 0.0)
    ta = tol["checks"]["accuracy"]
    by_test: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (tid, oid, grp), c in sens.items():
        by_test[tid].append(_judge(f"{tid}.{oid}.sensitivity[{grp}]", "realised sensitivity", c, z, ta["pp"], ta["min_n"], state_group=grp))
    for (tid, oid, grp), c in spec.items():
        by_test[tid].append(_judge(f"{tid}.{oid}.specificity[{grp}]", "realised specificity", c, z, ta["pp"], ta["min_n"], state_group=grp))
    for (tid, oid, grp), c in cat_acc.items():
        by_test[tid].append(_judge(f"{tid}.{oid}.accuracy[{grp}]", "realised accuracy (categorical)", c, z, ta["pp"], ta["min_n"], state_group=grp))
    groups = [_group(f"accuracy.{tid}", f"Test {tid}: realised accuracy of its outputs against the catalogue",
                     sorted(by_test[tid], key=lambda c: c["id"])) for tid in catalogue.tests if tid in by_test]
    tn = tol["checks"]["non_diagnostic"]
    nd_cells = [_judge(f"{tid}[{grp}]", "share of non-diagnostic attempts", c, z, tn["pp"], tn["min_n"], state_group=grp)
                for (tid, grp), c in sorted(nd.items())]
    return groups, _group("non_diagnostic", "Non-diagnostic attempts per test against the catalogue's rate", nd_cells)


def _state_consistency(cards, tol) -> dict[str, Any]:
    bad, total = 0, 0
    examples: list[str] = []
    for card in cards:
        base = card.hidden.findings[INITIAL_STATE]
        for state in card.states:
            if state == INITIAL_STATE:
                continue
            total += 1
            resolved = _resolved_ids(card, state)
            problems = []
            for vid, f in card.hidden.findings[state].items():
                if f.value is True and base.get(vid) is not None and base[vid].value is not True:
                    problems.append(f"{vid} true after resolution but not at first contact")
                if f.value is not None and set(f.caused_by) & resolved:
                    problems.append(f"{vid} still caused by a resolved illness")
            if problems:
                bad += 1
                if len(examples) < 5:
                    examples.append(f"{card.id} {state}: {problems[0]}")
    return _share_check("state_consistency", "Resolved states keep the rules of resolution", bad, total,
                        tol["checks"]["state_consistency"]["max_share"], "resolved states with a violation", examples=examples)


def _resolved_ids(card: Card, state: str) -> set[str]:
    ids = [c.id for c in card.hidden.conditions]
    # an illness has a ``<id>_resolved`` state on the card; a cancer never does
    ill = tuple(s[: -len("_resolved")] for s in card.states if s.endswith("_resolved") and s != "all_resolved")
    try:
        return set(resolved_in_state(state, ill)) & set(ids)
    except ValueError:
        return set()


def _presenting(cards, catalogue, tol) -> dict[str, Any]:
    bad, total = 0, 0
    examples: list[str] = []
    for card in cards:
        for state, p in card.presenting.items():
            for vid in p.reported:
                total += 1
                f = card.hidden.findings[state].get(vid)
                v = catalogue.variables.get(vid)
                if f is None or f.value is not True or v is None or v.kind != "symptom":
                    bad += 1
                    if len(examples) < 5:
                        examples.append(f"{card.id} {state}: reports {vid}")
    return _share_check("presenting", "Presenting complaints are true symptoms", bad, total,
                        tol["checks"]["presenting"]["max_share"], "reported complaints that are not true symptoms", examples=examples)


def _diversity(cards, tol) -> dict[str, Any]:
    seen: set[str] = set()
    dup, same_findings = 0, 0
    seen_f: set[str] = set()
    for card in cards:
        f = {v: x.value for v, x in card.hidden.findings[INITIAL_STATE].items()}
        kf = json.dumps(f, sort_keys=True)
        k = json.dumps([card.background, kf], sort_keys=True)
        dup += k in seen
        same_findings += kf in seen_f
        seen.add(k)
        seen_f.add(kf)
    return _share_check("diversity", "Near-duplicate cards (identical background and findings at first contact)", dup,
                        len(cards), tol["checks"]["diversity"]["max_share"], "cards that repeat an earlier card",
                        identical_findings_only=same_findings)


def _leak(cards, catalogue, tol) -> dict[str, Any]:
    from .validate import _Checker                              # the validator's own rule 8, run alone (fast)
    flagged = {"notes": 0, "presenting": 0, "reports": 0}
    notes_total = 0
    for card in cards:
        notes_total += len(card.notes)
        ck = _Checker(card_to_json(card), catalogue)
        ck.r8_notes()
        for p, _ in ck.found:
            if p.code != "card_reveals_condition":
                continue
            path = p.path or ""
            flagged["notes" if path.startswith("notes[") else "presenting" if path.startswith("presenting") else "reports"] += 1
    return _share_check("leak", "Notes that name the hidden diagnosis without a revealing fact", flagged["notes"], notes_total,
                        tol["checks"]["leak"]["max_share"], "notes flagged by the validator's leak rule",
                        presenting_texts_flagged=flagged["presenting"], reports_flagged=flagged["reports"])


# ============================================================================ background realism (review w7, M4)

_BG_DEFAULTS = {"pp": 5.0, "min_n": 20, "max_share": 0.0, "max_under_50": 0.10}


def _background_realism(cards, catalogue, tol) -> dict[str, Any]:
    """Is the background of the cards a possible, plausible population? Hard rules (no violation accepted):
    pack-years that cannot fit in the card's age (more than two packs a day since age 13), never-smokers with
    pack-years. Against the population file (``params/population_<catalogue id>.yaml``, patient_engine/population.py),
    with the expectation of each card given its own age, sex and primary condition: the share of each smoking
    status in the library, and for each condition with ``min_n`` cards the share aged 65 and over and under 50.
    Plain rule: at most ``max_under_50`` of lung-cancer cards under 50 (Finland: a few percent). Without a
    population file only the hard rules run."""
    from .population import STATUSES, get_model
    t = {**_BG_DEFAULTS, **tol["checks"].get("background_realism", {})}
    z = float(tol["z"])
    model = get_model(catalogue)
    cells: list[dict[str, Any]] = []
    smokers = [c for c in cards if "pack_years" in c.background and "age" in c.background]
    cap = (lambda a: model.max_pack_years(a)) if model else (lambda a: 2.0 * max(0.0, a - 13))
    imp = [c for c in smokers if c.background["pack_years"] > cap(c.background["age"]) + 1e-9]
    cells += _share_check("background_realism.pack_years_possible", "", len(imp), len(smokers), t["max_share"],
                          "cards with more pack-years than the age allows (two packs a day from age 13)",
                          examples=[c.id for c in imp[:3]])["cells"]
    nev = [c for c in cards if c.background.get("smoking_status") == "never"]
    bad = [c for c in nev if c.background.get("pack_years", 0)]
    cells += _share_check("background_realism.never_smoker_pack_years", "", len(bad), len(nev), t["max_share"],
                          "never-smokers with pack-years", examples=[c.id for c in bad[:3]])["cells"]
    if model is not None:
        mix = [_Cell() for _ in STATUSES]
        by_cond: dict[str, list] = defaultdict(list)
        for c in cards:
            bg, cond = c.background, c.hidden.primary.id
            if bg.get("smoking_status") not in STATUSES or "age" not in bg or bg.get("sex") not in model.sexes:
                continue
            probs = model.smoking_probs_given(bg["age"], bg["sex"], cond)
            for i, s in enumerate(STATUSES):
                mix[i].add(probs[i], float(bg["smoking_status"] == s))
            by_cond[cond].append(c)
        cells += [_judge(f"background_realism.smoking.{s}", "share", mix[i], z, t["pp"], int(t["min_n"]))
                  for i, s in enumerate(STATUSES)]
        b65, b50 = model.band(65), model.band(50)
        for cond, group in sorted(by_cond.items()):
            old, young = _Cell(), _Cell()
            for c in group:
                bg = c.background
                pb = model.age_band_probs_given(bg["smoking_status"], bg["sex"], cond)
                a = bg["age"]
                old.add(sum(pb[b65:]), float(a >= 65))
                young.add(sum(pb[:b50]), float(a < 50))
            cells.append(_judge(f"background_realism.age_65_plus.{cond}", "share", old, z, t["pp"], int(t["min_n"])))
            cells.append(_judge(f"background_realism.age_under_50.{cond}", "share", young, z, t["pp"], int(t["min_n"])))
    lc = [c for c in cards if catalogue.conditions[c.hidden.primary.id].cls == "cancer" and "age" in c.background]
    if len(lc) >= int(t["min_n"]):
        cells += _share_check("background_realism.cancer_under_50", "", sum(c.background["age"] < 50 for c in lc), len(lc),
                              t["max_under_50"], "cancer cards under 50")["cells"]
    return _group("background_realism", "Background realism: possible pack-years, smoking mix and age profile", cells)


# ============================================================================ the audit

def audit_library(library, catalogue, tolerances: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Audit a loaded ``Library`` against ``catalogue``. Returns the report dict (``audit/1``)."""
    tol = dict(tolerances) if tolerances is not None else load_tolerances(None)
    if library.manifest.catalogue_hash != catalogue.version_hash:
        raise AuditError(f"library {library.id} was made for catalogue hash {library.manifest.catalogue_hash[:12]}, "
                         f"not {catalogue.version_hash[:12]}")
    t0 = time.monotonic()
    cards = library.cards
    z = float(tol["z"])
    acc, nd = _accuracy_and_nondiagnostic(cards, catalogue, tol, z)
    checks = [*_findings_cells(cards, catalogue, tol, z), *acc, nd, _state_consistency(cards, tol),
              _presenting(cards, catalogue, tol), _diversity(cards, tol), _leak(cards, catalogue, tol),
              _background_realism(cards, catalogue, tol)]
    n_states: dict[str, int] = defaultdict(int)
    for c in cards:
        for s in c.states:
            n_states[s] += 1
    failed = [c["id"] for c in checks if c["status"] == "fail"]
    m = library.manifest
    return {
        "format": AUDIT_FORMAT, "library_id": m.id, "catalogue_id": m.catalogue_id, "catalogue_hash": m.catalogue_hash,
        "generator": m.generator, "model": m.model, "error_source": m.error_source, "n_cards": len(cards),
        "cards_by_condition": dict(m.card_count_by_condition), "states": dict(sorted(n_states.items())),
        "tolerances": {"z": z, "checks": tol["checks"]},
        "passed": not failed, "failed_checks": failed, "checks": checks,
        "not_audited": NOT_AUDITED, "seconds": round(time.monotonic() - t0, 2),
    }


NOT_AUDITED = [
    "Measurement error of continuous outputs (reported value against the true value): not compared with the catalogue's error_sd.",
    "Frequencies of findings in resolved states and on cards with a co-existing illness: the catalogue gives no single reference number for a mixture of causes. Those cards and states are covered by accuracy.*, non_diagnostic, state_consistency and presenting.",
    "Correlation between repeated attempts of one test on one card: attempts are treated as independent, so a model-written library whose repeats agree too closely has intervals that are too narrow.",
    "Free text (notes, reports) beyond the validator's leak rule.",
]


# ============================================================================ output

def render_markdown(report: Mapping[str, Any]) -> str:
    r = report
    verdict = "PASS" if r["passed"] else "FAIL"
    L = [f"# Library audit: {verdict}", "",
         f"Library `{r['library_id']}` ({r['n_cards']} cards, generator `{r['generator']}`"
         + (f", model `{r['model']}`" if r.get("model") else "") + f", error source `{r['error_source']}`), "
         f"catalogue `{r['catalogue_id']}` (`{r['catalogue_hash'][:12]}`).", "",
         f"States: " + ", ".join(f"{k} {v}" for k, v in r["states"].items()) + ". "
         "Accuracy and non-diagnostic checks use every state (all_active and the resolved states pooled as `resolved`); "
         "frequency checks use `all_active` of single-illness cards.", "",
         f"Tolerance: a cell fails when it is outside the {r['tolerances']['z']:.4g}-sigma interval and more than the check's "
         "percentage points from the catalogue's expectation. See `audit_tolerances.yaml` for each number and its reason.", "",
         "| Check | Result | Detail |", "|---|---|---|"]
    for c in r["checks"]:
        L.append(f"| `{c['id']}` | {c['status'].upper()} | {c['summary']} |")
    fails = [(c, x) for c in r["checks"] for x in c["cells"] if x["status"] == "fail"]
    if fails:
        L += ["", "## Failed cells", "", "| Check | Cell | n | Expected | Observed | 99% interval | Off (pp) |", "|---|---|---|---|---|---|---|"]
        for c, x in fails:
            if x["kind"] == "share":
                L.append(f"| `{c['id']}` | {x['id']} | {x['n']} | at most {x['max_share']:.2%} | {x['share']:.2%} | | |")
                for e in x.get("examples", []):
                    L.append(f"| | e.g. {e} | | | | | |")
            else:
                L.append(f"| `{c['id']}` | {x['id']} | {x['n']} | {x['expected']:.3f} | {x['observed']:.3f} | {x['lo']:.3f} to {x['hi']:.3f} | {x['off_pp']:+.1f} |")
    skipped = sum(c["n_skipped"] for c in r["checks"])
    L += ["", f"{skipped} cell(s) skipped for too few cases (not counted as pass or fail).", "", "## Not audited", ""]
    L += [f"- {s}" for s in r["not_audited"]]
    L += ["", f"Computed in {r['seconds']} s. Full cells (expected, observed, interval) are in `audit.json`.", ""]
    return "\n".join(L)


def write_audit(report: Mapping[str, Any], directory: str | Path) -> tuple[Path, Path]:
    """Write ``audit.json`` and ``audit.md`` into ``directory``."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    j, m = d / "audit.json", d / "audit.md"
    j.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    m.write_text(render_markdown(report))
    return j, m

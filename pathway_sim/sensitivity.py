"""One-at-a-time and joint sensitivity of "flowchart B beats flowchart A" to the scenario's assumptions.

Every numeric parameter tagged ``source: assumption`` (plus a few the notes call assumptions, see
``EXTRA``) is varied low / high (default x0.75 / x1.25; integer capacities +-1 for 1-4 slots,
+-25% above; a lognormal ``median`` keeps its p90/median ratio as in ``calibrate.set_path``). Each
variant reruns the *same patients* (hash-based common random numbers) through flowcharts A and B and
reports the headline metrics of A, of B and of the gain B - A (share within target in pp, median days).

    python -m pathway_sim.sensitivity scenarios/generated/stokstad_calibrated.yaml \\
        --compare observed,optimal --compare faster_pet,optimal --n 1000 --seeds 1,2,3 --draws 150 \\
        --out docs/sensitivity_stokstad.json

Three views are produced: a tornado (one parameter at a time, sorted by the swing of the gain), a joint
Monte Carlo (all parameters drawn together, uniform between low and high; share of draws where B still
beats A, plus Spearman rank correlation of each parameter with the gain) and a seed-noise floor.
If the scenario has a ``calibration`` block, variants whose calibration flowchart leaves the published
target band are flagged (a one-at-a-time change that breaks the fit to the observed pathway is not a
plausible world), and the joint draws are also summarised on the subset that still reproduces it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import re
import time
from pathlib import Path
from statistics import mean, median, pstdev

import yaml

from .engine import simulate
from .metrics import compute_metrics
from .patients import generate_patients
from .scenario import scenario_from_dict

SKIP_FIELDS = {"service_days", "cost_eur", "weekdays_only", "weekdays", "note", "source", "kind", "stage",
               "resource", "type", "label", "reveals", "invasive", "confirms_diagnosis"}

# Parameters whose notes call them assumptions but whose block is tagged with a source id (or that have base
# value 0, so they need absolute bounds). (id, label, kind, leaves, rel_or_bounds)
EXTRA = {
    "stokstad": [
        ("tests.bronchoscopy.wait.median", "bronchoscopy wait median (calibrated)", "median", ["tests.bronchoscopy.wait.median"], 0.25),
        ("tests.first_visit.extra_wait.median", "CT report not ready at first visit, extra wait median (calibrated)", "median",
         ["tests.first_visit.extra_wait.median"], 0.25),
        ("treatment_wait_after_board", "wait from tumour board to surgery / RT start (calibrated, joint)", "median",
         ["tests.surgery_booking.wait.median", "tests.radiotherapy_booking.wait.median"], 0.25),
        ("resources.tumour_board.cutoff_days", "tumour-board cutoff (days before the meeting, calibrated)", "abs",
         ["resources.tumour_board.cutoff_days"], (0.0, 2.0)),
        ("sampling_nondiagnostic", "non-diagnostic rate of bronchoscopy / needle biopsy (all, joint)", "prob",
         ["tests.bronchoscopy.p_nondiagnostic.central", "tests.bronchoscopy.p_nondiagnostic.peripheral",
          "tests.bronchoscopy_repeat.p_nondiagnostic.central", "tests.bronchoscopy_repeat.p_nondiagnostic.peripheral",
          "tests.ttnb.p_nondiagnostic.central", "tests.ttnb.p_nondiagnostic.peripheral"], 0.25),
        ("tests.pet_ct.wait.median", "PET-CT wait before the scanner, derived from the published 20.5 d referral-to-report", "median",
         ["tests.pet_ct.wait.median", "tests.pet_ct_late.wait.median"], 0.25),
    ],
}

# Default parameter shortlists (regex on parameter id) for scenarios too slow to run in full.
SHORTLIST = {
    "finland_lung": [
        r"^resources\.(clinic|ct_scanner|bronchoscopy|ttnb_slot|pet_scanner|treatment_slot)\.capacity_per_day$",
        r"^resources\.(clinic|ct_scanner|bronchoscopy|pet_scanner|treatment_slot)\.min_lead_days$",
        r"^resources\.(clinic|ct_scanner)\.urgent_lead_days$",
        r"^tests\.(treatment_booking)\.extra_wait\.median$",
        r"^tests\.(gp_represent)\.extra_wait\.median$",
        r"^tests\.(gp_second_look)\.wait\.median$",
        r"^tests\.chest_ct\.report_days\.median$",
        r"^tests\.(nurse_assessment|gp_assessment|gp_second_look|symptoms_persist)\.p_positive\[cancer\]$",
        r"^tests\.(specialist_visit|chest_ct)\.p_positive\[non-cancer\]$",
        r"^arrivals\.rate_per_day$",
        r"^attributes\.location\.central$",
        r"^policy\.sample_choice\.bronch$",
    ],
}
REL_OVERRIDE = {"arrivals.rate_per_day": 0.10}


# --------------------------------------------------------------------------------------------- raw helpers
def _walk(raw, keys):
    d = raw
    for k in keys:
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def _get(raw, path):
    return _walk(raw, path.split("."))


def _set(raw, path, v):
    keys = path.split(".")
    d = _walk(raw, keys[:-1])
    k = keys[-1]
    if isinstance(d, list):
        d[int(k)] = v
        return
    if k == "median" and "p90" in d and d.get("median"):
        d["p90"] = v * float(d["p90"]) / float(d["median"])
    d[k] = v


def _int_bounds(b, rel):
    if b <= 4:
        return max(1, b - 1), b + 1
    return max(1, int(round(b * (1 - rel)))), int(round(b * (1 + rel)))


class Param:
    """One varied quantity. ``t`` in [-1, 1]: -1 low, 0 base, +1 high; values interpolate linearly."""

    def __init__(self, pid, label, kind, leaves, raw, rel=0.25, bounds=None, source="assumption", extra_int_leaves=()):
        self.id, self.label, self.kind, self.leaves, self.rel, self.bounds = pid, label, kind, list(leaves), rel, bounds
        self.source = source
        self.base = {p: _get(raw, p) for p in self.leaves}
        self.int_leaves = list(extra_int_leaves)
        self.base.update({p: _get(raw, p) for p in self.int_leaves})

    def _val(self, leaf, t):
        b = self.base[leaf]
        k = self.kind
        if k == "int":
            lo, hi = _int_bounds(int(b), self.rel)
            v = lo + (b - lo) * (1 + t) if t <= 0 else b + (hi - b) * t
            return max(1, int(round(v)))
        if k == "abs":
            lo, hi = self.bounds
            return lo + (hi - lo) * (t + 1) / 2 if abs(t) > 1e-12 else b
        f = 1 + self.rel * t
        if k == "prob":
            return min(1.0, max(0.0, b * f))
        return b * f                                              # float / median

    def apply(self, raw, t):
        if abs(t) < 1e-12 and self.kind != "abs":
            return
        if self.kind == "share":
            tot = sum(float(self.base[p]) for p in self.leaves)
            s0 = float(self.base[self.leaves[0]]) / tot
            s = min(1.0, max(0.0, s0 * (1 + self.rel * t)))
            _set(raw, self.leaves[0], tot * s)
            _set(raw, self.leaves[1], tot * (1 - s))
            return
        for p in self.leaves + self.int_leaves:
            kind_save = self.kind
            if p in self.int_leaves:
                self.kind = "int"
            _set(raw, p, self._val(p, t))
            self.kind = kind_save

    def shown(self, t):
        p = self.leaves[0]
        if self.kind == "share":
            tot = sum(float(self.base[q]) for q in self.leaves)
            s0 = float(self.base[p]) / tot
            return round(min(1.0, max(0.0, s0 * (1 + self.rel * t))), 4)
        v = self.base[p] if abs(t) < 1e-12 and self.kind != "abs" else self._val(p, t)
        return round(v, 4) if isinstance(v, float) else v


# --------------------------------------------------------------------------------------------- discovery
def discover(raw: dict) -> list[Param]:
    sid = raw.get("id")
    conds = raw.get("conditions", [])
    cancer = {c["id"] for c in conds if c.get("cancer")}
    out: list[Param] = []

    def add(*a, **k):
        out.append(Param(*a, raw=raw, **k))

    for sect in ("tests", "resources"):
        for tid, spec in raw.get(sect, {}).items():
            if spec.get("source") != "assumption":
                continue
            for fld, val in spec.items():
                if fld in SKIP_FIELDS:
                    continue
                base = f"{sect}.{tid}.{fld}"
                if fld in ("wait", "extra_wait", "report_days"):
                    if isinstance(val, dict) and val.get("median"):
                        add(f"{base}.median", f"{tid}: {fld} median", "median", [f"{base}.median"])
                    elif isinstance(val, (int, float)) and val > 0:
                        add(base, f"{tid}: {fld}", "float", [base])
                elif fld == "p_positive" and isinstance(val, dict):
                    for tag, keys in (("cancer", [c for c in val if c in cancer]),
                                      ("non-cancer", [c for c in val if c not in cancer and c != "default"])):
                        keys = [c for c in keys if isinstance(val[c], (int, float)) and val[c] > 0]
                        if keys:
                            add(f"{base}[{tag}]", f"{tid}: P(positive), {tag} conditions", "prob", [f"{base}.{c}" for c in keys])
                elif fld == "p_nondiagnostic" and isinstance(val, dict):
                    keys = [c for c in val if c != "by" and isinstance(val[c], (int, float))]
                    add(base, f"{tid}: non-diagnostic rate", "prob", [f"{base}.{c}" for c in keys])
                elif fld == "capacity_per_day":
                    ov = [f"flowcharts.{fid}.resource_overrides.{tid}.capacity_per_day"
                          for fid, fc in raw.get("flowcharts", {}).items()
                          if tid in (fc.get("resource_overrides") or {}) and "capacity_per_day" in fc["resource_overrides"][tid]]
                    add(base, f"{tid}: slots per day" + (" (also the flowchart capacity overrides)" if ov else ""), "int", [base],
                        extra_int_leaves=ov)
                elif fld in ("min_lead_days", "urgent_lead_days"):
                    add(base, f"{tid}: {fld}", "float", [base])
    for name, spec in raw.get("attributes", {}).items():
        vals = spec.get("values", {})
        if spec.get("source") == "assumption" and len(vals) == 2:
            ks = list(vals)
            add(f"attributes.{name}.{ks[0]}", f"attribute {name}: share {ks[0]} (rest {ks[1]})", "share",
                [f"attributes.{name}.values.{ks[0]}", f"attributes.{name}.values.{ks[1]}"])
    # Non-cancer prevalences are not varied: they must sum to 1 with the sourced cancer prevalences, so scaling them only
    # changes the cancer share of presenters (a county-size question, covered by arrivals.rate_per_day).
    if raw.get("arrivals_source", {}).get("source") == "assumption" and "rate_per_day" in raw.get("arrivals", {}):
        add("arrivals.rate_per_day", "arrivals per day (county size)", "float", ["arrivals.rate_per_day"], rel=REL_OVERRIDE["arrivals.rate_per_day"])
    seen = set()
    for fid, fc in raw.get("flowcharts", {}).items():
        for pname, pspec in (fc.get("policy") or {}).items():
            mix = pspec.get("mix") if isinstance(pspec, dict) else None
            if not mix or pspec.get("source") != "assumption" or len(mix) != 2:
                continue
            k0 = list(mix)[0]
            pid = f"policy.{pname}.{k0}"
            if pid in seen:
                continue
            seen.add(pid)
            leaves = [f"flowcharts.{f}.policy.{pname}.mix.{k}" for f, c in raw["flowcharts"].items()
                      for k in list(mix) if (c.get("policy") or {}).get(pname, {}).get("mix", {}).get(k) is not None
                      and (c["policy"][pname].get("source") == "assumption")]
            # one param, same share applied to every flowchart that carries this policy (leaves in pairs)
            out.append(_MultiShare(pid, f"policy {pname}: share {k0} (rest {list(mix)[1]}), all flowcharts", leaves, raw))
    for pid, label, kind, leaves, r in EXTRA.get(sid, []):
        if any(p.id == pid for p in out):
            continue
        if kind == "abs":
            add(pid, label, kind, leaves, bounds=r)
        else:
            add(pid, label, kind, leaves, rel=r)
    for p in out:
        p.rel = REL_OVERRIDE.get(p.id, p.rel)
    return out


class _MultiShare(Param):
    """Mix share applied to several flowcharts: leaves come in (main, rest) pairs per flowchart."""

    def __init__(self, pid, label, leaves, raw):
        super().__init__(pid, label, "share", leaves, raw)
        self.pairs = [(leaves[i], leaves[i + 1]) for i in range(0, len(leaves), 2)]

    def apply(self, raw, t):
        if abs(t) < 1e-12:
            return
        for a, b in self.pairs:
            tot = float(self.base[a]) + float(self.base[b])
            s0 = float(self.base[a]) / tot if tot else 0.5
            s = min(1.0, max(0.0, s0 * (1 + self.rel * t)))
            _set(raw, a, tot * s)
            _set(raw, b, tot * (1 - s))

    def shown(self, t):
        a, b = self.pairs[0]
        tot = float(self.base[a]) + float(self.base[b])
        s0 = float(self.base[a]) / tot if tot else 0.5
        return round(min(1.0, max(0.0, s0 * (1 + self.rel * t))), 4)


def select(params: list[Param], only: list[str] | None, scenario_id: str, use_all: bool = False) -> list[Param]:
    pats = only if only else (None if use_all else SHORTLIST.get(scenario_id))
    if not pats:
        return params
    rx = [re.compile(p) for p in pats]
    return [p for p in params if any(r.search(p.id) for r in rx)]


# --------------------------------------------------------------------------------------------- evaluation
_PATIENT_KEYS = ("conditions", "groups", "attributes", "age", "arrivals")


class Evaluator:
    """Runs flowcharts on a (possibly modified) raw scenario with a patient cache across variants."""

    def __init__(self, raw: dict, flowcharts: list[str], n: int, seeds: list[int]):
        self.raw, self.flowcharts, self.n, self.seeds = raw, list(flowcharts), n, list(seeds)
        self._cache: dict = {}
        self.runs = 0

    def _patients(self, r: dict, sc, seed: int):
        spec = {k: r.get(k) for k in _PATIENT_KEYS}
        spec["tests"] = {t: (v.get("p_positive"), v.get("p_nondiagnostic")) for t, v in r["tests"].items()}
        key = (hashlib.md5(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest(), seed, self.n)
        if key not in self._cache:
            if len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = generate_patients(sc, self.n, seed)
        return self._cache[key]

    def run(self, params: list[Param] = (), ts: dict | None = None, seeds: list[int] | None = None, mutate=None) -> dict:
        r = copy.deepcopy(self.raw)
        ts = ts or {}
        for p in params:
            if p.id in ts:
                p.apply(r, ts[p.id])
        if mutate:
            mutate(r)
        sc = scenario_from_dict(r)
        per = {f: [] for f in self.flowcharts}
        for s in (seeds or self.seeds):
            pts = self._patients(r, sc, s)
            for f in self.flowcharts:
                per[f].append(compute_metrics(simulate(sc, f, pts, seed=s), sc))
                self.runs += 1
        return {f: summarise(ms) for f, ms in per.items()}


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summarise(ms: list[dict]) -> dict:
    out = {"share": _avg([m["share_within_target"] for m in ms]), "median": _avg([m["median_days_to_treatment"] for m in ms]),
           "mean": _avg([m["mean_days_to_treatment"] for m in ms]), "missed": _avg([m["missed_cancers"] for m in ms]),
           "untreated": _avg([m["untreated_cancers"] for m in ms]), "n_cancer": _avg([m["n_cancer"] for m in ms]),
           "tests_per_patient": _avg([m["tests_per_patient"] for m in ms]), "by_group": {}}
    for g in ms[0]["by_group"]:
        out["by_group"][g] = {k: _avg([m["by_group"][g][k] for m in ms]) for k in
                              ("n_cancer", "median_days_to_treatment", "share_within_target", "missed_cancers")}
    return out


def _gain(res, a, b):
    A, B = res[a], res[b]
    return {"share_pp": 100 * (B["share"] - A["share"]), "days": B["median"] - A["median"]}


def _calib_ok(res, raw):
    cal = raw.get("calibration")
    if not cal:
        return None
    m = res[cal["flowchart"]]
    key = {"share_within_target": "share", "median_days_to_treatment": "median"}
    return all(abs(m[key[k]] - t) <= tol for k, (t, tol) in cal["targets"].items() if k in key)


def _r(x, d=2):
    return None if x is None else round(x, d)


def _brief(res, flows):
    return {f: {"share": _r(100 * res[f]["share"], 1), "median": _r(res[f]["median"], 1),
                "untreated": _r(res[f]["untreated"], 1)} for f in flows}


# --------------------------------------------------------------------------------------------- analyses
def tornado(raw, ev: Evaluator, params, pairs, log=print):
    flows = ev.flowcharts
    base = ev.run()
    rows = []
    for i, p in enumerate(params):
        t0 = time.time()
        lo, hi = ev.run(params, {p.id: -1.0}), ev.run(params, {p.id: +1.0})
        row = {"param": p.id, "label": p.label, "kind": p.kind, "base": p.shown(0.0), "low": p.shown(-1.0), "high": p.shown(1.0),
               "calibration_ok": {"low": _calib_ok(lo, raw), "high": _calib_ok(hi, raw)}, "flowcharts": {"low": _brief(lo, flows), "high": _brief(hi, flows)}}
        for a, b in pairs:
            gl, gh, g0 = _gain(lo, a, b), _gain(hi, a, b), _gain(base, a, b)
            unstable = any(res[f]["median"] is not None and base[f]["median"] and res[f]["median"] > 1.5 * base[f]["median"]
                           for res in (lo, hi) for f in (a, b))
            row[f"{a}>{b}"] = {
                "A_low": _r(100 * lo[a]["share"], 1), "A_high": _r(100 * hi[a]["share"], 1),
                "B_low": _r(100 * lo[b]["share"], 1), "B_high": _r(100 * hi[b]["share"], 1),
                "A_median_low": _r(lo[a]["median"], 1), "A_median_high": _r(hi[a]["median"], 1),
                "B_median_low": _r(lo[b]["median"], 1), "B_median_high": _r(hi[b]["median"], 1),
                "gain_pp_low": _r(gl["share_pp"], 1), "gain_pp_high": _r(gh["share_pp"], 1), "gain_pp_base": _r(g0["share_pp"], 1),
                "gain_days_low": _r(gl["days"], 1), "gain_days_high": _r(gh["days"], 1), "gain_days_base": _r(g0["days"], 1),
                "swing_pp": _r(abs(gh["share_pp"] - gl["share_pp"]), 1), "swing_days": _r(abs(gh["days"] - gl["days"]), 1),
                "worst_gain_pp": _r(min(gl["share_pp"], gh["share_pp"]), 1),
                "gain_vanishes": bool(min(gl["share_pp"], gh["share_pp"]) <= 0), "unstable": bool(unstable),
            }
        rows.append(row)
        log(f"  [{i + 1}/{len(params)}] {p.id}  ({time.time() - t0:.0f}s)")
    out = {"base": _brief(base, flows), "base_full": {f: base[f] for f in flows}, "pairs": {}}
    for a, b in pairs:
        k = f"{a}>{b}"
        srt = sorted(rows, key=lambda r: -(r[k]["swing_pp"] or 0))
        out["pairs"][k] = {"base_gain_pp": _r(_gain(base, a, b)["share_pp"], 1), "base_gain_days": _r(_gain(base, a, b)["days"], 1),
                           "order": [r["param"] for r in srt]}
    out["rows"] = rows
    return out


def noise(ev: Evaluator, pairs, seeds):
    per = []
    for s in seeds:
        per.append(ev.run(seeds=[s]))
    out = {}
    for a, b in pairs:
        g = [_gain(r, a, b) for r in per]
        out[f"{a}>{b}"] = {"seeds": list(seeds), "gain_pp": [_r(x["share_pp"], 1) for x in g], "gain_days": [_r(x["days"], 1) for x in g],
                           "sd_pp_single_seed": _r(pstdev([x["share_pp"] for x in g]) * math.sqrt(len(g) / max(1, len(g) - 1)), 2) if len(g) > 1 else None,
                           "sd_days_single_seed": _r(pstdev([x["days"] for x in g]) * math.sqrt(len(g) / max(1, len(g) - 1)), 2) if len(g) > 1 else None}
    return out


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for k, i in enumerate(order):
        r[i] = k
    return r


def spearman(x, y):
    if len(x) < 4 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = _rank(x), _rank(y)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def joint(raw, ev: Evaluator, params, pairs, draws: int, rng_seed: int = 7, log=print):
    rng = random.Random(rng_seed)
    recs = []
    for d in range(draws):
        ts = {p.id: rng.uniform(-1, 1) for p in params}
        res = ev.run(params, ts)
        rec = {"ts": {k: round(v, 3) for k, v in ts.items()}, "calibration_ok": _calib_ok(res, raw), "flowcharts": _brief(res, ev.flowcharts)}
        for a, b in pairs:
            g = _gain(res, a, b)
            rec[f"{a}>{b}"] = {"gain_pp": _r(g["share_pp"], 2), "gain_days": _r(g["days"], 2)}
        recs.append(rec)
        if (d + 1) % 10 == 0:
            log(f"  draw {d + 1}/{draws}")
    summ = {}
    for a, b in pairs:
        k = f"{a}>{b}"

        def stats(sub):
            gp = [r[k]["gain_pp"] for r in sub]
            gd = [r[k]["gain_days"] for r in sub]
            if not gp:
                return None
            return {"draws": len(sub), "p_B_better_share": _r(sum(1 for x in gp if x > 0) / len(gp), 3),
                    "p_B_faster_median": _r(sum(1 for x in gd if x < 0) / len(gd), 3),
                    "gain_pp": {"min": _r(min(gp), 1), "p5": _r(_pct(gp, .05), 1), "median": _r(median(gp), 1), "p95": _r(_pct(gp, .95), 1), "max": _r(max(gp), 1)},
                    "gain_days": {"min": _r(min(gd), 1), "p5": _r(_pct(gd, .05), 1), "median": _r(median(gd), 1), "p95": _r(_pct(gd, .95), 1), "max": _r(max(gd), 1)}}

        sp = {p.id: _r(spearman([r["ts"][p.id] for r in recs], [r[k]["gain_pp"] for r in recs]), 2) for p in params}
        ok = [r for r in recs if r["calibration_ok"]]
        summ[k] = {"all": stats(recs), "calibration_consistent": stats(ok) if raw.get("calibration") else None,
                   "spearman_with_gain_pp": dict(sorted(sp.items(), key=lambda kv: -abs(kv[1] or 0)))}
    return {"draws": recs, "summary": summ}


# --------------------------------------------------------------------------------------------- equity (F4)
EQUITY_FLOWS = ["baseline", "bundled_workup", "fast_track_nonspecific"]
PARITY = {  # detection of non-specific presenters set equal to site-specific ones (no gap by construction)
    "tests.gp_assessment.p_positive.lung_cancer_nonspec": 0.97, "tests.nurse_assessment.p_positive.lung_cancer_nonspec": 0.45,
    "tests.gp_second_look.p_positive.lung_cancer_nonspec": 0.55, "tests.symptoms_persist.p_positive.lung_cancer_nonspec": 0.95,
    "tests.gp_represent.p_positive.lung_cancer_nonspec": 0.98,
}


def equity_params(raw: dict) -> list[Param]:
    T = "tests."
    spec = [
        ("gp_img_nonspec", "GP orders imaging at the first visit, non-specific cancers (0.45)", "prob",
         [T + "gp_assessment.p_positive.lung_cancer_nonspec"], 0.25),
        ("gp_img_site", "GP orders imaging at the first visit, site-specific cancers (0.97)", "prob",
         [T + "gp_assessment.p_positive.lung_cancer_site"], 0.25),
        ("nurse_img_nonspec", "nurse orders imaging, non-specific cancers (0.15)", "prob", [T + "nurse_assessment.p_positive.lung_cancer_nonspec"], 0.25),
        ("nurse_img_site", "nurse orders imaging, site-specific cancers (0.45)", "prob", [T + "nurse_assessment.p_positive.lung_cancer_site"], 0.25),
        ("second_look_nonspec", "GP still refers after a negative film, non-specific (0.10)", "prob", [T + "gp_second_look.p_positive.lung_cancer_nonspec"], 0.25),
        ("second_look_site", "GP still refers after a negative film, site-specific (0.55)", "prob", [T + "gp_second_look.p_positive.lung_cancer_site"], 0.25),
        ("persist_nonspec", "safety net: symptoms persist, non-specific cancers (0.90)", "prob", [T + "symptoms_persist.p_positive.lung_cancer_nonspec"], 0.25),
        ("persist_site", "safety net: symptoms persist, site-specific cancers (0.95)", "prob", [T + "symptoms_persist.p_positive.lung_cancer_site"], 0.25),
        ("represent_nonspec", "safety net: GP refers at re-presentation, non-specific (0.95)", "prob", [T + "gp_represent.p_positive.lung_cancer_nonspec"], 0.25),
        ("represent_timing", "safety net timing: re-presentation interval median (14 d, x0.5 / x1.5)", "median", [T + "gp_represent.extra_wait.median"], 0.5),
        ("site_cancer_share", "group shares: site-specific share of lung cancers (31%)", "share", ["conditions.0.prevalence", "conditions.1.prevalence"], 0.25),
        ("cxr_sensitivity", "chest X-ray sensitivity for cancers (0.754, sourced BRADLEY2021; x0.9 / x1.1)", "prob",
         [T + "chest_xray.p_positive.lung_cancer_site", T + "chest_xray.p_positive.lung_cancer_nonspec"], 0.10),
    ]
    assert raw["conditions"][0]["id"] == "lung_cancer_site" and raw["conditions"][1]["id"] == "lung_cancer_nonspec"
    return [Param(i, l, k, lv, raw, rel=r, source="assumption" if i != "cxr_sensitivity" else "BRADLEY2021") for i, l, k, lv, r in spec]


def _gaps(res, flows):
    out = {}
    for f in flows:
        g = res[f]["by_group"]
        s, n = g["site_specific"], g["non_specific"]
        out[f] = {"site_median": _r(s["median_days_to_treatment"], 1), "nonspec_median": _r(n["median_days_to_treatment"], 1),
                  "gap_days": _r(n["median_days_to_treatment"] - s["median_days_to_treatment"], 1),
                  "site_share": _r(100 * s["share_within_target"], 1), "nonspec_share": _r(100 * n["share_within_target"], 1),
                  "gap_share_pp": _r(100 * (s["share_within_target"] - n["share_within_target"]), 1),
                  "site_missed_pct": _r(100 * s["missed_cancers"] / s["n_cancer"], 1), "nonspec_missed_pct": _r(100 * n["missed_cancers"] / n["n_cancer"], 1)}
    return out


def _delta(gp):
    a = gp["baseline"]
    return {f: {"d_gap_days": _r(gp[f]["gap_days"] - a["gap_days"], 1), "d_gap_share_pp": _r(gp[f]["gap_share_pp"] - a["gap_share_pp"], 1)}
            for f in gp if f != "baseline"}


def equity_sensitivity(path: str = "scenarios/finland_lung.yaml", n: int = 14000, seeds=(1,), draws: int = 16,
                       noise_seeds=(1, 2, 3), log=print) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    ev = Evaluator(raw, EQUITY_FLOWS, n, list(seeds))
    params = equity_params(raw)
    t0 = time.time()

    def pack(res):
        g = _gaps(res, EQUITY_FLOWS)
        return {"gaps": g, "delta": _delta(g), "overall": _brief(res, EQUITY_FLOWS)}

    base = ev.run()
    out = {"scenario": raw["id"], "n": n, "seeds": list(seeds), "target_days": raw["target_days"], "base": pack(base), "rows": []}
    out["noise"] = [pack(ev.run(seeds=[s])) for s in noise_seeds]
    for i, p in enumerate(params):
        lo, hi = ev.run(params, {p.id: -1.0}), ev.run(params, {p.id: 1.0})
        out["rows"].append({"param": p.id, "label": p.label, "source": p.source, "base": p.shown(0), "low": p.shown(-1), "high": p.shown(1),
                            "low_res": pack(lo), "high_res": pack(hi)})
        log(f"  [{i + 1}/{len(params)}] {p.id}")

    def parity(r):
        for k, v in PARITY.items():
            _set(r, k, v)
    out["parity"] = pack(ev.run(mutate=parity))
    rng = random.Random(11)
    recs = []
    for d in range(draws):
        ts = {p.id: rng.uniform(-1, 1) for p in params}
        recs.append({"ts": {k: round(v, 3) for k, v in ts.items()}, **pack(ev.run(params, ts))})
        if (d + 1) % 5 == 0:
            log(f"  draw {d + 1}/{draws}")
    out["joint"] = recs
    allv = [out["base"]] + [r[k] for r in out["rows"] for k in ("low_res", "high_res")] + recs

    def rng_of(vals):
        return {"min": _r(min(vals), 1), "max": _r(max(vals), 1)}
    out["ranges"] = {
        "baseline_gap_days": rng_of([v["gaps"]["baseline"]["gap_days"] for v in allv]),
        "baseline_gap_share_pp": rng_of([v["gaps"]["baseline"]["gap_share_pp"] for v in allv]),
        "baseline_nonspec_median": rng_of([v["gaps"]["baseline"]["nonspec_median"] for v in allv]),
        "baseline_site_median": rng_of([v["gaps"]["baseline"]["site_median"] for v in allv]),
        "baseline_nonspec_share": rng_of([v["gaps"]["baseline"]["nonspec_share"] for v in allv]),
        "baseline_site_share": rng_of([v["gaps"]["baseline"]["site_share"] for v in allv]),
        "baseline_missed_nonspec_pct": rng_of([v["gaps"]["baseline"]["nonspec_missed_pct"] for v in allv]),
        "baseline_missed_site_pct": rng_of([v["gaps"]["baseline"]["site_missed_pct"] for v in allv]),
    }
    for f in EQUITY_FLOWS[1:]:
        dd = [v["delta"][f]["d_gap_days"] for v in allv]
        ds = [v["delta"][f]["d_gap_share_pp"] for v in allv]
        jd = [v["delta"][f]["d_gap_days"] for v in recs]
        out["ranges"][f] = {"d_gap_days": rng_of(dd), "d_gap_share_pp": rng_of(ds),
                            "share_of_all_variants_narrowing_days": _r(sum(1 for x in dd if x < 0) / len(dd), 2),
                            "share_of_joint_draws_narrowing_days": _r(sum(1 for x in jd if x < 0) / max(1, len(jd)), 2),
                            "share_of_all_variants_narrowing_share": _r(sum(1 for x in ds if x < 0) / len(ds), 2)}
    out["runtime_s"] = round(time.time() - t0, 1)
    return out


# --------------------------------------------------------------------------------------------- output
def markdown(result: dict, top: int = 15) -> str:
    lines = [f"### {result['scenario']}  (n={result['n']}, seeds={result['seeds']}, {result['n_params']} parameters, "
             f"{result['runtime_s']:.0f} s)", ""]
    rows = {r["param"]: r for r in result["tornado"]["rows"]}
    for key, info in result["tornado"]["pairs"].items():
        a, b = key.split(">")
        lines += [f"**{a} -> {b}**: base gain {info['base_gain_pp']:+.1f} pp share within target, {info['base_gain_days']:+.1f} d median. "
                  f"Seed noise (sd of the gain, one seed): {result['noise'][key]['sd_pp_single_seed']} pp, {result['noise'][key]['sd_days_single_seed']} d.", "",
                  "| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |",
                  "|---|---|---|---|---|---|---|---|"]
        for pid in info["order"][:top]:
            r = rows[pid]
            x = r[key]
            fl = []
            if x["gain_vanishes"]:
                fl.append("gain <= 0")
            if x["unstable"]:
                fl.append("queue blow-up")
            if r["calibration_ok"]["low"] is False or r["calibration_ok"]["high"] is False:
                fl.append("breaks calibration " + "/".join(k for k in ("low", "high") if r["calibration_ok"][k] is False))
            lines.append(f"| {r['label']} (`{pid}`) | {r['low']} / {r['base']} / {r['high']} | {x['A_low']}..{x['A_high']} | {x['B_low']}..{x['B_high']} "
                         f"| {x['gain_pp_low']:+.1f}, {x['gain_pp_high']:+.1f} | {x['gain_days_low']:+.1f}, {x['gain_days_high']:+.1f} | {x['swing_pp']} | {', '.join(fl)} |")
        lines.append("")
    if result.get("joint"):
        lines.append("**Joint draws (all parameters at once)**")
        lines.append("")
        lines += ["| Pair | subset | draws | B beats A (share) | B faster (median) | gain pp p5 / median / p95 | gain days p5 / median / p95 |", "|---|---|---|---|---|---|---|"]
        for key, s in result["joint"]["summary"].items():
            for sub in ("all", "calibration_consistent"):
                v = s[sub]
                if v:
                    lines.append(f"| {key} | {sub} | {v['draws']} | {v['p_B_better_share']:.0%} | {v['p_B_faster_median']:.0%} | "
                                 f"{v['gain_pp']['p5']} / {v['gain_pp']['median']} / {v['gain_pp']['p95']} | {v['gain_days']['p5']} / {v['gain_days']['median']} / {v['gain_days']['p95']} |")
        lines.append("")
    return "\n".join(lines)


def run_sensitivity(path: str, pairs: list[tuple[str, str]], n: int | None = None, seeds: list[int] | None = None,
                    draws: int = 0, only: list[str] | None = None, use_all: bool = False, noise_seeds: list[int] | None = None,
                    log=print) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    n = n or int(raw.get("default_n", 1000))
    seeds = seeds or [1]
    t0 = time.time()
    flows = []
    for a, b in pairs:
        for f in (a, b):
            if f not in flows:
                flows.append(f)
    cal = raw.get("calibration", {}).get("flowchart")
    if cal and cal not in flows:
        flows.append(cal)
    params = select(discover(raw), only, raw["id"], use_all)
    ev = Evaluator(raw, flows, n, seeds)
    log(f"{raw['id']}: {len(params)} parameters, flowcharts {flows}, n={n}, seeds={seeds}")
    tor = tornado(raw, ev, params, pairs, log)
    nz = noise(ev, pairs, noise_seeds or seeds)
    jt = joint(raw, ev, params, pairs, draws, log=log) if draws else None
    result = {"scenario": raw["id"], "file": str(path), "n": n, "seeds": seeds, "n_params": len(params), "pairs": [list(p) for p in pairs],
              "variation": "low/high = x0.75 / x1.25 unless the parameter row shows otherwise; integer capacities +-1 (1-4 slots) or +-25%",
              "parameters": [{"id": p.id, "label": p.label, "kind": p.kind, "rel": p.rel} for p in params],
              "tornado": tor, "noise": nz, "joint": jt, "simulations": ev.runs, "runtime_s": round(time.time() - t0, 1)}
    return result


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scenario")
    ap.add_argument("--equity", action="store_true", help="Finland equity-gap sensitivity (F4) instead of the tornado")
    ap.add_argument("--compare", action="append", help="A,B (baseline, improved); repeatable")
    ap.add_argument("--n", type=int)
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--noise-seeds", help="seeds for the noise floor (default: --seeds, one run each)")
    ap.add_argument("--draws", type=int, default=0, help="joint Monte Carlo draws (0 = skip)")
    ap.add_argument("--only", action="append", help="regex on parameter id (repeatable); default: shortlist or all")
    ap.add_argument("--all", action="store_true", help="ignore the built-in shortlist")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.equity:
        res = equity_sensitivity(a.scenario, a.n or 14000, [int(x) for x in a.seeds.split(",")], a.draws or 16)
        print(json.dumps(res["ranges"], indent=1))
        if a.out:
            Path(a.out).write_text(json.dumps(res, indent=1))
            print("wrote", a.out)
        return
    if not a.compare:
        ap.error("--compare is required")
    pairs = [tuple(c.split(",")) for c in a.compare]
    seeds = [int(s) for s in a.seeds.split(",")]
    nz = [int(s) for s in a.noise_seeds.split(",")] if a.noise_seeds else None
    res = run_sensitivity(a.scenario, pairs, a.n, seeds, a.draws, a.only, a.all, nz)
    print(markdown(res, a.top))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
        print("wrote", a.out)


if __name__ == "__main__":
    main()

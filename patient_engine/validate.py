"""Card validation and repair requests (WP-C1-4, pipeline stage G3).

``validate_card(card, catalogue)`` checks one card (a ``card/1`` dict, or a ``Card``) against its
catalogue and for internal consistency. It returns a list of ``Problem``: first the JSON Schema
problems (code ``card_schema``, ``card_schema_problems``), then the semantic rules below in rule
order. ``repair_prompt(card_json, problems)`` turns the problems into a short plain-text request that
asks a language model for the corrected card. No model is called here; the loop is WP-C1-5's.

The rules (each has its own code in ``patient_engine.problems.CODES``)::

    1  card_state_keys          states start with all_active; presenting, findings, observations (and
                                a set error_plan) have exactly the card's states as keys; notes name a state
    2  card_conditions          exactly one primary, at most one coexisting, no repeats; ids and
                                attributes are the catalogue's
    3  card_cause_inactive      every caused_by entry is an active condition of the card in that state
       card_unexplained_finding a binary finding that is true with no cause needs a background rate
    4  card_unsupported_cause   (warning) the catalogue gives the variable no entry for that cause
    5  card_attempts            1..max_attempts per test; non_diagnostic only where the test has a rate
       card_only_if             a finding or output is null exactly when its only_if is false
       (types, enums and required outputs are the schema's: code card_schema)
    6  card_plan_mismatch       a guided card's results agree with hidden.error_plan
    7  card_value_range         a number is inside the catalogue's range for its variable or field
       card_implausible         (warning) a measured value far from its truth when the card has no plan for it
    8  card_mention_unknown     every note mention is a variable id, test id or test.output
       card_reveals_condition   (warning) text names the hidden primary condition without a revealing fact
    9  card_report_contradiction (warning) a report says the opposite of a binary output

A rule that the schema already enforces (typed values, enums, required keys) keeps the schema's
code. Where the schema's message would be hard to act on (a non-diagnostic attempt, an unknown
condition, a note mention, a number out of range) the rule replaces it with its own code and a
sharper message at the same path. Semantic rules run even when the schema failed, so one repair
request can carry every problem; a semantic problem under a path the schema already flagged is
dropped to avoid noise.

Information boundary (I1): this module reads whole cards, so it is hidden-side code. The text of
its problems may name hidden facts (it is sent to the card author, not to the simulation).
"""

from __future__ import annotations

import difflib
import json
import re
from typing import Any, Iterable, Mapping

from pathway_sim import expr as _expr

from .card import INITIAL_STATE, Card, card_schema_problems, card_to_json
from .catalogue import ALL_RESOLVED
from .problems import ERROR, Problem

__all__ = ["validate_card", "repair_prompt", "has_errors"]

#: Deviation, in standard deviations of the test's stated error, up to which a ``correct`` measured
#: value is accepted (rule 6), beyond which a ``wrong`` one is required, and beyond which a measured
#: value is implausible when nothing was planned (rule 7).
CORRECT_SD = 3.0
WRONG_SD = 1.9   # generator calls a value wrong at |z| >= 1.96 (skeleton.OUTCOME_Z); 1.9 leaves room for rounding to 0.1
IMPLAUSIBLE_SD = 5.0

#: Phrases that say "nothing abnormal" in a report; checked only for outputs named ``abnormal*`` (rule 9).
_NORMAL_PHRASES = re.compile(
    r"\b(no (significant |acute |evident )?abnormalit(y|ies)|unremarkable|within normal limits|normal (study|chest|appearance|findings?)|"
    r"nothing abnormal|no abnormal)\b")


def validate_card(card: Mapping[str, Any] | Card, catalogue) -> list[Problem]:
    """Every problem of ``card`` against ``catalogue``: schema problems first, then the rules above
    in order. Warnings are included; ``has_errors(problems)`` says whether the card must be repaired
    or discarded. Never raises on a malformed card."""
    data = card_to_json(card) if isinstance(card, Card) else card
    schema = card_schema_problems(data, catalogue)
    if not isinstance(data, dict):
        return schema
    checker = _Checker(data, catalogue)
    checker.run()
    out = [p for p in schema if not _superseded(p.path, checker.supersede)]
    flagged = [p.path for p in out]
    for p, force in checker.found:
        if force or not any(_under(p.path, f) for f in flagged):
            out.append(p)
    return out


def has_errors(problems: Iterable[Problem]) -> bool:
    return any(p.severity == ERROR for p in problems)


# ============================================================================ helpers

def _join(path: str, key) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else str(key)


def _under(path: str | None, ancestor: str | None) -> bool:
    """``path`` is ``ancestor`` or lies inside it."""
    if not path or not ancestor:
        return False
    return path == ancestor or (path.startswith(ancestor) and path[len(ancestor)] in ".[")


def _superseded(path: str | None, supersede: list[tuple[str, bool]]) -> bool:
    return any(path == p or (deep and _under(path, p)) for p, deep in supersede)


def _dict(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def _list(x: Any) -> list:
    return x if isinstance(x, list) else []


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _close(name: str, known: Iterable[str]) -> str | None:
    m = difflib.get_close_matches(str(name), [str(k) for k in known], n=1, cutoff=0.6)
    return f"Did you mean {m[0]!r}?" if m else None


def _stem(output_id: str) -> str:
    """Words of an output id that name the finding: ``nodule_seen`` -> ``nodule``, ``cough_3wk`` -> ``cough``."""
    words = [w for w in output_id.split("_") if w and not any(c.isdigit() for c in w)
             and w not in ("seen", "present", "true", "found", "detected")]
    return " ".join(words) or output_id.replace("_", " ")


#: Words besides a condition's label and id that name it (review w8 M1): synonyms and abbreviations, matched as whole
#: words (an optional plural ``s``), case-insensitive. Only words that no test result needs to describe its own values:
#: "malignant cells", "suspicious for malignancy", "metastases", "airflow obstruction", "consolidation" and the cell
#: types ("adenocarcinoma", "small cell carcinoma"), "recurrent chest infection" stay allowed, so a report of the values
#: alone is never flagged (``tests/test_review_w8_g2_blind.py`` checks every output and label of the catalogue).
CONDITION_TERMS: dict[str, tuple[str, ...]] = {
    "lung_cancer": ("cancer", "lung carcinoma", "bronchial carcinoma", "bronchogenic carcinoma", "tumour", "tumor",
                    "neoplasm"),
    # not "chest infection": the history output and symptom ``recurrent_chest_infection`` describe it
    "pneumonia": ("lower respiratory tract infection", "lrti"),
    "copd_exacerbation": ("copd", "emphysema", "chronic bronchitis", "chronic obstructive pulmonary disease",
                          "chronic obstructive lung disease"),
    "asthma": ("asthmatic",),
    "heart_failure": ("cardiac failure", "congestive heart", "chf"),
    "tuberculosis": ("tb", "tuberculous"),
    "benign_nodule": ("granuloma", "hamartoma"),
    "reflux_postinfectious_cough": ("reflux", "gord", "gerd", "post-infectious cough", "postinfectious cough",
                                    "post-viral cough", "postviral cough"),
    "viral_self_limiting": ("viral illness", "viral infection", "common cold", "influenza", "flu"),
}


def condition_terms(condition) -> set[str]:
    """Lower-case words that name ``condition`` (a catalogue condition): its label, its id and ``CONDITION_TERMS``."""
    return {condition.label.lower(), condition.id.replace("_", " "), *CONDITION_TERMS.get(condition.id, ())}


def condition_pattern(condition) -> re.Pattern:
    """A regex that finds any name of ``condition`` in lower-case text with ``_`` read as a space (rule 8)."""
    names = sorted(condition_terms(condition), key=len, reverse=True)
    return re.compile("|".join(r"(?<![a-z])" + re.escape(x) + r"s?(?![a-z])" for x in names))


def report_contradictions(test, values: Mapping[str, Any], report: str) -> list[tuple[str, bool]]:
    """Rule 9 for one report: ``(output id, value)`` of every binary output that ``report`` states the opposite of."""
    text = report.lower()
    out = []
    for o in test.outputs:
        v = values.get(o.id)
        if o.type != "binary" or not isinstance(v, bool):
            continue
        stem = re.escape(_stem(o.id))
        negated = re.search(rf"\b(no|without|absence of)\s+(\w+\s+)?(evidence of\s+|sign of\s+)?{stem}", text) \
            or re.search(rf"\b{stem}\w*\s+(is |are |was |were )?(absent|not (seen|present|identified))", text)
        if o.id.startswith("abnormal"):
            negated = negated or _NORMAL_PHRASES.search(text)
        shown = re.search(rf"(?<!no )(?<!without )\b{stem}\w*\s+(is |are |was |were )?(seen|present|noted|identified|demonstrated|evident)", text)
        if (v and negated) or (not v and shown and not negated):
            out.append((o.id, v))
    return out


def _var_range(var) -> tuple[float | None, float | None]:
    lo, hi = var.range
    if var.type == "size_mm" and lo is None:
        lo = 0
    return lo, hi


# ============================================================================ the checker

class _Checker:
    def __init__(self, d: dict, cat):
        self.d, self.cat = d, cat
        self.found: list[tuple[Problem, bool]] = []         # (problem, replaces schema problems)
        self.supersede: list[tuple[str, bool]] = []         # schema paths a rule replaces (path, deep)
        states = d.get("states")
        self.states = [s for s in _list(states) if isinstance(s, str)]
        hidden = _dict(d.get("hidden"))
        self.conds = [c for c in _list(hidden.get("conditions")) if isinstance(c, dict)]
        self.cond_ids = {c["id"] for c in self.conds if isinstance(c.get("id"), str)}
        prim = [c for c in self.conds if c.get("role") == "primary" and isinstance(c.get("id"), str) and c["id"] in cat.conditions]
        self.primary = prim[0]["id"] if prim else None
        self.findings = {s: _dict(fs) for s, fs in _dict(hidden.get("findings")).items()}
        self.plan = hidden.get("error_plan")
        self.background = _dict(d.get("background"))

    def add(self, code: str, message: str, path: str, hint: str | None = None,
            replaces: str | None = None, deep: bool = False) -> None:
        """Record a problem. ``replaces`` = ``"here"`` drops the schema's problems at ``path``
        (``deep``: and under it); the semantic problem is kept even if the schema flagged the same place."""
        force = replaces is not None
        if force:
            self.supersede.append((path, deep))
        self.found.append((Problem(code, message, path=path, hint=hint), force))

    def run(self) -> None:
        for rule in (self.r1_states, self.r2_conditions, self.r3_r4_causes, self.r5_results,
                     self.r6_plan, self.r7_values, self.r8_notes, self.r9_reports):
            try:
                rule()
            except (KeyError, TypeError, AttributeError, ValueError, IndexError):
                # a malformed card: the schema problems already say so
                continue

    # ------------------------------------------------------------------ rule 1
    def r1_states(self) -> None:
        states = self.d.get("states")
        if isinstance(states, list) and states and isinstance(states[0], str) and states[0] != INITIAL_STATE:
            self.add("card_state_keys", f"the first state must be {INITIAL_STATE!r}, got {states[0]!r}", "states[0]",
                     "states lists the state at first contact first", replaces="here")
        want = set(self.states)
        sections: list[tuple[str, Any]] = [("presenting", self.d.get("presenting")),
                                           ("hidden.findings", _dict(self.d.get("hidden")).get("findings")),
                                           ("observations", self.d.get("observations"))]
        if isinstance(self.plan, dict):
            sections.append(("hidden.error_plan", self.plan))
        for path, sec in sections:
            if not isinstance(sec, dict):
                continue
            missing = [s for s in self.states if s not in sec]
            if missing:
                self.add("card_state_keys", f"no entry for state {', '.join(map(repr, missing))}", path,
                         "every section has one entry per state in `states`")
            for k in sec:
                if k not in want:
                    self.add("card_state_keys", f"entry for state {k!r}, which is not in `states`", _join(path, k),
                             "remove it, or add the state to `states` and to every section")
        for i, n in enumerate(_list(self.d.get("notes"))):
            s = _dict(n).get("state")
            if isinstance(s, str) and s not in want:
                self.add("card_state_keys", f"note state {s!r} is not in `states`", f"notes[{i}].state",
                         f"use one of {self.states}")

    # ------------------------------------------------------------------ rule 2
    def r2_conditions(self) -> None:
        cat = self.cat
        base = "hidden.conditions"
        roles = [c.get("role") for c in self.conds]
        n_primary, n_co = roles.count("primary"), roles.count("coexisting")
        if n_primary != 1:
            self.add("card_conditions", f"exactly one condition must have role 'primary', found {n_primary}", base,
                     "the primary condition is the one the patient is mainly being worked up for")
        if n_co > 1:
            self.add("card_conditions", f"at most one condition may have role 'coexisting', found {n_co}", base)
        seen: set[str] = set()
        for i, c in enumerate(self.conds):
            cid = c.get("id")
            p = f"{base}[{i}]"
            if not isinstance(cid, str):
                continue
            if cid in seen:
                self.add("card_conditions", f"condition {cid!r} appears twice", f"{p}.id")
            seen.add(cid)
            if cid not in cat.conditions:
                self.add("card_conditions", f"unknown condition {cid!r}", f"{p}.id",
                         _close(cid, cat.conditions) or f"conditions: {', '.join(cat.conditions)}",
                         replaces="here", deep=True)
                continue
            cond = cat.conditions[cid]
            attrs = c.get("attributes")
            if not isinstance(attrs, dict):
                continue
            for a in cond.attributes:
                if a not in attrs:
                    self.add("card_conditions", f"{cid} needs the attribute {a!r}", _join(f"{p}.attributes", a),
                             f"one of {list(cond.attribute_levels(a))}", replaces="here")
                elif not isinstance(attrs[a], str) or attrs[a] not in cond.attribute_levels(a):
                    self.add("card_conditions", f"{attrs[a]!r} is not a level of {cid}.{a}", _join(f"{p}.attributes", a),
                             f"one of {list(cond.attribute_levels(a))}", replaces="here")
            for a in attrs:
                if a not in cond.attributes:
                    self.add("card_conditions", f"{cid} has no attribute {a!r}", _join(f"{p}.attributes", a),
                             _close(a, cond.attributes) or f"attributes of {cid}: {list(cond.attributes) or 'none'}",
                             replaces="here")

    # ------------------------------------------------------------------ rules 3 and 4
    def resolved_in(self, state: str) -> set[str]:
        if state == ALL_RESOLVED:
            return {c for c in self.cond_ids if c in self.cat.conditions and self.cat.conditions[c].cls == "other_illness"}
        if state.endswith("_resolved"):
            return {state[: -len("_resolved")]}
        return set()

    def r3_r4_causes(self) -> None:
        cat = self.cat
        for state, fs in self.findings.items():
            resolved = self.resolved_in(state)
            for vid, f in fs.items():
                var = cat.variables.get(vid)
                if var is None or not isinstance(f, dict):
                    continue
                path = f"hidden.findings.{state}.{vid}"
                causes = _list(f.get("caused_by"))
                for i, c in enumerate(causes):
                    cp = f"{path}.caused_by[{i}]"
                    if not isinstance(c, str):
                        continue
                    if c in resolved and c in self.cond_ids:
                        self.add("card_cause_inactive", f"{c} is resolved in state {state}, so it cannot cause {vid} there", cp,
                                 "drop it; if nothing else explains the finding, the finding is absent in this state")
                    elif c not in self.cond_ids:
                        self.add("card_cause_inactive", f"{c!r} is not a condition of this patient", cp,
                                 f"conditions of the card: {sorted(self.cond_ids)}")
                    elif c in cat.conditions and c not in var.given:
                        self.add("card_unsupported_cause", f"the catalogue gives {vid} no entry for {c}", cp,
                                 "the catalogue treats it as background; list only causes the catalogue supports")
                    elif c in var.given and var.type == "binary" and f.get("value") is True \
                            and var.given[c].kind == "p" and var.given[c].params.get("p") == 0:
                        self.add("card_unsupported_cause", f"the catalogue says {c} never causes {vid}", cp)
                if var.type == "binary" and f.get("value") is True and causes == []:
                    dflt = var.given.get("default")
                    rate = dflt.params.get("p") if dflt is not None and dflt.kind == "p" else None
                    if not (_num(rate) and rate > 0):
                        self.add("card_unexplained_finding", f"{vid} is true with no cause, and the catalogue gives it no background rate",
                                 f"{path}.caused_by", "list a condition that causes it, or set the finding to false")

    # ------------------------------------------------------------------ rule 5
    def r5_results(self) -> None:
        cat = self.cat
        for state, fs in self.findings.items():
            env = {k: _dict(f).get("value") for k, f in fs.items()}
            for vid, f in fs.items():
                var = cat.variables.get(vid)
                if var is None or var.only_if is None or "value" not in _dict(f):
                    continue
                self._only_if(var.only_if, env, _dict(f)["value"], vid, f"hidden.findings.{state}.{vid}.value")
        for state, tests in _dict(self.d.get("observations")).items():
            for tid, atts in _dict(tests).items():
                test = cat.tests.get(tid)
                if test is None or not isinstance(atts, list):
                    continue
                p = f"observations.{state}.{tid}"
                if not atts:
                    self.add("card_attempts", f"{tid} needs at least one attempt", p, replaces="here")
                elif len(atts) > test.max_attempts:
                    self.add("card_attempts", f"{tid} allows at most {test.max_attempts} attempts, got {len(atts)}", p,
                             "drop the extra attempts", replaces="here")
                for i, a in enumerate(atts):
                    a = _dict(a)
                    ap = f"{p}[{i}]"
                    if a.get("status") == "non_diagnostic" and test.nondiagnostic is None:
                        self.add("card_attempts", f"{tid} never fails to give a result, so an attempt cannot be non_diagnostic", ap,
                                 "write an ok attempt with a value for every output", replaces="here", deep=True)
                    if a.get("status") != "ok" or not isinstance(a.get("values"), dict):
                        continue
                    for o in test.outputs:
                        if o.only_if is not None and o.id in a["values"]:
                            self._only_if(o.only_if, a["values"], a["values"][o.id], f"{tid}.{o.id}", f"{ap}.values.{o.id}")

    def _only_if(self, expression: str, env: Mapping, value: Any, name: str, path: str) -> None:
        try:
            holds = _expr.parse(expression).holds(env)
        except _expr.ExprError:
            return
        if holds and value is None:
            self.add("card_only_if", f"{name} needs a value because `{expression}` holds", path)
        elif not holds and value is not None:
            self.add("card_only_if", f"{name} must be null because `{expression}` does not hold", path, "write null")

    # ------------------------------------------------------------------ rule 6
    def facts(self, state: str) -> dict:
        facts: dict[str, Any] = {**self.background}
        facts.update({k: _dict(f).get("value") for k, f in self.findings.get(state, {}).items()})
        for c in self.conds:
            if c.get("role") == "primary":
                facts["condition"] = c.get("id")
                facts.update(_dict(c.get("attributes")))
        return facts

    def _sd(self, out, state: str) -> float | None:
        if out.error_sd is None:
            return None
        try:
            sd = out.error_sd.resolve(self.facts(state))
        except (KeyError, TypeError, ValueError):
            return None
        return float(sd) if _num(sd) and sd > 0 else None

    def planned(self, state: str, tid: str, i: int, oid: str) -> str | None:
        if not isinstance(self.plan, dict):
            return None
        pa = _list(_dict(_dict(self.plan).get(state)).get(tid))
        if i < len(pa):
            return _dict(_dict(pa[i]).get("outputs")).get(oid)
        return None

    def r6_plan(self) -> None:
        if not isinstance(self.plan, dict):
            return
        cat = self.cat
        for state, tplan in self.plan.items():
            for tid, plans in _dict(tplan).items():
                test = cat.tests.get(tid)
                atts = _list(_dict(_dict(self.d.get("observations")).get(state)).get(tid))
                if test is None or not isinstance(plans, list) or not atts:
                    continue
                p = f"observations.{state}.{tid}"
                if len(plans) != len(atts):
                    self.add("card_plan_mismatch", f"the error plan has {len(plans)} attempts for {tid} in {state}, the card has {len(atts)}", p,
                             f"write exactly {len(plans)} attempts, in plan order")
                for i, (plan, a) in enumerate(zip(plans, atts)):
                    plan, a = _dict(plan), _dict(a)
                    ap = f"{p}[{i}]"
                    if plan.get("status") != a.get("status"):
                        self.add("card_plan_mismatch", f"attempt {i + 1} of {tid} must have status {plan.get('status')!r} (error plan), got {a.get('status')!r}",
                                 f"{ap}.status")
                        continue
                    if a.get("status") != "ok" or not isinstance(a.get("values"), dict):
                        continue
                    for o in test.outputs:
                        outcome = _dict(plan.get("outputs")).get(o.id)
                        if outcome is None or o.id not in a["values"]:
                            continue
                        truth = _dict(self.findings.get(state, {}).get(o.measures)).get("value")
                        bad = self._plan_violation(o, outcome, a["values"][o.id], truth, state)
                        if bad:
                            self.add("card_plan_mismatch", f"{tid}.{o.id}: {bad}", f"{ap}.values.{o.id}",
                                     f"planned outcome {outcome!r} is fixed; change the value, not the plan")

    def _plan_violation(self, out, outcome: str, value: Any, truth: Any, state: str) -> str | None:
        if value is None or truth is None:
            return None
        if out.type == "binary" and isinstance(value, bool) and isinstance(truth, bool):
            if outcome == "correct" and value != truth:
                return f"planned correct, but the value is {value} and {out.measures} is {truth}"
            if outcome == "miss" and value is not False:
                return f"planned miss, so the test must not show the finding: value must be false ({out.measures} is {truth})"
            if outcome == "false_alarm" and value is not True:
                return f"planned false_alarm, so the test must show the finding: value must be true ({out.measures} is {truth})"
            if outcome == "wrong" and value == truth:
                return f"planned wrong, but the value equals the truth ({truth})"
        elif out.type in ("continuous", "size_mm") and _num(value) and _num(truth):
            sd = self._sd(out, state)
            if sd is None:
                return None
            if outcome == "correct" and abs(value - truth) > CORRECT_SD * sd:
                return f"planned correct, but {value} is more than {CORRECT_SD:g} x {sd:g} away from the true {truth}"
            var = self.cat.variables.get(out.measures)
            at_bound = var is not None and value in tuple(b for b in (getattr(var, "range", None) or ()) if b is not None)
            if outcome == "wrong" and abs(value - truth) <= WRONG_SD * sd and not at_bound:   # a wrong value clamped to the range is fine
                return f"planned wrong, but {value} is within {WRONG_SD:g} x {sd:g} of the true {truth}"
        elif out.type == "categorical":
            if outcome == "correct" and value != truth:
                return f"planned correct, but the value is {value!r} and the truth is {truth!r}"
            if outcome == "wrong" and value == truth:
                return f"planned wrong, but the value equals the truth ({truth!r})"
        return None

    # ------------------------------------------------------------------ rule 7
    def r7_values(self) -> None:
        cat = self.cat
        for fid, f in cat.background.items():
            self._range(self.background.get(fid), f.range, f"background.{fid}", fid)
        for state, fs in self.findings.items():
            for vid, f in fs.items():
                var = cat.variables.get(vid)
                if var is not None and var.type in ("continuous", "size_mm"):
                    self._range(_dict(f).get("value"), _var_range(var), f"hidden.findings.{state}.{vid}.value", vid)
        for state, tests in _dict(self.d.get("observations")).items():
            for tid, atts in _dict(tests).items():
                test = cat.tests.get(tid)
                if test is None:
                    continue
                for i, a in enumerate(_list(atts)):
                    a = _dict(a)
                    if a.get("status") != "ok" or not isinstance(a.get("values"), dict):
                        continue
                    for o in test.outputs:
                        v = a["values"].get(o.id)
                        if o.type not in ("continuous", "size_mm") or not _num(v):
                            continue
                        p = f"observations.{state}.{tid}[{i}].values.{o.id}"
                        self._range(v, _var_range(cat.variables[o.measures]), p, f"{tid}.{o.id}")
                        truth = _dict(self.findings.get(state, {}).get(o.measures)).get("value")
                        sd = self._sd(o, state)
                        if (sd is not None and _num(truth) and abs(v - truth) > IMPLAUSIBLE_SD * sd
                                and self.planned(state, tid, i, o.id) is None):
                            self.add("card_implausible", f"{tid}.{o.id} is {v}, far from the true {truth} (stated error sd {sd:g})", p,
                                     "keep a measurement within its usual error unless the plan asks for a wrong value")

    def _range(self, value: Any, rng, path: str, name: str) -> None:
        if not _num(value):
            return
        lo, hi = rng
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            lim = f"{'-' if lo is None else lo:} to {'-' if hi is None else hi}".replace("-: ", "")
            self.add("card_value_range", f"{name} = {value} is outside the allowed range {lim}", path,
                     "write a plausible value inside the range", replaces="here")

    # ------------------------------------------------------------------ rule 8
    def r8_notes(self) -> None:
        cat = self.cat
        known = [*cat.variables, *cat.tests, *(f"{t.id}.{o.id}" for t in cat.tests.values() for o in t.outputs)]
        kset = set(known)
        for i, n in enumerate(_list(self.d.get("notes"))):
            n = _dict(n)
            for j, m in enumerate(_list(n.get("mentions"))):
                if isinstance(m, str) and m not in kset:
                    self.add("card_mention_unknown", f"mention {m!r} is not a variable id, test id or test.output", f"notes[{i}].mentions[{j}]",
                             _close(m, known) or "use ids from the catalogue", replaces="here")
        prim = cat.conditions.get(self.primary) if self.primary else None
        if prim is None or prim.cls == "healthy":
            return
        rx = condition_pattern(prim)

        # The exemption (a mention that reveals the primary) is for clinicians' texts stating a result (GP notes,
        # reports). The patient's own words (account, complaint) never name the diagnosis (review w8 M1).
        def check(text: Any, state: str, keys: Iterable[str], path: str, exempt: bool = True) -> None:
            if isinstance(text, str) and rx.search(text.lower().replace("_", " ")) \
                    and not (exempt and any(self._reveals(state, k) for k in keys)):
                self.add("card_reveals_condition", f"the text names the hidden primary condition ({prim.label})", path,
                         "rephrase without the diagnosis" + (", or add to `mentions` the finding or test result that "
                                                             "reveals it" if exempt else ""))

        for i, n in enumerate(_list(self.d.get("notes"))):
            n = _dict(n)
            check(n.get("text"), str(n.get("state")), _list(n.get("mentions")), f"notes[{i}].text",
                  exempt=n.get("kind") != "patient_account")
        for state, p in _dict(self.d.get("presenting")).items():
            check(_dict(p).get("text"), state, _list(_dict(p).get("reported")), f"presenting.{state}.text", exempt=False)
        # A definitive test for the primary condition (an output measuring `dx_<primary>`, decision D46)
        # names what it tests for whether the result is positive or negative; that is not a leak.
        definitive = {t.id for t in cat.tests.values() if any(o.measures == f"dx_{self.primary}" for o in t.outputs)}
        for state, tests in _dict(self.d.get("observations")).items():
            for tid, atts in _dict(tests).items():
                if tid in definitive:
                    continue
                for i, a in enumerate(_list(atts)):
                    check(_dict(a).get("report"), state, [tid], f"observations.{state}.{tid}[{i}].report")

    def _reveals(self, state: str, key: Any) -> bool:
        """A fact reveals the primary condition if it is present and caused by that condition alone."""
        cat = self.cat
        if not isinstance(key, str):
            return False
        if key in cat.tests:
            variables = [o.measures for o in cat.tests[key].outputs]
        elif "." in key and key.split(".", 1)[0] in cat.tests:
            t = cat.tests[key.split(".", 1)[0]]
            variables = [o.measures for o in t.outputs if o.id == key.split(".", 1)[1]]
        else:
            variables = [key]
        for v in variables:
            f = _dict(self.findings.get(state, {}).get(v))
            if f.get("value") not in (None, False) and set(_list(f.get("caused_by"))) == {self.primary}:
                return True
        return False

    # ------------------------------------------------------------------ rule 9
    def r9_reports(self) -> None:
        cat = self.cat
        for state, tests in _dict(self.d.get("observations")).items():
            for tid, atts in _dict(tests).items():
                test = cat.tests.get(tid)
                if test is None:
                    continue
                for i, a in enumerate(_list(atts)):
                    a = _dict(a)
                    report = a.get("report")
                    if a.get("status") != "ok" or not isinstance(report, str) or not report.strip() \
                            or not isinstance(a.get("values"), dict):
                        continue
                    for oid, v in report_contradictions(test, a["values"], report):
                        p = f"observations.{state}.{tid}[{i}].report"
                        word = "absent" if v else "present"
                        self.add("card_report_contradiction",
                                 f"the report says {_stem(oid)} is {word}, but {tid}.{oid} is {'true' if v else 'false'}", p,
                                 "make the report agree with the values")


# ============================================================================ repair request

_HEAD = "Card {cid} failed validation. Fix every error below and return the full corrected card as JSON only, with the same format and nothing else changed."
_BUDGET = 1900          # characters for ten problems stay under 2 000 in total
_MAX_LINES = 10


def _line(p: Problem, limit: int) -> str:
    path = p.path or "card"
    head = f"- {path}: "
    msg = " ".join(p.message.split())
    hint = f" ({' '.join(p.hint.split())})" if p.hint else ""
    room = limit - len(head)
    if len(msg) + len(hint) > room:
        hint = hint[:41] + "...)" if len(hint) > 45 else hint
    if len(msg) + len(hint) > room:
        msg = msg[: max(room - len(hint) - 3, 20)].rstrip() + "..."
    return head + msg + hint


def repair_prompt(card_json: Mapping[str, Any] | str | None, problems: Iterable[Problem]) -> str:
    """The message that asks the card author to correct ``card_json``: one line per problem as
    ``- path: message (hint)``, errors first (every error is listed, none is cut), warnings after as
    space allows, then nothing else. Deterministic; about 1 900 characters for ten problems.
    ``card_json`` (a dict or its JSON text) is read only for the card id."""
    if isinstance(card_json, str):
        try:
            card_json = json.loads(card_json)
        except ValueError:
            card_json = None
    cid = _dict(card_json).get("id") or "(unnamed)"
    probs = list(problems)
    errs = [p for p in probs if p.severity == ERROR]
    warns = [p for p in probs if p.severity != ERROR][: max(_MAX_LINES - len(errs), 0)]
    head = _HEAD.format(cid=cid)
    n_lines = len(errs) + len(warns)
    limit = min(max((_BUDGET - len(head) - (30 if warns else 0)) // max(n_lines, 1), 90), 260)
    lines = [head, *(_line(p, limit) for p in errs)]
    if warns:
        lines += ["Also, if you can:", *(_line(p, limit) for p in warns)]
    return "\n".join(lines)

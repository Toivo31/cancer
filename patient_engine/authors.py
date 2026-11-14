"""The two model authors of a card (WP-C1-5): G1 writes the patient, G2 writes every test result.

::

    authors = Authors(catalogue)                       # schemas and prompts, built once per catalogue
    req1 = authors.g1_request(skeleton)                # dict(system, user, schema) for LLMClient.complete_json
    answer1 = client.complete_json(**req1, key="card-7:g1")
    findings = authors.findings_of(answer1)            # variable id -> value, ready for settle_error_plan
    plan = settle_error_plan(catalogue, skeleton, findings)["all_active"]
    req2 = authors.g2_request(skeleton, answer1, plan)
    answer2 = client.complete_json(**req2, key="card-7:g2")
    card = authors.assemble(skeleton, answer1, answer2, plan, provenance)      # a card/1 dict, not yet validated

Information boundary (I1). Both prompts are built from the skeleton, the catalogue and (for G2) the
findings G1 wrote: no ``Card`` and no reference result ever enters a prompt. G1 and G2 see the
hidden truth because they must write it; what they write into notes and reports is text the
revealed side will read, so the prompts tell them not to name the diagnosis, and the validator
(rule 8, ``card_reveals_condition``) checks it. The pipeline treats that warning as an error.

What each author returns (the shapes are JSON Schemas derived from ``card_schema(catalogue)``)::

    G1  {"states": {state: {"findings": {variable id: {"value", "caused_by"}},
                            "presenting": {"reported": [variable id], "text": str},
                            "account": {"text": str, "mentions": [variable id]}}}}      one call, every state
    G2  {"observations": {test id: [{"status", "values", "report"}]},
         "gp_note": {"text": str, "mentions": [test id | test.output id]}}              one call per state

The skeleton fixes the background, the conditions and their attributes and the error plan; the
authors never write those. Prompts are data files in ``patient_engine/prompts/`` (see its README).

States (C8). A card has the states of its skeleton (``all_active`` and one ``<illness>_resolved`` per ordinary
illness, ``all_resolved`` with two). G1 writes the whole patient for every state in one answer, so a resolved
state is written next to the first and stays consistent with it. The error plan is settled per state from
that state's findings. G2 is called once per state (a card with two illnesses has four states and one call
for all of them would not fit the output limit). Notes are ``n1, n2`` for the first state, ``n3, n4`` for the
second and so on: account then GP note.
"""

from __future__ import annotations

import json
import re
import string
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from pathway_sim.dists import sample

from .card import CARD_FORMAT, INITIAL_STATE, NOTE_KINDS, Finding
from .catalogue import Catalogue, Leaf, Test, TestOutput, Variable
from .problems import Problem
from .schema import card_schema, schema_problems
from .skeleton import Skeleton, common_facts, illness_ids, plan_to_json, settle_attempt
from .states import resolved_in_state

PROMPT_DIR = Path(__file__).with_name("prompts")

#: role -> (version id stored in ``provenance.prompts``, file stem). A new wording is a new file and a new entry here.
PROMPT_VERSIONS = {"patient": "g1@1", "results": "g2@1"}
_STEMS = {"g1@1": "g1_patient.v1", "g2@1": "g2_results.v1"}

def state_note(cat: Catalogue, sk: Skeleton, state: str) -> str:
    """What a state means for this patient, in words for the prompt."""
    resolved = resolved_in_state(state, illness_ids(cat, sk))
    if not resolved:
        return "every condition of the patient is active; this is the state at first contact"
    gone = ", ".join(cat.conditions[c].label for c in sorted(resolved))
    left = ", ".join(cat.conditions[c].label for c in sk.condition_ids if c not in resolved) or "none"
    return (f"after treatment has resolved: {gone}; still active: {left}. Findings that only the resolved illness "
            f"explained are gone; everything else is as before; no new symptom appears")


@lru_cache(maxsize=None)
def load_prompt(version: str, part: str) -> str:
    """The text of a prompt file: ``version`` is a key of ``_STEMS`` (``g1@1``), ``part`` is ``system`` or ``user``."""
    path = PROMPT_DIR / f"{_STEMS[version]}.{part}.md"
    return path.read_text(encoding="utf-8")


def fill(template: str, **values: str) -> str:
    """Fill a ``$name`` template; a missing or unused name is an error (so a prompt edit cannot silently drop a section)."""
    t = string.Template(template)
    needed = {m.group("named") or m.group("braced") for m in t.pattern.finditer(template)
              if m.group("named") or m.group("braced")}
    if needed != set(values):
        raise ValueError(f"prompt placeholders {sorted(needed)} do not match the values {sorted(values)}")
    return t.substitute(values)


# ============================================================================ rendering helpers

def _pct(p: float) -> str:
    return f"{p * 100:.0f}%" if p >= 0.0995 or p == 0 else f"{p * 100:.1f}%"


def _num(x: float) -> str:
    return f"{x:.3g}"


def describe_leaf(leaf: Leaf, facts: Mapping[str, Any]) -> str:
    """A reference number as short text, resolved for a patient with ``facts`` (as ``Leaf.resolve``)."""
    try:
        r = leaf.resolve(facts)
    except Exception:                                    # a `by` that needs a fact we do not have yet
        r = leaf.resolve({})
    if leaf.kind == "p":
        return _pct(r)
    if leaf.kind == "value":
        return _num(r)
    if leaf.kind == "values":
        return ", ".join(f"{k} {_pct(v)}" for k, v in r.items())
    lo, mid, hi = (sample(r, u) for u in (0.1, 0.5, 0.9))
    return f"{_num(lo)} / {_num(mid)} / {_num(hi)}"


def _background_text(bg: Mapping[str, Any]) -> str:
    return "; ".join(f"{k} {_show(v)}" for k, v in bg.items())


def _show(v: Any) -> str:
    if v is True:
        return "yes"
    if v is False:
        return "no"
    if v is None:
        return "null"
    return str(v)


def _conditions_text(cat: Catalogue, sk: Skeleton) -> str:
    lines = []
    for cid, role, attrs in sk.conditions:
        a = ", ".join(f"{k} {v}" for k, v in attrs.items())
        lines.append(f"- {role}: {cat.conditions[cid].label} (id {cid})" + (f"; {a}" if a else ""))
    return "\n".join(lines)


def _range_text(v: Variable) -> str:
    lo, hi = v.range
    parts = []
    if v.unit:
        parts.append(f"unit {v.unit}")
    if lo is not None or hi is not None:
        parts.append(f"range {'' if lo is None else _num(lo)}..{'' if hi is None else _num(hi)}")
    return ", ".join(parts)


def _variable_line(cat: Catalogue, sk: Skeleton, v: Variable) -> str:
    facts = common_facts(sk)
    refs = []
    for c in sk.condition_ids:
        if c in v.given:
            refs.append(f"{cat.conditions[c].label}: {describe_leaf(v.given[c], {**facts, 'condition': c})}")
    if "default" in v.given:
        refs.append(f"background rate (for a condition without its own number): "
                    f"{describe_leaf(v.given['default'], {**facts, 'condition': sk.primary})}")
    head = f"- {v.id} ({v.label}) [{v.kind}, {v.type}"
    if v.type == "categorical":
        head += f": {'/'.join(v.values)}"
    extra = _range_text(v)
    head += (", " + extra if extra else "") + "]"
    if v.only_if:
        head += f" exists only if `{v.only_if}`, else value null and no cause"
    return head + (" | reference " + "; ".join(refs) if refs else "")


def _findings_text(cat: Catalogue, findings: Mapping[str, Any]) -> str:
    lines = []
    for vid in cat.variables:
        f = findings.get(vid) or {}
        cause = ", ".join(f.get("caused_by") or ()) or "no condition"
        lines.append(f"- {vid}: {_show(f.get('value'))} (caused by {cause})")
    return "\n".join(lines)


def _output_line(cat: Catalogue, o: TestOutput, truth: Any) -> str:
    kind = o.type
    if o.type == "categorical":
        kind += ": " + "/".join(o.values or cat.variables[o.measures].values)
    if o.unit:
        kind += f", unit {o.unit}"
    line = f"  - {o.id} [{kind}] reads `{o.measures}`; its true value: {_show(truth)}"
    if o.only_if:
        line += f"; reported only if `{o.only_if}`, else null"
    return line


def _plan_line(k: int, test: Test, planned, suggested: Mapping[str, Any]) -> str:
    if planned.status == "non_diagnostic":
        return f"  attempt {k}: status non_diagnostic (values {{}}, report says why there is no usable result)"
    parts = []
    for o in test.outputs:
        outcome = planned.outputs.get(o.id, "correct")
        s = f"{o.id} {outcome}"
        v = suggested.get(o.id)
        if v is not None and (o.type in ("continuous", "size_mm") or outcome == "wrong"):
            s += f" (suggested value {_show(v)})"
        parts.append(s)
    return f"  attempt {k}: status ok; " + "; ".join(parts)


# ============================================================================ the authors

class Authors:
    """Schemas and prompt builders of G1 and G2 for one catalogue. Stateless after construction, thread-safe."""

    def __init__(self, catalogue: Catalogue):
        self.cat = catalogue
        full = card_schema(catalogue)
        self._defs = full["$defs"]
        variables = list(catalogue.variables)
        note_ids = [*variables, *catalogue.tests, *(f"{t.id}.{o.id}" for t in catalogue.tests.values()
                                                     for o in t.outputs)]
        self._text = {"type": "string", "minLength": 10}
        self._variables, self._note_ids = variables, note_ids
        self._g1_cache: dict[tuple, dict] = {}
        self.g2_schema: dict = {
            "type": "object", "required": ["observations", "gp_note"], "additionalProperties": False,
            "properties": {
                "observations": self._defs["observations"],
                "gp_note": {"type": "object", "required": ["text", "mentions"], "additionalProperties": False,
                            "properties": {"text": self._text,
                                           "mentions": {"type": "array", "uniqueItems": True,
                                                        "items": {"enum": note_ids}}}},
            },
            "$defs": {k: v for k, v in self._defs.items() if k.startswith("attempt__")},
        }

    def g1_schema_for(self, states: Sequence[str]) -> dict:
        """The G1 answer schema for a card with these states."""
        key = tuple(states)
        if key not in self._g1_cache:
            text, variables = self._text, self._variables
            block = {
                "type": "object", "required": ["findings", "presenting", "account"], "additionalProperties": False,
                "properties": {
                    "findings": self._defs["findings"],
                    "presenting": {"type": "object", "required": ["reported", "text"], "additionalProperties": False,
                                   "properties": {"reported": {"type": "array", "uniqueItems": True,
                                                               "items": {"enum": variables}}, "text": text}},
                    "account": {"type": "object", "required": ["text", "mentions"], "additionalProperties": False,
                                "properties": {"text": text, "mentions": {"type": "array", "uniqueItems": True,
                                                                          "items": {"enum": variables}}}}}}
            self._g1_cache[key] = {
                "type": "object", "required": ["states"], "additionalProperties": False,
                "properties": {"states": {"type": "object", "required": list(key), "additionalProperties": False,
                                          "properties": {st: block for st in key}}}}
        return self._g1_cache[key]

    # ------------------------------------------------------------------ requests

    def g1_request(self, sk: Skeleton) -> dict:
        """``dict(system, user, schema)`` for the patient author (every state of the card in one answer).
        Reads the skeleton and the catalogue only."""
        cat = self.cat
        variables = "\n".join(_variable_line(cat, sk, v) for v in cat.variables.values())
        states = "\n".join(f"- {st}: {state_note(cat, sk, st)}" for st in sk.states)
        user = fill(load_prompt(PROMPT_VERSIONS["patient"], "user"),
                    card_id=sk.id, states=states,
                    background=_background_text(sk.background), conditions=_conditions_text(cat, sk),
                    brief=sk.brief, n_variables=str(len(cat.variables)), variables=variables)
        return {"system": load_prompt(PROMPT_VERSIONS["patient"], "system"), "user": user,
                "schema": self.g1_schema_for(sk.states)}

    def g2_request(self, sk: Skeleton, g1: Mapping[str, Any], plan: Mapping[str, Sequence], state: str = INITIAL_STATE
                   ) -> dict:
        """``dict(system, user, schema)`` for the result author of one ``state``. ``g1`` is the patient author's
        (valid) answer, ``plan`` the settled error plan of that state (``settle_error_plan(...)[state]``)."""
        cat = self.cat
        findings = g1["states"][state]["findings"]
        values = self.findings_of(g1, state)
        blocks = []
        for t in cat.tests.values():
            lines = [f"### {t.id}: {t.label} ({t.category}); write {t.max_attempts} attempt(s)", "Outputs:"]
            lines += [_output_line(cat, o, values.get(o.measures)) for o in t.outputs]
            lines.append("Plan:")
            for k, p in enumerate(plan[t.id]):
                _, suggested = settle_attempt(cat, t, k, sk, values, state)
                lines.append(_plan_line(k, t, p, suggested))
            blocks.append("\n".join(lines))
        user = fill(load_prompt(PROMPT_VERSIONS["results"], "user"),
                    card_id=sk.id, state=state, state_note=state_note(cat, sk, state),
                    background=_background_text(sk.background), conditions=_conditions_text(cat, sk), brief=sk.brief,
                    findings=_findings_text(cat, findings), tests="\n\n".join(blocks))
        return {"system": load_prompt(PROMPT_VERSIONS["results"], "system"), "user": user, "schema": self.g2_schema}

    # ------------------------------------------------------------------ answers

    def findings_of(self, g1: Mapping[str, Any], state: str = INITIAL_STATE) -> dict[str, Any]:
        """Variable id -> true value in ``state`` from a (schema-valid) G1 answer, ready for ``settle_error_plan``."""
        f = g1["states"][state]["findings"]
        return {vid: f[vid]["value"] for vid in self.cat.variables}

    def g1_problems(self, g1: Any, states: Sequence[str] = (INITIAL_STATE,)) -> list[Problem]:
        """Schema problems of a G1 answer, plus: ``presenting.reported`` may name only true symptom findings."""
        probs = schema_problems(g1, self.g1_schema_for(states))
        if probs:
            return probs
        out = []
        for st in states:
            blk = g1["states"][st]
            for i, vid in enumerate(blk["presenting"]["reported"]):
                v = self.cat.variables[vid]
                if blk["findings"][vid]["value"] in (None, False) or v.kind != "symptom":
                    out.append(Problem("card_schema", f"{vid} is reported by the patient but is not a true symptom finding",
                                       f"presenting.{st}.reported[{i}]",
                                       "report only symptom variables whose finding value is true"))
        return out

    def g2_problems(self, g2: Any) -> list[Problem]:
        return schema_problems(g2, self.g2_schema)

    # ------------------------------------------------------------------ the card

    def assemble(self, sk: Skeleton, g1: Mapping[str, Any], g2: Mapping[str, Mapping[str, Any]],
                 plans: Mapping[str, Mapping[str, Sequence]], provenance: Mapping[str, Any]) -> dict:
        """A ``card/1`` dict from the skeleton (background, conditions) and the answers: ``g2`` and ``plans`` map
        each state to its G2 answer and settled plan. Not validated: run ``validate_card`` on it."""
        notes = []
        for i, st in enumerate(sk.states):
            blk = g1["states"][st]
            notes.append({"id": f"n{2 * i + 1}", "kind": "patient_account", "state": st, "text": blk["account"]["text"],
                          "mentions": list(blk["account"]["mentions"])})
            notes.append({"id": f"n{2 * i + 2}", "kind": "gp_note", "state": st, "text": g2[st]["gp_note"]["text"],
                          "mentions": list(g2[st]["gp_note"]["mentions"])})
        return {
            "format": CARD_FORMAT,
            "id": sk.id,
            "background": dict(sk.background),
            "states": list(sk.states),
            "presenting": {st: {"reported": list(g1["states"][st]["presenting"]["reported"]),
                                "text": g1["states"][st]["presenting"]["text"]} for st in sk.states},
            "hidden": {
                "conditions": [{"id": c, "role": role, "attributes": dict(a)} for c, role, a in sk.conditions],
                "findings": {st: {vid: {"value": g1["states"][st]["findings"][vid]["value"],
                                        "caused_by": list(g1["states"][st]["findings"][vid]["caused_by"])}
                                  for vid in self.cat.variables} for st in sk.states},
                "error_plan": plan_to_json({st: plans[st] for st in sk.states}),
            },
            "observations": {st: json.loads(json.dumps(g2[st]["observations"])) for st in sk.states},
            "notes": notes,
            "provenance": dict(provenance),
        }

    # ------------------------------------------------------------------ repair

    @staticmethod
    def route(problem: Problem, states: Sequence[str] = (INITIAL_STATE,)) -> tuple[str, str | None]:
        """Which author a problem of an assembled card belongs to: ``("g1", None)`` or ``("g2", state)`` (state
        None when the path names none: all of G2's calls are redone). G1 owns ``hidden.findings``, ``presenting``
        and the patient accounts (even note positions); G2 owns ``observations``, ``hidden.error_plan`` and the
        GP notes. Anything else is G2's (the skeleton parts are not model-written, so a problem there is a
        pipeline bug that a repair will not fix)."""
        p = problem.path or ""
        m = re.match(r"notes\[(\d+)\]", p)
        if m:
            i = int(m.group(1))
            return ("g1", None) if i % 2 == 0 else ("g2", states[min(i // 2, len(states) - 1)])
        if p.startswith(("hidden.findings", "presenting", "states")):
            return "g1", None
        m = re.match(r"(?:observations|hidden\.error_plan)\.([a-z_]+)", p)
        return "g2", (m.group(1) if m and m.group(1) in states else None)

    def repair_user(self, role: str, original_user: str, previous: Mapping[str, Any], text: str) -> str:
        """The user message for a repair call: the original request, the author's own answer, the problems."""
        shape = ("`states` (each with `findings`, `presenting` and `account`)" if role == "g1"
                 else "`observations` and `gp_note`")
        mapping = ("Paths starting `hidden.findings.<state>` refer to `states.<state>.findings`, `presenting.<state>` to "
                   "`states.<state>.presenting`, `notes[0]`, `notes[2]`... to the `account` of the first, second... state."
                   if role == "g1" else
                   "Paths starting `observations.<state>` refer to your `observations`, an odd `notes[i]` to your "
                   "`gp_note`, `hidden.error_plan` is the plan above.")
        return (f"{original_user}\n\n---\nYour previous answer:\n{json.dumps(previous, sort_keys=True)}\n\n"
                f"The card assembled from your answer was checked. You write only {shape}, not a whole card; "
                f"return those parts again, corrected. {mapping}\n{text}")

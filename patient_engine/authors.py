"""The two model authors of a card (WP-C1-5): G1 writes the patient, G2 writes every test result.

::

    authors = Authors(catalogue)                       # schemas and prompts, built once per catalogue
    req1 = authors.g1_request(skeleton)                # dict(system, user, schema) for LLMClient.complete_json
    answer1 = client.complete_json(**req1, key="card-7:g1")
    answer1, problems = authors.g1_accept(skeleton, answer1)   # g1@2: joins the engine's findings to the answer
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

Patient author versions (D58). ``g1@2`` (default): the engine draws every state's findings (``profile``, the
reference generator's ``draw_findings``) and the model writes presenting and account around them; it sees symptoms
and signs only. ``g1@1``: the model wrote the findings too, and one call per patient wrote each at its most likely
value (audit ``findings.*`` failed on every Gemini g1@1 library).

What each author returns (the shapes are JSON Schemas derived from ``card_schema(catalogue)``)::

    G1  g1@2: {"states": {state: {"presenting", "account"}}}; ``g1_accept`` adds the engine's findings, giving g1@1's
        g1@1: {"states": {state: {"findings": {variable id: {"value", "caused_by"}},
                            "presenting": {"reported": [variable id], "text": str},
                            "account": {"text": str, "mentions": [variable id]}}}}      one call, every state
    G2  g2@3 (default): {"variants": [str]} per result pattern (the report bank; see below)
        g2@2: {"reports": {test id: [str per attempt]}, "gp_note": {"text", "mentions"}}; the values are
        the engine's (``g2_values``) and ``g2_merge`` joins them to the reports        one call per state
        g2@1: {"observations": {test id: [{"status", "values", "report"}]}, "gp_note": {...}}

Information boundary of g2@2 (review w7 B1): the result author's prompt is ``results_user`` of public inputs only
(age, sex, smoking, reported symptoms, every attempt's status and values). Review w8 B1: those values include the
definitive and tissue tests and the other attempts, which predict whether a result is wrong, so g2@2 text is not served.

g2@3 (default, D65): ``{"variants": [str x N_VARIANTS]}`` per (test, result pattern), asked through ``ReportBank`` with
``report_user(test, pattern)``: the test and that one attempt's own values, numbers as placeholders. A report's prompt
can carry nothing about whether that result is right beyond its own values. ``g2v3_part`` fills a state's reports from
the bank (keyed pick, numbers filled in) and builds the GP note from them; there is no per-card G2 call.

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

import hashlib
import json
import re
import string
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from pathway_sim.dists import sample, uniform

from .card import CARD_FORMAT, INITIAL_STATE, NOTE_KINDS, Finding
from .catalogue import Catalogue, Leaf, Test, TestOutput, Variable
from .problems import Problem
from .schema import card_schema, schema_problems
from .skeleton import Skeleton, common_facts, illness_ids, plan_to_json, settle_attempt
from .states import resolved_in_state

from .reference import draw_findings

PROMPT_DIR = Path(__file__).with_name("prompts")

#: role -> version id stored in ``provenance.prompts`` for new cards (the default of ``Authors``). A new wording is a
#: new file, a new entry in ``_STEMS`` and, when it becomes the default, a new value here.
#: ``g2@2`` (review w7 B1): the engine decides every result value from the settled plan and the model writes only the
#: report wording and the GP note from public inputs. ``g2@1`` (the model saw the findings and the plan and wrote
#: values and reports) is kept selectable (``Authors(cat, results_prompt="g2@1")``) for comparison only: its report
#: text carries the error plan, and ``patient_engine.reveal`` never serves it (``SAFE_RESULTS_PROMPTS``).
#: ``g1@2`` (G1 skew fix, 14 Nov night): the engine draws every state's findings from the catalogue
#: (``reference.draw_findings``, the reference generator's own sampler) and the model writes only the presenting
#: complaint and the account around them. ``g1@1`` (the model wrote the findings) is kept selectable
#: (``Authors(cat, patient_prompt="g1@1")``): one call per patient cannot produce population frequencies, so its
#: findings collapse to the most likely value (every asthma card wheezes, every lab sits at its median; audit
#: ``findings.*`` fails on every Gemini g1@1 library).
#: patient-author versions this module can build
PATIENT_VERSIONS = ("g1@1", "g1@2")
#: g1@2: finding kinds the patient author sees (the patient's own experience and what an examination finds);
#: labs, imaging, function and tissue truths stay with the engine
G1_VISIBLE_KINDS = ("symptom", "sign")
#: ``g2@3`` (review w8 B1): g2@2's one prompt per state held every test and attempt of the patient (definitive and
#: tissue results among them), so the wording of one report could carry whether that result was right. g2@3 asks for
#: the wording of one result at a time, with nothing in the prompt but that test and that attempt's own values
#: (numbers as placeholders): a report bank keyed by test and value pattern, shared by every card.
PROMPT_VERSIONS = {"patient": "g1@2", "results": "g2@3"}
_STEMS = {"g1@1": "g1_patient.v1", "g1@2": "g1_patient.v2", "g2@1": "g2_results.v1", "g2@2": "g2_results.v2",
          "g2@3": "g2_results.v3"}
#: result-author versions this module can build
RESULTS_VERSIONS = ("g2@1", "g2@2", "g2@3")
#: g2@3: wordings the model writes per result pattern (the engine picks one per attempt with a keyed number)
N_VARIANTS = 4
#: g2@3: longest wording the bank schema accepts
BANK_TEXT_MAX_CHARS = 400
#: g2@3: categories of first-contact tests whose attempt-1 report the GP note repeats (history, examination, X-ray)
GP_NOTE_CATEGORIES = ("history", "examination", "imaging")
#: g2@3: output types written as a placeholder (``{size_mm}``) that the engine fills with the number and unit
NUMERIC_TYPES = ("continuous", "size_mm")
#: g2@2: tests whose attempt 1 the GP note summarises (primary-care resources), definitive tests excluded
FIRST_CONTACT_RESOURCES = frozenset({"gp", "gp_appt", "lab", "poc_device", "xray"})
#: g2@2: longest report and note the schema accepts (short outputs keep the JSON intact)
REPORT_MAX_CHARS = 600
NOTE_MAX_CHARS = 900
#: g2@2: background fields a reader of the results has (I1: the persona hint, region and conditions are not given)
PUBLIC_BACKGROUND = ("age", "sex", "smoking_status", "pack_years")

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


def profile_text(cat: Catalogue, findings: Mapping[str, Finding]) -> str:
    """g1@2: one state's symptom and sign findings in words (present with their cause, then absent). Only the kinds in
    ``G1_VISIBLE_KINDS``; measured, imaging and tissue truths are never shown to the patient author."""
    lines = []
    for kind, head in (("symptom", "Symptoms"), ("sign", "Signs a doctor would find on examination")):
        present, absent = [], []
        for vid, v in cat.variables.items():
            if v.kind != kind or v.type != "binary":
                continue
            f = findings[vid]
            if f.value is True:
                cause = ", ".join(cat.conditions[c].label for c in f.caused_by) or "the background"
                label = _lower(v.label)
                present.append(f"{vid} ({label + '; ' if label != vid.replace('_', ' ') else ''}from {cause})")
            else:
                absent.append(vid)
        lines.append(f"  {head} present: {'; '.join(present) or 'none'}")
        lines.append(f"  {head} absent: {', '.join(absent) or 'none'}")
    return "\n".join(lines)


def _findings_json(findings: Mapping[str, Finding]) -> dict:
    return {vid: {"value": f.value, "caused_by": list(f.caused_by)} for vid, f in findings.items()}


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


# ============================================================================ g2@2: public inputs only

def show_value(v: Any, unit: str | None = None) -> str:
    """A reported value as the g2@2 prompt shows it (``yes``/``no``, a number with its unit, a level)."""
    if v is True:
        return "yes"
    if v is False:
        return "no"
    if isinstance(v, (int, float)):
        return f"{v:g}" + (f" {unit}" if unit else "")
    return str(v)


def parse_value(text: str, output: TestOutput) -> Any:
    """The inverse of ``show_value`` for one output (used by the offline fake and the tests)."""
    t = text.strip()
    if output.type == "binary":
        return t == "yes"
    if output.type in ("continuous", "size_mm"):
        return float(t.split()[0])
    return t


def public_background_text(bg: Mapping[str, Any]) -> str:
    parts = []
    if bg.get("age") is not None:
        parts.append(f"age {bg['age']}")
    if bg.get("sex") is not None:
        parts.append(f"sex {bg['sex']}")
    if bg.get("smoking_status") is not None:
        parts.append(f"smoking {bg['smoking_status']}")
    if bg.get("pack_years") is not None:
        parts.append(f"{bg['pack_years']} pack-years")
    return ", ".join(parts) or "not recorded"


def attempt_line(test: Test, k: int, status: str, values: Mapping[str, Any]) -> str:
    """One attempt as the g2@2 prompt shows it: status and the reported values (outputs that are null left out)."""
    if status != "ok":
        return f"  attempt {k + 1}: non-diagnostic"
    vals = "; ".join(f"{o.id}: {show_value(values[o.id], o.unit)}" for o in test.outputs if values.get(o.id) is not None)
    return f"  attempt {k + 1}: ok | {vals}"


def results_user(cat: Catalogue, background: Mapping[str, Any], reported: Sequence[str],
                 observations: Mapping[str, Sequence[Mapping[str, Any]]], gp_tests: Sequence[str]) -> str:
    """The g2@2 user prompt. Its only inputs are what a reader of the results has (I1, review w7 B1): the public
    background fields, the symptom ids the patient reported, every attempt's status and reported values, and the
    (fixed) list of first-contact tests. No condition, finding, error plan, state name, persona or card id can
    reach it, because this function is not given them."""
    bg = {k: background.get(k) for k in PUBLIC_BACKGROUND}
    said = ", ".join(_lower(cat.variables[v].label) if v in cat.variables else v.replace("_", " ") for v in reported)
    blocks = []
    for t in cat.tests.values():
        atts = observations[t.id]
        lines = [f"### {t.id}: {t.label} ({t.category}); {len(atts)} attempt(s)"]
        lines += [attempt_line(t, k, a["status"], a.get("values") or {}) for k, a in enumerate(atts)]
        blocks.append("\n".join(lines))
    return fill(load_prompt("g2@2", "user"), patient=public_background_text(bg), reported=said or "none",
                tests="\n\n".join(blocks), gp_tests=", ".join(gp_tests), n_tests=str(len(cat.tests)))


def _lower(s: str) -> str:
    return s[:1].lower() + s[1:]


# ============================================================================ g2@3: one result at a time

def report_pattern(test: Test, status: str, values: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """The key of a result in the g2@3 report bank: the status and every output the attempt reported, binary and
    categorical outputs as their shown value, numbers as a placeholder ``{output id}``. Outputs that are null are
    left out, as in the card. Nothing about the patient, the other tests or the other attempts is in it."""
    if status != "ok":
        return (("status", "non_diagnostic"),)
    out = [("status", "ok")]
    for o in test.outputs:
        v = values.get(o.id)
        if v is None:
            continue
        out.append((o.id, "{" + o.id + "}" if o.type in NUMERIC_TYPES else show_value(v)))
    return tuple(out)


def _pattern_lines(test: Test, pattern: Sequence[tuple[str, str]]) -> str:
    if dict(pattern).get("status") != "ok":
        return "status: non-diagnostic (the attempt gave no usable result)"
    lines = ["status: ok"]
    shown = dict(pattern)
    for o in test.outputs:
        if o.id not in shown:
            lines.append(f"- {o.id}: none")
            continue
        line = f"- {o.id}: {shown[o.id]}"
        if o.type in NUMERIC_TYPES:
            line += f" (a measurement{', unit ' + o.unit if o.unit else ''}; the number is filled in later)"
        lines.append(line)
    return "\n".join(lines)


def report_user(test: Test, pattern: Sequence[tuple[str, str]]) -> str:
    """The g2@3 user prompt for one result pattern: the test's id, name and category and the pattern. A function of
    the test and the pattern only (I1, review w8 B1): it is not given the card, the patient, the other attempts or the
    other tests, so two cards whose attempt reported the same pattern send the same prompt (one cached answer)."""
    return fill(load_prompt("g2@3", "user"), test_id=test.id, test_label=test.label, category=test.category,
                result=_pattern_lines(test, pattern), n_variants=str(N_VARIANTS))


_PLACEHOLDER_RX = re.compile(r"\{([a-z0-9_]+)\}")


def fill_report(template: str, test: Test, values: Mapping[str, Any]) -> str:
    """A bank wording with each ``{output id}`` placeholder replaced by the attempt's number and unit."""
    def sub(m: re.Match) -> str:
        o = test.output(m.group(1))
        return show_value(values[o.id], o.unit)
    return _PLACEHOLDER_RX.sub(sub, template)


# ============================================================================ the authors

class Authors:
    """Schemas and prompt builders of G1 and G2 for one catalogue. Stateless after construction, thread-safe."""

    def __init__(self, catalogue: Catalogue, results_prompt: str | None = None, patient_prompt: str | None = None):
        self.cat = catalogue
        self.results_version = results_prompt or PROMPT_VERSIONS["results"]
        if self.results_version not in RESULTS_VERSIONS:
            raise ValueError(f"unknown result-author version {self.results_version!r}; known: {RESULTS_VERSIONS}")
        self.patient_version = patient_prompt or PROMPT_VERSIONS["patient"]
        if self.patient_version not in PATIENT_VERSIONS:
            raise ValueError(f"unknown patient-author version {self.patient_version!r}; known: {PATIENT_VERSIONS}")
        #: what goes into ``provenance.prompts`` and the library manifest
        self.prompt_versions = {"patient": self.patient_version, "results": self.results_version}
        self._g1_request_cache: dict[tuple, dict] = {}
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
        # g2@2: the tests the GP note summarises, and the answer schema (report strings and a GP note only)
        gp = [t.id for t in catalogue.tests.values() if t.resource_kind in FIRST_CONTACT_RESOURCES
              and not any(o.measures.startswith("dx_") for o in t.outputs)]
        self.gp_tests = tuple(gp or [t.id for t in catalogue.tests.values()
                                     if not any(o.measures.startswith("dx_") for o in t.outputs)])
        gp_ids = [*self.gp_tests, *(f"{t}.{o.id}" for t in self.gp_tests for o in catalogue.tests[t].outputs)]
        report = {"type": "string", "minLength": 10, "maxLength": REPORT_MAX_CHARS}
        self.g2v2_schema: dict = {
            "type": "object", "required": ["reports", "gp_note"], "additionalProperties": False,
            "properties": {
                "reports": {"type": "object", "required": list(catalogue.tests), "additionalProperties": False,
                            "properties": {t.id: {"type": "array", "minItems": t.max_attempts, "maxItems": t.max_attempts,
                                                  "items": report} for t in catalogue.tests.values()}},
                "gp_note": {"type": "object", "required": ["text", "mentions"], "additionalProperties": False,
                            "properties": {"text": {"type": "string", "minLength": 10, "maxLength": NOTE_MAX_CHARS},
                                           "mentions": {"type": "array", "uniqueItems": True, "items": {"enum": gp_ids}}}},
            },
        }
        # g2@2 condition-blind name check: every non-healthy condition's label and id (the validator's rule 8
        # patterns for any primary), so a repair request never depends on which condition the patient has
        # (review w8 M1: the label, the id and the synonyms of ``validate.CONDITION_TERMS``)
        from .validate import condition_pattern
        self._names: dict[str, re.Pattern] = {c.id: condition_pattern(c) for c in catalogue.conditions.values()
                                              if c.cls != "healthy"}
        self._definitive = {t.id: {o.measures[3:] for o in t.outputs if o.measures.startswith("dx_")}
                            for t in catalogue.tests.values()}

        # g2@3: the answer of one bank request
        self.bank_schema: dict = {
            "type": "object", "required": ["variants"], "additionalProperties": False,
            "properties": {"variants": {"type": "array", "minItems": N_VARIANTS, "maxItems": N_VARIANTS,
                                        "items": {"type": "string", "minLength": 10,
                                                  "maxLength": BANK_TEXT_MAX_CHARS}}}}
        self._banks: dict[tuple, ReportBank] = {}
        self._banks_lock = threading.Lock()

    @property
    def v2(self) -> bool:
        return self.results_version == "g2@2"

    @property
    def v3(self) -> bool:
        return self.results_version == "g2@3"

    @property
    def profiled(self) -> bool:
        """g1@2: the engine draws the findings, the patient author writes presenting and account only."""
        return self.patient_version == "g1@2"

    @property
    def results_schema(self) -> dict:
        return self.bank_schema if self.v3 else self.g2v2_schema if self.v2 else self.g2_schema

    # ------------------------------------------------------------------ g2@3: the report bank

    def bank_request(self, test: Test, pattern: Sequence[tuple[str, str]]) -> dict:
        """``dict(system, user, schema)`` asking for ``N_VARIANTS`` wordings of one result pattern (``report_pattern``).
        Reads the catalogue's test and the pattern only."""
        return {"system": fill(load_prompt("g2@3", "system"), n_variants=str(N_VARIANTS)),
                "user": report_user(test, pattern), "schema": self.bank_schema}

    def bank_problems(self, test: Test, pattern: Sequence[tuple[str, str]], answer: Any) -> list[Problem]:
        """Problems of a bank answer: schema; per wording, the placeholders (each number of the pattern once, no
        other), the condition-blind name check (any condition's name or synonym, except what a definitive test
        tests for) and rule 9 (the wording says the opposite of a yes/no value). Reads only the answer, the test and
        the pattern, so a repair request says nothing about any patient."""
        probs = schema_problems(answer, self.bank_schema)
        if probs:
            return probs
        from .validate import report_contradictions
        shown = dict(pattern)
        numbers = {o.id for o in test.outputs if o.id in shown and o.type in NUMERIC_TYPES}
        sample_values = _sample_values(test, pattern)
        allowed = self._definitive.get(test.id, set())
        seen: dict[str, int] = {}
        for i, text in enumerate(answer["variants"]):
            path = f"variants[{i}]"
            found = _PLACEHOLDER_RX.findall(text)
            if sorted(found) != sorted(numbers) or re.sub(_PLACEHOLDER_RX, "", text).count("{") \
                    or re.sub(_PLACEHOLDER_RX, "", text).count("}"):
                want = ", ".join("{" + n + "}" for n in sorted(numbers)) or "none"
                probs.append(Problem("card_schema", f"the placeholders are {found or 'none'}; write each of these "
                                     f"exactly once and no other text in braces: {want}", path))
                continue
            doubled = [o.id for o in test.outputs if o.id in numbers and o.unit
                       and re.search(r"\{" + o.id + r"\}\s*" + re.escape(o.unit), text)]
            if doubled:
                probs.append(Problem("card_schema", f"the unit follows the placeholder of {doubled[0]}; the placeholder "
                                     "is replaced by the number with its unit, so leave the unit out", path))
            low = text.lower().replace("_", " ")
            if any(rx.search(low) for c, rx in self._names.items() if c not in allowed):
                probs.append(Problem("card_reveals_condition", "the text names a diagnosis; describe the reported "
                                     "values only, without naming a diagnosis or disease", path))
            for oid, v in report_contradictions(test, sample_values, fill_report(text, test, sample_values)):
                probs.append(Problem("card_report_contradiction", f"{oid} is {'yes' if v else 'no'}, but the text "
                                     f"says the opposite", path))
            key = " ".join(low.split())
            if key in seen:
                probs.append(Problem("card_schema", f"the same text as variants[{seen[key]}]; write a different "
                                     "version", path))
            seen.setdefault(key, i)
        return probs

    def bank_good(self, test: Test, pattern: Sequence[tuple[str, str]], answer: Any) -> tuple[str, ...]:
        """The wordings of a bank answer that have no problem (``bank_problems``), in order."""
        if schema_problems(answer, self.bank_schema):
            return ()
        bad = {p.path for p in self.bank_problems(test, pattern, answer)}
        return tuple(t for i, t in enumerate(answer["variants"]) if f"variants[{i}]" not in bad)

    @staticmethod
    def bank_repair_user(original_user: str, previous: Mapping[str, Any], problems: Sequence[Problem]) -> str:
        lines = list(dict.fromkeys(f"- {p.path or 'answer'}: {p.message}" for p in problems))
        return (f"{original_user}\n\n---\nYour previous answer:\n{json.dumps(previous, sort_keys=True)}\n\n"
                "Your answer failed validation. Fix every point below and return the whole JSON object again.\n"
                + "\n".join(lines[:20]))

    def report_bank(self, client, temperature: float | None = None, max_repairs: int = 2) -> "ReportBank":
        """The bank of ``client`` (one per client, temperature and repair count; shared by the threads of a run)."""
        key = (id(client), temperature, max_repairs)
        with self._banks_lock:
            if key not in self._banks:
                self._banks[key] = ReportBank(self, client, temperature, max_repairs)
            return self._banks[key]

    def g2v3_part(self, sk: Skeleton, g1: Mapping[str, Any], plan: Mapping[str, Sequence], state: str,
                  bank: "ReportBank") -> dict:
        """g2@3: the result author's part of a card for one state, ``{"observations", "gp_note"}``. Values are the
        engine's (``g2_values``); each attempt's report is a wording from the bank for that attempt's own pattern,
        picked with a keyed number (seed, index, state, test, attempt) that depends on nothing hidden, with the
        numbers filled in. The GP note joins the attempt-1 reports of the first-contact tests that gave a result."""
        obs = self.g2_values(sk, g1, plan, state)
        for tid, atts in obs.items():
            test = self.cat.tests[tid]
            for k, a in enumerate(atts):
                texts = bank.texts(test, report_pattern(test, a["status"], a["values"]))
                u = uniform(sk.seed, sk.index, "report_variant", state, tid, k)
                a["report"] = fill_report(texts[min(int(u * len(texts)), len(texts) - 1)], test, a["values"])
        gp = [t for t in self.gp_tests if obs[t] and obs[t][0]["status"] == "ok"
              and self.cat.tests[t].category in GP_NOTE_CATEGORIES]
        text = "First-contact results. " + " ".join(obs[t][0]["report"] for t in gp) if gp else \
            "First-contact tests gave no usable result yet."
        return {"observations": obs, "gp_note": {"text": text, "mentions": list(gp)}}

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

    def g1_request_schema_for(self, states: Sequence[str]) -> dict:
        """The schema the patient author answers with: g1@1 the whole ``g1_schema_for``; g1@2 presenting and account
        only (no findings), with ``reported`` limited to symptoms and ``mentions`` to symptoms and signs."""
        if not self.profiled:
            return self.g1_schema_for(states)
        key = tuple(states)
        if key not in self._g1_request_cache:
            text = self._text
            symptoms = [v for v, x in self.cat.variables.items() if x.kind == "symptom"]
            visible = [v for v, x in self.cat.variables.items() if x.kind in G1_VISIBLE_KINDS]
            block = {
                "type": "object", "required": ["presenting", "account"], "additionalProperties": False,
                "properties": {
                    "presenting": {"type": "object", "required": ["reported", "text"], "additionalProperties": False,
                                   "properties": {"reported": {"type": "array", "uniqueItems": True,
                                                               "items": {"enum": symptoms}}, "text": text}},
                    "account": {"type": "object", "required": ["text", "mentions"], "additionalProperties": False,
                                "properties": {"text": text, "mentions": {"type": "array", "uniqueItems": True,
                                                                          "items": {"enum": visible}}}}}}
            self._g1_request_cache[key] = {
                "type": "object", "required": ["states"], "additionalProperties": False,
                "properties": {"states": {"type": "object", "required": list(key), "additionalProperties": False,
                                          "properties": {st: block for st in key}}}}
        return self._g1_request_cache[key]

    def profile(self, sk: Skeleton) -> dict[str, dict[str, Finding]]:
        """g1@2: every state's findings, drawn by the engine exactly as the reference generator draws them
        (``reference.draw_findings``: deterministic in catalogue and skeleton, keyed numbers per variable)."""
        return {st: draw_findings(self.cat, sk, st) for st in sk.states}

    # ------------------------------------------------------------------ requests

    def g1_request(self, sk: Skeleton) -> dict:
        """``dict(system, user, schema)`` for the patient author (every state of the card in one answer).
        Reads the skeleton and the catalogue only (g1@2: and the engine's findings drawn from them)."""
        cat = self.cat
        ver = self.patient_version
        if self.profiled:
            prof = self.profile(sk)
            states = "\n\n".join(f"- {st}: {state_note(cat, sk, st)}\n{profile_text(cat, prof[st])}" for st in sk.states)
            user = fill(load_prompt(ver, "user"), card_id=sk.id, states=states,
                        background=_background_text(sk.background), conditions=_conditions_text(cat, sk), brief=sk.brief)
            return {"system": load_prompt(ver, "system"), "user": user, "schema": self.g1_request_schema_for(sk.states)}
        variables = "\n".join(_variable_line(cat, sk, v) for v in cat.variables.values())
        states = "\n".join(f"- {st}: {state_note(cat, sk, st)}" for st in sk.states)
        user = fill(load_prompt(ver, "user"),
                    card_id=sk.id, states=states,
                    background=_background_text(sk.background), conditions=_conditions_text(cat, sk),
                    brief=sk.brief, n_variables=str(len(cat.variables)), variables=variables)
        return {"system": load_prompt(ver, "system"), "user": user,
                "schema": self.g1_schema_for(sk.states)}

    def g1_accept(self, sk: Skeleton, answer: Any) -> tuple[dict | None, list[Problem]]:
        """The patient author's answer as the rest of the pipeline reads it (``{"states": {st: {findings, presenting,
        account}}}``) and its problems. g1@1: the answer itself and ``g1_problems``. g1@2: the answer is checked
        against its own schema, then the engine's findings (``profile``) are joined to it and ``presenting.reported``
        is checked against them. A problem list that is not empty comes with ``None``."""
        states = tuple(sk.states)
        if not self.profiled:
            probs = self.g1_problems(answer, states)
            return (None if probs else answer), probs
        probs = schema_problems(answer, self.g1_request_schema_for(states))
        if probs:
            return None, probs
        prof = self.profile(sk)
        full = {"states": {st: {"findings": _findings_json(prof[st]), "presenting": answer["states"][st]["presenting"],
                                "account": answer["states"][st]["account"]} for st in states}}
        probs = self.g1_problems(full, states)
        return (None if probs else full), probs

    def g2_request(self, sk: Skeleton, g1: Mapping[str, Any], plan: Mapping[str, Sequence], state: str = INITIAL_STATE
                   ) -> dict:
        """``dict(system, user, schema)`` for the result author of one ``state``. ``g1`` is the patient author's
        (valid) answer, ``plan`` the settled error plan of that state (``settle_error_plan(...)[state]``).

        g2@2 (default): the result values are the engine's (``g2_values``); the prompt is ``results_user`` of the
        public background, the reported symptoms and those values, nothing else."""
        if self.v2:
            obs = self.g2_values(sk, g1, plan, state)
            user = results_user(self.cat, sk.background, g1["states"][state]["presenting"]["reported"], obs,
                                self.gp_tests)
            return {"system": load_prompt("g2@2", "system"), "user": user, "schema": self.g2v2_schema}
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
        user = fill(load_prompt("g2@1", "user"),
                    card_id=sk.id, state=state, state_note=state_note(cat, sk, state),
                    background=_background_text(sk.background), conditions=_conditions_text(cat, sk), brief=sk.brief,
                    findings=_findings_text(cat, findings), tests="\n\n".join(blocks))
        return {"system": load_prompt("g2@1", "system"), "user": user, "schema": self.g2_schema}

    def g2_values(self, sk: Skeleton, g1: Mapping[str, Any], plan: Mapping[str, Sequence], state: str = INITIAL_STATE
                  ) -> dict[str, list[dict]]:
        """g2@2: every attempt's status and reported values, decided by the engine from the findings and the settled
        plan (``skeleton.settle_attempt``, as the reference generator does). Test id -> [{"status", "values"}]."""
        values = self.findings_of(g1, state)
        out: dict[str, list[dict]] = {}
        for t in self.cat.tests.values():
            atts = []
            for k, p in enumerate(plan[t.id]):
                planned, reported = settle_attempt(self.cat, t, k, sk, values, state)
                if planned != p:                      # the plan was settled from the same findings: a pipeline bug
                    raise AssertionError(f"{sk.id} {state} {t.id}[{k}]: settled attempt differs from the plan")
                atts.append({"status": planned.status, "values": dict(reported)})
            out[t.id] = atts
        return out

    def g2_merge(self, sk: Skeleton, g1: Mapping[str, Any], plan: Mapping[str, Sequence], state: str,
                 answer: Mapping[str, Any]) -> dict:
        """The result author's part of a card for one state, ``{"observations", "gp_note"}``: g2@1's answer as is,
        g2@2's reports joined to the engine's values."""
        if not self.v2:
            return dict(answer)                         # g2@1's answer, or g2@3's part (already merged)
        obs = self.g2_values(sk, g1, plan, state)
        for tid, atts in obs.items():
            for a, text in zip(atts, answer["reports"][tid]):
                a["report"] = text
        return {"observations": obs, "gp_note": dict(answer["gp_note"])}

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
        """Schema problems of a G2 answer; for g2@2 also the condition-blind name check (no report or note names a
        condition, except a definitive test's report naming what it tests for). The check reads only the answer
        and the catalogue, so a repair it asks for says nothing about the patient."""
        if self.v3:
            return []                                   # g2@3: every wording was checked in the bank
        if not self.v2:
            return schema_problems(g2, self.g2_schema)
        probs = schema_problems(g2, self.g2v2_schema)
        if probs:
            return probs
        hint = "describe the reported values only, without naming a diagnosis or disease"
        for tid, texts in g2["reports"].items():
            allowed = self._definitive.get(tid, set())
            for i, text in enumerate(texts):
                low = text.lower().replace("_", " ")
                if any(rx.search(low) for c, rx in self._names.items() if c not in allowed):
                    probs.append(Problem("card_reveals_condition", "the report names a diagnosis", f"reports.{tid}[{i}]", hint))
        low = g2["gp_note"]["text"].lower().replace("_", " ")
        if any(rx.search(low) for rx in self._names.values()):
            probs.append(Problem("card_reveals_condition", "the note names a diagnosis", "gp_note.text", hint))
        return probs

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

    #: g2@2 repair: codes whose validator message reads only the answer and the reported values (safe to send)
    _SAFE_MESSAGE_CODES = frozenset({"card_schema", "card_report_contradiction", "card_mention_unknown"})

    def repair_text(self, role: str, card_id: str, problems: Sequence[Problem]) -> str:
        """The problem list of a repair request. G1 and g2@1: ``validate.repair_prompt``. g2@2: paths in the
        author's own answer (``reports.<test>[i]``, ``gp_note``), and for any code whose message could depend on
        the hidden side (``card_reveals_condition`` names the true condition; plan and range codes read the plan) a
        fixed message instead. No card id and no state name (a state name like ``pneumonia_resolved`` names a
        condition)."""
        from .validate import repair_prompt
        if role == "g1" or not self.v2:
            return repair_prompt({"id": card_id}, problems)
        lines, seen = [], set()
        for p in problems:
            path = p.path or ""
            m = re.match(r"observations\.[a-z_]+\.([a-z0-9_]+)\[(\d+)\]", path)
            if m:
                path = f"reports.{m.group(1)}[{m.group(2)}]"
            elif re.match(r"notes\[\d+\]", path):
                path = "gp_note" + (".mentions" if ".mentions" in path else ".text")
            elif not path.startswith(("reports", "gp_note")):
                path = "answer"
            if p.code in self._SAFE_MESSAGE_CODES:
                msg = re.sub(r"observations\.[a-z_]+\.", "", p.message)
            elif p.code == "card_reveals_condition":
                msg = "the text names a diagnosis; describe the reported values only, without naming a diagnosis or disease"
            else:
                msg = "this part could not be accepted; describe exactly the reported values"
            line = f"- {path}: {msg}" + (f" ({p.hint})" if p.code in self._SAFE_MESSAGE_CODES and p.hint else "")
            if line not in seen:
                seen.add(line)
                lines.append(line)
        return "Your answer failed validation. Fix every point below and return the whole JSON object again.\n" + \
            "\n".join(lines[:20])

    def repair_user(self, role: str, original_user: str, previous: Mapping[str, Any], text: str) -> str:
        """The user message for a repair call: the original request, the author's own answer, the problems."""
        if role == "g2" and self.v2:
            return (f"{original_user}\n\n---\nYour previous answer:\n{json.dumps(previous, sort_keys=True)}\n\n"
                    f"{text}\nThe values are final; change only the texts.")
        if role == "g1" and self.profiled:
            shape = "`states` (each with `presenting` and `account`; the findings are fixed)"
        else:
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


# ============================================================================ g2@3: the bank

def _sample_values(test: Test, pattern: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Values that show as ``pattern`` (numbers 1.0), for checking a wording against rule 9."""
    shown = dict(pattern)
    out: dict[str, Any] = {}
    for o in test.outputs:
        if o.id not in shown:
            continue
        out[o.id] = 1.0 if o.type in NUMERIC_TYPES else parse_value(shown[o.id], o)
    return out


class ReportBank:
    """g2@3 report wordings per (test, result pattern), asked of the model once per pattern and shared by every card
    of a run (and, through the client's on-disk cache keyed by the prompt, by every later run). Thread-safe: one lock
    per pattern, so two cards needing the same pattern at once make one call.

    A pattern whose answer still has problems after ``max_repairs`` keeps its good wordings; if none is good, or the
    model never gives valid JSON, its wording is the reference template (``reference.report_text`` with
    placeholders), counted in ``fallbacks``. ``BudgetExceeded`` and endpoint errors propagate (the card stops)."""

    def __init__(self, authors: Authors, client, temperature: float | None = None, max_repairs: int = 2):
        self.authors, self.client, self.temperature, self.max_repairs = authors, client, temperature, max_repairs
        self._memo: dict[tuple, tuple[str, ...]] = {}
        self._locks: dict[tuple, threading.Lock] = {}
        self._lock = threading.Lock()
        self.fallbacks: list[tuple] = []
        self.repaired = 0

    def __len__(self) -> int:
        return len(self._memo)

    def texts(self, test: Test, pattern: tuple) -> tuple[str, ...]:
        key = (test.id, pattern)
        with self._lock:
            if key in self._memo:
                return self._memo[key]
            lk = self._locks.setdefault(key, threading.Lock())
        with lk:
            if key not in self._memo:
                self._memo[key] = self._ask(test, pattern)
            return self._memo[key]

    def _ask(self, test: Test, pattern: tuple) -> tuple[str, ...]:
        from .llm import LLMOutputError
        a = self.authors
        req = a.bank_request(test, pattern)
        tag = "bank:" + test.id + ":" + hashlib.blake2b(repr(pattern).encode(), digest_size=4).hexdigest()
        good: tuple[str, ...] = ()
        try:
            ans = self.client.complete_json(**req, key=tag, temperature=self.temperature)
            for rep in range(self.max_repairs + 1):
                probs = a.bank_problems(test, pattern, ans)
                if not probs or rep == self.max_repairs:
                    break
                self.repaired += 1
                ans = self.client.complete_json(**{**req, "user": a.bank_repair_user(req["user"], ans, probs)},
                                                key=f"{tag}:r{rep + 1}", temperature=self.temperature)
            good = a.bank_good(test, pattern, ans)
        except LLMOutputError:
            good = ()
        if not good:
            from .reference import report_text
            self.fallbacks.append((test.id, pattern))
            shown = dict(pattern)
            vals = {o.id: ("{" + o.id + "}" if o.type in NUMERIC_TYPES else parse_value(shown[o.id], o))
                    for o in test.outputs if o.id in shown}
            good = (report_text(test, "ok" if shown.get("status") == "ok" else "non_diagnostic", vals)
                    .replace(" (synthetic report)", ""),)
        return good

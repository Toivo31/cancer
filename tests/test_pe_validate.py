"""Card validation and repair request (WP-C1-4): one mutation test per rule, the repair message,
and a property test over reference cards (skipped while ``patient_engine.reference`` does not exist)."""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import pytest

from patient_engine.card import Card, card_from_json
from patient_engine.catalogue import load_catalogue
from patient_engine.problems import CODES, ERROR, WARNING, Problem
from patient_engine.validate import has_errors, repair_prompt, validate_card

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "patient_engine"
AA = "all_active"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(ROOT / "catalogue" / "_examples" / "tiny")


def example() -> dict:
    return json.loads((FIX / "card_example.json").read_text())


def free(d: dict) -> dict:
    """The example as a free-mode card (no error plan), for mutations that would also break the plan."""
    d["hidden"]["error_plan"] = None
    d["provenance"]["error_source"] = "free"
    return d


def second_state(d: dict) -> dict:
    """Add the state ``pneumonia_resolved`` as a copy of ``all_active`` (pneumonia no longer causes anything)."""
    d["states"] = [AA, "pneumonia_resolved"]
    r = "pneumonia_resolved"
    d["presenting"][r] = copy.deepcopy(d["presenting"][AA])
    d["observations"][r] = copy.deepcopy(d["observations"][AA])
    d["hidden"]["findings"][r] = copy.deepcopy(d["hidden"]["findings"][AA])
    d["hidden"]["error_plan"][r] = copy.deepcopy(d["hidden"]["error_plan"][AA])
    for f in d["hidden"]["findings"][r].values():
        f["caused_by"] = [c for c in f["caused_by"] if c != "pneumonia"]
    d["hidden"]["findings"][r]["fever"]["value"] = False
    d["hidden"]["findings"][r]["consolidation"]["value"] = False
    d["hidden"]["findings"][r]["consolidation"]["caused_by"] = []
    d["observations"][r]["history"][0]["values"]["fever"] = False
    d["observations"][r]["chest_xray"][0]["values"]["consolidation"] = False
    d["observations"][r]["chest_xray"][1]["values"]["consolidation"] = False
    d["hidden"]["error_plan"][r]["chest_xray"][0]["outputs"]["abnormal"] = "miss"
    return d


def check(tiny, mutate, *, plan_free: bool = False, base=None):
    d = base() if base else example()
    if plan_free:
        free(d)
    mutate(d)
    return validate_card(d, tiny)


def codes(problems) -> set[str]:
    return {p.code for p in problems}


def only(problems, code: str, path: str | None = None) -> list[Problem]:
    """Assert that ``code`` is the only code, optionally at ``path``; return its problems."""
    assert codes(problems) == {code}, [str(p) for p in problems]
    if path is not None:
        assert path in [p.path for p in problems], [p.path for p in problems]
    return problems


# ============================================================================ baseline

def test_valid_example_has_no_problems(tiny):
    assert validate_card(example(), tiny) == []


def test_accepts_card_object_and_matches_dict(tiny):
    d = example()
    assert validate_card(card_from_json(d), tiny) == validate_card(d, tiny) == []
    assert isinstance(card_from_json(d), Card)


def test_free_mode_example_is_valid(tiny):
    assert validate_card(free(example()), tiny) == []


def test_every_new_code_is_registered_and_documented():
    new = [c for c in CODES if c.startswith("card_") and c != "card_schema"]
    assert len(new) == 13
    assert all(CODES[c][1] for c in new)


def test_schema_problem_comes_first_and_card_schema_code(tiny):
    d = example()
    del d["observations"][AA]["history"]
    ps = validate_card(d, tiny)
    assert ps[0].code == "card_schema" and ps[0].path == "observations.all_active.history"
    assert has_errors(ps)


def test_garbage_does_not_raise(tiny):
    for junk in (None, [], "x", 3, {}, {"format": "card/1"}, {"hidden": {"conditions": 5, "findings": []}, "states": "x"}):
        ps = validate_card(junk, tiny)
        assert ps and has_errors(ps)
    d = example()
    d["hidden"]["findings"][AA]["fever"] = 5
    d["observations"][AA]["chest_ct"] = {"a": 1}
    d["notes"] = [3]
    assert has_errors(validate_card(d, tiny))


def test_random_damage_never_raises_and_always_gives_a_repair_prompt(tiny):
    import random
    rnd = random.Random(1)
    junk = [None, 5, -1.5, "x", [], {}, True, [1], {"a": 1}, {"id": ["x"]}]

    def paths(x, p=()):
        yield p
        if isinstance(x, dict):
            for k, v in x.items():
                yield from paths(v, p + (k,))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                yield from paths(v, p + (i,))

    base = example()
    for _ in range(250):
        d = copy.deepcopy(base)
        for _ in range(rnd.randint(1, 4)):
            p = rnd.choice([q for q in paths(d) if q])
            cur = d
            for k in p[:-1]:
                cur = cur[k]
            if rnd.random() < 0.2 and isinstance(cur, dict):
                del cur[p[-1]]
            else:
                cur[p[-1]] = copy.deepcopy(rnd.choice(junk))
        assert isinstance(repair_prompt(d, validate_card(d, tiny)), str)


# ============================================================================ rule 1

def test_r1_extra_state_in_states_only(tiny):
    def mut(d):
        d["states"] = [AA, "pneumonia_resolved"]
    ps = only(check(tiny, mut), "card_state_keys")
    paths = {p.path for p in ps}
    assert paths == {"presenting", "hidden.findings", "observations", "hidden.error_plan"}


def test_r1_section_has_state_not_in_states(tiny):
    def mut(d):
        d["presenting"]["pneumonia_resolved"] = copy.deepcopy(d["presenting"][AA])
    only(check(tiny, mut), "card_state_keys", "presenting.pneumonia_resolved")


def test_r1_first_state_must_be_all_active(tiny):
    def mut(d):
        second_state(d)
        d["states"] = ["pneumonia_resolved", AA]
    ps = check(tiny, mut)
    assert "card_state_keys" in codes(ps)
    assert [p.path for p in ps if p.code == "card_state_keys"] == ["states[0]"]
    assert not any(p.code == "card_schema" for p in ps)      # the rule replaces the schema's message


def test_r1_note_state_not_a_card_state(tiny):
    def mut(d):
        d["notes"][0]["state"] = "pneumonia_resolved"
    only(check(tiny, mut), "card_state_keys", "notes[0].state")


def test_r1_two_state_example_is_otherwise_valid(tiny):
    d = second_state(example())
    assert validate_card(d, tiny) == []


# ============================================================================ rule 2

def test_r2_two_primaries(tiny):
    def mut(d):
        d["hidden"]["conditions"][1]["role"] = "primary"
    only(check(tiny, mut), "card_conditions", "hidden.conditions")


def test_r2_no_primary(tiny):
    def mut(d):
        d["hidden"]["conditions"][0]["role"] = "coexisting"
    ps = check(tiny, mut)
    assert "card_conditions" in codes(ps)        # lung_cancer cannot be coexisting: the schema says so too


def test_r2_two_coexisting(tiny):
    def mut(d):
        d["hidden"]["conditions"][0] = {"id": "pneumonia", "role": "coexisting", "attributes": {}}
        d["hidden"]["conditions"][1]["role"] = "coexisting"
    ps = check(tiny, mut)
    assert {"card_conditions"} <= codes(ps)
    assert any("twice" in p.message for p in ps)


def test_r2_unknown_condition_has_did_you_mean(tiny):
    def mut(d):
        d["hidden"]["conditions"][1]["id"] = "pneumonai"
    ps = check(tiny, mut)
    hit = [p for p in ps if p.code == "card_conditions"]
    assert hit and hit[0].path == "hidden.conditions[1].id" and "pneumonia" in hit[0].hint
    assert not any(p.code == "card_schema" and p.path.startswith("hidden.conditions[1]") for p in ps)


def test_r2_attribute_level_unknown(tiny):
    def mut(d):
        d["hidden"]["conditions"][0]["attributes"]["stage"] = "V"
    ps = only(check(tiny, mut), "card_conditions", "hidden.conditions[0].attributes.stage")
    assert "'I'" in ps[0].hint


def test_r2_attribute_missing_and_unknown(tiny):
    d = example()
    del d["hidden"]["conditions"][0]["attributes"]["location"]
    d["hidden"]["conditions"][0]["attributes"]["grade"] = "high"
    ps = validate_card(d, tiny)
    assert codes(ps) == {"card_conditions"}
    assert {p.path for p in ps} == {"hidden.conditions[0].attributes.location", "hidden.conditions[0].attributes.grade"}


# ============================================================================ rules 3 and 4

def test_r3_cause_is_not_a_condition_of_the_card(tiny):
    def mut(d):
        del d["hidden"]["conditions"][1]
    ps = check(tiny, mut, plan_free=True)
    assert codes(ps) == {"card_cause_inactive"}
    assert "hidden.findings.all_active.fever.caused_by[0]" in [p.path for p in ps]


def test_r3_cause_resolved_in_state(tiny):
    d = second_state(example())
    d["hidden"]["findings"]["pneumonia_resolved"]["crp_true"]["caused_by"] = ["pneumonia"]
    ps = validate_card(d, tiny)
    assert codes(ps) == {"card_cause_inactive"}
    assert ps[0].path == "hidden.findings.pneumonia_resolved.crp_true.caused_by[0]"
    assert "resolved" in ps[0].message


def test_r3_true_finding_without_cause_is_fine_with_background_rate(tiny):
    d = example()
    d["hidden"]["findings"][AA]["fever"]["caused_by"] = []        # default p 0.03
    assert validate_card(d, tiny) == []


def test_r3_true_finding_without_cause_and_without_background_rate(tiny):
    fever = tiny.variables["fever"]
    no_default = dataclasses.replace(fever, given={k: v for k, v in fever.given.items() if k != "default"})
    cat = dataclasses.replace(tiny, variables={**tiny.variables, "fever": no_default})
    d = example()
    d["hidden"]["findings"][AA]["fever"]["caused_by"] = []
    ps = validate_card(d, cat)
    assert codes(ps) == {"card_unexplained_finding"}
    assert ps[0].path == "hidden.findings.all_active.fever.caused_by"
    # a default of exactly zero is no background rate either
    zero = dataclasses.replace(fever.given["default"], params={"p": 0.0})
    cat0 = dataclasses.replace(tiny, variables={**tiny.variables, "fever": dataclasses.replace(fever, given={**fever.given, "default": zero})})
    assert codes(validate_card(d, cat0)) == {"card_unexplained_finding"}


def test_r4_cause_without_catalogue_entry_is_a_warning(tiny):
    def mut(d):
        d["hidden"]["findings"][AA]["fever"]["caused_by"] = ["pneumonia", "lung_cancer"]
    ps = only(check(tiny, mut), "card_unsupported_cause", "hidden.findings.all_active.fever.caused_by[1]")
    assert ps[0].severity == WARNING and not has_errors(ps)


# ============================================================================ rule 5

def test_r5_too_many_attempts(tiny):
    def mut(d):
        a = d["observations"][AA]["chest_ct"]
        a.extend([copy.deepcopy(a[0]), copy.deepcopy(a[0])])
    ps = only(check(tiny, mut, plan_free=True), "card_attempts", "observations.all_active.chest_ct")
    assert "at most 2" in ps[0].message


def test_r5_non_diagnostic_where_the_test_cannot_fail(tiny):
    def mut(d):
        d["observations"][AA]["history"][0].update(status="non_diagnostic", values={})
    ps = only(check(tiny, mut, plan_free=True), "card_attempts", "observations.all_active.history[0]")
    assert not any(p.code == "card_schema" for p in ps)


def test_r5_non_diagnostic_allowed_where_the_test_can_fail(tiny):
    def mut(d):
        d["observations"][AA]["blood_count"][0].update(status="non_diagnostic", values={})
    assert check(tiny, mut, plan_free=True) == []


def test_r5_output_with_only_if_must_be_null_when_it_does_not_hold(tiny):
    def mut(d):
        d["observations"][AA]["chest_ct"][0]["values"]["nodule_seen"] = False
    ps = only(check(tiny, mut, plan_free=True), "card_only_if", "observations.all_active.chest_ct[0].values.size_mm")
    assert {p.path for p in ps} == {"observations.all_active.chest_ct[0].values.size_mm",
                                    "observations.all_active.chest_ct[0].values.location"}


def test_r5_output_with_only_if_needs_a_value_when_it_holds(tiny):
    def mut(d):
        d["observations"][AA]["chest_ct"][0]["values"]["size_mm"] = None
    only(check(tiny, mut, plan_free=True), "card_only_if", "observations.all_active.chest_ct[0].values.size_mm")


def test_r5_finding_with_only_if(tiny):
    def mut(d):
        f = d["hidden"]["findings"][AA]
        f["lung_lesion"]["value"] = False
        f["lung_lesion"]["caused_by"] = []
    ps = check(tiny, mut, plan_free=True)
    assert "card_only_if" in codes(ps)
    assert "hidden.findings.all_active.lesion_size_mm.value" in [p.path for p in ps if p.code == "card_only_if"]


def test_r5_typed_values_and_required_outputs_are_the_schemas(tiny):
    def mut(d):
        d["observations"][AA]["blood_count"][0]["values"]["crp"] = "high"
        del d["observations"][AA]["history"][0]["values"]["fever"]
    ps = check(tiny, mut, plan_free=True)
    assert codes(ps) == {"card_schema"}
    assert {p.path for p in ps} == {"observations.all_active.blood_count[0].values.crp",
                                    "observations.all_active.history[0].values.fever"}


# ============================================================================ rule 6

def test_r6_miss_must_not_show_the_finding(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][0]["values"]["abnormal"] = True      # planned miss
        d["observations"][AA]["chest_xray"][0]["report"] = "Abnormal opacity seen."
    ps = only(check(tiny, mut), "card_plan_mismatch", "observations.all_active.chest_xray[0].values.abnormal")
    assert "miss" in ps[0].message


def test_r6_correct_must_agree_with_the_truth(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][1]["values"]["abnormal"] = False        # planned correct, lesion present
        d["observations"][AA]["chest_xray"][1]["report"] = "Consolidation persists; no separate lesion."
    only(check(tiny, mut), "card_plan_mismatch", "observations.all_active.chest_xray[1].values.abnormal")


def test_r6_false_alarm_must_show_the_finding(tiny):
    def mut(d):
        d["hidden"]["error_plan"][AA]["chest_xray"][1]["outputs"]["consolidation"] = "false_alarm"
        d["hidden"]["findings"][AA]["consolidation"].update(value=False, caused_by=[])
        d["observations"][AA]["chest_xray"][0]["values"]["consolidation"] = False
        d["observations"][AA]["chest_xray"][0]["report"] = "No lesion identified."
        d["observations"][AA]["chest_xray"][1]["values"]["consolidation"] = False
        d["observations"][AA]["chest_xray"][1]["report"] = "A rounded 18 mm opacity is seen."
        d["observations"][AA]["history"][0]["report"] = "Cough for four weeks, fever for three days. No weight loss reported."
    ps = check(tiny, mut)
    assert codes(ps) == {"card_plan_mismatch"}
    assert ps[0].path == "observations.all_active.chest_xray[1].values.consolidation"
    # and a planned false alarm that does show the finding is accepted
    def ok(d):
        mut(d)
        d["observations"][AA]["chest_xray"][1]["values"]["consolidation"] = True
        d["observations"][AA]["chest_xray"][1]["report"] = "Consolidation, and a rounded 18 mm opacity is seen."
    assert check(tiny, ok) == []


def test_r6_measured_value_must_follow_the_plan(tiny):
    def far(d):
        d["observations"][AA]["blood_count"][0]["values"]["crp"] = 200.0            # planned correct, truth 85, sd 2
        d["observations"][AA]["blood_count"][0]["report"] = "CRP 200 mg/L, Hb 127 g/L."
    ps = only(check(tiny, far), "card_plan_mismatch", "observations.all_active.blood_count[0].values.crp")
    assert "away from the true" in ps[0].message

    def wrong_but_close(d):
        d["hidden"]["error_plan"][AA]["blood_count"][0]["outputs"]["crp"] = "wrong"
    only(check(tiny, wrong_but_close), "card_plan_mismatch", "observations.all_active.blood_count[0].values.crp")

    def wrong_and_far(d):
        wrong_but_close(d)
        far(d)
    assert check(tiny, wrong_and_far) == []


def test_r6_categorical_outcomes(tiny):
    def mut(d):
        d["hidden"]["error_plan"][AA]["chest_ct"][0]["outputs"]["location"] = "wrong"
    only(check(tiny, mut), "card_plan_mismatch", "observations.all_active.chest_ct[0].values.location")

    def ok(d):
        mut(d)
        d["observations"][AA]["chest_ct"][0]["values"]["location"] = "central"
    assert check(tiny, ok) == []


def test_r6_status_and_attempt_count_must_match_the_plan(tiny):
    def status(d):
        d["observations"][AA]["chest_xray"][2].update(status="ok", values={"abnormal": True, "consolidation": True},
                                                      report="Nothing new; consolidation seen, abnormal.")
    ps = only(check(tiny, status), "card_plan_mismatch", "observations.all_active.chest_xray[2].status")

    def count(d):
        del d["observations"][AA]["chest_xray"][2]
    only(check(tiny, count), "card_plan_mismatch", "observations.all_active.chest_xray")


def test_r6_free_mode_has_no_plan_to_break(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][0]["values"]["abnormal"] = True
        d["observations"][AA]["chest_xray"][0]["report"] = "Abnormal opacity seen."
    assert check(tiny, mut, plan_free=True) == []


# ============================================================================ rule 7

def test_r7_background_value_out_of_range(tiny):
    def mut(d):
        d["background"]["age"] = 150
    ps = only(check(tiny, mut), "card_value_range", "background.age")
    assert "18" in ps[0].message and "100" in ps[0].message


def test_r7_finding_out_of_range(tiny):
    def mut(d):
        d["hidden"]["findings"][AA]["lesion_size_mm"]["value"] = 400.0
        d["observations"][AA]["chest_ct"][0]["values"]["size_mm"] = 400.0
        d["observations"][AA]["chest_ct"][0]["report"] = "Peripheral 400 mm nodule."
    ps = check(tiny, mut)
    assert codes(ps) == {"card_value_range"}
    assert {p.path for p in ps} == {"hidden.findings.all_active.lesion_size_mm.value",
                                    "observations.all_active.chest_ct[0].values.size_mm"}


def test_r7_negative_size(tiny):
    def mut(d):
        d["observations"][AA]["chest_ct"][0]["values"]["size_mm"] = -3.0
    ps = check(tiny, mut, plan_free=True)
    assert "card_value_range" in codes(ps)


def test_r7_measured_value_far_from_truth_without_a_plan_is_a_warning(tiny):
    def mut(d):
        d["observations"][AA]["blood_count"][0]["values"]["crp"] = 120.0
    ps = only(check(tiny, mut, plan_free=True), "card_implausible", "observations.all_active.blood_count[0].values.crp")
    assert ps[0].severity == WARNING


def test_r7_a_planned_wrong_value_is_not_implausible(tiny):
    def mut(d):
        d["hidden"]["error_plan"][AA]["blood_count"][0]["outputs"]["crp"] = "wrong"
        d["observations"][AA]["blood_count"][0]["values"]["crp"] = 120.0
    assert check(tiny, mut) == []


# ============================================================================ rule 8

def test_r8_unknown_mention(tiny):
    def mut(d):
        d["notes"][0]["mentions"] = ["fevr"]
    ps = only(check(tiny, mut), "card_mention_unknown", "notes[0].mentions[0]")
    assert "fever" in ps[0].hint


def test_r8_known_mention_forms(tiny):
    def mut(d):
        d["notes"][0]["mentions"] = ["fever", "chest_xray", "chest_ct.size_mm"]
    assert check(tiny, mut) == []


def test_r8_note_names_the_hidden_primary_condition(tiny):
    def mut(d):
        d["notes"][1]["text"] = "Chest X-ray shows consolidation; the picture suggests lung cancer. Review in six weeks."
    ps = only(check(tiny, mut), "card_reveals_condition", "notes[1].text")
    assert ps[0].severity == WARNING


def test_r8_note_may_name_it_when_a_mention_reveals_it(tiny):
    def mut(d):
        d["notes"][1]["text"] = "CT shows a nodule: lung cancer is likely."
        d["notes"][1]["mentions"] = ["lung_lesion"]            # present, caused by lung_cancer alone
    assert check(tiny, mut) == []
    def shared(d):
        mut(d)
        d["notes"][1]["mentions"] = ["cough_3wk"]              # caused by two conditions: reveals nothing
    assert codes(check(tiny, shared)) == {"card_reveals_condition"}


def test_r8_presenting_text_and_report_are_checked_too(tiny):
    def mut(d):
        d["presenting"][AA]["text"] = "I think I have Lung Cancer."
        d["observations"][AA]["history"][0]["report"] = "Cough for four weeks. No weight loss. Query lung cancer."
    ps = only(check(tiny, mut), "card_reveals_condition")
    assert {p.path for p in ps} == {"presenting.all_active.text", "observations.all_active.history[0].report"}


def test_r8_id_form_and_healthy_primary(tiny):
    def mut(d):
        d["notes"][0]["text"] = "Suspected lung_cancer."
    assert codes(check(tiny, mut)) == {"card_reveals_condition"}
    # a healthy primary has no diagnosis to leak
    h = example()
    h["hidden"]["conditions"] = [{"id": "healthy", "role": "primary", "attributes": {}}]
    for f in h["hidden"]["findings"][AA].values():
        f["caused_by"] = []
    ps = validate_card(h, tiny)
    assert "card_reveals_condition" not in codes(ps)


# ============================================================================ rule 9

def test_r9_report_denies_a_true_output(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][1]["report"] = "Consolidation persists. No abnormality seen."
    ps = only(check(tiny, mut), "card_report_contradiction", "observations.all_active.chest_xray[1].report")
    assert ps[0].severity == WARNING


def test_r9_report_denies_a_true_binary_symptom(tiny):
    def mut(d):
        d["observations"][AA]["history"][0]["report"] = "No cough. Fever for three days. No weight loss reported."
    only(check(tiny, mut), "card_report_contradiction", "observations.all_active.history[0].report")


def test_r9_report_asserts_a_false_output(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][0]["report"] = "Consolidation seen. Abnormality seen in the right lower lobe."
    only(check(tiny, mut), "card_report_contradiction", "observations.all_active.chest_xray[0].report")


def test_r9_negations_and_empty_reports_are_fine(tiny):
    def mut(d):
        d["observations"][AA]["chest_xray"][0]["report"] = "Consolidation. No abnormality of the pleura beyond that."
        d["observations"][AA]["blood_count"][0]["report"] = ""
    ps = check(tiny, mut)
    assert not any(p.code == "card_report_contradiction" and "blood_count" in p.path for p in ps)


# ============================================================================ repair_prompt

def _problems(n: int, severity_error: bool = True) -> list[Problem]:
    code = "card_plan_mismatch" if severity_error else "card_implausible"
    return [Problem(code, f"observations.all_active.chest_xray: planned miss, so the test must not show the finding: value must be false (lung_lesion is true) {i}",
                    path=f"observations.all_active.test_{i}[0].values.abnormal",
                    hint="planned outcome 'miss' is fixed; change the value, not the plan") for i in range(n)]


def test_repair_prompt_is_deterministic_and_lists_every_error_path(tiny):
    d = example()
    d["hidden"]["conditions"][0]["attributes"]["stage"] = "V"
    d["notes"][0]["mentions"] = ["fevr"]
    d["observations"][AA]["chest_xray"][0]["values"]["abnormal"] = True
    d["observations"][AA]["chest_xray"][0]["report"] = "Abnormal opacity seen."
    ps = validate_card(d, tiny)
    errs = [p for p in ps if p.severity == ERROR]
    assert len(errs) == 3
    a, b = repair_prompt(d, ps), repair_prompt(copy.deepcopy(d), list(ps))
    assert a == b
    for p in errs:
        assert f"- {p.path}: " in a
    assert "example:000001" in a and "JSON only" in a
    assert repair_prompt(json.dumps(d), ps) == a


def test_repair_prompt_for_ten_problems_is_short():
    text = repair_prompt({"id": "x:1"}, _problems(10))
    assert len(text) < 2000, len(text)
    for p in _problems(10):
        assert p.path in text


def test_repair_prompt_never_cuts_an_error_path():
    text = repair_prompt(None, _problems(25))
    for p in _problems(25):
        assert p.path in text


def test_repair_prompt_warnings_only_as_space_allows():
    ps = _problems(3, severity_error=False) + _problems(2)
    text = repair_prompt({"id": "c"}, ps)
    assert text.index("test_0[0]") < text.index("Also, if you can")       # errors first
    assert text.count("\n- ") == 5
    many = repair_prompt({"id": "c"}, _problems(10) + _problems(4, severity_error=False))
    assert "Also, if you can" not in many and len(many) < 2000
    assert "(unnamed)" in repair_prompt(None, [])


# ============================================================================ property test over reference cards

def test_reference_cards_have_no_errors(tiny):
    try:
        from patient_engine import reference
        generate_reference = reference.generate_reference
    except (ImportError, AttributeError):
        pytest.skip("patient_engine.reference is built in parallel (WP-C1-3) and is not available yet")
    from patient_engine.skeleton import design_library
    skeletons = design_library(tiny, None, 0.1, 7)[:200]   # design_library returns the skeletons themselves
    assert len(skeletons) >= 100
    cards = [generate_reference(tiny, s, 7) for s in skeletons]
    for card in cards:
        errs = [p for p in validate_card(card, tiny) if p.severity == ERROR]
        assert not errs, (card.id, [str(p) for p in errs])

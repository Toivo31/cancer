"""Card states for the encounter loop (WP-C8-2, tickets T1 and T2): ``patient_engine.states``, multi-state
skeletons, the reference generator's resolved states, and the validator over them."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from patient_engine.card import INITIAL_STATE, Card, card_from_json, card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.reference import draw_findings, generate_reference
from patient_engine.skeleton import (make_design, make_skeleton, proportional_design, skeleton_from_json)
from patient_engine.states import next_state, persisting_symptoms, resolvable_conditions, resolved_in_state, states_for
from patient_engine.validate import validate_card
from patient_engine.problems import ERROR

ROOT = Path(__file__).resolve().parent.parent
TINY = ROOT / "catalogue" / "_examples" / "tiny"
LUNG = ROOT / "catalogue" / "lung-primary-care"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def cards_of(cat, n, co_rate, seed=3):
    d = proportional_design(n, co_rate)
    return [generate_reference(cat, make_skeleton(cat, i, d, seed)) for i in range(n)]


def card_with(cat, primary: str, coexisting: bool, seed=3) -> Card:
    d = make_design(cat, {primary: 60}, 1.0 if coexisting else 0.0)
    for i in range(d.n):
        c = generate_reference(cat, make_skeleton(cat, i, d, seed))
        if (len(c.hidden.conditions) == 2) == coexisting:
            return c
    raise AssertionError("no such card")


# ---------------------------------------------------------------- names and next_state

def test_state_names_by_number_of_illnesses():
    assert states_for([]) == (INITIAL_STATE,)
    assert states_for(["pneumonia"]) == (INITIAL_STATE, "pneumonia_resolved")
    assert states_for(["pneumonia", "copd"]) == (INITIAL_STATE, "pneumonia_resolved", "copd_resolved", "all_resolved")
    assert resolved_in_state("all_resolved", ["a", "b"]) == {"a", "b"}
    assert resolved_in_state("a_resolved", ["a", "b"]) == {"a"}
    assert resolved_in_state(INITIAL_STATE, ["a", "b"]) == frozenset()
    with pytest.raises(ValueError):
        resolved_in_state("c_resolved", ["a", "b"])


def test_states_follow_the_catalogue_names_and_the_cards_illnesses(tiny):
    allowed = set(tiny.states())
    seen = Counter()
    for c in cards_of(tiny, 400, 0.4):
        assert c.states[0] == INITIAL_STATE and set(c.states) <= allowed
        ill = [x.id for x in c.hidden.conditions if tiny.conditions[x.id].cls == "other_illness"]
        assert c.states == states_for(ill)
        seen[len(c.states)] += 1
    assert seen[1] and seen[2]                        # healthy-with-nothing / cancer alone, and one-illness cards


def test_next_state_on_one_and_two_illness_cards(tiny):
    c = card_with(tiny, "lung_cancer", True)          # cancer + pneumonia
    assert c.states == (INITIAL_STATE, "pneumonia_resolved")
    assert resolvable_conditions(c) == ("pneumonia",)
    assert next_state(c, set()) == INITIAL_STATE
    assert next_state(c, {"pneumonia"}) == "pneumonia_resolved"
    assert next_state(c, ["pneumonia"]) == "pneumonia_resolved"                  # any collection
    assert next_state(c, {"lung_cancer"}) == INITIAL_STATE                       # a cancer never resolves
    assert next_state(c, {"lung_cancer", "pneumonia", "no_such_condition"}) == "pneumonia_resolved"
    cancer_only = card_with(tiny, "lung_cancer", False)
    assert cancer_only.states == (INITIAL_STATE,)
    assert next_state(cancer_only, {"pneumonia"}) == INITIAL_STATE               # treating what is not there changes nothing

    two = Card(**{**c.__dict__, "states": states_for(["pneumonia", "copd"])})     # a card with two illnesses
    assert next_state(two, {"copd"}) == "copd_resolved"
    assert next_state(two, {"copd", "pneumonia"}) == "all_resolved"
    assert next_state(two, {"pneumonia"}) == "pneumonia_resolved"
    broken = Card(**{**c.__dict__, "states": (INITIAL_STATE, "pneumonia_resolved", "copd_resolved")})
    with pytest.raises(ValueError):
        next_state(broken, {"copd", "pneumonia"})                                # no state for that combination


def test_skeleton_states_round_trip(tiny):
    d = proportional_design(60, 0.5)
    for i in range(60):
        sk = make_skeleton(tiny, i, d, 4)
        assert skeleton_from_json(sk.to_json()).states == sk.states
        assert set(sk.error_plan) == set(sk.states)


# ---------------------------------------------------------------- resolved states: findings

def test_pneumonia_alone_resolves_and_its_findings_disappear(tiny):
    d = make_design(tiny, {"pneumonia": 400}, 0.0)
    gone_fever = crp_drop = n = 0
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 5))
        assert c.states == (INITIAL_STATE, "pneumonia_resolved")
        a, r = c.hidden.findings[INITIAL_STATE], c.hidden.findings["pneumonia_resolved"]
        assert all("pneumonia" not in f.caused_by for f in r.values())
        if a["fever"].value:                                                  # pneumonia caused it (or the background)
            n += 1
            gone_fever += not r["fever"].value
        crp_drop += r["crp_true"].value < a["crp_true"].value
    assert gone_fever / n > 0.9                                               # background rate 0.03 only
    assert crp_drop / d.n > 0.9


def test_cancer_findings_survive_the_resolution_of_the_coexisting_illness(tiny):
    d = make_design(tiny, {"lung_cancer": 300}, 1.0)
    checked = 0
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 6))
        if c.states == (INITIAL_STATE,):
            continue
        a, r = c.hidden.findings[INITIAL_STATE], c.hidden.findings["pneumonia_resolved"]
        for name, fa in a.items():
            fr = r[name]
            assert "pneumonia" not in fr.caused_by
            if "lung_cancer" in fa.caused_by or not fa.caused_by:             # not explained by the resolved illness alone
                assert fr.value == fa.value, name                              # keeps its value
                assert fr.caused_by == tuple(x for x in fa.caused_by if x != "pneumonia")
            elif fa.value is True and fa.caused_by == ("pneumonia",):
                checked += 1
            if fr.value is True and isinstance(fr.value, bool):
                assert fa.value is True                                        # nothing appears because the state changed
        assert a["lung_lesion"].value is True and r["lung_lesion"].value is True
        assert r["lesion_size_mm"].value == a["lesion_size_mm"].value
        assert c.hidden.findings["pneumonia_resolved"]["consolidation"].value in (True, False)
    assert checked > 50


def test_the_resolved_state_is_a_function_of_the_skeleton_and_independent_of_other_states(tiny):
    d = make_design(tiny, {"lung_cancer": 40}, 1.0)
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 8)
        assert draw_findings(tiny, sk, "pneumonia_resolved") == draw_findings(tiny, sk, "pneumonia_resolved") \
            if "pneumonia_resolved" in sk.states else True
    c1 = generate_reference(tiny, make_skeleton(tiny, 3, d, 8))
    assert c1 == generate_reference(tiny, make_skeleton(tiny, 3, d, 8))
    assert card_from_json(card_to_json(c1)) == c1


def test_test_accuracy_follows_the_conditions_still_active(tiny):
    """Chest X-ray specificity is 0.8 with pneumonia and 0.902 otherwise: false alarms on a lesion-free chest
    drop when the pneumonia has resolved."""
    d = make_design(tiny, {"pneumonia": 1500}, 0.0)
    fa = Counter()
    n = Counter()
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 9))
        for state in c.states:
            if c.hidden.findings[state]["lung_lesion"].value:
                continue
            for att in c.observations[state]["chest_xray"]:
                if att.status == "ok":
                    n[state] += 1
                    fa[state] += att.values["abnormal"] is True
    assert abs(fa[INITIAL_STATE] / n[INITIAL_STATE] - 0.2) < 0.03
    assert abs(fa["pneumonia_resolved"] / n["pneumonia_resolved"] - 0.098) < 0.03


def test_presenting_follows_the_state(tiny):
    d = make_design(tiny, {"pneumonia": 200}, 0.0)
    fewer = 0
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 10))
        a, r = c.presenting[INITIAL_STATE], c.presenting["pneumonia_resolved"]
        for state, p in ((INITIAL_STATE, a), ("pneumonia_resolved", r)):
            assert all(c.hidden.findings[state][v].value is True for v in p.reported)
        fewer += len(r.reported) < len(a.reported)
    assert fewer > 50                                                         # most patients report less once the illness is gone


def test_persisting_symptoms_with_and_without_the_catalogue(tiny):
    d = make_design(tiny, {"lung_cancer": 300}, 1.0)
    saw_cancer_symptom = saw_pneumonia_only = 0
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 12))
        for state in c.states:
            full = persisting_symptoms(c, state, tiny)
            assert full == {v for v, f in c.hidden.findings[state].items()
                            if f.value is True and tiny.variables[v].kind == "symptom"}
            assert persisting_symptoms(c, state) <= full                     # the fallback is a subset
            assert "crp_true" not in full and "lung_lesion" not in full       # signs and truths are not symptoms
        if len(c.states) == 2:
            before, after = persisting_symptoms(c, INITIAL_STATE, tiny), persisting_symptoms(c, "pneumonia_resolved", tiny)
            assert after <= before
            saw_cancer_symptom += bool(after)
            saw_pneumonia_only += bool(before) and not after
    assert saw_cancer_symptom and saw_pneumonia_only
    with pytest.raises(KeyError):
        persisting_symptoms(c, "no_state", tiny)


# ---------------------------------------------------------------- validator property tests

def _no_problems(cat, n, seed, co_rate=0.3):
    d = proportional_design(n, co_rate)
    states = Counter()
    for i in range(n):
        card = generate_reference(cat, make_skeleton(cat, i, d, seed, plan=False))
        states[len(card.states)] += 1
        errs = [p for p in validate_card(card, cat) if p.severity == ERROR]
        assert not errs, (card.id, [str(p) for p in errs])
    return states


def test_3000_multi_state_cards_of_the_tiny_catalogue_validate():
    states = _no_problems(load_catalogue(TINY), 3000, 21)
    assert states[1] > 100 and states[2] > 100


@pytest.mark.skipif(not LUNG.is_dir(), reason="lung catalogue missing")
def test_500_multi_state_cards_of_the_lung_catalogue_validate():
    states = _no_problems(load_catalogue(LUNG), 500, 22)
    assert states[2] > 50


def test_validator_flags_a_resolved_cause_left_in_a_resolved_state(tiny):
    c = card_with(tiny, "pneumonia", False)
    data = card_to_json(c)
    data["hidden"]["findings"]["pneumonia_resolved"]["crp_true"]["caused_by"] = ["pneumonia"]
    assert any(p.code == "card_cause_inactive" for p in validate_card(data, tiny))

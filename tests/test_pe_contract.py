"""Contract tests for card/1, library/1 and cohort/1 (WP-C1-1)."""

from __future__ import annotations

import copy
import dataclasses
import json
import typing
from pathlib import Path

import pytest

from patient_engine import card as C

FIX = Path(__file__).parent / "fixtures" / "patient_engine"


def _example() -> dict:
    return json.loads((FIX / "card_example.json").read_text())


# ---------------------------------------------------------------- round trip

def test_card_round_trip_is_exact():
    d = _example()
    assert C.card_to_json(C.card_from_json(d)) == d


def test_card_round_trip_survives_json_text():
    d = _example()
    card = C.card_from_json(json.loads(json.dumps(C.card_to_json(C.card_from_json(d)))))
    assert C.card_to_json(card) == d


def test_card_accessors():
    card = C.card_from_json(_example())
    assert card.primary_condition == "lung_cancer"
    assert card.states[0] == C.INITIAL_STATE
    a = card.attempt("chest_xray", 1)
    assert a.status == "ok" and a.values["abnormal"] is True
    assert card.attempt("chest_xray", 2).status == "non_diagnostic"


def test_card_from_json_rejects_other_format():
    d = _example()
    d["format"] = "card/0"
    with pytest.raises(ValueError):
        C.card_from_json(d)


def test_card_is_frozen():
    card = C.card_from_json(_example())
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- I1: hidden and revealed are different types

def _dataclass_types_in(tp, seen: set) -> None:
    """Collect dataclass types reachable through the type hints of ``tp``."""
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        if tp in seen:
            return
        seen.add(tp)
        for f in typing.get_type_hints(tp).values():
            _dataclass_types_in(f, seen)
        return
    for arg in typing.get_args(tp):
        _dataclass_types_in(arg, seen)


def _public_closure() -> set:
    seen: set = set()
    for t in C.PUBLIC_TYPES:
        _dataclass_types_in(t, seen)
    return seen


def test_i1_public_types_have_no_hidden_field_names():
    for t in _public_closure():
        names = {f.name for f in dataclasses.fields(t)}
        assert not names & C.HIDDEN_FIELD_NAMES, f"{t.__name__} has hidden field(s) {names & C.HIDDEN_FIELD_NAMES}"


def test_i1_public_types_do_not_reach_hidden_types():
    hidden_types = {C.Card, C.Hidden, C.ConditionTruth, C.Finding, C.PlannedAttempt, C.Note, C.Attempt}
    reached = _public_closure()
    assert not reached & hidden_types, f"revealed side reaches {sorted(t.__name__ for t in reached & hidden_types)}"


def test_i1_named_types_are_covered():
    assert {C.PublicView, C.RevealedObservation} <= set(C.PUBLIC_TYPES)
    assert {"hidden", "conditions", "findings", "caused_by"} <= C.HIDDEN_FIELD_NAMES


def test_i1_check_would_catch_a_hidden_field():
    """The guard itself works: a revealed type with a `findings` field is caught."""
    Bad = dataclasses.make_dataclass("Bad", [("card_id", str), ("findings", dict)], frozen=True)
    names = {f.name for f in dataclasses.fields(Bad)}
    assert names & C.HIDDEN_FIELD_NAMES == {"findings"}


def test_i1_revealed_observation_can_be_built_from_an_attempt_without_hidden_data():
    card = C.card_from_json(_example())
    a = card.attempt("chest_ct", 0)
    obs = C.RevealedObservation(test="chest_ct", attempt=0, state=card.states[0], status=a.status,
                                values=dict(a.values), report=a.report)
    view = C.PublicView(card_id=card.id, state=card.states[0], background=dict(card.background),
                        presenting=card.presenting[card.states[0]], observations=(obs,))
    assert view.observations[0].values["size_mm"] == 17.0


# ---------------------------------------------------------------- library/1, cohort/1

def test_library_manifest_round_trip():
    d = json.loads((FIX / "library_manifest_example.json").read_text())
    m = C.LibraryManifest.from_json(d)
    assert m.to_json() == d
    assert m.n_cards == 600


def test_cohort_spec_round_trip():
    d = json.loads((FIX / "cohort_spec_example.json").read_text())
    s = C.CohortSpec.from_json(d)
    assert s.to_json() == d
    bad = copy.deepcopy(d)
    bad["format"] = "cohort/0"
    with pytest.raises(ValueError):
        C.CohortSpec.from_json(bad)

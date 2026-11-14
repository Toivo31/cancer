"""card_schema(catalogue) and the example card (WP-C1-1, ticket T5)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from patient_engine.card import card_from_json, card_schema, card_schema_problems, card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.schema import schema_problems

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "patient_engine"

try:
    import jsonschema
except ImportError:  # pragma: no cover - optional cross-check
    jsonschema = None


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(ROOT / "catalogue" / "_examples" / "tiny")


@pytest.fixture(scope="module")
def schema(tiny):
    return card_schema(tiny)


def _card() -> dict:
    return json.loads((FIX / "card_example.json").read_text())


def _errors(card, schema) -> list:
    """Our validator's problems; when jsonschema is installed, it must agree on valid/invalid."""
    ours = schema_problems(card, schema)
    if jsonschema is not None:
        theirs = list(jsonschema.Draft202012Validator(schema).iter_errors(card))
        assert bool(ours) == bool(theirs), (ours, [e.message for e in theirs])
    return ours


def test_schema_is_draft_2020_12(schema):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    if jsonschema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_is_json_and_deterministic(tiny, schema):
    assert json.loads(json.dumps(schema)) == schema
    assert card_schema(tiny) == schema


def test_example_card_validates(tiny, schema):
    assert _errors(_card(), schema) == []
    assert card_schema_problems(_card(), tiny) == []


def test_round_trip_of_example_still_valid(schema):
    assert _errors(card_to_json(card_from_json(_card())), schema) == []


@pytest.mark.parametrize("path", [
    ("id",), ("background",), ("background", "region"), ("hidden",), ("hidden", "findings"),
    ("hidden", "error_plan"), ("observations",), ("notes",), ("provenance",), ("provenance", "catalogue_id"),
])
def test_removing_a_required_field_fails(schema, path):
    card = _card()
    target = card
    for k in path[:-1]:
        target = target[k]
    del target[path[-1]]
    probs = _errors(card, schema)
    assert any(p.path == ".".join(path) and "required" in p.message for p in probs), probs


def test_removing_a_finding_fails(schema):
    card = _card()
    del card["hidden"]["findings"]["all_active"]["fever"]
    assert _errors(card, schema)


def test_removing_a_test_from_observations_fails(schema):
    card = _card()
    del card["observations"]["all_active"]["chest_ct"]
    assert any(p.path == "observations.all_active.chest_ct" for p in _errors(card, schema))


def test_unknown_test_id_fails(schema):
    card = _card()
    card["observations"]["all_active"]["pet_ct"] = [{"status": "ok", "values": {}, "report": ""}]
    probs = _errors(card, schema)
    assert [p.path for p in probs] == ["observations.all_active.pet_ct"]
    assert "unknown key" in probs[0].message


def test_unknown_output_and_wrong_types_fail(schema):
    card = _card()
    att = card["observations"]["all_active"]["chest_xray"][0]
    att["values"]["nodule"] = True
    card2 = _card()
    card2["observations"]["all_active"]["blood_count"][0]["values"]["crp"] = "high"
    card3 = _card()
    card3["observations"]["all_active"]["history"][0]["values"]["fever"] = 1      # not a boolean
    card4 = _card()
    card4["observations"]["all_active"]["chest_ct"][0]["values"]["location"] = "left"
    for c in (card, card2, card3, card4):
        assert _errors(c, schema)


def test_too_many_attempts_fail(schema):
    card = _card()
    ct = card["observations"]["all_active"]["chest_ct"]
    ct.extend([copy.deepcopy(ct[0]), copy.deepcopy(ct[0])])      # chest_ct allows 2
    assert any("at most 2" in p.message for p in _errors(card, schema))


def test_non_diagnostic_only_for_tests_with_a_rate(schema):
    card = _card()
    card["observations"]["all_active"]["chest_ct"].append(
        {"status": "non_diagnostic", "values": {}, "report": "Contrast not given."})
    assert _errors(card, schema)                                  # chest_ct has no nondiagnostic rate
    card2 = _card()
    card2["observations"]["all_active"]["chest_xray"][2]["values"] = {"abnormal": True}
    assert _errors(card2, schema)                                 # non-diagnostic carries no values


def test_only_if_outputs_and_variables_may_be_null(schema):
    card = _card()
    card["observations"]["all_active"]["chest_ct"][0]["values"].update(
        {"nodule_seen": False, "size_mm": None, "location": None})
    card["hidden"]["findings"]["all_active"]["lesion_size_mm"]["value"] = None
    assert _errors(card, schema) == []
    card["observations"]["all_active"]["chest_ct"][0]["values"]["nodule_seen"] = None
    assert _errors(card, schema)                                  # nodule_seen has no only_if


def test_values_respect_ranges(schema):
    card = _card()
    card["hidden"]["findings"]["all_active"]["crp_true"]["value"] = -3.0
    card2 = _card()
    card2["background"]["age"] = 140
    assert _errors(card, schema) and _errors(card2, schema)


def test_conditions_and_attributes_come_from_the_catalogue(schema):
    card = _card()
    card["hidden"]["conditions"][0]["attributes"]["stage"] = "V"
    card2 = _card()
    card2["hidden"]["conditions"][1]["id"] = "flu"
    card3 = _card()
    card3["hidden"]["conditions"][0]["role"] = "coexisting"     # a cancer cannot be the co-existing illness
    card4 = _card()
    card4["hidden"]["findings"]["all_active"]["fever"]["caused_by"] = ["influenza"]
    for c in (card, card2, card3, card4):
        assert _errors(c, schema)


def test_states_must_start_with_all_active_and_be_known(schema):
    card = _card()
    card["states"] = ["pneumonia_resolved", "all_active"]
    card2 = _card()
    card2["observations"]["later"] = card2["observations"]["all_active"]
    card3 = _card()
    card3["states"] = ["all_active", "pneumonia_resolved"]
    card3["observations"]["pneumonia_resolved"] = copy.deepcopy(card3["observations"]["all_active"])
    assert _errors(card, schema) and _errors(card2, schema)
    assert _errors(card3, schema) == []                           # a second state is allowed by the schema


def test_note_mentions_must_be_known_keys(schema):
    card = _card()
    card["notes"][0]["mentions"].append("chest_xray.nodule")
    assert _errors(card, schema)


def test_card_from_another_catalogue_fails(schema):
    card = _card()
    card["provenance"]["catalogue_id"] = "lung_primary_care"
    assert _errors(card, schema)


def test_error_plan_may_be_null(schema):
    card = _card()
    card["hidden"]["error_plan"] = None
    card["provenance"]["error_source"] = "free"
    assert _errors(card, schema) == []
    card["hidden"]["error_plan"] = {"all_active": {"chest_xray": [{"status": "ok", "outputs": {"abnormal": "lucky"}}]}}
    assert _errors(card, schema)

"""Contracts care/1 (patient_engine/care.py) and record/1 (patient_engine/record.py)."""
import dataclasses
import typing

import pytest

from patient_engine.card import HIDDEN_FIELD_NAMES
from patient_engine.care import CareError, load_care
from patient_engine.catalogue import load_catalogue
from patient_engine.record import RECORD_TYPES, Entry, Observation, Record

TINY = "catalogue/_examples/tiny"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def test_tiny_care_loads(tiny):
    care = load_care(TINY, tiny)
    assert set(care.roles) == {"nurse", "gp"}
    assert care.roles["nurse"].gathers[0].outputs == ("cough_3wk", "fever")
    assert "weight_loss" in care.roles["gp"].gathers[0].outputs
    assert [a.kind for a in care.role_actions("nurse")] == ["discharge", "book", "book"]
    assert care.treatments["antibiotics"].resolves["pneumonia"][0].resolve() == 0.9
    assert care.behaviour["horizon_days"].resolve() == 365


def test_missing_care_file_is_none(tiny, tmp_path):
    assert load_care(tmp_path, tiny) is None


def test_care_errors(tiny, tmp_path):
    (tmp_path / "care.yaml").write_text(
        "format: care/1\nroles: [{id: gp, gathers: [{test: nope}], actions: [x]}]\n"
        "actions: [{id: o, kind: order, test: nope}, {id: t, kind: treat, treatment: none}]\n"
        "treatments: [{id: a, resolves: {not_a_condition: {p: {p: 2, source: assumption}, days: {value: 1}}}}]\n"
        "behaviour: {}\n")
    with pytest.raises(CareError) as e:
        load_care(tmp_path, tiny)
    codes = {p.code for p in e.value.problems}
    assert "unknown_reference" in codes and "bad_type" in codes


def test_record_types_hold_no_hidden_fields():
    for t in RECORD_TYPES:
        names = {f.name for f in dataclasses.fields(t)}
        assert not names & HIDDEN_FIELD_NAMES, (t.__name__, names & HIDDEN_FIELD_NAMES)
        for hint in typing.get_type_hints(t).values():
            assert "Card" not in str(hint) and "Hidden" not in str(hint)


def test_record_append_and_read():
    r = Record("c_1", {"age": 60})
    r.append(Entry(0.0, 1, "encounter", encounter=1, role="nurse", found={"cough_3wk": True}, action="book_gp_routine"))
    r.append(Entry(2.0, 1, "result", observations=(Observation("chest_xray", 1, "ok", {"abnormal": False}, "Clear."),)))
    r.append(Entry(3.0, 1, "encounter", encounter=2, role="gp", found={"cough_3wk": True, "fever": False}))
    assert r.latest_found() == {"cough_3wk": True, "fever": False}
    assert r.attempts_done("chest_xray") == 1
    assert r.to_json()["entries"][1]["observations"][0]["values"] == {"abnormal": False}
    with pytest.raises(ValueError):
        r.append(Entry(1.0, 1, "encounter"))
    with pytest.raises(ValueError):
        r.append(Entry(9.0, 1, "made_up_kind"))

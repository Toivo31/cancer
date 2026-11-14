"""M6-1 / M6-2: dataset rows, readers, validator, export from a run log."""

import json
from pathlib import Path

import pytest

import jev
from jev import dataset as D
from pathway_sim import generate_patients, simulate
from pathway_sim.documents import documents_to_scenario
from service.templates import load_templates

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def world():
    t = load_templates(ROOT / "scenarios")["finland_lung"]
    sc = documents_to_scenario(t["world"], t["flowcharts"])
    return sc, sc.flowcharts["baseline"]


@pytest.fixture(scope="module")
def run(world):
    sc, fc = world
    fc2, pol = jev.prepare(sc, fc, backend="stub", seed=3)
    return fc2, simulate(sc, fc2, generate_patients(sc, 2800, 3), policy=pol, seed=3)


def good_row(**kw):
    r = {"decision_point": "sample_choice", "patient_id": "p1", "t_days": 31.5,
         "context": {"group": "non_specific", "age": 67, "fast_track": False, "attributes": {"location": "peripheral"},
                     "history": [{"step": "ct", "test": "chest_ct", "result": True, "t_days": 30.9}]},
         "offered": ["bronch", "ttnb"], "chosen": "ttnb", "outcome": {"usable_result": True, "days_to_next_milestone": 9.5}}
    r.update(kw)
    return r


def test_exported_rows_validate_against_their_own_flowchart(world, run):
    sc, _ = world
    fc2, log = run
    ds = D.dataset_from_log(sc, fc2, log, 3)
    assert len(ds) > 2800 and not ds.read_problems
    rep = D.validate(ds, sc, fc2)
    assert rep["trainable"] and rep["n_errors"] == 0 and rep["patients"] <= 2800
    assert set(rep["decision_points"]) == {"first_contact", "sample_choice"} or "first_contact" in rep["decision_points"]
    assert all(r["patient_id"].startswith("s3:") for r in ds.rows)


def test_export_matches_the_service_export(world, run):
    sc, _ = world
    fc2, log = run
    from service.runs_core import decision_rows
    mine = [r for pr in log.patients for r in D.rows_from_patient(sc, fc2, pr, 3, log.warmup_days)]
    theirs = [{k: v for k, v in r.items() if k != "probs"} for pr in log.patients for r in decision_rows(sc, fc2, pr, 3, log.warmup_days)]
    assert mine == theirs


def test_export_never_carries_hidden_truth(world, run):
    sc, _ = world
    fc2, log = run
    text = json.dumps(D.rows_from_log(sc, fc2, log, 3))
    for hidden in ("condition", "cancer"):
        assert hidden not in text
    # an attribute only appears after the step that reveals it
    for r in D.rows_from_log(sc, fc2, log, 3):
        if r["context"]["attributes"]:
            assert any(h["test"] == "chest_ct" for h in r["context"]["history"])


def test_run_export_drops_the_generating_probabilities():
    raw = json.dumps({**good_row(), "probs": {"bronch": 0.1, "ttnb": 0.9}, "measured": True})
    ds = D.rows_from_run_export([raw])
    assert "probs" not in ds.rows[0] and ds.rows[0]["measured"] is True and not ds.read_problems


def test_jsonl_and_csv_agree():
    j = D.Dataset.from_jsonl(json.dumps(good_row()) + "\n\n")
    csv_text = ("decision_point,patient_id,t_days,offered,chosen,ctx.group,ctx.age,ctx.fast_track,ctx.location,step.ct,out.usable_result,out.days_to_next_milestone\n"
                "sample_choice,p1,31.5,bronch|ttnb,ttnb,non_specific,67,false,peripheral,+,true,9.5\n")
    c = D.Dataset.from_csv(csv_text)
    assert not c.read_problems
    a, b = j.rows[0], c.rows[0]
    b["context"]["history"][0].update(test="chest_ct", t_days=30.9)       # CSV has no per-step times or test ids
    assert a == b
    assert D.Dataset.read(csv_text).rows[0]["chosen"] == "ttnb"
    with pytest.raises(D.DatasetError):
        D.Dataset.from_csv("a,b\n1,2\n")


def test_malformed_rows_are_reported_not_fatal():
    text = "\n".join([json.dumps(good_row()), "{not json", json.dumps(good_row(patient_id="has space")),
                      json.dumps(good_row(patient_id="p2", context={"attributes": {"note": "Matti Meikalainen, born in Oulu 1950"}}))])
    ds = D.Dataset.from_jsonl(text)
    assert len(ds) == 1 and ds.n_input == 4
    codes = {g["code"] for g in ds.read_problems}
    assert {"malformed_row", "bad_patient_id", "bad_value"} <= codes


def test_every_problem_class_in_the_spec(world):
    sc, fc = world
    rows = [good_row(patient_id=f"a{i}") for i in range(3)]
    rows += [good_row(patient_id="b1", decision_point="nope"),
             good_row(patient_id="b2", decision_point="ct"),                                   # a step, not a decision
             good_row(patient_id="b3", offered=["bronch", "xyz"], chosen="xyz"),             # option not in flowchart
             good_row(patient_id="b4", chosen="ttnb", offered=["bronch"]),                    # chosen not offered
             good_row(patient_id="b5", context={**good_row()["context"], "history": []}),     # attribute with no revealing step
             good_row(patient_id="b6", t_days=10.0),                                          # history after the decision
             good_row(patient_id="b7", context={**good_row()["context"], "attributes": {"location": "peripheral", "colour": "red"}}),
             good_row(patient_id="a0")]                                                       # duplicate of a0
    ds = D.Dataset.from_rows(rows)
    rep = D.validate(ds, sc, fc)
    codes = {g["code"] for g in rep["problems"]}
    for c in ("unknown_decision_point", "unknown_option", "chosen_not_offered", "unrevealed_attribute", "history_after_decision",
              "unknown_attribute", "no_rows_for_point", "option_never_chosen", "duplicate_rows"):
        assert c in codes, c
    assert not rep["trainable"] and rep["duplicates"] == 1
    assert rep["unknown"]["attributes"] == {"colour": 1}
    pt = rep["decision_points"]["sample_choice"]
    assert "group" in pt["context_shares"] and pt["options"]["ttnb"]["chosen"] >= 3
    with pytest.raises(jev.training.TrainingError):
        jev.train("frequency", ds, sc, fc)


def test_hidden_truth_fields_are_rejected():
    r = good_row()
    r["context"]["condition"] = "lung_cancer"
    ds = D.Dataset.from_rows([r])
    assert not ds.rows and ds.read_problems[0]["code"] == "hidden_truth"


def test_small_cells_warn(world):
    sc, fc = world
    ds = D.Dataset.from_rows([good_row(patient_id=f"p{i}", t_days=40.0) for i in range(5)])
    rep = D.validate(ds, sc, fc, context_fields=["group"])
    assert rep["trainable"] and rep["decision_points"]["sample_choice"]["cells"] == 1
    assert not any(g["code"] == "small_cell" for g in rep["problems"])         # one cell: the field does not vary, no split
    rows = [good_row(patient_id=f"p{i}", context={**good_row()["context"], "group": "site_specific" if i % 2 else "non_specific"}) for i in range(10)]
    rep = D.validate(D.Dataset.from_rows(rows), sc, fc, context_fields=["group"])
    assert any(g["code"] == "small_cell" for g in rep["problems"])


def test_split_is_by_patient():
    rows = [{"patient_id": f"p{i % 50}"} for i in range(500)]
    tr, ho = D.split_by_patient(rows, 0.2, 0)
    assert tr and ho and not ({r["patient_id"] for r in tr} & {r["patient_id"] for r in ho})
    assert 0.1 < len({r["patient_id"] for r in ho}) / 50 < 0.35

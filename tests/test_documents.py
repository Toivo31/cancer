"""Document format v1: converters both ways, YAML import, round trip gives identical metrics (M2-1)."""

import glob
import json
from pathlib import Path

import pytest

import jev

from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate
from pathway_sim.documents import (DocumentError, canonical_json, doc_hash, documents_to_scenario, documents_to_yaml,
                                   flowchart_document_to_raw, load_yaml_as_documents, normalise_flowchart_doc,
                                   scenario_to_documents, yaml_text_to_documents)

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = sorted(glob.glob(str(ROOT / "scenarios/**/*.yaml"), recursive=True))


def metrics_text(sc, fid, n, seed, via_jev=False):
    pts = generate_patients(sc, n, seed)
    if via_jev:                         # documents carry stub tables; jev.prepare builds the engine policy from them
        fc, policy = jev.prepare(sc, sc.flowcharts[fid], seed=seed)
        run = simulate(sc, fc, pts, policy=policy, seed=seed)
    else:
        run = simulate(sc, fid, pts, seed=seed)
    return json.dumps(compute_metrics(run, sc), sort_keys=True, default=str)


def n_for(sc):
    return 300 if sc.id == "finland_lung" else 60


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: Path(p).name)
def test_round_trip_identical_metrics(path):
    sc = load_scenario(path)
    world, fcs = scenario_to_documents(sc)
    # through real JSON text, as the service stores them
    world, fcs = json.loads(json.dumps(world)), json.loads(json.dumps(fcs))
    assert {f["id"] for f in fcs} == set(sc.flowcharts)
    for doc in fcs:
        sc2 = documents_to_scenario(world, [doc])
        for seed in (1, 2):
            assert metrics_text(sc2, doc["id"], n_for(sc), seed, via_jev=True) == metrics_text(sc, doc["id"], n_for(sc), seed), doc["id"]


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: Path(p).name)
def test_document_is_stable_under_second_round_trip(path):
    world, fcs = load_yaml_as_documents(path)
    sc = documents_to_scenario(world, fcs)
    world2, fcs2 = scenario_to_documents(sc)
    assert canonical_json(world2) == canonical_json(world)
    assert [canonical_json(f) for f in fcs2] == [canonical_json(f) for f in fcs]


def test_yaml_export_and_reimport():
    world, fcs = load_yaml_as_documents(ROOT / "scenarios/stokstad.yaml")
    text = documents_to_yaml(world, fcs)
    world2, fcs2 = yaml_text_to_documents(text)
    assert canonical_json(world2) == canonical_json(world)
    assert [f["id"] for f in fcs2] == [f["id"] for f in fcs]


def test_document_shape():
    world, fcs = load_yaml_as_documents(ROOT / "scenarios/finland_lung.yaml")
    assert world["schema_version"] == 1 and world["id"] == "finland_lung" and "flowcharts" not in world
    base = next(f for f in fcs if f["id"] == "baseline")
    kinds = {n["kind"] for n in base["nodes"]}
    assert kinds <= {"step", "decision", "join", "milestone", "exit"} and "decision" in kinds and "join" in kinds
    types = {e["type"] for e in base["edges"]}
    assert types == {"required", "optional", "option"}
    assert base["decision_policy"]["backend"] == "stub" and base["decision_policy"]["mode"] == "sample"
    assert base["decision_policy"]["points"]["first_contact"]["source"] == "KHALIFE2025" and base["world_id"] == "finland_lung"
    opts = [e for e in base["edges"] if e["type"] == "option" and e["from"] == "first_contact"]
    assert [e["to"] for e in sorted(opts, key=lambda e: e["index"])] == ["nurse_visit", "gp_visit"]
    # the unquoted YAML key `on:` must not leave a boolean key in a JSON document
    assert "on" in next(n for n in base["nodes"] if n["id"] == "bronch")["retry"]


def test_choice_alias_and_option_order():
    world, fcs = load_yaml_as_documents(ROOT / "scenarios/finland_lung.yaml")
    doc = next(f for f in fcs if f["id"] == "baseline")
    legacy = json.loads(json.dumps(doc))
    for n in legacy["nodes"]:
        if n["kind"] == "decision":
            n["kind"] = "choice"
    assert flowchart_document_to_raw(legacy) == flowchart_document_to_raw(doc)
    assert all(n["kind"] != "choice" for n in normalise_flowchart_doc(legacy)["nodes"])
    # option order follows `index`, not the position in the edge list
    doc["edges"].reverse()
    raw = flowchart_document_to_raw(doc)
    assert next(n for n in raw["nodes"] if n["id"] == "first_contact")["options"] == ["nurse_visit", "gp_visit"]


def test_structural_problems_have_codes():
    world, fcs = load_yaml_as_documents(ROOT / "scenarios/finland_lung.yaml")
    doc = next(f for f in fcs if f["id"] == "baseline")

    def codes(mutate):
        d = json.loads(json.dumps(doc))
        mutate(d)
        with pytest.raises(DocumentError) as e:
            flowchart_document_to_raw(d)
        return {p["code"] for p in e.value.problems}

    assert codes(lambda d: d["nodes"].append(dict(d["nodes"][0]))) == {"duplicate_id"}
    assert codes(lambda d: d["edges"].append({"from": "ghost", "to": "cxr", "type": "required"})) == {"unknown_reference"}
    assert codes(lambda d: d["edges"].append({"from": "cxr", "to": "ct", "type": "sideways"})) == {"unknown_kind"}
    assert codes(lambda d: d["edges"].append({"from": "cxr", "to": "ct", "type": "option"})) == {"unknown_kind"}
    assert codes(lambda d: d["nodes"][1].update(kind="blob")) == {"unknown_kind"}


def test_hash_ignores_key_order():
    assert doc_hash({"a": 1, "b": [1, 2]}) == doc_hash({"b": [1, 2], "a": 1})


def test_rule_backend_keeps_legacy_policy_exactly():
    from pathway_sim.documents import flowchart_to_document
    sc = load_scenario(ROOT / "scenarios/finland_lung.yaml")
    fc = sc.flowcharts["baseline"]
    doc = json.loads(json.dumps(flowchart_to_document(fc, sc.id, decision_backend="rule")))
    assert doc["decision_policy"]["backend"] == "rule"
    world, _ = scenario_to_documents(sc)
    sc2 = documents_to_scenario(json.loads(json.dumps(world)), [doc])
    assert sc2.flowcharts["baseline"].policy == json.loads(json.dumps(fc.policy))
    assert metrics_text(sc2, "baseline", 300, 1) == metrics_text(sc, "baseline", 300, 1)

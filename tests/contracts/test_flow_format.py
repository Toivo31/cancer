"""flow/1 (docs/platform/flow-format.md): top-level keys, graph and step shapes, on a fresh small run and on the fixtures."""

import json
from pathlib import Path

import pytest

from pathway_sim import generate_patients, load_scenario, simulate
from pathway_sim.flow import build_flow

ROOT = Path(__file__).resolve().parents[2]
TOP = {"format", "scenario", "flowchart", "policy", "seeds", "synthetic", "clock_start", "target_days", "warmup_days",
       "totals", "metrics", "by_group", "graph", "steps", "resources", "queues", "decisions", "exits", "time_lost", "cohort", "meta"}
TOTALS = {"n", "n_cancer", "missed_cancers", "untreated_cancers", "treated_cancers", "stuck", "cohorts"}
NODE_KINDS = {"step", "decision", "milestone", "exit"}
EDGE_KINDS = {"then", "maybe", "option"}


def check_flow(f: dict) -> None:
    assert f["format"] == "flow/1"
    assert TOP <= set(f), TOP - set(f)
    assert TOTALS <= set(f["totals"])
    json.dumps(f)  # plain JSON, no numpy leaking through
    ids = {n["id"] for n in f["graph"]["nodes"]}
    assert ids, "empty graph"
    for n in f["graph"]["nodes"]:
        assert {"id", "label", "kind"} <= set(n) and n["kind"] in NODE_KINDS, n
    for e in f["graph"]["edges"]:
        assert e["source"] in ids and e["target"] in ids, e
        assert e["id"] == f"{e['source']}>{e['target']}" and e["kind"] in EDGE_KINDS and e["n"] >= 0, e
    for nid, s in f["steps"].items():
        assert nid in ids and {"n", "n_cancer"} <= set(s), nid  # nodes nobody reached or that take no time carry only the counts
    timed = [s for s in f["steps"].values() if "wait_median" in s]
    assert timed, "no step carries waiting times"
    for s in timed:
        assert {"wait_mean", "wait_p90", "service_median", "critical_share"} <= set(s)
    for nid, d in f["decisions"].items():
        assert nid in ids and {"n", "options", "chosen", "share"} <= set(d), nid
    for nid, e in f["exits"].items():
        assert nid in ids and {"n", "n_cancer", "outcome"} <= set(e), nid
    for q in f["queues"].values():
        assert len(q["x"]) == len(q["y"])
    assert f["cohort"]["patients"] and {"v", "c", "out", "exit"} <= set(f["cohort"]["patients"][0])


@pytest.mark.parametrize("name", ["flow_norway.json", "flow_finland.json", "flow_norway_optimised.json", "flow_finland_optimised.json"])
def test_documented_fixtures_satisfy_the_contract(name):
    check_flow(json.loads((ROOT / "docs" / "platform" / "fixtures" / name).read_text()))


def test_a_fresh_norway_run_satisfies_the_contract():
    sc = load_scenario(str(ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"))
    run = simulate(sc, "observed", generate_patients(sc, 150, 5), seed=5)
    f = build_flow(run, sc, "observed", sample=20, seed=1)
    check_flow(f)
    # the counts add up: every measured patient is in exactly one exit or stuck
    assert sum(e["n"] for e in f["exits"].values()) + f["totals"]["stuck"] == f["totals"]["n"]

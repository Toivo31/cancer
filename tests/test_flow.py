"""Flow data (pathway_sim/flow.py): totals equal the run's metrics on both shipped templates."""
import json
import math

import pytest

from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate
from pathway_sim.flow import build_flow

CASES = [("scenarios/generated/stokstad_calibrated.yaml", "observed", 400, 201),
         ("scenarios/finland_lung.yaml", "baseline", 5000, 301)]


@pytest.fixture(scope="module", params=CASES, ids=["norway", "finland"])
def case(request):
    path, fid, n, seed = request.param
    sc = load_scenario(path)
    run = simulate(sc, fid, generate_patients(sc, n, seed), seed=seed)
    return sc, run, build_flow(run, sc, fid, sample=60, seed=3), compute_metrics(run, sc)


def test_json_serialisable_and_format(case):
    _, _, f, _ = case
    assert f["format"] == "flow/1"
    json.dumps(f)


def test_totals_equal_metrics(case):
    _, _, f, m = case
    assert f["totals"]["n"] == m["n"] and f["totals"]["n_cancer"] == m["n_cancer"]
    assert f["totals"]["missed_cancers"] == m["missed_cancers"]
    for k in ("share_within_target", "median_days_to_treatment", "median_days_to_diagnosis"):
        assert f["metrics"][k] == (None if m[k] is None else pytest.approx(m[k], abs=1e-4))


def test_exits_sum_to_patients(case):
    _, _, f, m = case
    assert sum(e["n"] for e in f["exits"].values()) + f["totals"]["stuck"] == m["n"]
    treated = sum(e["n_cancer"] for e in f["exits"].values() if e["outcome"] == "treatment")
    assert treated == f["totals"]["treated_cancers"]


def test_critical_path_equals_node_breakdown(case):
    _, _, f, m = case
    for nid, b in m["node_breakdown"].items():
        s = f["steps"][nid]
        assert s["critical_wait"] == pytest.approx(b["wait"], abs=0.011)
        assert s["critical_service"] == pytest.approx(b["service"], abs=0.011)
    assert sum(s.get("critical_share", 0) or 0 for s in f["steps"].values()) == pytest.approx(1.0, abs=0.01)
    assert f["time_lost"][0]["wait"] == max(t["wait"] for t in f["time_lost"])


def test_edges_and_decisions(case):
    _, _, f, _ = case
    ids = {n["id"] for n in f["graph"]["nodes"]}
    for e in f["graph"]["edges"]:
        assert e["source"] in ids and e["target"] in ids and e["n"] >= 0
    for nid, d in f["decisions"].items():
        if d["n"]:
            assert sum(d["chosen"].values()) == d["n"]
            assert sum(d["share"].values()) == pytest.approx(1.0, abs=0.01)
    # a visited non-start step is reached through at least as many edge traversals as patients
    into = {}
    for e in f["graph"]["edges"]:
        into[e["target"]] = into.get(e["target"], 0) + e["n"]
    for n in f["graph"]["nodes"]:
        if n["id"] in into and f["steps"].get(n["id"]):
            assert into[n["id"]] <= f["steps"][n["id"]]["n"] * 4
    for q in f["queues"].values():
        assert len(q["x"]) == len(q["y"]) and min(q["y"]) >= 0


def test_trace_equals_run_log(case):
    _, run, f, _ = case
    by_id = {pr.patient.id: pr for pr in run.patients}
    assert 0 < len(f["cohort"]["patients"]) <= 60
    for t in f["cohort"]["patients"]:
        pr = by_id[t["id"]]
        a = pr.patient.arrival
        assert a >= run.warmup_days
        assert t["out"] == pr.outcome and t["exit"] == pr.exit_node
        assert len(t["v"]) == len(pr.events)
        for row in t["v"]:
            e = next(e for e in pr.events if e.node == row[0] and abs(e.t_ready - a - row[1]) < 0.002)
            assert row[2] == pytest.approx(e.t_start - a, abs=0.002) and row[4] == pytest.approx(e.t_result - a, abs=0.002)
            assert row[6] == int(e.critical)
        assert [c[0] for c in t["c"]] == [c["node"] for c in pr.choices]
        # critical events chain: waiting plus service add up to the time to exit
        crit = [r for r in t["v"] if r[6]]
        if crit and t["t_exit"] is not None and t["out"] == "treatment":
            tot = sum((r[2] - r[1]) + (r[4] - r[2]) for r in crit)
            assert tot == pytest.approx(t["t_exit"], abs=0.05 * max(1, len(crit)))


def test_sample_reproducible(case):
    sc, run, f, _ = case
    g = build_flow(run, sc, run.flowchart, sample=60, seed=3)
    assert [t["id"] for t in g["cohort"]["patients"]] == [t["id"] for t in f["cohort"]["patients"]]
    h = build_flow(run, sc, run.flowchart, sample=20, seed=4)
    assert len(h["cohort"]["patients"]) == 20


def test_two_cohorts_pooled():
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    runs = [simulate(sc, "observed", generate_patients(sc, 200, s), seed=s) for s in (1, 2)]
    f = build_flow(runs, sc, "observed", sample=30)
    assert f["totals"]["n"] == 400 and f["totals"]["cohorts"] == 2
    assert f["metrics"]["share_within_target"] == pytest.approx(
        sum(compute_metrics(r, sc)["share_within_target"] for r in runs) / 2, abs=1e-4)

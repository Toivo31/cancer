"""Core simulator tests: determinism, accounting, guards, parallel steps, queues, missed cancers."""

import math

import pytest

from pathway_sim import compute_metrics, generate_patients, scenario_from_dict, simulate
from pathway_sim.dists import sample, uniform
from pathway_sim.scenario import load_scenario


def tiny(**over):
    raw = {
        "id": "tiny",
        "target_days": 30,
        "arrivals": {"spread_days": 100},
        "conditions": [
            {"id": "cancer", "cancer": True, "prevalence": 0.2},
            {"id": "benign", "cancer": False, "prevalence": 0.8},
        ],
        "groups": [{"id": "specific", "share_by_condition": {"cancer": 0.7, "benign": 0.3}}, {"id": "nonspecific"}],
        "resources": {
            "ct": {"type": "server", "capacity_per_day": 2},
            "pet": {"type": "delay", "wait": {"dist": "fixed", "value": 10}},
            "ex": {"type": "delay", "wait": {"dist": "fixed", "value": 6}},
            "mdt": {"type": "batch", "weekdays": [2]},
        },
        "tests": {
            "ct": {"resource": "ct", "service_days": 0.1, "report_days": 1,
                   "p_positive": {"cancer": 0.9, "default": 0.1}},
            "pet": {"resource": "pet", "report_days": 1},
            "ex": {"resource": "ex", "report_days": 1},
            "mdt": {"resource": "mdt", "kind": "admin", "stage": "treatment_start"},
            "treat": {"resource": "none", "kind": "treatment", "stage": "treatment_start"},
        },
        "flowcharts": {
            "serial": {"nodes": [
                {"id": "ct", "test": "ct"},
                {"id": "home", "kind": "exit", "outcome": "discharged", "after": ["ct"], "when": "not ct"},
                {"id": "pet", "test": "pet", "after": ["ct"], "when": "ct"},
                {"id": "ex", "test": "ex", "after": ["pet"]},
                {"id": "mdt", "test": "mdt", "after": ["ex"]},
                {"id": "treat", "kind": "exit", "outcome": "treatment", "test": "treat", "after": ["mdt"]},
            ]},
            "parallel": {"nodes": [
                {"id": "ct", "test": "ct"},
                {"id": "home", "kind": "exit", "outcome": "discharged", "after": ["ct"], "when": "not ct"},
                {"id": "pet", "test": "pet", "after": ["ct"], "when": "ct"},
                {"id": "ex", "test": "ex", "after": ["ct"], "when": "ct"},
                {"id": "mdt", "test": "mdt", "after": ["pet", "ex"]},
                {"id": "treat", "kind": "exit", "outcome": "treatment", "test": "treat", "after": ["mdt"]},
            ]},
        },
    }
    raw.update(over)
    return scenario_from_dict(raw)


def test_uniform_deterministic_and_in_range():
    a = uniform(1, 2, "x", 3)
    assert a == uniform(1, 2, "x", 3)
    assert a != uniform(1, 2, "x", 4)
    assert 0 < a < 1


def test_lognormal_median_and_p90():
    spec = {"dist": "lognormal", "median": 10, "p90": 20}
    assert sample(spec, 0.5) == pytest.approx(10)
    assert sample(spec, 0.9) == pytest.approx(20, rel=1e-6)


def test_patients_deterministic_and_prevalence():
    sc = tiny()
    a = generate_patients(sc, 2000, 7)
    b = generate_patients(sc, 2000, 7)
    assert [p.to_dict() for p in a] == [p.to_dict() for p in b]
    share = sum(p.cancer for p in a) / len(a)
    assert 0.17 < share < 0.23
    assert generate_patients(sc, 50, 8)[0].to_dict() != a[0].to_dict()


def test_run_deterministic():
    sc = tiny()
    pts = generate_patients(sc, 300, 1)
    m1 = compute_metrics(simulate(sc, "serial", pts, seed=1), sc)
    m2 = compute_metrics(simulate(sc, "serial", pts, seed=1), sc)
    assert m1 == m2


def test_every_patient_exits_and_guards_route():
    sc = tiny()
    pts = generate_patients(sc, 500, 3)
    run = simulate(sc, "serial", pts, seed=3)
    for pr in run.patients:
        assert pr.outcome in ("treatment", "discharged")
        ct = pr.patient.results["ct"][0]
        assert pr.outcome == ("treatment" if ct else "discharged")


def test_missed_cancer_accounting():
    sc = tiny()
    pts = generate_patients(sc, 2000, 4)
    run = simulate(sc, "serial", pts, seed=4)
    m = compute_metrics(run, sc)
    expected = sum(1 for p in pts if p.cancer and p.results["ct"][0] is False)
    assert m["missed_cancers"] == expected
    assert expected > 0
    assert m["false_treatments"] == sum(1 for p in pts if not p.cancer and p.results["ct"][0])


def test_critical_path_adds_up_exactly():
    sc = tiny()
    pts = generate_patients(sc, 400, 5)
    run = simulate(sc, "parallel", pts, seed=5)
    for pr in run.patients:
        if pr.t_exit is None:
            continue
        crit = [e for e in pr.events if e.critical]
        total = sum(e.t_result - e.t_ready for e in crit)
        assert total == pytest.approx(pr.t_exit - pr.patient.arrival, abs=1e-6)


def test_parallel_is_faster_than_serial_with_same_patients():
    sc = tiny()
    pts = generate_patients(sc, 400, 6)
    ms = compute_metrics(simulate(sc, "serial", pts, seed=6), sc)
    mp = compute_metrics(simulate(sc, "parallel", pts, seed=6), sc)
    assert mp["median_days_to_treatment"] < ms["median_days_to_treatment"]
    assert mp["missed_cancers"] == ms["missed_cancers"]


def test_server_queue_grows_when_overloaded():
    # 2 CT slots per weekday = 10/week; arrivals 3/day = 21/week -> queue must grow
    sc = tiny(arrivals={"rate_per_day": 3.0})
    pts = generate_patients(sc, 600, 2)
    run = simulate(sc, "serial", pts, seed=2)
    waits = [e.t_start - e.t_ready for pr in run.patients for e in pr.events if e.node == "ct"]
    first, last = sum(waits[:50]) / 50, sum(waits[-50:]) / 50
    assert last > first + 20
    assert run.resources["ct"]["utilisation"] > 0.9


def test_server_no_queue_when_underloaded():
    sc = tiny(arrivals={"rate_per_day": 0.5})
    pts = generate_patients(sc, 300, 2)
    run = simulate(sc, "serial", pts, seed=2)
    waits = [e.t_start - e.t_ready for pr in run.patients for e in pr.events if e.node == "ct"]
    assert sum(waits) / len(waits) < 3.5   # next working day, plus weekends


def test_batch_meets_on_its_weekday():
    sc = tiny()
    pts = generate_patients(sc, 200, 9)
    run = simulate(sc, "serial", pts, seed=9)
    for pr in run.patients:
        for e in pr.events:
            if e.node == "mdt":
                assert math.floor(e.t_start) % 7 == 2
                assert e.t_start >= e.t_ready


def test_bad_flowchart_rejected():
    with pytest.raises(ValueError):
        tiny(flowcharts={"bad": {"nodes": [{"id": "a", "test": "ct", "after": ["missing"]},
                                           {"id": "x", "kind": "exit", "outcome": "treatment", "after": ["a"]}]}})
    with pytest.raises(ValueError):
        tiny(flowcharts={"cyc": {"nodes": [{"id": "a", "test": "ct", "after": ["b"]},
                                           {"id": "b", "test": "ct", "after": ["a"]},
                                           {"id": "x", "kind": "exit", "outcome": "treatment", "after": ["a"]}]}})


def test_stokstad_scenario_loads_and_runs():
    sc = load_scenario("scenarios/stokstad.yaml")
    pts = generate_patients(sc, 200, 1)
    for fid in sc.flowcharts:
        m = compute_metrics(simulate(sc, fid, pts, seed=1), sc)
        assert m["stuck"] == 0, fid
        assert m["n_cancer"] == 200
        assert m["untreated_cancers"] == 0


def test_flowchart_copy_keeps_guards():
    sc = tiny()
    fc = sc.flowcharts["serial"].copy("copy")
    pts = generate_patients(sc, 300, 11)
    a = compute_metrics(simulate(sc, "serial", pts, seed=11), sc)
    b = compute_metrics(simulate(sc, fc, pts, seed=11), sc)
    assert {k: v for k, v in a.items() if k != "flowchart"} == {k: v for k, v in b.items() if k != "flowchart"}


def test_choice_availability_and_queue_state_in_view():
    from pathway_sim.policy import RulePolicy
    seen = []

    class Spy(RulePolicy):
        def choose(self, view, options):
            seen.append((tuple(options), dict(view.option_leads)))
            return super().choose(view, options)

    sc = tiny(flowcharts={"c": {"nodes": [
        {"id": "pick", "kind": "choice", "options": ["ct", "pet"], "availability": {"ct": {"p_available": 0.5}}},
        {"id": "ct", "test": "ct"}, {"id": "pet", "test": "pet"},
        {"id": "x", "kind": "exit", "outcome": "treatment", "after_any": ["ct", "pet"]}]}})
    pts = generate_patients(sc, 400, 1)
    simulate(sc, "c", pts, policy=Spy(), seed=1)
    only_pet = sum(1 for o, _ in seen if o == ("pet",))
    assert 120 < only_pet < 280                      # ct offered about half the time
    assert all(("ct" in leads) == ("ct" in o) for o, leads in seen)   # server option gets a queue lead
    assert all(v >= 0 for _, leads in seen for v in leads.values())

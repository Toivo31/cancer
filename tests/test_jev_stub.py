"""M1-3: the stub backend, the migration of mix / rules / prefer, exact reproduction of shipped scenarios."""

import glob

import pytest

import jev
from jev import DecisionRequest, StubBackend, StubTableError
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate

SHIPPED = ["scenarios/stokstad.yaml", "scenarios/finland_lung.yaml"]


def req(point="sample_method", ctx=None, options=("bronch", "ttnb")):
    return DecisionRequest("r", point, ctx or {"group": "g", "age": 60, "t_days": 5.0, "attributes": {"location": "central"},
                                               "history": [{"step": "ct", "test": "ct", "result": True, "t_days": 4.0}]},
                           [{"id": o} for o in options])


TABLE = {"sample_method": {"default": {"bronch": 0.5, "ttnb": 0.5},
                           "rules": [{"when": "location == 'central'", "probs": {"bronch": 0.9, "ttnb": 0.1}},
                                     {"when": "location == 'peripheral'", "probs": {"bronch": 0.15, "ttnb": 0.85}}]}}


def test_rules_first_match_then_default_then_uniform():
    s = StubBackend(TABLE)
    assert s.decide([req()])[0].probs == {"bronch": 0.9, "ttnb": 0.1}
    peri = req(ctx={"group": "g", "age": 1, "attributes": {"location": "peripheral"}})
    assert s.decide([peri])[0].probs == {"bronch": 0.15, "ttnb": 0.85}
    other = req(ctx={"group": "g", "age": 1, "attributes": {}})
    assert s.decide([other])[0].probs == {"bronch": 0.5, "ttnb": 0.5}
    r = s.decide([req(point="unknown_point")])[0]
    assert r.probs == {"bronch": 0.5, "ttnb": 0.5} and "missing_probabilities:unknown_point" in s.summary()["warnings"]


def test_conditions_read_step_results_age_and_t():
    s = StubBackend({"d": {"default": {"a": 1, "b": 0},
                           "rules": [{"when": "ct and age >= 60 and t < 10", "probs": {"a": 0, "b": 1}}]}})
    assert s.decide([req("d", options=("a", "b"))])[0].probs == {"a": 0.0, "b": 1.0}


def test_unoffered_options_are_dropped_and_renormalised():
    s = StubBackend({"d": {"default": {"a": 0.2, "b": 0.3, "c": 0.5}}})
    p = s.decide([req("d", options=("a", "c"))])[0].probs
    assert abs(p["a"] - 0.2 / 0.7) < 1e-12 and abs(p["c"] - 0.5 / 0.7) < 1e-12
    # a rule that puts all its mass on an option that is not offered is skipped
    s = StubBackend({"d": {"default": {"a": 0.5, "b": 0.5}, "rules": [{"when": "True", "probs": {"a": 1, "b": 0}}]}})
    assert s.decide([req("d", options=("b",))])[0].probs == {"b": 1.0}


def test_info_declares_context_fields_and_is_deterministic():
    inf = StubBackend(TABLE).info()
    assert inf.deterministic and "attributes.location" in inf.context_fields


@pytest.mark.parametrize("bad", [
    {"d": {"default": {"a": -1, "b": 2}}}, {"d": {"default": {"a": 0, "b": 0}}}, {"d": {"rules": [{"when": "x"}]}},
    {"d": {"default": {"a": 1}, "rules": [{"when": "__import__('os')", "probs": {"a": 1}}]}},
    {"d": {"default": {"a": 1}, "rules": [{"when": "a ==", "probs": {"a": 1}}]}}, {"d": "nope"},
])
def test_bad_tables_rejected(bad):
    with pytest.raises(StubTableError):
        StubBackend(bad)


def test_validate_against_flowchart():
    sc = load_scenario("scenarios/finland_lung.yaml")
    fc = sc.flowcharts["baseline"]
    assert StubBackend({"sample_choice": {"default": {"bronch": 1, "nope": 1}}}).validate_against(fc, sc)
    assert StubBackend({"ct": {"default": {"a": 1}}}).validate_against(fc, sc)
    assert StubBackend({"sample_choice": {"default": {"bronch": 1, "ttnb": 1},
                                          "rules": [{"when": "cxrr", "probs": {"bronch": 1}}]}}).validate_against(fc, sc)
    assert not StubBackend(jev.table_from_policy(fc)).validate_against(fc, sc)


def _scenarios():
    out = list(SHIPPED)
    out += sorted(glob.glob("scenarios/experiments/*.yaml"))
    return out


@pytest.mark.parametrize("path", SHIPPED)
def test_shipped_scenarios_reproduce_exactly(path):
    sc = load_scenario(path)
    n = 700 if "finland" in path else 500
    for fid, fc0 in sc.flowcharts.items():
        pts = generate_patients(sc, n, 3)
        old = simulate(sc, fid, pts, seed=3)
        fc, pol = jev.prepare(sc, fc0, backend="stub", mode="sample", seed=3)
        new = simulate(sc, fc, pts, policy=pol, seed=3)
        assert compute_metrics(new, sc) == compute_metrics(old, sc), (path, fid)
        key = lambda r: [[(c["node"], c["chosen"]) for c in p.choices] for p in r.patients]
        assert key(new) == key(old), (path, fid)
        assert new.patients[0].choices == [] or new.patients[0].choices[0]["backend"] == "stub"


def test_experiment_scenarios_reproduce_exactly():
    # the experiment scenarios use rules / prefer / mix with availability on some nodes
    for path in _scenarios()[2:]:
        sc = load_scenario(path)
        for fid, fc0 in sc.flowcharts.items():
            pts = generate_patients(sc, 200, 5)
            old = simulate(sc, fid, pts, seed=5)
            fc, pol = jev.prepare(sc, fc0, backend="stub", mode="sample", seed=5)
            new = simulate(sc, fc, pts, policy=pol, seed=5)
            assert compute_metrics(new, sc) == compute_metrics(old, sc), (path, fid)


def test_changing_one_probability_changes_the_run():
    sc = load_scenario("scenarios/finland_lung.yaml")
    fc0 = sc.flowcharts["baseline"]
    pts = generate_patients(sc, 600, 2)
    exits = lambda r: [p.t_exit for p in r.patients]
    fc, pol = jev.prepare(sc, fc0, mode="sample", seed=2)
    a = simulate(sc, fc, pts, policy=pol, seed=2)
    fc, pol = jev.prepare(sc, fc0, mode="sample", seed=2, sets={("first_contact", "nurse_visit"): 0.9})
    b = simulate(sc, fc, pts, policy=pol, seed=2)
    nurse = lambda r: sum(1 for p in r.patients for c in p.choices if c["node"] == "first_contact" and c["chosen"] == "nurse_visit")
    assert nurse(b) > nurse(a) + 100
    assert exits(a) != exits(b)                      # patients' times moved


def test_set_probability_rescales_the_rest():
    pts = {"d": {"default": {"a": 0.2, "b": 0.3, "c": 0.5}}}
    jev.set_probability(pts, "d", "a", 0.6)
    assert abs(sum(pts["d"]["default"].values()) - 1) < 1e-12
    assert abs(pts["d"]["default"]["b"] / pts["d"]["default"]["c"] - 0.6) < 1e-12
    with pytest.raises(ValueError):
        jev.set_probability(pts, "d", "zzz", 0.5)
    with pytest.raises(ValueError):
        jev.set_probability(pts, "nope", "a", 0.5)
    with pytest.raises(ValueError):
        jev.set_probability(pts, "d", "a", 1.5)


def test_migration_covers_mix_rules_prefer_default_and_missing_policy():
    from pathway_sim import scenario_from_dict
    from test_pathway_sim import tiny
    sc = tiny(flowcharts={"c": {"nodes": [
        {"id": "p1", "kind": "choice", "options": ["a", "b"]}, {"id": "p2", "kind": "decision", "options": ["c", "d"]},
        {"id": "p3", "kind": "choice", "options": ["e", "f"]},
        {"id": "a", "test": "ct"}, {"id": "b", "test": "ct"}, {"id": "c", "test": "ct"}, {"id": "d", "test": "ct"},
        {"id": "e", "test": "ct"}, {"id": "f", "test": "ct"},
        {"id": "x", "kind": "exit", "outcome": "treatment", "after_any": ["a", "b", "c", "d", "e", "f"]}],
        "policy": {"p1": {"mix": {"b": 0.25, "a": 0.75}, "rules": [{"when": "age > 70", "choose": "a"}]},
                   "p2": {"prefer": ["d", "c"]}}}})
    fc = sc.flowcharts["c"]
    mig = jev.migrate_flowchart(fc)
    assert mig.nodes["p1"].options == ["b", "a"]           # follows the mix order
    pts = mig.decision_policy["points"]
    assert pts["p1"]["default"] == {"b": 0.25, "a": 0.75}
    assert pts["p1"]["rules"] == [{"when": "age > 70", "probs": {"b": 0.0, "a": 1.0}}]
    assert pts["p2"]["default"] == {"c": 0.0, "d": 1.0}
    assert pts["p3"]["default"] == {"e": 1.0, "f": 0.0}      # no policy entry: first option wins, as today
    # and the engine run is identical to the rule policy
    pt = generate_patients(sc, 400, 9)
    old = simulate(sc, fc, pt, seed=9)
    f2, pol = jev.prepare(sc, fc, mode="sample", seed=9)
    new = simulate(sc, f2, pt, policy=pol, seed=9)
    assert compute_metrics(new, sc) == compute_metrics(old, sc)

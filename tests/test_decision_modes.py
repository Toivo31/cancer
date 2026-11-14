"""M1-2: engine decision modes (sample / argmax) and the 'decision' node kind."""

import pytest

from jev import BackendInfo, BackendPolicy, DecisionResponse
from pathway_sim import compute_metrics, generate_patients, simulate
from test_pathway_sim import tiny


class Table:
    def __init__(self, table):
        self.table = table

    def decide(self, requests):
        return [DecisionResponse(q.request_id, dict(self.table[q.decision_point])) for q in requests]

    def info(self):
        return BackendInfo("table", "table@1")


def _fc(kind="choice", extra=None):
    nodes = [{"id": "pick", "kind": kind, "options": ["ct", "pet"]},
             {"id": "ct", "test": "ct"}, {"id": "pet", "test": "pet"}]
    nodes += extra or []
    nodes.append({"id": "x", "kind": "exit", "outcome": "treatment", "after_any": ["ct", "pet"]})
    return {"nodes": nodes}


def _chosen(run):
    return {pr.patient.id: pr.choices[0]["chosen"] for pr in run.patients}


def test_decision_kind_is_accepted_and_equals_choice():
    sc = tiny(flowcharts={"a": _fc("choice"), "b": _fc("decision")})
    assert sc.flowcharts["b"].nodes["pick"].kind == "choice"
    pts = generate_patients(sc, 200, 4)
    pol = lambda: BackendPolicy(Table({"pick": {"ct": 0.3, "pet": 0.7}}))
    a = simulate(sc, "a", pts, policy=pol(), seed=4)
    b = simulate(sc, "b", pts, policy=pol(), seed=4)
    assert _chosen(a) == _chosen(b)


def test_sample_shares_follow_probabilities_and_argmax_is_deterministic():
    sc = tiny(flowcharts={"a": _fc()})
    pts = generate_patients(sc, 2000, 5)
    s = simulate(sc, "a", pts, policy=BackendPolicy(Table({"pick": {"ct": 0.3, "pet": 0.7}}), mode="sample"), seed=5)
    share = sum(1 for v in _chosen(s).values() if v == "ct") / len(pts)
    assert 0.26 < share < 0.34
    m = simulate(sc, "a", pts, policy=BackendPolicy(Table({"pick": {"ct": 0.3, "pet": 0.7}}), mode="argmax"), seed=5)
    assert set(_chosen(m).values()) == {"pet"}
    c = s.patients[0].choices[0]
    assert (c["mode"], c["backend"], c["model"]) == ("sample", "table", "table@1")
    assert m.patients[0].choices[0]["mode"] == "argmax"


def test_same_patient_same_probabilities_same_choice_across_flowcharts():
    # variant adds an unrelated step and reorders nodes; the decision point keeps its id
    extra = [{"id": "ex", "test": "ex", "after": ["pick"]}]
    sc = tiny(flowcharts={"a": _fc(), "b": _fc(extra=extra)})
    pts = generate_patients(sc, 500, 6)
    mk = lambda: BackendPolicy(Table({"pick": {"ct": 0.4, "pet": 0.6}}), mode="sample")
    a, b = simulate(sc, "a", pts, policy=mk(), seed=6), simulate(sc, "b", pts, policy=mk(), seed=6)
    assert _chosen(a) == _chosen(b)
    # another seed gives other draws
    c = simulate(sc, "a", pts, policy=mk(), seed=7)
    assert _chosen(c) != _chosen(a)


def test_legacy_policies_unchanged_and_probabilities_zero_never_chosen():
    sc = tiny(flowcharts={"a": _fc()})
    pts = generate_patients(sc, 300, 8)
    r = simulate(sc, "a", pts, policy=BackendPolicy(Table({"pick": {"ct": 0.0, "pet": 1.0}}), mode="sample"), seed=8)
    assert set(_chosen(r).values()) == {"pet"}
    legacy = simulate(sc, "a", pts, seed=8)
    assert legacy.patients[0].choices[0]["mode"] == "argmax"


def test_bad_mode_rejected():
    sc = tiny(flowcharts={"a": _fc()})
    pol = BackendPolicy(Table({"pick": {"ct": 0.5, "pet": 0.5}}))
    pol.decision_mode = "bogus"
    with pytest.raises(ValueError):
        simulate(sc, "a", generate_patients(sc, 3, 1), policy=pol, seed=1)

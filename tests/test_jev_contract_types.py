"""M1-1: the JEV contract types, JSON examples and the BackendPolicy adapter."""

import json
from pathlib import Path

import pytest

from jev import (BackendInfo, BackendPolicy, ContractError, DecisionRequest, DecisionResponse, build_context,
                 check_probs, check_responses, decode_request, decode_response, encode_request, encode_response)
from pathway_sim import PatientView, generate_patients, simulate
from test_pathway_sim import tiny

EX = Path(__file__).resolve().parent.parent / "jev" / "examples"


def load(name):
    return json.loads((EX / name).read_text())


class Fixed:
    """Test backend: fixed probabilities per decision point, records what it was asked."""

    def __init__(self, table, model="fixed@1"):
        self.table, self.model, self.seen = table, model, []

    def decide(self, requests):
        self.seen += requests
        return [DecisionResponse(q.request_id, dict(self.table[q.decision_point])) for q in requests]

    def info(self):
        return BackendInfo("fixed", self.model)


def test_examples_round_trip():
    model, reqs = decode_request(load("decide_request.json"))
    assert model == "stub@1" and reqs[0].decision_point == "sample_method"
    assert reqs[0].option_ids == ["bronch", "ttnb"]
    assert encode_request(model, reqs) == load("decide_request.json")
    model, resps = decode_response(load("decide_response.json"))
    assert encode_response(model, resps) == load("decide_response.json")
    check_responses(reqs, resps)


@pytest.mark.parametrize("probs,ok", [
    ({"a": 0.5, "b": 0.5}, True),
    ({"a": 0.5, "b": 0.5000004}, True),           # within 1e-6: renormalised
    ({"a": 0.5, "b": 0.51}, False),
    ({"a": 1.0}, False),                          # missing b
    ({"a": 0.5, "b": 0.5, "c": 0.0}, False),      # not offered
    ({"a": -0.1, "b": 1.1}, False),
    ({"a": "x", "b": 1.0}, False),
    ({"a": float("nan"), "b": 0.5}, False),
])
def test_check_probs(probs, ok):
    if ok:
        out = check_probs(probs, ["a", "b"])
        assert abs(sum(out.values()) - 1) < 1e-12 and list(out) == ["a", "b"]
    else:
        with pytest.raises(ContractError):
            check_probs(probs, ["a", "b"])


def test_check_responses_order_and_count():
    q = [DecisionRequest("r1", "d", {}, [{"id": "a"}, {"id": "b"}]), DecisionRequest("r2", "d", {}, [{"id": "a"}, {"id": "b"}])]
    r = [DecisionResponse("r2", {"a": 1, "b": 0}), DecisionResponse("r1", {"a": 1, "b": 0})]
    with pytest.raises(ContractError):
        check_responses(q, r)
    with pytest.raises(ContractError):
        check_responses(q, r[:1])


def test_request_validation():
    with pytest.raises(ContractError):
        DecisionRequest.from_dict({"request_id": "x", "decision_point": "d", "options": []})
    with pytest.raises(ContractError):
        DecisionRequest.from_dict({"request_id": "x", "decision_point": "d", "options": [{"id": "a"}, {"id": "a"}]})
    with pytest.raises(ContractError):
        decode_request({"nope": 1})


def test_context_from_view():
    v = PatientView(7, "non_specific", 67, 31.5, "sample_method",
                    history=[("gp_visit", "gp_assessment", True, 13.2), ("ct", "ct_chest", None, 30.9)],
                    attributes={"location": "peripheral"}, priority=False, offered=["bronch", "ttnb"],
                    option_leads={"ttnb": 2.0})
    c = build_context(v)
    assert c == {"group": "non_specific", "age": 67, "t_days": 31.5, "fast_track": False,
                 "attributes": {"location": "peripheral"},
                 "history": [{"step": "gp_visit", "test": "gp_assessment", "result": True, "t_days": 13.2},
                             {"step": "ct", "test": "ct_chest", "result": None, "t_days": 30.9}]}
    json.dumps(c)                                  # plain JSON types only


def test_backend_policy_builds_request_and_validates():
    sc = tiny(flowcharts={"c": {"nodes": [
        {"id": "pick", "kind": "choice", "label": "Pick one", "options": ["ct", "pet"]},
        {"id": "ct", "test": "ct"}, {"id": "pet", "test": "pet"},
        {"id": "x", "kind": "exit", "outcome": "treatment", "after_any": ["ct", "pet"]}]}})
    fc = sc.flowcharts["c"]
    be = Fixed({"pick": {"ct": 0.25, "pet": 0.75}})
    pol = BackendPolicy(be, mode="sample", scenario=sc, flowchart=fc)
    assert (pol.decision_mode, pol.backend_name, pol.model_id) == ("sample", "fixed", "fixed@1")
    run = simulate(sc, fc, generate_patients(sc, 40, 1), policy=pol, seed=1)
    q = be.seen[0]
    assert q.decision_point == "pick" and q.request_id.startswith("p") and q.request_id.endswith(":pick")
    assert [o["id"] for o in q.options] == ["ct", "pet"]
    assert q.options[0]["test"] == "ct" and "lead_days" in q.options[0]["features"]   # ct is a server
    assert "lead_days" not in q.options[1].get("features", {})                        # pet is a delay
    assert len(be.seen) == len(run.patients)
    with pytest.raises(ValueError):
        BackendPolicy(be, mode="nope")
    bad = BackendPolicy(Fixed({"pick": {"ct": 0.9, "pet": 0.9}}), scenario=sc, flowchart=fc)
    with pytest.raises(ContractError):
        simulate(sc, fc, generate_patients(sc, 5, 1), policy=bad, seed=1)

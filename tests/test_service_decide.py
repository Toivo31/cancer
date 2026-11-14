"""Try a decision (M2-8) and the policy checks in validate."""

import copy

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "w"))) as c:
        yield c


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "t", "template": "finland_lung"}).json()["id"]


def decide(client, p, **body):
    body.setdefault("flowchart", {"id": "baseline"})
    return client.post(f"/api/projects/{p}/decide", json=body)


def test_decide_default_row_and_rule(client, project):
    r = decide(client, project, decision_point="sample_choice", context={"attributes": {"location": "peripheral"}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["backend"] == "stub" and out["mode"] == "sample"
    probs = {o["id"]: o["probability"] for o in out["options"]}
    assert probs == pytest.approx({"bronch": 0.35, "ttnb": 0.65}) and out["explanation"] == "default"
    out = decide(client, project, decision_point="sample_choice", context={"attributes": {"location": "central"}}).json()
    assert {o["id"]: o["probability"] for o in out["options"]} == pytest.approx({"bronch": 1.0, "ttnb": 0.0})
    assert "location" in out["explanation"] and out["context_used"]["age"] == 65 and out["context_used"]["group"]


def test_decide_with_offered_subset_and_labels(client, project):
    out = decide(client, project, decision_point="first_contact", offered=["gp_visit"]).json()
    by = {o["id"]: o for o in out["options"]}
    assert by["gp_visit"]["probability"] == pytest.approx(1.0) and by["nurse_visit"]["probability"] == 0 and not by["nurse_visit"]["offered"]
    assert by["gp_visit"]["label"] == "GP appointment"


def test_decide_changes_with_the_table(client, project):
    doc = client.get(f"/api/projects/{project}/flowcharts/baseline").json()["latest"]
    doc["decision_policy"]["points"]["first_contact"]["default"] = {"nurse_visit": 0.9, "gp_visit": 0.1}
    out = decide(client, project, flowchart=doc, decision_point="first_contact").json()    # unsaved edit, sent whole
    assert {o["id"]: o["probability"] for o in out["options"]} == pytest.approx({"nurse_visit": 0.9, "gp_visit": 0.1})
    # a policy override for this call only
    over = {"backend": "stub", "mode": "sample", "points": {"first_contact": {"default": {"nurse_visit": 0.2, "gp_visit": 0.8}}}}
    out = decide(client, project, decision_point="first_contact", decision_policy=over).json()
    assert out["options"][0]["probability"] == pytest.approx(0.2)


def test_decide_errors(client, project):
    assert decide(client, project, decision_point="ct").status_code == 422
    assert decide(client, project, decision_point="nope").json()["error"]["code"] == "unknown_decision_point"
    assert decide(client, project, decision_point="first_contact", offered=["ct"]).json()["error"]["code"] == "invalid_offered"
    assert decide(client, project, flowchart={"id": "ghost"}, decision_point="first_contact").status_code == 404
    assert decide(client, "p_nope", decision_point="x").status_code == 404
    assert decide(client, project, flowchart={"id": "baseline", "version": 9}, decision_point="first_contact").status_code == 404


def test_validate_checks_probability_tables(client, project):
    doc = client.get(f"/api/projects/{project}/flowcharts/baseline").json()["latest"]

    def check(mutate):
        d = copy.deepcopy(doc)
        mutate(d)
        return client.post(f"/api/projects/{project}/validate", json={"flowchart": d}).json()

    r = check(lambda d: d["decision_policy"]["points"]["first_contact"]["default"].update(ghost=0.1))
    assert any(p["code"] == "policy_unknown_option" and p["node"] == "first_contact" for p in r["problems"])
    r = check(lambda d: d["decision_policy"]["points"].update(ct={"default": {"a": 1.0}}))
    assert any(p["code"] == "policy_not_decision" for p in r["problems"])
    r = check(lambda d: d["decision_policy"]["points"].pop("first_contact"))
    assert r["ok"] is True and any(p["code"] == "missing_probabilities" and p["severity"] == "warning" for p in r["problems"])
    r = check(lambda d: d["decision_policy"]["points"]["first_contact"]["default"].update(nurse_visit=-1))
    assert r["ok"] is False and any(p["code"] == "policy_probabilities" for p in r["problems"])
    r = check(lambda d: d["decision_policy"]["points"]["sample_choice"]["rules"][0].update(when="nonsense_name == 1"))
    assert any(p["code"] == "guard_unknown_name" for p in r["problems"])
    assert check(lambda d: None)["problems"] == []


def test_unsafe_condition_is_rejected_not_run(client, project):
    doc = client.get(f"/api/projects/{project}/flowcharts/baseline").json()["latest"]
    for evil in ("__import__('os').system('echo hi')", "().__class__.__bases__", "[x for x in range(3)]"):
        d = copy.deepcopy(doc)
        d["decision_policy"]["points"]["sample_choice"]["rules"][0]["when"] = evil
        r = client.post(f"/api/projects/{project}/validate", json={"flowchart": d}).json()
        assert r["ok"] is False and any(p["code"] == "guard_syntax" for p in r["problems"]), evil
        assert client.post(f"/api/projects/{project}/flowcharts/baseline/versions", json=d).status_code == 422
        assert decide(client, project, flowchart=d, decision_point="sample_choice").status_code == 422
    d = copy.deepcopy(doc)
    next(n for n in d["nodes"] if n.get("when"))["when"] = "__import__('os').getcwd()"
    assert client.post(f"/api/projects/{project}/validate", json={"flowchart": d}).json()["ok"] is False

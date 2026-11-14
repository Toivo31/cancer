"""M6-4: datasets, training jobs, model registry and attach-model through the API."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings

N = 2800        # the Finnish world measures nobody below 2690 patients (44 a day x 60 days of warm-up)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    app = create_app(Settings(data_dir=d / "data", web_dir=d / "noweb", max_jobs=2, max_patients=5000, max_seeds=3))
    with TestClient(app) as c:
        yield c


def wait_job(client, job_id, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


@pytest.fixture(scope="module")
def project(client):
    r = client.post("/api/projects", json={"name": "t", "template": "finland_lung"})
    assert r.status_code == 201, r.text
    p = r.json()["id"]
    run = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "baseline"}, "n": N, "seeds": [1]}).json()
    assert wait_job(client, run["job_id"])["status"] == "succeeded"
    return p, run["id"]


def good_row(i, **kw):
    r = {"decision_point": "first_contact", "patient_id": f"u{i}", "t_days": 0.0,
         "context": {"group": "site_specific" if i % 2 else "non_specific", "age": 60, "fast_track": False, "attributes": {}, "history": []},
         "offered": ["nurse_visit", "gp_visit"], "chosen": "nurse_visit" if i % 5 else "gp_visit"}
    r.update(kw)
    return r


def test_upload_report_and_errors_do_not_stop_storing(client, project):
    p, _ = project
    body = "\n".join(json.dumps(good_row(i)) for i in range(40)) + "\n" + json.dumps(good_row(99, decision_point="nope")) + "\n{bad"
    r = client.post(f"/api/projects/{p}/datasets?name=mine&flowchart=baseline", content=body)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "stored" and d["rows"] == 41 and d["trainable"] is False and "Synthetic data only" in d["synthetic_notice"]
    codes = {g["code"] for g in d["report"]["problems"]}
    assert {"unknown_decision_point", "malformed_row"} <= codes
    got = client.get(f"/api/projects/{p}/datasets/{d['id']}").json()
    assert got["report"]["decision_points"]["first_contact"]["rows"] == 40 and got["flowchart"] == {"id": "baseline", "version": 1}
    # training on a dataset with errors is refused with the errors listed
    r = client.post(f"/api/projects/{p}/models", json={"dataset": d["id"], "trainer": "frequency"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "dataset_has_errors" and r.json()["error"]["problems"]
    rows = client.get(f"/api/projects/{p}/datasets/{d['id']}/rows?limit=5").json()
    assert rows["total"] == 41 and len(rows["rows"]) == 5
    assert client.get(f"/api/projects/{p}/datasets/{d['id']}/download").text.count("\n") == 41
    # the same rows against another flowchart version are re-checked on request
    v = client.post(f"/api/projects/{p}/datasets/{d['id']}/validate", json={"flowchart": {"id": "direct_ct"}}).json()
    assert v["flowchart"]["id"] == "direct_ct" and v["report"]["rows"] == 41


def test_csv_upload(client, project):
    p, _ = project
    csv_text = "decision_point,patient_id,t_days,offered,chosen,ctx.group\n" + "\n".join(
        f"first_contact,c{i},0,nurse_visit|gp_visit,{'nurse_visit' if i % 3 else 'gp_visit'},{'site_specific' if i % 2 else 'non_specific'}" for i in range(60))
    r = client.post(f"/api/projects/{p}/datasets?name=csv&flowchart=baseline&format=csv", content=csv_text)
    assert r.status_code == 201 and r.json()["trainable"] is True and r.json()["rows"] == 60
    bad = client.post(f"/api/projects/{p}/datasets?format=csv", content="a,b\n1,2\n")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_dataset"


def test_run_to_dataset_to_model_to_attach(client, project):
    p, run_id = project
    r = client.post(f"/api/projects/{p}/datasets/from-run", json={"run": run_id, "name": "practice"})
    assert r.status_code == 202, r.text
    assert wait_job(client, r.json()["job_id"])["status"] == "succeeded"
    ds = client.get(f"/api/projects/{p}/datasets/{r.json()['id']}").json()
    assert ds["status"] == "stored" and ds["trainable"] is True and ds["rows"] > N and ds["source"]["kind"] == "run"
    assert "first_contact" in ds["report"]["decision_points"]
    # train: counting
    t = client.post(f"/api/projects/{p}/models", json={"dataset": ds["id"], "trainer": "frequency", "context_fields": ["group"]})
    assert t.status_code == 202, t.text
    assert wait_job(client, t.json()["job_id"])["status"] == "succeeded"
    m = client.get(f"/api/projects/{p}/models/{t.json()['id']}").json()
    assert m["status"] == "ready" and m["trainer"] == "frequency" and m["dataset_hash"] == ds["content_hash"]
    assert "reproduces practice" in m["notice"] and m["evaluation"]["label"].startswith("Agreement")
    assert m["evaluation"]["split"] == "by patient" and set(m["table"]) >= {"first_contact"}
    assert [x["id"] for x in client.get(f"/api/projects/{p}/models").json()] == [m["id"]]
    # attach: a new version carries the learned table
    a = client.post(f"/api/projects/{p}/flowcharts/baseline/attach-model", json={"model": m["id"], "decision_points": ["first_contact"]})
    assert a.status_code == 201, a.text
    out = a.json()
    assert out["attached"] == ["first_contact"] and out["flowchart"]["version"] == 2 and out["parent_version"] == 1
    doc = client.get(f"/api/projects/{p}/flowcharts/baseline/versions/2").json()
    pt = doc["decision_policy"]["points"]["first_contact"]
    assert pt["source"].startswith("trained: model " + m["id"]) and pt["default"] == m["table"]["first_contact"]["default"]
    assert doc["decision_policy"]["points"]["sample_choice"] == client.get(f"/api/projects/{p}/flowcharts/baseline/versions/1").json()["decision_policy"]["points"]["sample_choice"]
    # a run with the attached version works and uses the table
    rr = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "baseline", "version": 2}, "n": N, "seeds": [1]}).json()
    assert wait_job(client, rr["job_id"])["status"] == "succeeded"
    # points the model was not trained on, and stale bases, are refused clearly
    bad = client.post(f"/api/projects/{p}/flowcharts/baseline/attach-model", json={"model": m["id"], "decision_points": ["ct"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "model_mismatch"
    stale = client.post(f"/api/projects/{p}/flowcharts/baseline/attach-model", json={"model": m["id"], "base_version": 1})
    assert stale.status_code == 409
    # a dataset in use cannot be deleted before its model
    assert client.delete(f"/api/projects/{p}/datasets/{ds['id']}").status_code == 409
    assert client.delete(f"/api/projects/{p}/models/{m['id']}").status_code == 204
    assert client.delete(f"/api/projects/{p}/datasets/{ds['id']}").status_code == 204


def test_local_trainer_attach_and_run(client, project):
    p, run_id = project
    d = client.post(f"/api/projects/{p}/datasets/from-run", json={"run": run_id, "point": "first_contact"}).json()
    assert wait_job(client, d["job_id"])["status"] == "succeeded"
    t = client.post(f"/api/projects/{p}/models", json={"dataset": d["id"], "trainer": "local", "settings": {"epochs": 4}}).json()
    assert wait_job(client, t["job_id"])["status"] == "succeeded"
    m = client.get(f"/api/projects/{p}/models/{t['id']}").json()
    assert m["status"] == "ready" and m["decision_points"] == ["first_contact"] and "table" not in m and m["artifact_summary"]["kind"] == "local_numpy"
    a = client.post(f"/api/projects/{p}/flowcharts/direct_ct/attach-model", json={"model": m["id"]})
    assert a.status_code == 201, a.text
    assert a.json()["trained_on_other_version"] is True
    v = a.json()["flowchart"]["version"]
    rr = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "direct_ct", "version": v}, "n": N, "seeds": [1]})
    assert rr.status_code == 202, rr.text
    assert wait_job(client, rr.json()["job_id"])["status"] == "succeeded"
    lines = client.get(f"/api/projects/{p}/runs/{rr.json()['id']}/decisions?point=first_contact").text.splitlines()
    assert lines and all(json.loads(x) for x in lines[:5])
    pat = client.get(f"/api/projects/{p}/runs/{rr.json()['id']}/patients?limit=50").json()["patients"]
    assert {c["backend"] for pt in pat for c in pt["choices"] if c["node"] == "first_contact"} == {"local"}


def test_exploration_dataset_has_outcomes(client, project):
    p, _ = project
    r = client.post(f"/api/projects/{p}/datasets/explore", json={"flowchart": {"id": "baseline"}, "points": ["sample_choice"], "n": N, "seeds": [2]})
    assert r.status_code == 202, r.text
    assert wait_job(client, r.json()["job_id"])["status"] == "succeeded"
    ds = client.get(f"/api/projects/{p}/datasets/{r.json()['id']}").json()
    assert ds["source"]["kind"] == "exploration" and set(ds["source"]["outcomes"]["sample_choice"]) == {"bronch", "ttnb"}
    row = client.get(f"/api/projects/{p}/datasets/{ds['id']}/rows?limit=1").json()["rows"][0]
    assert "usable_result" in row["outcome"]
    bad = client.post(f"/api/projects/{p}/datasets/explore", json={"flowchart": {"id": "baseline"}, "points": ["ct"], "n": N})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_decision_point"


def test_trainers_listing_and_unavailable_jev(client, project):
    p, _ = project
    t = client.get("/api/trainers").json()
    assert {x["id"]: x["available"] for x in t["trainers"]} == {"frequency": True, "local": True, "jev": False} and "reproduces practice" in t["notice"]
    r = client.post(f"/api/projects/{p}/models", json={"dataset": "d_x", "trainer": "jev"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "trainer_unavailable"
    assert client.post(f"/api/projects/{p}/models", json={"dataset": "d_x"}).status_code == 404


def test_attach_lists_mismatches_when_the_flowchart_has_moved_on():
    import copy
    from service.datasets_core import attach
    doc = {"nodes": [{"id": "d", "kind": "decision"}, {"id": "a"}, {"id": "b"}, {"id": "c"}],
           "edges": [{"from": "d", "to": "a", "type": "option", "index": 0}, {"from": "d", "to": "b", "type": "option", "index": 1}]}
    art = {"points": {"d": {"default": {"a": 0.4, "b": 0.6}}}}
    model = {"id": "m_1", "dataset_id": "d_1", "decision_points": ["d"]}
    new, mism, attached, skipped = attach(doc, model, art, None)
    assert attached == ["d"] and not mism and new["decision_policy"]["points"]["d"]["default"] == {"a": 0.4, "b": 0.6}
    assert "decision_policy" not in doc                                   # the stored version is not touched
    grown = copy.deepcopy(doc)
    grown["edges"].append({"from": "d", "to": "c", "type": "option", "index": 2})
    new, mism, attached, _ = attach(grown, model, art, None)
    assert attached == ["d"] and [m["code"] for m in mism] == ["option_added"] and new["decision_policy"]["points"]["d"]["default"]["c"] == 0.0
    shrunk = copy.deepcopy(doc)
    shrunk["edges"].pop()
    new, mism, attached, skipped = attach(shrunk, model, art, None)
    assert not attached and skipped == ["d"] and mism[0]["code"] == "option_removed"
    _, mism, attached, skipped = attach(doc, model, art, ["zzz"])
    assert not attached and mism[0]["code"] == "not_in_model"

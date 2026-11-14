"""Runs through the API: start, progress, metrics, bundle, decisions, patients, cache, limits, cancel, crash, compare."""

import json
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings

N = 160   # Norway check: no warm-up, so small cohorts are measured


def _dies_job(ctx, **kw):
    os._exit(9)


@pytest.fixture()
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "noweb", max_jobs=2, max_patients=5000, max_seeds=3))
    with TestClient(app) as c:
        yield c


def make(client, template="norway_check"):
    r = client.post("/api/projects", json={"name": "t", "template": template})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def start(client, p, **kw):
    body = {"flowchart": {"id": "observed"}, "n": N, "seeds": [1, 2], **kw}
    return client.post(f"/api/projects/{p}/runs", json=body)


def wait_job(client, job_id, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture()
def finished(client):
    p = make(client)
    r = start(client, p, label="first")
    assert r.status_code == 202, r.text
    run = r.json()
    assert wait_job(client, run["job_id"])["status"] == "succeeded"
    return p, run["id"]


def test_run_result_shape(client, finished):
    p, rid = finished
    run = client.get(f"/api/projects/{p}/runs/{rid}").json()
    assert run["status"] == "succeeded" and run["progress"] == 1.0 and run["label"] == "first"
    assert run["flowchart"] == {"id": "observed", "version": 1} and run["seeds"] == [1, 2] and run["n"] == N
    h = run["headline"]
    assert 0 <= h["on_time"] <= 1 and h["median_days"] > 0 and h["n"] > 0
    assert len(run["per_seed"]) == 2 and run["metrics"]["node_breakdown"] and run["metrics"]["by_group"]
    assert run["engine_version"] and run["patients_key"] and run["finished_at"]
    assert [r["id"] for r in client.get(f"/api/projects/{p}/runs").json()] == [rid]
    brief = client.get(f"/api/projects/{p}/runs?brief=true").json()[0]
    assert "metrics" not in brief and brief["headline"] == h
    # the flowchart version used is now locked
    v = client.get(f"/api/projects/{p}/flowcharts/observed/versions/1")
    assert v.headers["X-Version-Locked"].lower() in ("true", "1")


def test_job_endpoint_mirrors_the_run(client, finished):
    p, rid = finished
    j = client.get(f"/api/jobs/{client.get(f'/api/projects/{p}/runs/{rid}').json()['job_id']}").json()
    assert j["status"] == j["state"] == "succeeded" and j["progress"] == 1.0 and j["log_tail"] and j["owner"]["id"] == rid
    assert j["result"]["run_id"] == rid
    assert client.get("/api/jobs/j_nope").status_code == 404
    assert "counts" in client.get("/api/jobs").json()


def test_bundle_in_dashboard_format(client, finished):
    p, rid = finished
    b = client.get(f"/api/projects/{p}/runs/{rid}/bundle").json()
    sc = b["scenarios"][0]
    assert b["fixture"] is False and sc["baseline"]["metrics"]["share_within_target"] is not None
    assert sc["flowchart_before"]["nodes"] and sc["target_days"] and b["assumptions"]
    node = sc["flowchart_before"]["nodes"][0]
    assert "id" in node and "label" in node


def test_decisions_export_rows(client, finished):
    p, rid = finished
    r = client.get(f"/api/projects/{p}/runs/{rid}/decisions")
    assert r.status_code == 200
    rows = [json.loads(x) for x in r.text.splitlines()]
    assert rows, "the Norway check has decision points"
    row = rows[0]
    assert set(row) >= {"decision_point", "patient_id", "t_days", "context", "offered", "chosen"}
    assert row["chosen"] in row["offered"] and {"group", "age", "history", "attributes", "fast_track"} <= set(row["context"])
    only = client.get(f"/api/projects/{p}/runs/{rid}/decisions", params={"seed": 1, "point": row["decision_point"]}).text.splitlines()
    assert 0 < len(only) <= len(rows)
    assert client.get(f"/api/projects/{p}/runs/{rid}/decisions", params={"seed": 99}).status_code == 404


def test_patient_log_paging(client, finished):
    p, rid = finished
    a = client.get(f"/api/projects/{p}/runs/{rid}/patients", params={"limit": 5}).json()
    b = client.get(f"/api/projects/{p}/runs/{rid}/patients", params={"limit": 5, "offset": 5}).json()
    assert len(a["patients"]) == 5 and a["total"] == N and a["seed"] == 1
    assert [x["id"] for x in a["patients"]] != [x["id"] for x in b["patients"]]
    assert a["patients"][0]["events"] and a["patients"][0]["seed"] == 1


def test_identical_run_is_cached_and_two_users_share_one(client, finished):
    p, rid = finished
    again = start(client, p, label="someone else")
    assert again.status_code == 200 and again.json()["id"] == rid and again.json()["cached"] is True
    other_seeds = start(client, p, seeds=[3, 4])
    assert other_seeds.status_code == 202 and other_seeds.json()["id"] != rid
    # two simultaneous identical requests: one run
    ids = []
    def go():
        ids.append(start(client, p, seeds=[7]).json()["id"])
    ts = [threading.Thread(target=go) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(set(ids)) == 1


def test_policy_override_is_a_different_run(client, finished):
    p, rid = finished
    r = start(client, p, decision_policy={"backend": "rule", "mode": "argmax", "points": {}})
    assert r.status_code == 202 and r.json()["id"] != rid


def test_limits_and_validation(client):
    p = make(client)
    assert start(client, p, n=999999).status_code == 429
    assert start(client, p, seeds=[1, 2, 3, 4]).status_code == 429
    assert start(client, p, seeds=[1, 1]).status_code == 422
    assert start(client, p, n=0).status_code == 422
    e = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "nope"}, "n": N}).json()["error"]
    assert e["code"] == "not_found"
    assert client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed", "version": 9}, "n": N}).status_code == 404
    assert client.post("/api/projects/p_nope/runs", json={"flowchart": {"id": "observed"}}).status_code == 404
    f = make(client, "finland_lung")
    e = client.post(f"/api/projects/{f}/runs", json={"flowchart": {"id": "baseline"}, "n": 500}).json()["error"]
    assert e["code"] == "n_too_small" and "2690" in e["message"] or e["code"] == "n_too_small"


def test_cancel_a_running_run(client):
    p = make(client)
    run = start(client, p, n=4000, seeds=[1, 2, 3]).json()
    end = time.time() + 30
    while client.get(f"/api/jobs/{run['job_id']}").json()["status"] != "running" and time.time() < end:
        time.sleep(0.02)
    time.sleep(0.3)
    r = client.post(f"/api/projects/{p}/runs/{run['id']}/cancel").json()
    assert r["status"] == "cancelled"
    assert client.get(f"/api/projects/{p}/runs/{run['id']}/bundle").status_code == 409
    # a cancelled run is not a cache hit: starting again makes a new one
    again = start(client, p, n=4000, seeds=[1, 2, 3])
    assert again.status_code == 202 and again.json()["id"] != run["id"]
    client.post(f"/api/jobs/{again.json()['job_id']}/cancel")


def test_crashing_worker_marks_the_run_failed_and_the_service_lives(client, monkeypatch):
    import service.run_service as rs
    monkeypatch.setattr(rs, "execute_run", _dies_job)
    p = make(client)
    run = start(client, p).json()
    j = wait_job(client, run["job_id"])
    assert j["status"] == "failed" and j["error"]["code"] == "worker_died"
    row = client.get(f"/api/projects/{p}/runs/{run['id']}").json()
    assert row["status"] == "failed" and row["error"]["code"] == "worker_died"
    monkeypatch.undo()
    ok = start(client, p, seeds=[5]).json()
    assert wait_job(client, ok["job_id"])["status"] == "succeeded"


def test_compare_same_patients_and_refusal(client, finished):
    p, rid = finished
    fc = client.get(f"/api/projects/{p}/flowcharts/optimal/versions/latest")
    assert fc.status_code == 200, fc.text
    r2 = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "optimal"}, "n": N, "seeds": [1, 2]}).json()
    assert wait_job(client, r2["job_id"])["status"] == "succeeded"
    c = client.post(f"/api/projects/{p}/compare", json={"runs": [rid, r2["id"]]})
    assert c.status_code == 200, c.text
    c = c.json()
    h = c["headline"]["share_within_target"]
    assert c["same_patients"] and h["delta"] == pytest.approx(h["b"] - h["a"], abs=1e-3) and c["nodes"] and c["stages"]
    other = client.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "optimal"}, "n": N + 10, "seeds": [1, 2]}).json()
    wait_job(client, other["job_id"])
    e = client.post(f"/api/projects/{p}/compare", json={"runs": [rid, other["id"]]})
    assert e.status_code == 409 and e.json()["error"]["code"] == "different_patients"
    # the dashboard bundle with the earlier run as 'before'
    b = client.get(f"/api/projects/{p}/runs/{r2['id']}/bundle", params={"compare_to": rid}).json()
    assert len(b["scenarios"][0]["variants"]) == 1


def test_restart_marks_unfinished_runs_failed(tmp_path):
    from service.runs_db import Runs
    from service.store import Store
    app = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "x"))
    with TestClient(app) as c:
        p = make(c)
        run = start(c, p, n=3000, seeds=[1, 2, 3]).json()
    # app closed while the job ran: shutdown cancelled it; simulate a hard kill by leaving a running row
    store = Store(tmp_path / "d")
    Runs(store).update(run["id"], status="running")
    app2 = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "x"))
    with TestClient(app2) as c2:
        row = c2.get(f"/api/projects/{p}/runs/{run['id']}").json()
        assert row["status"] == "failed" and row["error"]["code"] == "service_restarted"


def test_flow_endpoint_totals_equal_metrics(client, finished):
    p, rid = finished
    run = client.get(f"/api/projects/{p}/runs/{rid}").json()
    f = client.get(f"/api/projects/{p}/runs/{rid}/flow")
    assert f.status_code == 200, f.text
    f = f.json()
    assert f["format"] == "flow/1" and f["seeds"] == [1, 2] and f["meta"]["complete"] is True
    m = run["metrics"]
    # pooled counts over both seeds; headline metrics are the mean over cohorts, as the run's
    assert f["metrics"]["share_within_target"] == pytest.approx(m["share_within_target"], abs=1e-3)
    assert f["metrics"]["median_days_to_treatment"] == pytest.approx(m["median_days_to_treatment"], abs=0.02)
    assert f["totals"]["n"] == sum(s["n"] for s in run["per_seed"])
    assert f["totals"]["missed_cancers"] == pytest.approx(2 * m["missed_cancers"], abs=1e-6)
    for node, v in m["node_breakdown"].items():   # critical-path waits agree with the run's node breakdown (pooled vs mean of seeds)
        assert f["steps"][node]["critical_wait"] == pytest.approx(v["wait"], abs=1.0), node
    assert len(f["cohort"]["patients"]) <= 300


def test_flow_with_another_sample_and_seed_subset(client, finished):
    p, rid = finished
    f = client.get(f"/api/projects/{p}/runs/{rid}/flow", params={"sample": 40, "sample_seed": 3, "seeds": [2]}).json()
    assert f["seeds"] == [2] and len(f["cohort"]["patients"]) <= 40 and f["meta"]["complete"] is False
    assert client.get(f"/api/projects/{p}/runs/{rid}/flow", params={"seeds": [99]}).status_code == 404

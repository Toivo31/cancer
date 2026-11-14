"""Can results be forged, versions edited, runs mixed between projects, or hidden truth read? (all of this is safe today)"""

from __future__ import annotations

import json

import pytest

from sec_helpers import make_client, new_project, wait_job, world_of
from service.runs_core import ENGINE_VERSION

RUN = {"flowchart": {"id": "observed"}, "n": 150, "seeds": [3]}


@pytest.fixture
def two_projects(tmp_path):
    with make_client(tmp_path, max_jobs=2) as c:
        yield c, new_project(c, name="A"), new_project(c, name="B")


def test_locked_versions_cannot_be_edited_or_deleted(client, project):
    B = f"/api/projects/{project}"
    run = client.post(B + "/runs", json=RUN).json()
    wait_job(client, run["job_id"])
    doc = client.get(B + "/flowcharts/observed/versions/1").json()
    assert client.get(B + "/flowcharts/observed/versions/1").headers["x-version-locked"] == "true"
    doc["description"] = "tampered after the run"
    r = client.put(B + "/flowcharts/observed/versions/1", json=doc)
    assert r.status_code == 409 and r.json()["error"]["code"] == "version_locked"
    assert client.delete(B + "/flowcharts/observed").status_code == 409
    assert client.get(B + "/flowcharts/observed/versions/1").json()["description"] != "tampered after the run"
    assert client.post(B + "/flowcharts/observed/versions", json=doc).status_code == 201      # a new version is the way to change it


def test_a_run_uses_the_document_as_it_was_when_started(client, project):
    B = f"/api/projects/{project}"
    run = client.post(B + "/runs", json=RUN).json()
    wait_job(client, run["job_id"])
    before = client.get(f"{B}/runs/{run['id']}").json()["headline"]
    w = world_of(client, project)
    w["target_days"] = 5
    assert client.put(B + "/world", json=w).status_code == 200
    assert client.get(f"{B}/runs/{run['id']}").json()["headline"] == before          # a stored run does not change when the world does
    again = client.post(B + "/runs", json=RUN)
    assert again.status_code == 202 and again.json()["id"] != run["id"]                # and the edited world is not served from the cache


def test_client_cannot_write_results_into_a_run(client, project):
    B = f"/api/projects/{project}"
    forged = {**RUN, "metrics": {"share_within_target": 1.0}, "headline": {"on_time": 1.0, "median_days": 0}, "status": "succeeded", "progress": 1.0,
              "engine_version": "forged", "source": {"optimisation": "o_x", "role": "rerun"}, "id": "r_forged", "job_id": "j_forged", "per_seed": [], "patients_key": "x"}
    r = client.post(B + "/runs", json=forged)
    assert r.status_code == 202
    run = r.json()
    assert run["id"] != "r_forged" and run["job_id"] != "j_forged" and run["status"] == "queued" and run["source"] is None
    wait_job(client, run["job_id"])
    got = client.get(f"{B}/runs/{run['id']}").json()
    assert got["engine_version"] == ENGINE_VERSION and got["headline"]["on_time"] != 1.0
    assert got["metrics"]["share_within_target"] == got["headline"]["on_time"]


def test_identical_runs_in_two_projects_never_share_results(two_projects):
    c, a, b = two_projects
    ra = c.post(f"/api/projects/{a}/runs", json=RUN).json()
    rb = c.post(f"/api/projects/{b}/runs", json=RUN).json()
    assert ra["id"] != rb["id"] and rb["cached"] is False
    wait_job(c, ra["job_id"]), wait_job(c, rb["job_id"])
    for path in ("", "/bundle", "/decisions", "/patients", "/flow"):
        assert c.get(f"/api/projects/{b}/runs/{ra['id']}{path}").status_code == 404, path       # project B cannot read project A's run by id
    assert c.post(f"/api/projects/{b}/compare", json={"runs": [ra["id"], rb["id"]]}).status_code == 404
    assert c.get(f"/api/projects/{b}/runs/{rb['id']}/bundle", params={"compare_to": ra["id"]}).status_code == 404


def test_cache_returns_the_same_run_only_for_the_same_inputs(client, project):
    B = f"/api/projects/{project}"
    first = client.post(B + "/runs", json=RUN).json()
    wait_job(client, first["job_id"])
    same = client.post(B + "/runs", json={**RUN, "label": "another label"})
    assert same.status_code == 200 and same.json()["id"] == first["id"] and same.json()["cached"] is True
    for change in ({"n": 151}, {"seeds": [4]}, {"seeds": [3, 4]}):
        other = client.post(B + "/runs", json={**RUN, **change})
        assert other.status_code == 202 and other.json()["id"] != first["id"], change
    policy = {"backend": "stub", "mode": "argmax", "points": {}}
    assert client.post(B + "/runs", json={**RUN, "decision_policy": policy}).json()["id"] != first["id"]


# ------------------------------------------------------------------------------------------ hidden truth
ROW_KEYS = {"decision_point", "patient_id", "t_days", "context", "offered", "chosen", "probs", "measured"}
CONTEXT_KEYS = {"group", "age", "t_days", "fast_track", "attributes", "history"}
HISTORY_KEYS = {"step", "test", "result", "t_days"}


def _decision_rows(c, p, n=250, template_flowchart="observed"):
    run = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": template_flowchart}, "n": n, "seeds": [8]}).json()
    assert wait_job(c, run["job_id"])["status"] == "succeeded"
    text = c.get(f"/api/projects/{p}/runs/{run['id']}/decisions").text
    return run, [json.loads(l) for l in text.splitlines() if l]


def test_decisions_export_has_no_hidden_patient_truth(client, project):
    world = world_of(client, project)
    run, rows = _decision_rows(client, project)
    assert rows, "the export should have rows"
    reveals = {t: set(spec.get("reveals") or []) for t, spec in world["tests"].items()}
    saw_attribute = False
    for r in rows:
        assert set(r) == ROW_KEYS, set(r) ^ ROW_KEYS
        assert set(r["context"]) == CONTEXT_KEYS
        revealed = set().union(*[reveals.get(h["test"], set()) for h in r["context"]["history"]]) if r["context"]["history"] else set()
        assert set(r["context"]["attributes"]) <= revealed, (r["context"]["attributes"], revealed)
        saw_attribute |= bool(r["context"]["attributes"])
        assert all(set(h) == HISTORY_KEYS for h in r["context"]["history"])
    assert saw_attribute, "the check above should have had revealed attributes to look at"
    blob = json.dumps(rows)
    for cond in world["conditions"]:
        assert f'"{cond["id"]}"' not in blob, f"condition id {cond['id']} appears in the training export"
    assert '"cancer"' not in blob and '"condition"' not in blob and '"prevalence"' not in blob


def test_patient_log_is_the_analyst_view_and_does_contain_the_truth(client, project):
    """Not a leak: /patients is for the person running the simulation. It is the one place that carries the truth and must never feed a model."""
    run, _ = _decision_rows(client, project, n=100)
    p = client.get(f"/api/projects/{project}/runs/{run['id']}/patients", params={"limit": 3}).json()["patients"][0]
    assert "cancer" in p and "condition" in p


def test_what_the_jev_receives_contains_only_revealed_information(tmp_path, allow_jev, monkeypatch):
    """Run the whole path through a local JEV server that records every request body."""
    import jev
    from jev.stub import StubBackend
    from jev.stub_server import serve_in_thread

    # The job process must see JEV_ALLOWED_HOSTS, which this test sets after the shared forkserver started: use spawn, which copies the environment.
    monkeypatch.setenv("PATHWAY_JOB_START", "spawn")
    with make_client(tmp_path, max_jobs=1) as c:
        p = new_project(c)
        world = world_of(c, p)
        fc = c.get(f"/api/projects/{p}/flowcharts/observed/versions/1").json()
        table = fc["decision_policy"]["points"]
        seen: list[dict] = []

        class Recording:
            def __init__(self):
                self.inner = StubBackend(table)

            def info(self):
                i = self.inner.info()
                return jev.BackendInfo(i.name, i.model, False, None)       # not cacheable: every request reaches the server

            def decide(self, reqs):
                seen.extend(q.to_dict() for q in reqs)
                return self.inner.decide(reqs)

        srv, url = serve_in_thread(Recording())
        allow_jev(url)
        try:
            policy = {**fc["decision_policy"], "backend": "http", "url": url, "model": "stub@1", "timeout": 5}
            run = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 150, "seeds": [2], "decision_policy": policy})
            assert run.status_code == 202, run.text
            assert wait_job(c, run.json()["job_id"], 120)["status"] == "succeeded"
        finally:
            srv.shutdown()
    assert seen, "the JEV was never asked"
    reveals = {t: set(spec.get("reveals") or []) for t, spec in world["tests"].items()}
    for q in seen:
        assert set(q) == {"request_id", "decision_point", "question_type", "context", "options"}
        ctx = q["context"]
        assert set(ctx) == CONTEXT_KEYS
        revealed = set().union(*[reveals.get(h["test"], set()) for h in ctx["history"]]) if ctx["history"] else set()
        assert set(ctx["attributes"]) <= revealed
        assert all(set(o) <= {"id", "label", "test", "features"} for o in q["options"])
    assert '"cancer"' not in json.dumps(seen) and '"condition"' not in json.dumps(seen)

"""Extra tests written with the fixes of WP-C6-SEC1 (F3, F5, F6, F7, F16); each fails on the code before the fix."""

from __future__ import annotations

import json
import logging

import pytest

import sec_jobfuncs as jf
from sec_helpers import make_client, new_project, post_raw, put_raw, wait_job, world_of


# ------------------------------------------------------------------------------------------ F3
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_non_finite_numbers_are_refused_with_a_problem_naming_the_field(client, project, literal):
    w = json.dumps(world_of(client, project)).replace('"target_days": 42', f'"target_days": {literal}')
    assert literal in w
    r = put_raw(client, f"/api/projects/{project}/world", w)
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "invalid_document"
    assert err["problems"][0]["path"] == ["target_days"] and "target_days" in err["problems"][0]["message"]


def test_non_finite_number_in_a_policy_or_run_request_is_refused(client, project):
    r = post_raw(client, f"/api/projects/{project}/runs", '{"flowchart": {"id": "observed"}, "n": 100, "decision_policy": {"x": [1, NaN]}}')
    assert r.status_code == 422 and r.json()["error"]["problems"][0]["path"] == ["decision_policy", "x", "1"]


def test_finite_numbers_and_strings_that_look_like_nan_are_accepted(client, project):
    w = world_of(client, project)
    w["description"] = "NaN Infinity 1e999 are only words here"
    w["target_days"] = 1e300
    assert client.put(f"/api/projects/{project}/world", json=w).status_code == 200


def test_json_lines_upload_with_nan_is_refused(client, project):
    body = '{"a": 1}\n{"a": NaN}\n'
    r = client.post(f"/api/projects/{project}/datasets", content=body, headers={"content-type": "application/x-ndjson"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_document"


def test_a_project_that_already_holds_a_nan_still_lists_its_runs(client, project):
    """A run row written before the check existed (or by a metric that came out 0/0) must not make GET /runs a 500."""
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1]}).json()
    assert wait_job(client, r["job_id"])["status"] == "succeeded"
    rt = client.app.state.runtime
    rt.store.execute("UPDATE runs SET metrics_json=?, headline_json=? WHERE id=?",
                     ('{"share_within_target": NaN, "by_group": {"a": [Infinity]}}', '{"share_within_target": NaN}', r["id"]))
    lst = client.get(f"/api/projects/{project}/runs")
    assert lst.status_code == 200 and lst.json()[0]["headline"]["share_within_target"] is None
    one = client.get(f"/api/projects/{project}/runs/{r['id']}")
    assert one.status_code == 200 and one.json()["metrics"]["by_group"]["a"] == [None]


# ------------------------------------------------------------------------------------------ F5
def test_policy_cannot_raise_the_timeout_or_retries_of_the_http_backend():
    from jev.http import MAX_TIMEOUT, HttpBackend
    b = HttpBackend("http://jev.example.org", timeout=3600, retries=50)
    assert b.timeout == MAX_TIMEOUT and b.retries == 1
    for bad in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            HttpBackend("http://jev.example.org", timeout=bad)


def test_non_numeric_timeout_in_a_policy_is_a_422(client, project, internal_server):
    url, _ = internal_server
    for bad in ("soon", None, [1], -5, 0):
        r = client.post(f"/api/projects/{project}/decide", json={"flowchart": {"id": "observed"}, "decision_point": "sample_plan",
                                                                 "decision_policy": {"backend": "http", "url": url, "model": "m", "timeout": bad}})
        assert r.status_code == 422, (bad, r.status_code, r.text)


def test_call_limits_only_lower_the_timeout():
    from jev.factory import _http_limits, call_limits
    assert _http_limits({"timeout": 99}) == (5.0, 1)
    assert _http_limits({"timeout": 0.3}) == (0.3, 1)
    with call_limits(1.0, 0):
        assert _http_limits({"timeout": 99}) == (1.0, 0)
        assert _http_limits({"timeout": 0.3}) == (0.3, 0)
    assert _http_limits({}) == (2.0, 1)


# ------------------------------------------------------------------------------------------ F6
def test_job_error_has_no_traceback_key_and_no_server_path_in_the_message(client, caplog):
    rt = client.app.state.runtime
    with caplog.at_level(logging.ERROR, logger="pathway.jobs"):
        j = rt.runner.submit("t", jf.failer_with_path)
        rt.runner.wait(j.id, 20)
    err = client.get(f"/api/jobs/{j.id}").json()["error"]
    assert err["code"] == "FileNotFoundError" and "traceback" not in err
    assert "/home" not in err["message"] and "/tmp" not in err["message"] and "<path>" in err["message"], err
    stored = rt.jobrows.get(j.id)
    assert "Traceback" not in json.dumps(stored)
    assert "Traceback" in caplog.text and "sec_jobfuncs" in caplog.text        # the server log keeps the full traceback


# ------------------------------------------------------------------------------------------ F7
def test_deleting_a_project_cancels_all_its_jobs_and_leaves_other_projects_alone(tmp_path):
    with make_client(tmp_path, max_jobs=1) as c:
        a, b = new_project(c, "finland_lung", "a"), new_project(c, "finland_lung", "b")
        ra = [c.post(f"/api/projects/{a}/runs", json={"flowchart": {"id": "baseline"}, "n": 3000, "seeds": [s]}).json() for s in (1, 2)]
        rb = c.post(f"/api/projects/{b}/runs", json={"flowchart": {"id": "baseline"}, "n": 3000, "seeds": [1]}).json()
        rt = c.app.state.runtime
        assert c.delete(f"/api/projects/{a}").status_code == 204
        for r in ra:                        # one was running, one queued: both are final at once, nothing waits for 3000 patients
            assert rt.runner.get(r["job_id"]).status == "cancelled", rt.runner.get(r["job_id"]).status
        assert rt.runner.get(rb["job_id"]).status in ("queued", "running", "succeeded")
        assert c.get(f"/api/projects/{b}/runs/{rb['id']}").status_code == 200
        c.post(f"/api/projects/{b}/runs/{rb['id']}/cancel")


def test_flow_rebuild_job_is_cancelled_with_its_project(tmp_path):
    with make_client(tmp_path, max_jobs=1) as c:
        p = new_project(c)
        rt = c.app.state.runtime
        j = rt.runner.submit("flow", jf.sleeper, {"seconds": 60}, owner={"project": p, "kind": "flow", "id": "r_x"})
        assert rt.cancel_project_jobs(p) == 1 and rt.runner.get(j.id).status == "cancelled"

"""Hostile or odd input: JSON, numbers, ids, sizes (findings F3, F9, F10, F15)."""

from __future__ import annotations

import json

import pytest

from sec_helpers import make_client, new_project, post_raw, put_raw, wait_job, world_of


# ------------------------------------------------------------------------------------------ F3: NaN and Infinity
def _world_with_nan(c, p):
    w = world_of(c, p)
    return json.dumps(w).replace('"target_days": 42', '"target_days": NaN'), w


def test_world_with_nan_is_rejected(client, project):
    text, _ = _world_with_nan(client, project)
    r = put_raw(client, f"/api/projects/{project}/world", text)
    assert r.status_code == 422, r.status_code


def test_world_with_infinity_is_rejected(client, project):
    w = json.dumps(world_of(client, project)).replace('"target_days": 42', '"target_days": Infinity')
    assert put_raw(client, f"/api/projects/{project}/world", w).status_code == 422


def test_flowchart_with_nan_is_rejected(client, project):
    doc = client.get(f"/api/projects/{project}/flowcharts/observed/versions/1").json()
    doc.pop("version", None), doc.pop("parent_version", None)
    doc["id"] = "nanny"
    doc["test_overrides"] = {"first_visit": {"extra": "NANPLACEHOLDER"}}
    text = json.dumps(doc).replace('"NANPLACEHOLDER"', "NaN")
    assert post_raw(client, f"/api/projects/{project}/flowcharts", text).status_code == 422


def test_nan_in_world_does_not_poison_the_run_list(client, project):
    text, w = _world_with_nan(client, project)
    put_raw(client, f"/api/projects/{project}/world", text)
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 120, "seeds": [1]})
    if r.status_code == 202:
        wait_job(client, r.json()["job_id"])
    client.put(f"/api/projects/{project}/world", json=w)          # the owner repairs the world ...
    assert client.get(f"/api/projects/{project}/runs").status_code == 200       # ... but the stored run still breaks the list


# ------------------------------------------------------------------------------------------ parsing limits (safe)
def test_deeply_nested_json_is_a_client_error_not_a_crash(client, project):
    for body in ("[" * 150_000 + "]" * 150_000, '{"flowchart":{"id":"a","nodes":' + "[" * 60_000 + "]" * 60_000 + "}}", '{"a":' * 50_000 + "1" + "}" * 50_000):
        r = post_raw(client, f"/api/projects/{project}/validate", body)
        assert r.status_code in (400, 413, 422), r.status_code


def test_huge_and_odd_numbers_are_refused_or_clamped(client, project):
    B = f"/api/projects/{project}/runs"
    assert post_raw(client, B, '{"flowchart":{"id":"observed"},"n":1' + "0" * 5000 + "}").status_code in (400, 422)     # int/str digit limit
    assert post_raw(client, B, '{"flowchart":{"id":"observed"},"n":1e400}').status_code == 422
    assert post_raw(client, B, '{"flowchart":{"id":"observed"},"n":NaN}').status_code == 422
    assert post_raw(client, B, '{"flowchart":{"id":"observed"},"n":10.5}').status_code == 422
    assert post_raw(client, B, '{"flowchart":{"id":"observed"},"n":10,"seeds":[Infinity]}').status_code == 422


def test_duplicate_keys_last_one_wins_and_is_validated_as_such(client, project):
    r = post_raw(client, "/api/projects", '{"name":"a","template":"does_not_exist","template":"norway_check"}')
    assert r.status_code == 201 and r.json()["template"] == "norway_check"


def test_limits_are_enforced(tmp_path):
    with make_client(tmp_path, max_patients=500, max_seeds=2, max_projects=2, max_versions_per_flowchart=2, max_document_bytes=20_000) as c:
        p = new_project(c)
        B = f"/api/projects/{p}"
        assert c.post(B + "/runs", json={"flowchart": {"id": "observed"}, "n": 501}).status_code == 429
        assert c.post(B + "/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1, 2, 3]}).status_code == 429
        assert c.post(B + "/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1, 1]}).status_code == 422
        assert c.post(B + "/runs", json={"flowchart": {"id": "observed"}, "n": 0}).status_code == 422
        assert c.post(B + "/optimisations", json={"flowchart": {"id": "observed"}, "n": 501}).status_code == 429
        assert c.post(B + "/optimisations", json={"flowchart": {"id": "observed"}, "max_changes": 1000}).status_code == 429
        new_project(c, name="second")
        assert c.post("/api/projects", json={"name": "third", "template": "norway_check"}).status_code == 429
        assert c.post(B, content="x" * 30_000).status_code == 413
        assert c.post("/api/projects", content=b"{" + b" " * 30_000 + b"}", headers={"content-type": "application/json"}).status_code == 413


def test_streamed_body_without_content_length_is_cut_at_the_limit(tmp_path):
    with make_client(tmp_path, max_document_bytes=10_000) as c:
        def chunks():
            for _ in range(50):
                yield b" " * 1000
        r = c.post("/api/projects", content=chunks(), headers={"content-type": "application/json"})
        assert r.status_code == 413


# ------------------------------------------------------------------------------------------ F9: integer overflow
def test_huge_version_in_path_is_a_404_or_422(client, project):
    r = client.get(f"/api/projects/{project}/flowcharts/observed/versions/{10 ** 30}")
    assert r.status_code in (404, 422), r.status_code


def test_huge_version_in_run_request_is_a_404_or_422(client, project):
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed", "version": 10 ** 30}, "n": 100})
    assert r.status_code in (404, 422), r.status_code


# ------------------------------------------------------------------------------------------ F10: ids that browsers normalise
@pytest.mark.parametrize("bad_id", ["..", "."])
def test_flowchart_id_cannot_be_a_dot_segment(client, project, bad_id):
    doc = client.get(f"/api/projects/{project}/flowcharts/observed/versions/1").json()
    doc.pop("version", None), doc.pop("parent_version", None)
    doc["id"] = bad_id
    assert client.post(f"/api/projects/{project}/flowcharts", json=doc).status_code == 422


def test_world_id_cannot_be_a_dot_segment(tmp_path):
    from service.models import WorldDocument
    with pytest.raises(ValueError):
        WorldDocument(id="..", conditions=[{"id": "x"}])


# ------------------------------------------------------------------------------------------ F15: validation lets bad worlds through
@pytest.mark.xfail(strict=True, reason="F15: arrivals.rate_per_day = 0 passes validation and then fails every run with ZeroDivisionError")
def test_world_with_zero_arrival_rate_is_refused(client, project):
    w = world_of(client, project)
    w["arrivals"] = {"rate_per_day": 0}
    assert client.put(f"/api/projects/{project}/world", json=w).status_code == 422


@pytest.mark.xfail(strict=True, reason="F15: a text where a number belongs in a distribution passes validation and fails the job")
def test_world_with_text_in_a_distribution_is_refused(client, project):
    w = world_of(client, project)
    w["age"] = {"dist": "uniform", "low": "a", "high": "b"}
    assert client.put(f"/api/projects/{project}/world", json=w).status_code == 422


# ------------------------------------------------------------------------------------------ SQL
def test_sql_metacharacters_are_data(client, project):
    nasty = "x'); DROP TABLE projects; --"
    r = client.post("/api/projects", json={"name": nasty, "template": "norway_check"})
    assert r.status_code == 201 and r.json()["name"] == nasty
    assert client.patch(f"/api/projects/{project}", json={"name": "' OR '1'='1"}).status_code == 200
    assert client.get(f"/api/projects/{project}/runs", params={"flowchart": "' OR 1=1 --"}).json() == []
    assert client.get("/api/jobs", params={"status": "x' OR 1=1 --"}).status_code == 200
    lab = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "label": nasty})
    assert lab.status_code == 202 and lab.json()["label"] == nasty
    assert len(client.get("/api/projects").json()) == 2          # both projects survived

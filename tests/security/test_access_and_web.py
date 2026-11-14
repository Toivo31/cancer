"""Who may call the API, and what a browser will let other sites do (findings F1, F12, F13)."""

from __future__ import annotations

import pytest

from sec_helpers import make_client, new_project


def test_requests_without_the_access_token_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PATHWAY_ACCESS_TOKEN", "s3cret-token")
    with make_client(tmp_path) as c:
        assert c.get("/api/health").status_code == 200                      # liveness stays open
        for method, path in (("GET", "/api/projects"), ("POST", "/api/projects"), ("GET", "/api/jobs"), ("GET", "/api/templates")):
            r = c.request(method, path, json={"name": "x", "template": "norway_check"} if method == "POST" else None)
            assert r.status_code in (401, 403), f"{method} {path} answered {r.status_code} without a token"


def test_today_anybody_who_can_reach_the_port_can_list_and_delete(tmp_path):
    """Documents F1 as it stands: this test passes now and should be changed when the token lands."""
    with make_client(tmp_path) as c:
        p = new_project(c)
        assert any(x["id"] == p for x in c.get("/api/projects").json())
        assert c.delete(f"/api/projects/{p}").status_code == 204


def test_project_and_job_ids_are_only_32_bits(tmp_path):
    """F1 context: ids are 8 hex digits, so 'isolation by id' (spec 03) is a few billion guesses, and GET /api/projects lists them anyway."""
    with make_client(tmp_path) as c:
        p = new_project(c)
        assert len(p.split("_", 1)[1]) == 8
        assert [x["id"] for x in c.get("/api/projects").json()] == [p]


@pytest.mark.xfail(strict=True, reason="F12: job list, job status and job cancel are global; any caller sees every project's job ids, labels and project ids")
def test_job_list_is_scoped_to_what_the_caller_may_see(tmp_path):
    with make_client(tmp_path) as c:
        a, b = new_project(c, name="team-a"), new_project(c, name="team-b")
        r = c.post(f"/api/projects/{a}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "label": "team A private label"}).json()
        listing = c.get("/api/jobs").text
        assert "team A private label" not in listing and a not in listing, "the global job list names another project's run"
        assert c.post(f"/api/jobs/{r['job_id']}/cancel").status_code in (403, 404), "any caller may cancel any job by id"


# ------------------------------------------------------------------------------------------ browsers
def test_no_cors_headers_so_other_sites_cannot_read_responses(client):
    r = client.get("/api/projects", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    pre = client.options("/api/projects/p_x", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "DELETE"})
    assert pre.status_code in (400, 405) and "access-control-allow-origin" not in {k.lower() for k in pre.headers}


def test_simple_cross_site_posts_are_not_accepted(client):
    """A form or fetch(no-cors) can only send these content types without a preflight; the JSON endpoints refuse them."""
    for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
        r = client.post("/api/projects", content='{"name":"csrf","template":"norway_check"}', headers={"content-type": ctype})
        assert r.status_code == 422, (ctype, r.status_code)
    assert client.get("/api/projects").json() == []


def test_markup_in_names_is_returned_as_json_data(client):
    nasty = "<img src=x onerror=alert(1)>\"'</script>"
    r = client.post("/api/projects", json={"name": nasty[:100], "template": "norway_check"})
    assert r.status_code == 201 and r.json()["name"] == nasty[:100]
    got = client.get("/api/projects")
    assert got.headers["content-type"].startswith("application/json")
    assert "text/html" not in got.headers["content-type"]


def test_basic_security_headers_are_set(client):
    h = {k.lower(): v for k, v in client.get("/api/projects").headers.items()}
    assert h.get("x-content-type-options") == "nosniff"

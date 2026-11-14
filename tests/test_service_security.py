"""Access token, read-only modes, limits and the JEV host allowlist (M7-2, M7-6)."""

import socket

import pytest
from fastapi.testclient import TestClient

from service import security
from service.app import create_app
from service.config import Settings

TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ENV = ["PATHWAY_ACCESS_TOKEN", "PATHWAY_PUBLIC_READ", "PATHWAY_READ_ONLY", "PATHWAY_REQUIRE_AUTH", "PATHWAY_RATE_PER_MIN",
       "PATHWAY_JOB_STARTS_PER_MIN", "PATHWAY_MAX_ACTIVE_JOBS", "PATHWAY_AUTH_FAILURES_PER_MIN", "PATHWAY_MIN_FREE_MB",
       "JEV_ALLOWED_HOSTS", "JEV_DEFAULT_URL", "PATHWAY_SYNTHETIC_ONLY", "PATHWAY_DATA_NOTICE"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for n in ENV:
        monkeypatch.delenv(n, raising=False)


def make_client(tmp_path, **settings):
    app = create_app(Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "noweb", **settings))
    return TestClient(app)


def with_env(monkeypatch, **kv):
    for k, v in kv.items():
        monkeypatch.setenv(k, str(v))


def code(r, status):
    assert r.status_code == status, r.text
    return r.json()["error"]["code"]


def test_open_mode_without_token_is_the_development_default(tmp_path):
    with make_client(tmp_path) as c:
        assert c.get("/api/templates").status_code == 200
        a = c.get("/api/access").json()
        assert a["mode"] == "open" and a["token_required"] is False and a["can_write"] is True
        assert a["data_notice"]["synthetic_only"] is True and "synthetic" in a["data_notice"]["text"]


def test_token_required_for_everything_but_health_and_access(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    with make_client(tmp_path) as c:
        assert code(c.get("/api/templates"), 401) == "unauthorized"
        assert c.get("/api/templates").headers["www-authenticate"].startswith("Bearer")
        assert code(c.post("/api/projects", json={"name": "x", "template": "norway_check"}), 401) == "unauthorized"
        assert code(c.get("/api/templates", headers={"Authorization": "Bearer nope"}), 401) == "invalid_token"
        assert code(c.get("/api/templates", headers={"Authorization": f"Bearer {TOKEN}x"}), 401) == "invalid_token"
        assert c.get("/api/health").status_code == 200
        a = c.get("/api/access").json()
        assert a["mode"] == "token" and a["authenticated"] is False and a["can_write"] is False and a["jev_default_url"] is None
        assert c.get("/api/templates", headers=AUTH).status_code == 200
        assert c.get("/api/templates", headers={"X-Pathway-Token": TOKEN}).status_code == 200
        assert c.get("/api/access", headers=AUTH).json()["authenticated"] is True
        assert c.get("/api/templates", params={"token": TOKEN}).status_code == 401         # never from the URL
        assert c.get("/docs").status_code == 200 and c.get("/openapi.json").status_code == 200   # no data in them


def test_path_tricks_do_not_reach_data(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    with make_client(tmp_path) as c:
        for p in ("//api/projects", "/api/projects/", "/API/projects", "/api/./projects", "/api%2Fprojects", "/api/projects;x"):
            r = c.get(p, follow_redirects=True)
            assert r.status_code in (401, 404), (p, r.status_code)


def test_wrong_tokens_are_throttled(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_AUTH_FAILURES_PER_MIN=3)
    with make_client(tmp_path) as c:
        codes = [c.get("/api/projects", headers={"Authorization": "Bearer guess"}).status_code for _ in range(5)]
        assert codes == [401, 401, 401, 429, 429]
        r = c.get("/api/projects", headers=AUTH)               # the real token is not blocked by earlier failures
        assert r.status_code == 200


def test_public_read_lets_visitors_read_but_not_write(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_PUBLIC_READ=1)
    with make_client(tmp_path) as c:
        pid = c.post("/api/projects", json={"name": "seed", "template": "norway_check"}, headers=AUTH).json()["id"]
        assert c.get("/api/templates").status_code == 200
        assert c.get(f"/api/projects/{pid}").status_code == 200
        assert code(c.post("/api/projects", json={"name": "x", "template": "norway_check"}), 401) == "unauthorized"
        assert code(c.delete(f"/api/projects/{pid}"), 401) == "unauthorized"
        assert code(c.post(f"/api/projects/{pid}/runs", json={"flowchart": {"id": "observed"}}), 401) == "unauthorized"
        # calculations that store nothing stay open
        assert c.post(f"/api/projects/{pid}/validate", json={"flowchart": {}}).status_code != 401
        assert c.get("/api/access").json()["mode"] == "public_read"
        assert c.delete(f"/api/projects/{pid}", headers=AUTH).status_code == 204


def test_read_only_refuses_writes_even_with_the_token(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_PUBLIC_READ=1, PATHWAY_READ_ONLY=1)
    with make_client(tmp_path) as c:
        assert code(c.post("/api/projects", json={"name": "x", "template": "norway_check"}, headers=AUTH), 403) == "read_only"
        assert code(c.put("/api/projects/p_1/world", json={}, headers=AUTH), 403) == "read_only"
        assert code(c.delete("/api/projects/p_1", headers=AUTH), 403) == "read_only"
        assert code(c.post("/api/projects/p_1/runs", json={}, headers=AUTH), 403) == "read_only"
        assert c.get("/api/templates").status_code == 200
        assert c.get("/api/access", headers=AUTH).json()["can_write"] is False


def test_job_starts_are_rate_limited(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_JOB_STARTS_PER_MIN=2)
    with make_client(tmp_path) as c:
        pid = c.post("/api/projects", json={"name": "p", "template": "norway_check"}, headers=AUTH).json()["id"]
        statuses = [c.post(f"/api/projects/{pid}/runs", json={"flowchart": {"id": "nope"}}, headers=AUTH).status_code for _ in range(4)]
        assert statuses[:2] == [404, 404] or statuses[:2] == [422, 422]    # reached the route
        assert statuses[2:] == [429, 429]
        r = c.post(f"/api/projects/{pid}/optimisations", json={"flowchart": {"id": "x"}}, headers=AUTH)
        assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_active_job_cap(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_MAX_ACTIVE_JOBS=3)
    with make_client(tmp_path) as c:
        class Runner:
            def counts(self):
                return {"queued": 2, "running": 1}
        class RT:
            runner = Runner()
        c.app.state.runtime = RT()
        pid = c.post("/api/projects", json={"name": "p", "template": "norway_check"}, headers=AUTH).json()["id"]
        assert code(c.post(f"/api/projects/{pid}/runs", json={"flowchart": {"id": "x"}}, headers=AUTH), 429) == "too_many_jobs"
        c.app.state.runtime = None


def test_general_rate_limit(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN, PATHWAY_RATE_PER_MIN=5)
    with make_client(tmp_path) as c:
        s = [c.get("/api/templates", headers=AUTH).status_code for _ in range(7)]
        assert s == [200] * 5 + [429] * 2
        assert c.get("/api/health").status_code == 200          # health checks are never throttled


def test_size_limit_returns_413_and_is_checked_after_the_token(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    with make_client(tmp_path, max_document_bytes=2000) as c:
        big = {"name": "x" * 5000, "template": "norway_check"}
        assert code(c.post("/api/projects", json=big, headers=AUTH), 413) == "payload_too_large"
        assert code(c.post("/api/projects", json=big), 401) == "unauthorized"      # nothing is read for a stranger
        assert code(c.post("/api/projects", content=b"{" + b" " * 5000 + b"}", headers={**AUTH, "content-type": "application/json"}), 413) == "payload_too_large"


def test_full_volume_refuses_writes_but_not_deletes(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    with make_client(tmp_path) as c:
        pid = c.post("/api/projects", json={"name": "p", "template": "norway_check"}, headers=AUTH).json()["id"]
        monkeypatch.setenv("PATHWAY_MIN_FREE_MB", str(10**9))            # more than any disk has
        c.app.user_middleware  # noqa: B018 - the guard re-reads the env, the disk probe is cached per guard
        import service.security as sec
        monkeypatch.setattr(sec.shutil, "disk_usage", lambda p: type("U", (), {"free": 1_000_000})())
        for g in _guards(c.app):
            g._disk = None
        assert code(c.post("/api/projects", json={"name": "q", "template": "norway_check"}, headers=AUTH), 507) == "storage_full"
        assert c.get("/api/projects", headers=AUTH).status_code == 200
        assert c.delete(f"/api/projects/{pid}", headers=AUTH).status_code == 204


def _guards(app):
    out, node = [], app.middleware_stack
    while node is not None:
        if isinstance(node, security.Guard):
            out.append(node)
        node = getattr(node, "app", None)
    return out


def test_startup_refuses_unsafe_environments(monkeypatch):
    with_env(monkeypatch, PATHWAY_REQUIRE_AUTH=1)
    with pytest.raises(security.ConfigError, match="no PATHWAY_ACCESS_TOKEN"):
        create_app(Settings())
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN="short")
    with pytest.raises(security.ConfigError, match="shorter"):
        create_app(Settings())
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    create_app(Settings())
    with_env(monkeypatch, JEV_ALLOWED_HOSTS="http://evil/x")
    with pytest.raises(security.ConfigError):
        create_app(Settings())


def test_data_notice_can_be_reworded_or_switched_off(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_DATA_NOTICE="Only toy numbers here.")
    with make_client(tmp_path) as c:
        assert c.get("/api/access").json()["data_notice"] == {"synthetic_only": True, "text": "Only toy numbers here."}
    with_env(monkeypatch, PATHWAY_SYNTHETIC_ONLY=0)
    with make_client(tmp_path) as c:
        assert c.get("/api/access").json()["data_notice"] == {"synthetic_only": False, "text": ""}


def test_safe_headers_and_no_store(tmp_path):
    with make_client(tmp_path) as c:
        r = c.get("/api/templates")
        assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
        assert c.get("/docs").headers["x-frame-options"] == "DENY"


# ------------------------------------------------------------------------------------------ JEV allowlist (SSRF)
def policy(url, **kw):
    return {"backend": "http", "url": url, **kw}


@pytest.fixture()
def resolver(monkeypatch):
    table = {}
    real = socket.getaddrinfo

    def fake(host, port, *a, **k):
        if host in table:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (table[host], port))]
        return real(host, port, *a, **k)
    monkeypatch.setattr(security.socket, "getaddrinfo", fake)
    return table


def test_http_policy_refused_when_nothing_is_allowed():
    with pytest.raises(security.HostNotAllowed, match="allows no JEV hosts"):
        security.check_decision_policy(policy("http://203.0.113.5:9000"))
    security.check_decision_policy({"backend": "stub"})          # stub and rule need nothing
    security.check_decision_policy({"backend": "rule"})
    security.check_decision_policy(None)


def test_only_listed_hosts_and_ports(monkeypatch, resolver):
    with_env(monkeypatch, JEV_ALLOWED_HOSTS="203.0.113.5:9000, jev.example")
    resolver["jev.example"] = "198.51.100.7"
    security.check_decision_policy(policy("http://203.0.113.5:9000/base"))
    security.check_decision_policy({"backend": "http://jev.example:1234"})
    security.check_decision_policy(policy("jev.example"))                     # scheme-less, as the HTTP backend accepts
    for bad in ("http://203.0.113.5:9001", "http://203.0.113.6:9000", "http://localhost:9000", "http://127.0.0.1:9000",
                "http://jev.example.evil.com", "http://203.0.113.5:9000@evil.example", "http://evil.example@203.0.113.5:9000",
                "http://203.0.113.5:9000\\@evil", "ftp://jev.example", "http://2130706433/", "http://0x7f.1/", "http://[::1]:9000"):
        with pytest.raises(security.HostNotAllowed):
            security.check_decision_policy(policy(bad))


def test_metadata_addresses_are_refused_even_when_listed(monkeypatch, resolver):
    with_env(monkeypatch, JEV_ALLOWED_HOSTS="169.254.169.254,metadata.internal,sneaky.example,[fd00:ec2::254],100.100.100.200")
    resolver["metadata.internal"] = "169.254.169.254"
    resolver["sneaky.example"] = "169.254.1.1"
    for url in ("http://169.254.169.254/latest/meta-data", "http://metadata.internal", "http://sneaky.example",
                "http://[fd00:ec2::254]/", "http://100.100.100.200/"):
        with pytest.raises(security.HostNotAllowed, match="never allowed"):
            security.check_decision_policy(policy(url))


def test_loopback_and_private_are_allowed_when_the_operator_lists_them(monkeypatch):
    with_env(monkeypatch, JEV_ALLOWED_HOSTS="127.0.0.1:9100,10.0.0.5")
    security.check_decision_policy(policy("http://127.0.0.1:9100"))
    security.check_decision_policy(policy("http://10.0.0.5:8000"))


def test_per_point_urls_are_checked_too(monkeypatch):
    with_env(monkeypatch, JEV_ALLOWED_HOSTS="203.0.113.5")
    dp = {"backend": "stub", "points": {"a": {"backend": "http", "url": "http://evil.example"}}}
    with pytest.raises(security.HostNotAllowed, match="points.a"):
        security.check_decision_policy(dp)
    with pytest.raises(security.HostNotAllowed):
        security.check_decision_policy({"backend": "stub", "url": "http://evil.example", "points": {"a": {"backend": "http"}}})
    security.check_decision_policy({"backend": "stub", "url": "http://evil.example"})      # never used, not called


def test_default_url_host_is_allowed_implicitly(monkeypatch):
    with_env(monkeypatch, JEV_DEFAULT_URL="http://203.0.113.9:9000")
    security.check_decision_policy(policy("http://203.0.113.9:9000"))


def test_the_service_applies_the_allowlist_to_runs_and_try_a_decision(tmp_path, monkeypatch):
    with_env(monkeypatch, PATHWAY_ACCESS_TOKEN=TOKEN)
    with make_client(tmp_path) as c:
        pid = c.post("/api/projects", json={"name": "p", "template": "norway_check"}, headers=AUTH).json()["id"]
        evil = {"backend": "http", "url": "http://169.254.169.254/latest"}
        r = c.post(f"/api/projects/{pid}/runs", json={"flowchart": {"id": "observed"}, "n": 500, "seeds": [1], "decision_policy": evil}, headers=AUTH)
        assert r.status_code == 422 and "JEV_ALLOWED_HOSTS" in r.text, r.text
        fc = c.get(f"/api/projects/{pid}", headers=AUTH).json()["flowcharts"][0]["id"]
        point = next(n["id"] for n in c.get(f"/api/projects/{pid}/flowcharts/{fc}/versions/latest", headers=AUTH).json()["nodes"] if n.get("kind") == "decision")
        r = c.post(f"/api/projects/{pid}/decide", json={"flowchart": {"id": fc}, "decision_point": point, "decision_policy": evil}, headers=AUTH)
        assert r.status_code == 422 and "JEV_ALLOWED_HOSTS" in r.text, r.text

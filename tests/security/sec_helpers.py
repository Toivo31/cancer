"""Helpers shared by the security review tests (docs/platform/security-review.md).

Everything runs against a local TestClient and local servers on 127.0.0.1 with synthetic data; each test builds its own
app on a temporary data directory, so no test touches another test's projects and none writes outside ``tmp_path``.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings

FINAL = ("succeeded", "failed", "cancelled")


def make_client(tmp_path, **settings):
    """TestClient on a fresh data directory. Server errors come back as 500 responses, not exceptions."""
    base = dict(data_dir=tmp_path / "data", web_dir=tmp_path / "noweb", max_jobs=2, job_seconds=60)
    base.update(settings)
    app = create_app(Settings(**base))
    return TestClient(app, raise_server_exceptions=False)


def wait_job(c, job_id, timeout=60.0):
    end = time.time() + timeout
    j = {}
    while time.time() < end:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j.get("status") in FINAL:
            return j
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} still {j.get('status')} after {timeout}s")


def new_project(c, template="norway_check", name="sec"):
    r = c.post("/api/projects", json={"name": name, "template": template})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def world_of(c, p):
    return c.get(f"/api/projects/{p}/world").json()["world"]


def put_raw(c, path, text: str):
    """Send ``text`` as the JSON body unchanged (to get NaN, duplicate keys and the like past the test client's encoder)."""
    return c.put(path, content=text, headers={"content-type": "application/json"})


def post_raw(c, path, text: str):
    return c.post(path, content=text, headers={"content-type": "application/json"})

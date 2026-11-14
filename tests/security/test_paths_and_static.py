"""Client text that becomes a path: ids, blob keys, static files (findings F11 and what is safe)."""

from __future__ import annotations

import os
from urllib.parse import quote

import pytest

from sec_helpers import make_client, new_project, wait_job
from service.store import Store

TRAVERSAL = ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "%2e%2e%2f%2e%2e%2fetc%2fpasswd", "....//....//etc/passwd", "/etc/passwd", "C:\\Windows\\win.ini",
             "..\\..\\x", "a/../../b", "p_1\x00../..", "\u2025/\u2025/etc", "\uff0e\uff0e/\uff0e\uff0e/x", "x" * 5000, "\u0130\u0131", "con", "NUL", "p_ ", "p_.", "~root"]


def test_hostile_ids_in_urls_only_ever_give_404_or_422(tmp_path):
    with make_client(tmp_path) as c:
        p = new_project(c)
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 60}).json()
        wait_job(c, r["job_id"])
        for bad in TRAVERSAL:
            q = quote(bad, safe="%")
            for url in (f"/api/projects/{q}", f"/api/projects/{q}/runs", f"/api/projects/{p}/runs/{q}", f"/api/projects/{p}/runs/{q}/decisions",
                        f"/api/projects/{p}/runs/{q}/bundle", f"/api/projects/{p}/runs/{q}/patients", f"/api/projects/{p}/runs/{q}/flow",
                        f"/api/projects/{p}/flowcharts/{q}", f"/api/projects/{p}/flowcharts/{q}/versions/1", f"/api/jobs/{q}", f"/api/templates/{q}",
                        f"/api/projects/{p}/optimisations/{q}"):
                resp = c.get(url, follow_redirects=False)
                assert resp.status_code in (404, 307, 422, 405), (url[:80], resp.status_code)
                assert "root:" not in resp.text and "[fonts]" not in resp.text


def test_hostile_ids_in_bodies_are_data_only(tmp_path):
    with make_client(tmp_path) as c:
        p = new_project(c)
        for bad in TRAVERSAL:
            r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": bad}, "n": 60})
            assert r.status_code in (404, 422), (bad[:30], r.status_code)
            r = c.post(f"/api/projects/{p}/compare", json={"runs": [bad, bad]})
            assert r.status_code in (404, 422, 409), r.status_code
        r = c.post("/api/projects", json={"name": "../../../../tmp/evil", "template": "../../etc/passwd"})
        assert r.status_code == 404                                              # template names are dictionary keys, never paths
        r = c.post("/api/projects", json={"name": "../../../../tmp/evil_name", "template": "norway_check"})
        assert r.status_code == 201 and not os.path.exists("/tmp/evil_name")     # a project name is a label; its files are named by generated id


def test_unique_ids_and_blob_names_come_from_the_server(tmp_path):
    with make_client(tmp_path) as c:
        p = new_project(c)
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "label": "../../x"}).json()
        wait_job(c, r["job_id"])
        names = {f.name for f in (tmp_path / "data" / "blobs").rglob("*") if f.is_file()}
        assert names and all(n.startswith("r_") for n in names), names


# ------------------------------------------------------------------------------------------ F11: the blob key check is weaker than it looks
@pytest.mark.xfail(strict=True, reason="F11: the key pattern allows '..' as a whole path part; Store._blob_path('..', '..', 'x') leaves the blob directory")
def test_blob_path_rejects_dot_segments(tmp_path):
    s = Store(tmp_path / "d")
    path = s._blob_path("..", "..", "x")
    assert (tmp_path / "d" / "blobs") in path.resolve().parents, f"{path} is outside the blob directory"


@pytest.mark.xfail(strict=True, reason="F11: '$' in the key pattern also matches before a trailing newline")
def test_blob_path_rejects_trailing_newline(tmp_path):
    s = Store(tmp_path / "d")
    with pytest.raises(ValueError):
        s._blob_path("p_ok", "runlogs", "r_1\n")


@pytest.mark.xfail(strict=True, reason="F11: the same pattern is repeated in service/runs_core.py (stream_path)")
def test_stream_path_rejects_dot_segments(tmp_path):
    from service.runs_core import stream_path
    with pytest.raises(ValueError):
        stream_path(Store(tmp_path / "d"), "..", "..", "x")


def test_blob_path_rejects_slashes_and_odd_characters(tmp_path):
    s = Store(tmp_path / "d")
    for bad in ["a/b", "a\\b", "a b", "", "x" * 81, "é", "a\x00b", "a:b"]:
        with pytest.raises(ValueError):
            s._blob_path("p_ok", "runlogs", bad)


# ------------------------------------------------------------------------------------------ static files
def test_static_mount_does_not_serve_files_outside_the_web_directory(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>app</html>")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    (web / "leak").symlink_to(secret)
    (web / "linkdir").symlink_to(tmp_path / "data")
    with make_client(tmp_path, web_dir=web) as c:
        assert c.get("/").text == "<html>app</html>"
        for path in ["/leak", "/linkdir/pathway.sqlite3", "/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/%2e%2e%2fsecret.txt",
                     "/....//secret.txt", "//secret.txt", "/web/../secret.txt", "/\\..\\secret.txt", "/index.html/../../secret.txt"]:
            r = c.get(path, follow_redirects=False)
            assert "TOP-SECRET" not in r.text and b"SQLite format" not in r.content, path


def test_api_routes_win_over_the_static_catch_all(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("app")
    with make_client(tmp_path, web_dir=web) as c:
        assert c.get("/api/health").json()["ok"] is True
        assert c.get("/api/nope").status_code == 404
        assert c.get("/api/nope").headers["content-type"].startswith("application/json")

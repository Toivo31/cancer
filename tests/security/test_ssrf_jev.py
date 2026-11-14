"""Outbound calls: the ``http`` decision backend takes a URL from the client (finding F2, F5, F10).

Spec 03/07 say a JEV URL is called "only to allowed hosts" (``JEV_ALLOWED_HOSTS``). At f0bca56 nothing reads that variable.
Only 127.0.0.1 servers started by these tests are contacted; link-local and private addresses are only passed to the URL
parser of ``HttpBackend`` (its constructor does not connect).
"""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sec_helpers import make_client, new_project
from jev.http import HttpBackend

DECIDE = {"flowchart": {"id": "observed"}, "decision_point": "sample_plan"}


def http_policy(url, **extra):
    return {"backend": "http", "url": url, "model": "m", **extra}


# ------------------------------------------------------------------------------------------ F2: no destination checks
def test_run_with_url_outside_the_allowlist_is_refused_before_any_request(client, project, internal_server, monkeypatch):
    url, srv = internal_server
    monkeypatch.setenv("JEV_ALLOWED_HOSTS", "jev.example.org")
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(url)})
    assert r.status_code in (400, 403, 422)
    assert srv.hits == [], "the service already sent a request to a host that is not on the allowlist"


def test_internal_response_body_is_not_reflected_to_the_client(client, project, internal_server):
    url, srv = internal_server
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(url + "/admin")})
    assert "SECRET-FROM-INTERNAL-SERVICE" not in r.text


def test_credentials_in_url_are_refused_or_hidden(client, project, internal_server):
    url, _ = internal_server
    dirty = url.replace("http://", "http://svc:hunter2@")
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(dirty)})
    assert "hunter2" not in r.text


@pytest.mark.parametrize("url", ["http://127.0.0.1:9", "http://localhost:9", "http://10.0.0.5", "http://192.168.1.1", "http://169.254.169.254/latest/meta-data",
                                 "http://[::1]:9", "http://[fd00::1]", "http://0.0.0.0:9", "http://2130706433/", "http://metadata.google.internal"])
def test_backend_refuses_non_public_destinations(url, monkeypatch):
    """The destination check lives in ``service.security`` (``check_jev_url``, called before ``jev.prepare`` builds a backend):
    nothing is on the allowlist by default, and link-local / cloud-metadata addresses stay refused even when listed."""
    from service import security
    monkeypatch.delenv("JEV_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError):
        security.check_jev_url(url)          # nothing is resolved or sent for an unlisted host
    host = url.split("://", 1)[1].split("/", 1)[0]
    monkeypatch.setenv("JEV_ALLOWED_HOSTS", host)
    if host.startswith(("169.254.", "metadata")):
        with pytest.raises(ValueError):
            security.check_jev_url(url)      # listed, still refused: cloud metadata


def test_redirects_are_not_followed(client, project):
    """Safe today: http.client never follows a 3xx, so an allowed host cannot bounce the service to an internal one."""
    target = ThreadingHTTPServer(("127.0.0.1", 0), _quiet(lambda h: h.send_response(200) or h.end_headers()))
    target.hits = []
    threading.Thread(target=target.serve_forever, daemon=True).start()

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_address[1]}/pwned")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_POST = do_GET

        def log_message(self, *a):
            pass

    hop = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=hop.serve_forever, daemon=True).start()
    seen = []
    orig = target.RequestHandlerClass.do_GET
    target.RequestHandlerClass.do_GET = lambda h: (seen.append(h.path), orig(h))[1]
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60,
                                                         "decision_policy": http_policy(f"http://127.0.0.1:{hop.server_address[1]}")})
    assert r.status_code == 422
    assert seen == [], "the redirect target was contacted"
    hop.shutdown(); target.shutdown()


def _quiet(fn):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            fn(self)

        do_POST = do_GET

        def log_message(self, *a):
            pass
    return H


# ------------------------------------------------------------------------------------------ F5: sizes and timeouts
def test_oversized_jev_response_is_cut_off():
    big = 40 * 1024 * 1024

    class Flood(BaseHTTPRequestHandler):
        sent = 0

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(big))
            self.end_headers()
            chunk = b" " * 65536
            try:
                for _ in range(big // len(chunk)):
                    self.wfile.write(chunk)
                    Flood.sent += len(chunk)
            except OSError:
                pass

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Flood)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b = HttpBackend(f"http://127.0.0.1:{srv.server_address[1]}", timeout=10, retries=0)
    try:
        b.info()
    except Exception:
        pass
    srv.shutdown()
    # What the server managed to write is the client's reading plus the kernel's socket buffers (a few MiB on loopback);
    # the unlimited client took all 40 MiB.
    assert Flood.sent < 8 * 1024 * 1024, f"the client read {Flood.sent // 1024} KiB of an answer that should have been cut off at about 1 MiB"


def test_slow_drip_jev_response_hits_a_wall_clock_deadline():
    """A server that sends one byte just inside the socket timeout would restart it forever; the call has a total deadline."""
    class Drip(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "100000")
            self.end_headers()
            try:
                for _ in range(100000):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.2)
            except OSError:
                pass

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Drip)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b = HttpBackend(f"http://127.0.0.1:{srv.server_address[1]}", timeout=1, retries=0)
    t = time.time()
    try:
        b.info()
    except Exception:
        pass
    took = time.time() - t
    srv.shutdown()
    assert took < 3.0, f"a dripping JEV held the call for {took:.1f}s although the timeout is 1 s"


def test_client_cannot_choose_a_long_jev_timeout(client, project, allow_jev):
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(8)
    url = f"http://127.0.0.1:{silent.getsockname()[1]}"
    allow_jev(url)                 # allowed host: what is under test is the time the service waits for it
    t = time.time()
    client.post(f"/api/projects/{project}/decide", json={**DECIDE, "decision_policy": http_policy(url, timeout=2.5)})
    took = time.time() - t
    silent.close()
    assert took < 2.0, f"the request was held for {took:.1f}s because the client asked for a 2.5 s timeout (and the call is retried once)"


def test_slow_jev_calls_cannot_stall_the_whole_api():
    """The child process allows its own silent local server through ``JEV_ALLOWED_HOSTS`` (it sets it itself)."""
    import subprocess
    import sys
    from pathlib import Path
    here = Path(__file__).resolve().parent
    p = subprocess.run([sys.executable, "-W", "ignore", str(here / "sec_stall_child.py")], capture_output=True, text=True, timeout=60,
                       cwd=here.parent.parent, env={**__import__("os").environ, "PYTHONPATH": str(here.parent.parent)})
    health = float(p.stdout.strip().splitlines()[-1])
    assert health < 1.0, f"/api/health took {health:.1f}s while 48 JEV calls were hanging"


# ------------------------------------------------------------------------------------------ F4: errors become 500
def test_decide_with_unreachable_jev_is_a_client_error(client, project, allow_jev):
    allow_jev("127.0.0.1:1")
    r = client.post(f"/api/projects/{project}/decide", json={**DECIDE, "decision_policy": http_policy("http://127.0.0.1:1", timeout=0.2)})
    assert r.status_code in (400, 422, 502, 503, 504), r.status_code


@pytest.mark.parametrize("policy", [{"backend": 5}, {"backend": None}, {"backend": ["http"]}, {"backend": "http", "url": 5}, {"backend": "http", "url": ["x"]}])
@pytest.mark.parametrize("where", ["decide", "runs"])
def test_wrong_typed_decision_policy_is_a_422(client, project, policy, where):
    body = {**DECIDE, "decision_policy": policy} if where == "decide" else {"flowchart": {"id": "observed"}, "n": 60, "decision_policy": policy}
    r = client.post(f"/api/projects/{project}/{where}", json=body)
    assert r.status_code == 422, (r.status_code, r.text[:100])


# ------------------------------------------------------------------------------------------ what is safe
def test_http_backend_only_talks_to_the_named_host_and_two_paths(client, project, internal_server):
    """The service never forwards its own request headers or the caller's data to the JEV URL."""
    url, srv = internal_server
    srv.status, srv.body = 200, b'{"models": [{"id": "m", "context_fields": null, "deterministic": false}]}'
    client.post(f"/api/projects/{project}/decide", json={**DECIDE, "decision_policy": http_policy(url, timeout=1)},
                headers={"Authorization": "Bearer caller-secret", "Cookie": "session=caller-cookie"})
    assert srv.hits, "expected the JEV to be called"
    for _m, path, headers, _body in srv.hits:
        assert path in ("/v1/models", "/v1/decide")
        assert "caller-secret" not in str(headers) and "caller-cookie" not in str(headers)

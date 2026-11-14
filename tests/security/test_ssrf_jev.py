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
@pytest.mark.xfail(strict=True, reason="F2: JEV_ALLOWED_HOSTS is not implemented; the service calls any host a client names")
def test_run_with_url_outside_the_allowlist_is_refused_before_any_request(client, project, internal_server, monkeypatch):
    url, srv = internal_server
    monkeypatch.setenv("JEV_ALLOWED_HOSTS", "jev.example.org")
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(url)})
    assert r.status_code in (400, 403, 422)
    assert srv.hits == [], "the service already sent a request to a host that is not on the allowlist"


@pytest.mark.xfail(strict=True, reason="F2: the first 300 bytes of whatever an internal host answers are echoed back in the 422 message")
def test_internal_response_body_is_not_reflected_to_the_client(client, project, internal_server):
    url, srv = internal_server
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(url + "/admin")})
    assert "SECRET-FROM-INTERNAL-SERVICE" not in r.text


@pytest.mark.xfail(strict=True, reason="F2: user:password@ in the URL is accepted and then repeated in error messages")
def test_credentials_in_url_are_refused_or_hidden(client, project, internal_server):
    url, _ = internal_server
    dirty = url.replace("http://", "http://svc:hunter2@")
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "decision_policy": http_policy(dirty)})
    assert "hunter2" not in r.text


@pytest.mark.xfail(strict=True, reason="F2: loopback, private, link-local (cloud metadata) and IPv6 addresses all pass URL parsing")
@pytest.mark.parametrize("url", ["http://127.0.0.1:9", "http://localhost:9", "http://10.0.0.5", "http://192.168.1.1", "http://169.254.169.254/latest/meta-data",
                                 "http://[::1]:9", "http://[fd00::1]", "http://0.0.0.0:9", "http://2130706433/", "http://metadata.google.internal"])
def test_backend_refuses_non_public_destinations(url):
    with pytest.raises(ValueError):
        HttpBackend(url)          # the constructor only parses; nothing is sent


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
@pytest.mark.xfail(strict=True, reason="F5: the response is read whole with no size limit (an oversized JEV answer is held in memory)")
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
    assert Flood.sent < 2 * 1024 * 1024, f"the client read {Flood.sent // 1024} KiB of an answer that should have been cut off at about 1 MiB"


@pytest.mark.xfail(strict=True, reason="F5: the client chooses the timeout; /decide waits for it in an API worker thread")
def test_client_cannot_choose_a_long_jev_timeout(client, project):
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(8)
    url = f"http://127.0.0.1:{silent.getsockname()[1]}"
    t = time.time()
    client.post(f"/api/projects/{project}/decide", json={**DECIDE, "decision_policy": http_policy(url, timeout=2.5)})
    took = time.time() - t
    silent.close()
    assert took < 2.0, f"the request was held for {took:.1f}s because the client asked for a 2.5 s timeout (and the call is retried once)"


@pytest.mark.xfail(strict=True, reason="F5: enough slow /decide calls occupy every API worker thread, and even /api/health stops answering")
def test_slow_jev_calls_cannot_stall_the_whole_api():
    import subprocess
    import sys
    from pathlib import Path
    here = Path(__file__).resolve().parent
    p = subprocess.run([sys.executable, "-W", "ignore", str(here / "sec_stall_child.py")], capture_output=True, text=True, timeout=60,
                       cwd=here.parent.parent, env={**__import__("os").environ, "PYTHONPATH": str(here.parent.parent)})
    health = float(p.stdout.strip().splitlines()[-1])
    assert health < 1.0, f"/api/health took {health:.1f}s while 48 JEV calls were hanging"


# ------------------------------------------------------------------------------------------ F4: errors become 500
@pytest.mark.xfail(strict=True, reason="F4: an unreachable JEV makes /decide answer 500 (BackendError is not caught there)")
def test_decide_with_unreachable_jev_is_a_client_error(client, project):
    r = client.post(f"/api/projects/{project}/decide", json={**DECIDE, "decision_policy": http_policy("http://127.0.0.1:1", timeout=0.2)})
    assert r.status_code in (400, 422, 502, 503, 504), r.status_code


@pytest.mark.xfail(strict=True, reason="F4: a decision_policy whose backend or url has the wrong type is a 500, not a 422")
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

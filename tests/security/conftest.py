"""Fixtures for the security review tests; helpers live in ``sec_helpers``."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sec_helpers import make_client, new_project


@pytest.fixture
def client(tmp_path):
    with make_client(tmp_path) as c:
        yield c


@pytest.fixture
def project(client):
    return new_project(client)


class _Recorder(BaseHTTPRequestHandler):
    """A local stand-in for an 'internal service' that a JEV URL could be pointed at."""
    body = b'{"internal":"SECRET-FROM-INTERNAL-SERVICE"}'

    def _answer(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.server.hits.append((self.command, self.path, dict(self.headers), self.rfile.read(n) if n else b""))
        self.send_response(self.server.status)
        self.send_header("Content-Length", str(len(self.server.body)))
        self.end_headers()
        self.wfile.write(self.server.body)

    do_GET = do_POST = _answer

    def log_message(self, *a):
        pass


@pytest.fixture
def allow_jev(monkeypatch):
    """``allow_jev(url_or_hostport, ...)``: put these local stand-in servers on this test's JEV allowlist (the operator's
    ``JEV_ALLOWED_HOSTS``). Without it every http decision policy is refused, which is the hosted default."""
    def allow(*urls):
        hosts = [u.split("://", 1)[-1].split("/", 1)[0] for u in urls]
        monkeypatch.setenv("JEV_ALLOWED_HOSTS", ",".join(hosts))
    return allow


@pytest.fixture
def internal_server(allow_jev):
    """``(url, server)``: records every request it receives (``server.hits``) and answers ``server.status`` / ``server.body``.
    Its address is on the JEV allowlist, so what the tests check is what the service does with an *allowed* host."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    srv.hits, srv.status, srv.body = [], 404, _Recorder.body
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    allow_jev(f"127.0.0.1:{srv.server_address[1]}")
    yield f"http://127.0.0.1:{srv.server_address[1]}", srv
    srv.shutdown()

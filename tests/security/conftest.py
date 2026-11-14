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
def internal_server():
    """``(url, server)``: records every request it receives (``server.hits``) and answers ``server.status`` / ``server.body``."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    srv.hits, srv.status, srv.body = [], 404, _Recorder.body
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", srv
    srv.shutdown()

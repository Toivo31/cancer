"""Serve a backend (by default the stub) over the JEV HTTP contract, so the whole network path can
be tested before the real JEV exists.

    python -m jev.stub_server --scenario scenarios/finland_lung.yaml --flowchart baseline --port 8100
    python -m jev.stub_server --table table.json --port 8100        # {"points": {...}} or the points

Endpoints: ``GET /v1/health``, ``GET /v1/models``, ``POST /v1/decide``. Standard library only.
Errors are JSON: ``{"error": {"code": "...", "message": "..."}}``.
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .contract import BackendInfo, ContractError, DecisionBackend, check_responses, decode_request, encode_response

MAX_BODY = 8 * 1024 * 1024
MAX_BATCH = 5000


def _handler(backend: DecisionBackend, state: dict):
    info: BackendInfo = backend.info()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"               # keep-alive

        def setup(self):
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        def log_message(self, fmt, *args):          # quiet
            pass

        def _send(self, status: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _err(self, status: int, code: str, message: str):
            self._send(status, {"error": {"code": code, "message": message}})

        def do_GET(self):
            if self.path == "/v1/health":
                self._send(200, {"status": "ok"})
            elif self.path == "/v1/models":
                self._send(200, {"models": [{"id": info.model, "created": state.get("created"), "trained_on": None,
                                             "deterministic": info.deterministic, "context_fields": info.context_fields,
                                             "kind": info.name}]})
            else:
                self._err(404, "not_found", f"no such endpoint {self.path}")

        def do_POST(self):
            if self.path != "/v1/decide":
                return self._err(404, "not_found", f"no such endpoint {self.path}")
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._err(413, "too_large", "request body too large")
            raw = self.rfile.read(n)
            state["calls"] = state.get("calls", 0) + 1
            if state.get("delay"):
                time.sleep(state["delay"])
            if state.get("fail_next", 0) > 0:        # test hook: answer 503 this many times
                state["fail_next"] -= 1
                return self._err(503, "unavailable", "injected failure")
            try:
                body = json.loads(raw)
            except ValueError:
                return self._err(400, "bad_json", "body is not valid JSON")
            try:
                model, reqs = decode_request(body)
                if model not in (None, info.model):
                    return self._err(404, "unknown_model", f"model {model!r} is not served; try {info.model!r}")
                if len(reqs) > MAX_BATCH:
                    return self._err(413, "too_large", f"at most {MAX_BATCH} requests per call")
                resp = check_responses(reqs, backend.decide(reqs))
            except ContractError as e:
                return self._err(422, "contract", str(e))
            except Exception as e:                    # a backend bug must not kill the connection silently
                return self._err(500, "internal", f"{type(e).__name__}: {e}")
            self._send(200, encode_response(info.model, resp))

    return Handler


def make_server(backend: DecisionBackend, host: str = "127.0.0.1", port: int = 0):
    """A ``ThreadingHTTPServer`` for ``backend``; ``server.state`` holds test hooks
    (``delay`` seconds, ``fail_next`` count) and ``calls``. Port 0 picks a free port."""
    state: dict = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    srv = ThreadingHTTPServer((host, port), _handler(backend, state))
    srv.daemon_threads = True
    srv.state = state
    return srv


def serve_in_thread(backend: DecisionBackend, host: str = "127.0.0.1", port: int = 0):
    srv = make_server(backend, host, port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://{host}:{srv.server_address[1]}"


def main(argv=None) -> None:
    from pathway_sim import load_scenario

    from .migrate import migrate_flowchart
    from .stub import StubBackend

    ap = argparse.ArgumentParser(prog="jev.stub_server", description=__doc__.split("\n\n")[0])
    ap.add_argument("--scenario")
    ap.add_argument("--flowchart", default="baseline")
    ap.add_argument("--table", help="JSON file with the stub table")
    ap.add_argument("--model", default="stub@1")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    a = ap.parse_args(argv)
    if bool(a.scenario) == bool(a.table):
        ap.error("give --scenario (with --flowchart) or --table")
    if a.table:
        t = json.load(open(a.table))
        stub = StubBackend(t.get("points", t), a.model)
    else:
        sc = load_scenario(a.scenario)
        fc = migrate_flowchart(sc.flowcharts[a.flowchart])
        stub = StubBackend(fc.decision_policy["points"], a.model)
        problems = stub.validate_against(fc, sc)
        if problems:
            raise SystemExit("; ".join(problems))
    srv = make_server(stub, a.host, a.port)
    print(f"JEV stub '{a.model}' serving {len(stub.points)} decision points on http://{a.host}:{srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

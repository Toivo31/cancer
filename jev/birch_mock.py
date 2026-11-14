"""A local stand-in for the proxy's ``POST /api/decision/pathway`` (tests and the offline demo).

Answers in the format recorded in ``decision_api/web/precomputed.json`` (``questions[0].choices[].score``,
``proposed_action_id``, ``score_margin``, ``latency_ms``, ``backend``) with scores that are a fixed function
of the option ids, so it is deterministic. Its ``backend.mode`` is ``mock``: it is never mistaken for the model
(the backend refuses it, and never caches it, unless told to allow non-model answers). It checks what the
real endpoint checks: evidence from a later step is dropped and never reported as visible.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOCK_BACKEND = {"mode": "mock", "model": "local-mock-of-the-recorded-format", "step": 1138}


def _weight(case_text: str, action_id: str) -> float:
    h = hashlib.sha256((case_text + "|" + action_id).encode()).digest()
    return 1.0 + h[0] / 64.0


def propose(body: dict) -> dict:
    case, wf, node_id = body["case"], body["workflow"], body["node_id"]
    node = wf["nodes"][node_id]
    step = case["step"]
    visible = [e for e in case["evidence"] if e["available_at_step"] <= step]
    basis = case["context"] + "".join(e["text"] for e in visible)
    w = {a["id"]: _weight(basis, a["id"]) for a in node["actions"]}
    tot = sum(w.values())
    choices = [{"id": a["id"], "text": a["description"], "score": w[a["id"]] / tot} for a in node["actions"]]
    ranked = sorted(choices, key=lambda c: (-c["score"], c["id"]))
    margin = ranked[0]["score"] - (ranked[1]["score"] if len(ranked) > 1 else 0.0)
    return {"id": hashlib.md5(json.dumps(body, sort_keys=True).encode()).hexdigest(), "case_id": case["case_id"],
            "backend": dict(MOCK_BACKEND), "score_kind": "candidate_softmax", "requires_review": True,
            "questions": [{"id": node_id, "text": node["question"], "candidate_format": "newline", "choices": choices,
                           "proposed_action_id": ranked[0]["id"], "score_margin": margin}],
            "latency_ms": 1.0,
            "pathway": {"workflow_id": wf["id"], "workflow_version": wf["version"], "node_id": node_id, "step": step,
                        "visible_source_ids": [e["source_id"] for e in visible],
                        "allowed_next_nodes": {a["id"]: a["next"] for a in node["actions"]}},
            "proposed_next_node_id": next(a["next"] for a in node["actions"] if a["id"] == ranked[0]["id"])}


class MockProxy:
    """``with MockProxy() as m: BirchBackend(m.url, allow_non_model=True)``. ``m.bodies`` are the raw requests;
    ``m.status`` (an HTTP status other than 200) and ``m.delay`` (seconds) make it fail on purpose."""

    def __init__(self, status: int = 200, delay: float = 0.0, detail: str = "Model may still be starting. Retry shortly."):
        self.status, self.delay, self.detail = status, delay, detail
        self.bodies: list[dict] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                outer.bodies.append(body)
                if outer.delay:
                    time.sleep(outer.delay)
                if outer.status != 200:
                    out, code = {"detail": outer.detail}, outer.status
                else:
                    out, code = propose(body), 200
                data = json.dumps(out).encode()
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._t = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self.server.shutdown()
        self.server.server_close()

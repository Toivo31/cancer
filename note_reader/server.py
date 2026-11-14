"""Note reader demo server (standard library only).

    .venv/bin/python -m note_reader.server            # http://127.0.0.1:8770
    .venv/bin/python -m note_reader.server --precompute   # refresh note_reader/precomputed.json

GET  /                 the page (note_reader/index.html)
GET  /api/examples     synthetic example notes
POST /api/read         {"text": "..."} -> flags (checked against the text) + next-step estimates

API key from .env (LLM_* or VERDA_*). If the LLM call fails for one of the example notes, the
precomputed result is served and marked as such, so the live demo still works offline.
Synthetic notes only: never paste real patient data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from technique_classifier import load_taxonomy  # noqa: E402
from technique_classifier.llm import classify  # noqa: E402
from note_reader.next_step import next_step  # noqa: E402

PRE = HERE / "precomputed.json"
MAX_CHARS = 2000


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def key(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:16]


def names() -> dict:
    return {t["id"]: t["name"] for t in load_taxonomy("clinical_notes")["techniques"]}


def read_note(text: str) -> dict:
    t0 = time.time()
    verdict, problems = classify(text, "clinical_notes", key(text))
    d = verdict.to_dict()
    nm = names()
    for f in d["flags"]:
        f["name"] = nm.get(f["technique_id"], f["technique_id"])
    return {"text": text, "verdict": d, "dropped": problems, "next": next_step(text, d["flags"]),
            "model": os.environ.get("LLM_MODEL") or os.environ.get("VERDA_MODEL", ""), "seconds": round(time.time() - t0, 1)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/examples":
            self._send(200, (HERE / "examples.json").read_bytes(), "application/json")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/read":
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
            text = (req.get("text") or "").strip()
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "send JSON {\"text\": ...}"})
        if not text or len(text) > MAX_CHARS:
            return self._json(400, {"error": f"text must be 1-{MAX_CHARS} characters"})
        if req.get("stored"):  # instant answer for the example notes (stored from an earlier live run)
            pre = json.loads(PRE.read_text()) if PRE.exists() else {}
            if key(text) in pre:
                out = dict(pre[key(text)]); out["precomputed"] = True
                return self._json(200, out)
        try:
            return self._json(200, read_note(text))
        except Exception as e:  # noqa: BLE001 - fall back to a stored result for example notes
            pre = json.loads(PRE.read_text()) if PRE.exists() else {}
            if key(text) in pre:
                out = dict(pre[key(text)]); out["precomputed"] = True; out["error"] = str(e)[:200]
                return self._json(200, out)
            return self._json(502, {"error": f"LLM call failed: {str(e)[:200]}"})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def precompute() -> None:
    ex = json.loads((HERE / "examples.json").read_text())
    out = {}
    for e in ex:
        r = read_note(e["text"])
        out[key(e["text"])] = r
        print(f"{e['id']:<22} {len(r['verdict']['flags'])} flags {[f['technique_id'] for f in r['verdict']['flags']]}"
              f" dropped={len(r['dropped'])} {r['seconds']}s")
    PRE.write_text(json.dumps(out, indent=1))
    print("wrote", PRE)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--precompute", action="store_true")
    a = ap.parse_args(argv)
    load_env(ROOT / ".env")
    if a.precompute:
        return precompute()
    print(f"note reader on http://{a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

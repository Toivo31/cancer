#!/usr/bin/env python3
"""Optional: serve demo/ and the local decision proxy on one origin.

You do not need this to score live: demo/jev.html calls the team's hosted gateway straight from the browser by default
(the gateway sends Access-Control-Allow-Origin: *, holds the model key itself, and needs no install). Open the file, pick
an example, press "Score live". Use this server only to route calls through the local proxy instead:

    python demo/serve_jev.py                 # http://127.0.0.1:8772/jev.html ; choose "This server's /api/decision"
    python demo/serve_jev.py --fixture       # scripted fixture answers (the page labels them "not the model")

The local proxy (decision_api.server) refuses calls from other origins (a page opened from disk is one), which is why
the page and the proxy share this origin. Without a local key the proxy relays to the hosted gateway (on main).
Standard library only; it binds to 127.0.0.1.
"""
from __future__ import annotations

import argparse
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from decision_api.server import handle_request  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/decision/"):
            handle_request(self)
            return
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/jev.html")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if not (self.path.startswith("/api/decision/") and handle_request(self)):
            self.send_error(404)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--fixture", action="store_true", help="scripted fixture answers instead of the model")
    a = ap.parse_args(argv)
    if a.fixture:
        os.environ["BIRCH_DECISION_MODE"] = "fixture"
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), partial(Handler, directory=str(HERE)))
    print(f"JEV page on http://127.0.0.1:{a.port}/jev.html (live calls: choose \"This server's /api/decision\")", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

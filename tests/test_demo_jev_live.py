"""Live path of the JEV page (demo/jev.html): the page calls the team's hosted gateway straight from the browser.

The gateway itself is not called here. ``MockGateway`` follows the protocol of decision_api/hosted.py (on main) and
HOSTED_API.md: CORS ``*`` on every answer and on the preflight, quick results as 200, longer ones as a 202 job polled at
``/jobs/{id}``, 429 when busy, 404 for a lost job, 422 for a request over the demo budget. Its answers are labelled
mode "fixture", so nothing it returns can pass for the model.

Checks: the bundle carries the gateway's limits (and they match decision_api/hosted.py when that file is in the
checkout); the page defaults to the hosted gateway but sends nothing on load; ``export_jev.py --record`` stops at a busy
gateway and exits non-zero; and, when headless Chrome and Playwright are installed, the page in a browser goes through
waiting, answer and busy states against the mock from a file:// URL."""
import json
import re
import shutil
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
sys.path.insert(0, str(DEMO))
JS = (DEMO / "jev.js").read_text(encoding="utf-8")


def bundle() -> dict:
    t = (DEMO / "data" / "jev_bundle.js").read_text(encoding="utf-8")
    return json.loads(re.match(r"window\.JEV_DATA = (.*);\s*$", t, re.S).group(1))


# ------------------------------------------------------------------------------------------------ mock gateway

class MockGateway:
    """Stdlib stand-in for the hosted gateway's public protocol (decision_api/hosted.py)."""

    def __init__(self, delay=0.0, per_minute=6, outstanding=3):
        self.delay, self.per_minute, self.outstanding = delay, per_minute, outstanding
        self.jobs, self.starts, self.posts, self.lock, outer = {}, [], [], threading.Lock(), self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj, extra=()):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Access-Control-Allow-Origin", "*")
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(b)

            def do_OPTIONS(self):                       # CORS preflight, as Starlette's CORSMiddleware answers it
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
                outer.posts.append((self.path, body))
                target = body.get("request", body)
                ctx = target.get("case", {}).get("context", target.get("context", ""))
                qs = target.get("questions", [])
                if len(json.dumps(target)) > 32000 or len(ctx) > 12000 or len(qs) > 4 or any(len(q.get("choices", [])) > 8 for q in qs):
                    return self._send(422, {"detail": "Invalid demo request or context/question budget exceeded"})
                now = time.time()
                with outer.lock:
                    active = sum(j["done_at"] > now for j in outer.jobs.values())
                    if active >= outer.outstanding or sum(now - t < 60 for t in outer.starts) >= outer.per_minute:
                        return self._send(429, {"detail": "Demo busy; wait before submitting another request"}, [("Retry-After", "60")])
                    outer.starts.append(now)
                    jid = uuid.uuid4().hex
                    outer.jobs[jid] = {"done_at": now + outer.delay, "result": outer.answer(self.path, target)}
                if outer.delay < 0.5:
                    return self._send(200, outer.jobs[jid]["result"])
                self._send(202, {"delivery": "pending", "job_id": jid, "status_url": "/jobs/" + jid}, [("Retry-After", "1")])

            def do_GET(self):
                m = re.match(r"^/api/decision/jobs/(\w+)$", self.path)
                job = m and outer.jobs.get(m.group(1))
                if not job:
                    return self._send(404, {"detail": "Job expired; do not automatically resubmit scoring"})
                if job["done_at"] > time.time():
                    return self._send(202, {"delivery": "pending", "job_id": m.group(1), "status_url": "/jobs/" + m.group(1)})
                self._send(200, job["result"])

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/api/decision"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @staticmethod
    def answer(route, target):
        if "workflow" in target:
            n = target["workflow"]["nodes"][target["node_id"]]
            qs = [{"id": target["node_id"], "text": n["question"], "choices": [{"id": a["id"], "text": a["description"]} for a in n["actions"]]}]
        else:
            qs = target.get("questions", [])
        dec = {"id": uuid.uuid4().hex, "created_at": "2000-01-01T00:00:00+00:00", "requires_review": True,
               "backend": {"mode": "fixture", "model": "mock gateway (not the model)", "step": None},
               "questions": [{"id": q["id"], "text": q["text"], "proposed_action_id": q["choices"][0]["id"],
                              "choices": [dict(c, score=1 / len(q["choices"])) for c in q["choices"]]} for q in qs]}
        return {"decision": dec} if route.endswith("/reason") else dec

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


# ------------------------------------------------------------------------------------------------ data and script

def test_bundle_carries_the_gateway_limits():
    g = bundle()["model"]["gateway"]
    for k in ("per_minute", "per_hour", "outstanding", "window_seconds", "hour_seconds", "retry_after_seconds",
              "poll_seconds", "overall_seconds", "max_body", "max_context"):
        assert isinstance(g[k], (int, float)) and g[k] > 0, k
    assert g["statuses"]["429"] == "busy" and g["statuses"]["404"] == "expired" and g["statuses"]["202"] == "pending"


def test_gateway_limits_match_hosted_py_when_present():
    src = ROOT / "decision_api" / "hosted.py"
    if not src.exists():
        pytest.skip("decision_api/hosted.py is not in this checkout yet (it is on main)")
    t, g = src.read_text(encoding="utf-8"), bundle()["model"]["gateway"]
    assert f"len(starts)>={g['per_hour']}" in t and f"now-t<{g['window_seconds']} for t in starts)>={g['per_minute']}" in t
    assert f"active>={g['outstanding']}" in t
    assert f"len(json.dumps(target))>{g['max_body']}" in t and f"len(context)>{g['max_context']}" in t
    assert "allow_origins=['*']" in t                    # the page relies on this to call it from any page


def test_page_defaults_to_the_hosted_gateway_and_sends_nothing_on_load():
    assert re.search(r'else mode\.value = "hosted";', JS)
    assert 'var HOSTED_API = "https://' in JS and "/api/decision" in JS
    # the only fetches are the POST and the job poll inside live(); live() is reached from click handlers only
    body = JS[JS.index("function live("):JS.index("// ====", JS.index("function live("))]
    assert JS.count("fetch(") == body.count("fetch(") == 2
    assert "/health" not in JS                           # no health polling (owner's rule)


def test_page_guard_and_states_use_the_gateway_facts():
    for k in ("G.per_minute", "G.per_hour", "G.outstanding", "G.retry_after_seconds", "G.overall_seconds",
              "G.poll_seconds", "G.max_body", "G.max_context"):
        assert k in JS, k
    for state in ('"sending"', '"pending"', '"busy"', 'kind === "expired"', 'kind === "refused"', 'kind === "unavailable"'):
        assert state in JS, state
    assert "not resent" in JS or "does not resend" in JS


# ------------------------------------------------------------------------------------------------ --record

def test_record_stops_at_a_busy_gateway_and_fails(tmp_path, monkeypatch):
    import export_jev
    monkeypatch.setattr(export_jev, "PRESET_OUTPUTS", tmp_path / "outs.json")
    gw = MockGateway(per_minute=1)
    try:
        items = [p for p in export_jev.presets(None, None) if p["key"] in ("triage", "screening", "compare")]
        out = export_jev.record_presets(gw.url, items, allow_non_model=False)
    finally:
        gw.close()
    assert len(gw.posts) == 2                            # one answered (fixture: not stored), one refused busy, then stop
    assert set(out["failed"]) == {"triage", "screening", "compare"} and not out["outputs"]


def test_record_polls_a_job(tmp_path, monkeypatch):
    import export_jev
    monkeypatch.setattr(export_jev, "PRESET_OUTPUTS", tmp_path / "outs.json")
    gw = MockGateway(delay=1.2)
    try:
        items = [p for p in export_jev.presets(None, None) if p["key"] == "triage"]
        out = export_jev.record_presets(gw.url, items, allow_non_model=True)
    finally:
        gw.close()
    assert len(gw.posts) == 1 and out["outputs"]["triage"]["response"]["backend"]["mode"] == "fixture"


# ------------------------------------------------------------------------------------------------ in a browser

def _chrome():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return None
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


@pytest.mark.skipif(not _chrome(), reason="needs Playwright and a local Chrome")
def test_page_scores_live_from_a_file_url():
    from playwright.sync_api import sync_playwright
    gw = MockGateway(delay=1.5, per_minute=3)
    page_url = (DEMO / "jev.html").as_uri() + "?api=" + gw.url + "#triage"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=_chrome(), args=["--no-sandbox", "--no-proxy-server"])
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            errs, nonfile = [], []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("request", lambda r: r.url.startswith("file:") or nonfile.append(r.url))
            pg.goto(page_url)
            pg.wait_for_timeout(300)
            assert nonfile == []                         # nothing is sent until a button is pressed
            pg.click("#work .jev-run")
            pg.wait_for_selector("#work .jev-wait", timeout=5000)
            assert "Job accepted" in pg.inner_text("#work .jev-wait") or "Sending" in pg.inner_text("#work .jev-wait")
            pg.wait_for_selector("#work .jev-col.out .jev-prov", timeout=15000)
            assert "NOT THE MODEL" in pg.inner_text("#work .jev-col.out .jev-prov").upper()
            pg.click("#tab-screening")
            pg.click("#work .jev-run")                   # second call this minute: allowed by the page, sent
            pg.wait_for_function("!document.querySelector('#work .jev-wait')", timeout=15000)
            gw.starts.append(time.time())                # another visitor takes the last slot
            pg.click("#tab-compare")
            pg.click("#work .jev-run")
            pg.wait_for_selector("#work .jev-busy", timeout=5000)
            assert pg.eval_on_selector("#work .jev-run", "e => e.disabled")
            assert "busy" in pg.inner_text("#ep-status").lower()
            assert errs == []
            b.close()
    finally:
        gw.close()
    assert len(gw.posts) == 3                            # two answered; the busy one refused before any job; none resent

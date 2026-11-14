"""The JEV node page (demo/jev.html, demo/jev.js, demo/data/jev_bundle.js, demo/export_jev.py).

Checks: links and assets exist, no result is typed into the page, the bundle's requests fit the deployed contract and
carry no hidden-side text, recorded outputs are the model's own and labelled, and --record keeps only model answers."""
import json
import re
import sys
import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
sys.path.insert(0, str(DEMO))
PAGE = DEMO / "jev.html"


def bundle() -> dict:
    t = (DEMO / "data" / "jev_bundle.js").read_text(encoding="utf-8")
    m = re.match(r"window\.JEV_DATA = (.*);\s*$", t, re.S)
    assert m, "jev_bundle.js must be `window.JEV_DATA = {...};`"
    return json.loads(m.group(1))


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.assets, self.text, self._skip, self._code = [], [], [], 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self._skip += 1
            if a.get("src"):
                self.assets.append(a["src"])
        if tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        if tag == "code":
            self._code += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self._skip -= 1
        if tag == "code" and self._code:
            self._code -= 1

    def handle_data(self, d):
        if not self._skip and not self._code:
            self.text.append(d)


def parsed():
    p = P()
    p.feed(PAGE.read_text(encoding="utf-8"))
    return p


def test_links_and_assets_exist():
    p = parsed()
    for ref in p.links + p.assets:
        path = urlsplit(ref).path
        assert path and (DEMO / path).resolve().exists(), f"missing target: {ref}"


def test_linked_from_start_page():
    assert 'href="jev.html"' in (DEMO / "start.html").read_text(encoding="utf-8")


def test_no_number_typed_into_page_text():
    text = " ".join(parsed().text)
    assert not re.search(r"\d", text), re.findall(r".{20}\d.{20}", text)


def test_script_has_no_hand_typed_results():
    js = (DEMO / "jev.js").read_text(encoding="utf-8")
    code = re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S), flags=re.M)
    code = re.sub(r"//[^\n\"]*$", "", code, flags=re.M)
    nums = set(re.findall(r"(?<![\w.$#])\d+(?:\.\d+)?(?![\w])", re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)))
    # formatting, timing and protocol constants only (polling interval, 11-minute limit, HTTP 202, token budget)
    assert nums <= {"0", "1", "2", "3", "4", "9", "10", "16", "100", "128", "202", "1000", "660000"}, nums


def test_hugging_face_link_is_one_constant():
    js = (DEMO / "jev.js").read_text(encoding="utf-8")
    assert len(re.findall(r"^\s*var HF_URL = ", js, re.M)) == 1


def test_bundle_presets_fit_the_contract():
    d = bundle()
    assert d["format"] == "jev-bundle/1"
    keys = [p["key"] for p in d["presets"]]
    assert {"reasoning", "triage", "screening", "compare"} <= set(keys)
    assert [p["key"] for p in d["presets"] if p.get("default")] in (["gp_visit"], [])
    gw = d["model"]["max_choices_gateway"]
    for p in d["presets"]:
        assert p["route"] in ("/score", "/pathway", "/reason")
        for q in p["questions"]:
            ids = [c["id"] for c in q["choices"]]
            assert 2 <= len(ids) <= gw and len(set(ids)) == len(ids), (p["key"], q["id"])
        if p["route"] == "/score":
            r = p["request"]
            assert set(r) <= {"context", "case_id", "questions", "image_ids"} and len(r["questions"]) <= d["model"]["max_questions_gateway"]
            assert len(r["context"]) <= 12000 and len(json.dumps(r)) <= 32000
    cmp_ = next(p for p in d["presets"] if p["key"] == "compare")
    assert len(cmp_["questions"]) == 2      # two questions share one context


def test_gp_visit_is_a_real_node_without_hidden_side():
    d = bundle()
    gp = next((p for p in d["presets"] if p["key"] == "gp_visit"), None)
    if gp is None:
        pytest.skip("bundle built without the encounter bundle")
    g, req = gp["gp"], gp["request"]
    node = req["workflow"]["nodes"][req["node_id"]]
    assert req["node_id"] == "gp_encounter" and len(node["actions"]) <= d["model"]["max_choices_gateway"]
    assert set(g["table"]["probs"]) <= {a["id"] for a in node["actions"]}      # every action the table weighs is offered
    assert all(e["available_at_step"] <= req["case"]["step"] for e in req["case"]["evidence"])
    sent = json.dumps(req).lower() + g["model_text"].lower()
    cond = g["teach"]["primary"].lower()
    assert cond not in sent and cond.replace("_", " ") not in sent
    for k in ("hidden", "primary_condition", "card_id", "truth"):
        assert f'"{k}"' not in sent
    assert g["link"].startswith("encounter.html?p=")


def test_recorded_outputs_are_the_models_own():
    d = bundle()
    r = next(p for p in d["presets"] if p["key"] == "reasoning")
    rec = r["recorded"]
    assert rec["with_refinement"]["decision"]["backend"]["mode"] == "model"
    assert rec["without_refinement"]["backend"]["mode"] == "model"
    assert rec["with_refinement"]["refinement"]["trace"], "the recorded trace is what the card shows"
    assert d["model"]["backend"]["step"] == rec["with_refinement"]["decision"]["backend"]["step"]
    for p in d["presets"]:
        if p.get("recorded_preset"):
            out = p["recorded_preset"]["response"]
            assert (out.get("decision", out)["backend"]["mode"]) in ("model", "fixture", "mock")


def test_export_without_gp_visit(tmp_path):
    import export_jev
    out = tmp_path / "b.js"
    assert export_jev.main(["--skip-gp", "--out", str(out)]) == 0
    d = json.loads(re.match(r"window\.JEV_DATA = (.*);\s*$", out.read_text(), re.S).group(1))
    assert "gp_visit" not in [p["key"] for p in d["presets"]] and len(d["presets"]) >= 4


class _Fake:
    """A decision API that answers through a 202 job, as the hosted gateway does."""

    def __init__(self, mode):
        self.jobs, self.posts, outer = {}, [], self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.posts.append(body)
                qs = body.get("questions") or [{"id": "x", "text": "x", "choices": [{"id": "a", "text": "a"}, {"id": "b", "text": "b"}]}]
                dec = {"backend": {"mode": mode, "step": 1}, "questions": [
                    {"id": q["id"], "text": q["text"], "proposed_action_id": q["choices"][0]["id"],
                     "choices": [dict(c, score=1 / len(q["choices"])) for c in q["choices"]]} for q in qs]}
                j = str(len(outer.jobs))
                outer.jobs[j] = dec
                self._send(202, {"delivery": "pending", "status_url": "/jobs/" + j})

            def do_GET(self):
                self._send(200, outer.jobs[self.path.rsplit("/", 1)[-1]])

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/api/decision"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.mark.parametrize("mode,stored", [("model", True), ("mock", False)])
def test_record_keeps_only_model_answers(tmp_path, monkeypatch, mode, stored):
    import export_jev
    monkeypatch.setattr(export_jev, "PRESET_OUTPUTS", tmp_path / "outs.json")
    f = _Fake(mode)
    try:
        items = [p for p in export_jev.presets(None, None) if p["key"] == "triage"]
        out = export_jev.record_presets(f.url, items, allow_non_model=False)
    finally:
        f.close()
    assert len(f.posts) == 1                   # one explicit call per preset, no retry
    assert ("triage" in out["outputs"]) is stored


def test_serve_jev_serves_the_page():
    import urllib.request
    from functools import partial
    import serve_jev
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(serve_jev.Handler, directory=str(DEMO)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/jev.html", timeout=10) as r:
            assert r.status == 200 and b"jev.js" in r.read()
    finally:
        srv.shutdown()
        srv.server_close()

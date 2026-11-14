"""Contract tests for a JEV service (spec 02). Run against any address:

    pytest tests/test_jev_contract.py --jev-url http://host:port [--jev-model ID] [--jev-point NAME] [--jev-options a,b,c]

Without ``--jev-url`` the stub server is started in-process, so this also checks the stub.
The JEV owner runs the same file against their service.
"""

import json
import statistics
import time
import urllib.error
import urllib.request

import pytest

import jev
from jev import StubBackend
from jev.stub_server import serve_in_thread

STUB_TABLE = {"sample_method": {"default": {"bronch": 0.2, "ttnb": 0.5, "ebus": 0.3},
                                "rules": [{"when": "location == 'central'", "probs": {"bronch": 0.7, "ttnb": 0.1, "ebus": 0.2}}]}}


@pytest.fixture(scope="module")
def target(request):
    cfg = request.config
    url = cfg.getoption("--jev-url")
    srv = None
    if url is None:
        srv, url = serve_in_thread(StubBackend(STUB_TABLE))
    url = url.rstrip("/")
    point, opts = cfg.getoption("--jev-point"), cfg.getoption("--jev-options").split(",")
    models = _get(url + "/v1/models")["models"]
    assert models, "GET /v1/models lists no models"
    want = cfg.getoption("--jev-model")
    m = next((x for x in models if x["id"] == want), None) if want else models[0]
    assert m is not None, f"model {want!r} not offered: {[x['id'] for x in models]}"
    yield {"url": url, "model": m["id"], "info": m, "point": point, "options": opts}
    if srv:
        srv.shutdown()
        srv.server_close()


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def _post(url, body, raw=False):
    data = body if raw else json.dumps(body).encode()
    rq = urllib.request.Request(url + "/v1/decide", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, None


def make(target, i=0, options=None, point=None, location="peripheral", group="non_specific", age=67, result=True):
    ids = options or target["options"]
    return {
        "request_id": f"p{i}:{point or target['point']}", "decision_point": point or target["point"],
        "question_type": "next_step",
        "context": {"group": group, "age": age, "t_days": 31.5 + i, "fast_track": False,
                    "attributes": {"location": location} if location else {},
                    "history": [{"step": "gp_visit", "test": "gp_assessment", "result": True, "t_days": 13.2},
                                {"step": "ct", "test": "ct_chest", "result": result, "t_days": 30.9}]},
        "options": [{"id": o, "label": o.title(), "test": o, "features": {"invasive": True, "cost_eur": 900, "lead_days": 2.0 + k}}
                    for k, o in enumerate(ids)],
    }


def decide(target, reqs):
    status, body = _post(target["url"], {"model": target["model"], "requests": reqs})
    assert status == 200, f"POST /v1/decide returned {status}: {body}"
    return body


def test_health(target):
    assert _get(target["url"] + "/v1/health")


def test_models_entry(target):
    m = target["info"]
    assert isinstance(m["id"], str) and m["id"]
    assert m.get("context_fields") is None or isinstance(m["context_fields"], list)


def test_response_shape_and_ids(target):
    body = decide(target, [make(target, 1)])
    assert body["model"] == target["model"]
    (r,) = body["responses"]
    assert r["request_id"] == "p1:" + target["point"] and isinstance(r["probs"], dict)
    assert r.get("explanation") is None or isinstance(r["explanation"], str)


def test_probabilities_cover_exactly_the_offered_options_and_sum_to_one(target):
    ids = target["options"]
    subsets = [ids, ids[:2], ids[1:], ids[:1]] if len(ids) > 2 else [ids, ids[:1]]
    for k, sub in enumerate(subsets):
        (r,) = decide(target, [make(target, k, options=sub)])["responses"]
        assert set(r["probs"]) == set(sub), f"offered {sub}, got {list(r['probs'])}"
        assert all(isinstance(v, (int, float)) and v >= 0 for v in r["probs"].values())
        assert abs(sum(r["probs"].values()) - 1) <= jev.TOLERANCE
        jev.check_probs(r["probs"], sub)


def test_batch_order_preserved(target):
    reqs = [make(target, i, location=("central" if i % 3 else "peripheral"), age=40 + i) for i in range(60)]
    resp = decide(target, reqs)["responses"]
    assert [r["request_id"] for r in resp] == [q["request_id"] for q in reqs]
    for q, r in zip(reqs, resp):
        jev.check_probs(r["probs"], [o["id"] for o in q["options"]])


def test_batch_equals_single_calls(target):
    reqs = [make(target, i, location="central" if i % 2 else None) for i in range(6)]
    if not target["info"].get("deterministic", True):
        pytest.skip("model declares itself non-deterministic")
    batch = decide(target, reqs)["responses"]
    singles = [decide(target, [q])["responses"][0] for q in reqs]
    for b, s in zip(batch, singles):
        assert b["probs"] == pytest.approx(s["probs"], abs=1e-9)


def test_unknown_decision_point_is_handled(target):
    status, body = _post(target["url"], {"model": target["model"], "requests": [make(target, 0, point="no_such_point_xyz")]})
    if status == 200:
        (r,) = body["responses"]
        jev.check_probs(r["probs"], target["options"])
    else:
        assert 400 <= status < 500 and isinstance(body, dict) and "error" in body, f"status {status}, body {body}"


def test_context_edge_cases(target):
    empty = make(target, 0)
    empty["context"] = {"group": "g", "age": 0, "t_days": 0.0, "fast_track": True, "attributes": {}, "history": []}
    nulls = make(target, 1, result=None)
    resp = decide(target, [empty, nulls])["responses"]
    assert len(resp) == 2


def test_deterministic_when_declared(target):
    if not target["info"].get("deterministic", True):
        pytest.skip("model declares itself non-deterministic")
    q = make(target, 5)
    a = decide(target, [q])["responses"][0]["probs"]
    b = decide(target, [q])["responses"][0]["probs"]
    assert a == pytest.approx(b, abs=1e-12)


def test_malformed_requests_get_client_errors_not_server_errors(target):
    assert _post(target["url"], b"{not json", raw=True)[0] in range(400, 500)
    assert _post(target["url"], {"model": target["model"]})[0] in range(400, 500)
    bad = make(target, 0)
    bad["options"] = []
    assert _post(target["url"], {"model": target["model"], "requests": [bad]})[0] in range(400, 500)


def test_latency_report(target, request):
    reqs = [make(target, i, age=30 + i % 50) for i in range(200)]
    times = []
    for q in reqs:
        t = time.perf_counter()
        decide(target, [q])
        times.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    decide(target, reqs)
    batch_ms = (time.perf_counter() - t) * 1000
    times.sort()
    request.config._jev_latency = (f"single call over {len(times)} requests: median {statistics.median(times):.2f} ms, "
                                   f"p95 {times[int(0.95 * len(times))]:.2f} ms; one batch of {len(reqs)}: {batch_ms:.1f} ms "
                                   f"({batch_ms / len(reqs):.3f} ms per decision). A Finnish run asks about 40000 questions.")

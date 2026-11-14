"""M1-5: stub server, HttpBackend (keep-alive, cache, timeout, error modes), per-point routing."""

import json
import socket
import urllib.request

import pytest

import jev
from jev import BackendError, BackendInfo, DecisionResponse, HttpBackend, StubBackend
from jev.stub_server import serve_in_thread
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate

TABLE = {"d": {"default": {"a": 0.3, "b": 0.7}, "rules": [{"when": "group == 'x'", "probs": {"a": 1, "b": 0}}]}}


def _req(i=0, group="y", point="d"):
    return jev.DecisionRequest(f"r{i}", point, {"group": group, "age": 50, "t_days": 1.0, "attributes": {}, "history": []},
                               [{"id": "a"}, {"id": "b"}])


@pytest.fixture
def server():
    srv, url = serve_in_thread(StubBackend(TABLE))
    yield srv, url
    srv.shutdown()
    srv.server_close()


def test_endpoints_and_json_errors(server):
    srv, url = server
    assert json.load(urllib.request.urlopen(url + "/v1/health")) == {"status": "ok"}
    m = json.load(urllib.request.urlopen(url + "/v1/models"))["models"][0]
    assert m["id"] == "stub@1" and m["deterministic"] is True and "group" in m["context_fields"]
    def post(body, raw=False):
        data = body if raw else json.dumps(body).encode()
        rq = urllib.request.Request(url + "/v1/decide", data=data, headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(rq).status, None
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)["error"]["code"]
    assert post(jev.encode_request("stub@1", [_req()]))[0] == 200
    assert post(b"{nope", raw=True) == (400, "bad_json")
    assert post({"requests": "x"}) == (422, "contract")
    assert post(jev.encode_request("other@9", [_req()])) == (404, "unknown_model")
    try:
        urllib.request.urlopen(url + "/v1/nothing")
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_http_backend_answers_like_the_stub_and_caches(server):
    srv, url = server
    be = HttpBackend(url)
    stub = StubBackend(TABLE)
    qs = [_req(i, "x" if i % 2 else "y") for i in range(20)]
    got = be.decide(qs)
    assert [g.probs for g in got] == [r.probs for r in stub.decide(qs)]
    assert [g.request_id for g in got] == [q.request_id for q in qs]       # order and ids preserved
    calls = srv.state["calls"]
    be.decide(qs)                                                             # all cached
    assert srv.state["calls"] == calls and be.summary()["cache_hits"] >= 20
    assert be.info().model == "stub@1" and be.info().context_fields


def test_keep_alive_reuses_one_connection(server):
    srv, url = server
    be = HttpBackend(url, cache=False)
    for i in range(30):
        be.decide([_req(i)])
    conn = be._conn
    assert conn is not None and conn.sock is not None
    be.decide([_req(99)])
    assert be._conn is conn


def test_retry_once_then_fail_with_clear_message(server):
    srv, url = server
    be = HttpBackend(url, cache=False)
    srv.state["fail_next"] = 1
    assert be.decide([_req()])[0].probs                       # one 503, retry succeeds
    srv.state["fail_next"] = 5
    with pytest.raises(BackendError, match="did not answer"):
        be.decide([_req(1)])


def test_fallback_stub_counts_never_silent(server):
    srv, url = server
    fb = StubBackend({"d": {"default": {"a": 0.5, "b": 0.5}}}, model="fallback")
    be = HttpBackend(url, cache=True, on_error="fallback_stub", fallback=fb)
    be.decide([_req(0)])                                       # healthy, cached
    srv.state["fail_next"] = 10
    out = be.decide([_req(1, group="x"), _req(2, group="y")])  # group x not cached -> fallback for the miss
    assert out[0].probs == {"a": 0.5, "b": 0.5} and out[0].explanation == "fallback"
    s = be.summary()
    assert s["fallbacks"] >= 1 and "last_error" in s
    srv.state["fail_next"] = 0
    assert be.decide([_req(3, group="x")])[0].probs == {"a": 1.0, "b": 0.0}    # fallback answers were not cached


def test_timeout_and_unreachable():
    srv, url = serve_in_thread(StubBackend(TABLE))
    try:
        be = HttpBackend(url, timeout=0.2, cache=False)
        be.info()
        srv.state["delay"] = 0.6
        with pytest.raises(BackendError, match="did not answer"):
            be.decide([_req()])
    finally:
        srv.shutdown()
        srv.server_close()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(BackendError):
        HttpBackend(f"http://127.0.0.1:{port}").info()
    with pytest.raises(ValueError):
        HttpBackend("ftp://x")
    with pytest.raises(ValueError):
        HttpBackend(url, on_error="fallback_stub")


def test_server_that_breaks_the_contract_is_a_backend_error():
    class Bad:
        def info(self):
            return BackendInfo("bad", "bad@1")

        def decide(self, qs):
            return [DecisionResponse(q.request_id, {"a": 0.2, "b": 0.2}) for q in qs]
    srv, url = serve_in_thread(Bad())
    try:
        with pytest.raises(BackendError, match="rejected the request|contract"):
            HttpBackend(url).decide([_req()])
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.parametrize("path,fid,n", [("scenarios/stokstad.yaml", "observed", 400), ("scenarios/finland_lung.yaml", "baseline", 600)])
def test_run_through_http_equals_in_process(path, fid, n):
    sc = load_scenario(path)
    pts = generate_patients(sc, n, 4)
    fc, pol = jev.prepare(sc, sc.flowcharts[fid], seed=4)
    local = simulate(sc, fc, pts, policy=pol, seed=4)
    stub = jev.StubBackend(fc.decision_policy["points"])
    srv, url = serve_in_thread(stub)
    try:
        fc2, pol2 = jev.prepare(sc, sc.flowcharts[fid], backend=url, seed=4)
        remote = simulate(sc, fc2, pts, policy=pol2, seed=4)
        n_dec = sum(len(p.choices) for p in remote.patients)
        assert pol2.run_summary()["requests_sent"] < n_dec / 2            # the cache does its job
    finally:
        srv.shutdown()
        srv.server_close()
    assert compute_metrics(remote, sc) == compute_metrics(local, sc)
    assert [[c["chosen"] for c in p.choices] for p in remote.patients] == [[c["chosen"] for c in p.choices] for p in local.patients]
    assert remote.patients[0].choices[0]["backend"] == "http" if remote.patients[0].choices else True


def test_per_point_routing_uses_http_for_one_point_only():
    sc = load_scenario("scenarios/finland_lung.yaml")
    fc0 = sc.flowcharts["baseline"]
    # a remote model that always picks ttnb at sample_choice
    remote = StubBackend({"sample_choice": {"default": {"bronch": 0.0, "ttnb": 1.0}}}, model="jev-test")
    srv, url = serve_in_thread(remote)
    try:
        fc0 = fc0.copy()
        fc0.decision_policy = {"points": {"sample_choice": {"backend": "http", "url": url, "model": "jev-test"}}}
        fc, pol = jev.prepare(sc, fc0, seed=1)
        run = simulate(sc, fc, generate_patients(sc, 500, 1), policy=pol, seed=1)
    finally:
        srv.shutdown()
        srv.server_close()
    seen = {}
    for p in run.patients:
        for c in p.choices:
            seen.setdefault(c["node"], set()).add((c["backend"], c["model"]))
    assert seen["sample_choice"] == {("http", "jev-test")}
    assert seen["first_contact"] == {("stub", "stub@1")}
    assert {c["chosen"] for p in run.patients for c in p.choices if c["node"] == "sample_choice"} == {"ttnb"}

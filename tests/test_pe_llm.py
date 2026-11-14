"""Offline tests for patient_engine.llm: a local http.server stub on 127.0.0.1 stands in for the endpoint."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from patient_engine import llm
from patient_engine.llm import (Budget, BudgetExceeded, CallLog, FakeLLMClient, LLMClient, LLMConfigError,
                                LLMHTTPError, LLMOutputError, parse_json_text, validation_errors)

KEY = "sk-test-SECRET-1234567890"
SCHEMA = {"type": "object", "required": ["age", "sex"],
          "properties": {"age": {"type": "integer"}, "sex": {"enum": ["f", "m"]}}}
GOOD = {"age": 61, "sex": "f"}


class Stub:
    """Serves scripted replies: each item is a dict (content), a str (raw content) or an int status (optionally (status, headers))."""

    def __init__(self, script=None, echo=None):
        self.script, self.requests, self.headers, self.lock = list(script or []), [], [], threading.Lock()
        self.echo = echo
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with stub.lock:
                    stub.requests.append(body)
                    stub.headers.append(dict(self.headers))
                    scripted = stub.script.pop(0) if stub.script else None
                item = scripted if scripted is not None else (stub.echo(body) if stub.echo else GOOD)
                status, hdrs = 200, {}
                if isinstance(item, tuple):
                    status, hdrs = item
                elif isinstance(item, int):
                    status = item
                if status != 200:
                    self.send_response(status)
                    for k, v in hdrs.items():
                        self.send_header(k, v)
                    payload = f"error echo {self.headers.get('Authorization')}".encode()  # a leaky server
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                content = item if isinstance(item, str) else json.dumps(item)
                payload = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                                      "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub_factory():
    made = []

    def make(*a, **k):
        s = Stub(*a, **k)
        made.append(s)
        return s
    yield make
    for s in made:
        s.close()


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm, "_sleep", sleeps.append)
    return sleeps


def client(stub, tmp_path=None, **kw):
    if tmp_path is not None:
        kw.setdefault("cache_dir", tmp_path / "cache")
    return LLMClient(stub.url, "test-model", KEY, **kw)


def test_request_shape_and_parse(stub_factory):
    s = stub_factory(["```json\n" + json.dumps(GOOD) + "\n```"])  # fenced answer
    assert client(s).complete_json("sys", "usr", SCHEMA, key="k1") == GOOD
    assert len(s.requests) == 1
    r = s.requests[0]
    assert r["model"] == "test-model" and r["response_format"] == {"type": "json_object"}
    assert r["messages"][0]["role"] == "system" and "sys" in r["messages"][0]["content"]
    assert '"required"' in r["messages"][0]["content"]  # schema is in the system prompt
    assert r["messages"][1] == {"role": "user", "content": "usr"}
    assert "temperature" not in r
    assert s.headers[0]["Authorization"] == f"Bearer {KEY}"


def test_json_schema_mode_and_temperature(stub_factory):
    s = stub_factory()
    client(s, json_schema_mode=True).complete_json("a", "b", SCHEMA, key="k", temperature=0.2)
    assert s.requests[0]["response_format"]["type"] == "json_schema"
    assert s.requests[0]["temperature"] == 0.2


def test_from_env(monkeypatch, stub_factory):
    for v in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(LLMConfigError, match="LLM_BASE_URL"):
        LLMClient.from_env()
    s = stub_factory()
    monkeypatch.setenv("LLM_BASE_URL", s.url)
    monkeypatch.setenv("LLM_MODEL", "m1")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    c = LLMClient.from_env(budget=Budget(max_calls=5))
    assert c.complete_json("a", "b", SCHEMA, key="k") == GOOD
    assert s.requests[0]["model"] == "m1" and KEY not in repr(c)


def test_repair_loop_feeds_errors_back(stub_factory):
    s = stub_factory([{"age": "sixty", "sex": "f"}, GOOD])
    assert client(s).complete_json("sys", "usr", SCHEMA, key="k") == GOOD
    assert len(s.requests) == 2
    second = s.requests[1]["messages"]
    assert second[-2]["role"] == "assistant" and "sixty" in second[-2]["content"]
    assert "age" in second[-1]["content"] and "did not validate" in second[-1]["content"]


def test_repair_not_json_then_gives_up(stub_factory):
    s = stub_factory(["no json here", "still none", "nope"])
    with pytest.raises(LLMOutputError, match="after 2 repairs"):
        client(s).complete_json("a", "b", SCHEMA, key="k")
    assert len(s.requests) == 3


@pytest.mark.parametrize("status,hdrs", [(429, {"Retry-After": "7"}), (503, {})])
def test_retry_then_success(stub_factory, fast_backoff, status, hdrs):
    s = stub_factory([(status, hdrs), (status, hdrs), GOOD])
    assert client(s).complete_json("a", "b", SCHEMA, key="k") == GOOD
    assert len(s.requests) == 3 and len(fast_backoff) == 2
    if hdrs:
        assert fast_backoff == [7.0, 7.0]  # Retry-After honoured
    else:
        assert fast_backoff == [1.0, 2.0]  # exponential


def test_give_up_after_n_attempts_no_key_leak(stub_factory):
    s = stub_factory([500] * 10)
    c = client(s, max_attempts=3)
    with pytest.raises(LLMHTTPError, match="after 3 attempts") as ei:
        c.complete_json("a", "b", SCHEMA, key="k")
    assert len(s.requests) == 3 and KEY not in str(ei.value)


def test_client_error_not_retried_and_scrubbed(stub_factory):
    s = stub_factory([400])
    with pytest.raises(LLMHTTPError, match="400") as ei:
        client(s).complete_json("a", "b", SCHEMA, key="k")
    assert len(s.requests) == 1 and KEY not in str(ei.value)  # server echoed the header; client scrubbed it


def test_connection_refused_is_clear_error():
    c = LLMClient("http://127.0.0.1:9/v1", "m", KEY, max_attempts=2)
    with pytest.raises(LLMHTTPError, match="2 attempts") as ei:
        c.complete_json("a", "b", SCHEMA, key="k")
    assert KEY not in str(ei.value)


def test_budget_calls_before_request(stub_factory):
    s = stub_factory()
    c = client(s, budget=Budget(max_calls=2))
    c.complete_json("a", "1", SCHEMA, key="k1")
    c.complete_json("a", "2", SCHEMA, key="k2")
    with pytest.raises(BudgetExceeded):
        c.complete_json("a", "3", SCHEMA, key="k3")
    assert len(s.requests) == 2


def test_budget_tokens(stub_factory):
    s = stub_factory()
    c = client(s, budget=Budget(max_tokens=200))  # 120 tokens per call
    c.complete_json("a", "1", SCHEMA, key="k1")
    c.complete_json("a", "2", SCHEMA, key="k2")  # 120 < 200 so allowed; now at 240
    with pytest.raises(BudgetExceeded, match="token"):
        c.complete_json("a", "3", SCHEMA, key="k3")
    assert len(s.requests) == 2


def test_cache_second_client_zero_http(stub_factory, tmp_path):
    s = stub_factory()
    client(s, tmp_path).complete_json("sys", "usr", SCHEMA, key="k")
    assert len(s.requests) == 1
    c2 = client(s, tmp_path, budget=Budget(max_calls=0))  # even a zero budget is fine for cached prompts
    assert c2.complete_json("sys", "usr", SCHEMA, key="other-label") == GOOD
    assert len(s.requests) == 1
    # a different prompt is not served from the cache
    with pytest.raises(BudgetExceeded):
        c2.complete_json("sys", "different", SCHEMA, key="k")


def test_cache_key_includes_temperature_and_model(stub_factory, tmp_path):
    s = stub_factory()
    c = client(s, tmp_path)
    c.complete_json("a", "b", SCHEMA, key="k", temperature=0.0)
    c.complete_json("a", "b", SCHEMA, key="k", temperature=0.7)
    assert len(s.requests) == 2
    LLMClient(s.url, "other-model", KEY, cache_dir=tmp_path / "cache").complete_json("a", "b", SCHEMA, key="k", temperature=0.0)
    assert len(s.requests) == 3


def test_log_lines_and_no_secret(stub_factory, tmp_path):
    s = stub_factory([{"age": "x", "sex": "f"}, GOOD])
    c = client(s, tmp_path)
    c.complete_json("a", "b", SCHEMA, key="card-1:g1")
    c.complete_json("a", "b", SCHEMA, key="card-1:g1")  # cache hit
    text = (tmp_path / "cache" / "calls.jsonl").read_text()
    lines = [json.loads(x) for x in text.splitlines()]
    assert [x["outcome"] for x in lines] == ["schema_invalid", "ok", "cache_hit"]
    first = lines[0]
    assert first["key"] == "card-1:g1" and first["model"] == "test-model" and len(first["prompt_hash"]) == 64
    assert first["tokens_in"] == 100 and first["tokens_out"] == 20 and first["latency_s"] >= 0
    assert KEY not in text
    # also not in cache files
    assert all(KEY not in p.read_text() for p in (tmp_path / "cache").iterdir())


def test_map_order_and_concurrency(stub_factory):
    seen = {"now": 0, "max": 0}
    lock = threading.Lock()

    def echo(body):
        n = int(body["messages"][1]["content"])
        with lock:
            seen["now"] += 1
            seen["max"] = max(seen["max"], seen["now"])
        import time
        time.sleep(0.02)
        with lock:
            seen["now"] -= 1
        return {"age": n, "sex": "m"}

    s = stub_factory(echo=echo)
    c = client(s, budget=Budget(max_calls=50))
    reqs = [dict(system="a", user=str(i), schema=SCHEMA, key=f"k{i}") for i in range(10)]
    out = c.map(reqs, concurrency=4)
    assert [o["age"] for o in out] == list(range(10))
    assert 1 < seen["max"] <= 4
    assert c.budget.calls == 10


def test_map_return_exceptions(stub_factory):
    c = FakeLLMClient(lambda s, u, sch: GOOD if u != "bad" else "junk")
    reqs = [dict(system="a", user=u, schema=SCHEMA, key=u, max_repairs=0) for u in ("x", "bad", "y")]
    out = c.map(reqs, concurrency=2, return_exceptions=True)
    assert out[0] == GOOD and isinstance(out[1], LLMOutputError) and out[2] == GOOD
    with pytest.raises(LLMOutputError):
        c.map(reqs)


def test_https_uses_ca_bundle_env(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(llm.ssl, "create_default_context", lambda cafile=None: seen.setdefault("ca", cafile) or object())
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/ca.pem")
    assert LLMClient("https://x.example/v1", "m")._ssl_context() is not None and seen["ca"] == "/tmp/ca.pem"
    assert LLMClient("http://x.example/v1", "m")._ssl_context() is None


def test_parse_and_validator():
    assert parse_json_text('Here: {"a": 1} done') == {"a": 1}
    assert parse_json_text("```\n[1,2]\n```") == [1, 2]
    assert validation_errors(GOOD, SCHEMA) == []
    errs = validation_errors({"age": 1.5, "sex": "x"}, SCHEMA)
    assert len(errs) == 2
    # minimal validator, used when jsonschema is missing
    nested = {"type": "object", "properties": {"xs": {"type": "array", "items": {"type": "integer"}}}, "required": ["xs"]}
    assert llm._minimal_errors({"xs": [1, "a", True]}, nested, "$") and not llm._minimal_errors({"xs": [1]}, nested, "$")
    assert llm._minimal_errors({}, nested, "$") and llm._minimal_errors(GOOD | {"sex": "x"}, SCHEMA, "$")
    assert llm.VALIDATOR in ("jsonschema", "minimal")


def test_fake_client_list_and_function(tmp_path):
    f = FakeLLMClient([{"age": "x", "sex": "f"}, GOOD], cache_dir=tmp_path / "c")
    assert f.complete_json("s", "u", SCHEMA, key="k") == GOOD and len(f.calls) == 2
    assert f.complete_json("s", "u", SCHEMA, key="k") == GOOD and len(f.calls) == 2  # cached
    with pytest.raises(llm.LLMError, match="no more"):
        FakeLLMClient([]).complete_json("s", "u", SCHEMA, key="k")
    assert FakeLLMClient(lambda s, u, sch: json.dumps(GOOD)).complete_json("s", "u", SCHEMA, key="k") == GOOD
    b = FakeLLMClient([GOOD, GOOD], budget=Budget(max_calls=1))
    b.complete_json("s", "1", SCHEMA, key="k")
    with pytest.raises(BudgetExceeded):
        b.complete_json("s", "2", SCHEMA, key="k")


def test_docstring_example():
    import doctest
    assert doctest.testmod(llm).failed == 0

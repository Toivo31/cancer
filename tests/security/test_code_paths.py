"""Anything that could turn client text into code: the condition language, YAML, pickle, templates (all safe today)."""

from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

import pytest

from pathway_sim import expr
from sec_helpers import make_client, new_project

ROOT = Path(__file__).resolve().parents[2]

HOSTILE = [
    "__import__('os').system('touch {mark}')", "().__class__.__bases__[0].__subclasses__()", "open('/etc/passwd').read()", "eval('1')", "exec('x=1')",
    "[x for x in ().__class__.__mro__]", "(lambda: 1)()", "age.__class__", "age[0]", "age + 1", "age ** 9 ** 9 ** 9", "'a' * 10 ** 10", "f'{age}'",
    "{'a': 1}", "{1, 2}", "x := 1", "await x", "yield", "*a", "a if b else c", "not", "group == ", "(" * 500 + "1" + ")" * 500, "a and " * 2000 + "b",
    "age in range(10)", "group in ('a',) + ('b',)", "__builtins__", "_private", "a.b", "a(b)", "1 if 2 else 3", "lambda: 1", "# comment", "group == 'x' # c",
    "age == 1e400", "age == 10 ** 13", "'" + "x" * 5000 + "'", "\x00", "group == '\x00'", "a is 5", "a is 'x'", "[1, 2, 3]", "print(age)", "ａｇｅ.__class__",
    "group in " + str(tuple(range(500))),
]


@pytest.mark.parametrize("src", HOSTILE)
def test_condition_language_rejects_or_neutralises(src, tmp_path):
    mark = tmp_path / "marker"
    text = src.format(mark=mark) if "{mark}" in src else src
    try:
        e = expr.parse(text)
    except expr.ExprError:
        pass
    except RecursionError as ex:                      # pragma: no cover - would be a finding
        pytest.fail(f"RecursionError escaped the parser: {ex}")
    else:
        e({"group": "x", "age": 5})                   # anything accepted must evaluate without side effects or crashing
    assert not mark.exists()


def test_fullwidth_unicode_names_are_normalised_not_smuggled():
    e = expr.parse("ａｇｅ > 3")                        # NFKC makes this the name 'age', which is on the allowed list of names
    assert e.names == frozenset({"age"}) and e({"age": 5}) is True
    with pytest.raises(expr.ExprError):
        expr.parse("＿＿import＿＿")                     # becomes a name starting with '_'


def test_evaluation_is_bounded_in_time():
    worst = "(" * 30 + "a or b or c or d or e or f" + ")" * 30
    e = expr.parse(" and ".join([f"({worst})"] * 4)) if len(worst) * 4 < expr.MAX_LENGTH else expr.parse(worst)
    t = time.time()
    for _ in range(2000):
        e({"a": None, "b": 0, "c": "", "d": False, "e": [], "f": 0})
    assert time.time() - t < 2.0


def test_conditions_sent_through_the_api_never_run(tmp_path):
    mark = tmp_path / "pwned"
    with make_client(tmp_path) as c:
        p = new_project(c)
        doc = c.get(f"/api/projects/{p}/flowcharts/observed/versions/1").json()
        doc.pop("version", None), doc.pop("parent_version", None)
        for bad in (f"__import__('os').system('touch {mark}')", f"open('{mark}', 'w')", "().__class__"):
            d = {**doc, "id": "evil", "nodes": [{**n, "when": bad} if i == 1 else n for i, n in enumerate(doc["nodes"])]}
            r = c.post(f"/api/projects/{p}/flowcharts", json=d)
            assert r.status_code == 422, r.text[:200]
            dp = {"backend": "stub", "mode": "sample", "points": {"sample_plan": {"default": {"bronch1": 0.5, "no_sampling": 0.5},
                                                                                   "rules": [{"when": bad, "probs": {"bronch1": 1, "no_sampling": 0}}]}}}
            r = c.post(f"/api/projects/{p}/decide", json={"flowchart": {"id": "observed"}, "decision_point": "sample_plan", "decision_policy": dp})
            assert r.status_code == 422 and not mark.exists(), r.text[:200]


# ------------------------------------------------------------------------------------------ static scan
SCAN_DIRS = ["service", "jev", "pathway_sim", "optimiser", "decision_model", "demo", "technique_classifier"]
FORBIDDEN = [
    (re.compile(r"\byaml\.load\s*\((?!.*Loader=yaml\.SafeLoader)"), "yaml.load without a safe loader"),
    (re.compile(r"\byaml\.(unsafe_load|full_load)\b"), "unsafe YAML loader"),
    (re.compile(r"\bpickle\.loads?\b|\bcPickle\b|\bmarshal\.loads?\b|\bshelve\.open\b"), "pickle-family deserialisation"),
    (re.compile(r"(?<![\w.])(eval|exec)\s*\("), "eval or exec"),
    (re.compile(r"\bos\.system\s*\(|\bos\.popen\s*\(|shell\s*=\s*True"), "shell execution"),
    (re.compile(r"\b__import__\s*\(|\bimportlib\.import_module\s*\(\s*[a-z_]*(req|body|doc|name)"), "dynamic import of client text"),
    (re.compile(r"\.format_map\s*\(|\bTemplate\s*\(\s*(req|body|doc)"), "string template built from client text"),
]
ALLOWED = {  # path suffix -> reason
    "pathway_sim/demo.py": "subprocess.run of fixed argument lists in a CLI helper (no client text)",
}


def _python_files():
    for d in SCAN_DIRS:
        base = ROOT / d
        if base.exists():
            yield from base.rglob("*.py")


def test_no_dangerous_calls_in_server_code():
    hits = []
    for f in _python_files():
        rel = str(f.relative_to(ROOT))
        for n, line in enumerate(f.read_text().splitlines(), 1):
            code = line.split("#")[0]
            if code.lstrip().startswith(('"', "'")):
                continue
            for rx, what in FORBIDDEN:
                if rx.search(code) and rel not in ALLOWED:
                    hits.append(f"{rel}:{n}: {what}: {line.strip()[:90]}")
    assert not hits, "\n".join(hits)


def test_expr_module_has_no_dynamic_execution():
    src = (ROOT / "pathway_sim" / "expr.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    body = re.sub(r'"""(.|\n)*?"""', "", code)                 # docstrings talk about eval; the code must not call it
    assert not re.search(r"(?<![\w.])(eval|exec|compile)\s*\(", body)         # re.compile is fine; a bare compile( is not
    assert "builtins" not in body.lower() or "__builtins__" not in body


# ------------------------------------------------------------------------------------------ the stub JEV server
@pytest.mark.xfail(strict=True, reason="F17: a negative Content-Length makes the stub server read until the client closes (one thread held per connection)")
def test_stub_server_survives_a_negative_content_length():
    import jev
    from jev.stub import StubBackend
    from jev.stub_server import serve_in_thread
    srv, url = serve_in_thread(StubBackend({"p": {"default": {"a": 0.5, "b": 0.5}}}))
    port = srv.server_address[1]
    s = socket.create_connection(("127.0.0.1", port))
    s.sendall(b"POST /v1/decide HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: -1\r\n\r\n")
    s.settimeout(2.0)
    try:
        answered = s.recv(100)
    except socket.timeout:
        answered = b""
    s.close()
    srv.shutdown()
    assert answered.startswith(b"HTTP/1.1 4"), "the server neither answered nor closed the connection within 2 s"

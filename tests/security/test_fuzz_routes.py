"""Fuzzer over every route of the app (security review, phase 4).

Walks ``app.routes``, fills path parameters with real and hostile values, and sends each body route a set of
structural mutations of a valid body (a key removed, a value replaced by null, a huge number, NaN, a deep
list, a long string, ...). It asserts two things:

* no response is a 5xx other than the ones already known and written down in ``KNOWN_500`` (a new 500 fails the test);
* no response body shows a stack trace, a source path or SQL text.

``KNOWN_500`` is empty: every 5xx is a failure.
"""

from __future__ import annotations

import copy
import json
import time
from collections import defaultdict
from urllib.parse import quote

import pytest

from sec_helpers import make_client, new_project, wait_job, world_of

HOSTILE_IDS = ["nope", "...", "..%2F..%2Fetc%2Fpasswd", "a" * 3000, "p_%E2%80%AE%00x", "' OR '1'='1", "-1", "1" + "0" * 30]
BIG = 10 ** 30

# (method, route template, case label) -> why. A 500 anywhere else fails the fuzzer.
KNOWN_500: dict[tuple[str, str], str] = {}      # emptied by WP-C6-SEC1 (F4, F9): any 5xx fails the fuzzer

LEAK_MARKERS = ("Traceback (most recent call last)", "/home/", "site-packages", "sqlite3.", "SELECT ", ".py\", line")


VALUES = (("null", None), ("neg", -1), ("big", BIG), ("long", "A" * 5000), ("list", [1, 2]), ("obj", {"a": {"b": [1]}}), ("true", True),
          ("unicode", "\u0000\u202e\ud7ff"), ("nan", float("nan")), ("inf", float("inf")))
NON_FINITE = ("nan", "inf")


def _mutations(body, depth=0, prefix="", keys=None, finite_only=False):
    """Structural variants of a valid JSON body: each key dropped or replaced, and (one level down) each key of nested objects."""
    out = [] if depth else [("empty_object", {}), ("null", None), ("list", []), ("string", "x"), ("number", 7)]
    if not isinstance(body, dict):
        return out
    for k, v in body.items():
        if keys is not None and k not in keys:
            continue
        d = copy.deepcopy(body)
        del d[k]
        out.append((f"drop_{prefix}{k}", d))
        for label, val in VALUES:
            if finite_only and label in NON_FINITE:
                continue
            d = copy.deepcopy(body)
            d[k] = val
            out.append((f"{prefix}{k}={label}", d))
        if depth == 0 and isinstance(v, dict) and 0 < len(v) <= 8:
            for label, sub in _mutations(v, 1, f"{k}.", finite_only=finite_only):
                d = copy.deepcopy(body)
                d[k] = sub
                out.append((label, d))
    return out


# NaN and Infinity are left out of world edits here: they poison the project (finding F3, tests/security/test_input_limits.py),
# and a poisoned project would make every later request of this fuzz fail for that one reason.
WORLD_KEYS = ("name", "target_days", "warmup_days", "arrivals", "default_n", "conditions", "groups", "resources", "tests", "age", "attributes", "id")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """App with one project holding one finished run, an unsaved-edit-ready flowchart and a finished optimisation."""
    tmp = tmp_path_factory.mktemp("fuzz")
    with make_client(tmp, max_jobs=2) as c:
        p = new_project(c)
        B = f"/api/projects/{p}"
        r = c.post(B + "/runs", json={"flowchart": {"id": "observed"}, "n": 60, "seeds": [1]})
        assert r.status_code == 202, r.text
        run = r.json()
        assert wait_job(c, run["job_id"])["status"] == "succeeded"
        o = c.post(B + "/optimisations", json={"flowchart": {"id": "observed"}, "n": 60, "train_seeds": [11], "heldout_seeds": [12], "max_changes": 1})
        assert o.status_code == 202, o.text
        wait_job(c, o.json()["job_id"], 120)
        fc, _ = c.get(B + "/flowcharts/observed").json(), None
        doc = c.get(B + "/flowcharts/observed/versions/1").json()
        yield {"c": c, "p": p, "r": run["id"], "j": run["job_id"], "o": o.json()["id"], "doc": doc, "world": world_of(c, p)}


def _path_values(w):
    return {"p": w["p"], "f": "observed", "v": "1", "r": w["r"], "j": w["j"], "o": w["o"], "template_id": "norway_check", "d": "d1", "m": "m1"}


def _valid_bodies(w):
    p_doc = w["doc"]
    new_doc = {**copy.deepcopy(p_doc), "id": "fuzz_new"}
    for k in ("version", "parent_version"):
        new_doc.pop(k, None)
    same_doc = {k: v for k, v in copy.deepcopy(p_doc).items() if k not in ("version", "parent_version")}
    return {
        ("POST", "/api/projects"): {"name": "fz", "template": "norway_check"},
        ("PATCH", "/api/projects/{p}"): {"name": "renamed"},
        ("PUT", "/api/projects/{p}/world"): w["world"],
        ("POST", "/api/projects/{p}/flowcharts"): new_doc,
        ("POST", "/api/projects/{p}/flowcharts/{f}/versions"): same_doc,
        ("PUT", "/api/projects/{p}/flowcharts/{f}/versions/{v}"): same_doc,
        ("POST", "/api/projects/{p}/validate"): {"flowchart": same_doc},
        ("POST", "/api/projects/{p}/decide"): {"flowchart": {"id": "observed"}, "decision_point": "sample_plan", "context": {"age": 60, "history": []},
                                               "offered": ["bronch1", "no_sampling"], "option_leads": {"bronch1": 3.0},
                                               "decision_policy": {"backend": "stub", "mode": "sample", "points": {"sample_plan": {"default": {"bronch1": 0.5, "no_sampling": 0.5}}}}},
        ("POST", "/api/projects/{p}/runs"): {"flowchart": {"id": "observed", "version": 1}, "n": 60, "seeds": [91], "label": "fz",
                                                  "decision_policy": {"backend": "http", "url": "http://127.0.0.1:9/", "model": "m", "on_error": "fallback_stub", "timeout": 0.2}},
        ("POST", "/api/projects/{p}/compare"): {"runs": [w["r"], w["r"]]},
        ("POST", "/api/projects/{p}/optimisations"): {"flowchart": {"id": "observed"}, "n": 60, "train_seeds": [21], "heldout_seeds": [22], "max_changes": 1,
                                                      "safety": {"tests_tolerance": 0.1, "equity": True}},
        ("POST", "/api/projects/{p}/optimisations/{o}/apply"): {"accept": [0], "rerun": False},
    }


def _routes(app):
    """(METHOD, path template) for every operation, read from the OpenAPI document (newer FastAPI nests routers lazily,
    so ``app.routes`` no longer lists them)."""
    for path, ops in app.openapi()["paths"].items():
        for m in ops:
            if m.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                yield m.upper(), path


def _fill(path, values):
    for k, v in values.items():
        path = path.replace("{" + k + "}", v)
    return path


def test_fuzz_every_route_has_no_unexpected_500(world):
    c = world["c"]
    values = _path_values(world)
    bodies = _valid_bodies(world)
    seen_500: dict[tuple[str, str], list[str]] = defaultdict(list)
    leaks: list[str] = []
    statuses: dict[int, int] = defaultdict(int)
    sent = 0
    t0 = time.time()

    def send(method, template, label, path, body=None, raw=None, query=None):
        nonlocal sent
        sent += 1
        kw = {}
        if raw is not None:
            kw = {"content": raw, "headers": {"content-type": "application/json"}}
        elif body is not None or method in ("POST", "PUT", "PATCH"):
            kw = {"content": json.dumps(body, allow_nan=True), "headers": {"content-type": "application/json"}}
        r = c.request(method, path, params=query, follow_redirects=False, **kw)
        statuses[r.status_code] += 1
        if r.status_code >= 500:
            seen_500[(method, template)].append(label)
        if any(m in r.text for m in LEAK_MARKERS):
            leaks.append(f"{method} {template} [{label}]: {r.text[:160]}")
        return r

    for method, template in _routes(c.app):
        hostile_only = method == "DELETE"      # a real delete would remove what the later requests need
        assert c.get(f"/api/projects/{values['p']}").status_code == 200, f"the fuzzer destroyed its own project at {method} {template}"
        # 1. hostile and wrong ids in every path parameter, one at a time
        names = [n for n in values if "{" + n + "}" in template]
        for name in names:
            for bad in HOSTILE_IDS:
                v = dict(values, **{name: quote(bad, safe="%")})   # a bare ".." segment would be normalised away by the HTTP client and hit the parent resource
                path = _fill(template, v)
                body = bodies.get((method, template), {})
                send(method, template, f"{name}={bad[:20]!r}", path, body if method in ("POST", "PUT", "PATCH") else None)
        if hostile_only:
            continue
        path = _fill(template, values)
        if template.endswith("/cancel"):
            continue
        # 2. query strings
        if method == "GET":
            for q in ({"offset": -1}, {"offset": BIG}, {"limit": 0}, {"limit": 10 ** 9}, {"limit": "x"}, {"seed": "x"}, {"seed": BIG},
                      {"sample": 0}, {"sample": 10 ** 9}, {"seeds": "x"}, {"seeds": [1, 2, 3]}, {"compare_to": "../x"}, {"compare_to": values["r"]},
                      {"flowchart": "' OR 1=1 --"}, {"status": "x' OR 1=1 --"}, {"point": "x"}, {"measured_only": "maybe"}, {"brief": "perhaps"}):
                send(method, template, f"query {q}", path, query=q)
        # 3. body mutations
        valid = bodies.get((method, template))
        if valid is not None:
            world_edit = template.endswith("/world")
            for label, mutated in _mutations(valid, keys=WORLD_KEYS if world_edit else None, finite_only=world_edit):
                send(method, template, label, path, mutated)
            # raw text variants of the body
            for label, raw in (("not_json", "{nope"), ("nan", json.dumps(valid).replace("1", "NaN", 1) if valid else "NaN"),
                               ("dup_keys", '{"name":"a","name":"b","template":"norway_check","flowchart":{"id":"observed"},"flowchart":{"id":1}}'),
                               ("deep", "[" * 2000 + "]" * 2000), ("bom", "﻿{}"), ("empty", "")):
                send(method, template, f"raw {label}", path, raw=raw)

    # a bogus method on every path
    for _method, template in _routes(c.app):
        send("TRACE", template, "trace", _fill(template, values))

    # let jobs the fuzzer started finish or be cancelled by the fixture's shutdown
    print(f"\nfuzz: {sent} requests in {time.time() - t0:.1f}s; statuses {dict(sorted(statuses.items()))}")
    for key, labels in sorted(seen_500.items()):
        print("500:", key, labels[:6], "..." if len(labels) > 6 else "")
    new = {k: v for k, v in seen_500.items() if k not in KNOWN_500}
    assert not new, "unexpected 500 responses: " + json.dumps({f"{m} {t}": v[:5] for (m, t), v in new.items()}, indent=1)
    assert not leaks, "responses that show internals:\n" + "\n".join(leaks[:10])

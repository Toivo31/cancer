"""WP-W5-1: the Birch (checkpoint 1138) backend against a local mock of the proxy. The real model is never called."""

from __future__ import annotations

import json
import re
from argparse import Namespace
from types import SimpleNamespace

import pytest

import jev
from jev.birch import (BirchBackend, BirchBudgetExceeded, BirchPolicy, BirchUnavailable, BirchVisibilityError,
                       check_visible, map_request, parse_spec)
from jev.birch_mock import MockProxy
from jev.contract import DecisionRequest
from patient_engine.card import HIDDEN_FIELD_NAMES
from patient_engine.catalogue import load_catalogue
from patient_engine.reveal import RevealHandle
from test_jev_record_context import TINY, coexisting_card, record_from, strings

OPTIONS = ["order_chest_xray", "treat_antibiotics", "refer_urgent"]


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def view_for(record, node="gp_encounter"):
    return SimpleNamespace(patient_id=1, group="", age=67, t_now=11.0, node=node, history=[], attributes={}, priority=False,
                           offered=OPTIONS, option_leads={}, record=record, role="gp")


def request(tiny, cache_dir=None, **kw):
    card, _ = coexisting_card(tiny)
    rec = record_from(RevealHandle(card))
    be = BirchBackend("http://127.0.0.1:1", cache_dir=cache_dir, allow_non_model=True, forbidden_values=frozenset(tiny.conditions))
    pol = BirchPolicy(be, catalogue=tiny)
    return pol.request_for(view_for(rec), OPTIONS), card, rec


def backend(m, tmp_path, **kw):
    kw.setdefault("allow_non_model", True)
    kw.setdefault("cache_dir", tmp_path / "cache")
    return BirchBackend(m.url, **kw)


# ---------------------------------------------------------------------------- mapping

def test_request_mapping(tiny):
    req, _, rec = request(tiny)
    p = map_request(req)
    assert set(p) == {"case", "workflow", "node_id"} and p["node_id"] == "gp_encounter"
    ev = p["case"]["evidence"]
    assert len(ev) == len(rec.entries) and [e["available_at_step"] for e in ev] == list(range(1, len(rec.entries) + 1))
    assert p["case"]["step"] == len(rec.entries)
    assert "age" in p["case"]["context"] or "67" in p["case"]["context"]
    wf = p["workflow"]
    assert wf["root"] == "gp_encounter"
    acts = wf["nodes"]["gp_encounter"]["actions"]
    assert [a["id"] for a in acts] == OPTIONS and all(wf["nodes"][a["next"]] == {"terminal": True} for a in acts)
    json.dumps(p)


def test_assessments_are_left_out_unless_asked(tiny):
    req, _, rec = request(tiny)
    rec.add_assessment(11.0, "gp_encounter/birch", "model said a thing", {"plan": "x"}, role="gp")
    be = BirchBackend("http://127.0.0.1:1", cache_dir=None, include_assessments=False)
    ev = map_request(BirchPolicy(be, catalogue=tiny).request_for(view_for(rec), OPTIONS))["case"]["evidence"]
    assert not any("model said a thing" in e["text"] for e in ev)
    be2 = BirchBackend("http://127.0.0.1:1", cache_dir=None, include_assessments=True)
    ev2 = map_request(BirchPolicy(be2, catalogue=tiny).request_for(view_for(rec), OPTIONS), True)["case"]["evidence"]
    assert any("model said a thing" in e["text"] for e in ev2)


def test_scores_become_probs_over_the_offered_ids(tiny, tmp_path):
    req, _, _ = request(tiny)
    with MockProxy() as m:
        resp = backend(m, tmp_path).decide([req])[0]
    assert set(resp.probs) == set(OPTIONS) and abs(sum(resp.probs.values()) - 1) < 1e-9
    sent = m.bodies[0]
    assert "birch step 1138" in resp.explanation and "margin" in resp.explanation and resp.record_note is None
    assert sent["case"]["case_id"] == req.request_id


def test_rationale_is_passed_as_the_record_note(tiny, tmp_path):
    req, _, _ = request(tiny)
    import jev.birch_mock as bm
    orig = bm.propose
    bm.propose = lambda body: {**orig(body), "questions": [{**orig(body)["questions"][0], "rationale": "Persisting cough, former smoker: image the chest."}]}
    try:
        with MockProxy() as m:
            assert backend(m, tmp_path).decide([req])[0].record_note == "Persisting cough, former smoker: image the chest."
    finally:
        bm.propose = orig


def test_a_shorter_option_list_gives_a_shorter_workflow(tiny, tmp_path):
    req, _, _ = request(tiny)
    req.options = req.options[:2]
    other = DecisionRequest(req.request_id, req.decision_point, req.context, req.options)
    with MockProxy() as m:
        be = backend(m, tmp_path)
        be.decide([other])                                       # fine
    assert len(m.bodies[0]["workflow"]["nodes"]["gp_encounter"]["actions"]) == 2


# ---------------------------------------------------------------------------- cost guards

def test_cache_hit_on_repeat_and_across_instances(tiny, tmp_path):
    req, _, _ = request(tiny)
    with MockProxy() as m:
        be = backend(m, tmp_path)
        a = be.decide([req])[0]
        b = be.decide([DecisionRequest("another-id", req.decision_point, req.context, req.options)])[0]
        assert a.probs == b.probs and len(m.bodies) == 1 and be.summary()["cache_hits"] == 1
        c = backend(m, tmp_path).decide([req])[0]                # new process, same disk cache
        assert c.probs == a.probs and len(m.bodies) == 1
    assert (tmp_path / "cache" / "calls.jsonl").read_text().count("\n") == 1


def test_non_model_answers_are_not_served_as_the_model(tiny, tmp_path):
    req, _, _ = request(tiny)
    with MockProxy() as m:
        be = backend(m, tmp_path, allow_non_model=False)
        with pytest.raises(BirchUnavailable, match="not the model"):
            be.decide([req])
    assert not list((tmp_path / "cache").glob("*.json")) if (tmp_path / "cache").exists() else True


def test_budget_stop(tiny, tmp_path):
    req, _, _ = request(tiny)
    other = DecisionRequest("r2", req.decision_point, {**req.context, "age": 99,
                            "record_text": {**req.context["record_text"], "case": "someone else"}}, req.options)
    with MockProxy() as m:
        be = backend(m, tmp_path, max_calls=1)
        be.decide([req])
        with pytest.raises(BirchBudgetExceeded, match="budget of 1"):
            be.decide([other])
        assert len(m.bodies) == 1
        be.decide([req])                                         # a cache hit costs nothing after the budget is spent


def test_single_option_is_never_sent(tiny, tmp_path):
    req, _, _ = request(tiny)
    one = DecisionRequest("r", req.decision_point, req.context, req.options[:1])
    with MockProxy() as m:
        resp = backend(m, tmp_path).decide([one])[0]
    assert resp.probs == {OPTIONS[0]: 1.0} and m.bodies == []


def test_503_is_a_loud_error_and_stops_after_two(tiny, tmp_path):
    req, _, _ = request(tiny)
    with MockProxy(status=503) as m:
        be = backend(m, tmp_path)
        for _ in range(2):
            with pytest.raises(BirchUnavailable, match="HTTP 503.*starting"):
                be.decide([req])
        with pytest.raises(BirchUnavailable, match="stopped after 2 failed calls"):
            be.decide([req])
        assert len(m.bodies) == 2 and be.summary()["failures"] == 2


def test_timeout_is_an_error(tiny, tmp_path):
    req, _, _ = request(tiny)
    with MockProxy(delay=1.0) as m:
        with pytest.raises(BirchUnavailable, match="no answer"):
            backend(m, tmp_path, timeout=0.2).decide([req])


def test_connection_refused_is_an_error(tiny, tmp_path):
    req, _, _ = request(tiny)
    with pytest.raises(BirchUnavailable, match="decision_api.server"):
        BirchBackend("http://127.0.0.1:9", cache_dir=None).decide([req])


def test_the_model_url_is_refused_and_concurrency_is_bounded():
    with pytest.raises(ValueError, match="local proxy"):
        BirchBackend("https://x--birch.modal.run")
    with pytest.raises(ValueError):
        BirchBackend(concurrency=5)
    assert parse_spec("birch") and parse_spec("birch+http://h:1") == "http://h:1" and parse_spec("http://h") is None


def test_concurrency_keeps_order_and_budget(tiny, tmp_path):
    req, _, _ = request(tiny)
    reqs = [DecisionRequest(f"r{i}", req.decision_point,
                            {**req.context, "record_text": {**req.context["record_text"], "case": f"patient {i}"}}, req.options)
            for i in range(6)]
    with MockProxy() as m:
        be = backend(m, tmp_path, concurrency=3, max_calls=4)
        with pytest.raises(BirchBudgetExceeded):
            be.decide(reqs)
        assert len(m.bodies) == 4


# ---------------------------------------------------------------------------- I1

def test_i1_nothing_hidden_is_sent(tiny, tmp_path):
    req, card, rec = request(tiny)
    ids = {c.id for c in card.hidden.conditions}
    assert len(ids) >= 2                                          # a co-existing illness
    with MockProxy() as m:
        backend(m, tmp_path).decide([req])
    body = m.bodies[0]
    text = json.dumps(body)
    hidden_only = set(card.hidden.findings["all_active"]) - set(tiny.variables)
    for bad in ids | set(tiny.conditions) | hidden_only:
        assert bad not in text, bad
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not set(keys(body)) & (set(HIDDEN_FIELD_NAMES) | ids)
    assert str(card.id) not in text
    case = body["case"]
    assert all(e["available_at_step"] <= case["step"] for e in case["evidence"])
    assert body["case"]["case_id"] not in (card.id,)


def test_guard_refuses_future_evidence_and_hidden_names(tiny):
    req, _, _ = request(tiny)
    p = map_request(req)
    check_visible(p, set(tiny.conditions))
    bad = json.loads(json.dumps(p))
    bad["case"]["evidence"].append({"source_id": "x", "available_at_step": bad["case"]["step"] + 1, "text": "later"})
    with pytest.raises(BirchVisibilityError, match="not available"):
        check_visible(bad)
    bad = json.loads(json.dumps(p))
    bad["case"]["hidden"] = {"a": 1}
    with pytest.raises(BirchVisibilityError, match="hidden-side"):
        check_visible(bad)
    bad = json.loads(json.dumps(p))
    bad["case"]["context"] += " lung_cancer"
    with pytest.raises(BirchVisibilityError, match="condition id"):
        check_visible(bad, {"lung_cancer"})


def test_context_only_fallback_has_the_same_guarantees(tiny):
    req, _, _ = request(tiny)
    ctx = {k: v for k, v in req.context.items() if k != "record_text"}
    p = map_request(DecisionRequest("r", "gp_encounter", ctx, req.options))
    check_visible(p, set(tiny.conditions))
    assert p["case"]["evidence"] and p["case"]["step"] == len(p["case"]["evidence"])


# ---------------------------------------------------------------------------- factory, walk

def test_factory_builds_a_birch_policy():
    from pathway_sim import load_scenario
    sc = load_scenario("scenarios/finland_lung.yaml")
    fc, pol = jev.prepare(sc, sc.flowcharts["baseline"], backend="birch+http://127.0.0.1:1", max_calls=3, cache_dir=None)
    assert isinstance(pol, BirchPolicy) and pol.backend.max_calls == 3 and pol.backend.url.endswith("/api/decision/pathway")


def test_walk_against_the_mock_runs_end_to_end(tmp_path):
    import time
    from jev.walk import walk
    t0 = time.time()
    lines = []
    a = Namespace(pick="cancer", library=None, patient=None, jev="mock", placeholder=True, auto_accept=True,
                  include_assessments=False, max_calls=50, concurrency=1, cache_dir=str(tmp_path / "c"),
                  work_dir=str(tmp_path), world="scenarios/finland_encounter.yaml", seed=1, out=None)
    res = walk(a, out=lines.append)
    assert time.time() - t0 < 30
    assert res["steps"] and res["model_calls"]["calls"] >= 1 and res["model_calls"]["backend"].keys() == {"mock:1138"}
    assert all(s["table"] for s in res["steps"]) and res["outcome"]
    assert any("proposed" in l for l in lines) and "hidden truth" in "\n".join(lines)
    saved = json.loads(next((tmp_path / "walks").glob("*.json")).read_text())
    assert saved["format"] == "jev_walk/1"
    # the saved record the decider saw holds no hidden truth: only the scoring block does
    truth = saved["hidden_truth_for_scoring"]["primary_condition"]
    assert truth not in json.dumps(saved["steps"]) and truth not in json.dumps(saved["record"])


def test_walk_override_by_a_person(tmp_path):
    from jev.walk import walk
    answers = iter(["", "2"] + ["1"] * 40)
    a = Namespace(pick="pneumonia", library=None, patient=None, jev="mock", placeholder=False, auto_accept=False,
                  include_assessments=False, max_calls=50, concurrency=1, cache_dir=str(tmp_path / "c"),
                  work_dir=str(tmp_path), world="scenarios/finland_encounter.yaml", seed=1, out=None)
    res = walk(a, out=lambda *_: None, input_fn=lambda *_: next(answers))
    assert res["steps"][0]["overridden"] is False and res["steps"][1]["overridden"] is True

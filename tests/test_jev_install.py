"""WP-W8-1: jev.birch pointed at checkpoint 2350 through the owner's bridge (decision_api/jev_bridge.py).

Offline only: a local mock of the proxy whose answers claim a model identity. The real model is never called.
"""

from __future__ import annotations

import json
import time
from argparse import Namespace

import pytest

import jev
import jev.birch_mock as birch_mock
from decision_api import jev_bridge
from jev import birch
from jev.birch import (BirchBackend, BirchError, BirchUnavailable, check_limits, check_visible, map_request,
                       pinned_backend)
from jev.birch_mock import MockProxy
from jev.contract import DecisionRequest
from test_jev_birch import request, tiny  # noqa: F401  (fixture)

SHA = birch.CHECKPOINT_SHA256
MODEL_2350 = {"mode": "model", "model": "birch07-refine-v3", "step": 2350, "checkpoint_sha256": SHA}


def as_model(monkeypatch, **identity):
    """Make the mock answer as if it were the model with this identity."""
    monkeypatch.setattr(birch_mock, "MOCK_BACKEND", {**MODEL_2350, **identity})


def pinned(m, tmp_path, **kw):
    kw.setdefault("cache_dir", tmp_path / "cache")
    kw.setdefault("min_interval", 0.0)
    return pinned_backend(url=m.url, **kw)


# ---------------------------------------------------------------------------- defaults

def test_defaults_are_checkpoint_2350_and_match_the_owners_bridge():
    assert birch.CHECKPOINT == 2350 and (jev_bridge.STEP, jev_bridge.SHA256) == (birch.CHECKPOINT, SHA)
    be = BirchBackend("http://127.0.0.1:1")
    assert be.checkpoint == 2350 and be.timeout == 660.0
    assert str(be.cache_dir) == f"runs/jev_cache/checkpoint-2350-{SHA[:12]}" != "runs/jev_cache"
    assert be.info().model == "birch-2350" and be.max_actions is None
    pb = pinned_backend(url="http://127.0.0.1:1")
    assert type(pb).__name__ == "HostedBirchBackend" and isinstance(pb, BirchBackend)
    assert pb.checkpoint == 2350 and pb.timeout == 660 and str(pb.cache_dir) == str(be.cache_dir)
    assert pb.min_interval == birch.GATEWAY_MIN_INTERVAL == 10.0 and pb.max_actions == 16
    with pytest.raises(ValueError, match="2350"):
        pinned_backend(checkpoint=1138)


def test_factory_birch_resolves_to_the_pinned_bridge_and_mocks_stay_plain():
    from pathway_sim import load_scenario
    sc = load_scenario("scenarios/finland_lung.yaml")
    _, pol = jev.prepare(sc, sc.flowcharts["baseline"], backend="birch", max_calls=3, cache_dir=None)
    assert type(pol.backend).__name__ == "HostedBirchBackend" and pol.backend.url == "http://127.0.0.1:8771/api/decision/pathway"
    be = birch.backend_from_config({"url": "http://127.0.0.1:1", "allow_non_model": True, "cache_dir": None})
    assert type(be) is BirchBackend and be.allow_non_model


def test_a_bridge_with_another_pin_is_refused(monkeypatch):
    monkeypatch.setattr(jev_bridge, "STEP", 9999)
    with pytest.raises(BirchError, match="update CHECKPOINT"):
        pinned_backend(url="http://127.0.0.1:1")


# ---------------------------------------------------------------------------- identity

def test_the_pinned_model_is_accepted_and_its_identity_shown(tiny, tmp_path, monkeypatch):
    as_model(monkeypatch)
    req, _, _ = request(tiny)
    with MockProxy() as m:
        be = pinned(m, tmp_path)
        out = be.decide([req])[0]
    assert abs(sum(out.probs.values()) - 1) < 1e-9
    assert "birch step 2350 sha 22570c201a9e (model)" in out.explanation
    assert be.summary()["backend"] == {"model:2350": 1}


@pytest.mark.parametrize("identity", [{"step": 1138}, {"checkpoint_sha256": "0" * 64}, {"mode": "mock"}])
def test_an_answer_from_another_model_is_refused(tiny, tmp_path, monkeypatch, identity):
    as_model(monkeypatch, **identity)
    req, _, _ = request(tiny)
    with MockProxy() as m:
        be = pinned(m, tmp_path)
        with pytest.raises(BirchUnavailable):
            be.decide([req])
    assert not list((tmp_path / "cache").glob("*.json")) or all(
        json.loads(f.read_text())["response"]["backend"].get("step") == 2350 for f in (tmp_path / "cache").glob("[0-9a-f]*.json"))


def test_a_1138_cache_entry_is_not_reused(tiny, tmp_path, monkeypatch):
    as_model(monkeypatch)
    req, _, _ = request(tiny)
    with MockProxy() as m:
        be = pinned(m, tmp_path)
        key = birch.cache_key(map_request(req))
        old = {"backend": {"mode": "model", "step": 1138}, "questions": [{"id": req.decision_point, "choices": [
            {"id": o["id"], "score": 1.0} for o in req.options]}]}
        (tmp_path / "cache").mkdir()
        (tmp_path / "cache" / f"{key}.json").write_text(json.dumps({"key": key, "response": old}))
        be.decide([req])
        assert len(m.bodies) == 1 and be.cache_hits == 0          # the old answer was ignored, the model asked
        be.decide([req])
        assert len(m.bodies) == 1 and be.cache_hits == 1          # the 2350 answer replaced it and is reused


# ---------------------------------------------------------------------------- limits (fail before sending)

def _payload_of_size(n: int) -> dict:
    p = {"case": {"case_id": "x", "context": "c", "step": 1, "evidence": [{"source_id": "s", "available_at_step": 1, "text": ""}]},
         "workflow": {"id": "w", "version": "1", "root": "n", "nodes": {"n": {"actions": []}}}, "node_id": "n"}
    p["case"]["evidence"][0]["text"] = "a" * (n - len(json.dumps(p)))
    assert len(json.dumps(p)) == n
    return p


def test_body_limit_edge_is_the_gateways_32000_bytes():
    check_limits(_payload_of_size(32000))
    with pytest.raises(BirchError, match="32000 bytes.*nothing was sent"):
        check_limits(_payload_of_size(32001))


def test_body_is_measured_as_the_gateway_measures_it():
    p = _payload_of_size(31990)
    p["case"]["evidence"][0]["text"] = p["case"]["evidence"][0]["text"][:-10] + "ä" * 5   # 5 chars, 30 bytes as \\u00e4
    with pytest.raises(BirchError, match="hosted gateway"):
        check_limits(p)


def test_a_long_record_fails_before_sending(tiny, tmp_path, monkeypatch):
    as_model(monkeypatch)
    req, _, _ = request(tiny)
    lines = req.context["record_text"]["lines"]
    big = [{"step": i + 1, "kind": "note", "text": "x" * 2900} for i in range(12)]
    req.context = {**req.context, "record_text": {**req.context["record_text"], "lines": lines + big}}
    with MockProxy() as m:
        be = pinned(m, tmp_path)
        with pytest.raises(BirchError, match="32000"):
            be.decide([req])
        assert m.bodies == [] and be.calls == 0 and be.failures == 0


def test_context_and_action_limits():
    p = _payload_of_size(1000)
    p["case"]["context"] = "c" * 12001
    with pytest.raises(BirchError, match="12000"):
        check_limits(p)
    p = _payload_of_size(1000)
    p["workflow"]["nodes"]["n"]["actions"] = [{"id": f"a{i}"} for i in range(17)]
    with pytest.raises(BirchError, match="at most 16"):
        check_limits(p)
    p["workflow"]["nodes"]["n"]["actions"].pop()
    check_limits(p)


def test_live_calls_are_paced(tiny, tmp_path, monkeypatch):
    as_model(monkeypatch)
    req, _, _ = request(tiny)
    reqs = [DecisionRequest(f"r{i}", req.decision_point,
                            {**req.context, "record_text": {**req.context["record_text"], "case": f"patient {i}"}}, req.options)
            for i in range(3)]
    with MockProxy() as m:
        be = pinned(m, tmp_path, min_interval=0.3)
        t0 = time.monotonic()
        be.decide(reqs)
        assert time.monotonic() - t0 >= 0.6 and len(m.bodies) == 3


# ---------------------------------------------------------------------------- I1 with the bridge, and the walk

def test_i1_still_holds_through_the_bridge(tiny, tmp_path, monkeypatch):
    as_model(monkeypatch)
    req, card, _ = request(tiny)
    with MockProxy() as m:
        pinned(m, tmp_path, forbidden_values=frozenset(tiny.conditions)).decide([req])
    body = m.bodies[0]
    check_visible(body, set(tiny.conditions), birch.public_phrases(tiny))
    text = json.dumps(body)
    for bad in {c.id for c in card.hidden.conditions} | set(tiny.conditions):
        assert bad not in text, bad


def test_walk_live_path_uses_the_bridge_and_stops_before_the_gp_node(tmp_path, monkeypatch):
    """`--jev birch+URL` (here the mock posing as 2350) goes through the pinned bridge. Every call sent is answered by
    2350; the GP node offers 24 actions (over the native 16, WP-W8-2), so the walk stops there before sending."""
    from jev.walk import walk
    as_model(monkeypatch)
    with MockProxy() as m:
        a = Namespace(pick="cancer", library=None, patient=None, jev=f"birch+{m.url}", placeholder=False, auto_accept=True,
                      include_assessments=False, max_calls=50, concurrency=1, cache_dir=str(tmp_path / "c"), min_interval=0.0,
                      work_dir=str(tmp_path), world="scenarios/finland_encounter.yaml", seed=1, out=None)
        lines = []
        with pytest.raises(BirchError, match="offers 24 actions; the model takes at most 16"):
            walk(a, out=lines.append)
    assert all(len(b["workflow"]["nodes"][b["node_id"]]["actions"]) <= 16 for b in m.bodies)
    assert all("step 2350 sha 22570c201a9e" in l for l in lines if l.strip().startswith("(birch step"))
    saved = json.loads(next((tmp_path / "walks").glob("walk_stopped_*.json")).read_text())
    assert saved["stopped"] and saved["steps"] and all(s["backend"]["step"] == 2350 for s in saved["steps"])
    assert "hidden_block_scoring_only" not in saved and "lung_cancer" not in json.dumps(saved["steps"])

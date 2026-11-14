"""The simulator on the JEV (lane w9/jev-sim): runner, request builder, pacing, resumable cache, exporter, page bundle.

Offline: every model answer comes from jev.birch_mock (backend.mode = mock). Nothing here reaches the gateway.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_pages import DEMO, ROOT
from jev.birch import BirchBackend, check_visible
from jev.birch_mock import MockProxy
from jev.flow_policy import FlowBirchPolicy
from pathway_sim import simulate
from pathway_sim import jev_run as jr

import importlib.util

_spec = importlib.util.spec_from_file_location("export_jev_flow", DEMO / "export_jev_flow.py")
ejf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ejf)


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.slept = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


# ------------------------------------------------------------------ pacing

def test_rate_gate_spaces_calls_and_keeps_the_hourly_cap():
    c = FakeClock()
    g = jr.RateGate(interval=11, per_hour=5, clock=c.clock, sleep=c.sleep, log=lambda *a: None)
    for _ in range(5):
        g.wait()
    assert c.slept == [11, 11, 11, 11]                  # first call immediately, then 11 s apart
    g.wait()                                            # sixth call in the hour waits for the first to age out
    assert c.t == pytest.approx(3600.0)
    assert len([t for t in g.sent if t > c.t - 3600]) <= 5


def test_rate_gate_refuses_settings_above_the_gateway_limits():
    with pytest.raises(ValueError):
        jr.RateGate(interval=5)
    with pytest.raises(ValueError):
        jr.RateGate(per_hour=121)


# ------------------------------------------------------------------ request builder (I1)

def _norway(n=8):
    sc, fcid, seed = jr.load("norway")
    return sc, sc.flowcharts[fcid], jr.select_patients(sc, n, seed), seed


def test_flow_requests_carry_visible_state_only_and_fit_the_gateway():
    sc, fc, pts, seed = _norway(10)
    with MockProxy() as m:
        be = BirchBackend(m.url, allow_non_model=True, cache_dir=None, max_calls=500)
        simulate(sc, fc, pts, policy=FlowBirchPolicy(be, sc, fc), seed=seed)
        bodies = m.bodies
    assert bodies
    hidden_words = ("Treatment planned", "lung_cancer_stage", "stage i")
    for b in bodies:
        check_visible(b, be.forbidden_values, be.public_phrases)
        assert len(json.dumps(b)) < 32000                                   # gateway body limit
        acts = b["workflow"]["nodes"][b["node_id"]]["actions"]
        assert 2 <= len(acts) <= 8                                          # never a single option; under 8 and 16
        text = b["case"]["context"] + " ".join(e["text"] for e in b["case"]["evidence"])
        assert "Norwegian" in text and "Decision now" in text
        assert not any(w in text for w in hidden_words), text               # treatment plan is hidden until the board
    assert be.forbidden_values == {"lung_cancer_stage_i_ii"}


def test_inconclusive_bronchoscopy_is_said_in_words():
    sc, fc, pts, seed = _norway(30)
    with MockProxy() as m:
        be = BirchBackend(m.url, allow_non_model=True, cache_dir=None, max_calls=500)
        simulate(sc, fc, pts, policy=FlowBirchPolicy(be, sc, fc), seed=seed)
        after = [b for b in m.bodies if b["node_id"] == "after_bronch"]
    assert after
    assert all(any("Bronchoscopy: inconclusive" in e["text"] for e in b["case"]["evidence"]) for b in after)


# ------------------------------------------------------------------ runner

def test_small_cohort_patients_have_the_same_path_as_in_the_full_run():
    sc, fc, pts, seed = _norway(30)
    from pathway_sim.patients import generate_patients
    full = simulate(sc, fc, generate_patients(sc, jr.COHORT_SIZE, seed), seed=seed)
    sub = simulate(sc, fc, pts, seed=seed)
    by = {pr.patient.id: pr.t_exit for pr in full.patients}
    assert all(abs(by[pr.patient.id] - pr.t_exit) < 1e-9 for pr in sub.patients)


def test_capacity_queue_scenario_is_refused():
    sc, _, _ = jr.load("finland")
    if all(r.get("type", "server") in ("delay", "batch") for r in sc.resources.values()):
        pytest.skip("finland has no capacity queue")
    with pytest.raises(SystemExit):
        jr.check_independent(sc)


def test_estimate_counts_multi_option_decisions():
    sc, fc, pts, seed = _norway(10)
    e = jr.estimate(sc, fc, pts, seed)
    assert e["calls_estimate"] >= e["calls_rule_path"] > 0
    assert e["calls_estimate"] <= 5 * 10


def _picks(doc):
    return [{k: v for k, v in d.items() if k != "explanation"} for d in doc["decisions"]]


def _run(tmp_path, n=6, **kw):
    return jr.run("norway", n=n, backend="mock", cache_dir=str(tmp_path / "cache"), out=tmp_path / "run.json",
                  log=lambda *a: None, **kw)


def test_mock_run_records_provenance_agreement_and_outcomes(tmp_path):
    doc = _run(tmp_path)
    p = doc["provenance"]
    assert p["n_patients"] == 6 and p["is_model"] is False and p["model_identity"]["mode"] == "mock"
    assert p["calls_live"] + p["answers_from_cache"] == sum(1 for d in doc["decisions"] if not d["single_option"])
    for node, a in doc["agreement"].items():
        assert 0 <= a["agree"] <= a["n"] and abs(sum(a["jev_share"].values()) - 1) < 1e-3
    assert doc["outcomes"]["rule_tables"]["n"] == doc["outcomes"]["jev"]["n"] == 6
    assert doc["caveats"] and json.loads((tmp_path / "run.json").read_text())["format"] == "jev-sim-run/1"


def test_rerun_is_served_from_the_cache(tmp_path):
    first = _run(tmp_path)
    again = _run(tmp_path)
    assert again["provenance"]["calls_live"] == 0
    assert again["provenance"]["answers_from_cache"] == first["provenance"]["calls_live"] + first["provenance"]["answers_from_cache"]
    assert _picks(again) == _picks(first)


def test_a_stopped_run_resumes_where_it_stopped(tmp_path):
    with pytest.raises(jr.RunStopped):
        _run(tmp_path, max_calls=3)
    done = _run(tmp_path, max_calls=200)
    full = _run(tmp_path / "fresh")
    assert done["provenance"]["calls_live"] == full["provenance"]["calls_live"] - 3
    assert _picks(done) == _picks(full)


def test_live_calls_go_through_the_gate(tmp_path):
    c = FakeClock()
    gate = jr.RateGate(interval=11, per_hour=115, clock=c.clock, sleep=c.sleep, log=lambda *a: None)
    doc = _run(tmp_path, gate=gate)
    assert len(gate.sent) == doc["provenance"]["calls_live"] > 0
    assert all(b - a >= 11 - 1e-9 for a, b in zip(gate.sent, gate.sent[1:]))


# ------------------------------------------------------------------ exporter and page

def test_exporter_replays_the_recorded_run_and_labels_a_mock(tmp_path):
    doc = _run(tmp_path, n=8)
    s = ejf.build(doc)
    assert s["mock"] is True and s["provenance_line"].startswith("MOCK")
    keys = [v["key"] for v in s["variants"]]
    assert keys == s["default_pair"] == ["jev_rules", "jev"]
    jev_flow = s["variants"][1]["flow"]
    assert jev_flow["totals"]["n"] == 8
    assert jev_flow["metrics"]["share_within_target"] == pytest.approx(doc["outcomes"]["jev"]["share_within_target"], abs=1e-3)


def test_exporter_refuses_a_tampered_or_mock_run(tmp_path):
    doc = _run(tmp_path, n=8)
    bad = json.loads(json.dumps(doc))
    d = next(x for x in bad["decisions"] if not x["single_option"])
    other = next(o for o in d["offered"] if o != d["jev_pick"])
    d["jev_pick"] = other                                                # recorded pick no longer matches the probs
    with pytest.raises(ejf.ReplayError):
        ejf.build(bad)
    f = tmp_path / "run.json"
    with pytest.raises(SystemExit):
        ejf.main(["--run", str(f), "--out", str(tmp_path / "b.js")])    # mock without --allow-mock
    assert ejf.main(["--run", str(f), "--allow-mock", "--out", str(tmp_path / "b.js")]) == 0


def _jev_bundle():
    t = (DEMO / "data" / "flow_jev_bundle.js").read_text(encoding="utf-8")
    assert t.startswith("window.FLOW_JEV_DATA = ")
    return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))


def test_committed_bundle_is_a_placeholder_or_a_real_model_run():
    b = _jev_bundle()
    assert b["format"] == "flow-jev-bundle/1"
    assert b["status"] in ("not_recorded", "recorded")
    for s in b["scenarios"]:
        assert s["mock"] is False and s["provenance"]["is_model"] is True, "a mock rehearsal must not ship"
        assert s["provenance"]["checkpoint_step"] == 2350


def test_flow_page_loads_the_jev_bundle_between_the_flow_bundle_and_flow_js():
    html = (DEMO / "flow.html").read_text(encoding="utf-8")
    i, j, k = html.index("data/flow_bundle.js"), html.index("data/flow_jev_bundle.js"), html.index('src="flow.js"')
    assert i < j < k
    assert 'id="jevsw"' in html and 'data-dec="jev"' in html
    js = (DEMO / "flow.js").read_text(encoding="utf-8")
    assert "FLOW_JEV_DATA" in js and "provenance_line" in js and "caveats" in js

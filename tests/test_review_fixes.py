"""Tests added by the independent review (docs/review.md)."""

import copy

from optimiser.analysis import reveal, score_edit
from optimiser.edits import apply, candidates
from pathway_sim import generate_patients, load_scenario, scenario_from_dict, simulate


def _fallback_scenario():
    return scenario_from_dict({
        "id": "fallback", "target_days": 42,
        "conditions": [{"id": "c", "cancer": True, "prevalence": 1.0}],
        "resources": {"r": {"type": "delay", "wait": 1}},
        "tests": {"a": {"resource": "r", "wait": 1, "p_nondiagnostic": 1.0},   # always non-diagnostic
                  "b": {"resource": "r", "wait": 1},
                  "c": {"resource": "r", "wait": 1}},
        "flowcharts": {"f": {"nodes": [
            {"id": "pick", "kind": "choice", "options": ["a", "b"]},
            {"id": "a", "test": "a", "retry": {"max": 0, "fallback": "b"}},
            {"id": "b", "test": "b"},
            {"id": "c", "test": "c", "after": ["b"]},
            {"id": "tx", "kind": "exit", "outcome": "treatment", "after_any": ["a", "c"]}]}},
    })


def test_forced_fallback_runs_its_downstream_steps():
    # Choice picks `a`, so `b` (and its strict descendant `c`, and `tx`) are skipped at choice time.
    # `a` fails and forces its fallback `b`; `c` and `tx` must then run, not stay skipped (patient was "stuck").
    sc = _fallback_scenario()
    run = simulate(sc, "f", generate_patients(sc, 5, 1), seed=1)
    for pr in run.patients:
        assert pr.outcome == "treatment"
        assert [e.node for e in pr.events] == ["a", "b", "c"]
        assert pr.cause["b"] == "a"


def test_proposal_scores_ignore_hidden_truth():
    # The optimiser's proposal side (reveal -> candidates -> score_edit -> apply) must give the same
    # proposals when every patient's hidden condition, cancer flag and pre-drawn results are scrambled
    # after the run (the run log itself, i.e. what a clinic would record, is unchanged).
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    fc = sc.flowcharts["observed"]
    run = simulate(sc, fc, generate_patients(sc, 200, 11), seed=11)
    servers = {rid for rid, r in sc.resources.items() if r.get("type", "server") == "server"}

    def proposals(r):
        pts = reveal(r, servers)
        out = []
        for c in candidates(sc, fc):
            c.score = score_edit(fc, pts, c)
            out.append((c.key(), round(c.score, 9), apply(sc, fc, c) is not None))
        return out

    before = proposals(run)
    scrambled = copy.deepcopy(run)
    for pr in scrambled.patients:
        pr.patient.condition = "scrambled"
        pr.patient.cancer = not pr.patient.cancer
        pr.patient.results = {}
        pr.patient.attributes = {}
    assert proposals(scrambled) == before


def _export():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("demo_export", Path(__file__).resolve().parent.parent / "demo" / "export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_suggested_change_label_matches_accepted_kinds():
    ex = _export()
    assert ex.suggested_change_label({"steps": [{"kind": "fast_track"}]}) == \
        "Suggested change: a fast lane (priority booking), same order, no new capacity"
    assert "new order and a fast lane" in ex.suggested_change_label({"steps": [{"kind": "relax"}, {"kind": "fast_track"}]})
    assert "new order," in ex.suggested_change_label({"steps": [{"kind": "detach"}]})


def test_sampling_label_says_triage_not_first_visit():
    # relax(sample_plan, visit) makes sample_plan wait only for the baseline CT (referral receipt)
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    from optimiser.edits import Edit
    new = apply(sc, sc.flowcharts["observed"], Edit("relax", "sample_plan", "visit"))
    assert new.nodes["sample_plan"].after == ["ct"]
    label = _export().polish_change(sc.flowcharts["observed"], "relax", "sample_plan", "visit")
    assert "triage" in label and "before the first hospital visit" in label


def test_small_fractions_are_not_shown_as_zero():
    ex = _export()
    assert ex.fmt_fraction(0.0035) == "0.35%"
    assert ex.fmt_fraction(0.013) == "1.3%"
    assert ex.fmt_fraction(0.4) == "40%"
    assert ex.fmt_fraction(0) == "0%"

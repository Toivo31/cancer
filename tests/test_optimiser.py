"""Optimiser tests: finds parallelism, respects information and clinical constraints, guardrails."""

from optimiser import Config, apply, candidates, search
from optimiser.edits import Edit
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate

from test_pathway_sim import tiny


def test_finds_parallel_order_and_reports_heldout():
    sc = tiny()
    res = search(sc, "serial", Config(n_train=300, heldout_seeds=(5, 6), max_steps=4), log=lambda *a: None)
    assert res["steps"], "expected at least one accepted change"
    assert res["heldout"]["after"]["median_days_to_treatment"] < res["heldout"]["before"]["median_days_to_treatment"]
    assert res["heldout"]["after"]["missed_cancers"] <= res["heldout"]["before"]["missed_cancers"]
    assert not res["guardrails_heldout"]


def test_cannot_schedule_decision_before_its_information():
    sc = tiny()
    fc = sc.flowcharts["serial"]
    # pet's guard reads the CT result: detaching pet from ct must be rejected
    assert apply(sc, fc, Edit("detach", "pet", "ct")) is None
    assert apply(sc, fc, Edit("relax", "pet", "ct")) is None


def test_treatment_still_waits_for_detached_step():
    sc = tiny()
    fc = sc.flowcharts["serial"]
    new = apply(sc, fc, Edit("relax", "ex", "pet"))
    assert new is not None
    pts = generate_patients(sc, 200, 3)
    run = simulate(sc, new, pts, seed=3)
    for pr in run.patients:
        if pr.outcome == "treatment":
            pet = [e for e in pr.events if e.node == "pet"]
            assert pet and pet[0].t_result <= pr.t_treatment + 1e-9


def test_needs_constraint_blocks_board_without_staging():
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    fc = sc.flowcharts["observed"]
    assert apply(sc, fc, Edit("detach", "mdt", "diagnosis")) is None          # would drop PET-CT before the board
    assert apply(sc, fc, Edit("detach", "mdt", "diagnosis/sampling_done")) is not None


def test_guardrail_blocks_skipping_tissue_sampling():
    from optimiser.search import cohorts, evaluate, guardrails
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    fc = sc.flowcharts["observed"]
    skip = apply(sc, fc, Edit("standardise", "sample_plan", "no_sampling"))
    tr = cohorts(sc, (7,), 400)
    m0, _ = evaluate(sc, fc, tr)
    m1, _ = evaluate(sc, skip, tr)
    assert m1["share_within_target"] > m0["share_within_target"]     # faster...
    assert "fewer tissue-confirmed diagnoses" in guardrails(m1, m0, Config())   # ...but rejected


def test_candidates_have_plain_language():
    sc = tiny()
    for c in candidates(sc, sc.flowcharts["serial"]):
        assert c.plain and "_" not in c.plain.split(":")[0]

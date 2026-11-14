"""M6-3: frequency trainer, patient-level evaluation, and the loop test (simulate, export, train, table within sampling error, rerun matches)."""

import copy
import math
from pathlib import Path

import pytest

import jev
from jev import dataset as D
from jev import training as T
from pathway_sim import compute_metrics, generate_patients, simulate
from pathway_sim.documents import documents_to_scenario
from service.templates import load_templates

ROOT = Path(__file__).resolve().parent.parent
TRUE = {"first_contact": {"default": {"nurse_visit": 0.3, "gp_visit": 0.7},
                          "rules": [{"when": "group == 'site_specific'", "probs": {"nurse_visit": 0.8, "gp_visit": 0.2}}]}}


@pytest.fixture(scope="module")
def loop():
    t = load_templates(ROOT / "scenarios")["finland_lung"]
    sc = documents_to_scenario(t["world"], t["flowcharts"])
    fc = sc.flowcharts["baseline"]
    fc.decision_policy = copy.deepcopy(fc.decision_policy)
    fc.decision_policy["points"]["first_contact"] = copy.deepcopy(TRUE["first_contact"])
    fc2, pol = jev.prepare(sc, fc, backend="stub", seed=1)
    pts = generate_patients(sc, 3500, 1)
    log = simulate(sc, fc2, pts, policy=pol, seed=1)
    return sc, fc2, pts, log


def test_loop_table_is_within_sampling_error_and_the_rerun_matches(loop):
    sc, fc, pts, log = loop
    ds = D.dataset_from_log(sc, fc, log, 1)
    res = jev.train("frequency", ds, sc, fc, {"context_fields": ["group"]})
    learned = res.artifact["points"]["first_contact"]
    # each cell against the generating probability, with the standard error of a proportion
    rows = [r for r in ds.rows if r["decision_point"] == "first_contact"]
    for cond, group, truth in (("site_specific", "site_specific", 0.8), ("rest", None, 0.3)):
        cell = [r for r in rows if (r["context"]["group"] == "site_specific") == (group is not None)]
        p_hat = (sum(r["chosen"] == "nurse_visit" for r in cell) + 1) / (len(cell) + 2)
        se = math.sqrt(truth * (1 - truth) / len(cell))
        want = "group == 'site_specific'" if group else "group == 'non_specific'"
        got = next(r["probs"]["nurse_visit"] for r in learned["rules"] if r["when"] == want)
        assert abs(got - truth) < 4 * se + 0.01, (cond, got, truth, se)
        assert abs(got - p_hat) < 0.05
    # the learned table is a valid stub table for this flowchart
    assert jev.StubBackend(res.artifact["points"]).validate_against(fc, sc) == []
    # a run with the learned table reproduces the original run's metrics within noise
    fc_l = fc.copy()
    fc_l.decision_policy = copy.deepcopy(fc.decision_policy)
    fc_l.decision_policy["points"].update(res.artifact["points"])
    fc3, pol3 = jev.prepare(sc, fc_l, backend="stub", seed=1)
    log2 = simulate(sc, fc3, pts, policy=pol3, seed=1)
    a, b = compute_metrics(log, sc), compute_metrics(log2, sc)
    # (the cancer subset is only a handful of patients at this n, so on-time share is too noisy to compare here)
    assert abs(a["tests_per_patient"] - b["tests_per_patient"]) < 0.05 * a["tests_per_patient"]
    assert abs(a["median_days_to_exit_noncancer"] - b["median_days_to_exit_noncancer"]) < 0.1 * a["median_days_to_exit_noncancer"] + 1
    nurse = lambda lg: sum(c["chosen"] == "nurse_visit" for p in lg.patients for c in p.choices) / len(lg.patients)
    assert abs(nurse(log) - nurse(log2)) < 0.03
    # rerunning the learned table is deterministic
    log3 = simulate(sc, fc3, pts, policy=jev.prepare(sc, fc_l, backend="stub", seed=1)[1], seed=1)
    assert compute_metrics(log3, sc) == b


def test_evaluation_is_by_patient_and_reports_baselines(loop):
    sc, fc, _, log = loop
    ds = D.dataset_from_log(sc, fc, log, 1)
    res = jev.train("frequency", ds, sc, fc, {"context_fields": ["group"]})
    ev = res.evaluation
    assert ev["split"] == "by patient" and ev["label"].startswith("Agreement")
    assert ev["holdout_rows"] > 300 and 0.1 < ev["holdout_patients"] / len({r["patient_id"] for r in ds.rows}) < 0.3
    # group matters at first_contact, so the table beats both baselines on held-out patients
    pt = ev["by_decision_point"]["first_contact"]
    assert pt["log_loss"] < pt["log_loss_uniform"] and pt["log_loss"] <= pt["log_loss_option_frequency"] + 1e-6
    assert all(0 <= p <= 1 and 0 <= o <= 1 for p, o in ev["calibration"])
    assert sum(ev["calibration_n"]) == sum(len(r["offered"]) for r in ds.rows if D.in_holdout(r["patient_id"], 0.2, 0))
    assert "reproduces practice" in res.notice


def test_outcome_is_never_read(loop):
    sc, fc, _, log = loop
    ds = D.dataset_from_log(sc, fc, log, 1)
    a = jev.train("frequency", ds, sc, fc, {"context_fields": ["group"]}).artifact["points"]
    for i, r in enumerate(ds.rows):
        r["outcome"] = {"usable_result": bool(i % 2)}
    assert jev.train("frequency", ds, sc, fc, {"context_fields": ["group"]}).artifact["points"] == a


def test_rare_cells_get_no_rule_of_their_own():
    from tests.test_dataset import good_row
    rows = [good_row(patient_id=f"p{i}", chosen="ttnb", t_days=40.0, context={**good_row()["context"], "attributes": {"location": "central"}})
            for i in range(60)]
    rows += [good_row(patient_id=f"q{i}", chosen="bronch", t_days=40.0, context={**good_row()["context"], "attributes": {"location": "peripheral"}})
             for i in range(3)]       # three rows, all bronch: a naive table would say 100% bronch
    pts, info = T.fit_frequency(rows, {"sample_choice": ["bronch", "ttnb"]}, ["attributes.location"], 30, 1.0)
    spec = pts["sample_choice"]
    assert all("peripheral" not in r["when"] for r in spec.get("rules", []))
    assert info["sample_choice"]["cells_dropped"][0]["rows"] == 3
    assert 0.0 < spec["default"]["bronch"] < 0.1             # smoothing keeps an unseen option above zero


def test_varying_offered_sets_are_fitted_for_the_stubs_renormalisation():
    rows = []
    for i in range(300):          # truth: a:b:c = 6:3:1; c is often unavailable
        offered = ["a", "b"] if i % 2 else ["a", "b", "c"]
        pick = ["a", "b"][i % 3 == 0] if i % 2 else ["a", "a", "a", "a", "a", "a", "b", "b", "b", "c"][i % 10]
        rows.append({"offered": offered, "chosen": pick})
    w = T.luce_weights(rows, ["a", "b", "c"], 1.0)
    assert abs(sum(w.values()) - 1) < 1e-9 and w["a"] > w["b"] > w["c"]
    full = [{"offered": ["a", "b", "c"], "chosen": o} for o in "aaabbc"]
    f = T.luce_weights(full, ["a", "b", "c"], 1.0)
    assert abs(f["a"] - 4 / 9) < 1e-6 and abs(f["c"] - 2 / 9) < 1e-6           # add-one frequency when everything is offered


def test_unknown_trainer_and_bad_field(loop):
    sc, fc, _, log = loop
    ds = D.dataset_from_log(sc, fc, log, 1)
    with pytest.raises(T.TrainingError):
        jev.train("jev", ds, sc, fc)
    with pytest.raises(ValueError):
        jev.train("frequency", ds, sc, fc, {"context_fields": ["colour"]})

"""Fast checks of the synthetic Finnish lung-cancer scenario (scenarios/finland_lung.yaml)."""
from collections import Counter
from pathlib import Path
from statistics import median

import pytest
import yaml

from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios" / "finland_lung.yaml"


@pytest.fixture(scope="module")
def sc():
    return load_scenario(SCEN)


@pytest.fixture(scope="module")
def baseline_run(sc):
    pts = generate_patients(sc, 6000, seed=1)          # ~136 days at 44 / day: past the 60-day warm-up
    return pts, simulate(sc, "baseline", pts, seed=1)


def test_loads_with_expected_flowcharts(sc):
    assert sc.clock_start == "first_contact"
    assert sc.target_days == 42
    assert sc.warmup_days >= 30
    assert "rate_per_day" in sc.arrivals
    assert {"baseline", "direct_ct", "bundled_workup", "fast_track_nonspecific"} <= set(sc.flowcharts)
    assert {g["id"] for g in sc.groups} == {"site_specific", "non_specific"}
    assert "42" in sc.description and "norwegian" in sc.description.lower()


def test_every_parameter_has_a_known_source():
    raw = yaml.safe_load(SCEN.read_text())
    ids = {s["id"] for s in yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())} | {"assumption"}
    blocks = [raw["conditions"], raw["groups"], list(raw["resources"].values()), list(raw["tests"].values()),
              list(raw["attributes"].values()), [raw["age"]]]
    for block in blocks:
        for item in block:
            assert item.get("source") in ids, item
    for fc in raw["flowcharts"].values():
        for cfg in (fc.get("policy") or {}).values():
            assert cfg.get("source", "assumption") in ids


def test_prevalence_is_realistically_low(sc):
    cancer = sum(c["prevalence"] for c in sc.conditions if c.get("cancer"))
    assert 0.01 <= cancer <= 0.05
    assert len(sc.conditions) >= 5


def test_baseline_has_no_stuck_patients_and_queues_form(sc, baseline_run):
    pts, run = baseline_run
    outcomes = Counter(pr.outcome for pr in run.patients)
    assert set(outcomes) <= {"treatment", "discharged"}, outcomes
    assert sum(1 for p in pts if p.cancer) >= 40
    m = compute_metrics(run, sc)
    assert m["stuck"] == 0
    assert m["n_cancer"] >= 20
    # queues: the specialist clinic and the CT book ahead, so waits are days, not hours
    waits = {}
    for pr in run.patients:
        for e in pr.events:
            waits.setdefault(e.resource, []).append(e.t_start - e.t_ready)
    assert median(waits["clinic"]) >= 8
    assert median(waits["gp_appt"]) >= 8
    assert median(waits["ct_scanner"]) >= 3
    assert max(waits["bronchoscopy"]) >= 5


def test_cancers_found_missed_and_both_groups_present(sc, baseline_run):
    _, run = baseline_run
    m = compute_metrics(run, sc)
    assert m["median_days_to_treatment"] is not None
    assert 60 <= m["median_days_to_treatment"] <= 160          # Finnish first contact -> treatment is about 100 days
    assert 1 <= m["missed_cancers"] < 0.3 * m["n_cancer"]       # chest X-ray misses exist, safety net catches most
    assert set(m["by_group"]) == {"site_specific", "non_specific"}
    assert all(g["n"] > 0 for g in m["by_group"].values())
    assert m["median_days_to_exit_noncancer"] is not None and m["median_days_to_exit_noncancer"] < 60


def test_missed_cancers_are_discharged_cancers(baseline_run):
    _, run = baseline_run
    discharged = [pr for pr in run.patients if pr.outcome == "discharged" and pr.patient.cancer]
    assert discharged
    assert all(pr.t_treatment is None for pr in discharged)


@pytest.mark.parametrize("fid", ["direct_ct", "bundled_workup", "fast_track_nonspecific", "baseline_plus_capacity"])
def test_alternative_flowcharts_run_without_stuck_patients(sc, fid):
    pts = generate_patients(sc, 1500, seed=2)
    run = simulate(sc, fid, pts, seed=2)
    assert all(pr.outcome in ("treatment", "discharged") for pr in run.patients)


def test_fast_track_marks_only_non_specific_presenters(sc):
    pts = generate_patients(sc, 3000, seed=3)
    run = simulate(sc, "fast_track_nonspecific", pts, seed=3)
    prio = [pr for pr in run.patients if pr.priority]
    assert prio and all(pr.patient.group == "non_specific" for pr in prio)

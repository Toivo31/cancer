"""WP-W4-1: pins the tuned encounter loop's key numbers (small n, fixed seed) so a later change to the care model,
the decision tables, the resources or the engine shows up in the gate. The numbers are the loop with PLACEHOLDER
decisions (D51), not findings; the full consistency check and the finding are scripts/encounter_report.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathway_sim.encounter import load_world, outcomes, run_encounter

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tuned():
    log = run_encounter(load_world(ROOT / "scenarios/finland_encounter.yaml"), 1500, 1)
    return outcomes(log)["overall"]


def test_tuned_run_key_numbers(tuned):
    # observed 2026-11-14 (n=1500, seed 1, no warm-up): referred 0.218, GP 4.54, episodes 2.4, tests 1.4, 562 EUR
    assert tuned["n"] == 1500
    assert 0.15 <= tuned["referral_share"] <= 0.30
    assert 3.5 <= tuned["gp_encounters_per_patient"] <= 5.5
    assert 1.9 <= tuned["episodes_per_patient"] <= 3.0
    assert 1.0 <= tuned["tests_per_patient"] <= 1.9
    assert 430 <= tuned["cost_per_patient_eur"] <= 700
    assert tuned["cancers"] >= 10 and tuned["cancer_treated_share"] >= 0.6


def test_tuned_values_are_recorded_with_old_values():
    care = (ROOT / "catalogue/lung-primary-care/care.yaml").read_text()
    assert "return_if_persisting: {p: 0.95" in care and "was 0.7" in care
    assert "median: 14, p90: 35" in care and "was median 21" in care


def test_report_json_if_present():
    p = ROOT / "docs/review_checks/encounter_results.json"
    if not p.exists():
        pytest.skip("run scripts/encounter_report.py")
    d = json.loads(p.read_text())
    assert d["format"] == "encounter_results/1" and "placeholder" in d["decisions"]
    assert set(d["consistency"]) >= {"ref_med", "ref28", "ref42", "referred", "treated", "within90", "noncancer_referred"}
    assert all("tolerance" in c and "passes" in c for c in d["consistency"].values())

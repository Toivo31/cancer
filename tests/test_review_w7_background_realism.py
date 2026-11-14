"""Review w7, finding M4: background fields of synthetic patients are drawn without a population model.

``patient_engine/skeleton.py::_draw_background``: age is a normal centred in 18..100 for every condition,
smoking status is uniform over three levels, sex ignores the condition, and pack-years (since the fix) depends
on smoking status but not on age. Fixed by the population model (populations/lung_primary_care.yaml,
patient_engine/population.py); these tests guard ``libraries/ref500``. The thresholds are generous
(Finnish lung cancer: median age at diagnosis about 70, under-50s a few percent, never-smokers 10 to 15%).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "libraries" / "ref500" / "cards.jsonl.gz"


@pytest.fixture(scope="module")
def cards():
    if not LIB.exists():
        pytest.skip("libraries/ref500 not present")
    with gzip.open(LIB, "rt") as f:
        return [json.loads(line) for line in f]


def _cancers(cards):
    return [c for c in cards if c["hidden"]["conditions"][0]["id"] == "lung_cancer"]


def test_lung_cancer_patients_are_mostly_older(cards):
    ca = _cancers(cards)
    under_50 = sum(1 for c in ca if c["background"]["age"] < 50) / len(ca)
    assert under_50 <= 0.10, f"{under_50:.0%} of lung-cancer cards are under 50 (Finland: a few percent)"


def test_pack_years_fit_inside_a_smoking_life(cards):
    """At most two packs a day from age 12: pack_years <= 2 * (age - 12)."""
    bad = [c["id"] for c in cards if c["background"]["pack_years"] > 2 * (c["background"]["age"] - 12)]
    assert not bad, f"{len(bad)} cards smoke more than two packs a day since age 12, e.g. {bad[:3]}"


def test_smoking_mix_matches_the_catalogues_own_assumption(cards):
    """The lung-cancer prevalence note assumes presenters are never 0.40 / former 0.38 / current 0.22; the
    generator draws a third each. Non-cancer cards (where prevalence barely depends on smoking) show it."""
    other = [c for c in cards if c["hidden"]["conditions"][0]["id"] in ("viral_self_limiting", "no_disease_found",
                                                                       "worried_well", "reflux_postinfectious_cough")]
    current = sum(1 for c in other if c["background"]["smoking_status"] == "current") / len(other)
    assert current <= 0.30, f"{current:.0%} current smokers among non-cancer presenters (catalogue note assumes 22%)"

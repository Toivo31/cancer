"""Population model for synthetic backgrounds (review w7 M4): params/population_lung_primary_care.yaml."""

from __future__ import annotations

from collections import Counter
from statistics import median

import pytest

from patient_engine.catalogue import load_catalogue
from patient_engine.population import STATUSES, get_model
from patient_engine.skeleton import _draw_primary_and_background, make_design, proportional_design

CAT = "catalogue/lung-primary-care"
LOCKED_HASH_PREFIX = "2bcb9c78b2e0"        # catalogue-v1


@pytest.fixture(scope="module")
def cat():
    return load_catalogue(CAT)


@pytest.fixture(scope="module")
def model(cat):
    return get_model(cat)


@pytest.fixture(scope="module")
def proportional(cat):
    d = proportional_design(6000)
    return [_draw_primary_and_background(cat, d, i, 7) for i in range(6000)]


@pytest.fixture(scope="module")
def stratified(cat):
    d = make_design(cat, {"lung_cancer": 400, "copd_exacerbation": 300, "asthma": 300, "worried_well": 300,
                          "heart_failure": 200})
    return [_draw_primary_and_background(cat, d, i, 7) for i in range(d.n)]


def test_catalogue_hash_is_unchanged_and_model_is_outside_the_catalogue(cat, model):
    assert cat.version_hash.startswith(LOCKED_HASH_PREFIX), "catalogue-v1 is locked; do not edit catalogue/"
    assert model is not None
    assert "population" not in cat.raw and not any("population" in k for k in cat.raw)


def test_overall_smoking_mix_is_the_catalogues_assumption(model):
    mix = [sum(model.w[b] * model.sex_p[sx] * model.p_smoke[sx][model._coarse(b)][i]
               for sx in model.sexes for b in range(model.nb)) for i in range(3)]
    assert mix == pytest.approx([0.40, 0.38, 0.22], abs=1e-6)


def test_condition_shares_per_smoking_level_are_the_catalogues(cat, model):
    assert model.max_fit_error < 1e-9
    overall = sum(model.pop_b[2][b] * model.Q[2][b]["lung_cancer"] for b in range(model.nb))
    assert overall == pytest.approx(0.0323 / sum(max(0, float(c.prevalence.resolve({"smoking_status": "current"})))
                                                 for c in cat.conditions.values()), rel=1e-6)
    total = sum(model.w[b] * model.sex_p[sx] * model.p_smoke[sx][model._coarse(b)][i] * model.Q[i][b]["lung_cancer"]
                for sx in model.sexes for b in range(model.nb) for i in range(3))
    assert total == pytest.approx(0.013, abs=2e-4)          # the catalogue's overall lung-cancer prevalence


def test_deterministic(cat):
    d = proportional_design(100)
    assert _draw_primary_and_background(cat, d, 5, 3) == _draw_primary_and_background(cat, d, 5, 3)
    assert _draw_primary_and_background(cat, d, 5, 3) != _draw_primary_and_background(cat, d, 6, 3)


def test_pack_years_possible_for_age(proportional, model):
    for _, bg in proportional:
        if bg["smoking_status"] == "never":
            assert bg["pack_years"] == 0
        else:
            assert 1 <= bg["pack_years"] <= model.max_pack_years(bg["age"]), bg
    young = [bg["pack_years"] for _, bg in proportional if bg["age"] < 30 and bg["smoking_status"] != "never"]
    assert young and max(young) <= 30


def test_proportional_mix_and_prevalence(proportional):
    n = len(proportional)
    mix = Counter(bg["smoking_status"] for _, bg in proportional)
    assert mix["current"] / n == pytest.approx(0.22, abs=0.02)
    assert mix["never"] / n == pytest.approx(0.40, abs=0.02)
    cancer = sum(1 for c, _ in proportional if c == "lung_cancer") / n
    assert cancer == pytest.approx(0.013, abs=0.005)


def test_lung_cancer_is_older_and_asthma_younger_in_both_modes(proportional, stratified):
    for rows in (proportional, stratified):
        age = {c: [bg["age"] for cc, bg in rows if cc == c] for c in ("lung_cancer", "copd_exacerbation", "asthma",
                                                                      "worried_well")}
        if len(age["lung_cancer"]) < 30:      # the proportional draw has few cancers
            continue
        assert 64 <= median(age["lung_cancer"]) <= 74
        assert sum(a < 50 for a in age["lung_cancer"]) / len(age["lung_cancer"]) <= 0.10
        assert median(age["copd_exacerbation"]) >= 62
        assert median(age["asthma"]) <= 58 and median(age["worried_well"]) <= 52


def test_stratified_cancers_are_mostly_ever_smokers(stratified):
    ca = [bg for c, bg in stratified if c == "lung_cancer"]
    never = sum(bg["smoking_status"] == "never" for bg in ca) / len(ca)
    assert 0.06 <= never <= 0.20          # catalogue note: about 12%; Finnish programme 10 to 15%


def test_other_catalogues_keep_the_old_default():
    tiny = load_catalogue("catalogue/_examples/tiny")
    assert get_model(tiny) is None

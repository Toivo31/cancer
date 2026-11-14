"""Cohort assembly (WP-C1-6): reproducibility, prefix stability (I2), prevalence, arrivals, compact arrays."""

from __future__ import annotations

import gzip
import statistics

import pytest

from patient_engine.card import CohortSpec
from patient_engine.cohort import (BLOCK, NEGATIVE, NO_ATTEMPT, NON_DIAGNOSTIC, POSITIVE, CohortError,
                                   draw_cohort)
from patient_engine.library import load_library, write_library
from test_pe_library_support import CONDITIONS, build_library, make_cards, tiny_catalogue, wide_catalogue

PREV = {"lung_cancer": 0.016, "pneumonia": 0.25, "healthy": 0.734}


@pytest.fixture(scope="module")
def lib_cat(tmp_path_factory):
    lib, cat = build_library(tmp_path_factory.mktemp("c") / "lib", per_condition=30)
    return lib, cat


def spec(lib, n, seed=1, prevalence=None):
    return CohortSpec(library_id=lib.id, prevalence=dict(prevalence or PREV), n=n, seed=seed)


# ---------------------------------------------------------------- reproducibility (I2)

def test_same_spec_gives_equal_cohorts(lib_cat):
    lib, _ = lib_cat
    a, b = draw_cohort(lib, spec(lib, 3000)), draw_cohort(lib, spec(lib, 3000))
    assert a == b and a.fingerprint() == b.fingerprint()
    assert draw_cohort(lib, spec(lib, 3000, seed=2)).fingerprint() != a.fingerprint()
    assert draw_cohort(lib, spec(lib, 3000), {"rate_per_day": 44}).fingerprint() != a.fingerprint()


def test_reloading_the_library_gives_the_same_cohort(lib_cat, tmp_path):
    lib, cat = lib_cat
    again = load_library(lib.path, cat)
    assert draw_cohort(again, spec(again, 2500)).fingerprint() == draw_cohort(lib, spec(lib, 2500)).fingerprint()


def test_prevalence_dict_order_and_scale_do_not_matter(lib_cat):
    lib, _ = lib_cat
    a = draw_cohort(lib, spec(lib, 2000, prevalence=PREV))
    b = draw_cohort(lib, spec(lib, 2000, prevalence=dict(reversed(list(PREV.items())))))
    c = draw_cohort(lib, spec(lib, 2000, prevalence={k: v * 7 for k, v in PREV.items()}))
    assert a.card_index == b.card_index and a.card_index == c.card_index and a.arrival == b.arrival


@pytest.mark.parametrize("arrivals", [None, {"spread_days": 90}, {"rate_per_day": 44}])
@pytest.mark.parametrize("small,big", [(1000, 2000), (700, 1500), (1, 1001), (0, 10)])
def test_changing_n_keeps_the_earlier_patients(lib_cat, small, big, arrivals):
    lib, _ = lib_cat
    a = draw_cohort(lib, spec(lib, small), arrivals)
    b = draw_cohort(lib, spec(lib, big), arrivals)
    assert (a.card_index, a.condition, a.arrival) == (b.card_index[:small], b.condition[:small], b.arrival[:small])
    assert [a.card(i) for i in range(small)] == [b.card(i) for i in range(small)]


def test_a_cohort_card_belongs_to_the_drawn_condition(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 2500))
    assert all(c.card(i).primary_condition == c.condition[i] for i in range(c.n))
    assert c.n == len(c) == 2500


# ---------------------------------------------------------------- prevalence

@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_prevalence_of_20000_within_half_a_point(lib_cat, seed):
    lib, _ = lib_cat
    assert min(len(v) for v in lib.by_condition.values()) >= 30
    c = draw_cohort(lib, spec(lib, 20000, seed=seed))
    for cond, share in PREV.items():
        assert abs(c.condition_counts()[cond] / 20000 - share) < 0.005, (cond, seed)
    # the stratified draw is much tighter than the 0.5 pp the plan asks for
    assert max(abs(c.condition_counts()[k] / 20000 - v) for k, v in PREV.items()) < 0.0006


def test_prevalence_holds_when_the_library_mix_differs_and_for_a_partial_block(tmp_path):
    cat = tiny_catalogue()
    cards = (make_cards(30, cat.version_hash, "A", ("lung_cancer",)) + make_cards(5, cat.version_hash, "A", ("pneumonia",))
             + make_cards(60, cat.version_hash, "A", ("healthy",)))
    write_library(cards, cat, tmp_path / "lib")
    lib = load_library(tmp_path / "lib", cat)
    prev = {"lung_cancer": 0.3, "pneumonia": 0.2, "healthy": 0.5}
    for n in (20000, 1500, 450):
        c = draw_cohort(lib, spec(lib, n, prevalence=prev))
        for cond, share in prev.items():
            assert abs(c.condition_counts()[cond] / n - share) < (0.005 if n >= 1000 else 0.05), (n, cond)
    assert c.distinct_cards <= 450


def test_each_full_block_has_the_expected_counts(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 3 * BLOCK))
    for b in range(3):
        counts = {k: c.condition[b * BLOCK:(b + 1) * BLOCK].count(k) for k in PREV}
        assert sum(counts.values()) == BLOCK
        assert all(abs(counts[k] - PREV[k] * BLOCK) < 1.0 + 1e-9 for k in PREV), counts
    # the conditions are mixed, not laid out in runs
    runs = sum(1 for i in range(1, BLOCK) if c.condition[i] != c.condition[i - 1])
    assert runs > 0.3 * BLOCK


def test_zero_share_conditions_need_no_cards(tmp_path):
    cat = tiny_catalogue()
    write_library(make_cards(5, cat.version_hash, "Z", ("lung_cancer", "healthy")), cat, tmp_path / "lib")
    lib = load_library(tmp_path / "lib", cat)
    c = draw_cohort(lib, spec(lib, 500, prevalence={"lung_cancer": 0.2, "healthy": 0.8, "pneumonia": 0.0, "other": 0}))
    assert set(c.condition) == {"lung_cancer", "healthy"}


def test_distinct_cards_counts_repeats(lib_cat):
    lib, _ = lib_cat
    assert draw_cohort(lib, spec(lib, 6)).distinct_cards <= 6
    big = draw_cohort(lib, spec(lib, 20000))
    assert 80 <= big.distinct_cards <= 90                       # a big cohort repeats cards
    assert big.distinct_cards == len(set(big.card_index))


# ---------------------------------------------------------------- arrivals

def test_spread_arrivals_are_uniform_over_the_window(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 5000), {"spread_days": 100})
    assert 0 <= min(c.arrival) and max(c.arrival) < 100
    assert abs(statistics.mean(c.arrival) - 50) < 2
    assert draw_cohort(lib, spec(lib, 5)).arrivals == {"spread_days": 365.0}


def test_rate_arrivals_are_a_poisson_stream(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 5000), {"rate_per_day": 44})
    assert list(c.arrival) == sorted(c.arrival)
    assert abs(c.arrival[-1] / 5000 - 1 / 44) < 0.002


def test_arrival_matches_the_simulators_own_draw(lib_cat):
    """Same keys as pathway_sim.patients: spread * uniform(seed, i, "arrival")."""
    from pathway_sim.dists import uniform
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 50, seed=9), {"spread_days": 200})
    assert c.arrival == tuple(200.0 * uniform(9, i, "arrival") for i in range(50))


# ---------------------------------------------------------------- refusals

def test_bad_specs_are_refused(lib_cat):
    lib, _ = lib_cat
    with pytest.raises(CohortError, match="library"):
        draw_cohort(lib, CohortSpec("L_other", PREV, 10, 1))
    with pytest.raises(CohortError, match="no cards"):
        draw_cohort(lib, spec(lib, 10, prevalence={"lung_cancer": 0.1, "mesothelioma": 0.9}))
    with pytest.raises(CohortError, match="zero"):
        draw_cohort(lib, spec(lib, 10, prevalence={"lung_cancer": 0}))
    with pytest.raises(CohortError):
        draw_cohort(lib, spec(lib, 10, prevalence={"lung_cancer": -1, "healthy": 2}))
    with pytest.raises(CohortError):
        draw_cohort(lib, spec(lib, 10, prevalence={"lung_cancer": float("nan")}))
    with pytest.raises(CohortError):
        draw_cohort(lib, spec(lib, -1))
    with pytest.raises(CohortError):
        draw_cohort(lib, spec(lib, 10), {"rate_per_day": 0})
    with pytest.raises(CohortError):
        draw_cohort(lib, spec(lib, 10), {})
    assert draw_cohort(lib, spec(lib, 0)).n == 0


# ---------------------------------------------------------------- handles

def test_cohort_handles_use_an_opaque_label_and_serve_the_patients_card(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 40))
    h = c.handle(7)
    assert h.card_id == "P000007" and h.card_id != c.card(7).id
    assert h.visible().card_id == "P000007"
    assert h.reveal("chest_xray", 1).values == c.card(7).attempt("chest_xray", 1).values
    assert h.truth_for_scoring()[0].id == c.condition[7]
    with pytest.raises(IndexError):
        c.handle(40)


def test_a_repeated_card_gives_the_same_results_for_different_patients(lib_cat):
    lib, _ = lib_cat
    c = draw_cohort(lib, spec(lib, 3000))
    first = {}
    for i in range(c.n):
        first.setdefault(c.card_index[i], i)
    pairs = [(i, first[ci]) for i, ci in enumerate(c.card_index) if first[ci] != i][:200]
    assert pairs
    for i, j in pairs:
        for t, a in (("chest_xray", 0), ("chest_xray", 1), ("blood_count", 0), ("chest_ct", 0)):
            x, y = c.handle(i).reveal(t, a), c.handle(j).reveal(t, a)
            assert x == y


# ---------------------------------------------------------------- compact arrays

def test_arrays_agree_with_the_handle_for_every_cell(lib_cat):
    lib, cat = lib_cat
    c = draw_cohort(lib, spec(lib, 300, prevalence={"lung_cancer": 0.3, "pneumonia": 0.3, "healthy": 0.4}))
    arr = c.to_arrays(cat)
    assert arr.n == 300 and arr.attempts == 3 and arr.tests == tuple(cat.tests)
    assert len(arr.results) == 300 * 4 * 3
    seen = set()
    for p in range(c.n):
        h = c.handle(p)
        assert arr.conditions[arr.condition[p]] == c.condition[p] and arr.card_index[p] == c.card_index[p]
        assert arr.arrival[p] == c.arrival[p]
        for ti, t in enumerate(arr.tests):
            for a in range(arr.attempts):
                code = arr.code(p, ti, a)
                seen.add(code)
                if a >= h.max_attempts(t):
                    assert code == NO_ATTEMPT
                    continue
                obs = h.reveal(t, a)
                if obs.status != "ok":
                    assert code == NON_DIAGNOSTIC and arr.positive(p, t, a) is None
                else:
                    assert code == (POSITIVE if cat.tests[t].is_positive(obs.values) else NEGATIVE)
                    assert arr.positive(p, t, a) is bool(code)
    assert seen == {NEGATIVE, POSITIVE, NON_DIAGNOSTIC, NO_ATTEMPT}


def test_arrays_have_no_report_text(lib_cat):
    lib, cat = lib_cat
    arr = draw_cohort(lib, spec(lib, 200)).to_arrays(cat)
    texts = {a.report for card in lib.cards for atts in card.observations["all_active"].values() for a in atts}
    blob = repr(arr.__dict__.keys()) + repr(arr.conditions) + repr(arr.tests) + arr.library_id
    assert not any(t in blob for t in texts)
    assert isinstance(arr.results, bytes) and set(arr.results) <= {0, 1, 2, 3, 4}


def test_arrays_need_the_matching_catalogue(lib_cat):
    lib, cat = lib_cat
    c = draw_cohort(lib, spec(lib, 20))
    assert c.to_arrays().catalogue_hash == cat.version_hash         # the library was loaded with it
    bare = load_library(lib.path)
    with pytest.raises(CohortError, match="needs the catalogue"):
        draw_cohort(bare, spec(bare, 20)).to_arrays()
    other = tiny_catalogue()
    object.__setattr__(other, "version_hash", "f" * 64)
    with pytest.raises(CohortError, match="differs"):
        c.to_arrays(other)
    with pytest.raises(CohortError, match="not served"):
        c.to_arrays(cat, state="all_resolved")


def test_size_of_20000_patients_x_20_tests_x_3_attempts(tmp_path, capsys):
    """Measured: the compact form for the simulator. The plan's ceiling is 50 MB."""
    cat, widen = wide_catalogue(tmp_path / "wide", n_tests=20)
    assert len(cat.tests) == 20
    cards = [widen(d) for d in make_cards(30, cat.version_hash)]
    write_library(cards, cat, tmp_path / "wide_lib", check_catalogue_hash=True)
    lib = load_library(tmp_path / "wide_lib", cat)
    c = draw_cohort(lib, spec(lib, 20000), {"rate_per_day": 44})
    arr = c.to_arrays()
    assert (arr.n, len(arr.tests), arr.attempts) == (20000, 20, 3)
    assert len(arr.results) == 20000 * 20 * 3
    size = arr.nbytes
    gz = len(gzip.compress(arr.results + arr.card_index.tobytes() + arr.arrival.tobytes(), 6))
    with capsys.disabled():
        print(f"\n[WP-C1-6] compact arrays, 20 000 patients x 20 tests x 3 attempts: {size:,} bytes "
              f"({size / 1e6:.2f} MB; results {len(arr.results):,} B, gzip of all arrays {gz:,} B)")
    assert size < 50 * 1024 * 1024
    assert size < 2 * 1024 * 1024                                       # in fact about 1.4 MB

"""Skeletons, the library design and the nominal error plan (WP-C1-3, tickets T1, T2, T5)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from patient_engine.catalogue import load_catalogue
from patient_engine.skeleton import (Design, default_counts, design_library, design_table, make_design,
                                     make_skeleton, proportional_design, skeleton_from_json)

ROOT = Path(__file__).resolve().parent.parent
TINY = ROOT / "catalogue" / "_examples" / "tiny"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


# ---------------------------------------------------------------- determinism (I2)

def test_same_inputs_give_equal_skeletons(tiny):
    d = proportional_design(1000)
    assert make_skeleton(tiny, 17, d, 5) == make_skeleton(tiny, 17, d, 5)
    assert make_skeleton(tiny, 17, d, 5) != make_skeleton(tiny, 17, d, 6)
    assert design_library(tiny, None, None, 5) == design_library(tiny, None, None, 5)


def test_changing_n_does_not_change_card_17(tiny):
    a = make_skeleton(tiny, 17, proportional_design(100, 0.3), 5)
    b = make_skeleton(tiny, 17, proportional_design(50_000, 0.3), 5)
    assert a == b


def test_stratified_card_numbers_do_not_depend_on_other_counts(tiny):
    """Which condition card 3 gets is the design's business; once it is the same condition, the rest of
    the card is the same whatever the other counts."""
    a = make_skeleton(tiny, 3, make_design(tiny, {"lung_cancer": 40, "pneumonia": 40, "healthy": 40}), 9)
    for extra in range(1, 30):
        b = make_skeleton(tiny, 3, make_design(tiny, {"lung_cancer": 40 + extra, "pneumonia": 40, "healthy": 40}), 9)
        if b.primary == a.primary:
            assert (a.background, a.attributes, a.brief, a.coexisting) == (b.background, b.attributes, b.brief, b.coexisting)
            assert a.error_plan == b.error_plan
            return
    pytest.fail("no pair of designs gave card 3 the same condition")


def test_stratified_counts_are_exact_and_mixed(tiny):
    sks = design_library(tiny, None, None, 3)
    d = default_counts(tiny)
    assert d == {"lung_cancer": 300, "pneumonia": 150, "healthy": 150}
    assert Counter(s.primary for s in sks) == Counter(d)
    # shuffled: the first 60 cards are not all one condition
    assert len({s.primary for s in sks[:60]}) == 3
    assert [s.index for s in sks] == list(range(len(sks)))
    assert len({s.id for s in sks}) == len(sks)


# ---------------------------------------------------------------- prevalence and background

def test_prevalence_of_50000_proportional_skeletons(tiny):
    d = proportional_design(50_000)
    counts = Counter(make_skeleton(tiny, i, d, 11, plan=False).primary for i in range(d.n))
    for cid, cond in tiny.conditions.items():
        share = counts[cid] / d.n
        assert abs(share - cond.prevalence.params["value"]) < 0.005, (cid, share)


def test_stratified_cancers_show_the_smoking_mix_the_prevalence_implies(tiny):
    """Prevalence by smoking status is 0.004 / 0.016 / 0.03, so among cancers about 60% are current smokers
    and 8% never smokers (uniform background); healthy cards stay near a third each."""
    sks = design_library(tiny, {"lung_cancer": 1500, "healthy": 1500}, None, 4)
    sm = {c: Counter(s.background["smoking_status"] for s in sks if s.primary == c) for c in ("lung_cancer", "healthy")}
    assert 0.52 < sm["lung_cancer"]["current"] / 1500 < 0.67
    assert sm["lung_cancer"]["never"] / 1500 < 0.15
    assert 0.28 < sm["healthy"]["never"] / 1500 < 0.38


def test_background_fields_are_complete_and_in_range(tiny):
    for s in design_library(tiny, {"lung_cancer": 60, "healthy": 60}, None, 1):
        assert list(s.background) == list(tiny.background)
        assert 18 <= s.background["age"] <= 100
        assert s.background["sex"] in ("f", "m")
        assert s.background["smoking_status"] in ("never", "former", "current")


def test_attributes_follow_the_catalogue(tiny):
    sks = design_library(tiny, {"lung_cancer": 3000, "healthy": 5}, None, 2)
    cancers = [s for s in sks if s.primary == "lung_cancer"]
    assert all(set(s.attributes) == {"stage", "location"} for s in cancers)
    stage = Counter(s.attributes["stage"] for s in cancers)
    assert abs(stage["IV"] / len(cancers) - 0.35) < 0.03
    assert all(s.attributes == {} for s in sks if s.primary == "healthy")


# ---------------------------------------------------------------- co-existing illness

def test_coexisting_follows_catalogue_shares_by_default(tiny):
    sks = design_library(tiny, {"lung_cancer": 3000, "pneumonia": 500, "healthy": 500}, None, 8)
    cancers = [s for s in sks if s.primary == "lung_cancer"]
    share = sum(s.coexisting == "pneumonia" for s in cancers) / len(cancers)
    assert abs(share - 0.10) < 0.02
    assert all(s.coexisting is None for s in sks if s.primary != "lung_cancer")


def test_coexisting_rate_overrides_and_is_exact_in_expectation(tiny):
    sks = design_library(tiny, {"lung_cancer": 2000, "healthy": 100}, 0.4, 8)
    cancers = [s for s in sks if s.primary == "lung_cancer"]
    assert abs(sum(s.coexisting is not None for s in cancers) / len(cancers) - 0.4) < 0.03
    assert all(s.coexisting is None for s in design_library(tiny, {"lung_cancer": 200}, 0.0, 8))
    assert all(s.coexisting == "pneumonia" for s in design_library(tiny, {"lung_cancer": 200}, 1.0, 8))
    with pytest.raises(ValueError):
        make_design(tiny, None, 1.5)


def test_design_table_counts_pairs(tiny):
    sks = design_library(tiny, {"lung_cancer": 400, "healthy": 100}, 0.5, 8)
    t = design_table(sks)
    assert t["n"] == 500 and t["by_primary"] == {"healthy": 100, "lung_cancer": 400}
    assert t["pairs"].keys() == {"lung_cancer+pneumonia"} and t["with_coexisting"] == t["pairs"]["lung_cancer+pneumonia"]


def test_bad_designs_are_refused(tiny):
    with pytest.raises(ValueError, match="unknown condition"):
        make_design(tiny, {"flu": 3})
    with pytest.raises(ValueError):
        make_design(tiny, {"lung_cancer": 0})
    with pytest.raises(IndexError):
        make_skeleton(tiny, 99, proportional_design(10), 1)


# ---------------------------------------------------------------- the nominal error plan

def test_error_plan_shape_and_attempt_counts(tiny):
    s = make_skeleton(tiny, 0, proportional_design(10), 1)
    plan = s.error_plan["all_active"]
    assert set(plan) == set(tiny.tests)
    for tid, t in tiny.tests.items():
        assert len(plan[tid]) == t.max_attempts
        for p in plan[tid]:
            assert p.status in ("ok", "non_diagnostic")
            assert (set(p.outputs) == set(t.output_ids)) if p.status == "ok" else p.outputs == {}
    assert len(plan["chest_ct"]) == 2          # the test's own max_attempts


def test_error_plan_rates_match_the_catalogue(tiny):
    d = proportional_design(6000)
    c = Counter()
    nd = Counter()
    for i in range(d.n):
        for p in make_skeleton(tiny, i, d, 2).error_plan["all_active"]["chest_xray"]:
            nd[p.status] += 1
            if p.status == "ok":
                c[p.outputs["consolidation"]] += 1
    assert abs(nd["non_diagnostic"] / sum(nd.values()) - 0.02) < 0.006
    n = sum(c.values())
    # nominal plan on the consolidation output: miss with 1 - 0.8, false alarm with 1 - 0.95 (per unit u)
    assert abs(c["miss"] / n - 0.2) < 0.02 and abs(c["false_alarm"] / n - 0.05) < 0.01


def test_continuous_plan_marks_only_large_errors_as_wrong(tiny):
    d = proportional_design(4000)
    outs = [p.outputs["crp"] for i in range(d.n) for p in make_skeleton(tiny, i, d, 2).error_plan["all_active"]["blood_count"]
            if p.status == "ok"]
    assert set(outs) == {"correct", "wrong"}
    assert abs(outs.count("wrong") / len(outs) - 0.05) < 0.01


def test_plan_false_does_not_draw_the_plan(tiny):
    s = make_skeleton(tiny, 4, proportional_design(10), 1, plan=False)
    assert s.error_plan is None
    full = make_skeleton(tiny, 4, proportional_design(10), 1)
    assert dataclasses.replace(full, error_plan=None) == s


def test_skeleton_json_round_trip(tiny):
    for i in range(5):
        s = make_skeleton(tiny, i, proportional_design(10, 0.5), 3)
        assert skeleton_from_json(json.loads(json.dumps(s.to_json()))) == s
    with pytest.raises(ValueError):
        skeleton_from_json({"format": "x"})


def test_attribute_that_reads_a_variable_is_refused(tiny):
    raw = json.loads(json.dumps(tiny.raw))                      # deep copy
    cond = next(c for c in raw["conditions"] if c["id"] == "lung_cancer")
    cond["attributes"]["stage"]["by"] = {"lung_lesion": {"true": {"values": {"I": 1, "II": 0, "III": 0, "IV": 0}}}}
    from patient_engine.catalogue import build_catalogue
    cat = build_catalogue(raw)
    with pytest.raises(ValueError, match="reads variable"):
        make_skeleton(cat, 0, make_design(cat, {"lung_cancer": 2}), 1)


# ---------------------------------------------------------------- the design command (T5)

def test_design_module_works_standalone():
    out = subprocess.run([sys.executable, "-c", "from patient_engine.commands.design import register; print('ok')"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr


def test_run_design_scales_counts_and_prints_the_table(tiny, tmp_path, capsys):
    from patient_engine.commands.design import format_table, register, run_design, scale_counts, write_skeletons
    assert scale_counts({"a": 300, "b": 150, "c": 150}, 1000) == {"a": 500, "b": 250, "c": 250}
    assert sum(scale_counts({"a": 300, "b": 150, "c": 150}, 101).values()) == 101
    design, sks = run_design(tiny, 7, n=200, coexisting_rate=0.3)
    assert design.n == 200 and len(sks) == 200
    table = format_table(tiny, design, sks)
    assert "lung_cancer" in table and "lung_cancer+pneumonia" in table
    _, prop = run_design(tiny, 7, n=300, proportional=True)
    assert len(prop) == 300
    with pytest.raises(ValueError):
        run_design(tiny, 7, proportional=True)
    # through argparse, the way __main__ calls it
    ap = argparse.ArgumentParser()
    register(ap.add_subparsers())
    out = tmp_path / "sk.jsonl"
    args = ap.parse_args(["design", "--catalogue", str(TINY), "--seed", "3", "--n", "120", "--out", str(out)])
    assert args.func(args) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 120 and skeleton_from_json(json.loads(lines[0])).seed == 3
    assert "co-existing pair" in capsys.readouterr().out
    bad = ap.parse_args(["design", "--catalogue", str(tmp_path), "--out", "-"])
    assert bad.func(bad) == 2

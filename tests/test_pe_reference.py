"""The reference generator (WP-C1-3, tickets T3, T4 and the acceptance checks)."""

from __future__ import annotations

import dataclasses
import math
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from patient_engine.card import card_from_json, card_schema_problems, card_to_json
from patient_engine.catalogue import load_catalogue
from patient_engine.reference import draw_findings, generate_reference, reference_cards
from patient_engine.skeleton import (common_facts, finding_values, make_design, make_skeleton, proportional_design,
                                     settle_error_plan)

ROOT = Path(__file__).resolve().parent.parent
TINY = ROOT / "catalogue" / "_examples" / "tiny"
LUNG = ROOT / "catalogue" / "lung-primary-care"

# For the integrator (do not edit tests/slow_tests.txt from this lane): no test here needs the slow tier;
# the longest, test_realised_accuracy_over_20000_cards (about 9 s), stays under 20 s. For the integrator: slow-tier
# candidates, if the fast tier needs room, are tests/test_pe_reference.py::test_realised_accuracy_over_20000_cards
# and tests/test_pe_reference.py::test_xray_sensitivity_by_lesion_size_and_false_alarms_with_pneumonia.


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def _mixed_design(tiny, n_each=170, rate=0.3):
    return make_design(tiny, {"lung_cancer": n_each * 2, "pneumonia": n_each, "healthy": n_each}, rate)


# ---------------------------------------------------------------- validity and determinism

def test_500_cards_pass_the_card_schema(tiny):
    d = make_design(tiny, {"lung_cancer": 250, "pneumonia": 125, "healthy": 125}, 0.3)
    kinds = Counter()
    for card in reference_cards(tiny, d, 21):
        assert card_schema_problems(card_to_json(card), tiny) == []
        kinds["co" if len(card.hidden.conditions) > 1 else "single"] += 1
        assert card.provenance.generator == "reference" and card.provenance.error_source == "guided"
    assert kinds["co"] > 20 and kinds["single"] > 300


def test_card_json_round_trips(tiny):
    d = _mixed_design(tiny)
    for i in (0, 5, 33, 200):
        card = generate_reference(tiny, make_skeleton(tiny, i, d, 4))
        j = card_to_json(card)
        assert card_to_json(card_from_json(j)) == j


def test_same_catalogue_seed_index_gives_equal_cards_and_n_does_not_matter(tiny):
    sk = make_skeleton(tiny, 17, proportional_design(100, 0.4), 6)
    assert generate_reference(tiny, sk) == generate_reference(tiny, sk)
    a = generate_reference(tiny, make_skeleton(tiny, 17, proportional_design(100, 0.4), 6))
    b = generate_reference(tiny, make_skeleton(tiny, 17, proportional_design(20_000, 0.4), 6))
    assert a == b
    assert a != generate_reference(tiny, make_skeleton(tiny, 17, proportional_design(100, 0.4), 7))


def test_seed_argument_must_match_the_skeleton(tiny):
    sk = make_skeleton(tiny, 1, proportional_design(10), 6)
    assert generate_reference(tiny, sk, 6) == generate_reference(tiny, sk)
    with pytest.raises(ValueError, match="seed"):
        generate_reference(tiny, sk, 7)


def test_attempt_k_does_not_change_when_max_attempts_is_raised(tiny):
    """I3 in spirit: results are keyed by (seed, card, test, attempt), not by how many attempts exist."""
    d = _mixed_design(tiny)
    bigger = dataclasses.replace(tiny, tests={
        **tiny.tests, "chest_ct": dataclasses.replace(tiny.tests["chest_ct"], max_attempts=5),
        "chest_xray": dataclasses.replace(tiny.tests["chest_xray"], max_attempts=6)})
    for i in range(0, 300, 7):
        sk = make_skeleton(tiny, i, d, 12)
        a, b = generate_reference(tiny, sk), generate_reference(bigger, make_skeleton(bigger, i, d, 12))
        for t in ("chest_ct", "chest_xray", "history"):
            n = len(a.observations["all_active"][t])
            assert b.observations["all_active"][t][:n] == a.observations["all_active"][t]
            assert b.hidden.error_plan["all_active"][t][:n] == a.hidden.error_plan["all_active"][t]
        assert len(b.observations["all_active"]["chest_ct"]) == 5
        assert a.hidden.findings == b.hidden.findings


# ---------------------------------------------------------------- findings and causes

def test_findings_cover_every_variable_and_causes_are_active_conditions(tiny):
    d = _mixed_design(tiny)
    seen_both = 0
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 3, plan=False)
        f = draw_findings(tiny, sk)
        assert set(f) == set(tiny.variables)
        for name, fd in f.items():
            assert set(fd.caused_by) <= set(sk.condition_ids), (name, fd, sk.condition_ids)
            if fd.value is None or fd.value is False:
                assert fd.caused_by == ()
            if tiny.variables[name].only_if is None:
                assert fd.value is not None
        if f["lung_lesion"].value is False:
            assert f["lesion_size_mm"].value is None and f["lesion_location"].value is None
        else:
            assert f["lesion_size_mm"].value >= 1 and f["lesion_location"].value in ("central", "peripheral")
        if sk.primary == "lung_cancer":
            assert f["lung_lesion"].value is True and f["lung_lesion"].caused_by == ("lung_cancer",)
            if sk.attributes["location"] == "central":
                assert f["lesion_location"].value == "central"
            if sk.coexisting == "pneumonia":
                seen_both += 1
    assert seen_both > 20


def test_cancer_plus_pneumonia_takes_the_pneumonia_crp_and_the_cancer_haemoglobin(tiny):
    d = make_design(tiny, {"lung_cancer": 1500, "healthy": 1}, 1.0)
    crp, hb, fever_cause, crp_cause = [], [], Counter(), Counter()
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 5, plan=False)
        if sk.primary != "lung_cancer":
            continue
        f = draw_findings(tiny, sk)
        crp.append(f["crp_true"].value)
        hb.append(f["hb_true"].value)
        assert f["hb_true"].caused_by == ("lung_cancer",)
        crp_cause[f["crp_true"].caused_by] += 1
        if f["fever"].value:
            fever_cause[f["fever"].caused_by] += 1
    crp.sort()
    assert crp[len(crp) // 2] > 50                      # pneumonia median is 80, cancer's 12
    assert crp_cause[("pneumonia",)] > 0.6 * len(crp)   # the value farthest from the baseline decides
    assert sum(hb) / len(hb) < 135                      # cancer uniform 105..150 (default would be 120..165)
    assert fever_cause[("pneumonia",)] > 0.9 * sum(fever_cause.values())


def test_binary_findings_follow_given_probabilities(tiny):
    d = make_design(tiny, {"lung_cancer": 4000, "pneumonia": 4000, "healthy": 4000}, 0.0)
    n, hit = Counter(), Counter()
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 9, plan=False)
        f = draw_findings(tiny, sk)
        n[sk.primary] += 1
        hit[(sk.primary, "cough")] += f["cough_3wk"].value
        hit[(sk.primary, "fever")] += f["fever"].value
        hit[(sk.primary, "cough_caused")] += bool(f["cough_3wk"].caused_by)
    assert abs(hit[("pneumonia", "cough")] / n["pneumonia"] - 0.30) < 0.02
    assert abs(hit[("healthy", "cough")] / n["healthy"] - 0.05) < 0.01
    assert hit[("healthy", "cough_caused")] == 0                      # a background rate has no cause
    assert abs(hit[("pneumonia", "fever")] / n["pneumonia"] - 0.70) < 0.02
    # cancer cough: 0.6 base, 0.75 in stage IV -> 0.35 * 0.75 + 0.65 * (stage I..III weighted) ~ 0.6 + 0.15 * 0.35
    assert abs(hit[("lung_cancer", "cough")] / n["lung_cancer"] - (0.6 * 0.65 + 0.75 * 0.35)) < 0.02


# ---------------------------------------------------------------- error plan against results

def test_plan_is_consistent_with_results(tiny):
    d = _mixed_design(tiny, n_each=500)
    counts = Counter()
    for card in reference_cards(tiny, d, 31):
        truth = finding_values({k: v for k, v in card.hidden.findings["all_active"].items()})
        plan = card.hidden.error_plan["all_active"]
        for t in tiny.tests.values():
            for k, att in enumerate(card.observations["all_active"][t.id]):
                p = plan[t.id][k]
                assert p.status == att.status
                if att.status == "non_diagnostic":
                    assert att.values == {} and p.outputs == {}
                    counts["nd"] += 1
                    continue
                for o in t.outputs:
                    outcome, shown, real = p.outputs[o.id], att.values[o.id], truth.get(o.measures)
                    if o.type == "binary":
                        if outcome == "miss":
                            assert real is True and shown is False
                        elif outcome == "false_alarm":
                            assert not real and shown is True
                        else:
                            assert shown == bool(real)
                    elif o.type == "categorical" and shown is not None:
                        assert (shown != real) == (outcome == "wrong") or real is None
                    counts[outcome] += 1
    assert counts["miss"] > 50 and counts["false_alarm"] > 50 and counts["nd"] > 20 and counts["wrong"] > 20


def test_settled_plan_differs_from_nominal_only_where_the_truth_makes_it_inapplicable(tiny):
    d = _mixed_design(tiny)
    for i in range(0, d.n, 3):
        sk = make_skeleton(tiny, i, d, 8)
        settled = settle_error_plan(tiny, sk, draw_findings(tiny, sk))["all_active"]
        for tid, atts in sk.error_plan["all_active"].items():
            for nominal, now in zip(atts, settled[tid]):
                assert nominal.status == now.status                     # nothing in tiny reads findings for it
                for o, outcome in now.outputs.items():
                    if outcome != "correct" and tiny.tests[tid].output(o).type == "binary" and tid in ("history", "chest_ct"):
                        assert nominal.outputs[o] == outcome            # plain sensitivity/specificity: same numbers


def test_only_if_outputs_and_false_alarm_lesions(tiny):
    d = _mixed_design(tiny, n_each=600)
    sizes_for_false_alarms = 0
    for card in reference_cards(tiny, d, 14):
        f = card.hidden.findings["all_active"]
        for att in card.observations["all_active"]["chest_ct"]:
            if att.status != "ok":
                continue
            v = att.values
            if not v["nodule_seen"]:
                assert v["size_mm"] is None and v["location"] is None
            else:
                assert isinstance(v["size_mm"], float) and v["size_mm"] >= 1 and v["location"] in ("central", "peripheral")
                if f["lung_lesion"].value is False:
                    sizes_for_false_alarms += 1
    assert sizes_for_false_alarms > 5


def test_texts_are_short_and_synthetic(tiny):
    d = _mixed_design(tiny)
    for i in range(0, d.n, 5):
        card = generate_reference(tiny, make_skeleton(tiny, i, d, 2))
        for atts in card.observations["all_active"].values():
            for a in atts:
                assert "synthetic" in a.report and len(a.report) < 200
        # two notes per state since C8 (WP-C8-2): the cards now have a state per resolved illness
        assert [n.kind for n in card.notes] == ["patient_account", "gp_note"] * len(card.states)
        assert [n.state for n in card.notes] == [s for s in card.states for _ in range(2)]
        assert len({n.id for n in card.notes}) == len(card.notes)
        assert all("Synthetic" in n.text for n in card.notes)
        for j, state in enumerate(card.states):
            truth = card.hidden.findings[state]
            pres = card.presenting[state]
            assert all(truth[v].value is True for v in pres.reported)
            assert card.notes[2 * j].mentions == pres.reported


# ---------------------------------------------------------------- accuracy (statistical)

def test_realised_accuracy_over_20000_cards(tiny):
    d = make_design(tiny, {"lung_cancer": 8000, "pneumonia": 6000, "healthy": 6000}, 0.3)
    tp, pos, tn, neg = defaultdict(float), Counter(), defaultdict(float), Counter()
    exp_sens, exp_spec = defaultdict(float), defaultdict(float)
    nd, atts = Counter(), Counter()
    cat_ok, cat_n = Counter(), Counter()
    err2, err_n = Counter(), Counter()
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 77, plan=False)
        card = generate_reference(tiny, sk)
        truth = finding_values(card.hidden.findings["all_active"])
        common = common_facts(sk, truth)
        for t in tiny.tests.values():
            for att in card.observations["all_active"][t.id]:
                atts[t.id] += 1
                if att.status != "ok":
                    nd[t.id] += 1
                    continue
                for o in t.outputs:
                    key = (t.id, o.id)
                    real, shown = truth[o.measures], att.values[o.id]
                    if o.type == "binary":
                        s = min(o.sensitivity.resolve({**common, "condition": c}) for c in sk.condition_ids)
                        c_ = min(o.specificity.resolve({**common, "condition": c}) for c in sk.condition_ids)
                        if real:
                            pos[key] += 1; tp[key] += shown; exp_sens[key] += s
                        else:
                            neg[key] += 1; tn[key] += (not shown); exp_spec[key] += c_
                    elif o.type == "categorical" and shown is not None and real is not None:
                        cat_n[key] += 1; cat_ok[key] += shown == real
                    elif o.type in ("continuous", "size_mm") and shown is not None and real is not None:
                        err2[key] += (shown - real) ** 2; err_n[key] += 1
    # every binary output: realised against what the catalogue says for those very patients, within 2 pp
    for key in pos:
        assert pos[key] > 300 and neg[key] > 300, key
        assert abs(tp[key] / pos[key] - exp_sens[key] / pos[key]) < 0.02, ("sensitivity", key)
        assert abs(tn[key] / neg[key] - exp_spec[key] / neg[key]) < 0.02, ("specificity", key)
    # outputs without `by:` against the catalogue's own number
    plain = {("history", "cough_3wk"): (0.9, 0.98), ("history", "fever"): (0.85, 0.97), ("history", "weight_loss"): (0.6, 0.98),
             ("chest_xray", "consolidation"): (0.8, 0.95), ("chest_ct", "nodule_seen"): (0.95, 0.8)}
    for key, (s, c) in plain.items():
        assert abs(tp[key] / pos[key] - s) < 0.02, ("sensitivity", key)
        # consolidation/nodule specificity is plain; history outputs too
        assert abs(tn[key] / neg[key] - c) < 0.02, ("specificity", key)
    assert abs(cat_ok[("chest_ct", "location")] / cat_n[("chest_ct", "location")] - 0.95) < 0.02
    for key, sd in {("blood_count", "crp"): 2.0, ("blood_count", "hb"): 3.0}.items():
        assert abs(math.sqrt(err2[key] / err_n[key]) / sd - 1) < 0.1, key
    assert abs(math.sqrt(err2[("chest_ct", "size_mm")] / err_n[("chest_ct", "size_mm")]) / 2.0 - 1) < 0.2
    for tid, rate in {"blood_count": 0.01, "chest_xray": 0.02}.items():
        assert abs(nd[tid] / atts[tid] - rate) < 0.005, tid
    assert nd["history"] == 0 and nd["chest_ct"] == 0           # no `nondiagnostic` rate, never non-diagnostic


def test_xray_sensitivity_by_lesion_size_and_false_alarms_with_pneumonia(tiny):
    """The `by:` numbers of the tiny chest X-ray act where they should."""
    d = make_design(tiny, {"lung_cancer": 6000, "pneumonia": 3000}, 0.0)
    big, small, fa_pneu, fa_n = [0, 0], [0, 0], 0, 0
    for card in reference_cards(tiny, d, 41):
        f = card.hidden.findings["all_active"]
        pneu = card.hidden.primary.id == "pneumonia"
        for att in card.observations["all_active"]["chest_xray"]:
            if att.status != "ok":
                continue
            if f["lung_lesion"].value:
                cell = small if f["lesion_size_mm"].value < 10 else big
                cell[0] += att.values["abnormal"]; cell[1] += 1
            elif pneu:
                fa_pneu += att.values["abnormal"]; fa_n += 1
    assert abs(big[0] / big[1] - 0.8) < 0.02
    assert abs(fa_pneu / fa_n - 0.2) < 0.02                      # specificity 0.8 with pneumonia
    if small[1] > 100:
        assert abs(small[0] / small[1] - 0.4) < 0.1


# ---------------------------------------------------------------- the lung catalogue (when it exists)

@pytest.mark.skipif(not LUNG.is_dir(), reason="catalogue/lung-primary-care not built yet (WP-C2-1)")
def test_200_cards_from_the_lung_catalogue_pass_the_schema():
    lung = load_catalogue(LUNG)
    d = proportional_design(200, 0.3)
    n_co = 0
    for card in reference_cards(lung, d, 5):
        assert card_schema_problems(card_to_json(card), lung) == []
        n_co += len(card.hidden.conditions) > 1
    stratified = make_design(lung, None, None)
    for i in (0, stratified.n // 2, stratified.n - 1):
        assert card_schema_problems(card_to_json(generate_reference(lung, make_skeleton(lung, i, stratified, 5))), lung) == []

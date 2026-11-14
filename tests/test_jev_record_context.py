"""Record -> JEV request context (WP-C8-4), invariant I1, build_context merge, readable lines."""

import json
from types import SimpleNamespace

import pytest

from jev.adapter import build_context
from jev.record_context import context_from_record
from patient_engine.card import HIDDEN_FIELD_NAMES
from patient_engine.catalogue import load_catalogue
from patient_engine.record import Entry, Observation, Record
from patient_engine.record_text import render
from patient_engine.reference import generate_reference
from patient_engine.reveal import RevealHandle
from patient_engine.skeleton import Design, make_skeleton

TINY = "catalogue/_examples/tiny"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def coexisting_card(tiny):
    d = Design(mode="stratified", n=6, counts=(("lung_cancer", 6),), coexisting_rate=1.0)
    for i in range(d.n):
        sk = make_skeleton(tiny, i, d, 7, plan=False)
        if sk.coexisting:
            return generate_reference(tiny, sk), sk
    raise AssertionError("no card with a co-existing illness")


def record_from(handle: RevealHandle):
    """A two-visit record built only from what the handle reveals."""
    first = handle.visible()
    rec = Record(first.card_id, dict(first.background))
    rec.append(Entry(0.0, 1, "encounter", encounter=1, role="nurse", reported=first.presenting.reported,
                     action="book_gp_routine", note="Cough, booked a GP visit."))
    pairs = [("history", 0), ("chest_xray", 0)]
    view = handle.visible(revealed=pairs)
    hist = view.observations[0]
    rec.append(Entry(9.0, 1, "encounter", encounter=2, role="gp", reported=first.presenting.reported,
                     found={k: v for k, v in hist.values.items() if v is not None},
                     action="order_chest_xray", note="Examined, chest X-ray ordered."))
    x = view.observations[1]
    rec.append(Entry(11.0, 1, "result",
                     observations=(Observation(x.test, x.attempt + 1, x.status, dict(x.values), x.report),)))
    return rec


def strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj, str):
        yield obj


def test_context_from_record_shape(tiny):
    card, _ = coexisting_card(tiny)
    rec = record_from(RevealHandle(card))
    ctx = context_from_record(rec, role="gp", now_days=11.0, catalogue=tiny)
    assert ctx["card_format"] == "card/1" and ctx["role"] == "gp" and ctx["episode"] == 1
    assert ctx["encounters_so_far"] == 2 and ctx["t_days"] == 11.0
    assert ctx["patient_id"] == rec.patient_id and ctx["background"]["age"] == ctx["age"]
    assert ctx["presenting"]["reported"]
    obs = ctx["observations"]
    assert [o["test"] for o in obs] == ["chest_xray"] and obs[0]["t_days"] == 11.0
    assert ctx["history"] == [{"step": "chest_xray", "test": "chest_xray", "t_days": 11.0,
                               "result": tiny.tests["chest_xray"].is_positive(obs[0]["values"])}]
    assert [n["id"] for n in ctx["notes"]] == ["n1", "n2"]
    assert ctx["actions"] == ["book_gp_routine", "order_chest_xray"]
    json.dumps(ctx)


def test_history_result_is_null_without_catalogue(tiny):
    rec = record_from(RevealHandle(coexisting_card(tiny)[0]))
    ctx = context_from_record(rec, role="gp", now_days=11.0)
    assert ctx["history"][0]["result"] is None


def test_i1_context_from_a_card_with_a_coexisting_illness_holds_no_condition_or_hidden_names(tiny):
    card, sk = coexisting_card(tiny)
    assert sk.coexisting and sk.coexisting != sk.primary
    ids = {c.id for c in card.hidden.conditions}
    assert len(ids) >= 2
    ctx = context_from_record(record_from(RevealHandle(card)), role="gp", now_days=11.0, catalogue=tiny)
    hidden_only = set(card.hidden.findings["all_active"]) - set(tiny.variables) | set(HIDDEN_FIELD_NAMES)
    shown_notes = {n["text"] for n in ctx["notes"]}
    for s in strings(ctx):
        if s in shown_notes:
            continue                      # a clinician's own words, written from revealed facts
        for bad in ids | hidden_only | {tiny_id for tiny_id in tiny.conditions}:
            assert bad not in s, f"{bad!r} in {s!r}"
    # the keys themselves, at every level, are never hidden field names or condition ids
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not (set(keys(ctx)) & (set(HIDDEN_FIELD_NAMES) | ids))
    assert str(card.id) not in json.dumps(ctx)        # the library's card id never appears


def test_context_is_independent_of_the_hidden_truth(tiny):
    """Same revealed record from two cards that differ only in hidden conditions gives the same context."""
    card, _ = coexisting_card(tiny)
    import dataclasses
    other = dataclasses.replace(card, hidden=dataclasses.replace(card.hidden, conditions=card.hidden.conditions[:1]))
    a = context_from_record(record_from(RevealHandle(card, public_id="P1")), role="gp", now_days=11.0, catalogue=tiny)
    b = context_from_record(record_from(RevealHandle(other, public_id="P1")), role="gp", now_days=11.0, catalogue=tiny)
    assert a == b


def view(**kw):
    base = dict(patient_id=1, group="g", age=60, t_now=5.0, node="gp_encounter", history=[], attributes={},
                priority=False, offered=["a"], option_leads={})
    base.update(kw)
    return SimpleNamespace(**base)


def test_build_context_unchanged_without_record():
    assert build_context(view()) == {"group": "g", "age": 60, "t_days": 5.0, "fast_track": False,
                                     "attributes": {}, "history": []}
    assert build_context(view(record=None)) == build_context(view())
    assert build_context(view(record=Record("C1", {"age": 60}))) == build_context(view())   # empty record


def test_build_context_merges_record(tiny):
    rec = record_from(RevealHandle(coexisting_card(tiny)[0]))
    ctx = build_context(view(t_now=11.0, record=rec))
    assert ctx["group"] == "g" and ctx["age"] == 60 and ctx["role"] == "gp"
    assert ctx["card_format"] == "card/1" and len(ctx["observations"]) == 1
    assert ctx["history"][0]["step"] == "chest_xray"
    own = build_context(view(t_now=11.0, record=rec, history=[("n1", "t", True, 2.0)]))
    assert own["history"] == [{"step": "n1", "test": "t", "result": True, "t_days": 2.0}]


def test_render_lines(tiny):
    rec = record_from(RevealHandle(coexisting_card(tiny)[0]))
    plain = render(rec)
    assert len(plain) == 3 and plain[0].startswith("Day 0 · Nurse · ") and "GP" in plain[1]
    assert plain[2].startswith("Day 11 · result · chest xray: ")
    lab = render(rec, tiny)
    assert lab[2].startswith("Day 11 · result · " + tiny.tests["chest_xray"].label + ": ")
    assert all(isinstance(x, str) and "\n" not in x for x in lab)


def test_render_example_line_format():
    rec = Record("C1", {})
    rec.append(Entry(9, 1, "encounter", encounter=1, role="gp", found={"cough_3wk": True, "fever": False},
                     action="order_chest_xray"))
    assert render(rec) == ["Day 9 · GP · cough 3wk, no fever · order chest xray"]


# ---------------------------------------------------------------- D49: assessments, choose_with_note

def test_assessments_newest_first_within_budget_and_mechanical_stays_complete(tiny):
    import jev.record_context as rc
    rec = record_from(RevealHandle(coexisting_card(tiny)[0]))
    for i in range(5):
        rec.add_assessment(12.0 + i, "gp_encounter/stub", note="x" * 1000, assessment={"plan": f"plan {i}"})
    ctx = context_from_record(rec, role="gp", now_days=20.0, catalogue=tiny)
    a = ctx["assessments"]
    assert [x["t_days"] for x in a] == sorted([x["t_days"] for x in a], reverse=True)
    assert a[0]["author"] == "gp_encounter/stub" and a[0]["assessment"] == {"plan": "plan 4"}
    assert len(a) == 5 and len(ctx["observations"]) == 1 and len(ctx["notes"]) == 2    # notes stay mechanical
    assert ctx["observations"][0]["positive"] is None or isinstance(ctx["observations"][0]["positive"], bool)
    old = rc.ASSESSMENT_BUDGET_CHARS
    rc.ASSESSMENT_BUDGET_CHARS = 2500
    try:
        small = context_from_record(rec, role="gp", now_days=20.0)["assessments"]
    finally:
        rc.ASSESSMENT_BUDGET_CHARS = old
    assert [x["t_days"] for x in small] == [16.0, 15.0]


def test_choose_with_note_returns_the_responses_words():
    from jev.adapter import BackendPolicy
    from jev.contract import BackendInfo, DecisionResponse

    class B:
        def info(self):
            return BackendInfo("b", "m@1", True, None)

        def decide(self, reqs):
            return [DecisionResponse(r.request_id, {"a": 0.4, "b": 0.6}, record_note="think", assessment={"plan": "p"})
                    for r in reqs]

    pol = BackendPolicy(B())
    probs, note, ass = pol.choose_with_note(view(), ["a", "b"])
    assert probs == {"a": 0.4, "b": 0.6} and note == "think" and ass == {"plan": "p"}
    assert pol.choose(view(), ["a", "b"]) == probs

    class Plain(B):
        def decide(self, reqs):
            return [DecisionResponse(r.request_id, {"a": 1.0, "b": 0.0}) for r in reqs]

    assert BackendPolicy(Plain()).choose_with_note(view(), ["a", "b"])[1:] == (None, None)


def test_render_assessment_is_distinct(tiny):
    rec = record_from(RevealHandle(coexisting_card(tiny)[0]))
    rec.add_assessment(12.0, "gp_encounter/stub", note="", assessment={"working_diagnosis": "post-viral cough",
                                                                     "plan": "review in 3 weeks"}, role="gp")
    assert "Day 12 · GP assessment · working diagnosis: post-viral cough · plan: review in 3 weeks" in render(rec)

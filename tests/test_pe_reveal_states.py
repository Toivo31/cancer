"""The reveal handle on multi-state cards and fresh attempts (WP-C8-2, T3). Review-required: I1 and I3.

I1: a handle with a catalogue and a multi-state card still returns only revealed types, with no hidden name
in any value or text, in every state and for attempts far beyond the stored ones; its public surface is the
reviewed one (test_pe_reveal.py pins it); the state is the caller's, and a state the card lacks raises one
message for every card.
I3: ``reveal(test, attempt, state)`` is the same however often, in whatever order and through whichever
handle it is asked, for stored and fresh attempts, in every state.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import pytest

from patient_engine.card import INITIAL_STATE, PUBLIC_TYPES, Card, RevealedObservation
from patient_engine.catalogue import load_catalogue
from patient_engine.reference import generate_reference
from patient_engine.reveal import LATER_STATE, RevealError, RevealHandle
from patient_engine.skeleton import make_design, make_skeleton
from test_pe_reveal import hidden_names, walk

ROOT = Path(__file__).resolve().parent.parent
TINY = ROOT / "catalogue" / "_examples" / "tiny"


@pytest.fixture(scope="module")
def tiny():
    return load_catalogue(TINY)


def make(cat, primary: str, coexisting: bool, index: int = 0, seed: int = 31) -> Card:
    d = make_design(cat, {primary: 80}, 1.0 if coexisting else 0.0)
    n = -1
    for i in range(d.n):
        c = generate_reference(cat, make_skeleton(cat, i, d, seed))
        if (len(c.hidden.conditions) == 2) == coexisting:
            n += 1
            if n == index:
                return c
    raise AssertionError("no such card")


PINNED = "5c12538e92f3676a"


def key(o: RevealedObservation):
    return (o.test, o.attempt, o.state, o.status, json.dumps(o.values, sort_keys=True), o.report)


# ====================================================================== any state of the card

def test_the_handle_serves_every_state_of_the_card_and_matches_the_stored_attempts(tiny):
    c = make(tiny, "lung_cancer", True)
    assert c.states == (INITIAL_STATE, "pneumonia_resolved")
    h = RevealHandle(c)
    for state in c.states:
        v = h.visible(state, [("chest_xray", 0), ("blood_count", 0)])
        assert v.state == (INITIAL_STATE if state == INITIAL_STATE else LATER_STATE) and v.presenting.text == c.presenting[state].text
        for t, atts in c.observations[state].items():
            assert h.max_attempts(t, state) == len(atts)
            for k, a in enumerate(atts):
                o = h.reveal(t, k, state)
                assert (o.status, o.values, o.report, o.state) == (a.status, a.values, a.report, v.state)
        assert [n.state for n in c.notes if n.id in {x.id for x in h.notes_visible(h.revealed_keys([], state), state)}] \
            == [state] * len(h.notes_visible(h.revealed_keys([], state), state))
    assert h.reveal("blood_count", 0, "pneumonia_resolved").values != h.reveal("blood_count", 0).values


def test_a_state_the_card_lacks_raises_one_message_for_every_card_and_reason(tiny):
    messages = set()
    cards = [make(tiny, "lung_cancer", True), make(tiny, "lung_cancer", False), make(tiny, "pneumonia", False),
             make(tiny, "healthy", False)]
    for c in cards:
        for catalogue in (None, tiny):
            h = RevealHandle(c, catalogue=catalogue)
            for state in ("copd_resolved", "all_resolved", "nonsense", "", "pneumonia_resolved_"):
                for call in (lambda s=state: h.reveal("chest_xray", 0, s), lambda s=state: h.visible(s),
                             lambda s=state: h.notes_visible((), s), lambda s=state: h.max_attempts("history", s),
                             lambda s=state: h.revealed_keys((), s), lambda s=state: h.reveal("chest_xray", 99, s)):
                    with pytest.raises(RevealError) as e:
                        call()
                    messages.add(str(e.value).replace(repr(state), "STATE"))
    assert len(messages) == 1, messages


def test_the_handle_does_not_list_a_cards_states(tiny):
    h = RevealHandle(make(tiny, "lung_cancer", True), catalogue=tiny)
    public = {n for n in dir(h) if not n.startswith("_")}
    assert not {n for n in public if "state" in n.lower()}
    assert "states" not in repr(h) and "resolved" not in repr(h)


# ====================================================================== fresh attempts

def test_without_a_catalogue_attempts_beyond_the_stored_ones_still_raise(tiny):
    c = make(tiny, "pneumonia", False)
    h = RevealHandle(c)
    stored = h.max_attempts("chest_xray")
    h.reveal("chest_xray", stored - 1)
    for k in (stored, stored + 5):
        with pytest.raises(RevealError):
            h.reveal("chest_xray", k)
    with pytest.raises(RevealError):
        h.reveal("chest_xray", -1)


def test_with_a_catalogue_the_handle_serves_any_attempt_and_keeps_the_stored_ones(tiny):
    c = make(tiny, "pneumonia", False)
    plain, h = RevealHandle(c), RevealHandle(c, catalogue=tiny)
    for state in c.states:
        for t in h.tests:
            stored = h.max_attempts(t, state)
            for k in range(stored):
                assert key(h.reveal(t, k, state)) == key(plain.reveal(t, k, state))      # below the stored count: the card
            for k in (stored, stored + 1, 10, 500):
                o = h.reveal(t, k, state)
                assert isinstance(o, RevealedObservation) and (o.test, o.attempt, o.state) == (t, k, h.visible(state).state)
                assert o.status in ("ok", "non_diagnostic")
                assert set(o.values) == (set(a for a in c.observations[state][t][0].values) if o.status == "ok" else set())
                assert "synthetic" in o.report
    with pytest.raises(RevealError):
        h.reveal("mri", 5)                                                                  # unknown test still raises
    for bad in (-1, 1.5, "3", True, None):
        with pytest.raises(RevealError):
            h.reveal("chest_xray", bad)


def test_the_catalogue_must_be_the_cards(tiny):
    other = load_catalogue(ROOT / "catalogue" / "lung-primary-care")
    with pytest.raises(ValueError):
        RevealHandle(make(tiny, "pneumonia", False), catalogue=other)


def test_i3_fresh_and_stored_attempts_are_the_same_however_asked(tiny):
    c = make(tiny, "lung_cancer", True)
    a, b = RevealHandle(c, catalogue=tiny), RevealHandle(c, catalogue=tiny)
    asks = [(t, k, s) for s in c.states for t in a.tests for k in (0, 1, 2, 3, 4, 7, 40, 41, 1000)]
    first = {x: key(a.reveal(*x)) for x in asks}
    shuffled = list(asks) * 2
    random.Random(1).shuffle(shuffled)
    for x in shuffled:                                                  # any order, repeats, a second handle
        assert key(b.reveal(*x)) == first[x] == key(a.reveal(*x))
    o = a.reveal("blood_count", 9, "pneumonia_resolved")
    if o.status == "ok":
        o.values["crp"] = -1.0                                          # a caller changing a result changes nothing
    assert key(a.reveal("blood_count", 9, "pneumonia_resolved")) == key(b.reveal("blood_count", 9, "pneumonia_resolved"))
    assert a.reveal("blood_count", 9, "pneumonia_resolved").values.get("crp") != -1.0
    asked_first = RevealHandle(c, catalogue=tiny)
    asked_first.reveal("chest_xray", 12, "pneumonia_resolved")
    assert key(asked_first.reveal("chest_xray", 3)) == key(a.reveal("chest_xray", 3))   # asking 12 first changes nothing
    # visible() assembled from fresh attempts is the same as the attempts
    v = a.visible("pneumonia_resolved", [("chest_xray", 6), ("chest_xray", 6), ("history", 3)])
    assert [key(o) for o in v.observations] == [first[("chest_xray", 6, "pneumonia_resolved")] if ("chest_xray", 6, "pneumonia_resolved") in first
                                                else key(a.reveal("chest_xray", 6, "pneumonia_resolved")),
                                                key(a.reveal("history", 3, "pneumonia_resolved"))]


def test_i3_pinned_fresh_results_do_not_depend_on_the_process(tiny):
    """Fresh results come from blake2b keys, not Python's hash(); this digest changes only if the keying does."""
    c = make(tiny, "lung_cancer", True, index=2)
    h = RevealHandle(c, catalogue=tiny)
    digest = hashlib.blake2b(digest_size=8)
    for s in c.states:
        for t in sorted(h.tests):
            for k in range(3, 9):
                digest.update(repr(key(h.reveal(t, k, s))).encode())
    assert digest.hexdigest() == PINNED


def test_fresh_attempts_are_independent_draws_not_copies(tiny):
    c = make(tiny, "pneumonia", False)
    h = RevealHandle(c, catalogue=tiny)
    crps = {h.reveal("blood_count", k).values.get("crp") for k in range(3, 60)}
    assert len(crps) > 30                                              # a measured value differs from attempt to attempt
    statuses = Counter(h.reveal("chest_xray", k).status for k in range(3, 400))
    assert 0 < statuses["non_diagnostic"] < 40                         # the catalogue's 2 % non-diagnostic rate appears


def test_fresh_results_follow_the_state_of_the_card(tiny):
    """Pneumonia explains a high CRP; in its resolved state fresh CRP readings are near the default (median 3)."""
    d = make_design(tiny, {"pneumonia": 60}, 0.0)
    act, res = [], []
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 33))
        h = RevealHandle(c, catalogue=tiny)
        for k in range(3, 8):
            for state, out in ((INITIAL_STATE, act), ("pneumonia_resolved", res)):
                o = h.reveal("blood_count", k, state)
                if o.status == "ok":
                    out.append(o.values["crp"])
    act.sort(), res.sort()
    assert act[len(act) // 2] > 40 and res[len(res) // 2] < 15


def test_fresh_attempts_realise_the_catalogue_accuracy(tiny):
    """X-ray false alarms on a lesion-free chest: 0.2 with pneumonia, about 0.1 once it has resolved."""
    d = make_design(tiny, {"pneumonia": 1200}, 0.0)
    fa, n = Counter(), Counter()
    for i in range(d.n):
        c = generate_reference(tiny, make_skeleton(tiny, i, d, 34))
        h = RevealHandle(c, catalogue=tiny)
        for state in c.states:
            if c.hidden.findings[state]["lung_lesion"].value:
                continue
            o = h.reveal("chest_xray", 7, state)
            if o.status == "ok":
                n[state] += 1
                fa[state] += o.values["abnormal"] is True
    assert abs(fa[INITIAL_STATE] / n[INITIAL_STATE] - 0.2) < 0.035
    assert abs(fa["pneumonia_resolved"] / n["pneumonia_resolved"] - 0.098) < 0.035


# ====================================================================== I1 on multi-state cards with fresh attempts

def test_i1_nothing_hidden_in_any_state_or_fresh_attempt(tiny):
    for primary, co in (("lung_cancer", True), ("pneumonia", False), ("lung_cancer", False), ("healthy", False)):
        c = make(tiny, primary, co)
        forbidden = hidden_names(c)
        h = RevealHandle(c, catalogue=tiny)
        for state in c.states:
            walk(h.visible(state, [(t, k) for t in h.tests for k in (0, 1, 2, 3, 9, 250)]), forbidden, f"visible[{state}]")
            walk(h.notes_visible(h.revealed_keys([(t, 4) for t in h.tests], state), state), forbidden, "notes")
            for t in h.tests:
                walk(h.reveal(t, 77, state), forbidden, f"reveal[{state}]")
        assert repr(h) == f"RevealHandle({h.card_id!r})" and primary not in repr(h)
    assert PUBLIC_TYPES


def test_i1_the_handle_holds_no_state_of_its_own(tiny):
    h = RevealHandle(make(tiny, "lung_cancer", True), catalogue=tiny)
    before = {s: getattr(h, s) for s in h.__slots__}
    for k in range(20):
        h.reveal("chest_ct", k, "pneumonia_resolved")
    assert {s: getattr(h, s) for s in h.__slots__} == before
    assert not hasattr(h, "__dict__")


def test_i1_fresh_attempts_do_not_reveal_the_hidden_findings_of_a_miss(tiny):
    """A planned miss must look like a negative result, not carry the finding: no key or text names the truth."""
    c = make(tiny, "lung_cancer", False)
    h = RevealHandle(c, catalogue=tiny)
    outs = [h.reveal("chest_xray", k) for k in range(3, 300)]
    assert {o.report for o in outs if o.status == "ok" and o.values["abnormal"] is False}
    for o in outs:
        assert set(o.values) <= {"abnormal", "consolidation"}
        assert "caused" not in o.report and "lung_cancer" not in o.report and "miss" not in o.report


def test_i1_the_revealed_objects_do_not_echo_the_state_name(tiny):
    """A name like 'pneumonia_resolved' names a hidden condition; views and observations say 'later' instead."""
    c = make(tiny, "lung_cancer", True)
    h = RevealHandle(c, catalogue=tiny)
    assert h.visible().state == INITIAL_STATE and h.reveal("history", 0).state == INITIAL_STATE
    for k in (0, 1, 50):
        assert h.reveal("history", k, "pneumonia_resolved").state == LATER_STATE == "later"
    assert h.visible("pneumonia_resolved", [("history", 0)]).observations[0].state == "later"
    assert h.visible("pneumonia_resolved").state == "later"

"""The reveal handle (WP-C1-6): invariants I1 (nothing hidden leaves the handle) and I3 (same answer however asked).

Review-required. The I1 tests are written to fail if someone
* adds a hidden-named field to a revealed type,
* makes a handle method return a ``Card``, ``Hidden`` or any type outside ``PUBLIC_TYPES``,
* adds a public attribute or method to ``RevealHandle`` without this file being updated,
* lets a hidden key or a condition id into anything the handle returns,
* makes the revealed side depend on the hidden truth,
* calls ``truth_for_scoring`` from outside scoring code.
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import json
import os
import random
import typing
from pathlib import Path

import pytest

from patient_engine import card as C
from patient_engine.card import PUBLIC_TYPES, Card, card_from_json
from patient_engine.reveal import RevealError, RevealHandle, opaque_id
from test_pe_library_support import ROOT, fixture_card, make_card, tiny_catalogue

ALL_PAIRS = [(t, a) for t, n in (("history", 1), ("blood_count", 1), ("chest_xray", 3), ("chest_ct", 1)) for a in range(n)]


def example() -> Card:
    return card_from_json(fixture_card())


def with_hidden(card: Card, **changes) -> Card:
    return dataclasses.replace(card, hidden=dataclasses.replace(card.hidden, **changes))


# ====================================================================== I1: a walker over everything returned

LEAF = (str, int, float, bool, type(None))


def hidden_names(card: Card) -> dict[str, set[str]]:
    """What must not appear in anything the handle returns, taken from this card's hidden side."""
    findings = set(card.hidden.findings["all_active"])
    visible_ids = {o for atts in card.observations["all_active"].values() for a in atts for o in a.values}
    visible_ids |= set(card.observations["all_active"]) | set(card.presenting["all_active"].reported)
    primary = {c.id for c in card.hidden.conditions if c.role == "primary"}
    other = {c.id for c in card.hidden.conditions} - primary
    return {
        "keys": set(C.HIDDEN_FIELD_NAMES) | primary | other | (findings - visible_ids),
        # technical tokens must never appear in any text; condition names are allowed in a note's prose
        # (a GP may write "treated as pneumonia") but not in a report, a presenting text or a key
        "strings": set(C.HIDDEN_FIELD_NAMES - {"hidden", "truth", "conditions"}) | (findings - visible_ids),
        "strings_outside_notes": primary | other,
    }


def walk(obj, forbidden: dict[str, set[str]], where="$", in_note=False, public_types=PUBLIC_TYPES):
    """Fail on anything that is not plain data or a revealed type, or that names hidden data."""
    t = type(obj)
    if isinstance(obj, LEAF):
        if isinstance(obj, str):
            bad = {s for s in forbidden["strings"] if s in obj}
            if not in_note:
                bad |= {s for s in forbidden["strings_outside_notes"] if s in obj}
            assert not bad, f"{where}: string mentions hidden {sorted(bad)}: {obj!r}"
        return
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        assert t in public_types, f"{where}: {t.__name__} is not a revealed type"
        for f in dataclasses.fields(obj):
            assert f.name not in C.HIDDEN_FIELD_NAMES, f"{where}: field {f.name}"
            assert f.name not in forbidden["keys"], f"{where}: field {f.name}"
            walk(getattr(obj, f.name), forbidden, f"{where}.{f.name}", in_note or t is C.RevealedNote, public_types)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert isinstance(k, str) and k not in forbidden["keys"], f"{where}: key {k!r}"
            walk(v, forbidden, f"{where}[{k!r}]", in_note, public_types)
        return
    if isinstance(obj, (list, tuple, frozenset, set)):
        for i, v in enumerate(obj):
            walk(v, forbidden, f"{where}[{i}]", in_note, public_types)
        return
    raise AssertionError(f"{where}: unexpected {t.__module__}.{t.__name__}")


def everything_the_handle_returns(h: RevealHandle, card: Card):
    """Every public output, on every path: first contact, each attempt alone, in every order, with all notes."""
    yield "visible()", h.visible()
    for t, a in ALL_PAIRS:
        yield f"reveal({t},{a})", h.reveal(t, a)
    yield "visible(all)", h.visible(revealed=ALL_PAIRS)
    yield "visible(reversed)", h.visible("all_active", revealed=list(reversed(ALL_PAIRS)))
    for pair in ALL_PAIRS:
        yield f"visible({pair})", h.visible(revealed=[pair])
    keys = h.revealed_keys(ALL_PAIRS)
    yield "revealed_keys", keys
    yield "notes_visible(all keys)", h.notes_visible(keys)
    yield "notes_visible(every mention)", h.notes_visible({m for n in card.notes for m in n.mentions})
    yield "card_id", h.card_id
    yield "tests", h.tests
    yield "max_attempts", {t: h.max_attempts(t) for t in h.tests}


@pytest.fixture(params=["lung_cancer", "pneumonia", "healthy"])
def any_card(request) -> Card:
    return card_from_json(make_card(3, request.param, tiny_catalogue().version_hash))


def test_i1_nothing_the_handle_returns_names_hidden_data(any_card):
    h = RevealHandle(any_card)
    forbidden = hidden_names(any_card)
    assert any_card.primary_condition in forbidden["keys"] and any_card.primary_condition in forbidden["strings_outside_notes"]
    assert any_card.primary_condition in any_card.id           # the card id itself carries the condition here
    n = 0
    for name, value in everything_the_handle_returns(h, any_card):
        walk(value, forbidden, name)
        n += 1
    assert n > 10


def test_i1_the_walker_sees_what_it_should():
    """The forbidden sets are non-trivial for the example card, so the walk above is not vacuous."""
    f = hidden_names(example())
    assert {"lung_cancer", "pneumonia", "findings", "caused_by", "error_plan", "lung_lesion", "lesion_size_mm",
            "lesion_location", "crp_true", "hb_true"} <= f["keys"]
    assert "consolidation" not in f["keys"] and "cough_3wk" not in f["keys"]      # revealed by a test or the patient
    assert {"caused_by", "error_plan", "lung_lesion"} <= f["strings"] and f["strings_outside_notes"] == {"lung_cancer", "pneumonia"}


def test_i1_walker_catches_a_card_a_hidden_object_and_hidden_fields():
    card = example()
    f = hidden_names(card)
    for leak in (card, card.hidden, card.hidden.conditions[0], card.hidden.findings["all_active"]["lung_lesion"],
                 card.observations["all_active"]["chest_ct"][0], card.notes[0], card.provenance):
        with pytest.raises(AssertionError):
            walk(leak, f)
    with pytest.raises(AssertionError):
        walk(card.hidden.conditions, f)
    # a revealed type that grew a hidden field
    for name in sorted(C.HIDDEN_FIELD_NAMES):
        Bad = dataclasses.make_dataclass("Bad", [("card_id", str), (name, dict)], frozen=True)
        with pytest.raises(AssertionError):
            walk(Bad("x", {}), f)                                     # not a revealed type at all
        # even if someone registers such a type as revealed, the field name is caught
        with pytest.raises(AssertionError, match="field"):
            walk(Bad("x", {}), f, public_types=PUBLIC_TYPES + (Bad,))
    # keys and strings
    for bad in ({"lung_cancer": 1}, {"findings": 1}, {"lung_lesion": True}, ["caused_by"], "stage: lung_cancer",
                ("pneumonia is present",)):
        with pytest.raises(AssertionError):
            walk(bad, f)
    walk({"abnormal": False, "consolidation": True, "size_mm": None}, f)           # real outputs pass


def test_i1_walker_catches_a_handle_that_returns_the_card():
    card = example()

    class LeakyVisible(RevealHandle):
        def visible(self, state="all_active", revealed=()):
            return self._card

    class LeakyReveal(RevealHandle):
        def reveal(self, test, attempt, state="all_active"):
            return self._card.hidden

    class LeakyNotes(RevealHandle):
        def notes_visible(self, revealed_keys=(), state="all_active"):
            return self._card.notes

    class LeakyValues(RevealHandle):
        def reveal(self, test, attempt, state="all_active"):
            o = super().reveal(test, attempt, state)
            return dataclasses.replace(o, values={**o.values, "lung_cancer": True})

    f = hidden_names(card)
    for cls in (LeakyVisible, LeakyReveal, LeakyNotes, LeakyValues):
        with pytest.raises(AssertionError):
            for _, v in everything_the_handle_returns(cls(card), card):
                walk(v, f)


def test_i1_revealed_side_is_independent_of_the_hidden_truth():
    """Scramble every hidden field: everything the handle returns stays identical."""
    card = example()
    scrambled = with_hidden(
        card,
        conditions=(C.ConditionTruth("healthy", "primary", {}),),
        findings={"all_active": {k: C.Finding(None, ("healthy",)) for k in card.hidden.findings["all_active"]}},
        error_plan=None,
    )
    a, b = RevealHandle(card), RevealHandle(scrambled)
    for (n1, v1), (n2, v2) in zip(everything_the_handle_returns(a, card), everything_the_handle_returns(b, card)):
        assert n1 == n2 and v1 == v2, n1
    assert a.truth_for_scoring() != b.truth_for_scoring()               # and the scoring side does differ


# ====================================================================== I1: the shape of the handle

PUBLIC_SURFACE = {"card_id", "tests", "max_attempts", "visible", "reveal", "revealed_keys", "notes_visible", "truth_for_scoring"}
SCORING_ONLY = {"truth_for_scoring"}


def public_names(obj) -> set[str]:
    return {n for n in dir(obj) if not n.startswith("_")}


def test_i1_the_public_surface_is_exactly_the_reviewed_one():
    """Adding a public name to RevealHandle fails here until a reviewer has looked at it and added it."""
    assert public_names(RevealHandle) == PUBLIC_SURFACE
    assert public_names(RevealHandle(example())) == PUBLIC_SURFACE


def _dataclasses_reached(tp, seen: set) -> set:
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        if tp not in seen:
            seen.add(tp)
            for ft in typing.get_type_hints(tp).values():
                _dataclasses_reached(ft, seen)
        return seen
    for arg in typing.get_args(tp):
        _dataclasses_reached(arg, seen)
    return seen


def test_i1_return_annotations_reach_only_revealed_types():
    allowed = set()
    for t in PUBLIC_TYPES:
        _dataclasses_reached(t, allowed)
    hidden_types = {Card, C.Hidden, C.ConditionTruth, C.Finding, C.PlannedAttempt, C.Note, C.Attempt, C.Provenance}
    reaching_hidden = set()
    for name in PUBLIC_SURFACE:
        member = inspect.getattr_static(RevealHandle, name)
        fn = member.fget if isinstance(member, property) else member
        hints = typing.get_type_hints(fn)
        assert "return" in hints, f"{name} has no return annotation"
        reached = _dataclasses_reached(hints["return"], set())
        assert not (reached & hidden_types) or name in SCORING_ONLY, f"{name} returns {reached & hidden_types}"
        if reached & hidden_types:
            reaching_hidden.add(name)
        if name not in SCORING_ONLY:
            assert reached <= allowed, f"{name} returns {reached - allowed}"
    assert reaching_hidden == SCORING_ONLY


def test_i1_no_public_attribute_holds_the_card_and_there_is_no_instance_dict():
    card = example()
    h = RevealHandle(card)
    assert not hasattr(h, "__dict__")
    for name in public_names(h) - set(m for m in PUBLIC_SURFACE if callable(getattr(h, m))):
        v = getattr(h, name)
        assert not isinstance(v, (Card, C.Hidden)) and not dataclasses.is_dataclass(v), name
    for text in (repr(h), str(h)):
        assert card.hidden.conditions[0].id not in text and "hidden" not in text.lower()


def test_i1_handle_refuses_a_non_card():
    with pytest.raises(TypeError):
        RevealHandle(fixture_card())          # type: ignore[arg-type]


def test_i1_revealed_types_have_no_hidden_field_names():
    for t in PUBLIC_TYPES:
        assert not {f.name for f in dataclasses.fields(t)} & C.HIDDEN_FIELD_NAMES, t.__name__


def test_i1_returned_containers_are_copies_not_the_cards_own_dicts():
    card = example()
    h = RevealHandle(card)
    obs = h.reveal("chest_ct", 0)
    obs.values["size_mm"] = 999.0
    obs.values["lung_cancer"] = True
    view = h.visible()
    view.background["age"] = 1
    assert h.reveal("chest_ct", 0).values == {"nodule_seen": True, "size_mm": 17.0, "location": "peripheral"}
    assert h.visible().background["age"] == 67
    assert card.attempt("chest_ct", 0).values["size_mm"] == 17.0


SCORING_NAMES = ("truth_for_scoring",)
ALLOWED_PREFIXES = ("patient_engine/", "tests/", "docs/")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"}


def test_i1_truth_for_scoring_is_called_only_from_scoring_code():
    """Source tripwire. Allowed: patient_engine/, tests/, and files whose name contains 'scor' (scoring code).
    A caller elsewhere (the decision layer, guards, the optimiser, the request builder) fails here and
    needs a reviewer; if it really is scoring code, name the file *scoring*.py or add its path to ALLOWED_PREFIXES."""
    offenders = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(dirpath) / fn
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(ALLOWED_PREFIXES) or "scor" in fn:
                continue
            text = p.read_text(errors="ignore")
            if any(name in text for name in SCORING_NAMES):
                offenders.append(rel)
    assert not offenders, f"truth_for_scoring used outside scoring code: {offenders}"


def test_i1_the_tripwire_works(tmp_path, monkeypatch):
    """A file outside the allowed places that mentions the scoring method is reported."""
    import test_pe_reveal as me
    fake_root = tmp_path
    (fake_root / "jev").mkdir()
    (fake_root / "jev" / "builder.py").write_text("x = handle.truth_for_scoring()\n")
    (fake_root / "scoring.py").write_text("x = handle.truth_for_scoring()\n")
    monkeypatch.setattr(me, "ROOT", fake_root)
    with pytest.raises(AssertionError, match="jev/builder.py"):
        me.test_i1_truth_for_scoring_is_called_only_from_scoring_code()


# ====================================================================== I3: same answer however asked

def test_i3_repeated_calls_and_two_handles_agree():
    card = example()
    a, b = RevealHandle(card), RevealHandle(card, public_id="other")
    for t, n in (("history", 1), ("blood_count", 1), ("chest_xray", 3), ("chest_ct", 1)):
        for k in range(n):
            first = a.reveal(t, k)
            assert a.reveal(t, k) == first and b.reveal(t, k) == first and RevealHandle(card).reveal(t, k) == first
    assert a.reveal("chest_xray", 0).values == {"abnormal": False, "consolidation": True}
    assert a.reveal("chest_xray", 2).status == "non_diagnostic" and a.reveal("chest_xray", 2).values == {}


def test_i3_attempt_two_does_not_depend_on_whether_attempt_one_was_asked():
    card = example()
    cold = RevealHandle(card).reveal("chest_xray", 2)
    h = RevealHandle(card)
    for t, k in [("chest_xray", 0), ("chest_xray", 1), ("blood_count", 0), ("chest_ct", 0), ("chest_xray", 0)]:
        h.reveal(t, k)
    assert h.reveal("chest_xray", 2) == cold
    skipped = RevealHandle(card)
    assert skipped.reveal("chest_xray", 1) == h.reveal("chest_xray", 1)           # asked without attempt 0
    assert RevealHandle(card).reveal("chest_xray", 1) == RevealHandle(card).visible(revealed=[("chest_xray", 1)]).observations[0]


@pytest.mark.parametrize("seed", range(5))
def test_i3_any_order_of_questions_gives_the_same_answers(seed):
    card = example()
    baseline = {p: RevealHandle(card).reveal(*p) for p in ALL_PAIRS}
    pairs = list(ALL_PAIRS) * 2
    random.Random(seed).shuffle(pairs)
    h = RevealHandle(card)
    for p in pairs:
        assert h.reveal(*p) == baseline[p]
    chosen = pairs[: 4 + seed]
    view = h.visible(revealed=chosen)
    assert {(o.test, o.attempt): o for o in view.observations} == {p: baseline[p] for p in set(chosen)}
    shuffled = list(chosen)
    random.Random(seed + 100).shuffle(shuffled)
    other = h.visible(revealed=shuffled)
    assert sorted(other.observations, key=lambda o: (o.test, o.attempt)) == sorted(view.observations, key=lambda o: (o.test, o.attempt))
    assert other.notes == view.notes and other.presenting == view.presenting and other.background == view.background


def test_i3_the_handle_keeps_no_state_between_calls():
    card = example()
    h = RevealHandle(card)
    before = (h.visible(), h.notes_visible(), h.revealed_keys())
    for p in ALL_PAIRS:
        h.reveal(*p)
        h.visible(revealed=[p])
    assert (h.visible(), h.notes_visible(), h.revealed_keys()) == before
    assert before[0].observations == () and before[0].notes == before[1]


def test_i3_every_attempt_of_every_card_matches_the_card():
    for primary in ("lung_cancer", "pneumonia", "healthy"):
        for i in range(10):
            card = card_from_json(make_card(i, primary, "h"))
            h = RevealHandle(card)
            for t, atts in card.observations["all_active"].items():
                assert h.max_attempts(t) == len(atts)
                for k, att in enumerate(atts):
                    o = h.reveal(t, k)
                    assert (o.test, o.attempt, o.state, o.status, o.values, o.report) == (t, k, "all_active", att.status, att.values, att.report)


# ====================================================================== refusals (no leak through errors either)

def test_reveal_refuses_what_the_card_does_not_offer():
    h = RevealHandle(example())
    for args in (("mri", 0), ("chest_xray", 3), ("chest_xray", -1), ("chest_xray", 1.0), ("chest_xray", True), ("chest_xray", None)):
        with pytest.raises(RevealError):
            h.reveal(*args)
    with pytest.raises(LookupError):
        h.reveal("mri", 0)
    with pytest.raises(RevealError):
        h.max_attempts("mri")


def test_other_states_raise_the_same_error_for_every_card():
    """Probing '<illness>_resolved' must not tell whether the patient has the illness.

    Intentional change (WP-C8-2): the handle used to refuse every state but ``all_active``. It now serves the
    states a card has (see tests/test_pe_reveal_states.py), so this test keeps the part that still holds:
    for cards that lack a state, and for names no card has, the refusal is one and the same message. The
    cards here are the single-state fixtures (none has a resolved state), and the refusal must not depend on
    the card or on the reason."""
    cat = tiny_catalogue()
    messages = set()
    for primary in ("lung_cancer", "pneumonia", "healthy"):
        h = RevealHandle(card_from_json(make_card(1, primary, cat.version_hash)))
        for state in ("pneumonia_resolved", "all_resolved", "nonsense"):
            for call in (lambda s=state: h.reveal("chest_xray", 0, s), lambda s=state: h.visible(s),
                         lambda s=state: h.notes_visible((), s), lambda s=state: h.max_attempts("history", s),
                         lambda s=state: h.revealed_keys((), s)):
                with pytest.raises(RevealError) as e:
                    call()
                messages.add(str(e.value).replace(repr(state), "STATE"))
    assert len(messages) == 1, messages


# ====================================================================== notes

def note_ids(notes) -> list[str]:
    return [n.id for n in notes]


def test_notes_follow_their_mentions_on_the_example_card():
    h = RevealHandle(example())
    # n1 mentions cough_3wk and fever: both reported at first contact
    assert note_ids(h.notes_visible()) == ["n1"] and note_ids(h.visible().notes) == ["n1"]
    # n2 mentions chest_xray.consolidation: shown once an ok X-ray result carries it
    assert "n2" not in note_ids(h.visible(revealed=[("history", 0), ("blood_count", 0), ("chest_ct", 0)]).notes)
    assert note_ids(h.visible(revealed=[("chest_xray", 0)]).notes) == ["n1", "n2"]
    assert note_ids(h.visible(revealed=[("chest_xray", 1)]).notes) == ["n1", "n2"]
    assert note_ids(h.visible(revealed=[("chest_xray", 2)]).notes) == ["n1"]          # non-diagnostic reveals nothing
    assert note_ids(h.notes_visible({"chest_xray.consolidation"})) == ["n1", "n2"]
    assert note_ids(h.notes_visible({"chest_xray.abnormal"})) == ["n1"]
    assert note_ids(h.notes_visible({"chest_xray"})) == ["n1"]                         # the bare test id is another key
    n2 = h.visible(revealed=[("chest_xray", 0)]).notes[1]
    assert n2 == C.RevealedNote("n2", "gp_note", example().notes[1].text) and not hasattr(n2, "mentions")


def test_a_note_needs_every_mention():
    card = example()
    partial = dataclasses.replace(card, notes=(dataclasses.replace(card.notes[0], mentions=("cough_3wk", "weight_loss")),))
    h = RevealHandle(partial)
    assert h.notes_visible() == ()                                       # weight_loss was not reported
    assert note_ids(h.notes_visible({"weight_loss"})) == ["n1"]          # the caller may reveal it
    assert h.notes_visible({"fever"}) == ()


def test_a_variable_measured_by_a_test_is_not_revealed_by_it():
    """A noisy result must not unlock a note that states the truth about the variable."""
    card = example()
    note = dataclasses.replace(card.notes[0], id="n9", mentions=("weight_loss",))
    h = RevealHandle(dataclasses.replace(card, notes=(note,)))
    view = h.visible(revealed=[("history", 0)])
    assert "history.weight_loss" in h.revealed_keys([("history", 0)]) and "weight_loss" not in h.revealed_keys([("history", 0)])
    assert view.notes == ()


def test_notes_without_mentions_or_for_another_state_are_never_shown():
    card = example()
    blank = dataclasses.replace(card.notes[0], id="n7", mentions=())
    elsewhere = dataclasses.replace(card.notes[0], id="n8", state="pneumonia_resolved")
    h = RevealHandle(dataclasses.replace(card, notes=(blank, elsewhere)))
    assert h.notes_visible({"cough_3wk", "fever", "anything"}) == () and h.visible(revealed=ALL_PAIRS).notes == ()


def test_outputs_without_a_value_do_not_reveal_their_key():
    h = RevealHandle(card_from_json(make_card(1, "healthy", "h")))
    keys = h.revealed_keys([("chest_ct", 0)])
    assert "chest_ct" in keys and "chest_ct.nodule_seen" in keys                  # False is a value
    assert "chest_ct.size_mm" not in keys and "chest_ct.location" not in keys     # None is not
    assert h.revealed_keys([("chest_xray", 0)]) == frozenset(
        {"cough_3wk", "chest_xray", "chest_xray.consolidation", "chest_xray.abnormal"})


def test_notes_come_in_card_order_and_only_for_the_state():
    card = example()
    h = RevealHandle(card)
    view = h.visible(revealed=[("chest_xray", 0)])
    assert [n.id for n in view.notes] == [n.id for n in card.notes]


# ====================================================================== first contact and truth

def test_visible_at_first_contact_is_background_and_presenting_only():
    card = example()
    v = RevealHandle(card).visible()
    assert isinstance(v, C.PublicView) and v.state == "all_active"
    assert v.card_id == RevealHandle(card).card_id == opaque_id("example:000001") and "example" not in v.card_id
    assert v.background == card.background and v.observations == ()
    assert v.presenting == C.Presenting(("cough_3wk", "fever"), card.presenting["all_active"].text)
    assert RevealHandle(card, public_id="P000001").visible().card_id == "P000001"
    assert RevealHandle(card).tests == ("history", "blood_count", "chest_xray", "chest_ct")
    assert RevealHandle(card).max_attempts("chest_xray") == 3


def test_visible_drops_duplicates_and_keeps_order():
    h = RevealHandle(example())
    v = h.visible(revealed=[("chest_xray", 1), ("history", 0), ("chest_xray", 1)])
    assert [(o.test, o.attempt) for o in v.observations] == [("chest_xray", 1), ("history", 0)]


def test_truth_for_scoring_returns_the_conditions():
    truth = RevealHandle(example()).truth_for_scoring()
    assert [(c.id, c.role) for c in truth] == [("lung_cancer", "primary"), ("pneumonia", "coexisting")]
    assert truth[0].attributes == {"stage": "II", "location": "peripheral"}

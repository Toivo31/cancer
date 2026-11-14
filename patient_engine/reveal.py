"""The reveal handle: the only way the simulation touches a card (invariants I1 and I3).

::

    handle = RevealHandle(card)                       # or cohort.handle(i)
    view   = handle.visible()                         # PublicView: background, presenting, nothing else
    obs    = handle.reveal("chest_xray", 0)           # RevealedObservation: outputs and report of one attempt
    notes  = handle.notes_visible({"chest_xray.consolidation"})   # RevealedNote tuple
    view   = handle.visible(revealed=[("chest_xray", 0)])         # the above, assembled
    truth  = handle.truth_for_scoring()               # hidden conditions: scoring code only, after the run

Rules the code keeps (the tests in ``tests/test_pe_reveal*.py`` fail if one is broken):

I1  Every public method returns only the revealed types of ``patient_engine.card`` (``PublicView``,
    ``RevealedObservation``, ``RevealedNote``, ``Presenting``) or plain strings, numbers, tuples and
    frozensets. ``truth_for_scoring`` is the single exception and is named so that a search finds every
    caller. The card is held in a private slot; ``repr`` shows the public id only.

I3  The handle keeps no state. ``reveal(test, attempt, state)`` is a pure function of the card and its
    three arguments, so the answer is the same on repeated calls, from two handles on the same card, and
    whether or not another attempt was asked first. Returned dicts are copies, so a caller cannot change
    what the next call returns.

What counts as revealed (for notes). A note carries ``mentions``: keys of the facts it may reveal. It is
shown only when it has at least one mention and every mention is revealed. A key is revealed when it is

* a variable id in the state's ``presenting.reported`` (the patient said it at first contact), or
* a test id, or ``test.output``, of an ``ok`` attempt that was revealed (``test.output`` also needs a
  value that is not ``None``), or
* given by the caller in ``revealed_keys`` (the caller decides, for example after a clinician asked).

A variable id is *not* revealed by a test that measures it: a noisy result must not unlock a note that
states the truth. A note without mentions is never shown (nothing says what it would reveal).

States (C8, D40). The handle serves every state the card has and nothing else: the caller names the state.
The caller is the engine (hidden side), which owns it and derives it with ``patient_engine.states.next_state``;
the revealed side (decision layer, guards, request builder) must never choose a state itself, because a
state the card lacks raises and so tells which illnesses the patient has. A state that is not served raises
the same ``RevealError`` whatever the reason (an unknown name, a state of another card), and the handle has
no method that lists the card's states.

The revealed objects do not echo the state: ``state`` on a ``PublicView`` or ``RevealedObservation`` is
``all_active`` for the first state and ``LATER_STATE`` (``"later"``) for every other, because the names
``<illness>_resolved`` name a hidden condition (I1).

Fresh attempts. With a ``catalogue`` the handle also serves attempt ``k`` of a test for every ``k`` at or
beyond the stored attempts, without limit (a patient may be re-tested again and again). Such an attempt is
drawn by ``skeleton.settle_attempt`` from the catalogue's accuracy given the card's findings in that state,
with keyed random numbers (a hash of the card id, state, test, attempt, output), and its report by
``reference.report_text``. It is a pure function of the card, the catalogue and the three arguments, so I3
holds exactly as for stored attempts. Attempts below the stored count always come from the card.

Standard library only.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

from .card import (
    INITIAL_STATE,
    Card,
    ConditionTruth,
    Presenting,
    PublicView,
    RevealedNote,
    RevealedObservation,
)

__all__ = ["RevealHandle", "RevealError", "LATER_STATE"]

#: What ``PublicView.state`` and ``RevealedObservation.state`` say for every state but the first. A state name
#: such as ``pneumonia_resolved`` names a hidden condition (I1), so the revealed objects never echo it; the
#: caller (the engine) knows which state it asked for.
LATER_STATE = "later"


class RevealError(LookupError):
    """The request names something a card does not offer (unknown test, attempt out of range, state not
    served). The message depends on the request and the catalogue, never on the card's hidden data."""


def opaque_id(card_id: str) -> str:
    """A stable label for a card id that says nothing about it."""
    return "C" + hashlib.blake2b(card_id.encode(), digest_size=5).hexdigest()


def _label(state: str) -> str:
    """The state as the revealed side may see it: ``all_active`` or ``LATER_STATE``."""
    return INITIAL_STATE if state == INITIAL_STATE else LATER_STATE


def _seed_of(card_id: str) -> int:
    """The keyed-random-number seed of a card for fresh attempts: a hash of its id."""
    return int.from_bytes(hashlib.blake2b(b"fresh|" + card_id.encode(), digest_size=8).digest(), "big") >> 1


class RevealHandle:
    """A patient as the revealed side may see them. See the module docstring."""

    __slots__ = ("_card", "_public_id", "_catalogue")

    def __init__(self, card: Card, *, public_id: str | None = None, catalogue=None) -> None:
        """``public_id`` is the label the revealed side sees as ``PublicView.card_id``. The default is opaque
        (``C`` + 10 hex of a hash of the card id): a card id written by a generator could carry the condition
        (``lung_cancer_017``). A cohort passes a per-patient label (``P000042``); a tool for people may pass
        the real card id on purpose.

        ``catalogue`` (optional, the card's catalogue): with it the handle serves attempts beyond the stored
        ones, each a fresh but reproducible draw (see ``reveal``). Without it only stored attempts exist."""
        if not isinstance(card, Card):
            raise TypeError("RevealHandle needs a Card")
        if catalogue is not None and catalogue.id != card.provenance.catalogue_id:
            raise ValueError(f"card {opaque_id(card.id)} is from catalogue {card.provenance.catalogue_id!r}, "
                             f"not {catalogue.id!r}")
        self._card = card
        self._public_id = opaque_id(card.id) if public_id is None else str(public_id)
        self._catalogue = catalogue

    def __repr__(self) -> str:
        return f"RevealHandle({self._public_id!r})"

    # ------------------------------------------------------------------ public facts

    @property
    def card_id(self) -> str:
        """The label of this patient on the revealed side."""
        return self._public_id

    @property
    def tests(self) -> tuple[str, ...]:
        """Test ids the card has results for (every test of the catalogue; public knowledge)."""
        return tuple(self._card.observations[INITIAL_STATE])

    def max_attempts(self, test: str, state: str = INITIAL_STATE) -> int:
        """Number of attempts stored for ``test`` (the catalogue's ``max_attempts`` for it). With a catalogue
        attempts beyond it are served as fresh draws; this is the count of the stored ones."""
        return len(self._attempts(test, state))

    def _check_state(self, state: str) -> None:
        if not isinstance(state, str) or state not in self._card.observations:
            raise RevealError(f"state {state!r} is not served")

    def _attempts(self, test: str, state: str):
        self._check_state(state)
        try:
            return self._card.observations[state][test]
        except KeyError:
            raise RevealError(f"unknown test {test!r}") from None

    # ------------------------------------------------------------------ reveal

    def reveal(self, test: str, attempt: int, state: str = INITIAL_STATE) -> RevealedObservation:
        """Outputs and report of attempt ``attempt`` (0-based) of ``test`` in ``state``.

        A pure function of the card (and catalogue) and the arguments (I3). Attempts below the stored count
        come from the card. At or beyond it, with a catalogue, the attempt is a fresh keyed draw (module
        docstring); without one it raises. Raises ``RevealError`` for an unknown test, a state that is not
        served, a negative or non-integer attempt, or an attempt beyond the stored ones when the handle has
        no catalogue."""
        attempts = self._attempts(test, state)
        if isinstance(attempt, bool) or not isinstance(attempt, int):
            raise RevealError(f"attempt must be an int, got {attempt!r}")
        if attempt < 0 or (attempt >= len(attempts) and self._catalogue is None):
            raise RevealError(f"attempt {attempt} of {test!r} is not available (stored: {len(attempts)})")
        if attempt < len(attempts):
            a = attempts[attempt]
            return RevealedObservation(test=test, attempt=attempt, state=_label(state), status=a.status,
                                       values=dict(a.values), report=a.report)
        return self._fresh(test, attempt, state)

    def _fresh(self, test: str, attempt: int, state: str) -> RevealedObservation:
        """A fresh attempt: drawn from the catalogue's accuracy given this card's findings in ``state``."""
        from .reference import report_text
        from .skeleton import Skeleton, finding_values, settle_attempt
        card, cat = self._card, self._catalogue
        primary = card.hidden.primary
        co = next((c for c in card.hidden.conditions if c.role == "coexisting"), None)
        skeleton = Skeleton(id=card.id, index=0, seed=_seed_of(card.id), catalogue_id=cat.id,
                            catalogue_hash=cat.version_hash, primary=primary.id, attributes=dict(primary.attributes),
                            coexisting=co.id if co else None,
                            coexisting_attributes=dict(co.attributes) if co else {},
                            background=dict(card.background), brief="", states=card.states)
        planned, reported = settle_attempt(cat, cat.tests[test], attempt, skeleton,
                                           finding_values(card.hidden.findings[state]), state)
        return RevealedObservation(test=test, attempt=attempt, state=_label(state), status=planned.status,
                                   values=dict(reported), report=report_text(cat.tests[test], planned.status, reported))

    # ------------------------------------------------------------------ keys and notes

    def revealed_keys(self, revealed: Iterable[tuple[str, int]] = (), state: str = INITIAL_STATE) -> frozenset[str]:
        """Keys revealed so far: what the patient reported at first contact plus, for each revealed
        ``(test, attempt)`` that is ``ok``, the test id and ``test.output`` for every output that has a value."""
        self._check_state(state)
        keys = set(self._card.presenting[state].reported)
        for test, attempt in revealed:
            obs = self.reveal(test, attempt, state)
            if obs.status != "ok":
                continue
            keys.add(test)
            keys.update(f"{test}.{o}" for o, v in obs.values.items() if v is not None)
        return frozenset(keys)

    def notes_visible(self, revealed_keys: Iterable[str] = (), state: str = INITIAL_STATE) -> tuple[RevealedNote, ...]:
        """Notes of ``state`` whose mentions are all revealed, in card order. What the patient reported at
        first contact counts as revealed; ``revealed_keys`` adds the rest (see ``revealed_keys``)."""
        self._check_state(state)
        known = set(revealed_keys) | set(self._card.presenting[state].reported)
        return tuple(
            RevealedNote(id=n.id, kind=n.kind, text=n.text)
            for n in self._card.notes
            if n.state == state and n.mentions and all(m in known for m in n.mentions)
        )

    # ------------------------------------------------------------------ the view

    def visible(self, state: str = INITIAL_STATE, revealed: Iterable[tuple[str, int]] = ()) -> PublicView:
        """What the revealed side may know: background, what the patient presents in ``state``, the
        observations for the ``(test, attempt)`` pairs in ``revealed`` (in that order, duplicates dropped)
        and the notes those unlock. With no ``revealed`` it is the picture at first contact."""
        self._check_state(state)
        pairs = list(dict.fromkeys((t, a) for t, a in revealed))
        observations = tuple(self.reveal(t, a, state) for t, a in pairs)
        p = self._card.presenting[state]
        return PublicView(
            card_id=self._public_id,
            state=_label(state),
            background=dict(self._card.background),
            presenting=Presenting(tuple(p.reported), p.text),
            observations=observations,
            notes=self.notes_visible(self.revealed_keys(pairs, state), state),
        )

    # ------------------------------------------------------------------ scoring only

    def truth_for_scoring(self) -> tuple[ConditionTruth, ...]:
        """The patient's true conditions (primary first as stored). For scoring code after the run ends:
        never call it from the decision layer, a guard, the optimiser's proposal step or the request
        builder (I1). The name is the marker a search or review looks for."""
        return tuple(self._card.hidden.conditions)

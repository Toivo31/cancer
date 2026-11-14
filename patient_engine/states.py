"""Card states for the encounter loop (C8 rule 3, C1 "More than one illness", D40). Hidden side.

A card has one state per combination of resolved ordinary illnesses (an illness is a condition of class
``other_illness`` in the catalogue; a cancer never resolves by treatment here). Names, as the catalogue
(``Catalogue.states()``) and the validator use them::

    all_active                 nothing resolved (the state at first contact, always first)
    <illness>_resolved         exactly that illness resolved
    all_resolved               every illness of the card resolved (only when the card has two illnesses;
                               with one illness ``<illness>_resolved`` is that state)

A card with one illness (cancer plus pneumonia, or a pneumonia alone) has ``all_active`` and
``pneumonia_resolved``. A card with two illnesses has four states. A card without an illness has only
``all_active``.

The engine owns the state of a patient: it keeps the set of conditions treatment has resolved, calls
``next_state(card, resolved)`` after each resolution and passes the result to
``RevealHandle.reveal(test, attempt, state)``. Nothing here is for the revealed side (I1): it reads the
hidden findings and condition list of a card.

    from patient_engine.states import next_state, persisting_symptoms

    state = next_state(card, {"pneumonia"})                    # "pneumonia_resolved"
    left = persisting_symptoms(card, state, catalogue)         # {"cough_3wk"} if the cancer still causes it

Standard library only.
"""

from __future__ import annotations

from typing import Collection, Iterable, Sequence

from .card import INITIAL_STATE, Card

__all__ = ["next_state", "persisting_symptoms", "resolvable_conditions", "states_for", "resolved_in_state"]

ALL_RESOLVED = "all_resolved"
_SUFFIX = "_resolved"


def resolvable_conditions(card: Card) -> tuple[str, ...]:
    """Condition ids that have a resolved state on ``card`` (its ordinary illnesses), in state order."""
    return tuple(s[: -len(_SUFFIX)] for s in card.states if s.endswith(_SUFFIX) and s != ALL_RESOLVED)


def states_for(illnesses: Sequence[str]) -> tuple[str, ...]:
    """State names of a card whose ordinary illnesses are ``illnesses`` (order of the argument is kept)."""
    ill = tuple(dict.fromkeys(illnesses))
    if not ill:
        return (INITIAL_STATE,)
    if len(ill) == 1:
        return (INITIAL_STATE, f"{ill[0]}{_SUFFIX}")
    return (INITIAL_STATE, *(f"{c}{_SUFFIX}" for c in ill), ALL_RESOLVED)


def resolved_in_state(state: str, illnesses: Iterable[str]) -> frozenset[str]:
    """The illnesses that are resolved in ``state`` of a card whose illnesses are ``illnesses``."""
    ill = tuple(illnesses)
    if state == INITIAL_STATE:
        return frozenset()
    if state == ALL_RESOLVED:
        return frozenset(ill)
    if state.endswith(_SUFFIX) and state[: -len(_SUFFIX)] in ill:
        return frozenset({state[: -len(_SUFFIX)]})
    raise ValueError(f"{state!r} is not a state of a card with illnesses {list(ill)}")


def next_state(card: Card, resolved: Collection[str]) -> str:
    """The state of ``card`` in which exactly the conditions in ``resolved`` have been resolved by treatment.

    ``resolved`` is cumulative (every condition resolved so far, not only the latest). Ids that cannot
    resolve on this card (a cancer, a condition the patient does not have, an unknown id) are ignored, so
    the engine may pass "the conditions this treatment targets that the patient truly has" or simply
    everything treated: a treatment aimed at something the patient lacks changes nothing. Empty (after
    ignoring) gives ``all_active``. Pure function of the card and the set; deterministic.

    Raises ``ValueError`` if the card has no state for that combination (a malformed card)."""
    ill = resolvable_conditions(card)
    got = frozenset(c for c in resolved if c in ill)
    if not got:
        return INITIAL_STATE
    for s in card.states:
        if s != INITIAL_STATE and resolved_in_state(s, ill) == got:
            return s
    raise ValueError(f"card {card.id!r} has no state for resolved conditions {sorted(got)}; states: {list(card.states)}")


def persisting_symptoms(card: Card, state: str, catalogue=None) -> set[str]:
    """Symptom variable ids that are still true in ``state`` (the patient still has the complaint).

    The engine uses it at discharge: a non-empty set means the patient may return (C8 behaviour).
    With ``catalogue`` a symptom is a variable of kind ``symptom`` (the engine should pass it). Without,
    the card cannot tell symptoms from signs, so the answer is limited to the true findings that the
    patient mentions in some state (``presenting.reported`` of any state): an approximation that
    can miss a symptom the patient never reports. Raises ``KeyError`` for a state the card lacks."""
    findings = card.hidden.findings[state]
    if catalogue is not None:
        kinds = catalogue.variables
        return {v for v, f in findings.items() if f.value is True and v in kinds and kinds[v].kind == "symptom"}
    named = {v for p in card.presenting.values() for v in p.reported}
    return {v for v, f in findings.items() if f.value is True and v in named}

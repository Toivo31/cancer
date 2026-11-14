# WP-C8-2: Cards for the encounter loop: states, fresh repeat results

| | |
|---|---|
| Component | C8 (rules 2, 3) and C1 (states, D40) |
| Size | M · Model: Sonnet |
| Needs | merged `patient_engine` |
| Provides | multi-state reference cards; `RevealHandle` that serves any card state and attempts beyond `max_attempts`; `next_state(card, resolved_conditions)` |
| Owned paths | `patient_engine/reveal.py`, `patient_engine/reference.py`, `patient_engine/skeleton.py`, `patient_engine/validate.py`, `patient_engine/states.py` (new), `tests/test_pe_reveal*.py`, `tests/test_pe_reference*.py`, `tests/test_pe_skeleton*.py`, `tests/test_pe_validate*.py`, `tests/test_pe_states*.py` |
| Review required | yes: I1, I3 |

## Outcome

1. **States.** The reference generator writes one state per combination of resolved co-existing and
   primary ordinary illnesses (`Catalogue.states()` and the validator's naming: `<illness>_resolved`,
   `all_resolved`). In a resolved state, findings caused only by resolved conditions are absent, the
   rest keep their values; observations are drawn for every state with keyed numbers (state in the key).
   A cancer never resolves by treatment here.
2. **`next_state(card, resolved: set[str]) -> str`** in `patient_engine/states.py` (hidden side), and
   `persisting_symptoms(card, state) -> set[str]` (symptom variables still true).
3. **Fresh attempts.** `RevealHandle(card, catalogue=...)` serves `reveal(test, attempt, state)` for
   `attempt > max_attempts` by drawing from the catalogue's accuracy given the card's findings in that
   state, keyed by (card seed or id hash, test, attempt, state) — reuse `skeleton.settle_attempt` and
   `reference.report_text`. Same call twice = same result (I3).
4. **Any state.** The handle serves a state the caller passes (the engine is the hidden side and owns
   the state). Keep the existing guarantee that the revealed side cannot *discover* other states:
   an unknown state still raises; the state names reachable from a card are not exposed on the handle.
   Update the I1 test that refused non-initial states accordingly, with a reason in the test.
5. Validator: multi-state cards from the generator pass with no errors (property test over 3 000 cards
   of the tiny catalogue and 500 of `lung-primary-care`).

## Acceptance

- [ ] Tests for each point above; `python -m pytest -q tests/test_pe_*` green; `scripts/gate.sh` green.
- [ ] I1 tests still fail if a hidden field is added to a revealed type or the handle returns a card.

## Tickets

| | ID | Ticket | Done when |
|---|---|---|---|
| [ ] | C8-2-T1 | Publish `next_state` / `persisting_symptoms` signatures (stub implementation + docstring), STATUS | posted within ~30 min |
| [ ] | C8-2-T2 | Multi-state reference cards | validator property test |
| [ ] | C8-2-T3 | Handle: fresh attempts beyond max, any state | I3 tests |
| [ ] | C8-2-T4 | Lung catalogue property test; report | green |

## Report (builder fills in)

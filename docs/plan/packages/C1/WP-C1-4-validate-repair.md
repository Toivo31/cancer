# WP-C1-4: Validate and repair rules

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P6, stage G3) |
| Status | not started |
| Size | S–M |
| Needs | WP-C1-1 (merged) |
| Provides | `validate_card(card, catalogue) -> list[Problem]`, `repair_prompt(card_json, problems) -> str` |
| Owned paths | `patient_engine/validate.py`, `patient_engine/problems.py` (add codes only, one block, do not reorder), `tests/test_pe_validate*.py` |
| Review required | no |
| Track | submission |

## Outcome

A card written by a model is checked against the catalogue and for internal consistency. The result
is a list of `Problem` with codes and paths precise enough to give back to the model as a repair
request. No model call here: WP-C1-5 owns the loop.

## Rules to implement (each its own code in `problems.CODES`, each with a test)

Schema first (`card_schema_problems`); then:
1. `states` start with `all_active`; every per-state section has exactly those keys.
2. Exactly one `primary` condition; at most one `coexisting`; condition ids and attributes exist in the catalogue.
3. Every `caused_by` entry is an active condition of the card; a finding true with an empty
   `caused_by` is allowed only if the catalogue's default distribution gives it a background rate.
4. A finding value with a `caused_by` list that no catalogue entry supports (a cause for which the
   variable has no `given` and no default) is a warning.
5. Every test of the catalogue has results for every state; attempts at most `max_attempts`; a
   `non_diagnostic` attempt only if the test has a nondiagnostic rate; values only for the test's outputs, typed correctly and in range.
6. Guided mode: if `hidden.error_plan` is set, each output's value is consistent with its planned
   outcome (`miss` shows the finding absent when it is present; `false_alarm` shows it present when absent; `correct` agrees).
7. Plausibility: a continuous value within the catalogue's stated range for that variable (if given), a size is non-negative, age within background bounds.
8. Notes: every `mentions` key exists (variable id, test id or `test.output`); a note's text
   must not state the hidden primary condition's name when its `mentions` do not include a fact
   that reveals it (a simple check for condition labels and ids in note and report text: warning code).
9. Reports: each non-empty `report` does not contradict its values for binary outputs (a report
   containing "no abnormality" for `abnormal: true` is a warning; keep this check small, a keyword list per test is fine and optional).

`repair_prompt` builds a plain-text message listing each problem as `path: message (hint)` and the
instruction to return the full corrected card JSON only. Keep it under 2 000 characters for ten
problems.

## Acceptance

- [ ] A mutation test per rule: start from `tests/fixtures/patient_engine/card_example.json` (valid
      against `catalogue/_examples/tiny`), apply one mutation, expect exactly the intended code.
- [ ] The valid example returns no problems of severity error.
- [ ] A property test: 200 random cards from `patient_engine.reference.generate_reference`, if that
      module exists (it is built in parallel by WP-C1-3; skip the test when the import fails),
      produce no error-severity problems.
- [ ] `repair_prompt` is deterministic and includes every error path (test).
- [ ] Fast: under 10 s.

## Out of scope

Calling a model, the discard log (WP-C1-5), audit over many cards (WP-C1-7).

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [ ] | C1-4-T1 | Structure rules 1 to 3 with mutation tests | S | tests pass |
| [ ] | C1-4-T2 | Results rules 5 to 7 | M | tests pass |
| [ ] | C1-4-T3 | Guided consistency rule 6 and text rules 8, 9 | M | tests pass |
| [ ] | C1-4-T4 | `repair_prompt`; reference-card property test | S | tests pass |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

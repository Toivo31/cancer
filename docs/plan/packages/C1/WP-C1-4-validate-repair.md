# WP-C1-4: Validate and repair rules

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P6, stage G3) |
| Status | built on branch `w2/validate`; awaiting integration |
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

- [x] A mutation test per rule: start from `tests/fixtures/patient_engine/card_example.json` (valid
      against `catalogue/_examples/tiny`), apply one mutation, expect exactly the intended code.
- [x] The valid example returns no problems of severity error.
- [x] A property test: 200 random cards from `patient_engine.reference.generate_reference`, if that
      module exists (it is built in parallel by WP-C1-3; skip the test when the import fails),
      produce no error-severity problems.
- [x] `repair_prompt` is deterministic and includes every error path (test).
- [x] Fast: under 10 s.

## Out of scope

Calling a model, the discard log (WP-C1-5), audit over many cards (WP-C1-7).

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [x] | C1-4-T1 | Structure rules 1 to 3 with mutation tests | S | tests pass |
| [x] | C1-4-T2 | Results rules 5 to 7 | M | tests pass |
| [x] | C1-4-T3 | Guided consistency rule 6 and text rules 8, 9 | M | tests pass |
| [x] | C1-4-T4 | `repair_prompt`; reference-card property test | S | tests pass |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| Semantic rules run even when the schema failed; a semantic problem under a path the schema already flagged is dropped | One repair request can carry every problem (the loop has only two repairs); no double reports | Return early on schema errors in `validate_card` |
| Where the schema already enforces a rule (typed values, enums, required outputs and keys) the code stays `card_schema`; where its message is hard to act on the rule replaces it at the same path with its own code: non-diagnostic attempts and attempt counts (`card_attempts`), unknown condition or attribute (`card_conditions`), note mentions (`card_mention_unknown`), numbers out of range (`card_value_range`), first state (`card_state_keys`) | The schema picks "best branch" messages for `anyOf`/`oneOf` and truncates enum lists, which a model cannot use | Remove the `replaces=` argument of a rule |
| 13 new codes, all prefixed `card_`, one block in `problems.CODES` after `card_schema`; rules 3, 5, 7 and 8 have two codes each (an error and a related check) | The package asked for a code per rule; some rules mix an error with a warning | Merge codes in `problems.py` and `validate.py` |
| Rule 2 also checks attributes (missing, unknown, wrong level) and repeated ids; it does not check that a coexisting illness is a pair listed in `cooccurrence` | The brief says ids and attributes exist; co-occurrence lists may be empty in a catalogue | Add a check on `catalogue.cooccurring(primary)` |
| Rule 3: "active" per state: `<illness>_resolved` resolves that illness, `all_resolved` resolves every `other_illness` of the card; a resolved cause is `card_cause_inactive`. A true binary finding with an empty `caused_by` needs a `default` leaf of kind `p` with p > 0 (`card_unexplained_finding`); non-binary findings are not checked | The pipeline text says a resolved illness leaves no finding caused only by it; "background rate" only has a meaning for yes/no variables | Extend to categorical variables if wanted |
| Rule 4 reading: a cause is "unsupported" when the variable's `given` has no entry for that condition (the `default` entry does not count as support) or the entry is `p: 0` for a true finding; warning | Literal "no given and no default" can never happen in a validated catalogue (`missing_given`) | Count `default` as support: change one condition in `r3_r4_causes` |
| Rule 5 extra: `card_only_if`: a finding or output is null exactly when its `only_if` (`pathway_sim.expr`) holds over the same state's findings or the same attempt's values | The schema allows null for any `only_if` output, so a lesion size with no lesion would pass | – |
| Rule 6 outcomes: binary `correct` = equals truth, `miss` = false, `false_alarm` = true, `wrong` = differs; continuous `correct` = within 3 error_sd of truth, `wrong` = more than 2 error_sd away; categorical `correct` = equals, `wrong` = differs. A planned status must equal the attempt status and plan and attempts must be equally many; `error_plan` keys must be exactly the card's states. Skipped when the truth or value is null or the output has no error_sd | Matches the contract's `OUTCOMES`; the overlap between 2 and 3 sd leaves the author room | `CORRECT_SD`, `WRONG_SD` in `validate.py` |
| Rule 7: ranges come from the catalogue (`range` of the measured variable or background field; size at least 0). Extra warning `card_implausible`: a measured value more than 5 error_sd from its truth where the plan has no entry for it (free mode) | The schema covers ranges but not a "CRP 120 for a true 85" slip in free mode | `IMPLAUSIBLE_SD` |
| Rule 8 leak check: a text (note, presenting text, report) naming the primary condition (label or id, case-insensitive, `healthy` class skipped) is a warning unless one of its facts reveals it. A fact reveals it when it is present and caused by the primary alone: for a note its `mentions`, for presenting text `reported`, for a report the test's outputs | A fact caused by several conditions (a cough) reveals no diagnosis | Replace `_reveals` |
| Rule 9: per binary output a stem (output id without digits and `seen`) and regexes "no/without/absence of <stem>" for a true value, "<stem> seen/present" for a false one; outputs named `abnormal*` also match "unremarkable", "within normal limits", "no abnormality"; reports of non-ok attempts and empty reports are skipped | Small and catalogue-agnostic; warnings only | Edit `r9_reports` |
| `repair_prompt(card_json, problems)` lists errors first (all of them, paths never cut), then warnings only while the total stays within 10 lines; line length shrinks with the count; the card is not embedded (only its id is read) | Under 2 000 characters for ten problems (1 700 measured); WP-C1-5 already has the card in the conversation | `_BUDGET`, `_MAX_LINES` |
| `validate_card` accepts a dict or a `Card`, never raises on a malformed card (a rule that meets a malformed part skips it; the schema reports it) | The model may return anything that parses as JSON | – |

## Report (builder fills in at the end)

**Built** (branch `w2/validate`): `patient_engine/validate.py` (rules, `repair_prompt`), 13 codes in `patient_engine/problems.py`, `tests/test_pe_validate.py` (56 tests plus the property test, 0.5 s).

**API**

- `validate_card(card: dict | Card, catalogue) -> list[Problem]`: schema problems first, then rules 1 to 9 in order.
- `has_errors(problems) -> bool`.
- `repair_prompt(card_json: dict | str | None, problems) -> str`.

**New codes**: `card_state_keys`, `card_conditions`, `card_cause_inactive`, `card_unexplained_finding`, `card_unsupported_cause` (warning), `card_attempts`, `card_only_if`, `card_plan_mismatch`, `card_value_range`, `card_implausible` (warning), `card_mention_unknown`, `card_reveals_condition` (warning), `card_report_contradiction` (warning). Everything else the schema catches stays `card_schema`.

**Loop for WP-C1-5**: `problems = validate_card(card, cat)`; if `not has_errors(problems)` accept the card (store the warnings in `provenance.validation`). Otherwise at most twice: send the author `repair_prompt(card, problems)` as the next user message after its own card, parse the reply, validate again. If errors remain after the second repair, discard the card and log its problems. If a reply is not JSON, count that as a repair attempt and send the parse error text instead.

**Not done / limits**: no check that a coexisting illness is a listed co-occurrence pair; no check of `provenance` against `error_plan` (guided without plan); rule 8 does not look for leaks of anything but the primary condition's name; rule 9 is keyword-based and catalogue-agnostic, so it will miss paraphrases. The property test over reference cards skips while `patient_engine.reference` or `patient_engine.skeleton` is missing and was only exercised with a stand-in; it uses the signatures in WP-C1-3 (`design_library(cat, None, 0.1, seed)`, `make_skeleton(cat, i, design, seed)`, `generate_reference(cat, skeleton, seed)`) and skips on a TypeError, so check it ran once WP-C1-3 is merged. If the reference generator writes a null for an `only_if` output that holds (or the reverse), or a plan with fewer states than the card, rules `card_only_if` and `card_state_keys` will say so.

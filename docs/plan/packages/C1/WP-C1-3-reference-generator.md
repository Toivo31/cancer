# WP-C1-3: Skeleton, error plan and reference generator

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P4, P8) |
| Status | not started |
| Size | M |
| Needs | WP-C1-1 (merged: `patient_engine.card`, `.catalogue`, `.schema`) |
| Provides | `design_library(...)`, `make_skeleton(...)`, `generate_reference(...)` |
| Owned paths | `patient_engine/skeleton.py`, `patient_engine/reference.py`, `patient_engine/commands/design.py` (new folder; WP-C1-6 owns `__main__.py`, which loads `patient_engine/commands/*.py`), `tests/test_pe_skeleton*.py`, `tests/test_pe_reference*.py` |
| Review required | no |
| Track | submission |

## Outcome

`generate_reference(catalogue, skeleton) -> Card` produces a valid `card/1` card straight from the
catalogue's numbers (no network). Tests and CI use it; the model-written pipeline (WP-C1-5) uses
the same skeleton and error plan; the audit (WP-C1-7) uses reference libraries as its baseline.

## Interfaces

**Provides**
- `design_library(catalogue, counts: dict[str, int] | None, coexisting_rate, seed) -> list[Skeleton]`
  (counts of cards per primary condition; default stratified: at least 150 per condition, 300 for
  the cancer; a pair from `catalogue.cooccurring()` for a fraction of cards).
- `Skeleton` (frozen): card id, primary condition and attributes, optional coexisting condition,
  background (age band etc. drawn from the catalogue's `background` fields), a variation brief
  (persona hint: one short phrase), `error_plan` (per state, test, attempt, output:
  `correct | miss | false_alarm | wrong`, plus `status: ok | non_diagnostic`), all from keyed random
  numbers `pathway_sim.dists.uniform(seed, patient_index, *key)` so a skeleton never depends on
  how many others exist.
- `make_skeleton(catalogue, index, design, seed)`.
- `generate_reference(catalogue, skeleton, seed) -> Card`: draws every variable in
  `catalogue.generation_order(condition)` with `given_for(cond).resolve(facts)`, then for every
  test, attempt and output the result from the error plan and accuracy numbers, with a template
  report text and notes (one patient account, one GP note). Every test has `max_attempts`
  attempts pre-drawn.
- `python -m patient_engine design --catalogue PATH --seed S --n N` prints the design table
  (counts by condition and pair) and writes a skeleton file (JSON lines).

**Consumes**: `patient_engine.card`, `patient_engine.catalogue` (see `docs/plan/packages/C1/WP-C1-1-contracts.md` Report for the API), `pathway_sim.dists`.

## Acceptance (machine-checkable)

- [ ] Determinism: same `(catalogue, seed, index)` gives equal skeletons and cards; changing `n`
      does not change card 17 (I2, test).
- [ ] Every card of 500 generated from the tiny catalogue passes `card_schema_problems`.
- [ ] Prevalence: with 50 000 skeletons from `catalogue/_examples/tiny`, condition shares are within
      0.5 percentage points of the catalogue (test; use design counts = proportional for this test).
- [ ] Accuracy: over 20 000 cards, the realised sensitivity and specificity of each binary output in
      the tiny catalogue are within 2 percentage points of the catalogue values (test), measured
      from the cards' `observations` against `hidden.findings`.
- [ ] Error plan consistent with results: an output planned `miss` shows false for a true finding;
      `false_alarm` shows true for a false finding; a `non_diagnostic` attempt has no values (test).
- [ ] The same patient and test and attempt give the same result however many times it is asked
      (cards are stored, not recomputed): not applicable here; instead check that attempt k of a
      test does not change when `max_attempts` is raised (I3 spirit, test).
- [ ] Works on `catalogue/lung-primary-care` when it exists (a test that skips if the folder is absent
      and runs 200 cards if present; WP-C2-1 builds it in parallel).
- [ ] Fast tests under 20 s.

## Out of scope

Language model calls, validation rules beyond the schema (WP-C1-4), storage (WP-C1-6), states other
than `all_active`, co-existing illness resolution, return episodes (D40 later; `states` is `["all_active"]`).

## Things to look at and weigh

- Co-existing illness: include it in the skeleton and in `caused_by` (a finding is present if any
  active condition causes it) so the data shape is final, even though only one state is used now.
- Continuous outputs: measurement error from `error_sd`; a categorical `wrong` outcome needs a
  rule (draw a different level). Say what you chose.
- Non-diagnostic attempts: the probability comes from the test's `nondiagnostic`.
- Text reports are templates with the numbers filled in; keep them short and obviously synthetic.
- Memory: 20 000 cards in a test is fine only if each is small; do not store cards, aggregate as you go.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | C1-3-T1 | `Skeleton`, `design_library`, `make_skeleton` with keyed numbers; determinism tests | M | – | I2 and prevalence tests |
| [ ] | C1-3-T2 | Error plan draw per test/attempt/output | S | T1 | consistency test |
| [ ] | C1-3-T3 | `generate_reference` variables and findings with `caused_by` | M | T1 | schema test on 500 cards |
| [ ] | C1-3-T4 | Test results, reports, notes from plan | M | T2, T3 | accuracy test |
| [ ] | C1-3-T5 | `design` subcommand module and docs line in the package file | S | T1 | command prints the table |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

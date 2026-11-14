# WP-C1-3: Skeleton, error plan and reference generator

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P4, P8) |
| Status | built on branch `w2/ref-gen`; awaiting integration |
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
- `python -m patient_engine design --catalogue PATH --seed S --n N` (module `patient_engine/commands/design.py`, `register(subparsers)`, handler in `args.func`; options `--counts`, `--coexisting-rate`, `--proportional`, `--out`; docs in the module docstring) prints the design table
  (counts by condition and pair) and writes a skeleton file (JSON lines).

**Consumes**: `patient_engine.card`, `patient_engine.catalogue` (see `docs/plan/packages/C1/WP-C1-1-contracts.md` Report for the API), `pathway_sim.dists`.

## Acceptance (machine-checkable)

- [x] Determinism: same `(catalogue, seed, index)` gives equal skeletons and cards; changing `n`
      does not change card 17 (I2, test).
- [x] Every card of 500 generated from the tiny catalogue passes `card_schema_problems`.
- [x] Prevalence: with 50 000 skeletons from `catalogue/_examples/tiny`, condition shares are within
      0.5 percentage points of the catalogue (test; use design counts = proportional for this test).
- [x] Accuracy: over 20 000 cards, the realised sensitivity and specificity of each binary output in
      the tiny catalogue are within 2 percentage points of the catalogue values (test), measured
      from the cards' `observations` against `hidden.findings`.
- [x] Error plan consistent with results: an output planned `miss` shows false for a true finding;
      `false_alarm` shows true for a false finding; a `non_diagnostic` attempt has no values (test).
- [x] The same patient and test and attempt give the same result however many times it is asked
      (cards are stored, not recomputed): not applicable here; instead check that attempt k of a
      test does not change when `max_attempts` is raised (I3 spirit, test).
- [x] Works on `catalogue/lung-primary-care` when it exists (a test that skips if the folder is absent
      and runs 200 cards if present; WP-C2-1 builds it in parallel).
- [x] Fast tests under 20 s.

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
| [x] | C1-3-T1 | `Skeleton`, `design_library`, `make_skeleton` with keyed numbers; determinism tests | M | – | I2 and prevalence tests |
| [x] | C1-3-T2 | Error plan draw per test/attempt/output | S | T1 | consistency test |
| [x] | C1-3-T3 | `generate_reference` variables and findings with `caused_by` | M | T1 | schema test on 500 cards |
| [x] | C1-3-T4 | Test results, reports, notes from plan | M | T2, T3 | accuracy test |
| [x] | C1-3-T5 | `design` subcommand module and docs line in the package file | S | T1 | command prints the table |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| **Two plans.** `Skeleton.error_plan` is *nominal* (drawn at skeleton time with condition, attributes and background only); `settle_error_plan(catalogue, skeleton, findings)` is the *settled* plan (same keyed numbers, thresholds resolved with every finding) and is what a card stores in `hidden.error_plan` | Accuracy leaves read findings (sensitivity by lesion size, false alarms with pneumonia) and findings are written after the skeleton, so a plan fixed at skeleton time cannot be exact | Authors call `settle_error_plan` after G1 and give that plan to G2 |
| One keyed uniform `u` per (state, test, attempt, output) decides a binary output: `miss` if `u < 1 - sens` (only on a true finding), `false_alarm` if `u >= spec` (only on a false one), else `correct`. A planned miss on a false finding is `correct` once settled | Realised sensitivity and specificity equal the catalogue's because `u` is independent of the truth; the plan never asks for the impossible | `settle_attempt` in `skeleton.py` |
| **Categorical `wrong`**: `correct` with the output's `accuracy`, else `wrong` and the reported level is drawn uniformly among the *other* levels (second keyed number `err_level`); a one-level variable cannot be wrong | The ticket asked for "a different level"; uniform among the others needs no extra numbers in the catalogue | Weight the other levels by the variable's `given` shares if clinicians want plausible confusions |
| **Continuous and size error**: reported = truth + `error_sd` * z, `z = inv_cdf(u)`, clamped to the variable's range (size at least 0) and rounded to 0.1; outcome `wrong` when `abs(z) >= 1.96`, else `correct`; no `error_sd` means exact | Gives the plan a meaningful `wrong` for measurements (outside the stated error band, 5%) without a new field | `OUTCOME_Z` in `skeleton.py` |
| Something reported that the patient does not have (a false-alarm nodule's size or location) is drawn from the variable's `default` entry (else the primary's) with a keyed number | The schema needs a number where only_if holds; the benign-nodule distribution is the natural one | `_phantom_truth` |
| **Co-existing illness**, findings: each active condition draws separately. Binary: present if any condition with its own `given` entry draws true, or the `default` entry (a background rate, one draw, only when some active condition has no own entry) does; `caused_by` = conditions with own entries that drew true, empty when only the background rate did. Categorical: first active condition (primary first) with an own entry, else `default`. Continuous/size: one value per own entry, the one farthest from the `default` distribution's median in units of its 10-90 spread wins | A cancer next to a pneumonia must show the pneumonia's fever and CRP and keep its own haemoglobin and lesion; a rule that never needs a per-variable direction ("higher is worse") | `draw_findings` in `reference.py` |
| **Co-existing illness**, accuracy: leaves are resolved under each active condition (`condition` fact) and the least favourable is used (min sensitivity, specificity, accuracy; max error and non-diagnostic rate) | A pneumonia that raises false alarms or hides a lesion does so for the cancer patient too; defaults are unchanged when no leaf reads `condition` | `_resolve_worst` in `skeleton.py` |
| Co-existing illness in the design: `coexisting_rate=None` uses the catalogue's `share` (a cancer card gets a pneumonia with probability 0.10 in tiny); a number is the share of cards of every primary that has co-occurrence entries, the pair chosen in proportion to the shares. One illness at most, never equal to the primary | Matches "a pair from `cooccurring()` for a fraction of cards" and lets an experiment raise the rate | `Design.coexisting_rate` |
| Design modes: `make_design` (stratified, counts per primary; default 300 per cancer, 150 otherwise) and `proportional_design(n)` (primary drawn by prevalence). In a stratified design the strata are laid out and shuffled with keyed numbers, so any prefix is mixed; changing a count changes which condition card k gets, never a number inside a card | Stratified libraries need fixed counts; I2 holds for everything but the assignment | `_assignment` |
| Background and prevalence together: proportional draws background first, then the condition from the normalised resolved prevalences; stratified draws the background for the given condition by rejection sampling on `P(condition given background)`, so cancers skew to smokers as the catalogue's `prevalence.by` says | `prevalence` may read background fields; both modes give the same joint distribution | `_draw_primary_and_background` |
| **Background population model** (no `populations/` in `catalogue/1` yet): categorical uniform over its values, binary a fair coin, continuous a normal centred in `range` (SD width/6) truncated to it, default range 0..100 | Nothing better exists in the format | Needs a catalogue field: see Report, "Not done" |
| Attributes are drawn in the skeleton; an attribute whose `by:` reads a variable raises `ValueError` (the model authors would need to draw it with the findings) | A skeleton exists before any finding | Move such an attribute into G1 or forbid it in the lung catalogue |
| Texts: reports are templates ("<test> (synthetic report): output value; ..."), non-diagnostic ones say so; presenting = true symptoms each mentioned with probability 0.75 (at least one); two notes: `n1` patient account (mentions the reported symptoms) and `n2` GP note (first attempt of the first imaging test, mentions that test id) | Short, obviously synthetic, and notes reveal nothing that their `mentions` do not name | `reference.py` |
| `generate_reference(catalogue, skeleton, seed=None)`: the skeleton carries its seed, a different `seed` raises; the card ignores `skeleton.error_plan` and settles its own | One seed per skeleton keeps card id and numbers consistent | – |
| Repeated attempts of a test are independent given the patient | As in `pathway_sim.patients`; a missed lesion is not more likely to be missed again | Add persistence by keying a shared "reader" number per (card, test) |
| `patient_engine/commands/` has no `__init__.py` from this lane (WP-C1-6 owns it); `design.py` imports as a namespace package until then | Avoids a merge conflict | – |

## Report (builder fills in at the end)

**Built** (branch `w2/ref-gen`): `patient_engine/skeleton.py`, `patient_engine/reference.py`, `patient_engine/commands/design.py`,
`tests/test_pe_skeleton.py` (20 tests, about 7 s), `tests/test_pe_reference.py` (14 tests + 1 skipped until `catalogue/lung-primary-care` exists, about 17 s;
the 20 000-card accuracy test is about 9 s).

**Public API**

- `patient_engine.skeleton`: `Skeleton` (frozen; `id, index, seed, catalogue_id, catalogue_hash, primary, attributes, coexisting,
  coexisting_attributes, background, brief, error_plan, states`; `.conditions`, `.condition_ids`, `.all_attributes()`, `.to_json()`),
  `skeleton_from_json`, `Design`, `default_counts(cat)`, `make_design(cat, counts, coexisting_rate)`, `proportional_design(n, coexisting_rate)`,
  `design_library(cat, counts, coexisting_rate, seed) -> list[Skeleton]`, `make_skeleton(cat, index, design, seed, *, plan=True)`,
  `settle_error_plan(cat, skeleton, findings, state)`, `settle_attempt(cat, test, k, skeleton, values, state) -> (PlannedAttempt, values)`,
  `nominal_error_plan`, `design_table(skeletons)`, helpers `common_facts`, `finding_values`, `holds`, `pick`.
- `patient_engine.reference`: `generate_reference(cat, skeleton, seed=None) -> Card`, `draw_findings(cat, skeleton, state)`,
  `reference_cards(cat, design, seed)` (generator), `report_text`.
- `patient_engine.commands.design`: `register(subparsers)` (handler in `args.func`, returns the exit code), `run_design(...)`,
  `format_table`, `write_skeletons`, `scale_counts`, `parse_counts`.

**How the model authors (WP-C1-5) use it**

1. `design = make_design(cat, counts, rate)`; `sk = make_skeleton(cat, i, design, seed)` for every card. The skeleton's primary condition,
   attributes, co-existing illness, background and `brief` are fixed inputs to G1 (the model writes findings, causes and the story around them).
2. After G1, with the findings (`Finding` objects or plain values) call `plan = settle_error_plan(cat, sk, findings)["all_active"]`:
   per test and attempt a status and an outcome per output (`correct | miss | false_alarm | wrong`). Give it to G2: write a concrete result that
   fits the plan and the findings (a `miss` is only planned for a true finding, a `false_alarm` for a false one; a `wrong` categorical or
   measured output differs from the truth). Store the plan as `hidden.error_plan` with `provenance.error_source = "guided"`.
   `Skeleton.error_plan` (nominal) is only an early look; it can differ from the settled plan where an accuracy number reads a finding.
3. `settle_attempt(...)` also returns the values the plan implies when followed literally; use it as a repair target or as a check
   (the validator, WP-C1-4, can recompute the settled plan from the stored card and compare).
4. Per card draw `u` keys are `uniform(seed, index, ...)`; the model's output is not repeatable, the skeleton and plan are.

**Not done / limits**

- Background has no population model in `catalogue/1`: defaults are crude (uniform categories, centred truncated normal), so a never-smoker can
  have 80 pack-years and ages are about 59 +/- 14 for range 18..100. Needs a catalogue field (a `population`/`distribution` per background
  field in the `pathway_sim/dists.py` vocabulary, optionally `by` another field) or the future `populations/` folder; a QUESTION was posted.
- Only the `all_active` state; resolved states, return episodes and illness-resolution are out of scope as specified.
- Attempts of a test are independent given the patient; no reader persistence.
- A catalogue attribute whose `by:` reads a variable cannot be drawn in a skeleton and raises.
- The lung catalogue test skips until `catalogue/lung-primary-care` exists; its body was run against the tiny catalogue.

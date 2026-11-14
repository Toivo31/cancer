# WP-W8-7: Clinician review of the catalogue `lung-primary-care`

| | |
|---|---|
| Component | C2 clinical catalogue; C7 evidence (honesty rules); D46, D47, D50, D59 |
| Status | not started; needs a clinician |
| Size | reviewer: about 3 to 4 hours for the core read; agent: S per ticket to prepare and to apply |
| Needs | a clinician (Finnish primary care or respiratory medicine); T1 can start now |
| Owned paths | new `docs/review_clinical/` (reading guide, reviewer's sheet, corrections log); applying corrections: `catalogue/lung-primary-care/*.yaml`, `params/sources.yaml`, `populations/lung_primary_care.yaml` pin, `libraries/ref500`, `docs/decisions.md` (integrator) |
| Do not edit | anything while `w8/catalogue-check` style lanes hold the catalogue: one catalogue editor at a time (the hash changes on every edit) |
| Review required | yes (medical content; numbers in the pitch) |
| Track | needs a human; after submission (until then the catalogue stays labelled draft, as the pitch says) |

## Outcome

A clinician has read the parts of the catalogue that drive the story, marked each number "plausible / wrong (with a better
value) / cannot say", and the corrections are in a new catalogue version with its hash, regenerated reference library and an
entry in the decisions log. The catalogue's `status: draft` changes only when the reviewer says so, in their words.

## Why

`python scripts/catalogue_stats.py catalogue/lung-primary-care` (catalogue v2, hash `436ff728b717`): 370 reference numbers,
112 sourced, **258 assumptions**. A literature check of the numbers that drive tonight's cards was done by an agent
(`w8/catalogue-check`, D59): it is not a clinical read and this package does not repeat it; the reviewer should start from its
result, not from scratch.

## What the reviewer reads, in this order (a reading guide for T1 to produce)

1. **The story numbers** (15 minutes): the five numbers printed by `catalogue_stats.py` ("the five numbers that matter
   most") and the condition list with shares among presenters (`conditions.yaml`). Question: is this mix what a Finnish health
   centre sees in adults with chest or general symptoms (assumption V2)?
2. **Who does what** (30 minutes): `care.yaml`: nurse and GP roles, the 24 GP actions, definitive tests per condition, costs,
   turnaround and capacity (D46). Question: would a Finnish GP order and refer like this; are any actions missing or impossible?
3. **Symptoms and signs by condition** (60 minutes): `conditions.yaml` and `variables.yaml` findings, starting with lung
   cancer, pneumonia, COPD exacerbation and the two no-disease conditions (worried well, D47; no disease found: see the open
   D59 question in WP-W8-9 H5). Use `docs/research/catalogue/conditions_symptoms.md` for the sources behind each.
4. **Test accuracy and lab values** (60 minutes): `tests.yaml`, group tests (D50), with `docs/research/catalogue/tests_labs.md`.
5. **Assumptions by weight** (remaining time): the assumption-graded numbers sorted by how much they move the encounter
   loop's outputs. T1 decides how to sort (a quick one-at-a-time perturbation with `scripts/encounter_report.py` is one way;
   another is the order of `docs/ledger.md`). The reviewer stops when time runs out; the sheet records what was not read.
6. Optional: five patient cards from `ref500` and five from a model-written library, side by side (the cards data written
   by `demo/export_cards.py`, or the patient engine's command line; T1 picks what exists and is readable for a clinician). Question: would these patients walk in?

## How corrections flow back

reviewer's sheet → agent applies in one branch (one catalogue editor at a time) → each changed number gets `source:` (the
reviewer, as "expert opinion, <role>, <date>", grade C, added to `params/sources.yaml`) or stays `assumption` with the
reviewer's note → `catalogue_stats.py` before and after → **catalogue hash changes** → update the population hash pin
(`populations/lung_primary_care.yaml`, `tests/test_population_model.py`, `tests/test_pe_results_author_v2.py`) → regenerate
`ref500` and run the audit (40 of 40) → **model-written libraries made for the old hash no longer match** (their tests skip;
regenerate with `scripts/generate_gemini.sh` or label them as made for the old version) → rerun `scripts/encounter_report.py`
(the loop's pinned ranges may move; if they do, that is a finding, not something to tune away silently) → refill the pitch
(`docs/pitch/fill_numbers.py`) → one row in `docs/decisions.md`.

## Acceptance

- [ ] `docs/review_clinical/reading_guide.md` and a sheet (one row per number: file, id, value, source, grade, reviewer's
      verdict, better value, note) generated from the catalogue by a script, so the sheet matches the hash it was made from.
- [ ] After corrections: `catalogue_stats.py` shows the change in sourced vs assumption; audit of the new `ref500` 40 of 40;
      every test that pins a hash updated in the same commit; corrections log lists every changed number.
- [ ] Edge: a number the reviewer marks "wrong" without a better value stays as it is and is listed as "disputed" in the
      sheet and the ledger, not silently changed.

## Tickets

| | ID | Ticket | Size | Owner | Needs | Done when |
|---|---|---|---|---|---|---|
| [ ] | W8-CR-T1 | Write the reading guide and generate the reviewer's sheet from the catalogue (with hash) | S | agent | `w8/catalogue-check` merged (it is) | guide and sheet exist; sheet regenerates byte-identically for the same hash (test) |
| [ ] | W8-CR-T2 | Find and brief a clinician; agree what can be credited and how | S | **human (Tuomas)** | T1 | a named reviewer and date |
| [ ] | W8-CR-T3 | Review session (sections 1 to 4 at least) | M | **clinician** | T2 | filled sheet returned |
| [ ] | W8-CR-T4 | Apply corrections, new hash, pins, ref500, audit, encounter report, pitch refill, decision row | M | agent | T3 | acceptance items 2 and 3 |
| [ ] | W8-CR-T5 | Decide whether the catalogue's `status: draft` changes, and the wording in the pitch | S | **human (Tuomas, with the reviewer)** | T4 | wording agreed; pitch lane updates its templates |

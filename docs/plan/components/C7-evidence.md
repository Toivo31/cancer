# C7 Evidence and validation

| | |
|---|---|
| Where | `params/`, `docs/validation.md`, `docs/sensitivity.md`, `docs/parameters.md`, `docs/review.md`, `docs/pitch/`, `pathway_sim/calibrate.py`, `pathway_sim/sensitivity.py` |
| State | Exists and is the entry's strongest point on "data quality and transparency" (20% of the score). A consistency sweep, the ledger and ranges are in progress on `plat/evidence` |
| Used by | Every component; the pitch |
| Track | Submission track for the numbers the judges see; platform track for making it a product feature |

## Purpose

Make every claim checkable: where each number came from, how sure we are, what the model was
checked against, and how much the result moves when the uncertain inputs move.

## What exists

- A source registry (`params/sources.yaml`) and parameter tables where each value has a source or
  `assumption`.
- The **Norwegian check**: the published pathway (Stokstad 2019), rebuilt and calibrated, gives
  the published 40% treated within 42 days; the authors' reordered pathway and their estimate of
  80% are reproduced; the optimiser, started blind from the observed pathway, finds a reorder in
  the same family. Wording rules: 80 is the authors' own modelled estimate; 88 needs the faster
  scanner; 67 needs no new equipment.
- The **Finnish scenario**: synthetic county, held-out patients; headline 18% to 33% within the
  provisional 90-day target with two reorders and no new equipment; subgroups 13 to 26 and 27 to
  50. The urgent-booking figure (61.5%) is a conditional finding that depends on assumed booking
  times and is never the headline.
- Sensitivity runs with tornado data, bootstrap intervals, external checks (rapid CT, faster
  PET), and an independent review (`docs/review.md`) whose fixes are in.

## Honesty rules (apply to every component and every document)

1. Synthetic data only, and labelled as such wherever a number appears.
2. A number is shown with its kind: published, calibrated to a published figure, simulated from
   sourced inputs, simulated from assumptions, or conditional on an assumption.
3. Headline numbers come from held-out patients, with a range.
4. The same number is the same everywhere. `docs/pitch/fill_numbers.py` fills documents from the
   bundle; hand-typed headline numbers are not allowed in pitch files.
5. Negative results stay in (the faster-scanner over-prediction, the decision model only tying
   the rule policy, the half-compute claim not reproduced).
6. A language-model draft is never presented as a sourced value.

## What changes for the vision

| # | Change | Depends on |
|---|---|---|
| V1 | **The ledger covers the catalogue**: counts of entries by grade (A, B, C, assumption, draft) per catalogue, shown in the product | C2 K7; `params/ledger.py` from `plat/evidence` |
| V2 | **Cohort checks as evidence**: each cohort's check report (marginals, derived published quantities) is stored and shown | C1 P8 |
| V3 | **Golden checks in the gate**: Norway through the CLI and through the service template; pitch numbers against the bundle | `WP-INFRA-1`; the first one exists as `tests/test_golden_templates.py` |
| V4 | **Robustness of every accepted optimiser change** under the low and high values of what it depends on | C5 O6 |
| V5 | **Calibration against Finnish published waits** as a repeatable job, rerun whenever the catalogue or the judgement matrices change | C3 E4 |
| V6 | **Clinical read-through** of the catalogue and the judgement matrices by someone medically trained; until then everything says "draft" | a human |

## Sub-wholes (for the spec agent)

| # | Sub-whole | Contains |
|---|---|---|
| H1 | Ledger over catalogue and scenarios | V1 |
| H2 | Golden checks and number consistency in the gate | V3, rule 4 |
| H3 | Robustness and calibration as jobs in the service | V4, V5 (old tickets M8-2, M8-3) |
| H4 | Review rounds | an independent reviewer per wave on numbers and the information boundary |

# WP-C2-1: First catalogue `lung-primary-care`

| | |
|---|---|
| Component | C2 `components/C2-clinical-catalogue.md` (K2 migration, K3 to K5 content, a first K8) |
| Status | not started |
| Size | M |
| Needs | WP-C1-1 (merged: `patient_engine.catalogue`, `catalogue/README.md`), WP-C2-R1 and R2 (merged: `docs/research/catalogue/*.md`) |
| Provides | the catalogue `catalogue/lung-primary-care/` (draft), loaded by every later package |
| Owned paths | `catalogue/lung-primary-care/`, `params/sources.yaml` (append new sources only), `tests/test_catalogue_lung.py`, `scripts/catalogue_stats.py` |
| May create | the above |
| Review required | yes: medical content (a clinician has not read it; it stays `status: draft`) |
| Track | submission (Sunday slice item 2) |

## Outcome

`python -c "from patient_engine.catalogue import load_catalogue; c = load_catalogue('catalogue/lung-primary-care'); print(len(c.conditions), len(c.variables), len(c.tests))"`
loads without errors. `python scripts/catalogue_stats.py catalogue/lung-primary-care` prints counts of
leaf numbers by `source` kind (sourced / assumption / llm_draft) and by grade, plus the five numbers
that matter most (see below) with their source.

## Why

Everything downstream (reference generator, model-written cards, audit, adapter) needs one real
catalogue. The two research notes hold the numbers but not in the format.

## What to build

- **Setting and scope** in `catalogue.yaml`: adults contacting primary care with chest or general
  symptoms; prevalence is among presenters; `status: draft`; background fields: age, sex,
  smoking_status, pack_years, region (rural/urban or the research note's equity-relevant split).
- **Conditions** (8 to 12) from C2 and R1: lung cancer (attributes: stage, histology group,
  location), pneumonia, COPD exacerbation, asthma, heart failure, tuberculosis, benign nodule,
  reflux or post-infectious cough, self-limiting viral illness, no disease found. Prevalence with
  `by: smoking_status` where R1 gives it.
- **Variables** (25 to 40): symptoms, signs, true lab values (hb, platelets, crp, calcium, alp,
  ldh), imaging truth (lesion present, size, location, mediastinal nodes, distant spread,
  consolidation), function (fev1 percent). A distribution per condition with `default`.
- **Tests** (15 to 20) from R2 and `params/test_accuracy.yaml`: history, examination, bloodwork,
  chest X-ray, CT, low-dose CT, PET-CT, spirometry, bronchoscopy, EBUS, CT-guided biopsy,
  sputum cytology, histology report. Each output measures one variable; accuracy, nondiagnostic
  rate, timing, cost, harm, `positive_when`. **Process steps are not tests** (referral letters,
  triage, board meetings stay in the flowchart).
- **Cooccurrence**: lung cancer with pneumonia, lung cancer with COPD (R1 section on co-occurrence).
- **Migration (K2)**: every sourced number in `scenarios/finland_lung.yaml` and
  `params/test_accuracy.yaml` appears in the catalogue with the same source id.
- **Sources**: add the new sources listed in the two research notes to `params/sources.yaml`
  (append only; keep the file's existing style; check ids are unique).

## Acceptance

- [ ] `load_catalogue('catalogue/lung-primary-care')` raises no error; warnings are listed in the report.
- [ ] A test (`tests/test_catalogue_lung.py`) checks: counts within the ranges above; every test
      output `measures` a variable; the seven current Finnish conditions are all representable
      (mapping table in the test or a note); the migrated numbers equal the originals (read the
      two source files and compare at least: chest X-ray, low-dose CT, PET-CT, bronchoscopy by
      location, needle biopsy sensitivity and specificity).
- [ ] No leaf number lacks a source; none is `llm_draft` unless you say so in the report.
- [ ] `scripts/catalogue_stats.py` runs and prints the table (test: it exits 0 and prints "sourced" and "assumption").
- [ ] The five headline numbers are stated with source: lung cancer share among presenters,
      pneumonia share, chest X-ray sensitivity, low-dose CT sensitivity, haemoptysis frequency.
- [ ] Fast: tests under 10 s.

## Decisions for the builder (leans)

- **Where research and the current scenario disagree** (R1 section "Comparison with the current
  scenario": pneumonia 17% vs about 5%, lung cancer 1.6% vs 0.8 to 1.3%, benign nodule 3% vs 1.8%),
  use the sourced value, grade it as R1 does, and put the scenario's current value in `note`.
  List every such choice in the report. Tuomas has been asked whether the catalogue follows the
  sources or the scenario; the lean is the sources.
- Where R1 or R2 says "could not source": use the suggested assumption, `source: assumption`,
  reasoning in `note`.
- Where R2 gives a pooled value that differs from the carried one (CT biopsy pneumothorax
  26% vs 15%), keep both: carried one as the entry, the other in `note` with its source id, and list it.
- Numbers were read through a summarising tool: put "re-check against the page" in `note` for
  any value that is not already in `params/`.
- Keep ids snake_case and stable; a later model prompt will contain them.

## Out of scope

Behaviour (`behaviour.yaml`), treatments, constraints, populations folders; the audit tolerances;
rendering. Do not edit `patient_engine/` (if the format cannot express something, post a QUESTION
to claude-code@tuomas/architect with the example and carry on with the closest expression).

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [ ] | C2-1-T1 | `catalogue.yaml`, `conditions.yaml`, populations in `background` | S | loads, counts test |
| [ ] | C2-1-T2 | `variables.yaml`: symptoms and signs | M | loads |
| [ ] | C2-1-T3 | `variables.yaml`: lab, imaging, function truth | M | loads |
| [ ] | C2-1-T4 | `tests.yaml` incl. migration of sourced entries; sources appended | M | migration test passes |
| [ ] | C2-1-T5 | `cooccurrence.yaml`; `scripts/catalogue_stats.py`; test file | S | stats and tests pass |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

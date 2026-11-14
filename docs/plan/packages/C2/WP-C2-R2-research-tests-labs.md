# WP-C2-R2: Research: test accuracy, laboratory value distributions, report times

| | |
|---|---|
| Component | C2 `components/C2-clinical-catalogue.md`, K5 and the lab/imaging/function half of K4 |
| Status | not started |
| Size | M |
| Needs | – (WP-C2-1 converts the note into `tests.yaml` and `variables.yaml`) |
| Provides | `docs/research/catalogue/tests_labs.md` |
| Owned paths | `docs/research/catalogue/tests_labs.md` only |
| Review required | yes: medical content |
| Track | submission |

## Outcome

A research note a converter agent can turn into `tests.yaml` and the `lab_true`,
`imaging_true` and `function_true` part of `variables.yaml` without searching again.

## Scope

Read C2 "Scope of the first catalogue" (the test table) and `params/test_accuracy.yaml` first.
**Already sourced entries there are carried over unchanged**: list them in a "Carried over"
table with their existing source ids and do not research them again, except where they are
marked `assumption` (for example diagnostic CT sensitivity and specificity): research those.

1. **Tests**, for each: what it reveals (which hidden variable), sensitivity and specificity for
   lung cancer (and for the look-alike where relevant: chest X-ray for pneumonia, spirometry for
   COPD), non-diagnostic or failed-sample rate, report turnaround in days (Finnish or Nordic if
   possible), invasive or not, complication rate for invasive ones, cost in euros if a Finnish
   price list or study gives one (optional). Tests: structured history and physical examination
   (how often a symptom present is elicited, if anything is published; otherwise say so), basic
   blood count, CRP, chemistry (calcium, ALP, LDH), chest X-ray, CT chest with contrast,
   low-dose CT, PET-CT, brain MRI for staging, spirometry, bronchoscopy with biopsy, EBUS-TBNA,
   CT-guided needle biopsy, sputum cytology, histology report, molecular marker panel turnaround.
   Sensitivity of chest X-ray by nodule size and location if available.
2. **Laboratory and measured values by condition** (distribution: median and p10/p90, or mean
   and SD, with unit): haemoglobin (anaemia share in lung cancer at presentation), platelets
   (thrombocytosis share; note its PPV for cancer from primary-care studies), CRP in pneumonia vs
   other, calcium (hypercalcaemia share in lung cancer), ALP, LDH, FEV1 % predicted in COPD.
3. **Imaging truth**: size distribution of lung cancer at diagnosis by stage or overall;
   share with enlarged mediastinal nodes; share with distant spread at diagnosis (ties to stage).

## Acceptance

- [ ] Tables with columns: `entry` (proposed id, e.g. `chest_xray.abnormal`), `measures`
      (hidden variable), `value`, `low`, `high`, `unit`, `source` (citation + URL/DOI),
      `population/setting`, `grade`, `note`.
- [ ] Every value comes from a page you opened in this session (WebSearch/WebFetch). Never from
      memory; such numbers go to "Could not source".
- [ ] "Carried over" table, "New sources" (proposed ids in the style of `params/sources.yaml`,
      reusing existing ids), "Could not source" with suggested assumptions and reasoning.
- [ ] For each test, say whether it is a medical test or a process step (C2 rule 5: process steps
      are not tests) when you meet something in `scenarios/finland_lung.yaml` that is listed as a
      test but is a process step.

## Out of scope

Conditions, prevalence, symptoms (WP-C2-R1). Writing YAML. Editing any other file.

## Rules

Same as WP-C2-R1: short quotes only, grade honestly, stop at about 75 minutes with gaps listed.

## Tickets

| | ID | Ticket | Done when |
|---|---|---|---|
| [ ] | R2-T1 | Starting point: carried-over table from `params/test_accuracy.yaml` | section present |
| [ ] | R2-T2 | Imaging tests accuracy (X-ray by size/location, CT, LDCT, PET-CT, MRI) | table filled or gaps listed |
| [ ] | R2-T3 | Tissue and endoscopy tests (bronchoscopy, EBUS, CT biopsy, cytology, histology, markers) | table filled |
| [ ] | R2-T4 | Bloodwork and spirometry: test outputs and true-value distributions by condition | table filled |
| [ ] | R2-T5 | Imaging truth distributions; report times; new sources; could-not-source | all sections present |

## Report (builder fills in at the end)

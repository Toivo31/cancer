# WP-C2-1: First catalogue `lung-primary-care`

| | |
|---|---|
| Component | C2 `components/C2-clinical-catalogue.md` (K2 migration, K3 to K5 content, a first K8) |
| Status | built on branch w2/lung-cat; awaiting clinician review (content stays `status: draft`) |
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
| [x] | C2-1-T1 | `catalogue.yaml`, `conditions.yaml`, populations in `background` | S | loads, counts test |
| [x] | C2-1-T2 | `variables.yaml`: symptoms and signs | M | loads |
| [x] | C2-1-T3 | `variables.yaml`: lab, imaging, function truth | M | loads |
| [x] | C2-1-T4 | `tests.yaml` incl. migration of sourced entries; sources appended | M | migration test passes |
| [x] | C2-1-T5 | `cooccurrence.yaml`; `scripts/catalogue_stats.py`; test file | S | stats and tests pass |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| Sourced value over the scenario's: lung cancer 0.013 (BRADLEY2021, B; was 0.016 = 0.005 + 0.011), range 0.008 to 0.016 | R1 section 8; the scenario's value is the high bound and is in the note | `conditions.yaml`, `lung_cancer.prevalence` |
| Sourced over scenario: pneumonia 0.05 (VANVUGT2012, grade A as R1; was 0.17) | GRACE radiograph-confirmed, acute-cough presenters only | `pneumonia.prevalence` |
| Sourced over scenario: benign nodule 0.018 (VANVUGT2012, B; was 0.03) | upper value, includes undiagnosed cancers | `benign_nodule.prevalence` |
| Sourced over scenario: tumour location central 0.377 / peripheral 0.623 (KOSIN2014, C; was 0.35 / 0.65), made to depend on histology (same series) | R1 section 2b | `lung_cancer.attributes.location` |
| Sourced over scenario: CT malignancy reading sensitivity 0.948 and specificity 0.755 (WEIRMCCALL2020, B proxy; scenario 0.95 / about 0.80, both assumptions) | R2 section 2 | `tests.yaml` `chest_ct.suspicious_for_malignancy` |
| Sourced over scenario: needle biopsy non-diagnostic 0.027 for peripheral (UZUN2017; scenario 0.08); central 0.35 (scenario assumption) carried | the scenario had the sourced number only in a note | `ct_guided_biopsy.nondiagnostic` |
| Assumption, R1 range midpoint: COPD exacerbation 0.075 (range 0.05 to 0.10; was 0.14), reflux or post-infectious cough 0.055 (0.03 to 0.08), heart failure 0.05, no disease found 0.20; viral illness is the remainder 0.479 (was self_limiting 0.344) | R1 section 9: "renormalise through self_limiting"; scenario's other_benign 0.30 split across asthma 0.059 (CHEN2020 proxy), heart failure, reflux, no disease found | `conditions.yaml` |
| Prevalence by smoking status: lung cancer from LEE2012 relative risks (current 8.43; former 3.0 assumed inside R1's 2 to 4) and an assumed smoking mix 0.40 / 0.38 / 0.22; COPD by smoking is an assumption; viral illness absorbs the change so every level adds to 1 | R1 section 3 formula; gives about 12% never-smokers among cancers (FILHA2026 says 10 to 15%) | `prevalence.by.smoking_status` |
| Stage mix I 0.17 / II 0.09 / III 0.15 / IV 0.59 is derived from several sources, one source field (KHALIFE2025), grade C | no single source; III is a remainder | `lung_cancer.attributes.stage` |
| Chest X-ray: carried BRADLEY2021 0.754 / 0.902; sensitivity rises with lesion size (0.47, 0.66, 0.81), scaled so the cancer average stays 0.754 (checked in the test); false-positive rates by condition carried from the scenario | R2 section 9 suggestion | `chest_xray.abnormal` |
| Scenario p_positive for non-cancer conditions on CXR (benign nodule 0.90) and CT (pneumonia 0.15, benign nodule 0.65, others) not carried: they were assumptions and the new structure gives its own values (benign nodules are small, so the film mostly misses them) | CT reads a lesion first, then its malignancy | `chest_ct`, `chest_xray` |
| Bronchoscopy: RIVERA2013 sensitivities by location and size carried; the scenario's p_nondiagnostic (0.12 / 0.45) is 1 - sensitivity, so no `nondiagnostic` is given | counting it twice would halve the yield | `bronchoscopy`; add a `nondiagnostic` if the adapter needs it |
| Pooled-versus-carried (carried is the entry, the other is in `note` and in `low` or `high`): PET-CT 0.968 / 0.778 (GOULD2001, stand-alone PET) vs 0.89 / 0.70 (LI2018, PET-CT, grade A; low bound); needle biopsy pneumothorax 0.15 (WIENER2011) vs 0.259 (HUO2020; high), chest tube 0.066 vs 0.069 (HUO2020); needle sensitivity 0.90 (RIVERA2013) vs 0.973 (UZUN2017; high); EBUS sensitivity 0.89 (GELBERG2014) vs 0.76 unselected (ALMEIDA2012; low); CXR 0.754 vs 0.80 (HSSIB2021, BRADLEY2019; high) | acceptance says carried values stay; PET-CT in particular may deserve LI2018 as the central value | the leaf's `value` |
| Clinical clubbing 0.075 (assumption; research index 0.33 in the note) | R1 section 9 | `finger_clubbing` |
| Costs only where the scenario had a placeholder (CXR 40, CT 250, bronchoscopy 1200, needle 900, PET-CT 1500); no cost for other tests | no Finnish price list | `cost_eur` |
| Lab analytical error not modelled (no `error_sd` on bloods, spirometry); CT size error 2 mm is an assumption | none sourced | `error_sd` |
| 16 tests, 32 variables, 10 conditions; brain MRI added (R2 has data), molecular panel left out | pathway does not use marker status | `tests.yaml` |

## Report (builder fills in at the end)

**Built** (branch `w2/lung-cat`): `catalogue/lung-primary-care/` (draft), 54 sources appended to `params/sources.yaml`, `tests/test_catalogue_lung.py` (21 tests, under 1 s), `scripts/catalogue_stats.py`.

| | |
|---|---|
| Conditions | 10 (cancer with stage, histology, location; pneumonia, COPD exacerbation, asthma, heart failure, tuberculosis, benign nodule, reflux or post-infectious cough, viral illness, no disease found) |
| Variables | 32 (11 symptoms, 4 signs, 6 lab truths, 7 imaging truths, 2 function, 2 tissue) |
| Tests | 16 (history, examination, blood count, CRP, chemistry, chest X-ray, CT, low-dose CT, PET-CT, brain MRI, spirometry, bronchoscopy, EBUS, CT-guided biopsy, sputum cytology, histology report) |
| Co-occurrence | lung cancer with COPD 0.50 (YOUNG2009), with pneumonia 0.023 (WEINBERG2021) |
| Reference numbers | 261 (204 entries, 57 `by:` levels): 84 sourced (A 10, B 42, C 32), 177 assumption, 0 llm_draft |
| Loader warnings | none |

**Headline numbers**: lung cancer share among presenters 0.013 (BRADLEY2021, B); pneumonia 0.05 (VANVUGT2012, A); chest X-ray sensitivity 0.754 (BRADLEY2021, B); low-dose CT sensitivity 0.846 (HOREWEG2014, B, screening population); haemoptysis in lung cancer 0.202 (ADES2014, B; 0.015 in matched controls, risk of cancer after new haemoptysis 3.1% KOO2023 is in a note).

**Checked by sampling** (400,000 synthetic presenters through the catalogue, my own script, not in the repo): condition shares match the prevalences, lung cancer 0.0133, chest X-ray sensitivity among cancers 0.756, platelets above 400 in 29.8% of cancers, haemoptysis 20.4% of cancers. The chest X-ray positive predictive value comes out about 0.14, above BRADLEY2021's 0.09, because the scenario's false-positive rates (carried) are lower than the cohort's 0.902 specificity; the audit should look at it.

**Format limitations hit** (QUESTION posted to architect): no normal distribution in `pathway_sim/dists.py` (haemoglobin is 20 quantile values); a condition attribute has one source field, so the stage mix cites its main source and lists the rest in the note; no field for numbers that depend on prevalence or downstream value (NPV, PPV, PET-CT changed the plan in 2%), they stay in notes; `low`/`high` have no source of their own; co-occurrence can only name the COPD exacerbation although the sourced 0.50 is COPD present; `positive_when` cannot carry a note; `region` is a visible field that no number uses yet (populations/ not read).

**Problem found outside my paths**: `tests/test_params.py::test_no_unused_sources` fails (57 registered ids are cited only by the catalogue, limit 3). Posted as PROBLEM; the test should count catalogue sources.

**Clinician: check first**
1. The assumption-graded condition shares (COPD exacerbation 0.075, heart failure 0.05, reflux 0.055, no disease found 0.20, viral 0.479) and the smoking mix 0.40 / 0.38 / 0.22 with former-smoker relative risk 3.0: they decide the whole presenter mix.
2. Symptom frequencies of the look-alike conditions (asthma, COPD, heart failure, tuberculosis, viral): almost all assumptions; conditions with no number fall back to control-population rates.
3. History 0.85 and examination 0.60 sensitivities, and the alarm readings in `positive_when` of history, examination and CRP (50 mg/L).
4. Brain metastasis and mediastinal node shares by stage (assumptions tuned to R2's overall figures), and `distant_spread` = stage IV by definition.
5. Whether PET-CT should carry LI2018 (0.89 / 0.70) as its central value, and whether COPD present at 50% of cancers should be modelled as an exacerbation.

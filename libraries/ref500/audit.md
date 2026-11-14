# Library audit: PASS

Library `L_1d58bd5a943c00e9` (500 cards, generator `llm`, model `fake`, error source `guided`), catalogue `lung_primary_care` (`2bcb9c78b2e0`).

States: all_active 500, asthma_resolved 42, benign_nodule_resolved 42, copd_exacerbation_resolved 67, heart_failure_resolved 42, pneumonia_resolved 44, reflux_postinfectious_cough_resolved 42, tuberculosis_resolved 42, viral_self_limiting_resolved 41. Accuracy and non-diagnostic checks use every state (all_active and the resolved states pooled as `resolved`); frequency checks use `all_active` of single-illness cards.

Tolerance: a cell fails when it is outside the 4.2-sigma interval and more than the check's percentage points from the catalogue's expectation. See `audit_tolerances.yaml` for each number and its reason.

| Check | Result | Detail |
|---|---|---|
| `findings.asthma` | PASS | 46 of 46 cells within tolerance, 4 skipped (too few cases) |
| `findings.benign_nodule` | PASS | 50 of 50 cells within tolerance |
| `findings.copd_exacerbation` | PASS | 46 of 46 cells within tolerance |
| `findings.heart_failure` | PASS | 46 of 46 cells within tolerance, 4 skipped (too few cases) |
| `findings.lung_cancer` | PASS | 54 of 54 cells within tolerance |
| `findings.no_disease_found` | PASS | 46 of 46 cells within tolerance, 4 skipped (too few cases) |
| `findings.pneumonia` | PASS | 46 of 46 cells within tolerance |
| `findings.reflux_postinfectious_cough` | PASS | 46 of 46 cells within tolerance |
| `findings.tuberculosis` | PASS | 50 of 50 cells within tolerance |
| `findings.viral_self_limiting` | PASS | 46 of 46 cells within tolerance |
| `findings.worried_well` | PASS | 46 of 46 cells within tolerance |
| `accuracy.history` | PASS | 44 of 44 cells within tolerance |
| `accuracy.examination` | PASS | 14 of 14 cells within tolerance, 2 skipped (too few cases) |
| `accuracy.chest_xray` | PASS | 7 of 7 cells within tolerance, 1 skipped (too few cases) |
| `accuracy.chest_ct` | PASS | 14 of 14 cells within tolerance |
| `accuracy.low_dose_ct` | PASS | 4 of 4 cells within tolerance |
| `accuracy.pet_ct` | PASS | 8 of 8 cells within tolerance |
| `accuracy.brain_mri` | PASS | 2 of 2 cells within tolerance, 2 skipped (too few cases) |
| `accuracy.spirometry` | PASS | 4 of 4 cells within tolerance |
| `accuracy.bronchoscopy` | PASS | 4 of 4 cells within tolerance |
| `accuracy.ebus_tbna` | PASS | 4 of 4 cells within tolerance |
| `accuracy.ct_guided_biopsy` | PASS | 4 of 4 cells within tolerance |
| `accuracy.sputum_cytology` | PASS | 4 of 4 cells within tolerance |
| `accuracy.histology_report` | PASS | 2 of 2 cells within tolerance |
| `accuracy.nt_probnp` | PASS | 4 of 4 cells within tolerance |
| `accuracy.dx_lung_cancer_histology` | PASS | 4 of 4 cells within tolerance |
| `accuracy.dx_pneumonia_chest_xray` | PASS | 3 of 3 cells within tolerance |
| `accuracy.spirometry_reversibility` | PASS | 6 of 6 cells within tolerance |
| `accuracy.echocardiography` | PASS | 3 of 3 cells within tolerance |
| `accuracy.mycobacterial_culture` | PASS | 3 of 3 cells within tolerance |
| `accuracy.ct_nodule_followup` | PASS | 3 of 3 cells within tolerance |
| `accuracy.ph_monitoring` | PASS | 3 of 3 cells within tolerance |
| `accuracy.respiratory_virus_pcr` | PASS | 3 of 3 cells within tolerance |
| `non_diagnostic` | PASS | 52 of 52 cells within tolerance |
| `state_consistency` | PASS | 0 of 362 resolved states with a violation (0.00%); limit 0.00% |
| `presenting` | PASS | 0 of 1139 reported complaints that are not true symptoms (0.00%); limit 0.00% |
| `diversity` | PASS | 0 of 500 cards that repeat an earlier card (0.00%); limit 2.00% |
| `leak` | PASS | 0 of 1724 notes flagged by the validator's leak rule (0.00%); limit 2.00% |
| `background_realism` | PASS | 28 of 28 cells within tolerance |

17 cell(s) skipped for too few cases (not counted as pass or fail).

## Not audited

- Measurement error of continuous outputs (reported value against the true value): not compared with the catalogue's error_sd.
- Frequencies of findings in resolved states and on cards with a co-existing illness: the catalogue gives no single reference number for a mixture of causes. Those cards and states are covered by accuracy.*, non_diagnostic, state_consistency and presenting.
- Correlation between repeated attempts of one test on one card: attempts are treated as independent, so a model-written library whose repeats agree too closely has intervals that are too narrow.
- Free text (notes, reports) beyond the validator's leak rule.

Computed in 1.87 s. Full cells (expected, observed, interval) are in `audit.json`.

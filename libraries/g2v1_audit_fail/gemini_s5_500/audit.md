# Library audit: FAIL

Library `L_45e8094328ae41f5` (498 cards, generator `llm`, model `gemini-3.8-flash`, error source `guided`), catalogue `lung_primary_care` (`2bcb9c78b2e0`).

States: all_active 498, asthma_resolved 42, benign_nodule_resolved 42, copd_exacerbation_resolved 88, heart_failure_resolved 41, pneumonia_resolved 44, reflux_postinfectious_cough_resolved 42, tuberculosis_resolved 41, viral_self_limiting_resolved 41. Accuracy and non-diagnostic checks use every state (all_active and the resolved states pooled as `resolved`); frequency checks use `all_active` of single-illness cards.

Tolerance: a cell fails when it is outside the 4.2-sigma interval and more than the check's percentage points from the catalogue's expectation. See `audit_tolerances.yaml` for each number and its reason.

| Check | Result | Detail |
|---|---|---|
| `findings.asthma` | FAIL | 37 of 46 cells within tolerance |
| `findings.benign_nodule` | FAIL | 44 of 50 cells within tolerance |
| `findings.copd_exacerbation` | FAIL | 39 of 46 cells within tolerance |
| `findings.heart_failure` | FAIL | 39 of 46 cells within tolerance |
| `findings.lung_cancer` | FAIL | 49 of 54 cells within tolerance |
| `findings.no_disease_found` | FAIL | 40 of 46 cells within tolerance |
| `findings.pneumonia` | FAIL | 39 of 46 cells within tolerance |
| `findings.reflux_postinfectious_cough` | FAIL | 41 of 46 cells within tolerance |
| `findings.tuberculosis` | FAIL | 38 of 50 cells within tolerance |
| `findings.viral_self_limiting` | FAIL | 40 of 46 cells within tolerance |
| `findings.worried_well` | FAIL | 39 of 46 cells within tolerance |
| `accuracy.history` | PASS | 35 of 35 cells within tolerance |
| `accuracy.examination` | PASS | 10 of 10 cells within tolerance, 1 skipped (too few cases) |
| `accuracy.chest_xray` | PASS | 7 of 7 cells within tolerance |
| `accuracy.chest_ct` | PASS | 13 of 13 cells within tolerance, 1 skipped (too few cases) |
| `accuracy.low_dose_ct` | PASS | 4 of 4 cells within tolerance |
| `accuracy.pet_ct` | PASS | 8 of 8 cells within tolerance |
| `accuracy.brain_mri` | PASS | 2 of 2 cells within tolerance |
| `accuracy.spirometry` | PASS | 4 of 4 cells within tolerance |
| `accuracy.bronchoscopy` | PASS | 4 of 4 cells within tolerance |
| `accuracy.ebus_tbna` | PASS | 4 of 4 cells within tolerance |
| `accuracy.ct_guided_biopsy` | PASS | 4 of 4 cells within tolerance |
| `accuracy.sputum_cytology` | PASS | 4 of 4 cells within tolerance |
| `accuracy.histology_report` | PASS | 2 of 2 cells within tolerance |
| `accuracy.nt_probnp` | PASS | 3 of 3 cells within tolerance |
| `accuracy.dx_lung_cancer_histology` | PASS | 4 of 4 cells within tolerance |
| `accuracy.dx_pneumonia_chest_xray` | PASS | 3 of 3 cells within tolerance |
| `accuracy.spirometry_reversibility` | PASS | 6 of 6 cells within tolerance |
| `accuracy.echocardiography` | PASS | 3 of 3 cells within tolerance |
| `accuracy.mycobacterial_culture` | PASS | 3 of 3 cells within tolerance |
| `accuracy.ct_nodule_followup` | PASS | 3 of 3 cells within tolerance |
| `accuracy.ph_monitoring` | PASS | 3 of 3 cells within tolerance |
| `accuracy.respiratory_virus_pcr` | PASS | 3 of 3 cells within tolerance |
| `non_diagnostic` | PASS | 52 of 52 cells within tolerance |
| `state_consistency` | PASS | 0 of 381 resolved states with a violation (0.00%); limit 0.00% |
| `presenting` | PASS | 0 of 1231 reported complaints that are not true symptoms (0.00%); limit 0.00% |
| `diversity` | PASS | 0 of 498 cards that repeat an earlier card (0.00%); limit 2.00% |
| `leak` | PASS | 0 of 1758 notes flagged by the validator's leak rule (0.00%); limit 2.00% |
| `background_realism` | FAIL | 21 of 28 cells within tolerance |
| `report_wording` | FAIL | positive: hedged 55% wrong vs 4% right (gap +55 pp within strata, z 38.29), NB excess 0.313, n 3992/5979; negative: hedged 15% wrong vs 4% right (gap +11 pp within strata, z 23.47), NB excess 0.241, n 1984/56471 |

## Failed cells

| Check | Cell | n | Expected | Observed | 99% interval | Off (pp) |
|---|---|---|---|---|---|---|
| `findings.asthma` | asthma.wheeze | 42 | 0.700 | 1.000 | 0.381 to 0.952 | +30.0 |
| `findings.asthma` | asthma.abnormal_chest_sounds | 42 | 0.700 | 1.000 | 0.381 to 0.952 | +30.0 |
| `findings.asthma` | asthma.airflow_obstruction | 42 | 0.300 | 0.857 | 0.048 to 0.619 | +55.7 |
| `findings.asthma` | asthma.platelets_true<median | 42 | 0.500 | 0.905 | 0.191 to 0.809 | +40.5 |
| `findings.asthma` | asthma.crp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.asthma` | asthma.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.asthma` | asthma.alp_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.asthma` | asthma.ldh_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.asthma` | asthma.fev1_pct_predicted<median | 42 | 0.512 | 0.143 | 0.191 to 0.833 | -36.9 |
| `findings.benign_nodule` | benign_nodule.cough | 42 | 0.295 | 1.000 | 0.048 to 0.619 | +70.5 |
| `findings.benign_nodule` | benign_nodule.platelets_true<median | 42 | 0.500 | 0.941 | 0.191 to 0.809 | +44.0 |
| `findings.benign_nodule` | benign_nodule.crp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.benign_nodule` | benign_nodule.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.benign_nodule` | benign_nodule.alp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.benign_nodule` | benign_nodule.ldh_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.copd_exacerbation` | copd_exacerbation.recurrent_chest_infection | 42 | 0.250 | 0.000 | 0.024 to 0.548 | -25.0 |
| `findings.copd_exacerbation` | copd_exacerbation.wheeze | 42 | 0.600 | 1.000 | 0.286 to 0.881 | +40.0 |
| `findings.copd_exacerbation` | copd_exacerbation.crp_true<median | 42 | 0.500 | 0.024 | 0.191 to 0.809 | -47.6 |
| `findings.copd_exacerbation` | copd_exacerbation.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.copd_exacerbation` | copd_exacerbation.alp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.copd_exacerbation` | copd_exacerbation.ldh_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.copd_exacerbation` | copd_exacerbation.fev1_pct_predicted<median | 42 | 0.510 | 0.071 | 0.191 to 0.809 | -43.9 |
| `findings.heart_failure` | heart_failure.abnormal_chest_sounds | 41 | 0.600 | 1.000 | 0.268 to 0.902 | +40.0 |
| `findings.heart_failure` | heart_failure.ankle_oedema | 41 | 0.530 | 1.000 | 0.220 to 0.829 | +47.0 |
| `findings.heart_failure` | heart_failure.platelets_true<median | 41 | 0.500 | 0.829 | 0.195 to 0.805 | +32.9 |
| `findings.heart_failure` | heart_failure.crp_true<median | 41 | 0.500 | 0.976 | 0.195 to 0.805 | +47.6 |
| `findings.heart_failure` | heart_failure.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.heart_failure` | heart_failure.alp_true<median | 41 | 0.500 | 0.963 | 0.195 to 0.805 | +46.3 |
| `findings.heart_failure` | heart_failure.ldh_true<median | 41 | 0.500 | 0.963 | 0.195 to 0.805 | +46.3 |
| `findings.lung_cancer` | lung_cancer.cough | 35 | 0.648 | 1.000 | 0.286 to 0.943 | +35.2 |
| `findings.lung_cancer` | lung_cancer.dyspnoea | 35 | 0.563 | 0.971 | 0.229 to 0.886 | +40.8 |
| `findings.lung_cancer` | lung_cancer.fatigue | 35 | 0.352 | 0.943 | 0.057 to 0.714 | +59.1 |
| `findings.lung_cancer` | lung_cancer.crp_true<median | 35 | 0.500 | 0.057 | 0.171 to 0.829 | -44.3 |
| `findings.lung_cancer` | lung_cancer.lesion_size_mm<median | 35 | 0.500 | 0.000 | 0.171 to 0.829 | -50.0 |
| `findings.no_disease_found` | no_disease_found.chest_pain | 41 | 0.121 | 1.000 | 0.000 to 0.366 | +87.9 |
| `findings.no_disease_found` | no_disease_found.platelets_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.no_disease_found` | no_disease_found.crp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.no_disease_found` | no_disease_found.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.no_disease_found` | no_disease_found.alp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.no_disease_found` | no_disease_found.ldh_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.pneumonia` | pneumonia.dyspnoea | 42 | 0.633 | 1.000 | 0.309 to 0.905 | +36.7 |
| `findings.pneumonia` | pneumonia.fever | 42 | 0.532 | 1.000 | 0.214 to 0.833 | +46.8 |
| `findings.pneumonia` | pneumonia.abnormal_chest_sounds | 42 | 0.650 | 1.000 | 0.333 to 0.929 | +35.0 |
| `findings.pneumonia` | pneumonia.platelets_true<median | 42 | 0.500 | 0.048 | 0.191 to 0.809 | -45.2 |
| `findings.pneumonia` | pneumonia.crp_true<median | 42 | 0.500 | 0.000 | 0.191 to 0.809 | -50.0 |
| `findings.pneumonia` | pneumonia.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.pneumonia` | pneumonia.alp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.platelets_true<median | 42 | 0.500 | 0.893 | 0.191 to 0.809 | +39.3 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.crp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.alp_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.ldh_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.tuberculosis` | tuberculosis.weight_loss | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.tuberculosis` | tuberculosis.fever | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.tuberculosis` | tuberculosis.consolidation | 41 | 0.500 | 0.976 | 0.195 to 0.805 | +47.6 |
| `findings.tuberculosis` | tuberculosis.hb_true<median | 41 | 0.500 | 0.902 | 0.195 to 0.805 | +40.2 |
| `findings.tuberculosis` | tuberculosis.platelets_true<median | 41 | 0.500 | 0.012 | 0.195 to 0.805 | -48.8 |
| `findings.tuberculosis` | tuberculosis.crp_true<median | 41 | 0.500 | 0.000 | 0.195 to 0.805 | -50.0 |
| `findings.tuberculosis` | tuberculosis.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.tuberculosis` | tuberculosis.alp_true<median | 41 | 0.500 | 0.963 | 0.195 to 0.805 | +46.3 |
| `findings.tuberculosis` | tuberculosis.ldh_true<median | 41 | 0.500 | 0.915 | 0.195 to 0.805 | +41.5 |
| `findings.tuberculosis` | tuberculosis.fev1_pct_predicted<median | 41 | 0.525 | 0.902 | 0.195 to 0.829 | +37.7 |
| `findings.tuberculosis` | tuberculosis.lesion_size_mm<median | 21 | 0.500 | 0.000 | 0.095 to 0.905 | -50.0 |
| `findings.tuberculosis` | tuberculosis.lesion_size_mm<p90 | 21 | 0.900 | 0.238 | 0.571 to 1.000 | -66.2 |
| `findings.viral_self_limiting` | viral_self_limiting.fever | 41 | 0.400 | 0.976 | 0.098 to 0.732 | +57.6 |
| `findings.viral_self_limiting` | viral_self_limiting.platelets_true<median | 41 | 0.500 | 0.854 | 0.195 to 0.805 | +35.4 |
| `findings.viral_self_limiting` | viral_self_limiting.crp_true<median | 41 | 0.500 | 0.085 | 0.195 to 0.805 | -41.5 |
| `findings.viral_self_limiting` | viral_self_limiting.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.viral_self_limiting` | viral_self_limiting.alp_true<median | 41 | 0.500 | 0.976 | 0.195 to 0.805 | +47.6 |
| `findings.viral_self_limiting` | viral_self_limiting.ldh_true<median | 41 | 0.500 | 0.976 | 0.195 to 0.805 | +47.6 |
| `findings.worried_well` | worried_well.chest_pain | 41 | 0.350 | 1.000 | 0.073 to 0.683 | +65.0 |
| `findings.worried_well` | worried_well.fatigue | 41 | 0.400 | 1.000 | 0.098 to 0.732 | +60.0 |
| `findings.worried_well` | worried_well.platelets_true<median | 41 | 0.500 | 0.976 | 0.195 to 0.805 | +47.6 |
| `findings.worried_well` | worried_well.crp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.worried_well` | worried_well.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.worried_well` | worried_well.alp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.worried_well` | worried_well.ldh_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `background_realism` | background_realism.pack_years_possible | 498 | at most 0.00% | 7.23% | | |
| | e.g. lung_primary_care.s5:000015 | | | | | |
| | e.g. lung_primary_care.s5:000016 | | | | | |
| | e.g. lung_primary_care.s5:000043 | | | | | |
| `background_realism` | background_realism.age_65_plus.heart_failure | 41 | 0.858 | 0.293 | 0.585 to 1.000 | -56.5 |
| `background_realism` | background_realism.age_under_50.heart_failure | 41 | 0.014 | 0.195 | 0.000 to 0.146 | +18.1 |
| `background_realism` | background_realism.age_under_50.lung_cancer | 83 | 0.050 | 0.229 | 0.000 to 0.181 | +17.9 |
| `background_realism` | background_realism.age_65_plus.worried_well | 41 | 0.129 | 0.488 | 0.000 to 0.390 | +35.9 |
| `background_realism` | background_realism.age_under_50.worried_well | 41 | 0.597 | 0.098 | 0.268 to 0.902 | -49.9 |
| `background_realism` | background_realism.cancer_under_50 | 83 | at most 10.00% | 22.89% | | |
| `report_wording` | report_wording.positive (false alarms vs true positives) | 3992 | hedged 4% of right | hedged 55% of wrong | gap +54.5 pp within strata, z 38.29; NB excess 0.313 | |
| `report_wording` | report_wording.negative (misses vs true negatives) | 1984 | hedged 4% of right | hedged 15% of wrong | gap +10.8 pp within strata, z 23.47; NB excess 0.241 | |

2 cell(s) skipped for too few cases (not counted as pass or fail).

## Not audited

- Measurement error of continuous outputs (reported value against the true value): not compared with the catalogue's error_sd.
- Frequencies of findings in resolved states and on cards with a co-existing illness: the catalogue gives no single reference number for a mixture of causes. Those cards and states are covered by accuracy.*, non_diagnostic, state_consistency and presenting.
- Correlation between repeated attempts of one test on one card: attempts are treated as independent, so a model-written library whose repeats agree too closely has intervals that are too narrow.
- Free text (notes, reports) beyond the validator's leak rule and the report_wording check (hedging words, length, a bag-of-words classifier on binary results).

Computed in 6.96 s. Full cells (expected, observed, interval) are in `audit.json`.

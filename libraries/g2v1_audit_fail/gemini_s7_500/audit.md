# Library audit: FAIL

Library `L_dcb6acdb0acf33e8` (499 cards, generator `llm`, model `gemini-3.8-flash`, error source `guided`), catalogue `lung_primary_care` (`2bcb9c78b2e0`).

States: all_active 499, asthma_resolved 42, benign_nodule_resolved 42, copd_exacerbation_resolved 73, heart_failure_resolved 42, pneumonia_resolved 42, reflux_postinfectious_cough_resolved 42, tuberculosis_resolved 42, viral_self_limiting_resolved 41. Accuracy and non-diagnostic checks use every state (all_active and the resolved states pooled as `resolved`); frequency checks use `all_active` of single-illness cards.

Tolerance: a cell fails when it is outside the 4.2-sigma interval and more than the check's percentage points from the catalogue's expectation. See `audit_tolerances.yaml` for each number and its reason.

| Check | Result | Detail |
|---|---|---|
| `findings.asthma` | FAIL | 37 of 46 cells within tolerance |
| `findings.benign_nodule` | FAIL | 44 of 50 cells within tolerance |
| `findings.copd_exacerbation` | FAIL | 40 of 46 cells within tolerance |
| `findings.heart_failure` | FAIL | 37 of 46 cells within tolerance |
| `findings.lung_cancer` | FAIL | 44 of 54 cells within tolerance |
| `findings.no_disease_found` | FAIL | 40 of 46 cells within tolerance |
| `findings.pneumonia` | FAIL | 38 of 46 cells within tolerance |
| `findings.reflux_postinfectious_cough` | FAIL | 41 of 46 cells within tolerance |
| `findings.tuberculosis` | FAIL | 39 of 50 cells within tolerance |
| `findings.viral_self_limiting` | FAIL | 40 of 46 cells within tolerance |
| `findings.worried_well` | FAIL | 39 of 46 cells within tolerance |
| `accuracy.history` | PASS | 33 of 33 cells within tolerance, 2 skipped (too few cases) |
| `accuracy.examination` | PASS | 10 of 10 cells within tolerance |
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
| `state_consistency` | PASS | 0 of 366 resolved states with a violation (0.00%); limit 0.00% |
| `presenting` | PASS | 0 of 1193 reported complaints that are not true symptoms (0.00%); limit 0.00% |
| `diversity` | PASS | 0 of 499 cards that repeat an earlier card (0.00%); limit 2.00% |
| `leak` | PASS | 0 of 1730 notes flagged by the validator's leak rule (0.00%); limit 2.00% |
| `background_realism` | FAIL | 23 of 28 cells within tolerance |
| `report_wording` | FAIL | positive: hedged 53% wrong vs 4% right (gap +54 pp within strata, z 38.53), NB excess 0.33, n 3993/5565; negative: hedged 14% wrong vs 4% right (gap +10 pp within strata, z 22.46), NB excess 0.227, n 1819/56031 |

## Failed cells

| Check | Cell | n | Expected | Observed | 99% interval | Off (pp) |
|---|---|---|---|---|---|---|
| `findings.asthma` | asthma.wheeze | 42 | 0.700 | 1.000 | 0.381 to 0.952 | +30.0 |
| `findings.asthma` | asthma.abnormal_chest_sounds | 42 | 0.700 | 1.000 | 0.381 to 0.952 | +30.0 |
| `findings.asthma` | asthma.airflow_obstruction | 42 | 0.300 | 0.833 | 0.048 to 0.619 | +53.3 |
| `findings.asthma` | asthma.platelets_true<median | 42 | 0.500 | 0.857 | 0.191 to 0.809 | +35.7 |
| `findings.asthma` | asthma.crp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.asthma` | asthma.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.asthma` | asthma.alp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.asthma` | asthma.ldh_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.asthma` | asthma.fev1_pct_predicted<median | 42 | 0.512 | 0.167 | 0.191 to 0.833 | -34.6 |
| `findings.benign_nodule` | benign_nodule.cough | 42 | 0.295 | 1.000 | 0.048 to 0.619 | +70.5 |
| `findings.benign_nodule` | benign_nodule.platelets_true<median | 42 | 0.500 | 0.929 | 0.191 to 0.809 | +42.9 |
| `findings.benign_nodule` | benign_nodule.crp_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.benign_nodule` | benign_nodule.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.benign_nodule` | benign_nodule.alp_true<median | 42 | 0.500 | 0.964 | 0.191 to 0.809 | +46.4 |
| `findings.benign_nodule` | benign_nodule.ldh_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.copd_exacerbation` | copd_exacerbation.recurrent_chest_infection | 42 | 0.250 | 0.000 | 0.024 to 0.548 | -25.0 |
| `findings.copd_exacerbation` | copd_exacerbation.wheeze | 42 | 0.600 | 1.000 | 0.286 to 0.881 | +40.0 |
| `findings.copd_exacerbation` | copd_exacerbation.crp_true<median | 42 | 0.500 | 0.000 | 0.191 to 0.809 | -50.0 |
| `findings.copd_exacerbation` | copd_exacerbation.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.copd_exacerbation` | copd_exacerbation.alp_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.copd_exacerbation` | copd_exacerbation.ldh_true<median | 42 | 0.500 | 0.917 | 0.191 to 0.809 | +41.7 |
| `findings.heart_failure` | heart_failure.cough | 42 | 0.295 | 0.024 | 0.048 to 0.619 | -27.1 |
| `findings.heart_failure` | heart_failure.abnormal_chest_sounds | 42 | 0.600 | 1.000 | 0.286 to 0.881 | +40.0 |
| `findings.heart_failure` | heart_failure.ankle_oedema | 42 | 0.530 | 1.000 | 0.214 to 0.833 | +47.0 |
| `findings.heart_failure` | heart_failure.platelets_true<median | 42 | 0.500 | 0.881 | 0.191 to 0.809 | +38.1 |
| `findings.heart_failure` | heart_failure.crp_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.heart_failure` | heart_failure.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.heart_failure` | heart_failure.alp_true<median | 42 | 0.500 | 0.952 | 0.191 to 0.809 | +45.2 |
| `findings.heart_failure` | heart_failure.ldh_true<median | 42 | 0.500 | 0.952 | 0.191 to 0.809 | +45.2 |
| `findings.heart_failure` | heart_failure.fev1_pct_predicted<median | 42 | 0.525 | 0.857 | 0.214 to 0.833 | +33.2 |
| `findings.lung_cancer` | lung_cancer.cough | 52 | 0.648 | 1.000 | 0.365 to 0.904 | +35.2 |
| `findings.lung_cancer` | lung_cancer.haemoptysis | 52 | 0.202 | 0.000 | 0.019 to 0.462 | -20.2 |
| `findings.lung_cancer` | lung_cancer.dyspnoea | 52 | 0.563 | 1.000 | 0.269 to 0.846 | +43.7 |
| `findings.lung_cancer` | lung_cancer.chest_pain | 52 | 0.405 | 0.846 | 0.135 to 0.692 | +44.1 |
| `findings.lung_cancer` | lung_cancer.fatigue | 52 | 0.352 | 0.981 | 0.096 to 0.635 | +62.9 |
| `findings.lung_cancer` | lung_cancer.mediastinal_nodes | 52 | 0.447 | 0.808 | 0.173 to 0.731 | +36.1 |
| `findings.lung_cancer` | lung_cancer.platelets_true<median | 52 | 0.500 | 0.154 | 0.211 to 0.788 | -34.6 |
| `findings.lung_cancer` | lung_cancer.crp_true<median | 52 | 0.500 | 0.019 | 0.211 to 0.788 | -48.1 |
| `findings.lung_cancer` | lung_cancer.ldh_true<median | 52 | 0.500 | 0.096 | 0.211 to 0.788 | -40.4 |
| `findings.lung_cancer` | lung_cancer.lesion_size_mm<median | 52 | 0.500 | 0.000 | 0.211 to 0.788 | -50.0 |
| `findings.no_disease_found` | no_disease_found.chest_pain | 40 | 0.121 | 1.000 | 0.000 to 0.375 | +87.9 |
| `findings.no_disease_found` | no_disease_found.platelets_true<median | 40 | 0.500 | 0.912 | 0.175 to 0.825 | +41.2 |
| `findings.no_disease_found` | no_disease_found.crp_true<median | 40 | 0.500 | 1.000 | 0.175 to 0.825 | +50.0 |
| `findings.no_disease_found` | no_disease_found.calcium_true<median | 40 | 0.570 | 1.000 | 0.250 to 0.875 | +43.0 |
| `findings.no_disease_found` | no_disease_found.alp_true<median | 40 | 0.500 | 1.000 | 0.175 to 0.825 | +50.0 |
| `findings.no_disease_found` | no_disease_found.ldh_true<median | 40 | 0.500 | 1.000 | 0.175 to 0.825 | +50.0 |
| `findings.pneumonia` | pneumonia.dyspnoea | 42 | 0.633 | 1.000 | 0.309 to 0.905 | +36.7 |
| `findings.pneumonia` | pneumonia.fever | 42 | 0.532 | 1.000 | 0.214 to 0.833 | +46.8 |
| `findings.pneumonia` | pneumonia.abnormal_chest_sounds | 42 | 0.650 | 1.000 | 0.333 to 0.929 | +35.0 |
| `findings.pneumonia` | pneumonia.platelets_true<median | 42 | 0.500 | 0.024 | 0.191 to 0.809 | -47.6 |
| `findings.pneumonia` | pneumonia.crp_true<median | 42 | 0.500 | 0.000 | 0.191 to 0.809 | -50.0 |
| `findings.pneumonia` | pneumonia.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.pneumonia` | pneumonia.alp_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.pneumonia` | pneumonia.fev1_pct_predicted<median | 42 | 0.525 | 0.881 | 0.214 to 0.833 | +35.6 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.platelets_true<median | 42 | 0.500 | 0.833 | 0.191 to 0.809 | +33.3 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.crp_true<median | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.alp_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.reflux_postinfectious_cough` | reflux_postinfectious_cough.ldh_true<median | 42 | 0.500 | 0.988 | 0.191 to 0.809 | +48.8 |
| `findings.tuberculosis` | tuberculosis.weight_loss | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.tuberculosis` | tuberculosis.fever | 42 | 0.500 | 1.000 | 0.191 to 0.809 | +50.0 |
| `findings.tuberculosis` | tuberculosis.consolidation | 42 | 0.500 | 0.952 | 0.191 to 0.809 | +45.2 |
| `findings.tuberculosis` | tuberculosis.hb_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.tuberculosis` | tuberculosis.platelets_true<median | 42 | 0.500 | 0.048 | 0.191 to 0.809 | -45.2 |
| `findings.tuberculosis` | tuberculosis.crp_true<median | 42 | 0.500 | 0.000 | 0.191 to 0.809 | -50.0 |
| `findings.tuberculosis` | tuberculosis.calcium_true<median | 42 | 0.570 | 1.000 | 0.262 to 0.881 | +43.0 |
| `findings.tuberculosis` | tuberculosis.alp_true<median | 42 | 0.500 | 0.976 | 0.191 to 0.809 | +47.6 |
| `findings.tuberculosis` | tuberculosis.ldh_true<median | 42 | 0.500 | 0.857 | 0.191 to 0.809 | +35.7 |
| `findings.tuberculosis` | tuberculosis.lesion_size_mm<median | 26 | 0.500 | 0.000 | 0.115 to 0.885 | -50.0 |
| `findings.tuberculosis` | tuberculosis.lesion_size_mm<p90 | 26 | 0.900 | 0.077 | 0.577 to 1.000 | -82.3 |
| `findings.viral_self_limiting` | viral_self_limiting.fever | 41 | 0.400 | 0.976 | 0.098 to 0.732 | +57.6 |
| `findings.viral_self_limiting` | viral_self_limiting.platelets_true<median | 41 | 0.500 | 0.829 | 0.195 to 0.805 | +32.9 |
| `findings.viral_self_limiting` | viral_self_limiting.crp_true<median | 41 | 0.500 | 0.134 | 0.195 to 0.805 | -36.6 |
| `findings.viral_self_limiting` | viral_self_limiting.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.viral_self_limiting` | viral_self_limiting.alp_true<median | 41 | 0.500 | 0.902 | 0.195 to 0.805 | +40.2 |
| `findings.viral_self_limiting` | viral_self_limiting.ldh_true<median | 41 | 0.500 | 0.902 | 0.195 to 0.805 | +40.2 |
| `findings.worried_well` | worried_well.chest_pain | 41 | 0.350 | 1.000 | 0.073 to 0.683 | +65.0 |
| `findings.worried_well` | worried_well.fatigue | 41 | 0.400 | 0.951 | 0.098 to 0.732 | +55.1 |
| `findings.worried_well` | worried_well.platelets_true<median | 41 | 0.500 | 0.951 | 0.195 to 0.805 | +45.1 |
| `findings.worried_well` | worried_well.crp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.worried_well` | worried_well.calcium_true<median | 41 | 0.570 | 1.000 | 0.244 to 0.878 | +43.0 |
| `findings.worried_well` | worried_well.alp_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `findings.worried_well` | worried_well.ldh_true<median | 41 | 0.500 | 1.000 | 0.195 to 0.805 | +50.0 |
| `background_realism` | background_realism.pack_years_possible | 499 | at most 0.00% | 3.81% | | |
| | e.g. lung_primary_care.s7:000004 | | | | | |
| | e.g. lung_primary_care.s7:000040 | | | | | |
| | e.g. lung_primary_care.s7:000053 | | | | | |
| `background_realism` | background_realism.smoking.current | 499 | 0.316 | 0.413 | 0.231 to 0.405 | +9.7 |
| `background_realism` | background_realism.age_65_plus.heart_failure | 42 | 0.842 | 0.381 | 0.571 to 1.000 | -46.1 |
| `background_realism` | background_realism.age_under_50.lung_cancer | 83 | 0.052 | 0.217 | 0.000 to 0.181 | +16.5 |
| `background_realism` | background_realism.cancer_under_50 | 83 | at most 10.00% | 21.69% | | |
| `report_wording` | report_wording.positive (false alarms vs true positives) | 3993 | hedged 4% of right | hedged 53% of wrong | gap +54.2 pp within strata, z 38.53; NB excess 0.33 | |
| `report_wording` | report_wording.negative (misses vs true negatives) | 1819 | hedged 4% of right | hedged 14% of wrong | gap +10.5 pp within strata, z 22.46; NB excess 0.227 | |

3 cell(s) skipped for too few cases (not counted as pass or fail).

## Not audited

- Measurement error of continuous outputs (reported value against the true value): not compared with the catalogue's error_sd.
- Frequencies of findings in resolved states and on cards with a co-existing illness: the catalogue gives no single reference number for a mixture of causes. Those cards and states are covered by accuracy.*, non_diagnostic, state_consistency and presenting.
- Correlation between repeated attempts of one test on one card: attempts are treated as independent, so a model-written library whose repeats agree too closely has intervals that are too narrow.
- Free text (notes, reports) beyond the validator's leak rule and the report_wording check (hedging words, length, a bag-of-words classifier on binary results).

Computed in 6.55 s. Full cells (expected, observed, interval) are in `audit.json`.

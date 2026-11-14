# Parameters and sources

Every number the simulator uses, with its source id (see the source table at the end) or `assumption`.
Generated from `params/*.yaml`; edit the YAML, not this file. Access level of each source is in `params/sources.yaml`: `full_text`, `abstract` or `secondary`.
Times are calendar days. Rows tagged `assumption` are our own reasoning; the note column says how it was derived.

## Stokstad scenario (St Olavs, Trondheim)

### cohort

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `n_patients` | 100 | patients | STOKSTAD2019 | Stage I-II on baseline CT, curative treatment, no unplanned delay of 3 days or more |
| `n_diagnosed_period` | 454 | patients | STOKSTAD2019 | Lung cancer diagnoses 2011-2013. Flow: 449 not declining, 150 preliminary stage I-II, 26 ineligible for curative treatment, 24 excluded for delay of 3+ days, 100 analysed |
| `median_age` | 70 (range 54 to 84) | years | STOKSTAD2019 | 32% were 75 or older, 63% women |
| `share_stage_i` | 0.72 | fraction | STOKSTAD2019 | Stage II 20%. The baseline table also lists stage III 8% (likely restaging after the preliminary stage I-II classification; interpretation) |
| `share_stage_ii` | 0.2 | fraction | STOKSTAD2019 | See share_stage_i |
| `share_nsclc` | 0.77 | fraction | STOKSTAD2019 | SCLC 6%, other primary lung cancer 5%, remainder not tabulated |
| `share_no_tissue_diagnosis` | 0.12 | fraction | STOKSTAD2019 | Baseline table. The text separately says 54 patients were treated without a definitive cancer diagnosis (22 never sampled, 27 one negative bronchoscopy, 5 two attempts), so the two counts use different definitions |
| `n_treated_without_definitive_diagnosis` | 54 | patients | STOKSTAD2019 | 42 surgery, 11 stereotactic radiotherapy, 1 conventional radiotherapy. Relevant to benign-lesion exposure and the value of earlier tissue sampling |
| `share_treatment_surgery` | 0.76 | fraction | STOKSTAD2019 | Curative radiotherapy 8%, stereotactic radiotherapy 16% |
| `share_treatment_curative_radiotherapy` | 0.08 | fraction | STOKSTAD2019 | Includes chemoradiotherapy for limited-stage SCLC |
| `share_treatment_sbrt` | 0.16 | fraction | STOKSTAD2019 | Stereotactic radiotherapy |

### outcomes published

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `target_days` | 42 | days | STOKSTAD2019 | National target, referral receipt to treatment start |
| `median_days_to_treatment_observed` | 46.5 (range 5 to 145) | days | STOKSTAD2019 | Primary calibration target |
| `share_within_42d_observed` | 0.4 (95% CI 0.31 to 0.5) | fraction | STOKSTAD2019 | Calibration target for the baseline flowchart |
| `share_within_42d_pet_le7d` | 0.48 (95% CI 0.39 to 0.58) | fraction | STOKSTAD2019 | Observed intervals, PET-CT wait set to 7 days or less. p=0.254 in abstract, 0.255 in results |
| `share_within_42d_optimal_pathway` | 0.8 (95% CI 0.72 to 0.87) | fraction | STOKSTAD2019 | Optimal sequence with PET wait 7 days or less and observed intervals for other steps; p<0.001. A model estimate, not an observed result |
| `share_within_42d_optimal_pathway_median_intervals` | 0.93 | fraction | STOKSTAD2019 | Optimal sequence using median observed interval per procedure (Fig. 4). Upper bound; do not use as the main target |
| `tissue_sampling_procedures_observed` | 112 | procedures | STOKSTAD2019 | Whole cohort |
| `tissue_sampling_procedures_optimal` | 92 | procedures | STOKSTAD2019 | About 16% fewer. Check that the simulated optimal flowchart also reduces repeat sampling |

### step waits

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `referral_to_first_visit` | 7 ; dist dist=lognormal, median=7, p90=18.5 | days | assumption | The paper reports no median. It says 50 of 100 patients waited more than 7 days and 18 waited 14 days or more. Median about 7 and the 82nd percentile 14 gives lognormal sigma about 0.76, p90 about 18.5. Derived from published counts |
| `radiology_report_incomplete_at_first_visit` | 2 (range 1 to 55) | days | STOKSTAD2019 | Median extra wait; affected 39 patients. Median applies only to those patients |
| `share_report_incomplete_at_first_visit` | 0.39 | fraction | STOKSTAD2019 | 39 of 100 |
| `share_ct_inadequate_at_first_visit` | 0.08 | fraction | STOKSTAD2019 | CT poor quality, too old or upper abdomen missing; stage not correctly assessed |
| `ct_inadequate_extra_delay` | 15.5 (range 2 to 98) | days | STOKSTAD2019 | Median delay in the 8 affected patients |
| `pet_referral_late_after_first_visit` | 8 (range 1 to 36) | days | STOKSTAD2019 | Median, 27 patients not referred to PET-CT at the first consultation |
| `exercise_test_referral_late_after_first_visit` | 10 (range 2 to 28) | days | STOKSTAD2019 | Median, 16 patients not referred at the first visit; 21 patients had an exercise test overall |
| `pet_ct_referral_to_report_outsourced` | 20.5 (range 7 to 49) ; dist dist=lognormal, median=20.5, p90=35 | days | STOKSTAD2019 | Median and range from the paper (outsourced scanner period). The p90 of 35 is our assumption fitted to the range of 7 to 49 |
| `pet_ct_referral_to_report_after_new_scanner` | 7 | days | STOKSTAD2019 | Paper says the waiting time became 7 days or less after PET-CT became available in-house in October 2013. 7 is the upper bound; the typical value would be lower (assumption) |
| `exercise_test_wait` | 11 (range 1 to 19) ; dist dist=lognormal, median=11, p90=18 | days | STOKSTAD2019 | Median wait for the cardiopulmonary exercise test, n=9. p90 18 is our assumption from the range |
| `tumour_board_frequency` | weekly | schedule | STOKSTAD2019 | Weekly; the weekday is not given in the paper, so Wednesday in the architecture example is an assumption. The authors note more frequent meetings could reduce time further |
| `share_incomplete_workup_at_tumour_board` | 0.16 | fraction | STOKSTAD2019 | 16 patients: 10 awaiting PET-CT, 6 awaiting exercise test |
| `pathology_report_after_sampling` | 4.5 (range 0 to 14) ; dist dist=lognormal, median=4.5, p90=9 | days | STOKSTAD2019 | Median from the paper; p90 9 is our assumption from the range. Information appointments were routinely 1-2 weeks after sampling |
| `repeat_sampling_wait` | 8 (range 1 to 14) | days | STOKSTAD2019 | Median wait for repeat tissue sampling after a failed first attempt |
| `referral_to_treatment_surgery` | 13 (range 4 to 48) | days | STOKSTAD2019 | Reported as median referral-to-treatment by treatment type. The overall median is 46.5 days, so this cannot start at referral receipt; our reading is that it runs from the referral for treatment to the start of surgery (interpretation, not stated explicitly) |
| `referral_to_treatment_radiotherapy` | 22.5 (range 6 to 37) | days | STOKSTAD2019 | Same caveat as surgery |
| `share_further_workup_after_pet` | 0.12 | fraction | STOKSTAD2019 | 12 patients in the results; the abstract says 11 |
| `share_treatment_plan_changed_by_pet` | 0.02 | fraction | STOKSTAD2019 | Treatment plan changed in 2% after PET-CT. Argues PET-CT mostly confirms rather than redirects in this cohort |

### delay reason counts

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `late_pet_referral` | 27 | patients | STOKSTAD2019 | Abstract |
| `late_exercise_test_referral` | 16 | patients | STOKSTAD2019 | Abstract |
| `repeat_sampling_after_failed_bronchoscopy` | 15 | patients | STOKSTAD2019 | Abstract |
| `extra_investigations_after_pet` | 11 | patients | STOKSTAD2019 | Abstract says 11, results say 12 |
| `first_visit_over_7d_unexplained` | 50 | patients | STOKSTAD2019 | 18 of them waited 14 days or more |

### diagnostic yield

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `bronchoscopy_first_tissue_method_diagnostic` | 27 | patients | STOKSTAD2019 | 3 of them diagnostic only on a second attempt. The denominator (patients who had bronchoscopy) is not given in the text we read |
| `ttnb_diagnostic` | 19 | patients | STOKSTAD2019 | 15 of them after a negative bronchoscopy |
| `ttnb_after_negative_bronchoscopy` | 15 | patients | STOKSTAD2019 | Count of TTNB procedures that followed a negative bronchoscopy |

### not in paper estimates

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `ct_to_first_visit_wait` | 0 | days | assumption | Not reported. In the paper CT is usually done before or at the first visit, and the optimal pathway sets CT referral to the day the letter arrives. Treat CT as part of the first-visit interval unless a patient had no CT |
| `bronchoscopy_wait_after_referral` | 7 ; dist dist=lognormal, median=7, p90=14 | days | assumption | Not reported. Reasoned from the reported repeat-sampling wait (median 8, range 1-14), which is the only sampling wait given. Calibrate so the baseline reproduces the 46.5 day median |
| `ttnb_wait_after_referral` | 8 ; dist dist=lognormal, median=8, p90=14 | days | assumption | Not reported. Set equal to the repeat-sampling wait as the closest published number |
| `tumour_board_wait_after_workup_complete` | 3.5 ; dist dist=uniform, low=0, high=7 | days | assumption | Not reported. Follows from a weekly board with a cutoff; the simulator's batch resource produces this wait itself, so do not add a separate delay |
| `treatment_decision_to_start_surgery` | 13 | days | STOKSTAD2019 | Uses referral_to_treatment_surgery under our interpretation; see that entry |
| `treatment_decision_to_start_radiotherapy` | 22.5 | days | STOKSTAD2019 | Uses referral_to_treatment_radiotherapy under our interpretation |

## Finnish lung pathway

### waits

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `health_centre_appointment` | 14 ; dist dist=lognormal, median=14, p90=30 | days | KHALIFE2025 | Mode of survey answers (42 specialists). Respondents said it may be optimistic and often takes up to a month, hence the p90 of 30 (our assumption). Denmark, Norway, Sweden 2-7 days. IHE2026 repeats the figure |
| `health_centre_appointment_nordic_comparator` | 4.5 (range 2 to 7) | days | KHALIFE2025 | Midpoint of the 2-7 day range reported for DK/NO/SE, for the counterfactual 'Nordic' scenario |
| `specialist_consultation_after_gp` | 21 (range 14 to 28) ; dist dist=uniform, low=14, high=28 | days | KHALIFE2025 | 2-4 weeks, survey mode. DK/NO/SE 1-2 weeks (7-14 days) per IHE2026 |
| `diagnosis_after_specialist_consultation` | 28 ; dist dist=lognormal, median=28, p90=45 | days | KHALIFE2025 | 4 weeks, survey mode. p90 45 is our assumption. DK/NO 2-4 weeks, SE 4 weeks per IHE2026 |
| `cumulative_delay_estimate_first_contact_to_diagnosis` | 45 (range 30 to 60) | days | KHALIFE2025 | Authors' own 1-2 month estimate for Finland. Use as a plausibility check on the sum of step waits |
| `registry_diagnosis_to_treatment_start` | 37 (range 36 to 38) | days | IHE2026 | Registry median 2018-2022 for cancer patients in general, not lung-specific (IHE cites a national registry reference) |
| `satakunta_first_primary_visit_to_referral` | 14 | days | MATTILA2025 | About two weeks, n=131, pandemic period, abstract-level only |
| `satakunta_referral_to_diagnosis` | 55 | days | MATTILA2025 | 'Just under two months' in the abstract; 55 is our rounding, exact days not given. Supports the claim that most delay is in specialist care |
| `mot_symptom_onset_to_treatment_finland` | 155 | days | YLE_MOT2025 | Unpublished journalist study, secondary. Parts: patient interval more than 50, primary care 41, specialised care 58 (they sum to 149). DK 67, SE 107. Context only |
| `mot_primary_care_interval` | 41 | days | YLE_MOT2025 | Secondary, unpublished |
| `mot_specialised_care_interval` | 58 | days | YLE_MOT2025 | Secondary, unpublished |
| `thl_share_waiting_over_14d_for_doctor` | 0.35 | fraction | KHALIFE2025 | THL 2023 national primary care data, all patients, not lung-specific. Another 14% waited 1-3 months |
| `thl_share_waiting_1_to_3_months_for_doctor` | 0.14 | fraction | KHALIFE2025 | As above |
| `ct_report_turnaround_typical` | 7 | days | PIRHA_PATH | Pirkanmaa: lung and upper abdomen CT usually within a week of referral processing. Describes a typical process at one hospital district, not a measured median |
| `bronchoscopy_result_turnaround` | 4 (range 3 to 5) | days | PIRHA_PATH | Pirkanmaa: bronchoscopy results available 3-5 days after the procedure |
| `referral_processing` | 1.5 (range 1 to 2) | days | PIRHA_PATH | Working days; Pirkanmaa. Invitation letter usually posted within 3-4 working days of referral arrival |
| `radiotherapy_start_after_planning_ct` | 14 | days | PIRHA_PATH | Pirkanmaa: usually within about two weeks of the planning CT |
| `pet_ct_wait_finland` | 20.5 ; dist dist=lognormal, median=20.5, p90=35 | days | assumption | No Finnish PET-CT wait found. Placeholder borrowed from the Norwegian outsourced-scanner period (STOKSTAD2019); replace if a Finnish number is found. Finland has 57% more PET scanners than the EU average per IHE2026, so this may be pessimistic |
| `tumour_board_frequency` | weekly | schedule | assumption | Pirkanmaa pathway lists the multidisciplinary board but not its frequency. Weekly is the Norwegian value (STOKSTAD2019) and common practice |

### first contact

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `share_meeting_doctor_at_first_primary_care_contact` | 0.5 (range 0.4 to 0.6) | fraction | KHALIFE2025 | Survey mode 40-60% in Finland; Sweden 80-100%; DK/NO/IS 100%. Patients not seeing a doctor see a nurse |
| `share_seeing_nurse_at_first_contact` | 0.5 (range 0.4 to 0.6) | fraction | KHALIFE2025 | Complement of the share meeting a doctor. HELSINKI2025_NEWS reports it as 40-60% seeing a nurse |
| `share_primary_care_units_with_ct_access` | 0.1 | fraction | IHE2026 | Reported as fewer than 10% (upper bound), versus 90-100% in other Nordic countries. In Khalife only one Finnish respondent reported CT as an option in primary care |
| `ct_scanners_per_100k_vs_eu` | -0.34 | relative difference | IHE2026 | 2023 CT scanners per 100,000 inhabitants were 34% below the EU average and lowest in the Nordics; CT examinations 60% below the EU average |

### epidemiology

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `lung_cancer_new_cases_per_year_finland` | 2913 | cases per year | GLOBOCAN_FIN | 1,701 men and 1,212 women in the fact sheet estimate. The team brief quoted about 2,500-2,700 per year from an unverified source; the registry figure for 2023 was not retrieved |
| `population_finland` | 5617316 | people | GLOBOCAN_FIN | Fact sheet population |
| `typical_wellbeing_county_population` | 250000 | people | assumption | Not retrieved from Statistics Finland (the page we reached had changes only). Derived: about 5.6 million over 21 wellbeing counties plus Helsinki city is about 255,000 on average; counties range from roughly 100,000 to over 600,000 (our recollection, unverified) |
| `lung_cancer_cases_per_county_year` | 130 | cases per year | assumption | Derived: 2,913 cases divided by about 22 units. A county sized 250,000 sees roughly 130 lung cancers a year |
| `share_stage_i_at_diagnosis` | 0.17 | fraction | KHALIFE2025 | Finland 17%, over 25% in Denmark and Norway |
| `share_stage_iv_single_centre` | 0.59 | fraction | IHE2026 | Single-centre Finnish study 2007-2019, not national |
| `five_year_relative_survival_men` | 0.17 | fraction | IHE2026 | Diagnosed 2019-2023, NORDCAN. Denmark 27%, Norway 30%, Sweden 29% |
| `five_year_relative_survival_women` | 0.29 | fraction | IHE2026 | Diagnosed 2019-2023. Denmark 35%, Norway 37%, Sweden 37% |

### presentation and prevalence

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `lung_cancer_risk_12m_self_referred_cxr_over_50` | 0.013 | fraction | BRADLEY2021 | Leeds, symptomatic people over 50 who self-requested a chest X-ray, 114 of 8,996. UK, not Finland. 1.7% within 2 years |
| `lung_cancer_risk_12m_after_new_haemoptysis` | 0.031 | fraction | KOO2023 | English primary care, 253 of 8,120 within 12 months (3.6% where guideline-concordant imaging was done) |
| `lung_cancer_risk_12m_after_new_dyspnoea` | 0.007 | fraction | KOO2023 | English primary care, 1,103 of 162,161 within 12 months |
| `ppv_single_symptom_other_than_haemoptysis` | 0.01 | fraction | BRADLEY2021 | Upper bound: below 1% at one year for each individual symptom except haemoptysis (2.9%) |
| `lung_cancer_risk_after_negative_cxr_12m` | 0.0035 | fraction | BRADLEY2021 | Observed 0.35% (CI 0.22-0.48) at one year in people who had a negative X-ray; about 28 of 114 one-year cancers had a negative X-ray |
| `cxr_positive_predictive_value` | 0.0902 | fraction | BRADLEY2021 | Positive CXR in the same cohort |
| `urgent_referral_cancer_conversion_median_all_cancers` | 0.12 (range 0.08 to 0.17) | fraction | SEWELL2020 | Sewell describes urgent suspected-cancer pathways as converting 8-17% (median across studies, all cancers, not lung-specific); their own rapid diagnostic centre converted 12%. The lung-specific 2022 BJGP figure in the team brief was not found |
| `nonspecific_symptoms_extra_wait_to_diagnosis` | 34 | days | SEWELL2020 | Median extra wait to diagnosis for patients with vague versus alarm symptoms, cited in Sewell's introduction from earlier research (secondary; original not identified). Not Finnish. Use as the equity gap size for the non_specific group, or cite as UK evidence |
| `rapid_diagnostic_centre_mean_days_usual_care` | 84.2 | days | SEWELL2020 | Swansea Bay, vague symptoms, usual care mean (SD 65.3), all cancers |
| `rapid_diagnostic_centre_mean_days_diagnosed_at_clinic` | 5.9 | days | SEWELL2020 | Mean; those needing further tests 40.8 days |
| `median_diagnostic_interval_haemoptysis_uk` | 39 | days | KOO2023 | English lung cancer patients after first haemoptysis, IQR 21-71 |
| `median_diagnostic_interval_dyspnoea_uk` | 83 | days | KOO2023 | IQR 28-205; 34 days with guideline-concordant imaging versus 114 without. Evidence that a missing early image drives the delay |
| `cxr_miss_rate` | 0.2 | fraction | HSSIB2021 | About one in five lung cancers missed on chest X-ray in HSSIB's wording; underlying data is Bradley 2019 (sensitivity 77-80%) |

### capacity

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `ct_scans_per_day_county` | 30 | scans per weekday | assumption | No Finnish county capacity data found. Placeholder for all CT demand in a 250,000-person county, of which suspected-lung-cancer is a small share; set the lung-pathway server capacity by calibrating to the 14-28 day specialist wait. Finland has the fewest CT scanners per capita in the Nordics (IHE2026) |
| `bronchoscopy_ebus_slots_per_day` | 4 | slots per weekday | assumption | No data found. Placeholder; calibrate to the reported 28 day diagnosis-after-specialist wait |
| `pet_ct_slots_per_day_region` | 8 | slots per weekday | assumption | No data found. Placeholder; PET-CT is usually a regional (university hospital) resource |
| `gp_nurse_first_contacts_per_day` | 30 | contacts per day | assumption | Taken from the architecture example (gp capacity 30). Not sourced |
| `surgery_slots_thoracic_per_day` | 2 | operations per day | PIRHA_PATH | The Pirkanmaa page states about two operations per day for the unit named there; applies to one hospital, not a county |

## Test accuracy and invasiveness

### chest xray

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity_symptomatic` | 0.754 | fraction | BRADLEY2021 | Cancers diagnosed within 1 year among symptomatic over-50s in Leeds (self-referred); 86 of 114 had a positive film. Systematic review (BRADLEY2019) gives 76.8%, 79.3%, 79.7% in its three low-bias studies |
| `specificity_symptomatic` | 0.902 | fraction | BRADLEY2021 | Same cohort |
| `negative_predictive_value` | 0.997 | fraction | BRADLEY2021 | At one year; 0.35% still develop a diagnosis after a negative film |
| `miss_rate_hssib` | 0.2 | fraction | HSSIB2021 | About one in five cancers missed; consistent with sensitivity 77-80% |

### low dose ct

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity_screening` | 0.846 | fraction | HOREWEG2014 | NELSON interim analysis, high-risk smokers 50-75, first 3 rounds plus 2 years follow-up. Screening population, so use with care for symptomatic patients. Secondary (news summary) |
| `specificity_screening` | 0.986 | fraction | HOREWEG2014 | Same |
| `positive_predictive_value_screening` | 0.404 | fraction | HOREWEG2014 | Same |

### diagnostic ct chest

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity_detect_primary_tumour` | 0.95 | fraction | assumption | No direct source retrieved for diagnostic CT detection of a primary lung tumour in a symptomatic patient. Reasoned as at least the LDCT screening sensitivity of 0.846 (HOREWEG2014) because full-dose CT reads better; sensitivity analysis recommended over 0.85-0.98 |
| `specificity_for_cancer` | 0.8 | fraction | assumption | Nodules and masses are often benign (infection, scarring); no sourced number retrieved. For nodal staging see mediastinal_staging |

### pet ct

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity_malignant_lesion` | 0.968 | fraction | GOULD2001 | FDG-PET (stand-alone, not PET-CT) meta-analysis of 40 studies, 1,474 pulmonary lesions, at the operating point reflecting current practice. Pooled maximum joint sensitivity and specificity 91.2% |
| `specificity_malignant_lesion` | 0.778 | fraction | GOULD2001 | Same operating point; false positives from inflammation/infection |
| `treatment_plan_changed_by_pet_ct` | 0.02 | fraction | STOKSTAD2019 | In the Norwegian stage I-II cohort PET-CT changed the plan in 2%; further workup was triggered in about 12% |

### mediastinal staging

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `ct_sensitivity` | 0.55 | fraction | GELBERG2014 | Per ACCP 2013 (SILVESTRI2013) via Gelberg review; nodal disease prevalence about 30%. Studies differ in population so do not compare modalities directly |
| `ct_specificity` | 0.81 | fraction | GELBERG2014 | NPV 83% |
| `pet_sensitivity` | 0.8 | fraction | GELBERG2014 | Prevalence about 28% |
| `pet_specificity` | 0.88 | fraction | GELBERG2014 | NPV 91% |
| `ebus_tbna_sensitivity` | 0.89 | fraction | GELBERG2014 | ACCP 2013 value. Meta-analyses summarised by ALMEIDA2012 give 0.88 and 0.93; 0.94 when patients are selected by PET/CT positive nodes versus 0.76 when not selected |
| `ebus_tbna_sensitivity_unselected` | 0.76 | fraction | ALMEIDA2012 | From the meta-analysis summarised there; i.e. false negatives of about 24% when patients are not pre-selected by imaging |
| `ebus_tbna_specificity` | 1.0 | fraction | GELBERG2014 | Reviewers note 100% could not be verified without a follow-up test. Treat as 'very high', e.g. 0.99 in sensitivity runs (assumption) |
| `ebus_tbna_npv` | 0.91 | fraction | GELBERG2014 | ACCP 2013 |

### bronchoscopy

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity_central_endobronchial` | 0.88 | fraction | RIVERA2013 | Flexible bronchoscopy, central/endobronchial lesions (ACCP 2013) |
| `sensitivity_peripheral_over_2cm` | 0.63 | fraction | RIVERA2013 | Peripheral lesions larger than 2 cm |
| `sensitivity_peripheral_under_2cm` | 0.34 | fraction | RIVERA2013 | Peripheral lesions 2 cm or smaller (ACCP wording 'less than 2 cm'). Explains repeat sampling after failed bronchoscopy in Stokstad |
| `radial_ebus_diagnostic_yield_peripheral` | 0.73 | fraction | RIVERA2013 | Guideline describes it as emerging technology; electromagnetic navigation 0.71 |
| `specificity` | 1.0 | fraction | assumption | A positive tissue sample is taken as true cancer; false positives on cytology are rare. Not sourced here |
| `p_nondiagnostic_peripheral` | 0.4 | fraction | assumption | Derived: roughly 1 minus the blended peripheral sensitivity (0.34 to 0.63) for a mix of lesion sizes, and in Stokstad 15 patients needed repeat sampling after a failed bronchoscopy. Not a published rate |
| `complication_pneumothorax` | 0.01 | fraction | assumption | No sourced figure retrieved. Guideline abstract (RIVERA2013) says transthoracic needle has a higher pneumothorax rate than bronchoscopic methods |

### transthoracic needle biopsy

| Parameter | Value | Unit | Source | Note |
|---|---|---|---|---|
| `sensitivity` | 0.9 | fraction | RIVERA2013 | Pooled sensitivity of transthoracic needle aspiration/biopsy; trend to lower sensitivity for lesions under 2 cm |
| `p_nondiagnostic` | 0.027 | fraction | UZUN2017 | Single-centre CT-guided FNA, 12 of 432; diagnostic accuracy 97.6%. Optimistic for a general hospital; sensitivity analysis recommended up to 0.10 (assumption) |
| `pneumothorax_any` | 0.15 | fraction | WIENER2011 | About 15% in a US population-based sample of biopsies for nodules (secondary summary). Single-centre UZUN2017 found 19% |
| `pneumothorax_chest_tube` | 0.066 | fraction | WIENER2011 | Needing a chest tube; single-centre UZUN2017 found 2.9% |

## What we could not find

- Stokstad per-step waits not in the paper: referral to first visit (only counts over 7 and 14 days), CT to first visit, bronchoscopy wait, TTNB wait, tumour board wait, treatment decision to start (we read the surgery 13 and radiotherapy 22.5 day medians as referral-for-treatment to start; the paper's wording is ambiguous). Estimates for these are tagged `assumption` in `params/stokstad.yaml`; calibrate them so the baseline run gives the 46.5 day median and 40% on time.
- Which weekday the Trondheim tumour board met, and the companion 2017 paper (doi 10.1186/s12913-016-1952-y), which we did not reach.
- The paper's full text was read through a library mirror copy (d-nb.info); the publisher, PMC and Europe PMC hosts were blocked, so the figures (Fig. 4) were not seen directly, and the abstract and body differ on small counts (p 0.254 vs 0.255, 11 vs 12 further workups).
- Finnish PET-CT wait, tumour board frequency, CT and bronchoscopy daily capacity, and any county-level capacity data. Capacities are placeholders to calibrate against the survey waits.
- Finnish registry incidence for 2023 or 2024 (we have a GLOBOCAN estimate of 2,913 cases; the 2,500-2,700 in the brief is unverified) and population by wellbeing county (we use an average).
- The 'Smith et al. 2022 BJGP' figures on lung cancer prevalence among chest symptom presenters, CXR referrals and urgent referrals were not located. We use Bradley 2021 (self-referred CXR, Leeds) and Koo 2023 (dyspnoea/haemoptysis, English primary care) instead. Both are UK data. The lung-specific urgent-referral conversion rate is missing; only an all-cancer 8-17% range (via Sewell 2020) is given.
- Mattila 2025 was read as an abstract only; exact days were not given. Khalife 2025 waits are modal answers of 42 specialists, not measured waits, and respondents called the 14 day GP wait optimistic.
- The 34 day extra wait for non-specific symptoms is a secondary citation inside Sewell 2020; the Scotland RCDS data were not found. It is UK evidence, not Finnish.
- Source documents not found for: diagnostic CT sensitivity in symptomatic patients, bronchoscopy and EBUS complication rates, EBUS non-diagnostic rate, cost per test in euros. All of these are `assumption` or absent. The ACCP 2013 guideline numbers were read through the PubMed abstract (bronchoscopy) and a review that quotes the guideline (staging); the TTNB meta-analysis PMC pages were blocked, so the pneumothorax rate comes from a news summary of Wiener 2011 and a single-centre series.
- Not checked: BTS, NICE and Kaypa hoito guideline numbers (a Finnish pathway document from Pirkanmaa was used for process times instead).

## Sources

| Id | Citation | Year | Access | URL |
|---|---|---|---|---|
| STOKSTAD2019 | Stokstad T, et al. Reasons for prolonged time for diagnostic workup for stage I-II lung cancer and estimated effect of applying an optimized pathway for diagnostic procedures. BMC Health Services Research 2019;19:679. | 2019 | full_text | https://doi.org/10.1186/s12913-019-4517-z |
| IHE2026 | IHE. IHE Cancer Dashboard Finland (April 2026). Stockholm: Swedish Institute for Health Economics. | 2026 | full_text | https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf |
| KHALIFE2025 | Khalife G, Warisa J, Bodtger U, Isaksson J, Neumann K, Hardardottir H, et al. Comparative study of lung cancer care and survival outcomes across the Nordic countries. Acta Oncologica 2025;64:734-741. | 2025 | full_text | https://doi.org/10.2340/1651-226X.2025.42778 |
| MATTILA2025 | Mattila S. Keuhkosyovan diagnostinen viive Satakunnassa koronapandemian aikana (Lung cancer diagnostic delay in Satakunta during the COVID-19 pandemic). Advanced studies thesis, University of Turku, 2025. | 2025 | abstract | https://www.utupub.fi/handle/10024/180618 |
| YLE_MOT2025 | Yle (MOT programme), news article 23 Oct 2025, reporting an unpublished MOT study of lung cancer diagnostic delay in Finland, Sweden and Denmark. | 2025 | secondary | https://yle.fi/a/74-20251023 |
| HELSINKI2025_NEWS | University of Helsinki news item: Miksi Suomessa keuhkosyopaan kuollaan aiemmin kuin Pohjoismaissa? (reporting the Khalife et al. survey). | 2025 | secondary | https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa |
| BRADLEY2021 | Bradley SH, Hatton NLF, Aslam R, et al. Estimating lung cancer risk from chest X-ray and symptoms: a prospective cohort study. Br J Gen Pract 2021;71(705):e280-e286. | 2021 | full_text | https://bjgp.org/content/71/705/e280 |
| BRADLEY2019 | Bradley SH, Abraham S, Callister MEJ, et al. Sensitivity of chest X-ray for detecting lung cancer in people presenting with symptoms: a systematic review. Br J Gen Pract 2019;69(689):e827-e835. | 2019 | abstract | https://eprints.whiterose.ac.uk/id/eprint/146374/ |
| HSSIB2021 | HSIB (now HSSIB). Missed detection of lung cancer on chest X-rays of patients being seen in primary care. Investigation report R5323, 14 October 2021. | 2021 | full_text | https://hssib.org.uk/patient-safety-investigations/missed-detection-of-lung-cancer-on-chest-x-rays-of-patients-being-seen-in-primary-care/investigation-report |
| KOO2023 | Koo MM, Mounce LTA, Rafiq M, Callister MEJ, Singh H, Abel GA, Lyratzopoulos G. Guideline concordance for timely chest imaging after new presentations of dyspnoea or haemoptysis in primary care: a retrospective cohort study. Thorax 2023 (doi 10.1136/thorax-2022-219509). | 2023 | full_text | https://doi.org/10.1136/thorax-2022-219509 |
| SEWELL2020 | Sewell B, Jones M, Gray H, et al. Rapid cancer diagnosis for patients with vague symptoms: a cost-effectiveness study. Br J Gen Pract 2020;70(692):e186-e192. | 2020 | full_text | https://bjgp.org/content/70/692/e186 |
| RIVERA2013 | Rivera MP, Mehta AC, Wahidi MM. Establishing the diagnosis of lung cancer: Diagnosis and management of lung cancer, 3rd ed: ACCP evidence-based clinical practice guidelines. Chest 2013;143(5 Suppl):e142S-e165S. | 2013 | abstract | https://pubmed.ncbi.nlm.nih.gov/23649436/ |
| SILVESTRI2013 | Silvestri GA, Gonzalez AV, Jantz MA, et al. Methods for staging non-small cell lung cancer: ACCP evidence-based clinical practice guidelines. Chest 2013;143(5 Suppl):e211S-e250S. | 2013 | secondary | https://pubmed.ncbi.nlm.nih.gov/23649440/ |
| GELBERG2014 | Gelberg J, Grondin S, Tremblay A. Mediastinal staging for lung cancer. Can Respir J 2014;21(3):159-161. doi:10.1155/2014/890108. | 2014 | full_text | https://pmc.ncbi.nlm.nih.gov/articles/PMC4128458 |
| ALMEIDA2012 | Almeida FA. Bronchoscopy and endobronchial ultrasound for diagnosis and staging of lung cancer. Cleve Clin J Med 2012. | 2012 | full_text | https://www.mdedge.com/ccjm/article/95807/bronchoscopy-and-endobronchial-ultrasound-diagnosis-and-staging-lung-cancer/page/0/1 |
| GOULD2001 | Gould MK, et al. Accuracy of positron emission tomography for diagnosis of pulmonary nodules and mass lesions: a meta-analysis. JAMA 2001 (22 Feb issue). | 2001 | abstract | https://www.qxmd.com/r/11180735 |
| HOREWEG2014 | Horeweg N, et al. NELSON trial prespecified interim analysis of low-dose CT screening performance. Lancet Oncology 2014. | 2014 | secondary | https://www.news-medical.net/news/20141119/CT-screening-highly-sensitive-specific-for-lung-cancer-detection.aspx |
| WIENER2011 | Wiener RS, et al. Study of complications after transthoracic needle lung biopsy of pulmonary nodules. Ann Intern Med, 2 Aug 2011 issue (title paraphrased; volume/pages not verified). | 2011 | secondary | https://www.healthday.com/healthpro-news/pulmonology/pneumothorax-common-after-transthoracic-needle-biopsy-655390.html |
| UZUN2017 | Uzun C, Akkaya Z, Atman ED, et al. Non-coaxial CT-guided fine needle aspiration of pulmonary lesions, 442 biopsies. Diagn Interv Radiol 2017;23:137-. | 2017 | full_text | https://dirjournal.org/pdf/beb8919b-f013-4ea1-b1c8-40332e840fe1/articles/dir.2016.16173/Diagn%20Interv%20Radiol-23-137-En.pdf |
| GLOBOCAN_FIN | IARC Global Cancer Observatory. Finland fact sheet (GLOBOCAN), as retrieved 2026-11-14. | 2024 | full_text | https://gco.iarc.who.int/media/globocan/factsheets/populations/246-finland-fact-sheet.pdf |
| PIRHA_PATH | Pirkanmaa Hospital District (Pirha). Keuhkosyopapotilaan hoitopolku (lung cancer patient pathway), patient information document. | 2025 | full_text | https://pirha.fi/documents/d/kehitysversio/keuhkosyopapotilaan-hoitopolku |

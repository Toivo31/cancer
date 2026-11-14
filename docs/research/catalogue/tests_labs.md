# Research note WP-C2-R2: tests, laboratory values, imaging truth

Branch `w2/research-tl`. Written 2026-11-14 for the converter agent (WP-C2-1: `tests.yaml` and the
`lab_true`, `imaging_true`, `function_true` part of `variables.yaml`).

How to read this note:

- Every number in the "New findings" tables was read on a page opened in this session (WebFetch).
  The URL given is the page that was opened. Numbers I could not source are only in "Could not source".
- Quotes are short; everything else is paraphrase. `grade` follows C2 rule 2: A systematic review or
  large study in a comparable population, B single study or related population, C expert text,
  narrative review, proxy or derived, `assumption`.
- Per C2 rule 8, the grade is already lowered one step where the population differs from
  "adults with chest symptoms in Finnish primary care". The population is always in its own column.
- Access limits met: PMC and several publishers returned captcha or allowlist errors, so several
  sources are abstract or secondary access only. This is stated per source in "New sources".
- Process steps vs tests: see the last section before "Gaps".

## 1. Carried over unchanged (from `params/test_accuracy.yaml`, not re-researched)

Entries with a real source id. Converter: copy values and notes as they stand.

| entry | value | source id | grade (suggested) |
|---|---|---|---|
| chest_xray.sensitivity_symptomatic | 0.754 | BRADLEY2021 | A (large cohort, UK symptomatic over-50s) |
| chest_xray.specificity_symptomatic | 0.902 | BRADLEY2021 | A |
| chest_xray.negative_predictive_value | 0.997 (1 year) | BRADLEY2021 | A |
| chest_xray.miss_rate_hssib | 0.20 | HSSIB2021 | C (investigation report) |
| low_dose_ct.sensitivity_screening | 0.846 | HOREWEG2014 | B (screening population, secondary) |
| low_dose_ct.specificity_screening | 0.986 | HOREWEG2014 | B |
| low_dose_ct.positive_predictive_value_screening | 0.404 | HOREWEG2014 | B |
| pet_ct.sensitivity_malignant_lesion | 0.968 | GOULD2001 | B (stand-alone PET, not PET-CT) |
| pet_ct.specificity_malignant_lesion | 0.778 | GOULD2001 | B |
| pet_ct.treatment_plan_changed_by_pet_ct | 0.02 | STOKSTAD2019 | B (Norway stage I-II) |
| mediastinal_staging.ct_sensitivity / specificity | 0.55 / 0.81 | GELBERG2014 (ACCP via review) | B |
| mediastinal_staging.pet_sensitivity / specificity | 0.80 / 0.88 | GELBERG2014 | B |
| mediastinal_staging.ebus_tbna_sensitivity | 0.89 | GELBERG2014 | A |
| mediastinal_staging.ebus_tbna_sensitivity_unselected | 0.76 | ALMEIDA2012 | B |
| mediastinal_staging.ebus_tbna_specificity | 1.0 (use ~0.99 in sensitivity runs) | GELBERG2014 | B |
| mediastinal_staging.ebus_tbna_npv | 0.91 | GELBERG2014 | B |
| bronchoscopy.sensitivity_central_endobronchial | 0.88 | RIVERA2013 | A |
| bronchoscopy.sensitivity_peripheral_over_2cm | 0.63 | RIVERA2013 | A |
| bronchoscopy.sensitivity_peripheral_under_2cm | 0.34 | RIVERA2013 | A |
| bronchoscopy.radial_ebus_diagnostic_yield_peripheral | 0.73 | RIVERA2013 | B (emerging technology) |
| transthoracic_needle_biopsy.sensitivity | 0.90 | RIVERA2013 | A |
| transthoracic_needle_biopsy.p_nondiagnostic | 0.027 | UZUN2017 | B (single centre, Turkey; re-checked below) |
| transthoracic_needle_biopsy.pneumothorax_any | 0.15 | WIENER2011 | B (secondary); see section 3 for a pooled value |
| transthoracic_needle_biopsy.pneumothorax_chest_tube | 0.066 | WIENER2011 | B (secondary); see section 3 |
| report times in `scenarios/finland_lung.yaml`: tissue to pathology 4.5 d, PET report 2.5 d (STOKSTAD2019); CT within about a week, bronchoscopy result 3-5 d (PIRHA_PATH) | | STOKSTAD2019, PIRHA_PATH | B / C |

Entries marked `assumption` in the file and what this note did with them:

| entry | status after this note |
|---|---|
| diagnostic_ct_chest.sensitivity_detect_primary_tumour (0.95) | proxy source found: WEIRMCCALL2020, 0.948 (grade B proxy, nodule population). Keep the 0.95 value, change source from `assumption` to WEIRMCCALL2020 with the caveat |
| diagnostic_ct_chest.specificity_for_cancer (0.80) | proxy source found: WEIRMCCALL2020 specificity 0.755 (0.738 in its key points). 0.80 is within the range of PET-CT proxy values (0.70 to 0.78) but is slightly above the CT proxy. Suggest value 0.75 to 0.80, grade B proxy |
| bronchoscopy.specificity (1.0) | still assumption (not sourced here) |
| bronchoscopy.p_nondiagnostic_peripheral (0.40) | still derived (from RIVERA2013 sensitivities); no published non-diagnostic rate found |
| bronchoscopy.complication_pneumothorax (0.01) | partly sourced: STAHL2015 gives 0.07 to 0.16 % for fibreoptic bronchoscopy generally; no transbronchial-biopsy-specific figure found, so 0.01 for biopsy remains an assumption (flag as upper bound) |
| ebus_tbna_specificity "very high" | unchanged |

## 2. Imaging tests (R2-T2)

| entry | measures | value | low | high | unit | source | population / setting | grade | note |
|---|---|---|---|---|---|---|---|---|---|
| diagnostic_ct_chest.detect_lesion_sens | imaging_true.lung_lesion | 0.948 | 0.915 | 0.969 | fraction | WEIRMCCALL2020 | 23 studies, 2,397 participants, 2,514 solitary pulmonary nodules, dynamic contrast-enhanced CT, malignant vs benign | B (proxy) | This is nodule characterisation with dynamic contrast CT, not detection in a chest-symptom population. The Key Points of the paper give 0.951 and specificity 0.738, which differ slightly from the Results text (0.948, 0.755). Use as the proxy for "CT says suspicious for malignancy" |
| diagnostic_ct_chest.specific | same | 0.755 | 0.694 | 0.806 | fraction | WEIRMCCALL2020 | as above | B (proxy) | see above |
| pet_ct.sens_snp | imaging_true.lung_lesion (malignant) | 0.89 | 0.87 | 0.91 | fraction | LI2018 | 21 studies, 1,557 patients, solitary pulmonary nodules, FDG-PET/CT, about 59 % malignant (my calculation from 918/1,557) | A | Newer and PET-CT specific, compare with the carried GOULD2001 (stand-alone PET) 0.968 |
| pet_ct.spec_snp | same | 0.70 | 0.66 | 0.73 | fraction | LI2018 | as above | A | Suggest the converter offers LI2018 as the PET-CT value and keeps GOULD2001 as a sensitivity bound |
| chest_xray.missed_lesion_size_mm | imaging_true.lesion_size | 14.3 (mean) | 6.8 | 22.7 | mm | LI2008 | 34 patients with a visible-in-retrospect, unreported nodular cancer on a prior film, US academic centre, mean age 69, 32 NSCLC and 2 small cell | C | Describes the size of cancers a film missed, not a sensitivity by size. Median 14.8 mm. 68 % of the missed cancers were in the upper zones (23 of 34); left lung 19, right lung 15 |
| chest_xray.published_miss_range | | 0.20 | 0.90 | | fraction | LI2008 (citing earlier studies) | various | C | The paper states published error rates for missed cancers of 20 to 90 %. Wide; the carried BRADLEY2021 and HSSIB2021 values are the better anchors |
| brain_mri.bm_asymptomatic_stage_II | imaging_true.brain_metastasis | 0.021 | | | fraction | BROCKELSBY_PRENDECKI | Pre-treatment brain imaging, stage II NSCLC, 1 of 47 (UK multi-centre real-world) | B | Tiny numerator. Combined with post-treatment detection in patients not imaged before, the study reports 6.2 % (10/161); the NICE model assumed 9.5 % (CI 5.3 to 14.8) |
| brain_mri.bm_asymptomatic_stage_III | same | 0.052 | | | fraction | BROCKELSBY_PRENDECKI | stage III, 10 of 193 imaged pre-treatment | B | Combined 6.0 % (17/283); NICE model 9.3 % (CI 4.6 to 15.5) |
| brain_mri.bm_cum_incidence_2y_stage_III | imaging_true.brain_metastasis (later) | 0.17 | 0.11 | 0.23 | fraction | ALHUSAINI2023 | Stage III NSCLC with PET and MRI staging at diagnosis (no brain metastasis at baseline), n=160, Stanford | B | 2-year cumulative incidence of brain metastases; 54 % of those found were asymptomatic. Only relevant if the simulator models later progression |
| brain_mri.sensitivity | imaging_true.brain_metastasis | not found | | | | | | | The Brockelsby paper says CT vs MRI difference is "relatively modest" and gives no numbers. See "Could not source" |

Notes for the converter:
- Chest X-ray sensitivity by nodule size and location was not found in a usable form (see gaps). The
  carried BRADLEY2021 symptomatic sensitivity stays the main number; the upper-zone and 14 mm size
  of missed cancers (LI2008) can seed a `by: {nodule_size_mm}` modifier only as an assumption.
- Low-dose CT is a screening test, not part of the Finnish symptomatic pathway; carried values only.

## 3. Tissue, endoscopy, pathology, molecular (R2-T3)

| entry | measures | value | low | high | unit | source | population / setting | grade | note |
|---|---|---|---|---|---|---|---|---|---|
| sputum_cytology.sensitivity | tissue_true.malignant | 0.66 | | | fraction | RIVERA2013 | ACCP guideline, pooled sensitivity of sputum cytology for lung cancer | A | RIVERA2013 is already registered; the abstract was re-read this session. Not a centrally located-only number; true yield depends on tumour location (central higher), not given in the abstract |
| sputum_cytology.specificity | same | 0.99 | | | fraction | RIVERA2013 | same | A | |
| ttnb.pneumothorax_any | complication | 0.259 | 0.043 | 0.524 | fraction | HUO2020 | Systematic review and meta-analysis, 36 studies, 23,104 patients having CT-guided lung biopsy (31 retrospective, 3 prospective, 2 RCTs), pooled incidence; range is the spread across studies | A | Higher than the carried 0.15 (WIENER2011). The carried single-centre value 0.196 (UZUN2017) and WIENER2011 0.15 lie inside the range. Suggest HUO2020 as the central value and the others as low |
| ttnb.pneumothorax_chest_tube | complication | 0.069 | 0.0 | 0.15 | fraction | HUO2020 | same | A | Pooled chest drain insertion |
| ttnb.sens_spec_single_centre | tissue_true.malignant | 0.973 / 1.0 | | | fraction | UZUN2017 | 442 patients, CT-guided FNA, Ankara, 2011-2015; diagnostic accuracy 97.6 % (410/420), sensitivity 97.3 % (367/377) | B | Optimistic. Carried value 0.90 (RIVERA2013 pooled) is the safer central value |
| ttnb.p_nondiagnostic | | 0.027 | | | fraction | UZUN2017 | 12/432, as carried | B | Re-read; an open-access PTNB series (n=108) reported 16.7 % non-diagnostic (text) or 27.6 % (abstract), internally inconsistent and the citation was not on the page, so it is not used. Suggest low 0.027, high 0.10 as in the file |
| bronchoscopy.complication_fibreoptic_overall | complication | not a point value | 0.001 | 0.11 | fraction | STAHL2015 | narrative review of fibreoptic bronchoscopy: overall complication rate reported from under 0.1 % to 11 % in studies since the 1960s; mortality 0 to 0.1 % | C | Very wide, and it covers diagnostic and therapeutic bronchoscopy |
| bronchoscopy.pneumothorax_fibreoptic | complication | 0.0007 | | 0.0016 | fraction | STAHL2015 | "more recent studies", fibreoptic bronchoscopy generally (0.07 to 0.16 %) | C | Not transbronchial-biopsy-specific; the article does not give the rate after transbronchial biopsy |
| bronchoscopy.bleeding_over_50ml | complication | 0.0012 | 0.0017 | | fraction | STAHL2015 | 5 of 4,273 in a retrospective academic centre; 0.17 % in a Greek study | C | Prospective data: 0.7 % bleeding (6/908) and 2 % (4 of 205, trainee operators) |
| ebus_tbna.infectious_complication | complication | 0.0019 | 0.0016 | 0.0054 | fraction | AHMETOGLU2023 (secondary) | Japanese nationwide survey 0.19 % (total 7,345 cases); a 3,123-patient study 0.16 %; registry 0.48 % (33/6,826); literature range 0.19 to 0.54 % | C | Secondary: read in the introduction of a case report. Treat as order of magnitude |
| ebus_tbna.infectious_complication_prospective | complication | 0.0405 | | | fraction | SERRA2023 | Prospective multicentre cohort of 370 patients at 3 tertiary hospitals in Spain; 4.05 % overall, 5.71 % with risk factors, 0.8 % without (1/125) | B | The much higher rate than the surveys is probably due to prospective active follow-up; I did not check the definition of "infectious complication". Use as the upper bound |
| histology_report.turnaround_days | | 4.5 | 0 | 14 | days (median, range) | STOKSTAD2019 | Norway, stage I-II, tissue sampling to pathology report | B | Carried; range added. Patients often had a follow-up visit 1 to 2 weeks after sampling, which is queue not report time |
| molecular_panel.turnaround_days_in_house | | 4 | | | working days | PATHOLOGIST2024 | In-house NGS, Rigshospitalet Copenhagen; mean order to result 4 working days (544 DNA and 490 RNA samples) | C | Trade-press article that reports the study without a citation. The same article says outsourced NGS can take "several weeks" and gives a Danish recommended total diagnostic time of 24 days (no source named) |
| molecular_panel.finland_actionable | tissue_true.actionable_marker | 0.45 | | | fraction | HORMALAINEN2025 | 96 advanced NSCLC patients, Tampere University Hospital, comprehensive genomic profiling Nov 2021 to Mar 2023; 63 % of never-smokers and 41 % of ever-smokers; KRAS G12C 18 %, EGFR 14 % | B | Finnish. No turnaround reported on the page I opened. Only needed if the pathway models marker status |

Cost in euros: no Finnish price list was found in this session (see "Could not source").

## 4. Bloodwork, function, history, and true laboratory values by condition (R2-T4)

### 4a. Test accuracy and what the test reveals

| entry | measures | value | unit | source | population / setting | grade | note |
|---|---|---|---|---|---|---|---|
| crp.pneumonia_prediction | lab_true.crp, consolidation | PPV 0.47, NPV 0.84, AUC 0.69 (95 % CI 0.58 to 0.80) | fraction | GRAFFELMAN2007 (via a news summary of the paper) | 129 adults with lower respiratory tract infection in Leiden primary care, 26 with pneumonia | C | The best model included CRP; models based on history and examination alone did "not reliably predict" pneumonia. Doubles as an estimate for how much a clinical history is worth when pneumonia is the question |
| crp.pneumonia_pooled_models | | sensitivity 0.97 / specificity 0.28 (basic model) and 0.36 (with CRP) at risk threshold under 2.5 %; sensitivity 0.63 to 0.70 / specificity 0.87 to 0.90 at risk threshold over 20 % | fraction | MINNAARD2016 | Individual patient data meta-analysis, 8 studies, primary care and emergency departments, adults with suspected LRTI | A (for the clinical-model comparison) | These are for prediction models, not CRP alone. The paper does not report CRP-alone cut-offs |
| spirometry.copd_detection_proxy | function_true.fev1_fvc | sensitivity 0.932 (0.833 to 0.981), specificity 0.850 | fraction | VANDENBEMT2014 | 104 subjects in Dutch primary care, pre-bronchodilator microspirometer FEV1/FEV6 under 0.73 vs full spirometry post-bronchodilator FEV1/FVC under 0.70 | C | A proxy: it measures a handheld device against full spirometry, not full spirometry's own accuracy. Full spirometry is the reference test in COPD, so a converter can treat it as exact (sens/spec near 1) for "airflow obstruction" and put the error in the true variable |
| history_and_exam.symptom_elicitation | symptoms, signs | no published rate found | | | | | | See "Could not source" |

### 4b. Distribution of true values by condition

Units: `value` is the share or central value; `low`/`high` are CI or range as stated.

| entry | measures | value | low | high | unit | source | population / setting | grade | note |
|---|---|---|---|---|---|---|---|---|---|
| lab_true.haemoglobin.lung_cancer.anaemia_share | haemoglobin | 0.321 | | | fraction | CHEN2021 | 4,874 stage IV NSCLC patients at first visit, Zhejiang Cancer Hospital, China, 2013-2019. Anaemia: Hb under 120 g/L (men) or under 110 g/L (women) | C | Stage IV only, Chinese, so likely higher than for all stages and for Finland. Grade lowered |
| lab_true.haemoglobin.lung_cancer.mean | haemoglobin | 123.3 (SD 20.3) | | | g/L | CHEN2021 | same | C | Anaemia grades: mild 19.1 %, moderate 10.8 %, severe 1.9 %, life-threatening 0.3 % |
| lab_true.platelets.thrombocytosis_threshold | platelets | 400 | | | x10^9/L | BAILEY2017 | Definition used in a UK primary care cohort (CPRD linked to the cancer registry, 2000-2013, about 40,000 with thrombocytosis vs 10,000 matched normal) | A (for the definition) | |
| lab_true.platelets.thrombocytosis.prevalence_primary_care | platelets | 0.015 | | 0.022 | fraction | BAILEY2017 (cites earlier studies) | primary care consulters aged 40 or over | B | 1.5 to 2.2 % in the introduction |
| lab_true.platelets.thrombocytosis.lung_cancer_among_raised | platelets | 0.018 | | | fraction | BAILEY2017 | 573 of 31,261 patients with thrombocytosis later had lung cancer (derived by me: 573/31,261) | B | The follow-up window for this count was not stated on the page I opened; do not use as a one-year PPV without checking. 35.7 % of these had no symptoms warranting urgent investigation apart from thrombocytosis |
| lab_true.platelets.thrombocytosis.ppv_any_cancer_1y | platelets | 0.116 (men) / 0.062 (women) | 0.110 / 0.059 | 0.123 / 0.065 | fraction | BAILEY2017 (via GPNOTEBOOK summary) | one-year risk of any cancer with platelets above 400 | B | Lung-cancer-specific PPV by sex and age was not on any page I opened. A later study (Giannakeas 2022, summarised on GPNotebook) gives odds ratio 4.37 (4.22 to 4.53) for lung cancer within 6 months for very high vs medium platelet count; not opened directly |
| lab_true.crp.lrti_medians_by_setting | crp | median 7 to 96 | IQR 3 to 258 | | mg/L | MINNAARD2016 | 8 primary-care and emergency studies, not split by pneumonia status. Pneumonia prevalence per study 5 % to 43 % | C | Medians rise with pneumonia share: 7 mg/L (5 % pneumonia, 2,820 patients, GP), 14 (13 %, GP), 23 (13 %, GP), 36 (21 %, GP + ED), 50 (20 %, GP), 96 (43 %, ED, IQR 20 to 258). Use as a lognormal anchor: general LRTI in primary care about 7 to 50 mg/L, ED pneumonia-rich about 96. Pneumonia-only median not available |
| lab_true.calcium.lung_cancer.hypercalcaemia_share | calcium | 0.071 | | | fraction | CHAN2020 | 624 tissue-proven lung cancers, regional MDT in Cork, Ireland, 2011-2016; corrected calcium above 2.62 mmol/L; 38 moderate and 6 severe | B | By histology: squamous 12.2 %, non-squamous NSCLC 4.3 %, SCLC 3.9 %. By stage: I-II 3.7 %, IIIA 13.4 %, IIIB-IV 9.1 %, extensive SCLC 5.4 % |
| lab_true.sodium.lung_cancer.hyponatraemia_share | sodium (optional variable) | 0.316 | | | fraction | CHAN2020 | same, sodium 135 mEq/L or lower | B | SCLC 41.2 %, squamous 36.5 %, non-squamous 25.9 %. Only if sodium is added to the catalogue |
| lab_true.alp.lung_cancer.mean_with_bone_mets | alp | 115.3 (SD 21.6) | | | U/L | YE2025 | 68 NSCLC patients with bone metastasis, hospital in Zhejiang, China; normal range stated 45 to 125 U/L | C | Without bone metastasis: 106.2 (SD 15.5), n=80 |
| lab_true.alp.bone_mets_detection | alp | sens 0.413, spec 0.771 | | | fraction | SCIREP2017 | 2,021 lung cancer patients, ALP as an independent risk factor for bone metastasis | C | 23.9 % of the 2,021 patients had bone metastasis. A second study (YE2025) found sens 0.221, spec 0.900 at a 110 U/L cut-off. Both say ALP alone is a poor test for bone metastasis |
| lab_true.ldh.stage_IV_nsclc.elevated_share | ldh | 0.569 | | | fraction | LEE2016 | 394 stage IV NSCLC patients, Korea; elevated = above 450 IU/L (centre-specific cut-off); median 477 IU/L, range 113 to 2,850 | C | Stage IV only, high cut-off, so not transferable to "elevated vs Finnish reference range" without care. No all-stage LDH distribution found |
| function_true.fev1.copd.gold_stage_share | fev1_pct_predicted (by stage) | I 0.171, II 0.522, III 0.255, IV 0.052 | | | fraction | HAUGHNEY2014 | 6,283 UK general-practice COPD patients (of 9,219 in 80 practices) with FEV1 and symptom scores, GOLD 2007 spirometric stages | B | Stage = spirometric severity band. The percent-predicted thresholds of each GOLD stage were not on a page I opened (see "Could not source"), and a patient-level median and p10/p90 for FEV1 % predicted were not found |
| lab_true.crp.lung_cancer | crp | not found | | | | | | | See "Could not source" |

## 5. Imaging truth distributions (R2-T5)

| entry | measures | value | low | high | unit | source | population / setting | grade | note |
|---|---|---|---|---|---|---|---|---|---|
| stage_at_dx.nsclc.I_to_IIIA_share | stage | 0.395 (I 0.197, II 0.089, IIIA 0.109) | | | fraction | PAAPPANEN2025 | All 395 NSCLC patients diagnosed in 2018 in five Finnish hospitals (545 lung cancers in all) | B | The remaining 0.605 is stage IIIB, IV or not staged by derivation (100 % minus 39.5 %); the page I read did not split it. Finnish. Fits the simulator's default. The same paper notes Finland has a lower share of stage I than Norway (30.6 %) and Sweden (25.8 %) |
| stage_at_dx.nsclc.operable_cohort_stage | stage | I 0.50, II 0.224, IIIA 0.276 | | | fraction | PAAPPANEN2025 | 156 potentially operable NSCLC (stage I-IIIA by CT) | B | Subset, not for prevalence. 77 of 156 (49.4 %) underwent surgery |
| nodes.n0_by_tumour_size | imaging_true.mediastinal_nodes | N0M0: 0.91 (15 mm or less), 0.83 (16 to 25), 0.68 (26 to 35), 0.55 (36 or more) | | | fraction | LEE2006 (authors not listed on the page read) | 436 NSCLC from a CT screening programme (28,689 screened, 464 cancers) | B | Screening-detected, so smaller and earlier than symptomatic presenters. Pathological stage |
| nodes.n0_by_tumour_size_surgical | imaging_true.mediastinal_nodes | N0M0: 0.708 (20 mm or less), 0.589 (21 to 30), 0.480 (31 to 50), 0.476 (51 to 70), 0.333 (71 or more); overall 0.5365 | | | fraction | YANG2010 | 917 resected NSCLC, two Shanghai hospitals 2000-2009 | B | Surgical candidates only. N2M0 share rises from 18 % to 37 % with size; N1M0 from 7 % to 24 %. Mean size 37.2 mm (SD 21.3) in N0M0 and 45.8 mm (SD 23.2) in the rest |
| nodes.clinical_n0_surgical_norway | imaging_true.mediastinal_nodes | clinical N0 0.887; pathological N0 0.792 | | | fraction | SOLBERG2022 | 1,284 surgical patients in Norway 2018-2019 (stage I 68 %, II 19.4 %, IIIA 10.3 %); unexpected pN2 in 6.2 % | B | Surgery-selected, so understates nodal disease in the whole presenting population. Also gives clinical-vs-pathology agreement 83.3 % |
| distant_spread.share_stage_IV | imaging_true.distant_spread | not found as a population figure | | | | | | | Only surgical cohorts (1.1 % stage IV clinical, SOLBERG2022) and the Finnish residual of 60.5 % for IIIB, IV and unstaged (PAAPPANEN2025). See gaps |
| size.lesion_size_overall | imaging_true.lesion_size | not found | | | | | | | Only the size of missed cancers on X-ray (LI2008, mean 14.3 mm) and the surgical cohort mean (YANG2010, about 37 to 46 mm) were opened |

## 6. Report turnaround times (days)

| entry | value | unit | source | setting | grade | note |
|---|---|---|---|---|---|---|
| histology_report (tissue to report) | 4.5 median, range 0 to 14 | days | STOKSTAD2019 | Norway, St Olav's, stage I-II | B | carried |
| PET-CT (referral to final report) | 20.5 median, range 7 to 49 | days | STOKSTAD2019 | same | B | This is referral to report (includes waiting), unlike the carried 2.5 d report-only figure; only the report part belongs in `tests.yaml`. Note that C2 rule 4 puts waiting in C3 |
| radiology report completion | 2 median, range 1 to 55 | days | STOKSTAD2019 | same | B | a delay figure at the first visit |
| molecular panel, in-house NGS | 4 | working days | PATHOLOGIST2024 | Rigshospitalet, Copenhagen | C | |
| molecular panel, outsourced | "several weeks" | | PATHOLOGIST2024 | country not stated | C | no number |
| CT report | about a week; bronchoscopy result 3 to 5 d | days | PIRHA_PATH | Pirkanmaa | C | carried |
| Finnish molecular turnaround | not found | | | | | HORMALAINEN2025 did not report it |

## 7. New sources (proposed entries for `params/sources.yaml`)

All `accessed: 2026-11-14`. Reuse existing ids where listed in section 1.

| id | citation | url (page opened) | access | supports |
|---|---|---|---|---|
| WEIRMCCALL2020 | Weir-McCall JR, Joyce S, Clegg A, et al. Dynamic contrast-enhanced computed tomography for the diagnosis of solitary pulmonary nodules: a systematic review and meta-analysis. Eur Radiol 2020;30(6):3310-3323. | https://link.springer.com/article/10.1007/s00330-020-06661-8 | abstract | CT sensitivity 0.948, specificity 0.755 for malignant nodules |
| LI2018 | Li ZZ, Huang YL, Song HJ, Wang YJ, Huang Y. The value of 18F-FDG-PET/CT in the diagnosis of solitary pulmonary nodules: a meta-analysis. Medicine (Baltimore) 2018;97(12):e0130. | https://pmc.ncbi.nlm.nih.gov/articles/PMC5895332 | abstract | PET-CT sensitivity 0.89, specificity 0.70 |
| LI2008 | Li F, Engelmann R, Metz CE, Doi K, MacMahon H. Lung cancers missed on chest radiographs: results obtained with a commercial computer-aided detection program. Radiology 2008;246(1). | https://www2.rsna.org/timssnet/radiologyselect/pdf/category%202%20-%20detection,%20observer%20performance,%20technical%20aids%20for%20assessing%20pulmonary%20nodules/lung_cancers_missed_on_chest_radiographs.pdf | full_text (abstract-level summary) | size and location of missed cancers |
| HUO2020 | Huo YR, Chan MV, Habib AR, Lui I, Ridley L. Pneumothorax rates in CT-guided lung biopsies: a comprehensive systematic review and meta-analysis of risk factors. Br J Radiol 2020;93(1108):20190866. | https://pmc.ncbi.nlm.nih.gov/articles/PMC7362905 | full_text | pneumothorax 25.9 %, chest drain 6.9 %, risk factors (bulla OR 6.13, emphysema OR 3.33) |
| STAHL2015 | Stahl DL, Richard KM, Papadimos TJ. Complications of bronchoscopy: a concise synopsis. Int J Crit Illn Inj Sci 2015;5:189-195. | https://www.scienceopen.com/document_file/2ded9536-f0ae-4db9-83ea-6238d780100b/PubMedCentral/2ded9536-f0ae-4db9-83ea-6238d780100b.pdf | full_text | bronchoscopy complication rates |
| AHMETOGLU2023 | Ahmetoglu E, Karadogan D, Gundogdu H, et al. Mediastinitis and subcutaneous abscess complicated after EBUS-TBNA of 2R mediastinal lymph node. Tuberk Toraks 2023;71(3):20239713. | https://pmc.ncbi.nlm.nih.gov/articles/PMC10795241 | secondary | EBUS-TBNA infectious complication rates quoted from surveys (Asano, Kang) |
| SERRA2023 | Serra Mitja P, Goncalves dos Santos Carvalho F, Garcia Olive I, et al. Incidence and risk factors for infectious complications of EBUS-TBNA: prospective multicenter study. Arch Bronconeumol 2023;59:84-89. | https://archbronconeumol.org/en-incidence-risk-factors-for-infectious-articulo-S0300289622005956 | abstract | infectious complication 4.05 % |
| PATHOLOGIST2024 | The Pathologist. Timing matters, and liquid is part of the future (trade article on NSCLC biomarker turnaround; 2024 issue). | https://thepathologist.com/diagnostics/timing-matters-and-liquid-is-part-of-the-future | full_text (secondary) | in-house NGS 4 working days, outsourced several weeks |
| HORMALAINEN2025 | Hormalainen K, Marttila K, Nykter M, et al. Comprehensive genomic profiling in advanced non-small cell lung cancer: a real-world cohort study in Finland. Cancer Med 2025 (Oct). | https://researchportal.tuni.fi/en/publications/comprehensive-genomic-profiling-in-advanced-non-small-cell-lung-c/ | abstract | 45 % actionable alterations, Finland |
| BAILEY2017 | Bailey SER, Ukoumunne OC, Shephard EA, Hamilton W. Clinical relevance of thrombocytosis in primary care: a prospective cohort study of cancer incidence using English electronic medical records and cancer registry data. Br J Gen Pract 2017;67(659):e405-e413. | https://bjgp.org/content/early/2017/05/22/bjgp17X691109.full.pdf | full_text (partial) | thrombocytosis prevalence 1.5 to 2.2 %, 573/31,261 lung cancers, 1-year any-cancer PPV 11.6 % men / 6.2 % women (the PPVs were read in the GPNotebook summary https://gpnotebook.com/pages/haematology/high-platelet-count-and-cancer-risk) |
| CHEN2021 | Chen C, Song Z, Wang W, Zhou J. Baseline anemia and anemia grade are independent prognostic factors for stage IV non-small cell lung cancer. Mol Clin Oncol 2021;14:59. | https://www.spandidos-publications.com/10.3892/mco.2021.2221 | full_text | anaemia 32.1 %, mean Hb 123.3 g/L |
| CHAN2020 | Chan VWQ, Henry MT, Kennedy MP. Hyponatremia and hypercalcemia: a study of a large cohort of patients with lung cancer. Transl Cancer Res 2020;9(1):222-230. | https://tcr.amegroups.org/article/view/35140/html | full_text | hypercalcaemia 7.1 %, hyponatraemia 31.6 % |
| LEE2016 | Lee DS, Park KR, Kim SJ, et al. Serum lactate dehydrogenase levels at presentation in stage IV non-small cell lung cancer: predictive value of metastases and relation to survival outcomes. Tumour Biol 2016;37(1):619-625. | https://www.springermedizin.de/serum-lactate-dehydrogenase-levels-at-presentation-in-stage-iv-n/9259812 | abstract | LDH elevated 56.9 %, median 477 IU/L |
| SCIREP2017 | The risk factors of bone metastases in patients with lung cancer. Sci Rep, August 2017 (authors not shown on the page read). | https://doaj.org/article/fd2913af340e434ca17613f477908a66 | abstract | bone metastasis 23.9 %; ALP sens 41.3 %, spec 77.1 % |
| YE2025 | Ye H, Zhang Q. Diagnosis of bone metastasis in patients with non-small cell lung cancer by combined detection of CEA, CYFRA21-1, and ALP. Vojnosanit Pregl 2025;82(9):551-557. | https://www.vsp.mod.gov.rs/pdf_clanci/vsp271/01_vsp_9_55866_25_551_557_1758886286.pdf | full_text | ALP means, sens 22.1 %, spec 90.0 % |
| MINNAARD2016 | Minnaard MC, de Groot JAH, Hopstaken RM, et al. The added value of C-reactive protein measurement in diagnosing pneumonia in primary care: a meta-analysis of individual patient data. CMAJ 2016. | https://www.cmaj.ca/content/early/2016/09/19/cmaj.151163.full.pdf | full_text | CRP medians by study, model accuracy |
| GRAFFELMAN2007 | Graffelman AW, et al. J Fam Pract 2007;56(6):465-470 (read in a summary at https://www.mdedge.com/content/can-history-and-exam-alone-reliably-predict-pneumonia). | https://www.mdedge.com/content/can-history-and-exam-alone-reliably-predict-pneumonia | secondary | history and exam alone do not predict pneumonia; CRP model PPV 47 % |
| VANDENBEMT2014 | van den Bemt L, Wouters BCW, Grootens J, et al. Diagnostic accuracy of pre-bronchodilator FEV1/FEV6 from microspirometry to detect airflow obstruction in primary care. NPJ Prim Care Respir Med 2014;24:14033. | https://pmc.ncbi.nlm.nih.gov/articles/PMC4373403 | abstract | microspirometry sens 0.932 / spec 0.850 |
| HAUGHNEY2014 | Haughney J, Gruffydd-Jones K, Roberts J, Lee AJ, Hardwell A, McGarvey L. The distribution of COPD in UK general practice using the new GOLD classification. Eur Respir J 2014;43(4):993-1002. | https://abdn.elsevierpure.com/en/publications/the-distribution-of-copd-in-uk-general-practice-using-the-new-gol | abstract | GOLD stage shares |
| BROCKELSBY_PRENDECKI | Brockelsby C, Maconachie R, Navani N, Prendecki R, et al. A real-world, multi-centre study of brain metastasis prevalence, its impact on treatment, and re-modelling of the NICE lung cancer brain imaging economic analysis (year not shown on the copy read; about 2022). | https://discovery.ucl.ac.uk/id/eprint/10176080/1/Prendecki_Brain imaging in lung cancer staging.pdf | full_text | asymptomatic brain metastasis 2.1 to 6.2 % |
| ALHUSAINI2023 | Alhusaini S, Lanman TA, Ko RB, et al. Real-world risk of brain metastases in stage III non-small cell lung cancer in the era of PET and MRI staging. Front Oncol 2023;13:1139940. | https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2023.1139940/full | full_text | 2-year brain metastasis incidence 17 % |
| PAAPPANEN2025 | Paappanen V, Tikka J, Jukkola A, et al. Outcome of lung cancer surgery and proportion of lung cancer patients eligible for surgery in five Finnish hospitals in 2018, real world study. Acta Oncol 2025;64:909-916. | https://medicaljournalssweden.se/actaoncologica/article/download/43398/50813 | full_text | Finnish stage distribution (NSCLC), operability |
| SOLBERG2022 | Solberg S, Nilssen Y, Brustugun OT, et al. Concordance between clinical and pathology TNM-staging in lung cancer. Lung Cancer 2022;171:65-69. | https://munin.uit.no/bitstream/10037/27539/2/article.pdf | full_text | Norwegian surgical cohort nodal status, stage |
| LEE2006 | Computed tomographic screening for lung cancer: the relationship of disease stage to tumor size. Arch Intern Med 2006;166(3):321-325 (authors not on the page read). | https://pubmed.ncbi.nlm.nih.gov/16476872/ | abstract | N0M0 share by tumour size in screening |
| YANG2010 | Yang F, Chen H, Xiang J, et al. Relationship between tumor size and disease stage in non-small cell lung cancer. BMC Cancer 2010;10:474. | https://www.springermedizin.de/relationship-between-tumor-size-and-disease-stage-in-non-small-c/9460906 | full_text | N0M0 share and N1/N2 share by size, Shanghai |

## 8. Process steps listed as tests in `scenarios/finland_lung.yaml` (C2 rule 5)

Judged from the entries read in the file (ids and `kind`):

| scenario id | scenario kind | classification | catalogue handling |
|---|---|---|---|
| nurse_assessment, gp_assessment, gp_assessment_after_nurse | visit | The encounter is a medical test only through history and examination (rule 6); its `p_positive` ("orders a chest X-ray") is a clinician judgement | `history` and `examination` tests (reveal symptoms and signs); the order decision becomes a decision node (D41) |
| gp_second_look | visit | clinician judgement on a negative film | decision node, not a test |
| symptoms_persist | admin | patient behaviour (does the patient come back) | `behaviour.yaml`, not a test |
| gp_represent | visit | patient behaviour plus a GP referral decision | behaviour plus decision node |
| gp_referral_letter, referral_triage | admin | administrative steps | flowchart steps only |
| specialist_visit | visit | specialist judgement ("orders CT") | history/exam test plus decision node |
| tumour_board | admin/batch | multidisciplinary meeting | process step |
| treatment_booking | process | booking | process step |
| chest_ct, bronchoscopy, ttnb, pet_ct | test | medical tests | `tests.yaml` as in sections 1 to 3. Note: the file's `p_positive` for chest_ct per condition is a derived assumption; the sourced proxy is section 2 |
| chest_xray | test | medical test | `tests.yaml` |

## 9. Could not source (assumption suggestions)

| item | why not found | suggested assumption and reasoning | grade |
|---|---|---|---|
| Chest X-ray sensitivity by nodule size and location | The one relevant retrospective paper gave only the size of missed lesions (mean 14.3 mm) and location (68 % upper zones); a PMC article on nodule detection was blocked by a captcha | Assume sensitivity rises with size: about 0.5 under 10 mm, 0.7 for 10 to 20 mm, 0.85 above 20 mm, scaled so that the mean over the cancer size mix equals BRADLEY2021 0.754. Mark as assumption and include the upper-zone effect only if the converter wants a location variable | assumption |
| Brain MRI sensitivity / specificity for brain metastases | Number not given in the opened sources | assume sensitivity 0.95, specificity 0.95 (clinical MRI is the reference standard in practice; CT is slightly lower per the "relatively modest" statement) | assumption |
| Cost in euros (any test) | No Finnish price list opened. The scenario file already holds placeholder costs (CT 250, bronchoscopy 1,200, TTNB 900, PET-CT 1,500) | Keep the scenario values labelled assumption | assumption |
| History and examination: how often a present symptom is elicited | Nothing published found in the searches done. Related finding: history and exam alone do not reliably predict pneumonia (GRAFFELMAN2007), which is a different question | Assume 0.85 for a present symptom asked about in a structured history and 0.70 for an unprompted symptom (recall and omission), 0.60 for a physical sign such as clubbing that is looked for. Mark as assumption and flag as a modelling choice | assumption |
| Full spirometry accuracy and the FEV1 % predicted distribution in COPD (median, p10, p90) | Only stage shares (HAUGHNEY2014) and a microspirometry proxy found; a PMC article with FEV1 means was blocked | Use the GOLD 2007 stage shares and draw within stage bands (stage II 50 to 79 %, III 30 to 49 %, IV below 30 %, I 80 % or over, from the standard GOLD definition, which I did not read on a page this session). Treat full spirometry as exact for airflow obstruction | assumption |
| CRP in pneumonia (median, p10/p90) vs other causes | Only study-level medians in mixed populations (MINNAARD2016) | Pneumonia CRP lognormal median about 60 mg/L, p90 about 200 mg/L (anchored on the 43 % pneumonia emergency study, median 96 with IQR 20 to 258, and on the 20 % general-practice study, median 50); non-pneumonia primary care lognormal median 8 mg/L, p90 40 mg/L (anchored on 7 and 14 mg/L medians at 5 to 13 % pneumonia). Lung cancer: no CRP distribution found, assume as non-pneumonia with a heavier tail | assumption |
| Haemoglobin, ALP, LDH in lung cancer at all stages and for the other conditions | Only stage IV or bone-metastasis cohorts (China, Korea) | Draw from the normal reference interval for non-cancer conditions; for lung cancer use CHEN2021 mean and SD for stage IV and shrink the anaemia share to about 0.15 to 0.20 for stages I to III (a modelling choice, not sourced) | assumption |
| Lung-cancer-specific PPV of thrombocytosis by sex and age | Not on any page opened (only the any-cancer PPV and the 573/31,261 count) | Use 0.018 (573/31,261) as the share of lung cancer among those with thrombocytosis, with the caveat that follow-up window is unknown | B, derived |
| Platelet distribution in lung cancer vs others (the thrombocytosis share in lung cancer) | Not found | Assume 0.30 of lung cancers have thrombocytosis at diagnosis, 0.02 of others (the 0.02 is from the 1.5 to 2.2 % general figure) | assumption |
| Lung cancer lesion size and share with distant spread in a presenting Finnish population | Only surgical and screening cohorts | Draw sizes from lognormal median 30 mm, p10 12 mm, p90 70 mm (assumption consistent with the surgical means of 37 to 46 mm and the screening smaller sizes); distant spread from 1 minus the 39.5 % early-stage share is an upper bound (0.605 for IIIB, IV or unstaged) | assumption |
| Share of lung cancers with enlarged mediastinal nodes at diagnosis | No population figure opened; carried GELBERG2014 gives nodal disease prevalence of about 30 % among those staged | Use 0.30 (carried) as the share with nodal disease among those staged, and 0.40 among the whole presenting population as a rough bound from the N0M0 shares by size (0.55 to 0.9) | assumption |
| Pneumothorax after transbronchial biopsy specifically; non-diagnostic rate of bronchoscopy | STAHL2015 does not give it | Keep the assumptions in the file | assumption |
| Molecular panel turnaround in Finland | HORMALAINEN2025 does not report it | Lognormal median 10 days from tissue to report, p90 21, bracketed by the Danish in-house 4 working days and "several weeks" for outsourced testing | assumption |

## 10. Honest summary of coverage

- Tests with a source now: chest X-ray (carried), low-dose CT (carried), diagnostic CT (proxy), PET-CT (carried and updated),
  EBUS and mediastinal staging (carried), bronchoscopy (carried plus complications), TTNB (carried plus pooled
  complications), sputum cytology, histology report time, molecular panel time.
- Weak or missing: structured history, physical examination, spirometry accuracy, brain MRI accuracy, full lab
  distributions by condition, cost, Finnish turnaround for molecular tests.
- Time stopped at the budget; the PMC and some publisher pages could not be opened (captcha or allowlist), which
  is why several items rest on abstracts or summaries.

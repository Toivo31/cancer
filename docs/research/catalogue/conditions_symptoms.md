# Research note WP-C2-R1: conditions, prevalence among presenters, symptoms and signs

Package: `docs/plan/packages/C2/WP-C2-R1-research-conditions-symptoms.md`. Written 2026-11-14 by a research agent
(branch `w2/research-cs`). Feeds `conditions.yaml` and the symptom/sign part of `variables.yaml` of the catalogue
`lung-primary-care`. Status: DRAFT, not clinically reviewed.

How to read this note

- Every number below comes from a page opened in this session (WebFetch). Pages were read through a summarising
  tool, not as raw PDFs, so a number can carry an extraction error. Where a source looked internally inconsistent
  the note says so. A clinician or the converter should re-check any number that matters against the cited page.
- Grades follow C2 "Rules of the format": A = systematic review or large study in a comparable population;
  B = single study or a related but different population; C = guideline text, expert statement or derived from another
  number; `assumption` = ours. A grade drops by one when the population differs from the catalogue setting
  (adults contacting Finnish primary care with chest or general symptoms); that has already been applied in the
  `grade` column and explained in `note`.
- Ids in the `source` column are existing ids from `params/sources.yaml` or proposed ids listed under "New sources".
- Ranges: `low`/`high` are the source's own confidence interval or range unless the note says otherwise.
- Almost nothing here is Finnish primary care data. The Finnish items are the national lung cancer programme, a
  Tampere hospital cohort, a five-hospital Finnish cohort, THL smoking statistics (via a secondary copy) and ECDC TB
  notifications. UK primary care carries the symptom evidence.

## 1. Starting point (what exists today)

- `scenarios/finland_lung.yaml` has seven conditions with prevalence among chest-symptom presenters:
  `lung_cancer_site` 0.005 (BRADLEY/KOO derived), `lung_cancer_nonspec` 0.011, `pneumonia` 0.17 (assumption),
  `copd_exacerbation` 0.14 (assumption), `benign_nodule` 0.03 (assumption), `other_benign` 0.30 (assumption),
  `self_limiting` 0.344 (assumption). Tumour location central 0.35 / peripheral 0.65 (assumption). A group split
  `site_specific` (about 16% of presenters, about 31% of cancers) versus `non_specific`.
- `params/finland.yaml` has: stage I 17% (KHALIFE2025), stage IV 59% in a single centre (IHE2026), 12-month cancer risk
  after haemoptysis 3.1% and after dyspnoea 0.7% (KOO2023), 1.3% in symptomatic over-50s with a self-requested CXR
  (BRADLEY2021), single symptoms other than haemoptysis below 1% (BRADLEY2021), 2,913 cases a year (GLOBOCAN_FIN).
- No smoking status, no symptoms or signs by condition, no histology and no co-occurrence exist anywhere yet.
- The values carried over from `params/finland.yaml` and not re-opened in this session (stage I 17%) are listed
  only in section 8 for comparison and are not counted as sourced by this note.

## 2. Conditions and prevalence among presenters (K3)

Setting for all rows: adults contacting primary care with chest or general symptoms. The published denominators
are all different (acute cough, dyspnoea, haemoptysis, self-referred X-ray, chronic cough referrals), so no single
published table gives the seven or ten shares we need. Rows below give what each denominator supports; the
"derivation" rows combine them and are grade C at best.

### 2a. Lung cancer among presenters

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| lc_risk_12m_new_haemoptysis | 0.031 | | | fraction | KOO2023 | English primary care (CPRD), age 30+, 8,120 new haemoptysis presentations, 253 lung cancers within 12 months | A | Re-read this session (UCL Discovery full text). 3.6% when imaged within 14 days, 2.7% when not (143 and 110 cases); the imaged group differs by selection, not use as a causal contrast |
| lc_risk_12m_new_dyspnoea | 0.007 | | | fraction | KOO2023 | English primary care, age 30+, 162,161 new dyspnoea presentations, 1,103 cancers within 12 months | A | 1.1% if imaged within 14 days (249 cases), 0.6% if not (854). Same caveat |
| lc_risk_12m_dyspnoea_or_haemoptysis_combined | 0.0080 | | | fraction | KOO2023 | Same two cohorts pooled: 1,356 cancers over 170,281 presentations | C | DERIVED by us: (1,103+253)/(162,161+8,120). Overlap between the two cohorts, if any, is not stated in the page we read. Closest published proxy to "chest-symptom presenter" |
| lc_risk_12m_symptomatic_over50_selfreferred_cxr | 0.013 | 0.011 | 0.015 | fraction | BRADLEY2021 | Leeds, 8,996 symptomatic people over 50 who self-requested a chest X-ray, 114 cancers in 1 year | B | The CI is NOT in the page; low/high are our rough binomial interval (114/8,996), so grade `assumption` for the bounds. 2-year risk 154 (1.7%). Self-referred, not GP-presenters |
| lc_risk_2y_symptomatic_over50_selfreferred_cxr | 0.017 | | | fraction | BRADLEY2021 | Same cohort, 154 cancers within 2 years | B | |
| lc_risk_12m_after_negative_cxr | 0.0035 | 0.0022 | 0.0048 | fraction | BRADLEY2021 | Same cohort, people with a negative X-ray | B | Observed; adjusted 0.27% (0.13-0.55). 28 of 114 one-year cancers (24.6%) had a negative film |
| lc_share_of_presenters_current_scenario_check | 0.016 | | | fraction | assumption | Scenario value | assumption | See section 8: the published proxies (0.8% to 1.3%) are lower than the scenario's 1.6% unless the catalogue population is restricted to older smokers or alarm-symptom presenters |

### 2b. Stage, histology and location of lung cancer

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| lc_stage_iv_share_finland_tampere | 0.59 | | | fraction | AHVONEN2023 | Tampere University Hospital, all lung cancers 2007-2019, n=3,041 | B | "About 59%" in both sub-periods, no change over time. Single centre (matches IHE2026's single-centre figure). Stage I-III split not available from the page |
| lc_advanced_stage_share_finland_programme | 0.675 | 0.65 | 0.70 | fraction | FILHA2026 | Finnish national lung cancer programme 2026-2035 (section 1.1, undated) | C | Statement "65-70% found at a spread (advanced) stage". Programme text, no denominator or year given. Midpoint is ours |
| lc_stage_i_share_caper_exeter | 0.126 | | | fraction | ADES2014 | Exeter 1998-2002, 247 cases (31 stage I) | B | DERIVED 31/247 from Table 1. Old, UK. Stage IV (168/247 = 68%) includes missing stage, so it overstates true IV |
| lc_stage_distribution_secondary_care_referrals_uk | I-II 0.318; III 0.261; IV 0.412 | | | fraction | WALTER2015 | 153 lung cancers among 963 adults referred with suspected lung cancer to 5 hospitals in East and North East England, 2010-2012 | B | Stage IA 9.8, IB 9.2, IIA 7.2, IIB 5.2, IIIA 13.7, IIIB 12.4, IV 41.2 (%); 1.3% unstaged. III derived by us (21+19)/153. A referral cohort, so earlier than the whole population is not guaranteed |
| lc_stage_i_share_finland | 0.17 | | | fraction | KHALIFE2025 | Finland | (carried over) | Taken from `params/finland.yaml`; not re-opened in this session, so not counted as sourced here |
| lc_nsclc_share | >0.80 | 0.80 | | fraction | FILHA2026 | Finnish national programme, Table 1 | C | Programme text, no data year |
| lc_sclc_share | 0.175 | 0.15 | 0.20 | fraction | FILHA2026 | Finnish national programme, Table 1 | C | Reads "15-20%". Single-centre Korean series: 15.3% (KOSIN2014), a consistent second figure |
| lc_adenocarcinoma_share_of_nsclc_programme | 0.55 | 0.50 | 0.60 | fraction | FILHA2026 | Finnish national programme, Table 1 | C | The summary we read lists adenocarcinoma 50-60%, squamous about 40%, large cell 5-10%, which sum above 100%; the denominator and the table layout are unclear. Check the table before use |
| lc_histology_resectable_nsclc_finland | adeno 0.487; squamous 0.416; carcinoid 0.032; other 0.065 | | | fraction | PAAPPANEN2025 | 156 potentially operable NSCLC (stage I-IIIA) at five Finnish hospitals, diagnosed 2018 (histology n=154) | B | Operable subset only, so squamous/adeno proportions are not those of all lung cancers |
| lc_location_peripheral_share | 0.623 | | | fraction | KOSIN2014 | 1,139 lung cancer patients having bronchoscopy at one Korean university hospital, 2000-2010 | C | Central = 0.377 (derived). Peripheral share rose 49.7 -> 63.7 -> 73.7% over three time blocks. Bronchoscopy population, not primary-care presenters; Korean. Adenocarcinoma 81.3% peripheral; squamous 59% central; SCLC 56.9% peripheral |
| lc_location_central_share_nordic | not found | | | | assumption | | assumption | Scenario value 0.35/0.65 is close to the Korean series; keep, grade C at best |

### 2c. Look-alike conditions (share among presenters or among symptom cohorts)

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| pneumonia_share_acute_cough | 0.05 | | | fraction | VANVUGT2012 | GRACE: 2,823 adults, first GP consultation for acute cough of 28 days or less, 16 primary care networks in 12 European countries; pneumonia on chest radiograph in 140 | A | Radiograph-defined. Acute-cough presenters only (not all chest symptoms). Radiograph normal 70%; acute bronchitis 8% |
| pneumonia_share_acute_cough_prior | 0.05 | | | fraction | HECKERLING_UW | Adults with cough seen in primary care (cited by a UW teaching page) | C | Secondary page; consistent with VANVUGT2012 |
| pneumonia_infiltrate_share_lrti_trial | 0.03 | | | fraction | TEEPE2016 | Placebo arm of GRACE-10 amoxicillin trial, 834 adults with acute cough/LRTI, suspected pneumonia excluded | B | 26 of 834 had infiltrates. Lower bound because suspected pneumonia was excluded |
| nodule_or_shadow_share_acute_cough_cxr | 0.018 | | | fraction | VANVUGT2012 | Same 2,823 GRACE adults | B | "Suspected nodules or shadows" 1.8%; clinically relevant incidental findings 3%; incidental findings of any kind 19% (0 to 25% across networks). Includes undiagnosed cancers, so benign_nodule is somewhat lower |
| copd_new_diagnosis_after_first_breathlessness | 0.120 | | | fraction | CHEN2020 | CPRD, 75,698 adults with a first recorded breathlessness symptom, new COPD diagnosis over follow-up (1997-2014) | B | Mostly after 6 months (9,111 total, 2,970 within 0-6 months = 3.9%). NOT a share at presentation. Heart failure is not separate (inside IHD) |
| asthma_new_diagnosis_after_first_breathlessness | 0.150 | | | fraction | CHEN2020 | Same cohort | B | 4,430 within 0-6 months (5.9%); 11,355 total |
| ihd_incl_heart_failure_new_diagnosis_after_first_breathlessness | 0.173 | | | fraction | CHEN2020 | Same cohort | B | 4,430 within 0-6 months; 13,110 total. 35.4% received at least one of the three diagnoses; patients can be in more than one row |
| chronic_cough_cause_asthma | 0.287 | | | fraction | TURNER2016 | 266 GP referrals to a London hospital cough clinic, 2012-2014, with final diagnoses | C | Referred, selected cases, not primary-care presenters; chest X-ray normal. Grade C |
| chronic_cough_cause_gord | 0.215 | | | fraction | TURNER2016 | Same | C | |
| chronic_cough_cause_ace_inhibitor | 0.142 | | | fraction | TURNER2016 | Same | C | |
| chronic_cough_cause_unexplained | 0.119 | | | fraction | TURNER2016 | Same | C | |
| chronic_cough_cause_post_infective | 0.11 | | | fraction | TURNER2016 | Same | C | 30 patients; the percentage is our calculation (30/266) |
| chronic_cough_cause_upper_airway | 0.06 | | | fraction | TURNER2016 | Same | C | 17 patients; our calculation |
| chronic_cough_cause_malignancy | <0.01 | | | fraction | TURNER2016 | Same | C | 2 patients, neither a lung cancer. Selected by a normal X-ray, so not a lung-cancer share |
| tb_notification_rate_finland | 3.3 | | | per 100,000 per year | ECDC_TB2024 | Finland 2024, 184 notified cases | A | National surveillance. 67.9% pulmonary (125 cases); 45.7% (84) of foreign origin; new and relapse rate 3.2 |
| tb_share_of_presenters_county_derived | 0.0007 | 0.0005 | 0.0010 | fraction | ECDC_TB2024 | Derived for a 500,000 county with 44 presenters a day (scenario arrivals, itself an assumption) | C | Derivation: 3.3/100,000 x 500,000 = 16.5 cases a year, 67.9% pulmonary = 11; presenters 44 x 365 = 16,060; 11/16,060 = 0.07%. Not every TB case passes through this stream and the stream size is an assumption, so a range 0.05-0.10% is given. Say "rare in Finland" in the catalogue |
| viral_self_limiting_share | not found | | | | assumption | | assumption | See section 9. Acute bronchitis 8% and normal radiograph 70% of acute-cough presenters (VANVUGT2012) are the closest hard numbers; the remainder of the cough presenters recover without a specific diagnosis |
| reflux_postinfectious_cough_share | not found | | | | assumption | | assumption | See section 9. Chronic-cough causes above are conditional on referral to a cough clinic |
| heart_failure_share_dyspnoea_primary_care | not found | | | | assumption | | assumption | The HTA review (MANT2009) page we read gave no prevalence. Use CHEN2020 IHD 17.3% as an upper context number only |

### 2d. Derivation of the seven scenario conditions' shares

No published source gives shares across all of: cancer, pneumonia, COPD exacerbation, benign nodule, other benign, self-limiting among Finnish chest-symptom presenters. What can be said from the opened sources:

- Lung cancer is 0.7% to 3.1% depending on the entry symptom (KOO2023), 0.8% pooled over dyspnoea and haemoptysis,
  1.3% among symptomatic over-50s with a self-requested X-ray (BRADLEY2021). A catalogue figure between 0.8% and
  1.6% is defensible; 1.6% sits at the upper edge.
- Pneumonia is about 5% of acute-cough presenters with a radiograph (VANVUGT2012), 3% when suspected pneumonia is
  excluded (TEEPE2016). The scenario's 17% is more than three times higher.
- The scenario's conditions are not mutually exclusive in reality (COPD with pneumonia with cancer). Section 7 gives
  two co-occurrence numbers.

## 3. Smoking modifiers (for `prevalence.by`)

### 3a. Relative risk of lung cancer by smoking status

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| lc_rr_current_vs_never | 8.43 | 7.63 | 9.31 | relative risk | LEE2012 | Random-effects pooled RR (RR and OR combined), 287 epidemiological studies published before 2000, mostly case-control; Scandinavia 9.4% of principal studies | A | Older studies; RR is likely higher for squamous/small cell and lower for adenocarcinoma: squamous 16.91 (13.14-21.76), adenocarcinoma 4.21 (3.32-5.34) |
| lc_rr_former_vs_never | 4.30 | 3.93 | 4.71 | relative risk | LEE2012 | Same | A | Does not distinguish years since quitting. Ever smokers 5.50 (5.07-5.96) |
| lc_hr_exsmoker_vs_never_women | 1.84 | 1.60 | 2.13 | hazard ratio | HIPPISLEYCOX2015 | QResearch, English general practice, 4.94 million adults 25-84, 32,187 incident lung cancers (10-year risk models) | A | Much lower than LEE2012 for ex-smokers; the register records "ex-smoker" without cessation time and was derived in a population where most smoking is current or recent |
| lc_hr_exsmoker_vs_never_men | 2.37 | 2.04 | 2.76 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_light_smoker_1_9_per_day_women | 5.67 | 5.08 | 6.33 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_light_smoker_1_9_per_day_men | 5.93 | 5.19 | 6.78 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_moderate_smoker_10_19_per_day_women | 6.57 | 5.84 | 7.40 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_moderate_smoker_10_19_per_day_men | 7.13 | 6.15 | 8.27 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_heavy_smoker_20plus_per_day_women | 11.02 | 9.84 | 12.33 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_heavy_smoker_20plus_per_day_men | 10.24 | 8.94 | 11.74 | hazard ratio | HIPPISLEYCOX2015 | Same | A | |
| lc_hr_copd_vs_none | 1.97 women; 1.92 men | 1.76 | 2.15 | hazard ratio | HIPPISLEYCOX2015 | Same | A | Adjusted for smoking. Asthma 1.33 women / 1.18 men; family history 1.32 / 1.28; asbestos men 1.85 |
| lc_share_never_smokers_among_cases_finland | 0.125 | 0.10 | 0.15 | fraction | FILHA2026 | Finnish national programme (section 1.1): "10-15% of lung cancers occur in never-smokers, mostly women" | C | Programme text. Smoking causes 80-90% of cases (same text) |
| lc_smoking_status_resectable_nsclc_finland | current 0.311; ex 0.517; never 0.172 | | | fraction | PAAPPANEN2025 | 151 of 156 operable NSCLC patients with known status, five Finnish hospitals, 2018 | B | Operable subset; shows that ex-smokers are the largest group among Finnish cases |
| lc_smoking_hist_prevalence_note | how to use | | | | assumption | | assumption | To keep the overall presenter prevalence P unchanged while applying multipliers: P(never) = P / (n + f*r_f + c*r_c), where n, f, c are the shares of never, former and current smokers among presenters and r_f, r_c the relative risks. Use r_c about 8 and r_f about 2 to 4 as a range; do not stack with age effects without checking the product |

### 3b. Smoking-status distribution of Finnish adults (THL)

Opened: ASH Finland PDF "Tupakkatilasto 2023" (a secondary copy that reproduces THL Tilastoraportti 55/2024, data year
2022, THL Terve Suomi survey) and the ASH Finland smoking page (2024 figure, source not named). The THL pages
themselves were not reachable, so these rows are grade C.

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| fin_daily_smokers_men_20_64 | 0.12 | | | fraction | THL_TUPAKKA2022 | Finland 2022, Terve Suomi survey, men 20-64 | C | 20-34: 9%, 35-44: 14%, 45-54: 12%, 55-64: 14% |
| fin_daily_smokers_women_20_64 | 0.11 | | | fraction | THL_TUPAKKA2022 | Same, women | C | 20-34: 9%, 35-44: 12%, 45-54: 11%, 55-64: 12% |
| fin_daily_smokers_men_65_84 | 0.09 | | | fraction | THL_TUPAKKA2022 | Same, men 65-84 | C | |
| fin_daily_smokers_women_65_84 | 0.05 | | | fraction | THL_TUPAKKA2022 | Same, women 65-84 | C | |
| fin_never_smokers_men_20_64 | 0.33 | | | fraction | THL_TUPAKKA2022 | Same | C | |
| fin_never_smokers_women_20_64 | 0.43 | | | fraction | THL_TUPAKKA2022 | Same | C | |
| fin_never_smokers_men_65_84 | 0.28 | | | fraction | THL_TUPAKKA2022 | Same | C | |
| fin_never_smokers_women_65_84 | 0.46 | | | fraction | THL_TUPAKKA2022 | Same | C | |
| fin_daily_smokers_20_64_2024 | 0.10 | | | fraction | ASHFIN_2024 | Finland 2024, adults 20-64: men 11%, women 9% | C | Source of the 2024 figure not named on the page |
| fin_former_smokers_share | not found | | | | assumption | | assumption | Not in the page we read. Derived upper range: former plus occasional = 1 - never - daily = about 55% for men 20-64, about 46% for women 20-64 (our subtraction; occasional smokers are inside it). Suggest the catalogue treat "former" as an assumption until THL's own table is read |
| fin_smoking_data_inconsistency_flag | see note | | | | | | | The same PDF, as we read it, also lists daily smoking in adults 20+ as 18% (men) and 11% (women) and "daily or occasional" 30% / 19%, which does not fit the 20-64 and 65-84 numbers above (12%/9%). The 20+ rows were not used. A second reading of the THL table is needed |

## 4. Lung cancer: symptoms and signs (K4, part 1)

### 4a. Frequency among lung cancer cases at or before presentation

Two cohorts were opened in full: CAPER (Exeter, GP records, symptom ever recorded in the 2 years before diagnosis,
compared with matched controls) and Walter 2015 (English patients referred to hospital with suspected lung cancer,
patient-reported symptoms). They measure different things and are both UK. The "controls" are age-sex-practice
matched population controls over 2 years of records, not symptomatic presenters, so they give a background rate in
non-cancer adults, not the rate among people with a non-cancer chest diagnosis.

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| lc_cough_freq_gp_2y | 0.648 | | | fraction of cases | ADES2014 | CAPER: 247 lung cancers, Exeter GPs 1998-2002, symptom recorded at any time in the 2 years before diagnosis | B | Controls 29.5%. Stage I 54.8, II 64.7, III 61.3, IV 67.3 (stage IV includes missing). HAMILTON2005 gives cough 65% in the same data |
| lc_dyspnoea_freq_gp_2y | 0.563 | | | fraction of cases | ADES2014 | Same | B | Controls 15.5%. Stage I 38.7, II 41.2, III 64.5, IV 59.5. Hamilton: 139/247 (56%) |
| lc_chest_pain_freq_gp_2y | 0.405 | | | fraction of cases | ADES2014 | Same | B | Controls 12.1%. Stage I 35.5, II 47.1, III 38.7, IV 41.1 |
| lc_fatigue_freq_gp_2y | 0.352 | | | fraction of cases | ADES2014 | Same | B | Controls 15.1%. Stage I 41.9, II 11.8, III 35.5, IV 36.3 |
| lc_weight_loss_freq_gp_2y | 0.271 | | | fraction of cases | ADES2014 | Same | B | Controls 4.4%. Stage I 12.9, II 41.2, III 22.6, IV 29.2 |
| lc_appetite_loss_freq_gp_2y | 0.190 | | | fraction of cases | ADES2014 | Same | B | Controls 4.0%. Stage I 12.9, II 17.6, III 25.8, IV 19.0 |
| lc_haemoptysis_freq_gp_2y | 0.202 | | | fraction of cases | ADES2014 | Same | B | Controls 1.5%. Stage I 29.0, II 29.4, III 12.9, IV 19.0. HAMILTON2005: 20% of cases vs 1.5% of controls |
| lc_any_of_fatigue_weightloss_appetite_haemoptysis_gp_2y | 0.648 | | | fraction of cases | ADES2014 | Same | B | Controls 20.4% |
| lc_any_symptom_gp_2y | 0.919 | | | fraction of cases | ADES2014 | Same | B | Controls 47.2%. Stage I 90.3, II 88.2, III 93.5, IV 92.3. So about 8% of cases have no recorded symptom in the 2 years |
| lc_two_symptoms_within_3m_gp | 0.806 | | | fraction of cases | ADES2014 | Same | B | Controls 23.2%. A sensitivity/false-positive pair, not a PPV |
| lc_haemoptysis_freq_referred | 0.216 | | | fraction of cases | WALTER2015 | 153 lung cancers among adults referred with suspected lung cancer, East/North East England 2010-2012; patient-reported at any time | B | First symptom in 4.6%. In people referred without cancer (753): 11.8% |
| lc_cough_freq_referred | 0.562 | | | fraction of cases | WALTER2015 | Same | B | First symptom 39.9% (no-cancer 50.7% "first symptom") |
| lc_breathlessness_freq_referred | 0.412 | | | fraction of cases | WALTER2015 | Same | B | First symptom 26.1% |
| lc_chest_shoulder_pain_freq_referred | 0.353 | | | fraction of cases | WALTER2015 | Same | B | First symptom 15.7% |
| lc_hoarseness_freq_referred | 0.124 | | | fraction of cases | WALTER2015 | Same | B | First symptom 6.5% |
| lc_appetite_loss_freq_referred | 0.222 | | | fraction of cases | WALTER2015 | Same | B | First symptom 11.8% |
| lc_weight_loss_freq_referred | 0.150 | | | fraction of cases | WALTER2015 | Same | B | First symptom 7.2% |
| lc_fatigue_freq_referred | 0.451 | | | fraction of cases | WALTER2015 | Same | B | First symptom 26.1% |
| lc_feeling_different_freq_referred | 0.346 | | | fraction of cases | WALTER2015 | Same | B | First symptom 18.3% |
| lc_chest_infection_as_first_symptom_referred | 0.033 | | | fraction of cases | WALTER2015 | Same | B | 5 of 153 reported "chest infection/respiratory illness" as the first symptom; 0 as an "any time" symptom in the table as we read it, which looks like a coding artefact. Treat as at most a few percent |
| lc_feverish_unwell_freq_referred | 0.046 | | | fraction of cases | WALTER2015 | Same | B | 7 of 153 |
| lc_incidental_radiology_finding_referred | 0.020 | | | fraction of cases | WALTER2015 | Same | B | 3 of 153 as a reported symptom; FILHA2026 states about one quarter of Finnish cases are found in asymptomatic patients (below) |
| lc_asymptomatic_share_finland | 0.25 | | | fraction of cases | FILHA2026 | Finnish national programme: "about one quarter found in asymptomatic patients" (section 1.1) | C | Many early cases are found incidentally on imaging done for other reasons (section 1.3). Differs from ADES2014 (about 8% with no recorded symptom in GP records) because the denominators differ |
| lc_finger_clubbing_freq | 0.33 | | | fraction of cases | CLUBBING1998 | Hospital series, bronchogenic carcinoma, n about 109, new digital index (distal-to-interphalangeal depth ratio above 1.0) | C | The abstract says 33% above 1 and also "30 of 109 (37%)" above 1.05; 30/109 is 28%, so the abstract is inconsistent. Treat as "about one third, 28-37%". COPD 11%, controls 0 of 55. Not primary care; criterion is research-grade, clinical clubbing will be rarer. Hamilton 2005 reports no PPV because numbers were too small |
| lc_neck_nodes_freq | not found | | | | assumption | | assumption | See section 9 |
| lc_abnormal_chest_sounds_freq | not found | | | | assumption | | assumption | See section 9 |
| lc_raised_platelets_freq | 0.14 | | | fraction of cases | HAMILTON2005 | CAPER: 34 of 247 had thrombocytosis, but only 132 cases were tested; 19 of 396 tested controls (5%) | B | Of tested cases 34/132 = 26%, which matches the 26% vs 4.8% quoted in a review (SCHMIDTHANSEN2017). For the catalogue this is a lab variable (WP-C2-R2), listed here because NG12 uses it as a trigger |

### 4b. Positive predictive values and risks for lung cancer by symptom in primary care

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| ppv_haemoptysis_gp_hamilton | 0.024 | | | fraction | HAMILTON2005 | CAPER, Exeter, age 40+, 247 cases and 1,235 controls | B | Overall; 7.1% in patients aged 70+; 17% on a second presentation (as read); 2.0% when combined with cough. CI not in the page text |
| ppv_haemoptysis_gp_jones | 0.075 men; 0.043 women | 0.066 / 0.034 | 0.085 / 0.053 | fraction | JONES2007 | UK GPRD, 762,325 patients aged 15+, 128 practices, 1994-2000; outcome was respiratory tract neoplasm within 3 years (301 cases) | A | Men aged 75-84: 17.1% (13.5-21.1). Not adjusted for smoking. Outcome is "respiratory tract neoplasms", slightly broader than lung cancer |
| ppv_haemoptysis_12m_koo | 0.031 | | | fraction | KOO2023 | See 2a | A | Duplicate of lc_risk_12m_new_haemoptysis |
| ppv_haemoptysis_12m_bradley | 0.029 | | | fraction | BRADLEY2021 | Leeds self-referred CXR over 50 (2-year 3.9%) | B | Below 1% at one year (below 1.5% at two) for every other single symptom studied: cough, dyspnoea, chest pain, weight loss, change in voice |
| ppv_cough_gp_hamilton | 0.0077 | 0.0054 | 0.011 | fraction | HAMILTON2005 | CAPER, cough on a third presentation | B | Single cough presentation lower still. No symptom pair including cough exceeded 2% |
| ppv_dyspnoea_12m_koo | 0.007 | | | fraction | KOO2023 | See 2a | A | Hamilton: below 2%, no exact figure in the page text |
| ppv_chest_pain_weight_loss_fatigue_hamilton | <0.02 | | | fraction | HAMILTON2005 | CAPER | B | Individually below 2%; exact values only in the figure, not in the page text |
| ppv_appetite_loss_age_40_69_hamilton | 0.011 | | | fraction | HAMILTON2005 | CAPER, age 40-69 | B | |
| ppv_thrombocytosis_hamilton | 0.016 | | | fraction | HAMILTON2005 | CAPER overall; 3.0% in patients 40-69 | B | With cough 1.03%, with chest pain 2.17%, with weight loss 6.67% (BRADLEY2021, CIs include 0) |
| ppv_abnormal_spirometry_age_70plus_hamilton | 0.042 | | | fraction | HAMILTON2005 | CAPER, age 70+ | B | |
| ppv_cxr_positive_bradley | 0.0902 | | | fraction | BRADLEY2021 | Leeds, positive chest X-ray | B | Carried in `params/finland.yaml`; value appears in params, not re-read as a table row in this session |
| nice_ng12_ppv_threshold | 0.03 | | | fraction | NICE_NG12_CONTEXT | NICE NG12 guideline context text | C | NG12 uses 3% PPV as the threshold for suspected-cancer-pathway referral and urgent direct-access investigation |
| nice_ng12_lung_rules | see note | | | | NICE_NG12 | NICE NG12 lung and pleural recommendations, age 40+ | C | Refer on suspected-cancer pathway if CXR suggests lung cancer or age 40+ with unexplained haemoptysis. Urgent direct-access CXR if age 40+ with two or more of cough, fatigue, breathlessness, chest pain, weight loss, appetite loss, or with any one of them plus ever-smoking. Consider CXR in age 40+ with persistent or recurrent chest infection, finger clubbing, supraclavicular or persistent cervical nodes, chest signs of lung cancer, or raised platelets. Rule text, not data |
| ppv_any_two_symptoms_3m_ades | see 4a | | | | ADES2014 | | B | Sensitivity 80.6%, controls 23.2% (no PPV given by the source) |
| qresearch_symptom_hazard_ratios_lung | not obtained | | | | | | | The QCancer lung symptom paper (Hippisley-Cox and Coupland, BJGP 2011) could not be opened. The 2015 BMJ Open paper opened here has no symptoms. Listed in section 9 |
| iyen_omofoman_ppv | not obtained | | | | | | | The paper (Thorax 2013) could not be opened; only a systematic review's summary was read (SCHMIDTHANSEN2017: AUC 0.88 for the Iyen-Omofoman tool, THIN data, 12,074 cases). Listed in section 9 |

### 4c. Other CAPER details usable for the catalogue

Stage-specific symptom rates are in ADES2014 Table 1 (copied in 4a). The differences by stage are noisy (stage II has only
17 cases). The catalogue can use the all-case value and a note that stage IV has slightly more dyspnoea (59.5 vs
38.7% in stage I) and weight loss.

## 5. Symptoms and signs of the look-alikes (K4, part 2)

Graded honestly: these are fragments from guideline-level or review-level sources. For several look-alikes no
frequency could be sourced (section 9).

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| pneumonia_fever_lr_plus | 1.7 to 2.1 | | | likelihood ratio positive | METLAY_UW | Adults with suspected pneumonia, cited from Metlay et al. via a University of Washington teaching page | C | LR- 0.59-0.71. Secondary page, authors/year not in the page; the original (JAMA) was not opened |
| pneumonia_chills_lr_plus | 1.3 to 1.7 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.70-0.85 |
| pneumonia_cough_lr_plus | 1.8 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.31; not significant in 2 of the studies. So cough is nearly universal in pneumonia but not specific |
| pneumonia_dyspnoea_lr_plus | 1.4 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.67; not significant in 2 studies |
| pneumonia_tachycardia_over_100_lr_plus | 1.6 to 2.3 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.49-0.73 |
| pneumonia_crackles_lr_plus | 1.6 to 2.7 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.62-0.87. Rales in the right lung: sensitivity 0.54-0.75, specificity 0.39-0.61 across examiners (Wipf, via the same page) |
| pneumonia_rhonchi_lr_plus | 1.4 to 1.5 | | | likelihood ratio positive | METLAY_UW | Same | C | LR- 0.76-0.85 |
| pneumonia_prevalence_prior_cough_primary_care | 0.05 | | | fraction | HECKERLING_UW | Primary care cough | C | Same as in 2c |
| heart_failure_dyspnoea_sensitivity | 0.89 | | | fraction | MANT2009 | HTA systematic review plus individual patient data from 9 studies, primary-care patients with symptoms suggestive of heart failure | A | Specificity 51%. These are accuracy figures for diagnosing heart failure, not symptom frequency; sensitivity is the frequency of the symptom among confirmed HF |
| heart_failure_oedema_sensitivity | 0.53 | | | fraction | MANT2009 | Same | A | Specificity 72% |
| heart_failure_orthopnoea_specificity | 0.89 | | | fraction | MANT2009 | Same | A | Sensitivity not in the abstract |
| heart_failure_lung_crepitations_specificity | 0.81 | | | fraction | MANT2009 | Same | A | |
| heart_failure_added_heart_sounds_sensitivity | 0.11 | | | fraction | MANT2009 | Same | A | Specificity 99% |
| heart_failure_cxr_cardiomegaly_specificity | 0.85 | | | fraction | MANT2009 | Same | A | CXR overall sensitivity 67-68%, specificity 76-83% (WP-C2-R2 territory) |
| copd_exacerbation_definition | see note | | | | NICE_NG114 | NICE COPD guideline NG114 terms | C | Sustained, acute worsening of symptoms beyond daily variation: breathlessness, cough, sputum volume, sputum colour. Qualitative only; no frequencies. A study of exacerbation diaries (EJIOFOR2017) was opened but is an alpha-1 antitrypsin trial in 46 patients and is not usable as a primary-care frequency |
| chronic_cough_cause_distribution | see 2c | | | | TURNER2016 | Cough-clinic referrals | C | Asthma, reflux, ACE inhibitor, post-infective, upper airway |
| acute_cough_radiograph_distribution | normal 0.70; bronchitis 0.08; pneumonia 0.05 | | | fraction | VANVUGT2012 | GRACE adults with acute cough | A | Incidental finding 19%; used for the "no disease found" or self-limiting class in the catalogue |
| lrti_bacterial_share_among_acute_cough | 0.19 | | | fraction | TEEPE2016 | GRACE-10 placebo arm, 834 adults; bacterial LRTI in 162 | B | Current smokers 33% vs 24% in non-bacterial; cough duration before consultation 9 vs 8 days |
| asthma_symptom_frequencies | not found | | | | assumption | | assumption | Section 9 |
| tb_symptom_frequencies | not found | | | | assumption | | assumption | Section 9 |
| benign_nodule_symptom_frequencies | not found | | | | assumption | | assumption | Most nodules are incidental; see VANVUGT2012 1.8% and WALTER2015 incidental finding 2% |
| viral_illness_symptom_frequencies | not found | | | | assumption | | assumption | Section 9 |

## 6. Background symptom rates in people without lung cancer

Useful for the `default` entry of each symptom variable (CAPER matched controls, 1,235 adults aged 40+ in Exeter
general practice records; symptom recorded at any time in 2 years). These are population rates, not rates among
chest-symptom presenters, so they are a floor for the "other conditions" distributions.

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| ctrl_cough_2y | 0.295 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_dyspnoea_2y | 0.155 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_chest_pain_2y | 0.121 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_fatigue_2y | 0.151 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_weight_loss_2y | 0.044 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_appetite_loss_2y | 0.040 | | | fraction | ADES2014 | CAPER controls | B | |
| ctrl_haemoptysis_2y | 0.015 | | | fraction | ADES2014 | CAPER controls | B | HAMILTON2005 gives the same 1.5% |
| ctrl_any_symptom_2y | 0.472 | | | fraction | ADES2014 | CAPER controls | B | |
| walter_no_cancer_haemoptysis | 0.118 | | | fraction | WALTER2015 | 753 referred people without cancer (suspected lung cancer, secondary care) | B | Referral selection raises every symptom rate; usable as the upper bound of a "benign referred" population: weight loss 9.2%, cough "first symptom" 50.7% |

## 7. Co-occurrence (for D40)

| entry | value | low | high | unit | source | population/setting | grade | note |
|---|---|---|---|---|---|---|---|---|
| copd_among_lung_cancer_patients | 0.50 | | | fraction | YOUNG2009 | Patients with lung cancer vs a randomly recruited community control group (matched for age, sex, pack-years, n=602 controls); spirometric COPD | B | Controls 8%, odds ratio 11.6. In a subgroup with spirometry before diagnosis (n=127) 56% rising to 61%. Authors and country not in the abstract page we read (European Respiratory Journal 2009;34:380-6) |
| airflow_limitation_in_lung_cancer_screening_participants | 0.401 | 0.334 | 0.468 | fraction | CHEST2025_AIRFLOW | Pooled spirometry-confirmed airflow limitation in lung cancer screening populations (not cancer patients) | A | Emphysema on CT 45.3% (39.3-51.2); 65.2% of airflow limitation previously unrecognised. Screening participants are high-risk smokers, a different group |
| copd_hazard_ratio_for_lung_cancer | 1.9 to 2.0 | 1.76 | 2.15 | hazard ratio | HIPPISLEYCOX2015 | See 3a | A | Adjusted for smoking |
| pneumonia_before_diagnosis_in_nsclc | 0.023 | | | fraction | WEINBERG2021 | 2,289 NSCLC patients at the University of Michigan Rogel Cancer Center, 2011-2019 | B | Pneumonia recorded before diagnosis; single academic centre; NSCLC only. A weak indicator that "pneumonia first" is a minority route |
| lung_cancer_within_1y_after_pneumonia_in_heavy_smokers | 0.081 | | | fraction | SHEPSHELOVICH2016 | 381 admissions of heavy smokers with community-acquired pneumonia, Rabin Medical Center, Israel, 2007-2011; 31 lung cancers within a year | C | Read from a news summary of the paper (American Journal of Medicine 2016); the summary says 9%, 31/381 is 8.1%. 23.8% with upper-lobe pneumonia. Hospitalised heavy smokers, so far more than primary-care presenters |
| incidental_nodule_among_acute_cough | 0.018 | | | fraction | VANVUGT2012 | GRACE | B | See 2c |

## 8. Comparison with the current scenario

Compared with `scenarios/finland_lung.yaml` and `params/finland.yaml` (not edited).

| item | scenario / params | this note | difference | comment |
|---|---|---|---|---|
| Lung cancer share of presenters | 0.016 (0.005 + 0.011) | 0.008 (dyspnoea+haemoptysis pooled, KOO2023, derived); 0.013 (BRADLEY2021) | scenario about 2x the pooled UK figure, 1.2x BRADLEY | Scenario says "about 260 cancers a year in a large county" which fixes the arrival rate; a lower share needs a higher arrival rate, or a restriction to older presenters. Worth a decision |
| Haemoptysis presenters' cancer risk | 0.031 (note in `lung_cancer_site`) | 0.031 | none | Re-read and confirmed (253/8,120) |
| Dyspnoea presenters' cancer risk | 0.007 | 0.007 | none | Confirmed (1,103/162,161) |
| Pneumonia share of presenters | 0.17 (assumption) | 0.05 (acute-cough presenters, VANVUGT2012); 0.03 when suspected pneumonia excluded | scenario 3.4x higher | Different denominator (the scenario includes all chest symptoms and COPD/heart patients), but 17% is hard to defend from published data |
| COPD exacerbation share | 0.14 (assumption) | no direct share; COPD newly diagnosed in 12.0% of first-breathlessness patients over years (CHEN2020), mostly after 6 months | unknown | Not comparable. Exacerbation among known COPD patients was not sourced |
| Benign nodule | 0.03 (assumption) | 0.018 suspected nodules or shadows in acute-cough presenters with CXR (VANVUGT2012, includes cancers) | scenario about 1.7x higher | Roughly the same order |
| Other benign (asthma, reflux, heart failure, musculoskeletal pain, etc.) | 0.30 | asthma 15%, IHD incl. heart failure 17% (CHEN2020, over follow-up, overlapping); chronic cough causes (TURNER2016) | not comparable | Cannot be converted to a share at presentation without a Finnish primary-care diagnosis table |
| Self-limiting | 0.344 | acute-cough presenters: radiograph normal 70%, bronchitis 8% (VANVUGT2012) | scenario lower for acute cough | Different denominator; the scenario's share depends on how many acute-cough patients are in the stream |
| Alarm-symptom share of cancers | 31% (`site_specific`: haemoptysis, chest signs, hoarseness) | haemoptysis 20.2% (ADES2014), 21.6% (WALTER2015), 19% of combined dyspnoea/haemoptysis cancers (KOO2023, derived); plus hoarseness 12.4% (WALTER2015) | plausible; haemoptysis alone is about 20% | The scenario's 31% needs an overlap argument; the sourced numbers support 20-30% |
| Location | central 0.35 / peripheral 0.65 | 0.377 / 0.623 (KOSIN2014) | 0.03 | Within noise; a Korean bronchoscopy series |
| Stage IV share | 0.59 single centre (IHE2026) | 0.59 (AHVONEN2023, Tampere); 65-70% advanced stage (FILHA2026) | none for IV | Consistent. Stage I 17% (carried over) fits CAPER 12.6% and the 31.8% I-II referral cohort order of magnitude |
| Smoking | not in scenario | RR current 8.4, former 4.3 (LEE2012); QResearch HR 1.8-2.4 ex, 5.7-11 current by intensity | new | Enters `prevalence.by` |
| Histology | not in scenario | NSCLC >80%, SCLC 15-20% (FILHA2026) | new | Adds a condition attribute |
| TB | not in scenario | 3.3 per 100,000, about 0.07% of presenters (derived) | new condition, rare | Keep as a condition with very low prevalence or fold into "other" |

## 9. Could not source (and suggested assumptions)

All suggested values are `assumption` unless said otherwise. The reasoning is in the last column.

| entry | what was missing | suggested value | grade | reasoning |
|---|---|---|---|---|
| presenter_shares_finland | A table of diagnoses among adults presenting with chest symptoms in Finnish (or Nordic) primary care | Keep the scenario shares but cut pneumonia to about 0.05-0.10 and renormalise through `self_limiting` | assumption | Finnish primary-care diagnosis registers (Avohilmo) not found; GRACE gives 5% pneumonia among acute cough |
| copd_exacerbation_share_presenters | Share of chest-symptom presenters who have a COPD exacerbation | 0.05-0.10 | assumption | Not found. COPD is among the three commonest new diagnoses after breathlessness (12%, CHEN2020), but exacerbation is a fraction of those |
| asthma_share_presenters | Share and symptom frequencies | cough 0.8, wheeze 0.7, dyspnoea 0.8 | assumption | Not sourced; clinical knowledge only, to be replaced by a guideline (GINA, Finnish Käypä hoito) |
| heart_failure_share_and_symptoms | Prevalence in dyspnoea presenters; frequencies of cough and breathlessness | use MANT2009 sensitivities for dyspnoea 0.89 and oedema 0.53; prevalence 0.05 | assumption | HTA abstract gives accuracy not prevalence |
| tb_symptom_frequencies | Cough, weight loss, fever, haemoptysis frequencies in pulmonary TB | cough 0.8, weight loss 0.5, fever 0.5, haemoptysis 0.2 | assumption | WHO or ECDC material not opened. Rare in Finland (3.3 per 100,000); low priority |
| benign_nodule_symptoms | Symptoms of benign nodules | mostly asymptomatic; default symptom rates | assumption | Incidental by definition |
| reflux_postinfectious_cough_share | Share of presenters | 0.03-0.08 | assumption | No primary-care series; cough-clinic shares are conditional on referral |
| viral_illness_symptom_frequencies | Fever, cough, chest sounds in self-limiting viral illness | cough 0.9, fever 0.4, abnormal chest sounds 0.1 | assumption | GRACE publications give cohort-level numbers not extracted; no symptom table found |
| lc_neck_nodes_freq | Frequency of palpable supraclavicular or cervical nodes in lung cancer at presentation | 0.05 | assumption | No primary-care figure found; NG12 lists the sign as a trigger only |
| lc_abnormal_chest_sounds_freq | Frequency of abnormal chest sounds in lung cancer | 0.25 | assumption | Hamilton 2005 table not accessible; chest signs were recorded but frequencies were not in the page text |
| lc_finger_clubbing_primary_care | Clinical clubbing frequency (not index-based) | 0.05-0.10 | assumption | The only figure is a research index in a hospital cohort (about one third) |
| lc_fever_frequency | Fever in lung cancer at presentation | 0.05 (WALTER2015 "feverish/unwell" 4.6%) | B | Partial proxy only |
| lc_hoarseness_ppv | PPV of hoarseness | below 1% | assumption | Hamilton 2005: not independently associated with cancer; BRADLEY2021 "change in voice" below 1% |
| iyen_omofoman_2013 | Frequencies and odds ratios from the THIN case-control study | none | | PMC and publisher pages blocked in this session. Only a review's summary was read |
| qcancer_lung_symptoms | Adjusted hazard ratios for symptoms in the QCancer lung algorithm (2011) | none | | The article could not be opened (not on the fetch allowlist) |
| hamilton_2005_table2 | Frequencies for weight loss, chest pain, fatigue, clubbing, chest signs, hoarseness, chest infection | ADES2014 supplies the symptom frequencies from the same CAPER dataset; clubbing and chest signs remain missing | | Only the text, not the table, could be read |
| former_smoker_share_finland | Share of former smokers among Finnish adults and among older adults | men 20-64 about 0.35, women 20-64 about 0.25 | assumption | Not reported in the page read; derived upper ranges in 3b |
| finnish_symptom_data | Any Finnish primary-care symptom frequencies for lung cancer | none | | National programme text lists symptoms qualitatively and says fewer than half of patients with advanced disease had only one or two symptoms |
| nordic_central_peripheral | Share of central vs peripheral tumours in Nordic data | 0.35 central | assumption | Korean bronchoscopy series only |
| smoking_effect_by_condition | Smoking status distribution among pneumonia, COPD and other presenters | current smokers 33% vs 24% in bacterial vs non-bacterial LRTI (TEEPE2016) only | | No other source |
| qcancer_haemoptysis_hr | A recalled QCancer hazard ratio for haemoptysis | not recorded | | Not seen in any opened page, so deliberately not written down |

## 10. New sources (proposed registry entries)

Ids in the style of `params/sources.yaml`. `access`: full_text = we read the text through the fetch tool (may be an
abstract-plus-results page), abstract = abstract only, secondary = seen only via another document or a news summary.
Existing ids reused: BRADLEY2021 (re-read, text and results, tables not extracted), KOO2023 (re-read from a UCL
Discovery full-text copy).

| id | citation | url | year | supports | access |
|---|---|---|---|---|---|
| HAMILTON2005 | Hamilton W, Peters TJ, Round A, Sharp D. Thorax 2005;60(12):1059- (Exeter case-control study, CAPER; title not captured by the fetch) | https://thorax.bmj.com/content/60/12/1059 | 2005 | haemoptysis, cough PPVs; cough 65%, haemoptysis 20%, dyspnoea 56%; thrombocytosis | full_text (text only, tables absent) |
| ADES2014 | Ades AE, Biswas M, Welton NJ, Hamilton W. Symptom lead time distribution in lung cancer: natural history and prospects for early diagnosis. Int J Epidemiol 2014 (doi:10.1093/ije/dyu174) | https://core.ac.uk/download/29027139.pdf | 2014 | symptom frequencies in cases and controls by stage, CAPER dataset | full_text |
| WALTER2015 | Walter FM et al. Symptoms and other factors associated with time to diagnosis and stage of lung cancer: a prospective cohort study. Br J Cancer 2015 (doi:10.1038/bjc.2015.30) | https://link.springer.com/10.1038/bjc.2015.30 | 2015 | symptom frequencies and stage in 153 lung cancers among 963 referred adults. Table read via a Melbourne repository copy (minerva-access.unimelb.edu.au) | full_text |
| JONES2007 | Jones R, Latinovic R, Charlton J, Gulliford MC. Alarm symptoms in early diagnosis of cancer in primary care: cohort study using General Practice Research Database. BMJ 2007;334:1040 | https://www.bmj.com/content/334/7602/1040 | 2007 | haemoptysis PPV for respiratory tract neoplasm in men and women | full_text (age table absent) |
| SCHMIDTHANSEN2017 | Schmidt-Hansen M, Berendse S, Hamilton W, Baldwin DR. Lung cancer in symptomatic patients presenting in primary care: a systematic review of risk prediction tools. Br J Gen Pract 2017;67(659):e396-e404 (title partly from our reading of the page) | https://bjgp.org/content/67/659/e396 | 2017 | review of risk tools; Iyen-Omofoman AUC 0.88; thrombocytosis 26% vs 4.8%; two symptoms in 3 months 80.6% sensitivity | full_text (tables absent) |
| HIPPISLEYCOX2015 | Hippisley-Cox J, Coupland C. Development and validation of risk prediction algorithms to estimate future risk of common cancers in men and women: prospective cohort study. BMJ Open 2015;5:e007825 | https://nottingham-repository.worktribe.com/OutputFile/744023 | 2015 | smoking HR by intensity, COPD, asthma | full_text (first 100k of 124k characters) |
| LEE2012 | Systematic review with meta-analysis of the epidemiological evidence in the 1900s relating smoking to lung cancer (authors not captured). BMC Cancer 2012;12:385 | https://link.springer.com/doi/10.1186/1471-2407-12-385 | 2012 | RR current 8.43, former 4.30, by histology | full_text (first 100k of 647k characters) |
| NICE_NG12 | NICE. Suspected cancer: recognition and referral. NG12, lung and pleural cancer recommendations | https://www.nice.org.uk/guidance/ng12/chapter/recommendations-organised-by-site-of-cancer | 2015, updated | symptom rules for urgent CXR | full_text |
| NICE_NG12_CONTEXT | NICE NG12 context chapter (3% PPV threshold) | https://www.nice.org.uk/guidance/ng12/chapter/Context | 2015 | PPV threshold | full_text |
| NICE_NG114 | NICE NG114 COPD guideline, terms used: definition of exacerbation | https://www.nice.org.uk/guidance/ng114/chapter/terms-used-in-the-guideline | 2018 | exacerbation definition | full_text |
| VANVUGT2012 | van Vugt SF, Broekhuizen L, Zuithoff N, et al. Incidental chest radiographic findings in adult patients with acute cough. Ann Fam Med 2012;10(6):510-515 | https://www.annfammed.org/content/10/6/510.full.pdf | 2012 | pneumonia 5%, bronchitis 8%, normal 70%, nodules/shadows 1.8% among 2,823 acute-cough adults in European primary care | full_text |
| TEEPE2016 | Teepe J, et al. Disease course of lower respiratory tract infection with a bacterial cause. Ann Fam Med 2016;14(6):534-539 | https://www.annfammed.org/content/14/6/534.full.pdf | 2016 | pneumonia infiltrates 3% in GRACE-10 placebo arm; bacterial LRTI 19% | full_text |
| TURNER2016 | Turner RD, Bothamley GH. Chronic cough and a normal chest X-ray: a simple systematic approach to exclude common causes before referral to secondary care. npj Prim Care Respir Med 2016;26:15081 | https://www.nature.com/articles/npjpcrm201581 | 2016 | chronic-cough diagnosis distribution (cough-clinic referrals) | full_text |
| CHEN2020 | Chen Y, Hayward R, Chew-Graham CA, Hubbard R, Croft P, Sims K, Jordan KP. Prognostic value of first-recorded breathlessness for future chronic respiratory and heart disease: a cohort study using a UK national primary care database. Br J Gen Pract 2020;70(693):e264-e273 | https://bjgp.org/content/bjgp/70/693/e264.full.pdf | 2020 | COPD, asthma, IHD diagnoses after first breathlessness | full_text |
| MANT2009 | Mant J, Doust J, Roalfe A, et al. Systematic review and individual patient data meta-analysis of diagnosis of heart failure, with modelling of implications of different diagnostic strategies in primary care. Health Technol Assess 2009;13(32) | https://research.bond.edu.au/en/publications/systematic-review-and-individual-patient-data-meta-analysis-of-di/ | 2009 | symptom and sign sensitivity/specificity for heart failure | abstract |
| METLAY_UW | Metlay JP et al., likelihood ratios for history and exam in community-acquired pneumonia, as tabulated by the University of Washington physical diagnosis pages | https://depts.washington.edu/physdx/pulmonary/evid1.html | n.d. | LR for fever, cough, dyspnoea, crackles | secondary |
| HECKERLING_UW | Heckerling pneumonia prior (about 5% of cough patients), cited on the same UW page | https://depts.washington.edu/physdx/pulmonary/evid1.html | n.d. | pneumonia prior in primary-care cough | secondary |
| YOUNG2009 | COPD prevalence is increased in lung cancer, independent of age, sex and smoking history. Eur Respir J 2009;34(2):380-386 (authors not captured; first author recalled as Young but unverified) | https://pubmed.ncbi.nlm.nih.gov/19196816/ | 2009 | COPD 50% vs 8% | abstract |
| CHEST2025_AIRFLOW | Prevalence of airflow limitation and emphysema in lung cancer screening populations: a systematic review and meta-analysis. Chest 2025;168(1):67-82 (authors not captured) | https://pubmed.ncbi.nlm.nih.gov/40054601/ | 2025 | airflow limitation 40.1% | abstract |
| WEINBERG2021 | Weinberg FD, Zhao L, Chellappa N, Kalemkerian GP, Ramnath N. Characterization of pneumonia and other factors leading to poorer survival across all age groups in patients with non-small cell lung cancer. J Thorac Dis 2021;13(2):986-994 | https://jtd.amegroups.org/article/view/48747/html | 2021 | pneumonia before NSCLC diagnosis 2.3% | full_text |
| SHEPSHELOVICH2016 | Shepshelovich D et al., lung cancer within a year of hospitalisation for community-acquired pneumonia in heavy smokers. Am J Med 2016 (as reported in a news summary) | https://www.news-medical.net/news/20160108/Screening-smokers-with-community-acquired-pneumonia-could-facilitate-early-diagnosis-of-lung-cancer.aspx | 2016 | 31 of 381 lung cancers within a year | secondary |
| FILHA2026 | FILHA (Finnish Lung Health Association; authors not captured). Valtakunnallinen keuhkosyöpäohjelma 2026-2035, preprint 18.5.2026 (authors not captured) | https://www.filha.fi/wp-content/uploads/2026/05/Valtakunnallinen-keuhkosyopaohjelma-2026-2035_180526_preprint.pdf | 2026 | incidence, advanced stage 65-70%, NSCLC/SCLC and subtype shares, never smokers 10-15%, one quarter asymptomatic | full_text (preprint) |
| AHVONEN2023 | Ahvonen J, Luukkaala T, Laitinen T, Jukkola A. Survival with lung cancer in Finland has not improved during 2007-2019. Acta Oncol 2023;62(6):571-578 | https://researchportal.tuni.fi/en/publications/survival-with-lung-cancer-in-finland-has-not-improved-during-2007/ | 2023 | stage IV about 59% at Tampere University Hospital, n=3,041 | abstract |
| PAAPPANEN2025 | Paappanen V, Tikka J, et al. Outcome of lung cancer surgery and proportion of lung cancer patients eligible for surgery in five Finnish hospitals in 2018, real world study. Acta Oncol 2025;64:909-916 (doi:10.2340/1651-226X.2025.43398) | https://medicaljournalssweden.se/actaoncologica/article/download/43398/50813 | 2025 | histology, smoking status and stage in operable NSCLC | full_text |
| KOSIN2014 | Characteristics of peripheral versus central lung cancer since 2000. Kosin Medical Journal (about 2014, as listed by DOAJ; authors not captured) | https://doaj.org/article/863067cb9c164770a4896b18431a913f | 2014 | central/peripheral and histology by location | abstract |
| CLUBBING1998 | Prevalence of digital clubbing in bronchogenic carcinoma by a new digital index. Clin Exp Rheumatol 1998;16(1):21-26 (authors not captured) | https://api-pubmed-ncbi.laibokeji.com/9543557 | 1998 | clubbing about one third | abstract |
| THL_TUPAKKA2022 | THL Tupakkatilasto 2023 (Tilastoraportti 55/2024), data year 2022, Terve Suomi survey, as reproduced in the ASH Finland file | https://suomenash.fi/wp-content/uploads/2025/02/tupakkatilasto-2023.pdf | 2024 | daily and never-smoker shares by sex and age | secondary |
| ASHFIN_2024 | ASH Finland. Smoking in Finland (2024 figures for adults 20-64; source not named) | https://suomenash.fi/en/facts-about-smoking/smoking/ | 2024 | daily smoking 10% | secondary |
| ECDC_TB2024 | ECDC. Tuberculosis country profile Finland 2024 | https://www.ecdc.europa.eu/sites/default/files/documents/Country-profile-Finland-TB-2024.pdf | 2025 | TB notification rate 3.3 per 100,000, 184 cases, 67.9% pulmonary | full_text |
| EJIOFOR2017 | Ejiofor SI, Stolk J, Fernandez P, Stockley RA. Patterns and characterization of COPD exacerbations using real-time data collection. Int J Chron Obstruct Pulmon Dis 2017;12:427-434 | https://www.dovepress.com/patterns-and-characterization-of-copd-exacerbations-using-real-time-da-peer-reviewed-fulltext-article-COPD | 2017 | not used for numbers: alpha-1 antitrypsin trial, 46 patients | full_text |

Pages that could not be opened (for the next reader): PubMed Central pages (reCAPTCHA wall), bjgp.org e715 (QCancer lung),
thorax.bmj.com PDFs and the Iyen-Omofoman paper, thl.fi tobacco pages, the Nottingham eprints pages. A reader with
browser access should open Hamilton 2005 Table 2 and the QCancer lung table first; they are the missing pieces for
chest signs, clubbing, hoarseness and recurrent chest infection.

## 11. Notes for the converter

- Entries whose `value` is "not found" are placeholders; each has a matching row in section 9 with a suggested assumption.
- Counts are in the RELEASE note on the agent channel.
- Several entries are duplicates across sections on purpose (KOO2023 appears in 2a and 4b); use one id per quantity.
- Ades 2014 and Hamilton 2005 are the same patients (CAPER), so do not count them as two independent sources when weighing evidence.

## 12. Catalogue check, 14 Nov night (D59)

A targeted check of the numbers that most shape tonight's cards (the engine now draws every finding from the
catalogue, D58). Changed in `variables.yaml` (old → new):

- Benign nodule, cough: population floor 0.295 → 0.9 (VANVUGT2012, grade C: the condition's prevalence comes from
  GRACE, where every patient had acute cough). About a third of benign-nodule cards had no symptom at all.
- Tuberculosis, lesion size: fell back to the nodule default (median 8 mm, p90 15) → lognormal median 27, p90 42
  (GETNET2019: cavities mean 2.8 cm, SD 1.0; high-burden setting, grade C). At 8 mm the radiograph saw half of TB lesions.
- Tuberculosis, consolidation: 0.5 independent of the lesion → 0.85 without a nodular or cavitary lesion, 0.4 with
  one (assumption); a truly normal TB image falls from 25% to 7.5%.
- Sources added for unchanged values: TB lesion 0.5 (GETNET2019, cavitation 45.6%); asthma airflow obstruction 0.3
  (NICE_NG245, spirometry sensitivity 0.30-0.39 for asthma in adults).

Checked and kept: lung cancer symptom frequencies (CAPER, ADES2014/HAMILTON2005, consistent with WALTER2015);
lung cancer prevalence 1.3% (BRADLEY2021); TB symptoms (cough 0.8, fever 0.5, weight loss 0.5, haemoptysis 0.2,
plausible against general TB descriptions but unsourced); worried-well rates (D47 design; about 7% draw no symptom).
Left as they are, for a clinician to look at (evidence unclear or a change would ripple into tuned lanes):

- No disease found (20% of presenters): every symptom falls back to the CAPER control floor, so about 37% draw no
  symptom ("attends for a check-up", outside the scope) and only 12% have chest pain although the label is
  "musculoskeletal" first. Tried: chest pain 0.5, cough, breathlessness and tiredness 0.35 (assumptions). Reverted
  because nothing resolves this condition in `care.yaml`, so symptomatic patients return all year and the pinned
  encounter run went out of range (GP visits 4.25 → 5.8 per patient, cost 491 → 657 EUR). Needs a care-model rule
  first (natural resolution or reassurance), then these numbers.

- Lung cancer with a co-existing COPD exacerbation in 50% (`cooccurrence.yaml`, YOUNG2009): that is COPD present,
  not an active flare, and `airflow_obstruction` 0.5 already models COPD; an active flare in half of cancer
  presenters is probably too high. Changing it moves the encounter-loop tuning, so left.
- Symptoms that fall back to the CAPER control floor where a GP expects more: pneumonia chest pain 0.12 and
  tiredness 0.15; heart failure tiredness 0.15; TB tiredness 0.15; viral illness tiredness 0.15 and wheeze 0.05.
  These make look-alikes look cleaner than in practice (cancer stands out more).
- Worried well and no-disease classes inherit small floors for objective signs (oedema, chest sounds 5%, raised
  NT-proBNP 8%), against D47's "no objective findings".
- Prevalences that are pure assumptions: no disease found 0.20, COPD exacerbation 0.075, heart failure 0.05,
  reflux or post-infectious cough 0.055, worried well 0.03, viral (remainder) 0.45. They set cohorts, not cards.
- Lab distributions mostly assumed: CRP per condition, platelets in lung cancer, haemoglobin default not split by sex.
- COPD exacerbation airflow obstruction 0.9 (by definition close to 1; 0.9 allows for misdiagnosed COPD).

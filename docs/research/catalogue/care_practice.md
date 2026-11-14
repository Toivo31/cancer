# Care practice for the encounter loop (WP-C8-3)

Research note behind `catalogue/lung-primary-care/care.yaml`, the definitive tests, the worried-well condition, test costs and
timing, and `scenarios/finland_encounter_resources.yaml`. Pages opened 14 Nov 2026 (ids in `params/sources.yaml`). Almost
every page was read through a summarising tool, so figures say "re-check against the page". Where no page gave a number, the
number in the catalogue is `assumption` and says why. About 75 minutes of research were used; the gaps are listed in section 10.

## 1. Who does what in a Finnish health centre

| Item | Finding | Source | Grade |
|---|---|---|---|
| Nurse needs assessment | Done the same working day as the contact; the nurse decides what is needed, how urgently and which profession; "Älä siirrä asiaa toiselle ammattilaiselle, jos asia ei aidosti vaadi sitä" | INNOKYLA_HTA | C |
| Nurse orders | The guide says the nurse prepares referrals and requests and makes sure the doctor records the "määräykset" (orders); it does not say whether a nurse may order labs or X-rays alone | INNOKYLA_HTA | C, gap |
| Nurse prescribing | Limited prescribing since 2011, extra training and a written order from the responsible doctor; in one county 16 such nurses in outpatient care. Sore throat (strep, from 16) and allergic rhinitis are in scope; ear, sinus and prolonged upper respiratory infections go to a nurse clinic or a doctor | KEUSOTE_LAMA | C |
| Doctor | Diagnosis and the treatment plan are the doctor's | KEUSOTE_LAMA | C |
| Antibiotics for acute bronchitis | "Myös bakteerin aiheuttama äkillinen keuhkoputkentulehdus paranee yleensä ilman antibioottihoitoa" (not treated in immunocompetent adults) | PIRHA_ANTIB | C |
| Who sees the patient first | 40 to 60% see a doctor, the rest a nurse | KHALIFE2025 | B |

Modelled in `care.yaml`: the nurse gathers the main symptoms and chooses advice, a routine or an urgent GP booking; no orders,
no prescribing (a modelling choice following the sources above, not a rule found). The GP gathers the full history and
examination and may order, treat, follow up, refer or discharge.

## 2. Waiting for a visit

| Item | Value | Source | Grade |
|---|---|---|---|
| Non-urgent doctor visit within 7 days, October 2022 | just under 60% | MTV_THL2022 (journalist summary of a THL report) | secondary |
| Non-urgent nurse visit within a week, October 2022 | about 90% | MTV_THL2022 | secondary |
| Doctor wait over 3 months, October 2022 | 1% | MTV_THL2022 | secondary |
| Care guarantee, primary outpatient care from 2025 | 3 months (not for under 23) | STM_HOITOTAKUU2025 | A (law summary) |
| GP first visit about 14 days, 35% wait over 14 days | already in finland_lung | KHALIFE2025 | B |

The THL report itself was not opened (2022 data is old; no 2025 figure was found). Booking leads in the resources file keep the
scenario's GP lead (12 days, about 14 days to the visit).

## 3. Prices in euros

All from Finnish wellbeing-county price lists unless stated; one county each, so they are samples, not national prices.
`cost_eur` in `tests.yaml` carries the same numbers and a note.

| Item | EUR | Line item and source |
|---|---|---|
| Nurse visit | 92 | "Käynti hoitajalla", Ephva 2026 (EPHVA2026) |
| GP visit | 232 | "Käynti lääkärillä", Ephva 2026 (EPHVA2026). Soite 2024 has a nurse contact 59 to 106 and a GP contact 262 to 527 by content (SOITE2024) |
| CRP (laboratory and point of care) | 3 | Kela pilot patient price "S-CRP" (KELA_VVK2026); a patient price, not a unit cost |
| Blood count | 3 to 6 | Kela pilot patient price (KELA_VVK2026) |
| NT-proBNP | 12 | "P-ProBNP", Kela pilot patient price (KELA_VVK2026) |
| Routine bacterial culture | 6 | Kela pilot patient price (KELA_VVK2026) |
| Chest X-ray | 40 (45) | "Thorax PA-projektion" 40, "Thorax" 45, Soite 2024; Kela pilot patient price 48.50 |
| CT of the chest | 336 | "Thorax eller mediastinum", Soite 2024; high-resolution lung CT 271 |
| MRI of the head | 457 | Soite 2024 (411 to 822 by extent) |
| PET-CT | 3,718 to 3,951 | Ephva 2026, lines inside urology and gastro bundles |
| Spirometry | 94; with bronchodilator 128 | Soite 2024 |
| Echocardiography | 347 (386) | Soite 2024 ultrasound of the heart; Ephva 2026 first internal-medicine visit with echo 386 |
| Oesophageal pH monitoring | 293 | Soite 2024 |
| Bronchoscopy | 666 (1,265) | Soite 2024 with basic samples; Ephva 2026 lung-clinic bundle |
| CT-guided lung tissue sample | 490 | Soite 2024 |
| Pathology: core biopsy report 132 / 192 / 324; cytology 60 to 72; immunohistochemistry 120; molecular 693 | | Soite 2024 pathology list |
| Mycobacterial culture | not found | Ephva 2026 lung-clinic bundle with typing 756 (with a visit); catalogue value 60 is an assumption |
| Respiratory virus PCR, chemistry panel, EBUS | not found | assumptions in the catalogue, with reasoning |

`cost_scale` (D46) is a visible world setting, default 1.0 in `finland_encounter_resources.yaml` (`encounters.cost_scale`),
lean range 1.0 to 1.5. The prices are real 2024 to 2026 county prices, so 1.0 is the honest base.

## 4. Turnaround

| Test | Service / report | Basis |
|---|---|---|
| History, examination, vital signs | instant, in the visit slot | no separate resource |
| Point-of-care CRP | minutes, in the visit | Kela and HUS list CRP as a point-of-care test (KELA_LAB, HUS_DIAG2023); minutes is our reading |
| Laboratory CRP, blood count, chemistry, NT-proBNP | report median 0.5 day, p90 1.5 | assumption; HUS aims for a result within one hour for urgent tests (HUS_DIAG2023) |
| Chest X-ray | report median 1.5 days, p90 4 | scenario value (assumption); plain X-rays usually need no appointment (HUS_DIAG2023) |
| CT of the chest | report median 3 days, p90 7 | PIRHA_PATH (within a week), median assumed |
| Pathology report | median 4.5 days, range 0 to 14 | STOKSTAD2019 (Norway). Definitive histology with markers: median 7, p90 14 (our estimate) |
| Mycobacterial culture | median 35 days, p90 56 | CDC_TB: "a week or more"; 6 to 8 weeks for a negative is general knowledge, not opened (assumption) |
| Definitive nodule follow-up | median 95 days | follow-up interval of about 3 months (assumption) |
| pH monitoring, echo, spirometry with reversibility, virus PCR | assumptions | no Finnish figure found |

## 5. Capacity

No county scanner, endoscopy, laboratory or clinic capacities were found. HUS 2024 volumes (HUS_YEAR2024): radiology
1,178,368, pathology 529,985, microbiology 1,685,705, chemistry and haematology 18.9 million examinations a year, with "local
backlogs" in imaging because orders exceeded budgets. Finland has the fewest CT scanners per capita in the Nordics
(IHE2026). The population behind the HUS figures was not opened, so no per-capita capacity was derived. The slice sizes in
`finland_encounter_resources.yaml` are assumptions fitted to `finland_lung.yaml` and to these facts.

## 6. Rates for the decision tables

| Rate | Finding |
|---|---|
| GP chest X-ray for cough | not found for Finland. IHE2026 (CT in primary care under 10%) and KOO2023 (UK: guideline imaging after dyspnoea often not done at the first visit) are the only anchors |
| Antibiotics for acute bronchitis or cough | the Finnish register study of antibiotics for acute upper respiratory infections 2017 to 2021 turned up in search but could not be opened (not on the fetch allowlist); Finnish guidance is no antibiotic for bronchitis (PIRHA_ANTIB); adult outpatient antibacterial prescriptions fell from 582 to 428 per 1,000 adults a year 2008 to 2019 (Finnish register study, MDPI Antibiotics 2022, table only; not in sources.yaml) |
| Referral rate | not found |

So every number in the proposed decision table (section 11) is `assumption`, shaped by the guidance above.

## 7. Definitive tests (D46)

Each condition has exactly one test that measures its own marker `dx_<condition>`. Sensitivity and specificity are `assumption`
except where noted (a definitive test is the reference standard, so no accuracy figure exists for it by definition).

| Condition | Definitive test (id) | Cost EUR | Report time | Resource and slot | Sourced? |
|---|---|---|---|---|---|
| lung_cancer | tissue sampling with histology report (`dx_lung_cancer_histology`) | 802 (490 + 192 + 120) | median 7 d, p90 14 | `ttnb_slot` 1 a day, lead 6 d | cost SOITE2024 (derived); sensitivity 0.88 RIVERA2013; time estimate |
| pneumonia | chest X-ray read with the clinical picture (`dx_pneumonia_chest_xray`) | 40 | median 1.5 d | `xray` | cost SOITE2024; accuracy assumption. Not scarce in real practice |
| copd_exacerbation, asthma | spirometry with reversibility (`spirometry_reversibility`, two markers) | 128 | at the visit | `lung_function` 6 a day, lead 14 d | cost SOITE2024; accuracy assumption |
| heart_failure | echocardiography (`echocardiography`) | 347 | median 1 d | `echo` 5 a day, lead 21 d | cost SOITE2024; rest assumption |
| tuberculosis | sputum mycobacterial culture (`mycobacterial_culture`) | 60 (assumption) | median 35 d, p90 56 | `mycobacteriology` | specificity partly CDC_TB; rest assumption |
| benign_nodule | repeat CT for stability (`ct_nodule_followup`) | 336 | median 95 d | `ct_scanner` | cost SOITE2024; interval assumption |
| reflux_postinfectious_cough | oesophageal pH monitoring (`ph_monitoring`) | 293 | median 10 d | `gi_function` 1 a day, lead 28 d | cost SOITE2024; rest assumption |
| viral_self_limiting | respiratory virus PCR (`respiratory_virus_pcr`) | 40 (assumption) | median 1 d | `lab` | assumption |
| no_disease_found, worried_well | none: absence of disease is a diagnosis of exclusion | | | | decision to confirm |

## 8. Worried well (D47)

Condition `worried_well` (class healthy), prevalence 0.03 among presenters (range 0.01 to 0.08), assumption. Basis: a review
(MUS_BMJO2022, read through a summarising tool) cites medically unexplained symptoms as "approximately 45% of all general
practice consultations and 20% of new consultations in primary care"; those are all complaints and mostly have a plausible
ordinary explanation, so only a small slice is a random, incoherent cluster in a chest-symptom stream. Each symptom is drawn
independently: cough 0.30, dyspnoea 0.30, chest pain 0.35, fatigue 0.40, appetite loss 0.15, hoarseness 0.10, wheeze 0.10,
fever 0.08, weight loss 0.08, recurrent chest infection 0.05, haemoptysis 0.02. Signs, labs and imaging fall to the
catalogue's `default` (background rates), so findings are normal apart from chance. The 3% is taken from
`viral_self_limiting`, the catalogue's remainder.

## 9. Group markers (D50): group tests read these, definitive tests read the `dx_` markers

| Marker (hidden variable) | Group | Test and output | Sensitivity / specificity | Cost EUR, report time | Status |
|---|---|---|---|---|---|
| `lung_lesion` | lung_cancer 1.0, benign_nodule 1.0, tuberculosis 0.5, else 0.01 | `chest_xray.abnormal` | 0.754 / 0.902 (BRADLEY2021) | 40, 1.5 d | existed, reused |
| `lung_lesion` | same | `chest_ct.lesion_seen` | 0.95 / 0.98 (assumption) | 336, 3 d | existed, reused |
| `crp_true` (inflammation) | pneumonia median 60, tuberculosis 30, COPD exacerbation 25, lung cancer 10, else 8 | `crp_poc.crp` (positive at 50 mg/L) and `crp.crp` | analytical error not modelled; pneumonia PPV 0.47 NPV 0.84 (GRAFFELMAN2007) | 3, minutes (poc) or 0.5 d | TB and COPD entries added, assumption |
| `airflow_obstruction` | copd_exacerbation 0.9, asthma 0.3, lung_cancer 0.5, else 0.08 | `spirometry.airflow_obstruction` | 1.0 / 1.0 (reference for obstruction); handheld 0.93 / 0.85 (VANDENBEMT2014) | 94, in the visit | existed, reused |
| `cardiac_strain` | heart_failure 0.95, copd_exacerbation 0.2, pneumonia 0.15, else 0.08 | `nt_probnp.bnp_high` | 0.95 / 0.65 (assumption) | 12, 0.5 d | new, assumption (rule-out test) |

Group tests are cheaper, faster and less scarce than the definitive tests, so the sensible path is group tests first, then the
definitive test for the remaining candidate.

## 10. Gaps and what a clinician should check first

1. Every accuracy of a definitive test, NT-proBNP, the CRP and TB-culture timing, and all treatment response rates are assumptions.
2. Prices come from three counties (Soite 2024, Ephva 2026, Kela pilot patient prices), mixed years; PET-CT and bronchoscopy are inside bundles.
3. No Finnish decision-rate data (X-ray, antibiotics, referral) was found.
4. Vital signs (heart rate, SpO2, temperature) are not modelled; the catalogue has `fever` as a symptom only.
5. `worried_well` and `no_disease_found` have no definitive test (class healthy).
6. Whether Finnish nurses order tests or X-rays under standing orders is not established.

## 11. Proposed decision-table numbers

`scenarios/finland_encounter_policy.yaml` is created by the engine lane (`w3/c8-engine`, format `encounter_policy/1`) and does not exist
on this branch, so the proposal is written here ready to paste. Action ids are those of `care.yaml`. Every row is `assumption`;
the shape follows the Finnish guidance in section 1 (no antibiotics for bronchitis, nurse passes patients on, CT rarely from primary care).

```yaml
format: encounter_policy/1
points:
  nurse_encounter:
    default: {book_gp_routine: 0.6, advice_return: 0.37, book_gp_urgent: 0.03}
    source: assumption
    note: "Nurse passes most chest-symptom contacts to a GP; no orders (INNOKYLA_HTA, KHALIFE2025)"
    rules:
      - when: "found.haemoptysis or (found.weight_loss and age >= 50)"
        probs: {book_gp_urgent: 0.85, book_gp_routine: 0.15}
        source: assumption
        note: "alarm symptoms go to a GP soon (NICE NG12 list)"
      - when: "episode >= 2"
        probs: {book_gp_routine: 0.8, book_gp_urgent: 0.15, advice_return: 0.05}
        source: assumption
        note: "a patient who returns is rarely sent home again"
  gp_encounter:
    default: {advice_return: 0.3, order_crp: 0.25, order_chest_xray: 0.15, treat_antibiotics: 0.05, order_blood_count: 0.05, follow_up: 0.08, order_spirometry: 0.04, discharge: 0.05, refer_routine: 0.03}
    source: assumption
    note: "first visit without alarm findings; antibiotics are rare for cough (PIRHA_ANTIB); CRP in the visit is the usual first test"
    rules:
      - when: "found.haemoptysis and attempts.chest_xray == 0"
        probs: {order_chest_xray: 0.7, refer_urgent: 0.25, order_chest_ct: 0.05}
        source: assumption
        note: "alarm symptom: imaging or urgent referral at once"
      - when: "last.chest_xray.abnormal"
        probs: {refer_urgent: 0.8, refer_routine: 0.1, order_chest_ct: 0.1}
        source: assumption
        note: "suspicious film is referred; CT from primary care is rare (IHE2026 under 10%)"
      - when: "last.nt_probnp.positive"
        probs: {order_echo: 0.5, treat_diuretic: 0.25, refer_routine: 0.25}
        source: assumption
      - when: "last.spirometry.positive"
        probs: {treat_inhaler: 0.55, order_spirometry_reversibility: 0.3, follow_up: 0.15}
        source: assumption
      - when: "last.crp.crp is not None and last.crp.crp >= 50"
        probs: {treat_antibiotics: 0.5, order_chest_xray: 0.4, follow_up: 0.1}
        source: assumption
        note: "high CRP suggests bacterial infection"
      - when: "reason == 'result' and last.chest_xray.abnormal is False and episode >= 2"
        probs: {refer_routine: 0.4, order_chest_ct: 0.05, treat_antibiotics: 0.15, advice_return: 0.4}
        source: assumption
        note: "clear film but the patient keeps coming back"
      - when: "reason == 'result' and last.chest_xray.abnormal is False"
        probs: {advice_return: 0.65, follow_up: 0.15, treat_antibiotics: 0.1, order_spirometry: 0.1}
        source: assumption
      - when: "found.ankle_oedema and found.dyspnoea"
        probs: {order_nt_probnp: 0.6, order_chest_xray: 0.2, treat_diuretic: 0.1, order_echo: 0.1}
        source: assumption
      - when: "found.wheeze and attempts.spirometry == 0"
        probs: {order_spirometry: 0.45, treat_inhaler: 0.35, order_crp: 0.2}
        source: assumption
      - when: "reason == 'treatment'"
        probs: {advice_return: 0.6, order_chest_xray: 0.25, follow_up: 0.15}
        source: assumption
      - when: "episode >= 3"
        probs: {refer_routine: 0.45, order_chest_xray: 0.4, order_chest_ct: 0.05, advice_return: 0.1}
        source: assumption
        note: "third episode: work up or refer"
      - when: "episode >= 2 and attempts.chest_xray == 0"
        probs: {order_chest_xray: 0.7, order_crp: 0.15, advice_return: 0.15}
        source: assumption
```

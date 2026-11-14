> Reruns of the conflicts in section 1 (diagnosis to treatment, delay and survival, chest X-ray, PET-CT): see `docs/evidence_sensitivity.md`.

# Evidence research: what to add to the evidence base (14 Nov 2026, evening)

Research done in the coordinating chat. It is input for the team and the tracks, not a decision: nothing in `params/` was changed. Each item says what it would affect, so the person or agent who owns that file can decide whether and how to use it.

**Why it matters.** The brief asks for "reliable evidence … clearly show the sources supporting every claim", and data quality & transparency is 20% of the score. Our insights come from the simulator, so the simulator's inputs carry that weight.

**Status of this branch.** `overnight/sim` already covers most of the original plan: a source ledger (`params/*.yaml`, `params/sources.yaml`, generated `docs/ledger.md`), ranges next to headlines (`docs/ranges.md`), robustness runs (`docs/sensitivity.md`), Stokstad validation (`docs/validation.md`), external checks and equity subgroups (`docs/pitch/equity.md`); see `docs/plan/components/C7-evidence.md`. This file therefore lists only what is **new or in tension** with those files. Section 2 may also be useful input for the catalogue research packages `WP-C2-R1` (conditions and symptoms) and `WP-C2-R2` (tests and labs).

---

## 1. Possible conflicts with current parameters (look at these first)

| Topic | What we use now | What I found | Worth considering |
|---|---|---|---|
| Diagnosis → treatment, Finland | `registry_diagnosis_to_treatment_start` = 37 d (36–38), IHE2026, noted as *not lung-specific* | **Lung-specific, 5 Finnish hospitals (Kuopio, Tampere, Oulu, Mikkeli, Joensuu), 2018:** median 69 d (IQR 53–92) for surgical patients, 65 d (IQR 46–116) for non-surgical. [Acta Oncologica 2025, art. 43398](https://medicaljournalssweden.se/actaoncologica/article/view/43398) | Whether the Finnish calibration target should be a range spanning both, or the lung-specific figure, and how the baseline fit and headline numbers change |
| Survival effect of treatment delay | `docs/pitch/evidence_brief.md` §1: "Delay costs lives in general", Hanna 2020 HR ~1.06–1.08 for surgery (correctly flagged as not lung-specific) | In Hanna 2020 the **lung surgery** HR 1.06 per 4 weeks was **not statistically significant** ([summary](https://oncology.medicinematters.com/mortality/treatment/meta-analysis-mortality-risk-cancer-treatment-delays/18575470)). A **2025 lung-specific meta-analysis** (15 studies, 16 cohorts) found pooled HR **1.00** (95% CI 0.99–1.02) for a 4-week delay, with I² 97% ([Springer 2025](https://link.springer.com/article/10.1007/s11357-025-01684-9)). Systematic review: faster care is linked to worse outcomes in advanced disease (sicker-quicker, 6/8 studies) and to better outcomes in early-stage surgical patients ([Hall et al.](https://discovery.ucl.ac.uk/10143598/1/Fisher_762.full.pdf)). The effect is probably stage-dependent, highest around stage II and low for palliative-only patients ([Sainz Zuniga & Ost](https://mdanderson.elsevierpure.com/en/publications/impact-of-delays-in-lung-cancer-treatment-on-survival)) | Whether any days→mortality translation should be limited to the curative-intent subgroup and labelled illustrative, and whether the evidence brief should cite the lung-specific null result next to Hanna. An AZ oncologist is likely to know this literature |
| Chest X-ray accuracy | BRADLEY2021: sensitivity 0.754, specificity 0.902 (all cancers, Leeds) | Same Leeds cohort reported for **NSCLC within 1 year: 76% / 95%** ([Bhartia et al. 2021, Lung Cancer](https://eld.bl.uk/catalog/100175088713_0x000001)). Primary-care meta-analysis: pooled 81% / 68% ([BJR Open 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8327929/)) | Whether the specificity range in sensitivity runs should widen to 0.68–0.95 |
| PET accuracy | GOULD2001 (stand-alone FDG-PET, 96.8% / 77.8%) | **PET-CT**, pulmonary nodules: 89% / 70% ([Li et al. 2018](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5895332/)) | Whether to use a PET-CT source alongside the PET-only one, since Finnish practice is PET-CT |

## 2. New sources not yet in `params/sources.yaml`

**Patient mix and symptoms (patient generator, decision-model checks)**

| Fact | Source |
|---|---|
| Among 963 patients referred with symptoms suspicious of lung cancer (England): 15.9% lung cancer, 5.9% other thoracic cancer, 78.2% non-malignant; haemoptysis in 21.6% of cases | [Walter et al., Br J Cancer 2015](https://minerva-access.unimelb.edu.au/server/api/core/bitstreams/142055f5-ed18-5279-8525-30e3be025354/content) |
| Symptom diagnostic odds ratios: haemoptysis 6.39, dyspnoea 2.73, cough 2.64, chest pain 2.02 | [Systematic review and meta-analysis, PMC6248994](https://pmc.ncbi.nlm.nih.gov/articles/PMC6248994) |
| PPV of haemoptysis alone in primary care 2.4% | [Jones et al., BMJ 2007, citing Hamilton](https://www.bmj.com/content/334/7602/1040) |
| PPV after a negative chest X-ray: haemoptysis 2.9% within 1 year; all other single symptoms <1% | [Bradley et al., BJGP 2020](https://eprints.whiterose.ac.uk/164774/9/bjgp20X713993.full.pdf) |
| Stage I–IIIA share of NSCLC: Finland 39.5% vs Norway 48.7%, Sweden 50.4%, Denmark 44.0%. Surgery: 11.8% of all lung cancers in Finland (registry) vs about 26% in Norway and Denmark | [Acta Oncologica 2025, art. 43398](https://medicaljournalssweden.se/actaoncologica/article/view/43398) |
| About 3,000 new lung cancers a year in Finland; 2,947 in 2022 | [Syöpäjärjestöt via Verkkouutiset](https://www.verkkouutiset.fi/a/keuhkosyovan-hoidossa-on-suuria-alueellisia-eroja/); [Airaksinen 2025 thesis](https://www.utupub.fi/bitstreams/049ceb22-acf3-44b0-94f8-2d72ec8b2162/download) |

A possible check for the decision model: because the generator encodes published likelihoods, the trained model's probabilities could be compared with these PPVs. For example, P(cancer | haemoptysis alone) should land near the published 2.4–2.9% for an unselected primary-care population.

**Tests and harms**

| Fact | Source |
|---|---|
| EBUS-TBNA staging meta-analysis: 93% / 100%; complications 0.15% | [Gu et al., Eur J Cancer 2009](https://pubmed.ncbi.nlm.nih.gov/19124238/) |
| EBUS-TBNA in nodes normal on imaging: sensitivity 49% | [Leong et al. 2019](https://publications.wehi.edu.au/Publications/14913) |
| CT-guided transthoracic biopsy: ~92% diagnostic accuracy; pneumothorax 20.5%, haemorrhage 2.8% | [DiBardino et al., J Thorac Dis](https://jtd.amegroups.org/article/view/6159) |

Diagnostic chest CT sensitivity in symptomatic patients is still unsourced (`assumption` 0.95 in `test_accuracy.yaml`). I found nothing either; it's a good mentor question.

**Finnish intervals**

| Fact | Source |
|---|---|
| Average ~155 days from symptom onset to treatment (Kuopio, Tampere, Turku, Rovaniemi; unpublished, reported by Yle) | [Yle MOT 2025](https://yle.fi/a/74-20251023) (likely already YLE_MOT2025) |
| Curative-intent treatment: 27% of patients (2019–2023); clinical stage missing for almost half; MDT coverage cannot be assessed from registries | [Syöpäjärjestöt 2025](https://www.syopajarjestot.fi/uutinen/keuhkosyovan-toteamisessa-on-eroja-hyvinvointialueiden-valilla-tietojen-kattavuudessa-edelleen-parannettavaa/); [Verkkouutiset](https://www.verkkouutiset.fi/a/keuhkosyopa-todetaan-usein-liian-myohaan-vain-joka-neljas-saa-parantavaa-hoitoa/) |
| Official Finnish definitions of cancer access-to-care intervals (useful so our interval names match THL's) | [THL Ohjaus 21/2016, Hoitoonpääsyn seuranta syövän hoidossa](https://core.ac.uk/download/78470017.pdf) |
| Norwegian lung targets: 35 d referral → chemotherapy, 42 d referral → surgery/radiotherapy | [Norwegian cohort study 2021](https://hdl.handle.net/11250/2756752) |

## 3. Regional evidence (closes part of the `[gap]` in `docs/pitch/equity.md`)

- **"Keuhkosyöpä Suomessa" (Finnish Cancer Registry, Dec 2024), section 4.1 "Aika diagnoosista hoitoon"**: the share of patients reaching first treatment within 0–6 months of diagnosis, **by collaborative region**, sex and age group. This is the best regional timing table we know of. I could not download it from the cloud environment (403). **Someone should open it in a browser:** https://syoparekisteri.fi/assets/files/2024/12/Keuhkosyopa_Suomessa.pdf
- From the same report's text: the share going to surgery was lower, especially in **Kainuu and Kymenlaakso**. Drug therapy was given less often than nationally in **Lapland, Länsi-Uusimaa, Keski-Uusimaa, Vantaa–Kerava, Etelä-Karjala and Varsinais-Suomi**. In Eastern and Northern Finland, first treatment was more often radiotherapy or drug therapy ([Verkkouutiset](https://www.verkkouutiset.fi/a/keuhkosyovan-hoidossa-on-suuria-alueellisia-eroja/)).
- 5-year relative survival for lung cancer patients diagnosed 2019–2023: women 25.6%, men 16.2%. County figures for women did not differ significantly from the national figure ([Syöpä 2023](https://syoparekisteri.fi/assets/themes/ssy3/factsheets/syopa_2023_tilastoraportti.html)).

## 4. Ideas not yet visible on this branch

These are for consideration; whether they're worth the hours before Sunday 10:00 is the team's call.

1. **Validation scorecard using the ISPOR-SMDM types.** [Eddy et al. 2012](https://ispor.org/heor-resources/good-practices/article/model-transparency-and-validation) defines five validation types: face, verification, cross, external and predictive, with the last two the strongest. Most of the work already exists (tests, external checks, Stokstad). A one-slide mapping makes it legible to judges. The [STRESS-DES reporting checklist](https://ore.exeter.ac.uk/repository/handle/10871/40055) could serve as an appendix.
2. **AstraZeneca mentor input as a logged source.** The brief explicitly accepts "insights gathered from AstraZeneca mentors". Candidate questions:
   - Is the flowchart realistic for a Finnish central hospital? (face validity)
   - What are the Finnish Lung Cancer Programme's per-treatment time targets? (not found online)
   - Typical waits for PET-CT, EBUS and the MDT cycle?
   - Diagnostic CT sensitivity in practice?

   Each answer could go into `sources.yaml` with name, role and date.
3. **Missing evidence as a recommendation.** The parameters we cannot source are largely the data Finland does not collect: no lung-specific national waiting statistics, stage missing for about half, MDT coverage not assessable. That supports a national-level proposal: "the inputs this tool needs = the minimum dataset for the national lung cancer quality registry". It connects the demo to the policy fix.
4. **Lead with the Goal 3 indicator itself** (share treated within the target time), which we measure directly, rather than survival, given §1 above.

## Considered and set aside
- **Synthea** (open synthetic EHR generator with a lung cancer module): US-centric, and the integration cost is too high for the time left.
- **THL/Sotkanet live data**: specialist-care waits there cover all specialties, not cancer. They're usable on the problem slide only, e.g. HUS median 103 vs Etelä-Karjala 35 days in April 2023 ([THL via Verkkouutiset](https://www.verkkouutiset.fi/a/erikoissairaanhoidon-jonot-kasvoivat-edelleen-huhtikuussa/)).

# Making the simulator evidence-based (14 Nov 2026, evening)

**Problem.** The brief requires "reliable evidence … clearly show the sources supporting every claim", and Data quality & transparency is 20% of the score. Our insights come from the simulator, so the simulator itself has to be built from sourced numbers, fitted to observed Finnish data, and checked. Right now its inputs are "rough values, calibrated later" (master plan §6), and that is the weak point.

**One-line pitch for judges:** *"Every number in the simulator has a source you can click. It reproduces observed Finnish waiting times, and the recommendation still holds across the whole range the evidence allows."*

Note: the repo (Toivo31/cancer, last push 09:03 UTC) holds the master plan and the technique classifier, but no simulator code yet. Whoever builds the simulator should start from this doc.

---

## Ranked ideas (by score impact per hour, deadline Sun 10:00)

| # | Idea | Hits criterion | Effort |
|---|---|---|---|
| 1 | Evidence ledger: one parameter file, every value with source, range and grade, shown in the UI | Data quality 20%, "source for every claim" | Low |
| 2 | Calibrate to observed Finnish intervals, and back out unknown capacities from observed waits | Data quality, Insight | Medium |
| 3 | Robustness run: re-run the recommendation across parameter ranges, report "holds in X% of draws" | Data quality, Actionability | Low |
| 4 | Equity gap inside one region: patient subgroups with evidence-based disadvantages | Brief step 1 "identify the gap" | Low–Med |
| 5 | Validation scorecard following the ISPOR-SMDM validation types | Data quality, Clarity | Low |
| 6 | Get AZ mentor face validation tonight, logged as a source | Brief explicitly allows mentor insight | Low |
| 7 | Honest outcome translation: lead with the Goal 3 indicator, keep survival claims narrow | Credibility | Low |
| 8 | Turn missing evidence into a recommendation (minimum dataset for the quality registry) | Actionability | Low |

---

## 1. Evidence ledger (highest return)

One file (YAML or CSV) holds every simulator input: `value`, `low`, `high`, `unit`, `source`, `url`, `setting` (Finland / Nordic / UK / meta-analysis), `grade`, `note`.

Suggested grades:
- **A**: Finnish registry or national report, or a pooled meta-analysis
- **B**: single peer-reviewed study, or non-Finnish data
- **C**: AZ mentor input or a team assumption (labelled as such)

Payoff: the UI can show a source chip next to every number. The pitch can say "N of M parameters sourced, X% grade A/B". The C-grade items become an honest list of assumptions.

### Starter ledger (researched tonight)

**Patient mix and symptoms (patient generator)**

| Parameter | Value | Source |
|---|---|---|
| New lung cancers per year, Finland | ~3,000 (2,947 in 2022) | [Syöpäjärjestöt 2025](https://www.verkkouutiset.fi/a/keuhkosyopa-todetaan-usein-liian-myohaan-vain-joka-neljas-saa-parantavaa-hoitoa/); [Airaksinen 2025](https://www.utupub.fi/bitstreams/049ceb22-acf3-44b0-94f8-2d72ec8b2162/download) |
| Case mix among people referred with suspected lung cancer | 15.9% lung cancer, 5.9% other thoracic cancer, 78.2% non-malignant (n=963, England) | [Walter et al., BJC 2015](https://minerva-access.unimelb.edu.au/server/api/core/bitstreams/142055f5-ed18-5279-8525-30e3be025354/content) |
| Haemoptysis among cases | 21.6%; only first symptom associated with cancer | same |
| Symptom diagnostic odds ratios | haemoptysis 6.39, dyspnoea 2.73, cough 2.64, chest pain 2.02 | [Symptom meta-analysis, PMC6248994](https://pmc.ncbi.nlm.nih.gov/articles/PMC6248994) |
| PPV of haemoptysis alone in primary care | 2.4% (higher with other symptoms) | [Jones et al., BMJ 2007, citing Hamilton](https://www.bmj.com/content/334/7602/1040) |
| PPV of haemoptysis after a negative CXR | 2.9% within 1 year; all other single symptoms <1% | [Bradley et al., BJGP 2020](https://eprints.whiterose.ac.uk/164774/9/bjgp20X713993.full.pdf) |
| Most common first symptoms, Finland | cough and dyspnoea, each in >30% | [Mattila 2025, Satakunta](https://www.utupub.fi/handle/10024/180618) |
| Stage I–IIIA share of NSCLC | Finland 39.5% vs Norway 48.7%, Sweden 50.4% | [5 Finnish hospitals, Acta Oncol 2025](https://medicaljournalssweden.se/actaoncologica/article/view/43398) |
| Curative-intent treatment share | 27% (2019–2023) | [Lung cancer quality report](https://www.syopajarjestot.fi/uutinen/keuhkosyovan-toteamisessa-on-eroja-hyvinvointialueiden-valilla-tietojen-kattavuudessa-edelleen-parannettavaa/) |

**Test accuracy and harms (each step's error rate and cost)**

| Test | Sensitivity / specificity | Harm / note | Source |
|---|---|---|---|
| Chest X-ray, symptomatic primary care | 77–80% (low-bias studies); pooled 81% / 68% | Negative CXR still leaves risk | [Bradley SR 2019](https://eprints.whiterose.ac.uk/146374); [BJR Open 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8327929/) |
| Chest X-ray, prospective cohort | 76% / 95% (NSCLC, 1 yr) | 2-yr risk after negative CXR 0.8% | [Bhartia et al. 2021](https://eld.bl.uk/catalog/100175088713_0x000001) |
| FDG PET-CT, pulmonary nodule | 89% / 70% | False positives from inflammation | [Li et al. 2018](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5895332/) |
| EBUS-TBNA, staging | 93% / 100% overall; 49% for nodes normal on imaging | 0.15% complications | [Gu et al. 2009](https://pubmed.ncbi.nlm.nih.gov/19124238/); [Leong 2019](https://publications.wehi.edu.au/Publications/14913) |
| CT-guided transthoracic biopsy | ~92% diagnostic accuracy | pneumothorax 20.5%, haemorrhage 2.8% | [DiBardino et al., JTD](https://jtd.amegroups.org/article/view/6159) |
| Diagnostic chest CT | **gap, not sourced tonight** | | ask mentor or search |

The harm column answers open question 6 (how to cost invasive tests): complication probability can be the cost, rather than an invented penalty.

**Waits and intervals (calibration targets, not inputs)**

| Interval | Observed | Source |
|---|---|---|
| Wait for a health-centre appointment | ~2 weeks (other Nordics: under 1 week); 40–60% see a nurse first | [University of Helsinki 2025](https://www.helsinki.fi/fi/uutiset/terveys/miksi-suomessa-keuhkosyopaan-kuollaan-aiemmin-kuin-pohjoismaissa); [Khalife et al. 2025](https://doi.org/10.2340/1651-226X.2025.42778) |
| First doctor visit → referral | ~2 weeks | [Mattila 2025](https://www.utupub.fi/handle/10024/180618) |
| Referral → diagnosis | just under 2 months; largest delay in specialist care | same |
| Diagnosis → treatment | median 69 days (IQR 53–92) for surgery, 65 (46–116) for non-surgical, 2018 | [Acta Oncol 2025](https://medicaljournalssweden.se/actaoncologica/article/view/43398) |
| Diagnosis → treatment, national | median 36–38 days (2018–2022) | IHE Cancer Dashboard 2026 (already in master plan) |
| Symptom → treatment | ~155 days on average (4 university hospitals, unpublished) | [Yle MOT, Kuittinen study](https://yle.fi/a/74-20251023) |

Note the conflict: 36–38 days nationally against 65–69 days in five hospitals. **Show both and fit to a range.** Picking one would read as cherry-picking. Also align our interval definitions with THL's official ones ([Hoitoonpääsyn seuranta syövän hoidossa, THL 2016](https://core.ac.uk/download/78470017.pdf)), so our metric means what a Finnish official would expect.

**Target time (the Goal 3 indicator)**: the strategy says "within the established target times" without giving numbers. Usable anchors: STM working group 2010, diagnosis and treatment within 6 weeks of referral (already in our project notes); Norway, 35/42 days from referral to chemotherapy or surgery/radiotherapy ([Norwegian study](https://hdl.handle.net/11250/2756752)). The new Finnish Lung Cancer Programme defines per-treatment time targets, but I couldn't find the numbers. **Ask a mentor.**

---

## 2. Calibrate, and derive capacity from observed waits

Public data doesn't say how many PET-CT or bronchoscopy slots a region has. We can still avoid making them up: take the arrival rate from incidence and case mix, take the observed waits above, and **fit capacities so the simulated waits match the observed ones**. Capacity then becomes a fitted parameter traceable to evidence, which answers master plan §6's "calibrated later" directly.

Pitch framing: "We fitted the baseline to Finnish observations: GP wait ≈ 2 wk, referral ≈ 2 wk, referral→diagnosis ≈ 8 wk, diagnosis→treatment 36–69 days. Here is simulated vs observed."

This sits alongside the Stokstad (Norway) check already planned. Stokstad tests the optimiser. The Finnish fit tests the baseline.

## 3. Robustness instead of point estimates

Every ledger entry has a range. Run the baseline and the optimised flowchart a few hundred times with parameters drawn from those ranges, then report:
- "Reordering beats baseline in X% of draws; median gain Y days (IQR …)"
- a tornado chart of which parameters move the result most

This turns "our data is synthetic" from a weakness into a demonstrated property: the recommendation doesn't depend on any one guessed number. It's also cheap, because it's just a loop over the existing simulator.

## 4. Equity gap without adding regions

You ruled out regional variation in the simulator. The brief's step 1 still needs a detected gap. Option: keep one region, but add **patient subgroups** whose disadvantage is documented, and report the gap between them:
- **Nurse-first vs doctor-first contact** (40–60% see a nurse first in Finland)
- **Non-specific vs alarm symptoms.** Non-specific presenters wait a median 34 days longer (Sewell, in capacity-vs-order-evidence.md). Haemoptysis appears in only ~a fifth of cases (Walter 2015)
- **Education.** Highly educated patients are 10–16% more likely to be diagnosed early (project notes)

The output is then "the gap between subgroups shrinks from A to B days under the new flowchart". That is an equity result produced by the simulator, not only cited.

Regional evidence for the pitch's problem slide, cited rather than simulated:
- Surgery share notably lower in Kainuu and Kymenlaakso. Drug therapy less often given in Lapland, Länsi-Uusimaa, Keski-Uusimaa, Vantaa–Kerava, Etelä-Karjala and Varsinais-Suomi ([Keuhkosyöpä Suomessa 2024](https://syoparekisteri.fi/assets/files/2024/12/Keuhkosyopa_Suomessa.pdf))
- That report also has **time from diagnosis to treatment by collaborative region** (its section 4.1). It's the best equity table we have, but I couldn't download it from here. **Someone should open it in a browser.**
- 5-year relative survival: women 25.6%, men 16.2% ([Syöpä 2023](https://syoparekisteri.fi/assets/themes/ssy3/factsheets/syopa_2023_tilastoraportti.html))

*Open question for you:* would a "parameter-file swap" count as regional variation for you, i.e. the same one-region simulator run once with a fast region's fitted waits and once with a slow region's? It would show a regional gap directly, but it bends your earlier decision, so it's your call.

## 5. Validation scorecard (ISPOR-SMDM types)

[Eddy et al. 2012](https://ispor.org/heor-resources/good-practices/article/model-transparency-and-validation) lists five validation types, external and predictive being the strongest. A one-slide scorecard:

| Type | What we do |
|---|---|
| Face validity | AZ mentor reviews flowchart and ledger (logged) |
| Verification | Unit tests: a single queue matches the analytic M/M/1 answer; Little's law holds; same seed gives the same run |
| Cross validity | Compare with published DES results (Welsh lung pathway, ~11 days removed) |
| External validity | Reproduce Finnish intervals (§2) and Stokstad's 40% |
| Predictive | Stokstad blind search lands near 80% (already planned) |

Optional appendix: the [STRESS-DES reporting checklist](https://ore.exeter.ac.uk/repository/handle/10871/40055) filled in. It costs little and simulation-literate judges recognise it.

**Decision model check, same spirit:** because the generator encodes published likelihoods, the trained model's probabilities can be compared with published PPVs (e.g. P(cancer | haemoptysis alone) should land near 2.4–7.5%). That makes the model's calibration evidence-based too.

## 6. Mentors as a source, tonight

The brief names "insights gathered from AstraZeneca mentors" as valid evidence. Bring three questions to the challenge Discord:
1. Is our flowchart structure realistic for a Finnish central hospital? (face validity)
2. What are the Finnish Lung Cancer Programme's time targets?
3. Typical waits for PET-CT, bronchoscopy/EBUS and the MDT cycle in their experience?

Log each answer in the ledger as grade C with name, role and date.

## 7. Outcomes: claim only what the evidence carries

- **Lead with the indicator itself**: share treated within target time. It's what Goal 3 measures, and we measure it directly.
- **Be careful converting days into deaths for lung cancer.** In Hanna et al. (BMJ 2020) lung surgery was HR 1.06 per 4-week delay, but [not statistically significant](https://oncology.medicinematters.com/mortality/treatment/meta-analysis-mortality-risk-cancer-treatment-delays/18575470). A [2025 lung-specific meta-analysis](https://link.springer.com/article/10.1007/s11357-025-01684-9) found pooled HR 1.00. The waiting-time paradox (sicker patients are treated faster) confounds raw data ([Hall et al.](https://discovery.ucl.ac.uk/10143598/1/Fisher_762.full.pdf)). The effect is probably largest in early-stage, surgically treatable disease ([Ost review](https://mdanderson.elsevierpure.com/en/publications/impact-of-delays-in-lung-cancer-treatment-on-survival)).
- So any survival translation should be limited to the curative-intent subgroup, shown as a range and labelled illustrative. Saying this on stage will build trust with an AZ medical audience.

## 8. Turn the gaps into a recommendation

The ledger entries we can't source are largely the data Finland doesn't collect: no national waiting-time statistics per cancer type, stage missing for about half of patients, MDT coverage not assessable from registries. That gives an actionable national-level proposal: *"the inputs this tool needs = the minimum dataset for the national lung cancer quality registry."* It ties the demo to the policy fix, and to the €400k registry cut.

## Considered and not worth it tonight
- **Synthea** (open synthetic EHR generator with a lung cancer module): it's US-centric, and wiring it in costs hours. Our cause-first generator plus the ledger is more transparent.
- **Pulling THL/Sotkanet APIs live**: general specialist-care waits are not cancer-specific. Cite them on the problem slide instead (e.g. HUS median 103 vs Etelä-Karjala 35 days, April 2023, all specialties: [THL via Verkkouutiset](https://www.verkkouutiset.fi/a/erikoissairaanhoidon-jonot-kasvoivat-edelleen-huhtikuussa/)).

---

## Prompt for Claude Code (if you want to hand this off)

> We're building a discrete-event simulator of the Finnish lung cancer diagnostic pathway for the AstraZeneca challenge at Junction 2026 (deadline Sunday 10:00). The judging asks that every claim be backed by a visible source, and data quality and transparency is 20% of the score. Our insights come from the simulator, so the goal of this session is to make the simulator's inputs and outputs traceable to evidence. Please read `docs/master_plan.md` first, and then the evidence-grounding notes (the parameter tables and ideas below). I'd like you to work in phases and think about each one from a few angles before moving on.
>
> **Phase 1: orient and plan.** Find where the simulator code currently lives. It may not be in this repo yet, so check the branches and ask if it can't be found. Map how parameters currently enter the simulation: hard-coded, config, or generated. Then write a short plan covering how an evidence ledger could fit the existing code with the least disruption, and what it would take. Consider a few shapes (a single YAML/CSV file, per-module configs, something else) and weigh them against how the UI will need to read sources. Share the plan before building.
>
> **Phase 2: gather and audit the evidence.** Using the parameter tables in the notes, build the ledger with value, plausible range, unit, source, URL, setting and an evidence grade (A: Finnish registry or meta-analysis; B: single or non-Finnish study; C: mentor input or assumption). While doing this, think about where a published number doesn't map cleanly onto how our simulator defines a step. Examples: test sensitivity measured in a different population, or intervals defined differently from THL's definitions. Flag those mismatches rather than forcing a fit. Also look at which simulator parameters have no source at all, and list them as explicit assumptions.
>
> **Phase 3: calibrate.** Consider fitting the parameters that have no public data, such as per-test capacity, so that the baseline reproduces the observed Finnish intervals in the notes. Note that the sources conflict on diagnosis-to-treatment (36–38 vs 65–69 days), so think about how to treat that range honestly. Evaluate a few fitting approaches and whether each makes sense within the time we have. Report simulated vs observed side by side.
>
> **Phase 4: robustness and validation.** Explore running baseline and optimised flowcharts across draws from the ledger's ranges. Report how often the recommendation still wins, and which parameters matter most. Add verification tests where analytic answers exist, such as a single queue against M/M/1 or Little's law. Consider also checking the decision model's predicted probabilities against the published PPVs in the notes.
>
> **Phase 5: reflect.** Look back over the work: which claims would a sceptical AZ oncologist challenge, which numbers carry the most weight, and what we should say on stage about limitations. Update `docs/master_plan.md` wherever a decision changed, so the team's agents stay in sync.
>
> Two things to keep in mind throughout. First, the equity gap may be shown through patient subgroups within the single region (nurse-first contact, non-specific symptoms). Second, for lung cancer the evidence linking treatment delay to mortality is weak, so it's worth thinking about what the outputs should and shouldn't claim.

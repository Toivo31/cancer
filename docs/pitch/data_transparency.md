# Data quality and transparency (E5)

Answers the OPEN item in master_plan section 8 (20% of the score). Numbers in double square brackets are filled by `fill_numbers.py` from `demo/data/demo_bundle.json` (run of [[bundle_date]]); the filled copy is in `filled/`.

## 1. The data is synthetic, and we say so

No real patient, hospital or decision data is used anywhere. Each simulated patient is drawn from a hidden condition (cancer, a commonly confused non-cancer condition, or nothing serious), and each test result is drawn from that condition using the test's sensitivity and specificity (`params/test_accuracy.yaml`, each row with its source). Cancer is kept rare so that aggressive pathways are not rewarded for free. The demo, video and deck carry the label "synthetic data" on every results screen.

Why this is acceptable: the brief asks for a working system; real Finnish pathway data is not obtainable in a weekend. What we offer in its place is traceability and a check against a published pathway, and a design that runs unchanged on real logs.

## 2. Every parameter is traceable

- Each number in a scenario file carries a `source:` key pointing to an entry in `params/sources.yaml`, which records publication, page or table, and the value as printed.
- Numbers with no published source are labelled `source: assumption`. The demo's "Sources and assumptions" screen lists both groups: [[parameter_count]] parameters, [[sourced_count]] sourced and [[assumption_count]] marked as assumptions. The counts are read from the bundle, not typed.
- A judge can click from any result to the parameters behind it.

| Parameter group | Source type | Status |
|---|---|---|
| Pathway steps, order and waits (Norwegian scenario) | Stokstad 2019 | published; read from the abstract and the tables we could access, so two overlaps in the chain of steps are calibrated (decision D16) and labelled `assumption` |
| Finnish step waits (first appointment, specialist, diagnosis) | IHE dashboard citing Khalife 2025 | published survey modes, converted to booking leads by us |
| Finnish capacities (CT, clinics, PET-CT, treatment slots) | none found | **assumption**, calibrated to reproduce the Finnish waits |
| Test sensitivity and specificity | `params/test_accuracy.yaml`, one source per row | published, ranges from several studies |
| Lung cancer share among chest-symptom presenters | BRADLEY2021 and KOO2023, see `docs/finland_scenario.md` | published for the symptomatic cohorts; the synthetic county has [[f_prevalence]]% |
| Share of non-specific presenters and their lower detection rates | none for Finland | **assumption** (decision D9); size of the equity gap follows from it |
| Share seeing a nurse first | University of Helsinki (40-60%) | published range |

## 3. Calibration against Stokstad 2019

The check is described in `docs/validation.md`. We fit only the parameters the paper does not report, on the observed pathway only; the other two flowcharts are predictions. [[val_accepted]] of [[val_grid]] grid points reproduce the observed pathway (share [[val_target_share]]% plus or minus [[val_target_tol]] points, median [[val_pub_median]] days).

[[s_validation_table]]

Across the [[val_accepted]] accepted parameter sets the predicted share for the authors' pathway is [[val_opt_min]]-[[val_opt_max]]% (published [[s_pub_opt]]%, 95% interval [[val_pub_opt_ci]]), and for faster PET-CT only [[val_fast_min]]-[[val_fast_max]]% (published [[s_pub_fast]]%, interval [[val_pub_fast_ci]]). Sampling procedures: simulated ratio optimal to observed [[val_samp_ratio]] against [[val_samp_pub_opt]]/[[val_samp_pub_obs]] = [[val_samp_pub_ratio]] published.

**Where it does not match.** The faster-PET-only result is over-predicted by about [[s_fast_over_pp]] points. We think our model lets PET-CT hold patients back more often than it did in the real cohort, because we do not model delays such as incomplete workup at the tumour board or correlated delays within a patient. That makes our order-versus-capacity conclusion conservative, but it is an explanation, not something we tested.

**What was assumed.** Two structural overlaps the paper does not report (decision D16), plus the test results of individual patients. The paper's [[s_pub_opt]]% is itself a model estimate from re-timing real patients, so we compare shares, not individuals. All of the paper's patients already had cancer, so the check covers specialist care, not primary-care filtering.

## 4. Proposal from revealed information, acceptance by simulated truth

- **Proposing.** The search proposes a change using only what steps revealed in the run log (results, waits, queues), never the hidden condition. It reasons over groups of patients, because judging a test patient by patient after the fact is biased (later tests are run on patients who failed earlier ones).
- **Accepting.** A proposed change is kept only if a rerun of the same patients (common random numbers) shortens time to treatment without more missed cancers and within the other guardrails. That rerun uses the simulated truth, which in real life nobody has. In real life the acceptance step is a pilot.
- **Consequence.** Our claim is "this change is worth piloting", not "this change works in Finland".
- **Overfitting.** Best-of-many on the same patients selects on noise (decision D6). We accept on a training cohort and report on held-out cohorts the search never saw. The gap between training and held-out is shown below.

## 5. Held-out reporting

| Run | Training cohort, after change | Held-out, after change | Selection optimism (training minus held-out, pp) |
|---|---|---|---|
| Norwegian, blind search with faster scanner | [[s_opt_train]]% | [[s_opt_share]]% | [[s_opt_optimism_pp]] |
| Norwegian, blind search without new equipment | [[s_noeq_train]]% | [[s_noeq_share]]% | [[s_noeq_optimism_pp]] |
| Finnish synthetic county, target [[f_target]] d | [[f_train_opt]]% | [[f_share_opt]]% | [[f_optimism_pp]] |

Held-out cohorts hold about [[s_n]] simulated patients (Norwegian) and about [[f_n]] (Finnish) each. Headline figures in the video and deck are the held-out numbers. The optimism column is as reported by the optimiser (it compares the predicted with the rerun result); a negative value means the held-out result was higher than the training one.

Finnish guardrails on the held-out cohort (suggested change against baseline): missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort, tests per patient [[f_tests_base]] to [[f_tests_opt]], median days for non-cancer patients to leave the pathway [[f_noncancer_base]] to [[f_noncancer_opt]]. Seed-to-seed spread is not yet in the bundle; `docs/sensitivity_*.json` ([[sens_files]]) will carry it when it exists.

## 6. Known limitations

- Synthetic data; capacities for Finland are assumptions fitted to published waiting ranges.
- One region, one disease (lung cancer), one flowchart family; no differences between counties.
- One validation study, from one Norwegian centre with 100 patients; its 80% is a model estimate.
- Targets: the Norwegian check uses the study's 42 days. The Finnish scenario clock starts at first contact, where every flowchart is at 0% within 42 days, so the Finnish headline uses a **provisional [[f_target]]-day target (decision D20, team call pending)**. The Finnish statutory limits are 21 days to assessment and 180 days to treatment ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)); we found no Finnish first-contact-to-treatment target. We do not claim to match the official Finnish monitor.
- The Norwegian calibration fits two overlaps that the paper does not report (D16); the faster-PET-only prediction misses by about [[s_fast_over_pp]] points.
- The Finnish held-out result rests on two held-out cohorts and a single optimiser run; no sensitivity analysis is in the bundle yet.
- The decision model is benchmarked separately and does not drive the demo runs (a rule policy does, D4, D11).
- No simulated doctors: the starting flowchart is hand-written and the policy is rule-based (decisions D4, D11).
- Equity groups are modelled assumptions (D9); see the equity note for what is and is not sourced.
- Several sources could not be read in full here: Stokstad full text, Khalife 2025, Toronto and radiotherapy-review papers, the Finnish Cancer Societies report. Where we relied on an abstract or a news summary the source list says so.
- Safety: a clinician approves every proposal; a reserved treatment slot while tests finish does not mean treatment starts before diagnosis.

# Data quality and transparency (E5)

Answers the OPEN item in master_plan section 8 (20% of the score). Numbers in double square brackets are filled by `fill_numbers.py` from `demo/data/demo_bundle.json` (run of 2026-11-14); the filled copy is in `filled/`.

## 1. The data is synthetic, and we say so

No real patient, hospital or decision data is used anywhere. Each simulated patient is drawn from a hidden condition (cancer, a commonly confused non-cancer condition, or nothing serious), and each test result is drawn from that condition using the test's sensitivity and specificity (`params/test_accuracy.yaml`, each row with its source). Cancer is kept rare so that aggressive pathways are not rewarded for free. The demo, video and deck carry the label "synthetic data" on every results screen.

Why this is acceptable: the brief asks for a working system; real Finnish pathway data is not obtainable in a weekend. What we offer in its place is traceability and a check against a published pathway, and a design that runs unchanged on real logs.

## 2. Every parameter is traceable

- Each number in a scenario file carries a `source:` key pointing to an entry in `params/sources.yaml`, which records publication, page or table, and the value as printed.
- Numbers with no published source are labelled `source: assumption`. Counted from the scenario files the engine reads (every `source:` tag, read by `fill_numbers.py`): the Finnish scenario has 65 tagged inputs, 21 sourced and 44 assumptions; the Norwegian scenario has 26 tags, 23 sourced and 3 assumptions (more Norwegian parameters are calibrated, see section 3). The Finnish assumptions cover every server capacity, every booking lead and urgent booking lead, the GP, nurse and specialist decision probabilities and most prevalences.
- The demo's "Sources and assumptions" screen and `docs/parameters.md` list a wider table (131 rows, 113 sourced, 18 assumptions). Read it as evidence and calibration targets (published intervals, survival, incidence counts), not as the count of simulator inputs that are sourced.
- A judge can click from any result to the parameters behind it.

| Parameter group | Source type | Status |
|---|---|---|
| Pathway steps, order and waits (Norwegian scenario) | Stokstad 2019 | published; read from the abstract and the tables we could access, so two overlaps in the chain of steps are calibrated (decision D16) and labelled `assumption` |
| Finnish step waits (first appointment, specialist, diagnosis) | IHE dashboard citing Khalife 2025 | published survey modes, converted to booking leads by us |
| Finnish capacities (CT, clinics, PET-CT, treatment slots) and all booking leads, urgent booking leads included | none found | **assumption**, calibrated to reproduce the Finnish waits; per-step waits are mostly booking leads, with queueing adding a smaller part |
| Test sensitivity and specificity | `params/test_accuracy.yaml`, one source per row | published, ranges from several studies |
| Lung cancer share among chest-symptom presenters | BRADLEY2021 and KOO2023, see `docs/finland_scenario.md` | published for the symptomatic cohorts; the synthetic county has 1.6% |
| Share of non-specific presenters and their lower detection rates | none for Finland | **assumption** (decision D9); size of the equity gap follows from it |
| Share seeing a nurse first | University of Helsinki (40-60%) | published range |

## 3. Calibration against Stokstad 2019

The check is described in `docs/validation.md`. We fit only the parameters the paper does not report, on the observed pathway only; the other two flowcharts are predictions. 11 of 192 grid points reproduce the observed pathway (share 40% plus or minus 4 points, median 46.5 days).

| Flowchart | Published (Stokstad 2019) | Our simulation (held-out) | Verdict |
|---|---|---|---|
| Observed pathway | 40% within 42 d | 40% (fitted) | fitted to this number |
| Faster PET-CT only (7 d) | 48% (not significant) | 60% | we over-predict |
| Authors' reordered pathway | 80% | 80% | predicted, not fitted: matches |

Across the 11 accepted parameter sets the predicted share for the authors' pathway is 78-86% (published 80%, 95% interval 72-87), and for faster PET-CT only 55-67% (published 48%, interval 39-58). Sampling procedures: simulated ratio optimal to observed 0.82 against 92/112 = 0.82 published.

**Where it does not match.** The faster-PET-only result is over-predicted by about 12 points. We think our model lets PET-CT hold patients back more often than it did in the real cohort, because we do not model delays such as incomplete workup at the tumour board or correlated delays within a patient. That makes our order-versus-capacity conclusion conservative, but it is an explanation, not something we tested.

**Caveat on "predicted, not fitted".** The calibrated observed practice (PET-CT ordered when the referral is triaged, fitted at the grid edge) is carried into the authors' pathway. With PET-CT ordered at triage for 100%, 50% or 0% of patients, the simulated authors' pathway gives 80%, 73% or 66% (the last is PET-CT ordered at the first visit, as the paper describes). Three of the five calibrated parameters sit at the edge of the grid. We keep the word "predicted" but not as an independent validation of the 80%.

**What was assumed.** Two structural overlaps the paper does not report (decision D16), plus the test results of individual patients. The paper's 80% is itself a model estimate from re-timing real patients, so we compare shares, not individuals. All of the paper's patients already had cancer, so the check covers specialist care, not primary-care filtering.

## 4. Proposal from revealed information, acceptance by simulated truth

- **Proposing.** The search proposes a change using only what steps revealed in the run log (results, waits, queues), never the hidden condition. It reasons over groups of patients, because judging a test patient by patient after the fact is biased (later tests are run on patients who failed earlier ones).
- **The menu.** The search chooses among about 69 single changes in the Norwegian scenario (the Finnish search evaluated 21). The Norwegian menu included each of the authors' changes as one edit, and the list of clinically needed steps was hand-written; the search was not told which edits the authors made, but this is a blind search over a menu we wrote. Its fourth change plans tissue sampling when the referral is triaged, before a specialist has seen the patient, and needs a clinical check.
- **Accepting.** A proposed change is kept only if a rerun of the same patients (common random numbers) shortens time to treatment without more missed cancers and within the other guardrails. That rerun uses the simulated truth, which in real life nobody has. In real life the acceptance step is a pilot.
- **Consequence.** Our claim is "this change is worth piloting", not "this change works in Finland".
- **Overfitting.** Best-of-many on the same patients selects on noise (decision D6). We accept on a training cohort and report on held-out cohorts the search never saw. The gap between training and held-out is shown below.

## 5. Held-out reporting

| Run | Training cohort, after change | Held-out, after change | Selection optimism (training minus held-out, pp) |
|---|---|---|---|
| Norwegian, blind search with faster scanner | 88% | 88% | 1.7 |
| Norwegian, blind search without new equipment | 66% | 67% | -0.6 |
| Finnish synthetic county, target 90 d | 29% | 33% | -0.2 |

Held-out cohorts hold about 1 000 simulated patients (Norwegian) and about 16 177 (Finnish) each. Headline figures in the video and deck are the held-out numbers. The optimism column is as reported by the optimiser (it compares the predicted with the rerun result); a negative value means the held-out result was higher than the training one.

Finnish guardrails on the held-out cohort (suggested change against baseline; the tissue-confirmed guardrail is active because bronchoscopy and needle biopsy are marked as confirming): missed cancers 27.5 to 27.5 per cohort, tests per patient 0.41 to 0.41, median days for non-cancer patients to leave the pathway 16.8 to 16.8. Seed-to-seed spread is not in the held-out numbers. Sensitivity runs (sensitivity_external_rapid_ct.json, sensitivity_external_v4.json, sensitivity_finland_equity.json, sensitivity_finland_lung.json, sensitivity_finland_lung_capacity_control.json, sensitivity_stokstad.json, `docs/sensitivity.md`) vary the assumed inputs for the hand-written order-together pathway, not for the two accepted Finnish reorders. Per-cohort ranges are wide (cohorts of about 261 cancers).

## 6. Known limitations

- Synthetic data; capacities for Finland are assumptions fitted to published waiting ranges.
- One region, one disease (lung cancer), one flowchart family; no differences between counties.
- One validation study, from one Norwegian centre with 100 patients; its 80% is a model estimate.
- Targets: the Norwegian check uses the study's 42 days. The Finnish scenario clock starts at first contact, where every flowchart is at 0% within 42 days, so the Finnish headline uses a **provisional 90-day target (decision D20, team call pending)**. The Finnish statutory limits are 21 days to assessment and 180 days to treatment ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)); we found no Finnish first-contact-to-treatment target. We do not claim to match the official Finnish monitor.
- The Norwegian calibration fits two overlaps that the paper does not report (D16); the faster-PET-only prediction misses by about 12 points.
- The Finnish held-out result rests on two held-out cohorts and a single optimiser run. The sensitivity analysis covers the hand-written order-together comparison, not the accepted reorders. The urgent-booking finding (18% / 44% / 61% at 0 / 50 / 100% of the assumed lead reduction) is conditional on assumed booking leads and is not part of the headline.
- Guardrails: the Norwegian missed-cancer check is vacuous (every patient has cancer, no discharge exit). GP-first was blocked on the training patients by half a missed cancer per cohort, which is noise-level; on unseen patients it looked neutral to positive, so it needs a paired test.
- The decision model is benchmarked separately and does not drive the demo runs (a rule policy does, D4, D11). In the simulator loop it matched the hand-written rule, and showed that per-patient choices overload a shared queue unless queue state is visible.
- No simulated doctors: the starting flowchart is hand-written and the policy is rule-based (decisions D4, D11).
- Equity groups are modelled assumptions (D9); see the equity note for what is and is not sourced.
- Several sources could not be read in full here: Stokstad full text, Khalife 2025, Toronto and radiotherapy-review papers, the Finnish Cancer Societies report. Where we relied on an abstract or a news summary the source list says so.
- Safety: a clinician approves every proposal; a reserved treatment slot while tests finish does not mean treatment starts before diagnosis.

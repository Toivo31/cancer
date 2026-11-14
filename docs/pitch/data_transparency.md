# Data quality and transparency (E5)

Answers the OPEN item in master_plan section 8 (20% of the score). Numbers in `[[ ]]` are filled from the final run; do not publish with placeholders left.

## 1. The data is synthetic, and we say so

No real patient, hospital or decision data is used anywhere. Each simulated patient is drawn from a hidden condition (cancer, a commonly confused non-cancer condition, or nothing serious), and each test result is drawn from that condition using the test's sensitivity and specificity. Cancer is kept rare so that aggressive pathways are not rewarded for free. The demo, video and deck carry the label "synthetic data" on every results screen.

Why this is acceptable: the brief asks for a working system; real Finnish pathway data is not obtainable in a weekend. What we offer in its place is traceability and a check against a published pathway, and a design that runs unchanged on real logs.

## 2. Every parameter is traceable

- Each number in a scenario file carries a `source:` key pointing to an entry in `params/sources.yaml` (built by the parameters track), which records publication, page or table, and the value as printed.
- Numbers with no published source are labelled `source: assumption` and listed in the table below. The final list is generated from the files, not written by hand: `[[assumption_count]]` assumptions out of `[[parameter_count]]` parameters.
- The demo has a "Sources and assumptions" screen listing both groups. A judge can click from any result to the parameters behind it.

| Parameter group | Source type | Status |
|---|---|---|
| Pathway steps and order (Norwegian scenario) | Stokstad 2019 | published; read from abstract, full text blocked in our environment, so `[[stokstad_fulltext_check]]` |
| PET-CT wait, other step waits | Stokstad 2019 and others | published |
| Finnish step waits (first appointment, specialist, diagnosis) | IHE dashboard citing Khalife 2025 | published ranges, converted to distributions by us |
| Finnish capacities (CT, clinics, tumour board slots) | none found | **assumption**, calibrated to reproduce the Finnish waits |
| Test sensitivity and specificity | `[[sens_spec_sources]]` | to be filled by parameters track |
| Cancer prevalence among referred patients | `[[prevalence_source]]` | to be filled |
| Share of non-specific presenters | none for Finland | **assumption** |
| Share seeing a nurse first | University of Helsinki (40-60%) | published range |

## 3. Calibration against Stokstad 2019

What the paper provides (verified from the abstract): 100 stage I-II patients, 40% treated within 42 days, median 20.5 days from PET-CT referral to report, 48% with the 7-day PET-CT wait (p = 0.254), 80% with the reordered pathway (p < 0.001), sampling procedures 112 to 92. Causes of delay: late PET-CT referral (27 patients), late exercise test (16), repeat sampling after failed bronchoscopy (15), further tests after PET-CT (11). [Abstract](https://doaj.org/article/4acaa56fe36f47fea13458f6355b5944).

| Check | Paper | Our run | Matched? |
|---|---|---|---|
| Share treated within 42 days, observed pathway | 40% | `[[stokstad_sim_share]]` | `[[match_1]]` |
| Median PET-CT referral to report | 20.5 days | `[[stokstad_sim_pet_median]]` | input, so matches by construction |
| Share with PET-CT wait of 7 days only | 48% | `[[stokstad_sim_pet7]]` | `[[match_2]]` |
| Share with reordered pathway | 80% | `[[stokstad_sim_opt]]` | `[[match_3]]` |
| Sampling procedures per patient, observed vs reordered | 112 to 92 per 100 | `[[sim_sampling]]` | `[[match_4]]` |

What was assumed, because the abstract does not give it: step durations other than PET-CT, the test results of individual patients, the median time to treatment (the master plan quotes 46.5 days, which we could not confirm from the abstract; use only if checked against full text), and the pathology report time (master plan: 4.5 days, also not confirmed). The real paper's 80% is itself a model estimate from re-timing real patients; our simulator re-draws patients, so we compare shares, not individuals.

The check covers specialist care only: all of the paper's patients already had cancer, so primary-care filtering is not tested by it.

## 4. Proposal from revealed information, acceptance by simulated truth

This is the honest part and we state it in the demo.

- **Proposing.** The search proposes a change using only what steps revealed in the run log (results, waits, queues), never the hidden condition. It reasons over groups of patients, because judging a test patient by patient after the fact is biased (later tests are run on patients who failed earlier ones).
- **Accepting.** A proposed change is kept only if a rerun of the same patients shortens time to treatment without more missed cancers. That rerun uses the simulated truth, which in real life nobody has. The acceptance step has no real-world equivalent without a pilot.
- **Consequence.** In practice the acceptance rerun would be a monitored pilot in one county measured by the same indicators (recommendation actions 4 and 5). Our claim is therefore "this change is worth piloting", not "this change works in Finland".
- **Overfitting.** Best-of-many on the same patients selects on noise (decisions D6). We accept on a training cohort with common random numbers and report on a held-out cohort the search never saw.

## 5. Held-out reporting

| Metric | Training cohort | Held-out cohort |
|---|---|---|
| Share treated within target, base | `[[train_base]]` | `[[test_base]]` |
| Share treated within target, changed | `[[train_opt]]` | `[[test_opt]]` |
| Median days to treatment, base to changed | `[[train_days]]` | `[[test_days]]` |
| Missed cancers per 1,000 | `[[train_missed]]` | `[[test_missed]]` |
| Tests per patient | `[[train_tests]]` | `[[test_tests]]` |
| Waits for non-cancer patients | `[[train_noncancer]]` | `[[test_noncancer]]` |
| Number of seeds and spread (min-max) | `[[n_seeds]]` | `[[seed_range]]` |

Headline figures in the video and deck are the held-out column. If held-out and training differ by more than `[[tolerance]]` we say so.

## 6. Known limitations

- Synthetic data; capacities for Finland are assumptions fitted to published waiting ranges.
- One region, one disease (lung cancer), one flowchart family; no differences between counties.
- One validation study, from one Norwegian centre with 100 patients; its 80% is a model estimate.
- The target is 42 days from the Norwegian study; the Finnish statutory limits are 21 days to assessment and 180 days to treatment ([IHE](https://ihe.se/app/uploads/2026/04/IHE-Cancer-Dashboard-Finland_.pdf)). We do not claim to match the official Finnish monitor.
- No simulated doctors: the starting flowchart is hand-written and the policy is rule-based (decisions D4, D11).
- Equity groups are modelled assumptions (D9); see the equity note for what is and is not sourced.
- Several sources could not be read in full here: Stokstad full text, Khalife 2025, Toronto and radiotherapy-review papers, the Finnish Cancer Societies report. Where we relied on an abstract or a news summary the source list says so.
- Safety: a clinician approves every proposal; a reserved treatment slot while tests finish does not mean treatment starts before diagnosis.

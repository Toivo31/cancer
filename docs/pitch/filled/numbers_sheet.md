# Numbers sheet: every number that is said aloud or shown

This is the one place to check or change a number. Every other pitch file (`deck.md`, `submission.md`, `qa.md`, `video_script.md`, `data_transparency.md`, `recommendation.md`, `equity.md`, `platform_framing.md`) must agree with it.

How it is kept true: this file is a template like the others. Numbers in double square brackets are read from result files by `fill_numbers.py` (`python3 docs/pitch/fill_numbers.py`), so **read `filled/numbers_sheet.md`**, which is regenerated after every run. Only the parts that no result file holds (published numbers, assumptions, the pending items in section P) are typed by hand. If a result changes, rerun the script, then reread the sentence in the third column: a sentence that is no longer true must be rewritten here first, then in the other files.

Status words: **fitted** (we tuned the model to hit it), **predicted** (computed with the fitted model, not tuned to it), **simulated** (a result of a simulation run in a synthetic world), **published** (printed in a source), **assumption** (our choice, no source). **H** marks a headline number.

Wording rules that apply to every row: all patients are synthetic; say "in our synthetic Finnish county", never "in Finland"; never say "predicted exactly" or "matches"; the older "78 to 86%" must not appear.

## A. Norway validation (Stokstad et al. 2019: 100 patients, one hospital, one centre)

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file (command) | Status |
|---|---|---|---|---|---|
| A1 **H** | 40% within 42 days, observed pathway | "Fitted only to today's order, our model gives 40% treated within 42 days; the paper reports 40%." | Accepted settings 36 to 43%; 100-patient cohorts 30 to 51%; published 95% interval 31-50% | `docs/validation_results.json` (`python -m pathway_sim.calibrate scenarios/stokstad.yaml --n 2000 --out docs/validation_results.json`); bundle `demo/data/demo_bundle.json`; `docs/ranges.md` | fitted |
| A2 **H** | 80% authors' reordered pathway, best fit | "At our best fit the authors' reordered pathway gives 80%; they published 80%, which is itself a model estimate." | One point of a band, see A3. 100-patient cohorts 72 to 87%; published interval 72-87% | bundle `demo/data/demo_bundle.json` (`python -m pathway_sim demo`); `docs/ranges.md` | predicted (not fitted) |
| A3 **H** | 62 to 86%, typically about 75%, authors' pathway across all 184 settings | "Across all 184 settings that fit the observed pathway, the authors' pathway is predicted at 62 to 86%, typically about 75%." | Middle 80% of settings: 66 to 82%. Band is 24 points wide | `docs/review_checks/norway_grid_extension.json`; `docs/validation.md` "Robustness" (`python scripts/norway_robustness.py`; `--recompute` about 40 min) | predicted |
| A4 | 64% of settings inside the published interval | "About two thirds (64%) of those settings fall inside the paper's own interval of 72-87%." | Count of 184 settings, recounted by `fill_numbers.py` from the grid table | `docs/review_checks/norway_grid_table.json` (same acceptance rule as the calibration) | predicted |
| A5 **H** | 184 of 184 settings keep the ranking | "In all 184 settings, the authors' reordering beats the faster scanner alone, which beats today's pathway." | Also holds at 1028 of 1043 predicted grid points | `docs/review_checks/norway_ranking.json` | predicted |
| A6 | +24 to +47 points gain from reordering | "Reordering adds 24 to 47 points over today; the paper's model estimate is 40." | Magnitudes are not supported to better than about plus or minus 12 points | `docs/review_checks/norway_grid_extension.json`, `norway_ranking.json`; `docs/validation.md` section 6 | predicted |
| A7 **H** | 60% faster PET-CT only, best fit (published 48%) | "For a faster scanner alone we predict 60% at our best fit and the paper reports 48% (not statistically significant): we over-predict." | Across settings 50 to 74% (median 60.5%); only 34% inside the published 39-58% | bundle; `docs/review_checks/norway_grid_extension.json` | predicted (a miss) |
| A8 | 66% authors' pathway if PET-CT is ordered only at the first visit | "At our best fit, with PET-CT ordered only at the first visit as the paper describes, the authors' pathway gives 66%; ordered at triage for half of patients, 73%; for all, 80%." | One best-fit setting. This is why the 80% is not independent of the fitted practice | `docs/review_checks/stokstad_pet_triage_result.json` (`docs/review_checks/stokstad_authors_pathway_vs_pet_triage.py`) | predicted |
| A9 | 0.82 sampling procedures, optimal to observed (published 92 of 112 = 0.82) | "The reordered pathway needs 0.82 times as many sampling procedures as today in our model; the paper's figure is 0.82." | Checked on the first grid only; not rechecked on the extended grid | `docs/validation_results.json` | predicted |
| A10 | 11 of 192 first-grid points accepted; 184 of 1920 on the extended grid | "We first searched 192 settings; widening the search to 1920 settings showed that 184 of them fit the observed pathway equally well." | Targets (share and median) act as one constraint (correlation about -0.81); four of five unreported inputs are close to free | `docs/validation_results.json`; `docs/review_checks/norway_grid_extension.json`, `norway_identifiability.json` | fitted |
| A11 | "78 to 86%" (first grid, 78 to 86% here) | **Do not use as a headline.** It is the top corner of the extended band. | | `docs/validation.md` section 1 | retired |

## B. Norway optimiser (a search over a menu of about 69 single changes that we wrote and that contained the authors' changes)

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file (command) | Status |
|---|---|---|---|---|---|
| B1 **H** | 88% with the faster scanner | "Searching from the observed pathway with the faster scanner, the optimiser reaches 88%, against the authors' 80%; it finds the authors' three changes plus a fourth that needs a clinical check." | 100-patient cohorts 81 to 94%; across the first-grid accepted sets 86 to 93%; selection optimism 1.7 points. Best-fit setting only (see P1) | bundle; `docs/ranges.md` (`python3 docs/evidence_checks/ranges_norway.py`) | simulated |
| B2 **H** | 67% with no new equipment | "With no new equipment the same search reaches 67%." | 100-patient cohorts 56 to 75%; across the first-grid accepted sets 56 to 70% (the less certain of the two); optimism -0.6 points. Best-fit setting only (see P1) | bundle; `docs/ranges.md` | simulated |
| B3 | about 69 candidate single changes | "It chose from a menu of about 69 single changes that contained each of the authors' changes as one edit; it was not told which." | | bundle (`optimiser.candidates_evaluated`) | simulated |
| B4 | the fourth change: plan tissue sampling at referral triage | "The fourth change, planning tissue sampling when the referral is triaged, before a specialist has seen the patient, was not in the paper and needs a clinical check." The lead over the authors comes from it. | See P2 for the result without it | bundle; `docs/decisions.md` D18 | simulated |
| B5 | median 27 days (faster scanner), 37 days (no new equipment), 46 days (today) | "Median days to treatment: 46 today, 37 with no new equipment, 27 with the faster scanner." | Best-fit setting | bundle | simulated |

## C. Finland: synthetic county, held-out patients, provisional 90-day target (D20)

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file (command) | Status |
|---|---|---|---|---|---|
| C1 **H** | 18% today to 33% within 90 days | "In our synthetic Finnish county, two reorders with no new equipment take the share treated within 90 days from 18% to 33%." Say "synthetic" and "two held-out cohorts" | Today 14 to 25%, suggested 24 to 42% across 12 cohorts; quote the gain with it | bundle `demo/data/demo_bundle.json`; `docs/ranges.md` | simulated |
| C2 **H** | gain 9 to 19 points (mean 15) | "Across 12 cohorts of the same size the gain is 9 to 19 points and positive in 12 of 12." | Single-seed gain varies by about 4 points | `docs/ranges_finland.json` (`python3 docs/evidence_checks/ranges_finland.py`) | simulated |
| C3 | 102 to 94 days median | "Median days from first contact to treatment: 102 today, 94 with the two reorders." | Today 99 to 108, suggested 92 to 101 across cohorts | bundle; `docs/ranges.md` | simulated |
| C4 | 90-day target | "The 90-day target is our provisional choice; at the Norwegian 42 days every Finnish flowchart is at 0%. The Finnish statutory limits are 21 days to assessment and 180 days to treatment." | | `scenarios/finland_lung.yaml`; `docs/decisions.md` D20 | assumption |
| C5 | missed cancers 27.5 to 27.5 per cohort; tests per patient 0.41 to 0.41; non-cancer exit 16.8 to 16.8 days | "The two reorders leave missed cancers, tests per patient and the waits of patients without cancer unchanged." | Cohort has about 261 cancers | bundle | simulated |
| C6 | 31% same extra capacity, today's order; 54% hand-written order-together (needs 3 PET-CT slots) | "The same extra CT and PET-CT capacity with today's order reaches 31%; a hand-written order-together pathway reaches 54% but needs 3 PET-CT slots." | | bundle | simulated |
| C7 | conditional 18% / 44% / 61% | "Urgent booking for every referred patient gives 18%, 44% or 61% if none, half or all of an assumed booking-lead reduction holds." Never as a result or a headline | Entirely set by assumed urgent booking leads | bundle; `docs/review.md` B1; `docs/master_plan.md` | assumption |
| C8 | vague symptoms 13% to 26%; alarm 27% to 50%; gap in points widens (13.6 to 24.6); gap in median days narrows (11.2 to 9.9) | "Under our assumptions both groups gain; the gap in points widens and the gap in days narrows. The group difference is our assumption (D9)." Never "the gap closes" | 181 and 80 cancers per cohort in the two groups | bundle | simulated (groups assumed) |
| C9 | 87% of days are waiting; stages detection 30, referral 17, diagnosis 23, treatment start 21 days | "In our synthetic baseline, 87% of the days are waiting (mostly booking time calibrated to published waits), 30 days of them before a referral." | Per-step waits are calibrated, not an emergent queue result (`docs/booking_vs_queue.md`) | bundle | simulated |
| C10 | one more slot: +9.7 points at the PET-CT scanner; next +3.6; rest at most +1.5 | "One more slot at the busiest scanner adds 9.7 points; the rest add at most 3.6." | One seed; `docs/capacity_probe.md` | bundle; `docs/capacity_probe.md` | simulated |
| C11 | gain positive in 26 of 26 one-at-a-time changes; in 100% of 16 joint draws (8 to 21 points) | "The gain stays positive when each of 26 assumptions is varied; it nearly vanishes if CT capacity is one slot lower." | One seed per variant | `docs/ranges_finland.json`; `docs/ranges.md` | simulated |
| C12 | 49 input blocks: 9 sourced, 40 assumptions (Finland); 25, 22 and 3 (Norway) | "Of 49 inputs in the Finnish scenario, 9 cite a source; every capacity and booking lead is an assumption." | | `docs/ledger.md` (`python3 params/ledger.py`) | assumption |
| C13 | -0.2 points selection optimism, Finland | "Held-out patients did slightly better than the training patients (optimism -0.2 points)." | | bundle | simulated |

## D. Published context (not ours; always attribute)

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file | Status |
|---|---|---|---|---|---|
| D1 | 40% / 48% / 80% within 42 days | "In the Norwegian study, 40% started treatment within 42 days; re-timing with a faster PET-CT gave 48% (not significant); the authors' reordering would give 80%, a model estimate." | Intervals 31 to 50, 39 to 58, 72 to 87 | `docs/pitch/evidence_brief.md`, section 4 (Stokstad 2019) | published |
| D2 | 17% against 27 to 30% five-year survival, men | "Five-year relative survival in lung cancer in men is 17% in Finland against 27 to 30% in Denmark, Norway and Sweden." | NORDCAN 2019-2023 | `docs/pitch/evidence_brief.md`, section 1 (IHE dashboard) | published |
| D3 | first appointment about 14 days against 2 to 7; 40 to 60% see a nurse first; under 10% of primary-care units can perform CT | "A health-centre appointment takes about 14 days against 2 to 7 elsewhere in the Nordics." | One survey source (Khalife 2025, not read in full) | `docs/pitch/evidence_brief.md`, section 3 | published |

## E. Patient engine and primary-care loop (mechanism, not results)

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file (command) | Status |
|---|---|---|---|---|---|
| E1 | 500 template-written cards | "500 synthetic patient cards written from templates (library L_0dbfc37e2e45d8d4)." | Audit 38 of 38; stratified mix, not realistic prevalence | `libraries/ref500.md`, `libraries/ref500/manifest.json` (`python -m patient_engine library-info libraries/ref500`) | simulated |
| E2 | 35 model-written cards in 2 libraries (count at freeze) | "35 cards written by a language model so far, all synthetic; they pass the automatic audit, but the independent review found that report wording gives away false alarms, and a fix and regeneration are in progress." Never "no leaks". Counts and ids change on regeneration (see P3, P6) | Count is read from `libraries/*/manifest.json`; libraries that are not committed are not counted | `libraries/*/manifest.json` | simulated |
| E3 | 11 conditions, 42 hidden variables, 26 tests; 279 of 388 catalogue entries are tagged assumption (109 cite a source) | "The catalogue is a draft that no clinician has read; most of its numbers are our assumptions." | | `catalogue/lung-primary-care/*.yaml` (counted by `fill_numbers.py` as `demo/export_start.py` does; the older "177 of about 260" in `libraries/ref500.md` is out of date) | assumption |
| E4 | fails 7 of 8 consistency checks | "The primary-care loop is a mechanism with placeholder decision tables; it does not yet reproduce the calibrated chain (7 of 8 checks fail), so we show it as a mechanism, not a result." | Intervals are wide (about 45 cancers a seed). If the lane that tunes the loop passes more checks, this row and every sentence that quotes it change | `docs/review_checks/encounter_results.json`; `docs/encounter_results.md` (`python scripts/encounter_report.py`, about 110 s) | simulated |
| E4b | do not quote the encounter page or start page numbers (about 25 to 29% within 90 days, 28 days to referral) | Quote only `encounter_results.json` numbers (E4, E5). The demo page is a single illustration run without warm-up and disagrees with the report (`docs/review_w7.md` M2) | | `demo/data/encounter_bundle.js` vs `docs/review_checks/encounter_results.json` | not for use |
| E5 | median 37 days from first contact to referral in the loop | Only with the words "with placeholder decisions" and "mechanism, not a Finnish estimate". Prefer not to say it aloud. | 7 to 67 days (95% interval over 4 seeds) | `docs/encounter_results.md` section 3 | simulated (placeholder decisions) |

## E2. Context claims with known limits

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file | Status |
|---|---|---|---|---|---|
| G1 | lung-surgery delay hazard ratio about 1.06 per 4 weeks (Hanna 2020) | "Across cancers, a four-week delay is associated with higher mortality; for lung surgery the estimate was not statistically significant." Do not say faster care saves lives in lung cancer | Not lung-specific; a 2025 lung-specific meta-analysis is reported as null in `docs/evidence_research.md` | `docs/evidence_research.md` row "Survival effect of treatment delay" | published |
| G2 | 37 days diagnosis to treatment (calibration input) against a lung-specific Finnish median of 69 days (surgical patients, 5 hospitals, 2018) | "Our Finnish calibration uses 37 days, which is not lung-specific; a lung-specific Finnish study gives about 69. The effect on our shares was not rerun." | Known, unresolved conflict | `docs/evidence_research.md` | assumption |

## F. Decision models

| # | Number | The exact sentence it may be used in | Uncertainty or range | Source file | Status |
|---|---|---|---|---|---|
| F1 | 84.5% against 79.0% (78.3% for the smaller baseline) | "On a task where the right answer depends on the set of options, our own small model scores 84.5% against 79.0% for a parameter-matched dot-product baseline." This is our benchmark, not the team's JEV | On the control task the gap is 2.5 points, so part of the gain is capacity | `decision_model/README.md` | simulated |
| F2 | second question costs 76 to 91% of the first | "The claim that a second question costs half the compute did not reproduce." | | `decision_model/README.md` | simulated |
| F3 | The team's JEV | "The team's fine-tuned model is connected to the decision nodes through an adapter and a step-through tool; no number we report depends on it." No accuracy number is claimed | | `docs/platform/jev-birch.md` | (none) |

## P. Pending: waiting for tonight's results

Do not quote a number for any of these until the row is filled and the source file exists. `fill_numbers.py` prints a NOTE when `docs/review_checks/norway_opt_*.json` appear (files found now: none yet).

| # | What is waiting | Where the pitch says it is pending | What to write when it lands |
|---|---|---|---|
| P1 | The optimiser's flowcharts (88% and 67%) evaluated on all 184 settings | `deck.md` slide 6, `submission.md` Results, `qa.md` Q15, `data_transparency.md` section 4 ("checks on the other settings are pending") | Replace "pending" with the range, for example "67% at the best fit; across all 184 settings X to Y%", from `docs/review_checks/norway_opt_*.json`. Add the rows to B1 and B2 |
| P2 | The optimiser without the fourth change (leave-one-out) | same places; `qa.md` Q16 | Add one row to section B with the share with and without the fourth change; say what part of the lead over the authors it explains |
| P3 | Final count of model-written cards (2,500 more are being generated in five libraries of 500) | `data_transparency.md` section 7, `submission.md` "What we built", `deck.md` slide 10 | Nothing to type: the count is read from the manifests of libraries that are committed. Check `filled/` after the merge and that audit status is stated for each library |
| P4 | The primary-care loop after tuning (consistency checks) | `submission.md`, `qa.md` Q19, `platform_framing.md`, section E | Nothing to type if `docs/review_checks/encounter_results.json` is updated; reread E4 and any sentence that says "mechanism, not a result" |
| P6 | Regenerated libraries after the report-wording fix (prompt g2@2) and the background fix (age, smoking, sex) | `data_transparency.md` section 7, `qa.md` Q17, Q18 | Replace the "known problem" sentences with what the rerun review test shows (`tests/test_review_w7_report_leak.py`), only once it passes; keep the sentence that the review found it |
| P5 | The structure check of the optimiser's changes against the paper (lane w7/norway-opt) | not quoted yet | Add only if the lane reports it in `docs/validation.md` |

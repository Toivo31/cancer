# Independent review w7 (14 Nov 2026, evening, before the 04:00 UTC freeze)

Reviewer: read-only pass on branch `w7/review` (from `overnight/sim` at `b76bd38`). Nothing in product code was changed.
New tests: `tests/test_review_w7_report_leak.py`, `tests/test_review_w7_demo_numbers.py`,
`tests/test_review_w7_background_realism.py`. Each test shows an open finding, so each fails today. They are marked
`xfail(strict=True)`: the suite stays green, and once a finding is fixed its test passes, the run reports that as a
failure, and the marker must be removed. Run them: `python -m pytest -q -rx tests/test_review_w7_*.py` (2 s).

Words used below. **Decider**: whatever chooses the next action (decision tables, the JEV, the team's "Birch" model).
**Hidden side**: the true conditions, true findings, error plan and causes on a patient card. **Error plan**: the card's
list saying which test results are right, which are false alarms and which are misses. **I1**: deciders see only the
revealed side. **I3**: same patient and seed give the same result.

## Verdict (five lines)

1. The information boundary holds in the code: deciders read only the patient record, no path passes a condition, error plan or card id, and runs are exactly reproducible (I3 checked).
2. One real leak: text reports written by the language model reveal the error plan in their wording (50% of false-alarm reports hedge, 2% of true positives) and reach JEV requests and the training export verbatim. Birch is not affected. Blocker for any JEV training or testing on Gemini cards.
3. The demo shows stale numbers: the start page and encounter page are from before the tuned decision tables, and two "pending" rows are ready. Rerunning two exporters (under a minute) fixes it.
4. Synthetic backgrounds are not a population (22% of lung cancers under 50, a third of everyone a current smoker, pack-years ignore age). A clinician will see it on the first card, and it distorts the age and smoking splits.
5. The pitch is mostly honest. The biggest exposures are the Norway band (62 to 86%, not 78 to 86%), the second finding failing its own consistency check, and the equity gap in points widening (13.6 to 24.6).

## Blockers

### B1. Model-written report text carries the hidden error plan to the decider (I1 leak)

- **What.** When the language model writes a card's test results (prompt G2), it is told for each attempt whether the
  result is `correct`, `false_alarm` or `miss` (`patient_engine/authors.py:188-200`, `_plan_line`). The values it
  writes are right, but the free-text report often says the result is doubtful: "likely vascular overlap",
  "mimics patchy consolidation", "likely reactive", and once "misread on preliminary frozen section as squamous cell
  carcinoma". Over the two Gemini libraries, 157 of 316 false-alarm positives (50%) use such words, against 8 of 412
  true positives (2%). Misses: 24% against 6% of true negatives. A decider that reads the text can tell which
  positives are false, which a real clinician cannot (the catalogue's sensitivity and specificity are the only noise).
- **Where it reaches the decider.**
  - Ordered tests: `pathway_sim/encounter.py:627` takes `ro.report` from the card, stored at `:825` in the record.
  - Hospital CT and PET-CT read from the card: `pathway_sim/encounter.py:860` and `:883`.
  - Request builder: `jev/record_context.py:50` copies `report` into `context.observations[]`. This goes to every HTTP
    or local JEV, and into every training row (`pathway_sim/training_export.py`, `request` is built by the same code).
  - `jev/birch.py:189` (fallback evidence) uses the report when no rendered record is present.
  - Safe: Birch via `BirchPolicy` renders values only (`patient_engine/record_text.py`), and gathered outputs
    (history, examination) are re-rendered from values (`pathway_sim/encounter.py:710-718`).
  - Safe: the reference library (`ref500`, the world's own 60-per-condition cards) has template reports.
- **Evidence.** `test_report_wording_does_not_separate_false_alarms_from_true_positives` (50% against 2%);
  `test_request_context_report_is_derived_from_values_only` (a PET-CT false alarm, "reactive-appearing subcarinal
  lymph nodes", reaches the request verbatim). End to end: `export-training --library libraries/gemini_s2_30 --n 150`
  gave 33 positive observations with hedged text inside `request` (of 730 rows).
- **Fix (about 20 minutes).** In the encounter loop, write `report_text(test, status, values)` instead of the card's
  report for ordered and hospital tests, as is already done for gathers. Or drop `report` from
  `context_from_record` (Birch already ignores it). Longer term: either keep the model-written report out of
  every decider path, or stop telling the model the error plan (let it write from the values only); that changes the
  G2 prompt, not the catalogue hash. Until then: do not train or test the JEV on Gemini cards through the HTTP path.

### B2. The demo path shows pre-tuning numbers, and "pending" for numbers that are ready

- **What.** `demo/data/encounter_bundle.js` was generated at 16:42 UTC; the tuned decision tables were merged at 17:00
  UTC (`fe2132a`). The start page row 2 and `encounter.html` therefore show 29% of cancers treated within 90 days,
  median 28 days to referral, 101 to treatment and 18 cancers left with symptoms. The current code on the same run
  (`python demo/export_encounter.py --out /tmp/x.js`, 27 s) gives 25.5%, 47 days, 139 days and 3. The start bundle
  (16:34 UTC) has `norway_robustness: null` and `encounter_results: null` although both source files now exist, so
  the page says "pending" for the wider-grid range and the tuned report.
- **Where.** `demo/data/encounter_bundle.js`, `demo/data/start_bundle.js`; reader `demo/start.js:45-50, 80`.
- **Evidence.** `test_encounter_bundle_is_newer_than_the_tuned_decision_tables`,
  `test_start_bundle_reads_the_robustness_and_tuned_reports_that_exist`; headless Chrome render of `start.html`
  (no console errors, text as above).
- **Fix (2 minutes).** `python demo/export_encounter.py && python demo/export_start.py`, reload, check the example
  buttons (their patients change). Then see M2: the encounter page and `docs/encounter_results.md` still report
  different runs.

## Major

### M1. Plan and pitch still quote the superseded Norway band "78 to 86%"

- **What.** The robustness analysis (`docs/validation.md`, section Robustness) shows the 78 to 86% band was a corner:
  over the extended grid the authors'-pathway prediction is 62 to 86% (median 75%; 10 to 90%: 66 to 82%). Faster
  PET-CT is 50 to 74%. Still quoting 78 to 86: `docs/master_plan.md:161`, `docs/validation.md:34` (headline table),
  `docs/pitch/filled/data_transparency.md:38`. The start page says "80% published → 80% simulated" with no band.
- **Evidence.** `test_plan_does_not_quote_the_superseded_norway_band`; `docs/review_checks/norway_leave_one_out.json`
  (`both_targets.pred.optimal`: min 0.617, median 0.746, max 0.859).
- **Fix (15 minutes).** Say "predicted 75% (range 62 to 86%) against the published 80%" in the plan, validation
  headline table, the pitch template that feeds `data_transparency.md` (read the band from
  `norway_leave_one_out.json` in `fill_numbers.py`), and the start page row 4. Validation.md line 170 already
  recommends this.

### M2. Two different primary-care results for the same question

- **What.** The encounter page (one seed, about 3,900 patients, no warm-up) reports about 25 to 29% of cancers treated
  within 90 days. `docs/encounter_results.md` (4 seeds x 6,000 patients, 60-day warm-up) reports 12.2% [7.7, 16.8],
  median referral 37 days, treatment 158 days. The loop's queues fill up with run length, so the two are not
  comparable, and a presenter told to "say the number on the screen" will say a number the written report contradicts.
- **Where.** `demo/export_encounter.py` (n chosen for about 50 cancers, no warm-up) against `scripts/encounter_report.py`.
- **Fix (30 minutes).** Either make the exporter use the report's settings (warm-up, larger n, draw the dots from a
  sample), or label the page "illustration run, see the report for the numbers". Also: the pitch documents have no
  second-finding numbers yet (D48); when they are added, take them from `encounter_results.json`, with "placeholder
  decisions" and "consistency check not met".

### M3. Test outputs are shown to the model under the hidden variable's name

- **What.** `patient_engine/record_text.py:63` names each result by the label of the *variable it measures*, not by the
  output. A CT that is "suspicious for malignancy" (specificity 0.755) is rendered "Malignant tissue present in the
  lesion"; PET-CT's `fdg_avid` too; `nodes_avid` and `nodes_enlarged` become "Enlarged or involved mediastinal lymph
  nodes". This text is exactly what Birch reads (`jev/birch.py` `BirchPolicy.request_for`). It is not a leak (the
  value is the noisy one), but it tells the model a CT showed malignant tissue, which overstates every false alarm.
  A clinician reading `jev.walk` output will object at once.
- **Evidence.** `python -m jev.walk --pick cancer --auto-accept --jev mock`: "CT of the chest: ... Malignant tissue
  present in the lesion".
- **Fix (20 minutes).** Render output ids in words ("suspicious for malignancy", "FDG avid") or add output labels.
  The renderer change does not touch the catalogue hash; adding `label` to outputs in `tests.yaml` does.

### M4. Synthetic patient backgrounds are drawn without a population model

`patient_engine/skeleton.py:264-308`. Ranked by impact (on what a judge sees and on what a decision model learns):

| # | What is wrong | Seen in | Impact | Changes catalogue hash? |
|---|---|---|---|---|
| 1 | **Age ignores the condition.** Normal centred at 59 (SD 14) for everyone. 22% of lung-cancer cards in `ref500` are under 50 (youngest 24); in the shipped encounter run 15 of 51 cancers are under 50. Finland: median age at diagnosis about 70, under-50s a few percent. | `ref500`; encounter bundle groups | The age split in the second finding is meaningless; the GP suspicion rule (age 50+) misses a third of cancers that should barely exist. | No, if fixed in `skeleton.py` (an age distribution per condition or an age term in the acceptance step). Yes, if age enters `prevalence.by` in `conditions.yaml`. |
| 2 | **Smoking mix uniform (a third each).** The catalogue's own prevalence note assumes presenters are never 0.40 / former 0.38 / current 0.22. Result: 35% current smokers among non-cancer presenters; never-smokers 4% of cancers (note intends 12%). | `ref500`, `conditions.yaml` lung_cancer note | Inflates the "ever-smoker, 50+" suspicion rule, which likely feeds the over-referral of non-cancers (20% against 8%, `docs/encounter_results.md`). Also skews any smoking-group finding. | No (skeleton code). |
| 3 | **Pack-years ignore age.** After tonight's fix they follow smoking status (median 25 / 35), but a 24-year-old can have 35 pack-years; 36 of 500 cards smoke more than two packs a day since age 12. `gemini_s2_30` was generated before the fix: 28 of 30 cards have pack-years above age minus 14 (card 0: age 55, 69 pack-years). | `ref500`, `gemini_s2_30` | Visible on the card; a text model may learn odd age/smoking couplings. Check whether the 2,500 cards now being generated started after commit `d24278e`. | No. |
| 4 | **Sex ignores the condition.** Lung cancer 45 f / 38 m in `ref500` (Finland about 60% male). TB 30 f / 12 m by chance. | `ref500` | Minor for the decision model; visible in group splits. | No (skeleton) / Yes (`prevalence.by`). |
| 5 | **History changes between visits a day apart.** Each encounter gathers a fresh attempt of the history with its own error, so "breathless" on day 49 becomes "no breathlessness" at the GP on day 50. | `jev.walk --pick cancer --jev mock` | A clinician notices; the model learns that history is noise. | No (engine: reuse the latest history attempt within an episode unless the state changed). |
| 6 | **Presenters who report nothing.** 15 of 41 `no_disease_found` and 14 of 42 `benign_nodule` cards report no symptom at first contact. | `ref500` | Odd for a chest-symptom stream; small effect. | No (generator), or a catalogue rule (yes). |
| 7 | **Few distinct cards.** 30 Gemini cards cover 11 conditions (2 to 5 each), so a 6,000-patient cohort repeats each card about 200 times with identical background. | `gemini_s2_30` | A learned model memorises cards; the card-based split protects evaluation but leaves very little test data (23 of 730 rows in a test export). | No. |

Tests: `tests/test_review_w7_background_realism.py` (three, all fail). Fixing 1 to 3 in `skeleton.py` keeps the
catalogue hash but changes every generated library id (`ref500` again) and the skeletons given to the model, so do it
between generation batches, not during one.

### M5. The start page invites "67% < 80%" for Norway

- **What.** Row 3: "Norway, same method, no new equipment: 40% → 67%". Row 4: "80% published → 80% simulated" for the
  authors' pathway. The authors' 80% assumes a faster PET-CT; the optimiser with the same premise reaches 88%
  (`README.md:81`). Read together, the page suggests the optimiser does worse than the authors.
- **Where.** `demo/start.js:67`.
- **Fix (10 minutes).** Add "with the authors' faster scanner: 88% (authors 80%)" to row 3, or move the 67% next to
  the 88%.

### M6. Video material still shows the old 61% headline

`video/dots/README.md:10` (61.5% "Optimiser's change"), `docs/video_plan_draft.md:38, 53, 78, 94` ("18 → 61"). The
optimiser's change now gives 33%; 61% is the conditional urgent-booking result. Owner: Eemeli (already listed in
`docs/plan/04-status.md`). Effort: regenerate `video/dots/dots_data.js` and change the script, 30 minutes plus render.

## Minor

1. **Training rows contain the placeholder policy's own reasoning.** Earlier decisions' table notes ("Table rule:
   found.ankle_oedema and found.dyspnoea.") are in `request.context.assessments` of 580 of 730 rows. A model trained to
   imitate learns the tables' rule names, which do not exist when the real JEV decides. Fix: leave `assessments` out of
   exported requests, or export a flag. `pathway_sim/training_export.py`, `jev/record_context.py:64-73`.
2. **Training input differs from Birch's input.** Exported `request` is the JSON context; Birch receives the rendered
   text (`record_text`). `docs/platform/jev-training-data.md:43` says "training input equals inference input"; true
   for HTTP JEVs only. Say so.
3. **Hospital decisions never go to the JEV.** In the encounter world the hospital part keeps the flowchart's rule
   policy (`pathway_sim/encounter.py:541` passes `None`). D51 says only the JEV decides at every node. State it as a
   limitation.
4. **Hospital record lines read oddly.** Non-test steps are recorded as results: "Referral handling at hospital:
   positive", "Tumour board: positive", "Waiting for treatment slot: positive" (`pathway_sim/encounter.py:875-891`,
   `res_list or [True]`). Render these as "done".
5. **The "person decides" demo is not blind.** `python -m jev.walk --pick cancer` (`jev/walk.py:28`): the reviewer
   chose a cancer patient before the walk. The model is blind; the person is not. Say so on stage, or offer
   `--pick random`.
6. **Equity guardrail does not cover a widening gap.** D23 blocks a group getting slower, not the gap widening; the
   accepted change widens the gap in points from 13.6 to 24.6 while both groups gain. The pitch says this honestly
   (`docs/pitch/equity.md`), keep it.
7. **Agent channel.** I did not post to `agent-comms` (posting writes to a shared branch; the brief says never push).

## What was checked and found safe (I1, path by path)

| Path | Verdict | Where |
|---|---|---|
| Reveal handle | Safe: returns revealed types only; state names masked as `later`; card id opaque | `patient_engine/reveal.py` |
| Record | Safe: holds only revealed entries; patient id is the cohort label | `patient_engine/record.py` |
| Encounter decision tables | Safe: read `record_names(view.record)` only (background, found, reported, results, counts) | `pathway_sim/encounter.py:96-160, 254-276` |
| Encounter gathers | Safe: outputs re-rendered from values | `pathway_sim/encounter.py:710-718` |
| Encounter ordered and hospital card tests | **Leak with model-written cards** (B1) | `:627, :825, :860, :883` |
| Hospital-chain views | Safe: `group` from what the patient reported; attributes only after the revealing test | `pathway_sim/engine.py:292-299, 519-520` |
| Cohort order | Safe: conditions shuffled within blocks of 1,000, so the patient number says nothing | `patient_engine/cohort.py:202-207` |
| JEV request builder | Safe in structure; carries the report text (B1) | `jev/record_context.py`, `jev/adapter.py:16-41` |
| Birch | Safe: renders values only, refuses hidden field names and condition ids, checks evidence timing; mislabelled outputs (M3) | `jev/birch.py:115-141, 466-500` |
| `jev.walk` | Safe for the model; truth printed only after the walk | `jev/walk.py:164-184` |
| Training export | Labels (`label`, `outcome`) sit outside `request`; split by card; documented. Report text (B1) and table notes (Minor 1) are inside `request` | `pathway_sim/training_export.py:248-290` |
| Service | Does not use the encounter loop or cards; earlier security review covers it. Not re-traced in depth | `service/` |
| Demo bundles | The encounter bundle holds the truth for the teaching view, by design and labelled; not a decider path | `demo/data/encounter_bundle.js` (`truth`) |

**I3.** `python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 300 --seed 3 --library
libraries/ref500 --out ...` twice: outputs identical, records included.

## Numbers table

"Source" is the file or command that reproduces the number. "Current" compares it with that source tonight.

| Number | Where shown | Source | Current? |
|---|---|---|---|
| Finland 18% → 33% within 90 d (held-out), median 102 → 94 d | README, pitch (filled), start row 3 | `demo/data/demo_bundle.json` via `docs/pitch/fill_numbers.py` (`f_share_base/opt`) | Yes |
| Missed cancers 27.5 → 27.5 per cohort | pitch, start row 3 | same (`f_missed_*`) | Yes |
| Capacity-only control 31%; order-together 54% | README | same (`f_capctl_share`, `f_bundle_share`) | Yes |
| Conditional 18 / 44 / 61% | README, pitch | same (`f_cond_share_*`) | Yes, labelled conditional |
| 61% as the optimiser headline | `video/dots/README.md:10`, `docs/video_plan_draft.md` | old bundle | **No** (M6) |
| 12-cohort range 14–25% / 24–42%, gain 9–19 pt | README | `docs/ranges.md` | Not rerun |
| Norway observed 40% (published 40%) | README, pitch, start row 4 | `docs/validation_results.json` | Yes |
| Norway authors' pathway 80% simulated | README, pitch, start row 4 | `validation_results.json` (11 accepted points) | **Superseded**: extended grid 62–86%, central 75% (`norway_leave_one_out.json`) |
| "78 to 86%" | `master_plan.md:161`, `validation.md:34`, `pitch/filled/data_transparency.md:38` | old 11-point grid | **No** (M1) |
| Faster PET-CT 60% (published 48%) | README, start row 4 | demo bundle; extended grid 50–74% | Yes as a point; band missing |
| Optimiser same premise 88%, no new equipment 67% | README, start row 3 (67% only) | demo bundle (`s_opt_share`, `s_noeq_share`) | Yes; 67% shown without the 88% (M5) |
| PET-at-first-visit 66% | README | `docs/review_checks/stokstad_pet_triage_result.json` | Not rerun |
| Equity: vague 13 → 26%, alarm 27 → 50%, gap 13.6 → 24.6 pt | pitch | demo bundle (`f_ns_*`, `f_ss_*`, `equity_gap_*`) | Yes |
| Encounter loop 29% within 90 d, 28 d to referral, 18 left with symptoms | start row 2, `encounter.html` | `demo/data/encounter_bundle.js` (16:42 UTC) | **No**: current code gives 25.5%, 47 d, 3 (B2) |
| Encounter report 12.2% within 90 d, 37 d to referral, 16% first treated as something else, worried well 841 EUR | `docs/encounter_results.md` | `python scripts/encounter_report.py` (110 s) | Not rerun; disagrees with the page (M2) |
| Ledger 9 of 49 sourced; Norway 22 of 25; params 113 of 131 | start row 6, pitch | `docs/ledger.json` | Yes |
| Catalogue 109 sourced / 279 assumption of 388 | start row 6 | `catalogue/lung-primary-care` (counted by `export_start.py`) | Yes |
| ref500 library id | `libraries/ref500.md` | `L_0dbfc37e2e45d8d4`; old `L_224663a5217ab516` appears only as "old id" | Yes |
| Calibration 11 of 192 settings accepted | start row 4 | `validation_results.json` | Yes for that grid; extended grid accepts 184 of 1,920 |

## Ten questions a critical judge will ask

1. **"Your Norway check matches 80% exactly. Isn't that tuned?"** It was fitted only to the observed pathway. But the
   match was the corner of a wider band: across all settings that reproduce the observed pathway, the authors'
   pathway comes out 62 to 86%, centre 75%, and the fitted PET-at-triage practice is carried into it (66% without it).
   Say "consistent with 80%, not a precise prediction". `docs/validation.md` (Robustness), `README.md:80`.
2. **"Your model over-predicts the faster-scanner case by 12 points. Why trust it?"** We trust the ranking of
   reorderings, not their size; the miss is shown on screen and two candidate mechanisms were tested and do not explain
   it. `docs/validation.md` section 5, `docs/external_checks.md`.
3. **"Is the Finnish 18% → 33% a Finnish fact?"** No. 40 of 49 Finnish inputs are assumptions, booking leads are
   calibrated to survey waits, and the 90-day target is ours. The claim is that two reorders with no new capacity help
   in every one of 12 cohorts. `docs/ledger.md`, `docs/ranges.md`.
4. **"The challenge is equal care. Your change widens the gap."** In percentage points, yes (13.6 to 24.6); both
   groups gain and the gap in median days narrows. A priority track for vague symptoms is the option that narrows it,
   with a crowd-out guardrail. `docs/pitch/equity.md`, `docs/pitch/recommendation.md`.
5. **"Does the primary-care model reproduce anything real?"** Not yet. It fails 7 of 8 consistency checks against the
   calibrated chain (slower, refers 2.5 times as many non-cancers). Present it as a mechanism illustration with
   placeholder decisions. `docs/encounter_results.md`.
6. **"How do you know the decision model doesn't see the diagnosis?"** Deciders read only the record; requests are
   checked for hidden names and condition ids; this review traced every path. One leak was found (model-written report
   wording) and is not in the Birch path. `docs/review_w7.md` (this file), `tests/test_review_w7_report_leak.py`.
7. **"Your synthetic patients: a 24-year-old lung cancer with 35 pack-years?"** Background fields have no population
   model yet; the age and smoking splits are not interpretable, and that is said. `patient_engine/skeleton.py:264`, M4.
8. **"Slide 2 says Finland waits longest and survives least. Does faster care save lives in lung cancer?"** Not
   shown: in Hanna 2020 the lung-surgery hazard ratio per 4 weeks of delay (1.06) is not statistically significant.
   Keep survival as context for the gap, and argue for shorter waits on their own terms (guarantee, anxiety, stage
   drift is plausible but not proven here). `docs/evidence_research.md:16`, `docs/pitch/deck.md:10`.
9. **"Why 37 days from diagnosis to treatment when Finnish lung-specific data say about 69?"** The 37 days is not
   lung-specific (IHE); a 2018 study in five Finnish hospitals gives a median of 69 days for surgery. It is a known,
   unresolved conflict; the effect on the Finnish shares was not rerun. `docs/evidence_research.md:15`.
10. **"Who validated the clinical content?"** No clinician yet; the care catalogue is a draft (109 of 388 entries
    sourced). The optimiser's Norwegian fourth change (tissue sampling at triage) needs clinical review (D18).
    `catalogue/lung-primary-care`, `docs/decisions.md`.

## What I did not get to

- Did not rerun `scripts/encounter_report.py` (110 s) or `docs/ranges.md`; numbers marked "Not rerun" above.
- Did not test the service endpoints or `decision_api.server` live; no external model was called.
- Did not open `web/` (the React app) or `live_demo/` with its server.
- Did not run the full test suite (the brief allows one run; my tests run in 2 s and the rest was untouched).
- Did not inspect the 2,500 cards being generated now; check their pack-years (M4 row 3) and report wording (B1) when
  they land: `python3 -m pytest -q -rx tests/test_review_w7_report_leak.py` reads every library in `libraries/`
  that is listed in the test; add the new one there.

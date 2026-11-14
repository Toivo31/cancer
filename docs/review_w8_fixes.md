# Review w8: second pass on the g2@2 fix, the population model and the regeneration script (14 Nov night)

> Follow-up (branch `w8/g2blind`, decision D60): B1 fixed by result author `g2@3` (one result per prompt, report bank),
> M1 and M2 fixed; the xfails in `tests/test_review_w8_g2_blind.py` now pass. Measure: `scripts/g2_blindness.py`.

Branch `w8/verify` (from the integration branch at `1128fb6`, with `overnight/sim` `b9c7fe0` merged). Offline only:
fake library `generate --n 500 --seed 9 --fake` (`L_1c215eae13f0da9b`), skeleton draws, prompt builders read and run.
No real language model was called.

## Verdict

**Regenerate: yes, with conditions.** Running `generate_gemini.sh full` now is worth it: the engine decides every value,
the backgrounds are right, and the G1 answers sit in the cache, so a later change to the G2 prompt re-asks only G2
(cache key is the prompt hash; rerun into a new `--out` with the same `--work-dir`). **But the g2@2 report text is not
blind (B1 below), and D52's "never sees the patient's conditions, findings or the error plan" is false in effect.**
Until B1 is fixed or a regenerated library passes the audit's `report_wording` check and a manual read of 50 false-alarm
reports, either do not train or test a text-reading model on the new cards' report text, or remove `"g2@2"` from
`reveal.SAFE_RESULTS_PROMPTS` (one line: every report is then rebuilt from values; nothing else changes). That choice is
the architect's / Tuomas's, not mine, so I left the line as it is.

## Blocker

### B1. The g2@2 prompt still holds the diagnosis and the answer key, as values

- **What.** `authors.results_user` (`patient_engine/authors.py:265-280`) puts every test, every attempt and every value of
  the card into one prompt: 27 tests x 3 attempts. That includes the eight definitive tests, whose output ids and
  labels name the condition (`dx_lung_cancer_histology: Tissue sampling ... (definitive for lung cancer)`,
  `lung_cancer_confirmed: yes` three times), the tissue tests (`malignant_cells: yes`, specificity 1.0), and the other
  attempts of the same test. The "same prompt when hidden inputs change and values stay" test is true but empty: the
  values carry the hidden inputs.
- **Evidence (fake library, 500 cards, first state).** Can the information in the prompt tell a false alarm from a true
  positive? Gradient boosting, 5-fold cross-validated AUC:

  | positive result | n (FA) | this attempt's values + age/smoking (what the reader has) | + other attempts of the same test | whole prompt |
  |---|---|---|---|---|
  | chest_xray.abnormal | 356 (85) | 0.72 | 0.93 | 1.00 |
  | chest_ct.suspicious_for_malignancy | 271 (44) | 0.96 | 0.99 | 1.00 |
  | pet_ct.fdg_avid | 401 (161) | 0.87 | 1.00 (all attempts of non-definitive tests) | 1.00 |
  | chest_xray.consolidation | 214 (60) | 0.84 | 0.98 | 1.00 |
  | nt_probnp.bnp_high | 664 (403) | 0.87 | 0.98 (attempt k of non-definitive tests) | 1.00 |
  | echocardiography.heart_failure_confirmed | 255 (143) | 0.86 | 0.99 | 1.00 |

  A one-line rule a model can apply: "no tissue or definitive test says cancer, so this CT 'suspicious for malignancy'
  is a false alarm" is right for 271 of 271 positives (base rate 84%); for PET-CT `fdg_avid` 98% (base 60%); for the
  X-ray 96% (base 76%). "The other two attempts of this test are negative" alone gets 85 to 93%.
- **Why it matters.** Review w7 showed Gemini writes what it knows into the wording (51% of false alarms hedged against
  2%). The prompt now forbids hedging, so the leak needs the model to infer and to disobey; it may be small, but it is
  not closed by construction, and the model can also leak the *condition* through morphology words ("calcified",
  "spiculated", "smooth") that the audit does not test (see Q7). g2@2 text reaches every decider and every training row
  (`jev/record_context.py:56` copies `report`).
- **Partial fixes do not work.** Dropping the definitive and tissue tests still leaves 0.95 to 1.00 AUC from the other
  imaging and lab results of the same attempt index. The only clean designs: (a) one call per test and attempt with only
  that attempt's values plus age, sex, smoking and symptoms (81 calls a state: too many tonight), or (b) a phrase bank:
  the model writes report wording per test and value pattern, with no patient at all, cached across cards (wording then
  depends on values only; a few hours of work). Tonight: the one-line `SAFE_RESULTS_PROMPTS` switch, or keep g2@2 text
  but gate it on the audit plus a read.
- Tests: `tests/test_review_w8_g2_blind.py::test_g2_prompt_does_not_carry_a_definitive_result`,
  `::test_g2_prompt_for_the_chest_xray_does_not_include_tissue_results` (strict xfail).

## Major

### M1. Rule 8 (the patient-author leak rule) is weak, and the audit's `leak` check is the same rule

`patient_engine/validate.py:461-488`. Three ways a G1 leak passes:
1. **Synonyms.** It matches only the condition's label and id: "lung cancer" is caught, "cancer", "tumour", "growth",
   "malignancy" are not; "COPD" passes for `copd_exacerbation` (label "COPD exacerbation"); "TB" for tuberculosis;
   "reflux" alone; "chest infection" for pneumonia; "a virus" for the viral illness.
2. **The mention exemption.** A text may name the primary when its `mentions` (account) or `reported` (complaint)
   include a finding caused by the primary alone (`_reveals`, `:497-513`). Nearly every cancer patient has one
   (haemoptysis or weight loss caused by the cancer), so "I am frightened it is lung cancer" in the account passes.
   The exemption was meant for GP notes stating a result; it is applied to the patient's own words too.
3. **Hints without names**: "my doctor wants to rule out the worst", "they found something on the scan" (G1 prompt
   forbids it; nothing checks it).
- **Residual risk today: low.** No simulation, JEV or training path reads `presenting.text` or any note
  (`record_context` takes `reported` ids only; encounter never calls `notes_visible`). It is shown in
  `demo/export_cards.py:77` as "decider sees: complaint" (display only, a cancer card picked on purpose). The risk
  becomes live the moment someone adds the complaint text or notes to the request.
- Fix (30 min): a synonym list per condition in the validator (and the g2@2 name check) and drop the `_reveals`
  exemption for `patient_account` notes and `presenting.text`. Tests: `test_review_w8_g2_blind.py` (4 strict xfails).

### M2. A test reports an invented value where nothing exists: every non-cancer patient's histology is a cancer type

`patient_engine/skeleton.py:535-536` (`settle_attempt`): when the measured variable is null, an output *without*
`only_if` still gets a "phantom" value, planned `correct`. Only `histology_report.histology` is affected: all 1,251 ok
attempts of the 417 non-cancer cards report adenocarcinoma, squamous, small cell or other, each attempt drawn anew
(identical across attempts in 6% of non-cancer cards against 84% of cancers). `positive_when: histology is not None`
makes every one positive. Pre-existing (the reference generator uses the same function, so `ref500` has it); the
catalogue note says histology is null when the tissue is not malignant. Not reachable in the simulator
(`histology_report` is not in `care.yaml`), but it is in every g2@2 prompt (the model writes "small cell carcinoma"
for a worried-well patient) and the audit passes it (`accuracy.histology_report` 2 of 2). Fix (3 lines, but it changes
every library's content and id, so I did not do it the hour before a run): phantom only when the output's own
`only_if` holds; otherwise `None`. Test: `test_histology_of_a_non_cancer_patient_is_null` (strict xfail).

### M3. A rate-limit spell leaves holes that look like a finished library (fixed in the script, not in the pipeline)

`pipeline.py:252-276`: after the first accepted card, an endpoint error marks the card `failed` and the run goes on; the
library is written as complete, exit code 0, and `resume` will not retry (it only replaces a *partial* library). Five
runs at 20 threads each is 100 parallel requests; the client retries a 429 five times (about 30 s) and then gives up.
Failures hit the longest cards most (more states, more calls), so the condition mix of a library can shift. The old
`status` printed "done" for a partial library too. **Fixed**: `status` now says `PARTIAL` or `done, WITH FAILED CARDS`
with counts, and `resume` prints how to retry failed cards from the cache (move the library to `runs/old_libraries/`
and resume; answered calls are free). Consider `CONC=10`. Tests: `tests/test_review_w8_regeneration.py`.

### M4. The training-set builder would not hold out a new library (fixed)

`scripts/build_training_set.py:51`: the hold-out pattern `^gemini_s(\d+)_(\d+)$` does not match `gemini_v2_s17_500`, so
all five new libraries would go to training and the held-out test set would be an old g2@1 library (or `gemini_s2_30`,
made before the pack-years fix). **Fixed**: the pattern accepts `gemini_v2_s<seed>_<n>`; the highest seed (17) is held
out. Note the builder still trains on every `gemini_*` library it finds, including `gemini_s2_30` and `gemini_trial`
(old backgrounds, `background_realism` fails on `gemini_s2_30`) and the old g2@1 500s if copied in: pass the libraries
explicitly or move the old ones out of `libraries/`.

## Minor

1. **Labels in `populations/lung_primary_care.yaml`.** `lung_cancer` age ratios cite `FILHA2026`, whose entry in
   `params/sources.yaml` supports incidence, stage and subtype shares, not age; the note cites a different paper (not in
   `sources.yaml`) and our own review, and says the values are an assumption. Same for `tuberculosis` (`ECDC_TB2024`
   supports the notification rate only). Mark both `source: assumption` (D53 says assumptions are labelled so).
2. **Sex has no effect except through smoking** (known, review w7 M4 row 4): stratified draws give lung cancer 49% male
   (Finland about 60%), COPD 54%, heart failure 46%.
3. **CT misses drop the nodes.** `chest_ct.nodes_enlarged` has `only_if: lesion_seen`, so a CT that misses the lesion
   also cannot report enlarged nodes. Catalogue (locked); note only.
4. **Population model checks out.** IPF residual 2e-13; on 20,000 proportional draws every condition's share per
   smoking level is within z 2.6 of the catalogue's; stratified draws (400 per condition) match the model's
   P(age band, sex, smoking | condition) (chi-square 9 to 31 on 17 df); rejection acceptance 17% to 84%, so 200 tries
   never run out. Lung cancer median age 67, under 50 5.8%, never-smokers 11%; no pack-years beyond two packs a day from
   13; no never-smoker with pack-years. Rare edges remain plausible: 8 lung cancers and 1 heart failure under 40, 3
   COPD under 35 in 6,400 people.

## Question by question

1. **Value-level leak.** No degenerate tell in the values themselves. Misses give exactly what a true negative gives
   (dependent outputs null). A false-alarm CT lesion gets a size from the `default` distribution (median 8.8 mm, n 16)
   that matches benign nodules (7.7 mm) and differs from cancers (28 mm), which is realistic; location 90% peripheral
   like benign lesions. Lab values have no measurement error, so no rounding tell. The one invented-value defect is M2.
   Across attempts: a true lesion's sizes on repeat CT stay within a few mm (median range 3.4 mm); false alarms are
   independent per attempt, so two false-alarm attempts would disagree (never happened at n 500). Across tests errors
   are independent (realistic enough; a real false-positive scar would usually reappear on the next scan, so the model
   is if anything easier on the decider than reality).
2. **Prompt-level leak.** B1. Symptoms (the patient's report) are fine to pass. Order, units, the number of attempts
   (always 3) and the GP-note list are fixed. Co-existing conditions are not passed but show through definitive tests.
   The repair loop is clean: fixed messages, no state name, no card id. The name check allows a definitive test to name
   what it tests for and nothing blocks a histology report from saying "adenocarcinoma"; it misses synonyms (M1).
3. **G1.** M1. Not shown to deciders today.
4. **Old cards.** Every decider path (ordered tests, hospital CT and PET-CT, fresh attempts, the fallback path in
   `encounter.reveal`) reads report text through `RevealHandle.reveal`; `jev/birch.py` renders values; the training
   export builds `request` from the record. Notes and complaint text are not read by any decider. A merged library keeps
   per-card provenance (checked: merge of `/tmp/v9` and `gemini_s2_30` gives 500 g2@2 + 30 g2@1 cards; a g2@1 card's
   X-ray and PET-CT reports are rebuilt from values). `build_training_set.prompt_warning` reads the joined manifest
   (`g2@1+g2@2`) correctly.
5. **Population model.** Correct (Minor 4); labels (Minor 1); sex (Minor 2).
6. **Script.** M3 and M4 fixed. Seeds 12 (trial) and 13 to 17 do not collide with `ref500` / `gemini_trial` (s1),
   `gemini_s2_30` (s2) or the old s3 to s7. Audit flags are right; at n 30 the trial's `report_wording` runs (n 236), it
   is not hidden by the `grep -v SKIPPED`.
7. **What the audit would pass at n 500.** (a) B1-style leaks of the *condition* through words (the check compares wrong
   with right results only, within test and output); (b) M2 (an invented value planned `correct`); (c) uneven
   failures and discards by condition (the audit sees accepted cards only); (d) G1 synonyms (M1). Three checks worth
   adding tonight: **`report_condition_words`**: naive Bayes on report words against the same on value-only text, label =
   primary condition, within test and output (same code as `report_wording`, other label); **`null_truth_values`**: no
   reported value where the measured variable is null unless the output's `only_if` holds (count must be 0);
   **`design_coverage`**: accepted cards per primary condition against the design counts in the manifest, and discards
   or failures by condition from `generation_report.json` (fail above, say, 5 points of difference).

## D52 to D57

- D52: the mechanism is as described, the claim "never sees the patient's conditions" is not (B1). Reword to "sees only
  reported values, which include the definitive tests" until B1 is fixed.
- D53: correct; two labels wrong (Minor 1).
- D54: `ref500` id `L_424fcb177237f71f` matches `libraries/ref500/manifest.json`. Script issues fixed (M3, M4).
- D56: `--with-text` renders values only (`record_text`), but `request.context.observations[].report` still carries the
  card's report, i.e. the g2@2 model text for new cards (B1).
- D57: **the filled pitch files are out of date after `overnight/sim` (`b9c7fe0`)**: the gate's golden check fails on
  `test_pitch_templates_fill_completely_and_the_committed_copies_are_current` (data_transparency, deck, numbers_sheet,
  platform_framing, qa, submission). The merge changed `docs/review_checks/encounter_results*.json` without rerunning
  `python docs/pitch/fill_numbers.py`. Not caused by this branch (its diff against `b9c7fe0` is two scripts, two tests and
  this file); the pitch lane should refill and read the diff before anyone says a number aloud.
- D55: not checked.

## What I changed

- `scripts/generate_gemini.sh`: `status` shows running / PARTIAL / WITH FAILED CARDS and counts; `resume` warns about
  failed cards and says how to retry them from the cache.
- `scripts/build_training_set.py`: hold-out pattern accepts `gemini_v2_s<seed>_<n>`.
- Tests: `tests/test_review_w8_regeneration.py` (3 passing), `tests/test_review_w8_g2_blind.py` (7 strict xfails for
  B1, M1, M2). Nothing under `catalogue/` touched; catalogue hash unchanged.

## Gate

`bash scripts/gate.sh` (fast): 1253 passed, 7 xfailed (this review's), 1 xpassed (not from this branch), 1 failed:
the pitch golden check above (pre-existing in `b9c7fe0`). Contract tests pass.

## Not checked

A real model's output (no API here); D55 and D57; the `overnight/sim` changes themselves beyond confirming they do not
touch `patient_engine`; the slow test tier; the merged libraries s3 to s7 (not in the repo).

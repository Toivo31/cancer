# Synthetic data for JEV training: what it is, how to use it, limits

Status 14 Nov, evening. Everything here is synthetic; no real patient data exists anywhere in the project.

## What the data is

| Layer | What | Where |
|---|---|---|
| Catalogue (locked `catalogue-v1`, hash `2bcb9c78b2e0`) | 11 conditions (lung cancer, pneumonia, COPD flare, asthma, heart failure, TB, benign nodule, reflux/post-infectious cough, viral, no disease, worried well), 42 hidden variables (symptoms, signs, lab, imaging, function, tissue, one definitive marker per condition), 26 tests with accuracy, turnaround, cost | `catalogue/lung-primary-care/` |
| Patient cards | One patient = background, hidden conditions and findings, and the pre-written result of every test per state and attempt (misses and false alarms drawn from the catalogue's accuracy) | `libraries/ref500` (500 cards, template text, audit 38/38, id `L_0dbfc37e2e45d8d4`); handoff `libraries/ref500.md` |
| Model-written cards | Same structure. Gemini wrote the story and the findings, then the test results and the GP note, with reference frequencies as guidance and a checker with one repair try. Not template text | `libraries/gemini_trial` (5), `libraries/gemini_s2_30` (30), and `gemini_s3_500` to `gemini_s7_500` (500 each) when the integrator adds them |
| Training rows | One row per decision taken in the simulated primary-care loop | `python -m pathway_sim export-training ...` (below) |

## A training row

```
request   exactly what the JEV receives at that decision: decision point (nurse_encounter | gp_encounter),
          offered actions, and the patient record so far (background, what was reported and found,
          test results with positive/negative, earlier notes, earlier actions). Revealed information only.
chosen    the action taken;  policy: which policy acted (table or explore);  behaviour_probs
label     hidden truth: primary condition, co-existing illness, class (cancer | other_illness | healthy)
outcome   how the patient ended: diagnosed, days to correct treatment, cost, final state
meta      catalogue hash, library id, generator (reference | llm:<model>), seed, patient, split
```

Make the training and test files (one command, a few minutes, nothing to configure):

```
python scripts/build_training_set.py                 # realistic mix  -> runs/training/train.jsonl.gz, test.jsonl.gz
python scripts/build_training_set.py --mix balanced  # all 11 conditions equally often -> train_balanced..., test_balanced...
```

* **Training file:** ref500 plus every model-written library except one.
* **Test file:** that one model-written library, held out. It is the highest-seed `gemini_s*_500` present
  (today `gemini_s2_30`, because the 500-card ones are not in the repo yet). Run the command again when they arrive.
* It prints rows per decision point (nurse, GP), the label balance, the file sizes and a check that no
  request holds hidden information. Rebuild it after any change to the behaviour tables: nothing is cached.
* Use `split` in the training file: train for fitting, val for tuning. Its `test` rows are the same-generator check;
  the test file is the harder one (a different writer).
* Details, cohorts and flags: `docs/platform/jev-training-data.md`. The row format is above.

**Realistic or balanced?** Realistic follows the catalogue's prevalence: viral cough 45%, no disease 20%, lung cancer
1.3%, TB 0.07% (a few rows). Use it to see how the model does in the real mix. Balanced gives every condition the same
share: use it to train on rare conditions, then report on the realistic test file.

## How to use it for the JEV

1. **Diagnosis belief** (supervised): input `request`, target `label.primary`. Teaches what the record implies. Report calibration, not only accuracy.
2. **Action choice**: do not imitate `chosen` (it comes from placeholder tables and random exploration). Use `outcome` with `behaviour_probs` for off-policy learning, or derive the action from the belief plus each option's cost and delay.
3. **Generalisation check**: train on reference cards plus some model-written libraries, test on one model-written library that was never in training (`test.jsonl.gz`). If accuracy holds, the model learned the medicine, not the writer's wording.
4. **In the loop**: connect the model with `--jev birch` (or a URL) and compare outcomes against the placeholder tables on the same patients; `python -m jev.walk --pick cancer` steps one patient with the model proposing.

## Limitations (say these out loud)

- **It teaches the catalogue, not medicine.** 177 of about 260 numbers are our assumptions; no clinician has reviewed it. A model trained here is right about our synthetic world only.
- **`chosen` is a placeholder.** Decision tables and random exploration made it, not doctors. Do not imitate it. Use `outcome` with `behaviour_probs`, or the belief plus costs and delays.
- **Model-written cards:** made by Gemini, checked by an audit (38 checks; `gemini_s2_30` passes 38 of 38, `gemini_trial` 32 of 32 run) and a leak check on the notes. Their cards are few, so some checks have small counts (many skipped as "too few cases" at 30 cards). The audit of the 500-card libraries is not run yet.
- **Made before the pack-years fix:** `gemini_trial` and `gemini_s2_30` have never-smokers with pack-years above zero (8 of 8 never-smokers). The `gemini_s3`...`s7` libraries should not; the build command prints the count per library. ref500 was regenerated and is clean.
- **Even stratification:** every library has about the same number of cards per condition (lung cancer double). That is not real life. Realistic mix is applied when patients are drawn, not in the library. Rare conditions repeat the same few cards.
- **Few distinct patients:** a cohort reuses cards; rows from one card are correlated. Splits are by card for that reason.
- **Template wording** in ref500 and in record lines; a model can key on phrasing. Use the held-out model-written test file.
- **Behaviour numbers are assumptions** (visit counts, waits, who gets referred). The loop does not yet match the calibrated Finnish chain, so `outcome` values reflect the placeholder policy.
- **Findings are independent given the condition**; repeated tests are independent given the patient; disease does not progress while waiting.
- **Options carry no features** in encounter requests yet (ids only); cost and wait can be joined from the catalogue.
- **One primary condition**, at most one co-existing illness; 11 conditions cover chest-symptom presenters only.

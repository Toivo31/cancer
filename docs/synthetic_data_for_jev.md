# Synthetic data for JEV training: what it is, how to use it, limits

Status 14 Nov. Everything here is synthetic; no real patient data exists anywhere in the project.

## What the data is

| Layer | What | Where |
|---|---|---|
| Catalogue (locked `catalogue-v1`, hash `2bcb9c78b2e0`) | 11 conditions (lung cancer, pneumonia, COPD flare, asthma, heart failure, TB, benign nodule, reflux/post-infectious cough, viral, no disease, worried well), 42 hidden variables (symptoms, signs, lab, imaging, function, tissue, one definitive marker per condition), 26 tests with accuracy, turnaround, cost | `catalogue/lung-primary-care/` |
| Patient cards | One patient = background, hidden conditions and findings, and the pre-written result of every test per state and attempt (misses and false alarms drawn from the catalogue's accuracy) | `libraries/ref500` (500 cards, offline generator, template text, audit 38/38); handoff `libraries/ref500.md` |
| Model-written cards | Same structure, text and values written by a language model (Gemini trial in progress on Tuomas's machine) | `libraries/gemini_*` when ready |
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

Make it:

```
python -m pathway_sim export-training scenarios/finland_encounter.yaml --flowchart encounter \
  --n 20000 --seeds 1,2,3 --explore 0.3 --out runs/training/v1.jsonl.gz
```

About 228 000 rows (45 MB, 5–8 min): 183 000 GP and 45 000 nurse decisions; 70% from the placeholder
tables, 30% random exploration; split by library card into train/val/test. Add `--library libraries/ref500`
to fix the cards, `--holdout-library libraries/gemini_x` to put model-written patients in the test split.
Full format: `docs/platform/jev-training-data.md`.

## How to use it for the JEV

1. **Diagnosis belief** (supervised): input `request`, target `label.primary`. Teaches what the record implies. Report calibration, not only accuracy.
2. **Action choice**: do not imitate `chosen` (it comes from placeholder tables and random exploration). Use `outcome` with `behaviour_probs` for off-policy learning, or derive the action from the belief plus each option's cost and delay.
3. **Generalisation check**: train on reference cards, test on model-written cards (`--holdout-library`). If accuracy holds, the model learned the medicine, not the template wording.
4. **In the loop**: connect the model with `--jev birch` (or a URL) and compare outcomes against the placeholder tables on the same patients; `python -m jev.walk --pick cancer` steps one patient with the model proposing.

## Limitations (say these out loud)

- **It teaches the catalogue, not medicine.** 177 of about 260 numbers are our assumptions; no clinician has reviewed it. A model trained here is right about our synthetic world only.
- **Template wording** in reference cards and in record lines; a model can key on phrasing. Use the held-out model-written set.
- **Class imbalance**: at realistic prevalence lung cancer is about 1.3% of rows (3 000 of 228 000), TB 0.1%. Reweight or use the stratified library for the belief task.
- **Few distinct patients**: a 20 000-patient cohort reuses about 500–660 cards; rows from one card are correlated. Splits are by card for that reason.
- **Behaviour policy is a placeholder**: decision tables are assumed and the loop does not yet match the calibrated Finnish chain (7 of 8 consistency metrics outside tolerance), so `outcome` values reflect that policy.
- **Findings are independent given the condition**; repeated tests are independent given the patient; disease does not progress while waiting.
- **Options carry no features** in encounter requests yet (ids only); cost and wait can be joined from the catalogue.
- **One primary condition**, at most one co-existing illness; 11 conditions cover chest-symptom presenters only (no embolism, cardiac chest pain, bronchiectasis, metastases).

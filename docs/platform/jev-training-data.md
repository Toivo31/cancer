# Training data for the JEV from simulated patients

For the JEV owner. Code: `pathway_sim/training_export.py`. Tests: `tests/test_training_export.py`. Format name `jev_training/1`.
All data is synthetic.

## Make it

```
python -m pathway_sim export-training scenarios/finland_encounter.yaml --flowchart encounter \
    --n 20000 --seeds 1,2,3 --explore 0.3 --out runs/training/v1.jsonl.gz
```

20 000 patients x 3 seeds: about 228 000 rows, 45 MB gzipped, about 4.5 minutes. A `v1.summary.json` is written next to
the file (rows per decision point, per primary condition, per split and policy, libraries, JEV call statistics).
The same arguments give the same bytes (gzip header has no timestamp).

| Flag | Meaning |
|---|---|
| `--n`, `--seeds` | patients per seed and library; `1,2,3` or `1-3` |
| `--explore p` | with probability p a decision is drawn uniformly among the offered options (`policy` ends in `\|explore`), so rows are not all shaped by one policy |
| `--library DIR` (repeatable) | card library written by `patient_engine generate` / `write_library`; verified with `load_library` against the scenario's catalogue hash. Default: the world's reference library |
| `--holdout-library DIR` (repeatable) | the patients of this library all go to the `test` split: train on one generator, test on the other |
| `--holdout-generator reference\|llm` | rows from cards of that generator go to `test` |
| `--split-by card\|patient` | default `card`: every patient drawn from one library card shares a split (a library has few hundred cards, each reused by many patients, so a per-patient split would put the same card in train and test) |
| `--keep-table-notes` | keep the placeholder tables' own assessments ("Table rule: ...") in `request.context.assessments`. Default: removed, because a model trained on them would learn rule names that will not exist when the real decider decides. Assessments of a real decider (author `<role>_encounter/<backend>` other than `table`) always stay. On `--n 300 --seeds 1 --library libraries/ref500`: 6 812 entries removed from 1 201 of 1 501 rows |
| `--with-text` | also write `request_text` on each row: the `case` (context text and evidence lines) the Birch adapter would send, produced by `jev.birch.BirchPolicy.request_for` and `map_request`, so it cannot drift from the adapter |
| `--jev URL\|KIND` | decide with the JEV instead of the decision tables: an HTTP URL or any `jev.factory` backend kind (`stub`, `birch`, ...) (below) |

## One row (one decision)

```json
{"request": {"request_id": "p41:gp_encounter", "decision_point": "gp_encounter", "question_type": "next_step",
             "context": {"age": 73, "t_days": 21.7, "role": "gp", "background": {...}, "presenting": {"reported": [...]},
                         "found": {...}, "observations": [...], "notes": [...], "assessments": [...], "actions": [...]},
             "options": [{"id": "order_chest_xray"}, {"id": "treat_antibiotics"}, ...]},
 "chosen": "order_chest_xray", "policy": "encounter_policy/1", "behaviour_probs": {"order_chest_xray": 0.4, ...},
 "label": {"primary": "pneumonia", "coexisting": [], "class": "other_illness"},
 "outcome": {"diagnosed": true, "days_to_diagnosis": 21.7, "days_to_correct_treatment": 35.0, "cost_eur": 1240.0,
             "encounters": 5, "episodes": 1, "referred": false, "final": "treatment"},
 "meta": {"catalogue": "lung_primary_care@2bcb9c78b2e0", "library": "L_731c...", "generator": "reference",
          "seed": 1, "policy_model": "encounter_policy/1", "patient": "P000041", "split": "train"}}
```

* `request` is exactly what the JEV receives live: it is built by `jev.adapter.BackendPolicy.request_for`
  (`build_context` -> `jev.record_context.context_from_record`) from the patient's record, in the call the engine makes. Options are bare ids, as live. This is the input of a decision model called over HTTP with the JSON context. The team's fine-tuned model (the "Birch" adapter, `jev/birch.py`) does not receive this JSON: it receives rendered text (`patient_engine/record_text.py`, mapped by `jev.birch.map_request`). To train a model that will run behind Birch, export with `--with-text` and train on `request_text` (the exact case text and evidence lines the adapter sends; earlier assessments are left out of it unless the adapter is told to include them), not on `request`.
* `label` and `outcome` are the hidden side and never appear in `request` (I1; tested: no condition id, hidden field name,
  card id or the primary condition's word in the request, except the clinician's own prose in `notes` and `assessments`, a definitive test's own result, and earlier action ids such as `order_dx_pneumonia`).
* `outcome` is for the whole patient, repeated on each of its rows. `days_to_correct_treatment`: first treatment that matches a true condition, or the hospital treatment start; null if none.
* `behaviour_probs` are the probabilities of the policy that acted (uniform for explore rows), for off-policy work.
* `meta.generator` is `reference` or `llm:<model>`; `meta.library` is the library id.
* Split: 80/10/10 deterministic from the card id (or `seed:patient` with `--split-by patient`).

## Cautions (from the plan, "Training the JEV")

1. **Train on records, not cards.** The input is what a clinician can see in the record at that moment. The card holds the truth; a model that saw it would learn nothing usable. Rows only contain revealed information.
2. **A diagnosis is not a decision.** `label.primary` says what the patient had, not what to do. A model trained only to predict the label learns a classifier; the decision is a choice among actions (order a test, treat, refer, wait) with costs and delays. `chosen` is only as good as the policy that produced it.
3. **It learns the catalogue's assumptions.** Prevalences, test accuracies, care costs and the decision tables are assumptions in the catalogue and scenario files. A JEV fitted to these rows reproduces them, including the placeholder numbers. It is evidence about the model of care, not about real patients. Use the held-out test file (`scripts/build_training_set.py`, below) and several seeds to see whether it generalises beyond one generator.

## Suggested tasks

(a) **Condition belief from the request**: predict `label.primary` (or `class`) from `request`; evaluate on `split == test`; check calibration, especially for `lung_cancer` (about 1.3% of rows).
(b) **Action value from outcomes**: from `(request, chosen) -> outcome` (for example `days_to_correct_treatment`, `cost_eur`, `final`), learn what each action is worth, then pick actions by value. `--explore` gives the coverage needed; weight by `1/behaviour_probs[chosen]` for off-policy correction.

## Connecting the JEV (D51)

In the final model only the JEV decides; the decision tables are a placeholder. Both the run and the export take an HTTP JEV:

```
export JEV_ALLOWED_HOSTS=host:port          # or JEV_DEFAULT_URL=http://host:port (docs/platform/runbook.md)
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 2000 --jev http://host:port [--jev-model ID] [--jev-timeout 5]
python -m pathway_sim export-training scenarios/finland_encounter.yaml --n 5000 --seeds 1 --jev http://host:port --out runs/training/jev.jsonl.gz
```

The host must be allowed exactly as for the service (`service.security.check_jev_url`). An unreachable or refused JEV stops with a plain
message. A failure in the middle of a run stops the run (no silent fallback). The JEV's `record_note` and `assessment` land in the record
(`BackendPolicy.choose_with_note`) and are in later requests. After each run the CLI prints decisions, network calls, failures and
median and p95 latency per network call (`jev.http` answers repeated identical contexts from its cache when the model declares `context_fields`; such answers are counted as decisions, not as network calls). `export-training --jev` records the same in the summary (`jev_calls`) and `policy` is the JEV's model id.
Tests start `jev.stub_server`'s server in a thread (`tests/test_training_export.py`).

## Build the training and test files in one command

```
python scripts/build_training_set.py                  # realistic mix
python scripts/build_training_set.py --mix balanced   # every condition equally often
python scripts/build_training_set.py --dry-run        # list libraries, roles and patient counts, then stop
```

Output (folder `runs/training/`, git-ignored): `train.jsonl.gz`, `test.jsonl.gz`, `build_summary.json`
(balanced: `train_balanced...`, `test_balanced...`, `build_summary_balanced.json`). The summary holds library ids, row
counts by decision point, split, condition and policy, file sizes and SHA-256, and the boundary check result.

* **Training** = `libraries/ref500` + every `libraries/gemini_*` library except the held-out one.
* **Test** = one model-written library, never in training. Default: the `gemini_s<seed>_<n>` with the highest seed
  (more cards on a tie). With only the small libraries present that is `gemini_s2_30`. `--holdout DIR` picks another;
  `--exclude NAME` leaves one out. New `gemini_s*_500` folders are found by name: run the command again.
* Every row of the test file has `meta.split = "test"`. Rows of the training file keep their split by card
  (train / val / test); `test` there is the same-writer check.
* Patients per library and seed: `--n` (default 2000), but 20 per card for small libraries (floor 200), so a 5-card
  library is not copied 400 times. `--seeds 1-3` adds seeds; `--explore 0.3` is the share of random decisions.
* Rows are identified by `(meta.library, meta.seed, meta.patient)`. `request_id` repeats across libraries and seeds.
  Two libraries can share a card id (ref500 and gemini_trial both use seed 1), so the id alone does not say which card.
* Checks printed at the end: every row has exactly the seven keys; `label` and `outcome` are never inside `request`;
  the request holds no condition id, hidden field name, library id or card id (clinician prose, earlier action ids and a
  definitive test's own result are the allowed exceptions, as in `tests/test_training_export.py`); `chosen` is one of the
  offered options; no library is in both files. Exit code 1 if any row fails.
* Nothing is cached. Change the behaviour tables, run again. The same libraries, seeds and tables give the same bytes.

**Inputs and answers are separate fields.** Input: `request` only (`request.context` is the record at that moment,
`request.options` the choices). Answers and hidden truth: `chosen`, `policy`, `behaviour_probs` (what was done), `label`
(what the patient had), `outcome` (how the patient ended). `meta` is bookkeeping (library, seed, split): do not feed it to the model.

## Merge libraries

```
python -m patient_engine merge libraries/gemini_s3_500 libraries/gemini_s4_500 --out libraries/gemini_s34_1000
python -m patient_engine library-info libraries/gemini_s34_1000     # lists the libraries it came from
```

Combines libraries made for the same catalogue (same hash). Refuses different catalogues and any card id that occurs
twice (this includes the same library given twice). The same inputs give the same library id on any machine and in any
order. The manifest keeps `sources` (id, model, prompts, card count and date of every input), and it is covered by the
library id. `model` and each prompt version of the result are the distinct values joined with `+`; each card keeps its own
provenance. A merged library works wherever a library does: `audit`, `cohort`, `show`, `run --library`,
`export-training --library`, `jev.walk --library`. `build_training_set.py` does not need a merge: it takes the libraries
separately, so every row keeps its library id.

## Realistic or balanced mix

Libraries are stratified (about the same number of cards per condition). The mix is set when patients are drawn.

* **`export-training` and `run`** draw patients with the scenario's prevalence (`prevalence: catalogue`): viral 44.9%, no disease
  20%, COPD flare 7.5%, asthma 5.9%, reflux or post-infectious cough 5.5%, pneumonia 5%, heart failure 5%, worried well 3%,
  benign nodule 1.8%, lung cancer 1.3%, TB 0.07%. That is the realistic mix. Within a condition a card is chosen uniformly at random.
* **`patient_engine cohort`** with no `--prevalence` uses the library's own card counts as the mix. That is the even
  stratification (lung cancer 17%), not realistic. Give the mix with `--prevalence`. It fills a quota per block of 1000 patients
  (shares within a fraction of a percentage point) and reuses cards when a condition has fewer cards than patients. A condition
  with no card in the library is an error (`gemini_trial` has 5 conditions only).

```
# (a) realistic mix: 20 000 patients from ref500 at the catalogue's prevalence
python -m patient_engine cohort libraries/ref500 --n 20000 --seed 1 --prevalence \
  viral_self_limiting=0.4493,no_disease_found=0.2,copd_exacerbation=0.075,asthma=0.059,reflux_postinfectious_cough=0.055,pneumonia=0.05,heart_failure=0.05,worried_well=0.03,benign_nodule=0.018,lung_cancer=0.013,tuberculosis=0.0007
python scripts/build_training_set.py                  # training rows at that mix (the default)

# (b) balanced: every condition equally often, to train rare conditions
python scripts/build_training_set.py --mix balanced
python -m patient_engine cohort libraries/ref500 --n 11000 --seed 1 --prevalence \
  viral_self_limiting=1,no_disease_found=1,copd_exacerbation=1,asthma=1,reflux_postinfectious_cough=1,pneumonia=1,heart_failure=1,worried_well=1,benign_nodule=1,lung_cancer=1,tuberculosis=1
```

`--mix balanced` runs a copy of the scenario with an equal share per condition (written under `runs/training/_work/`, deleted
afterwards; the original is untouched). Train on the balanced file for the rare conditions and test on the realistic test file.
A model trained on a balanced mix is too confident about rare conditions in the real mix: recalibrate or use class weights.
Rare conditions repeat the same few cards (42 per condition in ref500, 2 to 6 in the small Gemini libraries): many rows, few patients.

## Libraries of model-written cards

Written by Gemini (`gemini-3.8-flash`) on the lead's machine, two calls per card: the first writes the patient's story and
findings, the second the test results and the GP note. Reference frequencies guide both calls; a validator checks each card
and gives one repair try. `ref500` has no language model: numbers are drawn from the catalogue, the text is a template.

Ids, card counts, models, prompt versions and audit status are in each library's `manifest.json` (`python -m patient_engine library-info <dir>`)
and `audit.md`; `libraries/` lists what exists. Not hard-coded here because they change. Status on 14 Nov evening:

* `ref500`: template cards, audit 38 of 38, regenerated for the pack-years fix and again for a realistic population, so its id changes; re-export old training data.
* `gemini_trial` (5 cards) and `gemini_s2_30` (30 cards): audit pass, made before the pack-years fix (never-smokers with pack-years above 0) and with prompt `g2@1`.
* `gemini_s*_500`: 500 cards each, added by the integrator. Run `python -m patient_engine audit <dir> --catalogue catalogue/lung-primary-care --out /tmp/audit`.

**Prompt `g2@1` warning.** In cards made with result prompt `g2@1` the wording of the test report gives away which results are false alarms or
misses (review finding B1). Do not train or test a text-reading model on that text. `build_training_set.py` prints the prompt versions of every library
it uses and warns on `g2@1`; with such libraries its output is for pipeline testing only. The fix is prompt `g2@2` and rebuilding report text from values;
all model-written libraries will be regenerated after it lands.

```
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --library libraries/gemini_s2_30 --n 2000
python -m jev.walk --library libraries/gemini_s2_30 --patient 0 --jev mock --auto-accept
```
A library made for another catalogue (hash mismatch) is refused.

## Limits

* Synthetic only. No real patient.
* The decisions in `chosen` are placeholders: decision tables plus random exploration. The "chosen" action is whatever they picked,
  not what a clinician would do.
* Libraries are stratified evenly by condition, not drawn by prevalence. Realistic mix comes from the draw.
* Behaviour numbers (waits, visit counts, referral rates) are assumptions, and the encounter loop is being retuned, so row counts and
  outcomes will change. Rebuild the files after that.
* Some audit checks have small counts at 5 or 30 cards. The model-written libraries were not clinician-reviewed.
* Libraries with result prompt `g2@1` leak through report wording (above).

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
| `--jev URL` | decide with the HTTP JEV instead of the decision tables (below) |

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
  (`build_context` -> `jev.record_context.context_from_record`) from the patient's record, in the call the engine makes. Training input equals inference input. Options are bare ids, as live.
* `label` and `outcome` are the hidden side and never appear in `request` (I1; tested: no condition id, hidden field name,
  card id or the primary condition's word in the request, except the clinician's own prose in `notes` and `assessments`, a definitive test's own result, and earlier action ids such as `order_dx_pneumonia`).
* `outcome` is for the whole patient, repeated on each of its rows. `days_to_correct_treatment`: first treatment that matches a true condition, or the hospital treatment start; null if none.
* `behaviour_probs` are the probabilities of the policy that acted (uniform for explore rows), for off-policy work.
* `meta.generator` is `reference` or `llm:<model>`; `meta.library` is the library id.
* Split: 80/10/10 deterministic from the card id (or `seed:patient` with `--split-by patient`).

## Cautions (from the plan, "Training the JEV")

1. **Train on records, not cards.** The input is what a clinician can see in the record at that moment. The card holds the truth; a model that saw it would learn nothing usable. Rows only contain revealed information.
2. **A diagnosis is not a decision.** `label.primary` says what the patient had, not what to do. A model trained only to predict the label learns a classifier; the decision is a choice among actions (order a test, treat, refer, wait) with costs and delays. `chosen` is only as good as the policy that produced it.
3. **It learns the catalogue's assumptions.** Prevalences, test accuracies, care costs and the decision tables are assumptions in the catalogue and scenario files. A JEV fitted to these rows reproduces them, including the placeholder numbers. It is evidence about the model of care, not about real patients. Use `--holdout-library` and several seeds to see whether it generalises beyond one generator.

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

## Library from model-written cards

```
python -m patient_engine generate ... --out libs/gemini1
python -m pathway_sim export-training scenarios/finland_encounter.yaml --n 20000 --seeds 1,2,3 --explore 0.3 \
    --library libs/gemini1 --out runs/training/llm.jsonl.gz
python -m pathway_sim export-training ... --library <reference dir> --holdout-library libs/gemini1 ...   # train on one, test on the other
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --library libs/gemini1 --n 2000
```
A library made for another catalogue (hash mismatch) is refused.

# Spec 06: Datasets and training

Milestone M6. Depends on specs 02 and 03. Open: fork F3 (JEV API), decision D25 (training on
outcomes).

## Purpose

"Train JEV with your dataset": a user uploads past decisions, the platform checks them against the
flowchart, a trainer produces a model, and the model is attached to decision points. The same path
has to work before the real JEV exists, so there is a simple trainer that turns a dataset into the
stub's probability tables.

## Dataset format: one row per decision

JSON lines, canonical:

```json
{"decision_point": "sample_method", "patient_id": "p1042", "t_days": 31.5,
 "context": {"group": "non_specific", "age": 67, "fast_track": false,
             "attributes": {"location": "peripheral"},
             "history": [{"step": "ct", "test": "ct_chest", "result": true, "t_days": 30.9}]},
 "offered": ["bronch", "ttnb"], "chosen": "ttnb",
 "outcome": {"usable_result": true, "days_to_next_milestone": 9.5}}
```

`context` is exactly the contract's context (spec 02), so a row is a request plus the answer that
was given. `outcome` is optional and only used by outcome-based training.

CSV is accepted as a convenience: columns `decision_point, patient_id, t_days, offered, chosen`,
context as `ctx.<name>` columns, results of earlier steps as `step.<id>` with `+`, `-` or empty.

Sources of a dataset:
1. Upload.
2. "Decisions from run X": `GET /runs/{r}/decisions` already has this shape. Replaces the ad hoc
   adapter in `decision_model/tasks.py`.
3. An exploration run: a run where chosen decision points pick at random, to get outcome-labelled
   rows for options that practice rarely takes (this is what `decision_model/in_loop.py` does today).

## Validation report

Against a chosen flowchart version and its world:

- every `decision_point` exists and is a decision; every `offered` and `chosen` id is one of its options;
- context names are known attributes, steps or built-ins; unknown ones are listed, not fatal;
- per decision point: rows, share of each option, share of rows per context value;
- warnings: a decision point with no rows; an option never chosen; fewer than 30 rows in a cell
  the trainer will estimate;
- patients, date range if present, duplicate rows.

A dataset with errors can be stored but not trained on.

## Trainers

All produce a registry entry and are used through the spec 02 contract.

| Trainer | What it does | When |
|---|---|---|
| `frequency` | Per decision point, estimates P(option given context cell) by counting, with add-one smoothing. Cells are the combinations of the context fields the user ticks (default: revealed categorical attributes and group). **Output is a stub table**, visible and editable on the Decisions screen | M6, first. Closes the loop without JEV |
| `local` | The numpy correction model in `decision_model/`, trained to imitate `chosen` | M6, optional reference |
| `jev` | Sends the dataset to the JEV API (`POST /v1/train`), polls, registers the returned model id | When the API exists |

Outcome-based training (pick what led to better outcomes, not what was done) exists as an
experiment in `decision_model/in_loop.py` with a reward of "usable result minus days/30". That
trade-off is a value judgement (D25) and is not offered in the UI until it is decided.

## Model registry

```json
{"id": "m_0c4", "trainer": "frequency", "dataset": "d_77", "dataset_hash": "…",
 "flowchart": {"id": "baseline", "version": 3}, "decision_points": ["first_contact", "sample_method"],
 "created": "…", "status": "ready",
 "evaluation": {"holdout_rows": 1830, "log_loss": 0.41, "log_loss_uniform": 0.69, "accuracy": 0.82,
                "by_decision_point": {…}, "calibration": [[0.1, 0.08], [0.3, 0.33], …]}}
```

Evaluation: split by patient (not by row) 80/20; report log-loss against the uniform and
option-frequency baselines, accuracy, and calibration (predicted probability against observed
share in ten bins).

Attaching: "use model m_0c4 at these decision points" writes the flowchart's `decision_policy`
and saves a new version.

## What the UI must say

- **Imitation learns practice.** A model trained on what was chosen reproduces the dataset,
  including its habits and its inequities. The page says so next to the train button, and the
  evaluation is labelled "agreement with past decisions", not "accuracy of care".
- **Synthetic data only on the hosted instance** (fork F5). An upload page with a banner, and no
  free-text fields in the format, so identifiable text has nowhere to go. Real patient data needs
  a data protection assessment that is outside this plan.
- A model trained on one flowchart version may not match another (options added or removed). The
  attach step revalidates and lists mismatches.

## API additions (service)

`POST /projects/{p}/datasets` (multipart or JSON lines), `GET …/datasets/{d}` (report),
`POST /projects/{p}/models` `{dataset, trainer, context_fields?, decision_points?}` → job,
`GET …/models`, `GET …/models/{m}`, `POST …/flowcharts/{f}/attach-model`.

## Build order

1. `jev/dataset.py`: row schema, CSV reader, validator, report (M6-1).
2. Decisions export from run logs; retire the adapter in `decision_model/tasks.py` (M6-2).
3. `frequency` trainer and evaluation (M6-3).
4. Registry, training jobs, API (M6-4); screen (M6-5).
5. Exploration run mode (M6-8); `local` trainer (M6-7).
6. `jev` trainer against the real API, contract tests green (M6-6, blocked on F3).

## Test that proves the loop

Simulate with a known stub table → export decisions → train `frequency` → the learned table is
within sampling error of the original → a run with the learned model reproduces the original run's
metrics within noise.

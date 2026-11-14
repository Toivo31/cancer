# WP-W4-4: Training data for the JEV from simulated patients

| | |
|---|---|
| Component | C4 (decision layer, training), C8; the doc "How the pathway simulation works" section "Training the JEV" |
| Size | S–M · Model: Sonnet |
| Needs | merged encounter loop (`pathway_sim/encounter.py`), `jev/record_context.py` (request context from a record), `jev/dataset.py` (existing dataset format), catalogue `lung-primary-care` locked at `catalogue-v1` |
| Owned paths | `pathway_sim/training_export.py` (new), `pathway_sim/__main__.py` (one new subcommand), `docs/platform/jev-training-data.md` (new), `tests/test_training_export.py` (new) |
| Do not edit | `pathway_sim/encounter.py` (ask on the channel if you need a hook), `jev/record_context.py` |
| Review required | yes: I1 (inputs must be revealed-only; labels are the only hidden field) |

## Outcome

`python -m pathway_sim export-training scenarios/finland_encounter.yaml --flowchart encounter --n 20000 --seeds 1,2,3 --explore 0.3 --out runs/training/v1.jsonl.gz`
writes one JSON line per decision taken in the simulation:

```json
{"request": {<the exact DecisionRequest the JEV would receive: decision_point, options with features, context from the record>},
 "chosen": "order_chest_xray", "policy": "table@1|explore",
 "label": {"primary": "lung_cancer", "coexisting": ["pneumonia"], "class": "cancer"},
 "outcome": {"diagnosed": true, "days_to_correct_treatment": 61.0, "cost_eur": 1240.0, "final": "treatment"},
 "meta": {"catalogue": "lung_primary_care@<hash>", "library": "L_...", "seed": 1, "patient": "P000042", "split": "train|val|test"}}
```

- `request` is built with the same code the live JEV path uses (`jev.record_context`, `jev.adapter.build_context`), so training input = inference input.
- `label` and `outcome` are the only hidden-side fields, kept outside `request`.
- `--explore p`: with probability p a decision is taken uniformly among offered options (so records are not all shaped by one policy); `policy` says which.
- Split by patient (not by row), deterministic from the seed: 80/10/10. A second split option `--holdout-generator` marks rows from a different library generator (reference vs model-written) as `test`, for the generalisation check.
- A summary file next to it: rows per decision point, label distribution, rows per split, file size.
- `docs/platform/jev-training-data.md`: the format, how to make it, and the three cautions from the doc (train on records not cards; a diagnosis is not a decision; it learns the catalogue's assumptions), plus suggested tasks: (a) condition belief from request (labels), (b) action value from outcomes.

## Acceptance

- [ ] I1 test: no `request` in a 2 000-patient export contains a condition id, a hidden field name, a library card id or the word of the primary condition's label outside notes written by definitive tests (reuse the patterns from `tests/test_jev_record_context.py`).
- [ ] Same seed → identical file (byte-equal gzip content after decompression).
- [ ] Every `request` validates with `jev.contract.DecisionRequest.from_dict`.
- [ ] 20 000 patients × 3 seeds exports in under 5 minutes (measure; report rows and size).
- [ ] `scripts/gate.sh` green.

## Report (builder fills in)

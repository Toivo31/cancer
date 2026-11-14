# Patient-card libraries

Each folder is one library (`library/1`): `manifest.json` + `cards.jsonl.gz`, immutable, named and
checked by a content hash (`python -m patient_engine library-info <folder>` verifies it). Small
libraries (a few MB) are committed here so the demo and the training export run with no network.

- Make one offline: `python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 500 --seed 1 --out libraries/<name> --fake`
- Make one with a language model: see `docs/plan/packages/C1/WP-C1-5-authors.md` (Report) for the command and environment variables.
- Audit before use: `python -m patient_engine audit libraries/<name> --catalogue catalogue/lung-primary-care` (once WP-W4-3 is merged).

Work folders (`<name>.work/`: cache, call log, discard log) are not committed. Training exports
(`runs/training/`) are regenerated from their command and seed, not committed.

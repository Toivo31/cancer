# Patient-card libraries

Each folder is one library (`library/1`): `manifest.json` + `cards.jsonl.gz`, immutable, named and
checked by a content hash (`python -m patient_engine library-info <folder>` verifies it). Small
libraries (a few MB) are committed here so the demo and the training export run with no network.

- Make one offline: `python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 500 --seed 1 --out libraries/<name> --fake`
- Make one with a language model: see `docs/plan/packages/C1/WP-C1-5-authors.md` (Report) for the command and environment variables.
- Combine libraries of one catalogue: `python -m patient_engine merge <lib> <lib> ... --out libraries/<name>` (refuses different catalogues and repeated card ids; `library-info` lists the sources).
- Training and test files from these libraries: `python scripts/build_training_set.py` (see `docs/platform/jev-training-data.md`).
- Audit before use: `python -m patient_engine audit libraries/<name> --catalogue catalogue/lung-primary-care` (once WP-W4-3 is merged).

Handoff notes per library: `libraries/<name>.md` (start with `libraries/ref500.md`).

Work folders (`<name>.work/`: cache, call log, discard log) are not committed. Training exports
(`runs/training/`) are regenerated from their command and seed, not committed.

Libraries here change often: read ids, counts, prompts and models from each `manifest.json` (`library-info`), not from prose.
`ref500` is the template-card library (its id changed on 14 Nov for the pack-years fix and changes again for a realistic
population). `gemini_*` are model-written; those with results prompt `g2@1` (including `gemini_trial` and `gemini_s2_30`)
leak through report wording and are for pipeline testing only (review B1). All are stratified evenly by condition.

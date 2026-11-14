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

Libraries now here: `ref500` (template cards; id `L_0dbfc37e2e45d8d4` since the 14 Nov pack-years fix, old id
`L_224663a5217ab516`), `gemini_trial` (5 cards) and `gemini_s2_30` (30 cards), both written by Gemini before that fix
(never-smokers with pack-years above 0). `gemini_s3_500` to `gemini_s7_500` follow. All are stratified evenly by condition.

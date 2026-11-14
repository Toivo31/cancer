# Command reference

Moved from `README.md`. Every command in the first four sections was run in a clean worktree on 14 Nov 2026 (evening) with small
sizes, and worked. Sizes are small so a shared 2-core machine can run them in seconds. The numbers they print are **not** the
reported results: those use larger cohorts (for example `--n 2000` for the calibration, see `docs/pitch/filled/numbers_sheet.md`
for the command behind each number). Raise `--n` and `--seeds` for stable numbers.

Run everything from the repository root. Python 3.13 was used.

## 1. Install

```bash
pip install -r requirements.txt                          # pyyaml, numpy: enough for the simulator, optimiser, JEV tools and offline demo
pip install -r requirements.txt -r service/requirements.txt   # adds fastapi, uvicorn, pydantic, httpx: needed for the web platform's API
```

## 2. Simulator, calibration, optimiser

```bash
# one flowchart, one cohort: share treated in time, median, where the waiting is
python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed --n 100

# compare all flowcharts in a scenario, averaged over seeds
python -m pathway_sim compare scenarios/generated/stokstad_calibrated.yaml --n 50 --seeds 1-2

# calibrate unsourced parameters on the observed pathway, predict the others (writes the --out file; the repo's own result file is docs/validation_results.json)
python -m pathway_sim.calibrate scenarios/stokstad.yaml --n 50 --out /tmp/cal.json

# optimiser, blind to the hidden diagnosis, from the observed order with the faster PET-CT scanner (one step, small cohort)
python -m optimiser scenarios/generated/stokstad_calibrated.yaml --start faster_pet --n 100 --steps 1 --out /tmp/opt.json

# decision-model benchmark (our own small correction model against a dot-product baseline; about 15 s)
python -m decision_model.benchmark --quick
```

A calibration at `--n 50` finds fewer accepted grid points than the reported one (5 of 192 in the run above, against 11 at `--n 2000`).
That is expected at a small size and is not a result.

## 3. Decisions through JEV

JEV is the team's decision model. At a decision point the simulator asks a backend for a score for each offered option, then either
draws the choice from those probabilities (`sample`, the default) or takes the most likely one (`argmax`). Without `--jev` the
rule policy runs as before. Interface: `docs/platform/specs/02-jev-interface.md`. With `--n 300` a Finnish cohort has too few
cancers for the share to mean anything; these commands show that the plumbing works.

```bash
# stub with hardcoded probabilities (migrated from the scenario's mix / rules / prefer)
python -m pathway_sim run scenarios/finland_lung.yaml --n 300 --jev stub
# change one probability and watch the run move (others in that row are rescaled)
python -m pathway_sim run scenarios/finland_lung.yaml --n 300 --jev stub --set first_contact.nurse_visit=0.9
python -m pathway_sim run scenarios/finland_lung.yaml --n 300 --jev stub --decision-mode argmax

# the same through a JEV service: start the stub server (second terminal, or add & and kill it afterwards), point the run at it
python -m jev.stub_server --scenario scenarios/finland_lung.yaml --flowchart baseline --port 8100
python -m pathway_sim run scenarios/finland_lung.yaml --n 300 --jev http://127.0.0.1:8100
python -m pathway_sim run scenarios/finland_lung.yaml --n 300 --jev http://127.0.0.1:8100 --on-error fallback_stub

# contract tests against any JEV address (without --jev-url they start the stub server themselves)
python -m pytest -q tests/test_jev_contract.py --jev-url http://127.0.0.1:8100 --jev-point sample_choice --jev-options bronch,ttnb
```

Walk one synthetic patient through the primary-care loop, one decision at a time. `--jev mock` needs no key and no model;
say that it is a mock if you show it. The person choosing `--pick cancer` knows the patient has cancer; the model does not.

```bash
python -m jev.walk --pick cancer --auto-accept --jev mock      # drop --auto-accept to accept or type another action yourself
```

The live model (checkpoint 1138, "Birch") needs a key: `docs/platform/jev-birch.md`. Run the primary-care loop on the reference library:

```bash
python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 300 --seed 3 --library libraries/ref500
```

At that size it has about 7 cancers. Do not read any share from it: the loop is a mechanism, not a result (`docs/encounter_results.md`).

## 4. Offline demo pages, platform, teammate demos

```bash
python demo/export_cards.py        # under 1 s; writes the git-ignored demo/data/cards_bundle.js that the start page's "Synthetic patients" card and two demo tests read
python -m http.server -d demo 8000 # only if your browser will not open files from disk; then open http://localhost:8000/start.html
python -m pytest -q tests/test_demo_start.py tests/test_demo_cards.py tests/test_demo_fixture.py   # about 1 s, after export_cards
```

The other pages open straight from disk: `demo/start.html`, `demo/index.html` (dashboard, keys 1-6), `demo/flow.html`, `demo/encounter.html`.
Rebuilding their data bundles is described in `demo/README.md` (`python demo/export_all.py`, 1 to 2 minutes; it rewrites tracked files in
`demo/data/`, so it was not re-run for this page).

The web platform (API, built web app, seeded example projects). Needs Node and `npm` for the web app:

```bash
(cd web && npm ci && npm run build)            # about 40 s; writes web/dist (git-ignored)
PATHWAY_DATA_DIR=/tmp/pw uvicorn service.app:app --port 8000   # serves the API (docs at /docs, health at /api/health) and, when web/dist exists, the web app at /
python deploy/seed.py http://localhost:8000 --quick            # about 2 minutes: adds a Finland and a Norway project and a "Guided tour" run
```

Open <http://localhost:8000>. With no token and no flags the server is open for everyone who can reach it: use it on a laptop only.
Hosting, access modes and limits: `docs/platform/runbook.md` (the deploy script itself was not run).

The decision-model panel and the teammate's note reader (also described in the README sections that keep their own text):

```bash
python3 -m decision_api.server      # http://127.0.0.1:8771/decision
python3 -m note_reader.server       # http://127.0.0.1:8770/  (and /note, /report/, /decision)
```

Patient engine and agent channel:

```bash
python -m patient_engine library-info libraries/ref500        # verifies a library's hash and prints its manifest and card counts
python scripts/build_training_set.py --help                   # builds JEV training and test files; see docs/synthetic_data_for_jev.md
python scripts/comms.py --help                                # the agent channel (CLAUDE.md)
```

## 5. Long commands, not re-run for this page

These take minutes or rewrite tracked files, so they were not run while writing this page. Times are those the project documents give.

| Command | What | Time and note |
|---|---|---|
| `python -m pytest -q` | the whole test suite | 4 to 7 minutes on a loaded machine (`docs/plan/04-status.md`); the gate is `scripts/gate.sh` |
| `python -m pathway_sim demo` (`--quick` for smaller cohorts) | simulate, optimise, evaluate on held-out patients, build the dashboard bundle `demo/data/demo_bundle.json` | about 9 minutes; `--quick` about 2.5 (older README) |
| `python demo/export_all.py` | rebuild every start-page bundle | 1 to 2 minutes (`demo/README.md`) |
| `python scripts/norway_robustness.py` (`--recompute` rebuilds the cache) | the 184-setting robustness tables | `--recompute` about 40 minutes (`docs/validation.md`) |
| `python scripts/encounter_report.py` | the multi-seed primary-care report `docs/encounter_results.md` | about 110 s |
| `python3 docs/pitch/fill_numbers.py` | regenerate `docs/pitch/filled/` from the result files | rerun after any result changes |
| `deploy/deploy.sh user@host --seed` | deploy to a host with Docker | untested; `docs/platform/runbook.md` |

## 6. How a scenario is written

See `scenarios/stokstad.yaml` (commented) and `docs/architecture.md`. A flowchart is a DAG of
steps with `after` / `after_any` / `after_optional` prerequisites, guards (`when:`) on revealed
results, `choice` nodes decided by a policy, and `exit` nodes. Resources are `server`
(capacity queue), `delay` (published wait distribution) or `batch` (weekly tumour board).

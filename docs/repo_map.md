# Repository map

One row per top-level folder and important file. "Owner" is what the project documents or the git history say; "unknown" means
the documents do not say. Code was mostly written by coding agents (Claude Code sessions) for Tuomas; the integrator is the
architect session (`docs/plan/README.md`). Teammates: Eemeli (video, classifier, note reader, live demo) and Toivo (decision
model kit, `decision_api/`). `decision_api/` (the teammate's model kit), `jev/` (our adapter to it) and `decision_model/` (our own small benchmark model) are three different things with similar names. Commands to run each start point: `docs/commands.md`. Status of each part: `docs/plan/04-status.md`.

| Path | What it is | Owner | Start with |
|---|---|---|---|
| `README.md` | The front door | integrator | read it |
| `CLAUDE.md` | Project context and the agent-channel rules for coding agents | architect | `docs/plan/README.md` |
| `demo/` | Offline pages that open from disk: `start.html` (the demo in order), `index.html` (dashboard, keys 1-6), `flow.html` (flowchart simulation), `encounter.html` (primary-care loop), plus the exporters that build their data | architect, demo lane | open `demo/start.html`; script in `docs/demo_path.md`; rebuild notes in `demo/README.md` |
| `pathway_sim/` | Event engine, scenario and flowchart loader, synthetic patients, policies, metrics, calibration, the primary-care encounter loop, CLI | architect | `python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed --n 100` |
| `optimiser/` | Proposes changes from revealed information, accepts on a rerun with guardrails, reports on held-out patients | architect | `python -m optimiser --help`; method in `docs/master_plan.md` |
| `scenarios/` | `stokstad.yaml` (Norwegian check), `finland_lung.yaml` (synthetic Finnish county), `finland_encounter*.yaml` (primary-care loop), `generated/` (calibrated), `experiments/` | architect | `scenarios/stokstad.yaml` (commented) |
| `params/` | Every input number with its source (`sources.yaml`) or tagged assumption; `ledger.py` counts them | evidence lane | `docs/ledger.md`, `docs/parameters.md` |
| `patient_engine/` | Synthetic patient cards: catalogue, generation, audit, cohorts, record text | architect | `python -m patient_engine library-info libraries/ref500`; `docs/synthetic_data_for_jev.md` |
| `catalogue/` | The medical content of the simulated world: 11 conditions, hidden variables, 26 tests. A draft no clinician has read | architect (needs a clinician) | `catalogue/README.md` |
| `libraries/` | Committed patient-card libraries (500 template-written, some model-written) with manifests and audits | architect | `libraries/README.md`, `libraries/ref500.md` |
| `jev/` | Decision layer: contract, adapter, stub tables, HTTP backend, the adapter to the team's model ("Birch"), `walk.py` step-through tool | architect for the adapter; the model itself is the team's | `python -m jev.walk --pick cancer --auto-accept --jev mock`; `docs/platform/jev-birch.md` |
| `decision_api/` | The teammate's kit for the hosted decision model: local server, JavaScript client, review panel, recorded examples. Not edited by us | Toivo (git history) | `decision_api/README.md`; `python3 -m decision_api.server`, then `/decision` on port 8771 |
| `decision_model/` | Our own small numpy decision model and benchmark. Separate from the team's JEV; no reported headline number depends on it | architect | `python -m decision_model.benchmark --quick`; `decision_model/README.md` |
| `service/` | FastAPI backend of the web platform: projects, flowchart versions, runs, optimisations, access control | platform lane | `service/README.md`; `uvicorn service.app:app --port 8000`, API docs at `/docs` |
| `web/` | The web app (React, Vite): canvas, run panel, optimise tab. Builds to `web/dist`, which the service serves | platform lane | `docs/commands.md` section 4 |
| `deploy/`, `Dockerfile`, `docker-compose.yml` | Hosting files and seeding. Written, never run on a host | needs a human with Docker and a host | `docs/platform/runbook.md` |
| `live_demo/`, `note_reader/` | The teammate's hosted flowchart demo, note reader and report page. Need their server to show data | Eemeli (git history) | `python3 -m note_reader.server`, then port 8770 |
| `video/` | Trailer animation (pathway dots) and render script. Older material may still show the old 61% headline (review M6) | Eemeli | `video/dots/README.md` |
| `technique_classifier/` | A separate deliverable (clinical notes, taxonomies and output schema). Not used by the simulator | Eemeli | `docs/technique_classifier.md` |
| `docs/` | Plans, contract, decisions, validation, parameters, pitch material | integrator | `docs/plan/README.md`; `docs/START_HERE.md` |
| `docs/pitch/` | Pitch text. `numbers_sheet.md` is the single source for numbers said aloud; `fill_numbers.py` writes `filled/`, which is what to read | pitch lane | `docs/pitch/filled/numbers_sheet.md` |
| `docs/validation.md` | Norway check: calibration, prediction, robustness over 184 settings | evidence lane | the "Robustness" section |
| `docs/review_w7.md` | Independent review: verdict, blockers, majors, ten questions a judge will ask | review lane | "Verdict" |
| `docs/platform/`, `docs/plan/` | Platform specs and tickets; planning framework and status | architect | `docs/plan/04-status.md` |
| `tests/` | Test suite; `tests/security/` is the service's security tests; `tests/test_review_w7_*.py` mark open review findings as expected failures | all | `python -m pytest -q tests/test_demo_start.py` |
| `scripts/` | `gate.sh` (the integrator's gate), `comms.py` (agent channel), Norway robustness and encounter report scripts, `build_training_set.py` | integrator | `python scripts/comms.py --help` |
| `runs/` | Saved optimiser and model-in-loop result files (JSON) | architect | `runs/opt_finland.json` |
| `docs/plan/overnight/BLOCKERS.md`, `docs/plan/overnight/TASKS.md` | Blockers log and the overnight task queue (history; `docs/plan/04-status.md` is current) | integrator | |
| `requirements.txt`, `pytest.ini` | Python requirements (`service/requirements.txt` adds the API's) and test settings | | `docs/commands.md` section 1 |

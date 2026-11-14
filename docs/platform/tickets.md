# Platform tickets

Plan: `README.md`. Specs: `specs/`. Nothing here has been started. Tick a box when its acceptance
line is met and the test suite passes.

Size: **S** up to about an hour, **M** a few hours, **L** half a day or more, for one agent or
person. "Needs" lists tickets that must be done first; tickets without a shared need can run in
parallel. **T** marks a ticket that waits on Tuomas (a fork in `README.md` section 5).

Critical path to the first browser loop:
`M1-1 → M1-2 → M1-3 → M2-1 → M2-3 → M2-5 → M2-6 → M3-1 → M3-4/5/6 → M2-11 → M3-10/11 → M2-7 → M4`.

## M0 Foundation wrap-up

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | M0-1 | Pull request `overnight/sim` → `main` | S | T | PR open with a summary; merged by the team |
| [ ] | M0-2 | Settle pending decisions D17, D20, D25, D27 and forks F1 to F7 | – | T | Each marked settled in `docs/decisions.md` |
| [ ] | M0-3 | Freeze the static dashboard as the fallback demo | S | – | `demo/` bundle committed and tagged; README says how to open it |

## M1 JEV in the graph (specs 01, 02)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [x] | M1-1 | `jev/` contract: request, response, backend info, `BackendPolicy` adapter, JSON examples | S | – | Types and examples match spec 02; adapter builds a request from a `PatientView`; unit tests |
| [x] | M1-2 | Engine decision modes `sample` and `argmax` with the common-random-number draw; choices log records mode, backend, model; `decision` accepted as a node kind | M | M1-1 | Same patient, same probabilities → same choice across flowcharts (test); existing tests pass |
| [x] | M1-3 | `StubBackend`: hardcoded and conditional probability tables; automatic migration of `mix`, `rules`, `prefer` | M | M1-2 | Every shipped scenario reproduces its current metrics exactly; changing one probability changes the run |
| [x] | M1-4 | Safe condition evaluator replacing `eval` in engine, policies and optimiser | M | – | Identical results on all scenarios; sandbox-escape strings rejected at load (test) |
| [x] | M1-5 | Stub HTTP server and `HttpBackend` (keep-alive, cache, timeout, error modes) | M | M1-3 | A run through `http://localhost` equals the in-process run; Finnish run at most 3× slower; failure modes tested |
| [x] | M1-6 | Contract test file runnable against any JEV address | S | M1-5 | `pytest tests/test_jev_contract.py --jev-url …` passes against the stub server |
| [x] | M1-7 | `LocalBackend` wrapping the numpy model in `decision_model/` | S | M1-1 | In-loop experiment runs through the contract with unchanged results |
| [x] | M1-8 | CLI: `--jev stub\|rule\|http://…`, `--decision-mode`, `--set point.option=prob` | S | M1-3 | Commands in README work |
| [ ] | M1-9 | Turn one clinician judgement in the Finnish scenario (GP: image or wait) into a decision point | M | M1-3, T (F1) | Scenario recalibrated to the same waits; `docs/finland_scenario.md` updated |
| [x] | M1-10 | Update `docs/architecture.md` and `docs/master_plan.md` for the JEV contract | S | M1-3 | Docs match code |

## M2 Service (specs 01, 03, 05)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [x] | M2-1 | Document format v1: world and flowchart JSON, converters both ways, YAML import | M | M1-3 | Round trip gives byte-identical metrics for all shipped scenarios |
| [x] | M2-2 | Structured validation: full problem list with codes, node references, reachability and dead-end warnings | M | M2-1 | One test per code; CLI behaviour unchanged |
| [x] | M2-3 | Service skeleton: FastAPI app, config, SQLite store, templates, generated API page | M | M2-1 | `uvicorn service.app:app` serves `/api/templates` and `/docs` |
| [x] | M2-4 | Projects, world, flowchart versions, validate endpoint | M | M2-2, M2-3 | CRUD tests; versions with runs are immutable |
| [x] | M2-5 | Job runner (process pool, status, progress, cancel, limits) and engine progress hook | M | M2-3 | Progress moves during a run; cancel works; a crashing job fails alone |
| [x] | M2-6 | Runs: start, list, get; metrics; dashboard bundle; decisions export; identical-run cache | M | M2-4, M2-5 | Bundle opens in the existing dashboard; cache hit tested |
| [x] | M2-7 | Optimisations: job, result with labels and evidence, `apply` with a subset and linked changes | M | M2-6 | Applying all changes equals the optimiser's own output; subset tests |
| [x] | M2-8 | "Try a decision" endpoint | S | M2-4 | Returns the stub's probabilities for a hand-entered context |
| [x] | M2-9 | API tests including the full loop: template → run → optimise → apply → rerun → compare | M | M2-7 | Loop test passes with small `n` and asserts same patients |
| [x] | M2-11 | Flow endpoint: per-step and per-edge counts, waits, critical-path share, queue series, decision shares, and a sampled cohort of patient traces for playback | M | M2-6 | Totals equal the run's metrics; sample size and seed configurable; one test on both shipped templates |
| [x] | M2-10 | `service/README.md` with a `curl` walkthrough of the loop | S | M2-9 | Walkthrough runs as written |

## M3 Run from the browser (spec 04)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [x] | M3-1 | Web scaffold (Vite, React, TypeScript), build served by the service | M | M2-3, T (F4) | `localhost:8000` shows the app shell |
| [x] | M3-2 | API client and types generated from the API description | S | M3-1 | Type check passes; regenerates with one command |
| [x] | M3-3 | Projects screen: list, new from template | S | M3-2, M2-4 | A project created from the Finnish template opens |
| [x] | M3-4 | Read-only flowchart graph with auto-layout; decisions highlighted; version picker | M | M3-3 | Both templates draw without overlaps; parallel steps side by side |
| [x] | M3-5 | Decisions table: edit hardcoded probabilities and conditions; saves a new version | M | M3-4 | Rows must sum to 100; saved table round-trips |
| [x] | M3-6 | Run panel: settings, start, progress, cancel, history | M | M3-3, M2-6 | A run started in the browser finishes and appears in history |
| [ ] | M3-7 | Report tab: existing dashboard embedded and fed by the run's bundle | M | M3-6 | All dashboard screens render for a fresh run |
| [ ] | M3-8 | Compare two runs: headline table and the Compare layer on the graph | S | M3-6, M3-10 | Deltas shown on steps and edges; different-patient runs refused with a reason |
| [x] | M3-10 | **Run layers on the flowchart**: flow counts, time per step, decisions' chosen shares, queues; "where time is lost" list | M | M3-4, M2-11 | After a run the Norway graph shows the PET and tumour-board waits as the darkest steps; counts match the metrics |
| [x] | M3-11 | **Playback**: time slider, play, speed, dots moving along the graph, live counters | M | M3-10 | A 300-patient cohort plays through the Finnish scenario at 60 frames a second on a laptop; counters at the end equal the run's totals |
| [x] | M3-12 | Patient trace: click a dot or list row; steps with wait/took/result, decisions with offered probabilities, critical path highlighted | S | M3-11 | Trace of one patient equals that patient's record in the run log |
| [x] | M3-13 | Offline flow page `demo/flow.html` (no build): graph, flow/time/decision layers and playback from precomputed logs; fallback demo | M | M2-11 shape agreed | Opens from disk with no server; shows Norway observed vs optimised side by side |
| [ ] | M3-9 | Scripted browser pass with screenshots | S | M3-7 | One command opens a template, edits a probability, runs, saves screenshots |

## M4 Optimise and rerun in the browser (specs 04, 05)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | M4-1 | Optimise panel: settings, start, progress by step | S | M2-7, M3-6 | Job runs from the browser |
| [ ] | M4-2 | Suggested changes with evidence; list of changes blocked by safety checks | M | M4-1 | Matches the API result; honesty line shown |
| [ ] | M4-3 | Graph diff: before and after side by side on the canvas with changed connections highlighted and the Compare layer on | M | M3-4, M4-1 | Norway template diff shows the tumour board moving before sampling |
| [ ] | M4-4 | Accept a subset → new version → rerun on unseen patients → comparison | M | M4-2, M3-8 | Whole loop in the browser without touching the CLI |
| [ ] | M4-5 | Optimiser under JEV: `standardise` rule, moved-probabilities report, conditional fast-track finding | S | M2-7, T (F7) | Tests for each rule; spec 05 behaviours hold |

## M5 Build your own flowchart (specs 01, 04)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | M5-1 | Editor: add, move, delete steps; connect with typed connections; undo and redo | L | M3-4 | The Norway observed pathway can be rebuilt from blank by hand |
| [ ] | M5-2 | Properties panel: label, what happens, stage, retry, fast track | M | M5-1 | Edits round-trip through the document |
| [ ] | M5-3 | Condition builder with generated expression and advanced field | M | M5-2, M1-4 | Every guard in both templates can be expressed |
| [ ] | M5-4 | Decision editing: options, availability; table rows appear on the Decisions screen | M | M5-2, M3-5 | New decision is runnable with uniform probabilities and a warning |
| [ ] | M5-5 | Live problems list with click-to-select; save blocked on errors | M | M5-1, M2-2 | Each problem code selects the right step |
| [ ] | M5-6 | World tables: who arrives, tests, resources; source chips | L | M3-3 | Changing a capacity changes the next run |
| [ ] | M5-7 | Import and export (JSON, YAML) | S | M2-1 | Exported project reimports identically |
| [ ] | M5-8 | Blank project with a minimal starter world | S | M5-6 | A three-step pathway can be built and run in five minutes |
| [ ] | M5-9 | Canvas positions saved per version | S | M5-1 | Layout survives reload |

## M6 Train JEV on your dataset (spec 06)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [x] | M6-1 | Dataset rows: schema, CSV reader, validator, report | M | M1-1 | Report lists every problem class in spec 06 |
| [x] | M6-2 | Decisions export from run logs; retire the adapter in `decision_model/tasks.py` | S | M6-1 | Exported rows validate against their own flowchart |
| [x] | M6-3 | `frequency` trainer producing a stub table; evaluation split by patient | M | M6-2, M1-3 | Loop test: simulate → export → train → table within sampling error → rerun matches |
| [x] | M6-4 | Model registry, training jobs, attach-model endpoint | M | M6-3, M2-5 | Train and attach through the API |
| [ ] | M6-5 | Data and training screen | M | M6-4, M3-5 | Upload, report, train, attach in the browser; imitation notice shown |
| [ ] | M6-6 | Real JEV: decide and train against the team's API | M | M1-6, T (F3) | Contract tests pass against the JEV address; a run uses it |
| [x] | M6-7 | `local` trainer (numpy model, imitation) | S | M6-4, M1-7 | Registered model usable at a decision point |
| [x] | M6-8 | Exploration run mode: random at chosen decision points | S | M1-3 | Produces outcome-labelled rows for every option |

## M7 Online (spec 07)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | M7-1 | Dockerfile and compose file | S | M3-1 | `docker run` serves the app with a data volume **Status: files written, `docker build` not run (no daemon); needs web/ merged.** |
| [x] | M7-2 | Access token, read-only demo mode, rate and size limits, JEV host allowlist | M | M2-5 | Requests without a token rejected; limits tested |
| [ ] | M7-3 | Host config and runbook | S | M7-1, T (F5) | Tuomas can deploy with one command **Status: runbook and `deploy/deploy.sh` written; waits on a host (F5).** |
| [ ] | M7-4 | CI on pull requests: tests, web build, type check, container build | S | M3-1 | Workflow green on a PR **Status: workflow written, not run on GitHub.** |
| [x] | M7-5 | Seed instance: two templates and a guided project | S | M7-3 | A first-time visitor can run the loop |
| [ ] | M7-6 | Synthetic-data notice on upload | S | M6-5 | Banner present **Status: backend done (`GET /api/access` data_notice); web banner open.** |

## M8 Evidence and robustness in the platform (after the loop works)

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | M8-1 | Evidence ledger: low, high and grade on every world parameter; ledger view | M | M5-6 | Counts of sourced and assumed inputs come from the world document |
| [ ] | M8-2 | Robustness run as a job (existing `sensitivity.py`) with tornado chart | M | M2-5 | "Holds in X of Y draws" for a chosen comparison |
| [ ] | M8-3 | Calibration as a job (existing `calibrate.py`): fit unknown capacities to observed waits | M | M2-5 | Simulated against observed table in the browser |
| [ ] | M8-4 | Capacity probe: "one more slot here gains X" | S | M2-6 | Table per run |
| [ ] | M8-5 | Pitch material updated for the platform framing | S | M4-4 | `docs/pitch/` templates refilled |
| [ ] | M8-6 | Open items from `docs/review.md`: booking time split from queueing; ranges next to headlines; sensitivity of the accepted Finnish changes | M | – | Review items closed |

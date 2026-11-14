# C6 Platform (service, web app, datasets and training, deployment)

| | |
|---|---|
| Packages | `service/`, `web/`, `deploy/`, `demo/` |
| State | Built in the first wave and merged into `overnight/sim`. Detailed specs: `docs/platform/README.md` and `docs/platform/specs/01` to `07`; API shapes: `service/README.md`; operations: `docs/platform/runbook.md` |
| Depends on | C3, C4, C5, later C1 |
| Track | The offline flow page and the dashboard are on the submission track; the rest is platform track |

## Purpose

The shell around the loop: store projects, worlds and flowchart versions; run simulations and
optimisations as background jobs; show the flowchart simulation as the main screen; let a person
edit decision tables, train a table from decisions, and deploy the whole thing.

## What exists

| Part | Where | What it does |
|---|---|---|
| Service | `service/` | FastAPI app; SQLite plus gzip JSON blobs; templates (Finnish scenario, Norway check); projects, world, immutable flowchart versions; validation; "try a decision"; runs with progress, cancel, identical-run cache; flow endpoint; optimisations with evidence and "apply a subset"; datasets, trainers, models; access token, read-only mode, limits, allowlist for outside decision services |
| Web app | `web/` | React, TypeScript, React Flow. Projects; the flowchart canvas with auto-layout; decisions table editor; run panel; run layers (flow, time, queues, decisions); playback of patients as dots; patient trace. `?mock=1` runs without the service |
| Offline flow page | `demo/flow.html` | No build, opens from disk; Norway observed against optimised side by side; Finland today against the reorder-only result; layers, playback, trace. The fallback demo |
| Dashboard | `demo/index.html` | The six-screen report fed by `demo/data/demo_bundle.json` |
| Deployment | `Dockerfile`, `docker-compose.yml`, `deploy/`, `.github/workflows/ci.yml` | Written, **not run**: no container runtime or host was available in the build session |

## What is missing (first-wave tickets not done)

| Gap | Old ticket | Notes |
|---|---|---|
| Report tab (dashboard inside the app) and the Compare layer | M3-7, M3-8 | Small; needs the web lane |
| Optimise in the browser: panel, suggested changes with evidence, graph diff, accept and rerun | M4-1 to M4-4 | The API exists; this is web work |
| Flowchart editor: add, move, connect steps; properties; condition builder; problems list; world tables; import and export | M5-1 to M5-9 | The largest remaining web piece |
| Data and training screen | M6-5 | API exists |
| Real JEV hook-up | M6-6 | Waits for the JEV owner |
| A real container build, a host, a CI run | M7-1, M7-3, M7-4 | Needs a human with a host (fork F5) |
| Fast and slow test tiers, contract test folder, golden checks in one command | new: `WP-INFRA-1` | See `02-execution-strategy.md`, "The gate" |
| Findings of the security review | `docs/platform/security-review.md` when it lands | Triage into fixes |

## What changes for the vision

| # | Change | Depends on |
|---|---|---|
| W1 | **Cohorts as a resource**: create a cohort from a catalogue, see its checks, pick it for a run | C1 P6 |
| W2 | **Patient card viewer**: background, what was presented, what each step revealed and when; hidden truth only in an explicit teaching view | C1 P1, P10 |
| W3 | **Catalogue browser**: conditions, variables and tests with their sources and grades; the ledger counts | C2 K7 |
| W4 | **Decision matrix and score editors** on the decisions screen | C4 J5 |
| W5 | **Criteria changes in the optimise view**: before and after rows of a decision table next to the graph diff | C5 O3 |
| W6 | Narratives in the patient trace (the referral letter as the GP would have written it) and a link to the note reader | C1 P7, Eemeli's side |

## Sub-wholes (for the spec agent)

Group by screen, because web lanes collide on shared components otherwise:

| # | Sub-whole | Contains |
|---|---|---|
| F1 | Close the run screen | Report tab, Compare layer |
| F2 | Optimise screen | M4-1 to M4-4, W5 |
| F3 | Editor | M5 tickets, W4 |
| F4 | Patients and catalogue screens | W1, W2, W3, W6 |
| F5 | Data and training screen | M6-5 |
| F6 | Test infrastructure | `WP-INFRA-1` |
| F7 | Security fixes | from the review |
| F8 | Deploy for real | with a human |

The canvas component is shared by F1, F2 and F3: one lane at a time may change it; the others
build beside it.

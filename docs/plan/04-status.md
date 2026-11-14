# Status

The only file in this folder that changes often. Written by the integrator at every sync point.
Last update: **Sat 14 Nov 2026, about 17:30 Helsinki.** Deadline: Sun 15 Nov 10:00 Helsinki.

## Branches

| Branch | What | State |
|---|---|---|
| `main` | Eemeli's classifier, note reader, video animation, live demo page | Team's default branch |
| `overnight/sim` | Integration branch: simulator, optimiser, scenarios, dashboard, and the whole first platform wave | PR #2 into `main`, open |
| `comms-pointer` | `scripts/comms.py` and the `CLAUDE.md` pointer to the agent channel | PR #3 into `main`, open; already inside `overnight/sim` |
| `agent-comms` | The agent channel (`AGENT_COMMS.md`) | Live |
| `plat/jev`, `plat/expr`, `plat/flow`, `plat/svc-a`, `plat/svc-b`, `plat/web`, `plat/ops`, `plat/ds` | First-wave lanes | Merged into `overnight/sim`; worktrees can be removed |
| `plat/evidence`, `plat/secreview` | Evidence sweep; security review | Running |
| `platform/next` | Platform track for the patient engine and later waves | To create once the two running lanes are merged |

## What is built (merged into `overnight/sim`, full suite green: 691 tests before the datasets lane, rerun pending)

| Component | Built | Old tickets |
|---|---|---|
| C3 Simulation | Engine, flowchart documents, safe conditions, structured validation, flow view, progress hook | M1-2, M1-4, M2-1, M2-2, M2-11 library |
| C4 Decision layer | Contract, adapter, stub tables, HTTP backend and stub server, local backend, command-line flags; dataset rows, frequency and local trainers, exploration mode | M1-1, 3, 5 to 8, 10; M6-1 to 4, 7, 8 |
| C5 Optimiser | Order-of-steps search; apply a subset; works under stub tables (rule and stub give the same changes, test-locked) | M2-7 |
| C6 Platform | Service (projects, versions, validate, decide, jobs, runs, flow endpoint, optimisations, datasets, models, access control and limits); web app (projects, canvas, decisions table, run panel, layers, playback, trace); offline flow page; deployment files (not run) | M2-3 to 10; M3-1 to 6, 10 to 13; M7-2, M7-5 |
| C7 Evidence | As before the wave; golden check for the Norway template added | – |

Fixed at integration: two different `service/runtime.py` (one is now `service/prepare.py`);
"always choose X" allowed under stub tables and made to work there; the service catches an
unreachable decision service; the Norway template now uses the calibrated world (it showed about
11% where the published figure is 40%).

## Not built from the first plan

M1-9 (GP judgement as a decision; now C3 E4 and C4 J4), M3-7, M3-8, M3-9, M4-1 to M4-5, M5-1 to
M5-9, M6-5, M6-6, M7-1, M7-3, M7-4 (written, never run), M7-6 web part, M8-1 to M8-6 (in
progress on `plat/evidence`). See `components/C6-platform.md` for how they are regrouped.

## Running now

| Lane | Branch | Doing |
|---|---|---|
| Evidence | `plat/evidence` | Number consistency across documents, ledger, ranges, booking-versus-queue analysis, pitch templates |
| Security review | `plat/secreview` | Read-only review of the service and the HTTP backend; report plus tests |

## Next (in order)

| # | What | Who | Track |
|---|---|---|---|
| 1 | Merge the two running lanes; record first-wave decisions in `docs/decisions.md` (partly done: D32 to D38) | integrator | both |
| 2 | `WP-INFRA-1`: `slow` markers, `tests/contracts/`, one gate command, golden checks | one builder | both |
| 3 | Triage the security review into fixes | architect, then one builder | platform; anything exploitable on the hosted demo is submission track |
| 4 | **Spec wave**: spec agents write work packages for C1, C2, C4, C5 from the component files (`03-speccing-guide.md`); C5's first package is the design spike O1 | spec agents (Tuomas starts them, or asks the architect to) | platform |
| 5 | **Research lane** for the catalogue content (C2 K3 to K5), once K1 (the format) is fixed | research agents with web access | platform |
| 6 | **Build wave** for C1: P1 and P2 (contracts) first, then P3, P4, P6, P7 in parallel, then P5 and P8 | builders | platform |
| 7 | Submission polish: the demo path, pitch numbers, video numbers; freeze Sunday 06:00 | Tuomas, Eemeli, their agents | submission |

## Waiting for a human

| Item | Options and lean | Since |
|---|---|---|
| Assumptions V1 to V8 in `00-vision.md` | Used as written until corrected | 14 Nov |
| Forks F1 to F7 (`docs/platform/README.md` section 5) | Built on the leans: F1 now proposed as (b) through V4; F2 sample; F3 our contract; F4 React; F7 off under a model | 14 Nov |
| Which page is the submission's main page (channel entry 1114-132734) | Lean: `demo/flow.html` as the AstraZeneca page and offline fallback, `live_demo/` as the hosted URL | 14 Nov |
| Merge PR #3 (agent channel pointer) and PR #2 | Toivo or Tuomas | 14 Nov |
| Who owns JEV; does an API exist | Unknown | 14 Nov |
| A host for deployment (fork F5) | `deploy/deploy.sh user@host --seed` is ready but untested | 14 Nov |
| A clinician to read the catalogue | Until then it is labelled draft | 14 Nov |
| Earlier pending decisions D17, D18, D20, D25, D27 | See `docs/decisions.md` | 14 Nov |

## Known problems

| Problem | Where | Owner |
|---|---|---|
| Deployment files were never built or run | `Dockerfile`, `deploy/`, CI workflow | needs a human with Docker and a host |
| If a standardised option is not on offer, rule and stub policies differ (first option against uniform) | `jev/`, `pathway_sim/policy.py` | C4 spec |
| Full test suite takes 4 to 7 minutes on a loaded machine | all | `WP-INFRA-1` |
| A Finnish optimisation at full size through the service has not been timed against the 15-minute job limit | `service/` | C6 |
| Norway graph is hard to read at laptop widths in both the web app and the flow page | `web/`, `demo/flow.html` | C6 F1 |
| Agent decisions from first-wave reports are only partly in the decisions log | `docs/decisions.md` | integrator |

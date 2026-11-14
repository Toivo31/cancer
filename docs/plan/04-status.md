# Status

The only file in this folder that changes often. Written by the integrator at every sync point.
Last update: **Sat 14 Nov 2026, about 17:00 Helsinki.** Deadline: Sun 15 Nov 10:00 Helsinki.

## Branches

| Branch | What | State |
|---|---|---|
| `main` | Eemeli's classifier, note reader, video animation, live demo page | Team's default branch |
| `overnight/sim` | Integration branch: simulator, optimiser, scenarios, dashboard, and the whole first platform wave | PR #2 into `main`, open |
| `comms-pointer` | `scripts/comms.py` and the `CLAUDE.md` pointer to the agent channel | PR #3 into `main`, open; already inside `overnight/sim` |
| `agent-comms` | The agent channel (`AGENT_COMMS.md`) | Live |
| `plat/jev`, `plat/expr`, `plat/flow`, `plat/svc-a`, `plat/svc-b`, `plat/web`, `plat/ops`, `plat/ds` | First-wave lanes | Merged into `overnight/sim`; worktrees can be removed |
| `plat/evidence` | Evidence sweep | Merged |
| `plat/secreview` | Security review | Merged (report and tests only) |
| `platform/next` | Platform track for the patient engine and later waves | To create once the two running lanes are merged |

## What is built (merged into `overnight/sim`; full suite green, 718 tests)

| Component | Built | Old tickets |
|---|---|---|
| C3 Simulation | Engine, flowchart documents, safe conditions, structured validation, flow view, progress hook | M1-2, M1-4, M2-1, M2-2, M2-11 library |
| C4 Decision layer | Contract, adapter, stub tables, HTTP backend and stub server, local backend, command-line flags; dataset rows, frequency and local trainers, exploration mode | M1-1, 3, 5 to 8, 10; M6-1 to 4, 7, 8 |
| C5 Optimiser | Order-of-steps search; apply a subset; works under stub tables (rule and stub give the same changes, test-locked) | M2-7 |
| C6 Platform | Service (projects, versions, validate, decide, jobs, runs, flow endpoint, optimisations, datasets, models, access control and limits); web app (projects, canvas, decisions table, run panel, layers, playback, trace); offline flow page; deployment files (not run) | M2-3 to 10; M3-1 to 6, 10 to 13; M7-2, M7-5 |
| C7 Evidence | Number sweep across documents; ledger (`docs/ledger.md`: Finland 49 input blocks, 9 sourced, 40 assumptions; Norway 25, 22 sourced); ranges (`docs/ranges.md`); booking against queue split; golden check for the Norway template | M8 partly |

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
| – | – | No lane is running |

## Next (in order)

| # | What | Who | Track |
|---|---|---|---|
| 1 | Merge the two running lanes; record first-wave decisions in `docs/decisions.md` (partly done: D32 to D38) | integrator | both |
| 2 | `WP-INFRA-1`: `slow` markers, `tests/contracts/`, one gate command, golden checks | one builder | both |
| 3 | Triage the security review into fixes | architect, then one builder | platform; anything exploitable on the hosted demo is submission track |
| 4 | **Spec the Sunday slice** of the patient engine (C1 P1 to P10) and the first catalogue (C2 K1, K2 plus symptoms and bloodwork) | spec agents (Tuomas starts them, or tells the architect to) | platform, then submission |
| 5 | **Build the slice**: P1, P2, P3, P8 in parallel; then P4 to P6; then P7, P9, P10 | builders | platform, then submission |
| 6 | **Generate a first library** of about 300 cards and its audit | whoever has the endpoint and key | submission |
| 6b | After the submission: C3 E7 (states, treatment, episodes), E4 and C4 J4 (all decisions as nodes), C5 O1 spike, C3 E8 spike | | platform |
| 7 | Submission polish: the demo path, pitch numbers, video numbers; freeze Sunday 06:00 | Tuomas, Eemeli, their agents | submission |

## Waiting for a human

| Item | Options and lean | Since |
|---|---|---|
| D42: is the patient engine part of Sunday's submission (my reading of "yes it does") | Read as yes | 14 Nov |
| Assumptions V2, V5, V6, V8 to V11 in `00-vision.md`, above all V10 (`guided` error rates) | Used as written until corrected | 14 Nov |
| A language-model endpoint and budget for generating patients; who runs it (the architect session has none) | Needed before any real library exists | 14 Nov |
| Booking split in the dashboard (channel 1114-141641) and emergent booking leads (C3 S12) | Lean: say plainly that leads are inputs; rebuild after the submission | 14 Nov |
| Stale 61% in Eemeli's `video/dots/README.md`, `docs/video_plan_draft.md` | Eemeli | 14 Nov |
| Forks F2 to F7 (`docs/platform/README.md` section 5); F1 is settled by D41 | Built on the leans: F2 sample; F3 our contract; F4 React; F7 off under a model | 14 Nov |
| Which page is the submission's main page (channel entry 1114-132734) | Lean: `demo/flow.html` as the AstraZeneca page and offline fallback, `live_demo/` as the hosted URL | 14 Nov |
| Merge PR #3 (agent channel pointer) and PR #2 | Toivo or Tuomas | 14 Nov |
| Who owns JEV; does an API exist | Unknown | 14 Nov |
| A host for deployment (fork F5) | `deploy/deploy.sh user@host --seed` is ready but untested | 14 Nov |
| A clinician to read the catalogue | Until then it is labelled draft | 14 Nov |
| Earlier pending decisions D17, D18, D20, D25, D27 | See `docs/decisions.md` | 14 Nov |

## Security review (`docs/platform/security-review.md`, reviewed the tree before access control was merged)

18 findings: 3 high, 7 medium, 8 low. Rerun on the current tree, file by file:

| Finding | State now |
|---|---|
| F1 no access token (high) | Fixed by the deployment lane; the review's test now passes |
| F2 outside decision service can be pointed at any host (high) | Allowlist in place, credentials and echoed response text no longer returned (three of the review's tests now pass). Still open: client-chosen long timeout, slow calls stalling the API |
| F16 the flow endpoint re-simulates inside the API process (high) | **Open** |
| F4 wrong-typed decision policy gave a 500 | Fixed |
| F13 missing security headers | Fixed |
| F3 NaN and Infinity stored; F5 response size; F6 tracebacks in job errors; F7 deleted project's jobs keep running; F14 quotas; F18 memory; the low ones | **Open** |

`tests/security/` is excluded from the default test run: nine of its expected-to-fail tests now
pass (the holes are closed) and five need the allowlist configured for a local test server. Work
package C6 F7: turn the passing ones into normal tests, fix the five, then close F16, F3, F5 to F7.
Do F16 before any public URL.

## Known problems

| Problem | Where | Owner |
|---|---|---|
| Deployment files were never built or run | `Dockerfile`, `deploy/`, CI workflow | needs a human with Docker and a host |
| If a standardised option is not on offer, rule and stub policies differ (first option against uniform) | `jev/`, `pathway_sim/policy.py` | C4 spec |
| Full test suite takes 4 to 7 minutes on a loaded machine | all | `WP-INFRA-1` |
| A Finnish optimisation at full size through the service has not been timed against the 15-minute job limit | `service/` | C6 |
| Norway graph is hard to read at laptop widths in both the web app and the flow page | `web/`, `demo/flow.html` | C6 F1 |
| Agent decisions from first-wave reports are only partly in the decisions log | `docs/decisions.md` | integrator |

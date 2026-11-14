# Status

The only file in this folder that changes often. Written by the integrator at every sync point.
Last update: **Sat 14 Nov 2026, 18:30 UTC (20:30 Helsinki).** Deadline: Sun 15 Nov 10:00 Helsinki; freeze 04:00 UTC.

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

## Running now (14 Nov, 20:40 UTC; Tuomas back)

Merged, green and pushed since 18:30 (`d7e08e2`): g2@2 results prompt and the two new audit checks (D52), the
population model for age and smoking (D53), the encounter loop retuned to the calibrated chain (8 of 8 tuning seeds,
6 of 8 fresh, 7 of 8 pooled), the Norway optimiser on the 184 fitting settings (it arrives at the authors' redesign,
it does not beat it; without new equipment it beats the scanner alone in 128 of 184), decisions D52 to D57, the
pitch and demo lanes (ranges next to every Norway point value), and an audit-report fix.

Model-written cards: the five 500-card Gemini libraries (2,495 cards, `g1@1` + `g2@1`) are committed under
`libraries/g2v1_audit_fail/`, outside the scanned folder. All five fail 13 of 40 audit checks: report wording
(expected, B1), backgrounds (expected, old step) and **findings in all 11 conditions** (presentations far more
textbook than the catalogue; unrelated labs low in nearly every card). No new real-model run until the two lanes
below report.

| Lane | What | Model |
|---|---|---|
| `w8/g1skew` | Root cause of the findings skew in model-written patients; fix as a new patient prompt version | Opus |
| `w8/g2blind` | Make the results prompt blind (review w8 blocker B1: g2@2 still shows all results incl. definitive ones), leak rule M1, histology M2 | Opus |
| `w8/jev-demo` | JEV demo page: model card (Hugging Face placeholder), node-level tester, five presets incl. answer comparison | Opus |
| `w8/fi-sens` | Finland sensitivity analysis | Sonnet |

`w8/verify` (review of tonight's fixes, `docs/review_w8_fixes.md`) is finished; it is merged through `w8/g2blind`.

Ticket index for wave 8 and after the submission (sorted: before freeze / after submission / needs a human): `docs/plan/packages/W8/README.md`.

## Next (in order)

| # | What | When |
|---|---|---|
| 1 | Merge `w8/g1skew` and `w8/g2blind`; gate; push; then Tuomas runs `scripts/generate_gemini.sh trial`, audit, then `full` | as they finish |
| 2 | Audit the new libraries, merge, build training and held-out sets; refill pitch | after 1 |
| 3 | Merge `w8/jev-demo` and `w8/fi-sens`; regenerate demo bundles | as they finish |
| 4 | 01:00 UTC checkpoint; freeze 04:00 UTC | |

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

## Security review (`docs/platform/security-review.md`; per-finding status and proving tests are in its Status table)

18 findings: 3 high, 7 medium, 8 low. State at the 14 Nov freeze (WP-C6-SEC1 merged, plus a wall-clock deadline for outside decision calls):

| Finding | State now |
|---|---|
| F1 no access token (high) | Fixed (deployment lane) |
| F2 outside decision service can be pointed at any host (high) | Fixed: allowlist, no credentials, no echoed response text, timeout capped at 5 s, 1 retry, 1 MiB response, total wall-clock deadline |
| F16 flow endpoint re-simulates in the API process (high) | Fixed: stored flow served as is; other parameters rebuild as a job (own process, 60 s limit, 429 when busy) |
| F3, F4, F5, F6, F7, F9, F10, F11, F13 | Fixed, each with a test |
| F14 quotas, F18 memory | Accepted for the hackathon: existing rate, job-start and active-job limits; hosted settings `PATHWAY_JOB_SECONDS=120`, `PATHWAY_MAX_PATIENTS=20000`, `PATHWAY_MAX_SEEDS=3`, `PATHWAY_MAX_JOBS=1..2` must be set on the host |
| F8, F12, F15, F17 | Accepted, still `xfail(strict=True)` (see the review) |

`tests/security/` runs as one command (about 2.5 min on a loaded 2-CPU machine) and is in the slow tier via `tests/slow_tests.txt`.

## Known problems

| Problem | Where | Owner |
|---|---|---|
| Deployment files were never built or run | `Dockerfile`, `deploy/`, CI workflow | needs a human with Docker and a host |
| If a standardised option is not on offer, rule and stub policies differ (first option against uniform) | `jev/`, `pathway_sim/policy.py` | C4 spec |
| Full test suite takes 4 to 7 minutes on a loaded machine | all | `WP-INFRA-1` |
| A Finnish optimisation at full size through the service has not been timed against the 15-minute job limit | `service/` | C6 |
| Norway graph is hard to read at laptop widths in both the web app and the flow page | `web/`, `demo/flow.html` | C6 F1 |
| Agent decisions from first-wave reports are only partly in the decisions log | `docs/decisions.md` | integrator |

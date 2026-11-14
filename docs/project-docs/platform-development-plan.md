# Platform development plan (14 Nov 2026, summary)

Full plan, specs and tickets are in the repo: `Toivo31/cancer`, branch `overnight/sim` (pull request #2 into `main`), folder `docs/platform/` (`README.md`, `specs/01` to `07`, `tickets.md`). This page is the short version for the coordination chat. **Nothing in the plan is built yet.**

## Design rule (decision D31, 14 Nov, from Tuomas's review)
**The flowchart simulation is the main screen.** Run results are layers on the graph itself: patient flow counts on edges, time per step (where time is lost), queues, the shares chosen at each decision point, and a compare layer for before/after. A playback slider replays the cohort as dots moving through the graph; clicking a dot opens that patient's trace. The existing dashboard (`demo/index.html`) is only a report/info tab. Offline fallback for Sunday: `demo/flow.html`, a no-build page with the graph, layers and playback from precomputed run logs (ticket M3-13). New tickets: M2-11 (flow endpoint), M3-10 (run layers), M3-11 (playback), M3-12 (patient trace), M3-13 (offline flow page).

## Where the code is
All simulator work is on branch `overnight/sim`, not yet on `main`. 77 tests pass. To try it (on a Mac use `python3`, inside a clone):

```
git clone https://github.com/Toivo31/cancer.git && cd cancer
git checkout overnight/sim
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
open demo/index.html                 # info dashboard, works offline
python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed --n 1000
python -m pathway_sim demo --quick   # whole loop, about 2.5 min
```

## Direction (Tuomas)
Online platform with one loop: build a flowchart → attach JEV to its decision points → train JEV on your dataset → simulate → optimise → rerun. JEV comes as an API: revealed context and offered options in, a probability per option out. Until it exists, a stub with hardcoded probabilities per decision point answers through the same contract.

## How the existing build fits
- **Reuse as libraries:** the simulation engine (`pathway_sim`), the optimiser, the two lung scenarios (they become templates), calibration and sensitivity code. The engine's run log already records every step's ready/start/end/result times, the critical path, and the choices made per patient, which is what the run layers and playback need.
- **Adapt:** the engine already asks a "policy" for a probability per option at choice nodes; that seam is where JEV plugs in. Today's fixed "mix" shares become the stub's probability tables.
- **New:** JEV contract, stub server and HTTP client; a service with background jobs and storage; the web app (flowchart canvas with run layers and playback, then the editor); dataset format, trainers and model registry; deployment.
- **Gaps:** few real decision points today (nurse and GP judgement is modelled as a noisy test, not a decision); conditions are evaluated with Python `eval`, which must be replaced before hosting; `decision_model/` is a local stand-in, not the team's JEV.

## Milestones
| # | Milestone | What can be tested |
|---|---|---|
| M0 | Foundation (done) | CLI and static dashboard |
| M1 | JEV in the graph: decision points, stub, API contract, stub server | CLI run with stub or an HTTP address; change a probability, result moves |
| M2 | Service: API and background jobs (incl. flow endpoint) | The loop with `curl` |
| M3 | Run from the browser: flowchart with run layers and playback, edit probabilities, report tab | Browser |
| M4 | Optimise and rerun in the browser (before/after on the canvas) | Browser |
| M5 | Build your own flowchart (editor, world tables) | Browser |
| M6 | Train JEV on a dataset; real JEV API hookup | Browser; contract tests against JEV |
| M7 | Online: container, access token, deploy | Public address |
| M8 | Evidence ledger, robustness and calibration in the platform | Browser |

71 tickets in `docs/platform/tickets.md`, each with size, dependencies and an acceptance line.

## Forks waiting on Tuomas (leans, not decisions)
| # | Fork | Lean |
|---|---|---|
| F1 | What is a decision point: only explicit decision nodes, or also clinician judgements now modelled as noisy tests | Explicit nodes first, then convert the Finnish nurse and GP steps one at a time |
| F2 | Sample from JEV's probabilities or take the most likely option | Sample by default, switchable per run |
| F3 | JEV API contract and who owns JEV | Start from the JSON proposal in spec 02; JEV owner marks what does not fit |
| F4 | Web stack | React + React Flow |
| F5 | Hosting, visibility, data | One container on Tuomas's host of choice, shared token, synthetic data only |
| F6 | Cut for Sunday 10:00 | M1 to M4 as thin slices, then M5; offline flow page as fallback demo |
| F7 | May the optimiser fix a decision when a JEV model is attached | Off by default |

Still pending from before: D17 (Norwegian headline 88% with the faster scanner or 68% without new equipment), D20 (90-day Finnish target), D25 (decision-model reward trade-off), D27 (Finnish headline 18% → 33% from two reorderings; urgent booking as a conditional finding).

## Note on priorities
Judging is actionability 30, insight 25, data quality 20, execution 15, clarity 10. The platform mainly raises execution and the demo. The evidence-grounding plan and the open items in `docs/review.md` raise the rest.

# Platform master development plan

Status: **draft for Tuomas, 14 Nov 2026.** Nothing in this folder has been built yet. Direction set
by Tuomas; every choice marked *fork* is open and has a lean, not a decision.

## 1. What we are building

An online platform with one loop:

1. **Build** a flowchart of a care pathway (steps, allowed orders, decision points).
2. **Attach JEV** to the decision points. JEV is the team's decision model. It arrives as an API:
   given the context at a decision point and the options on offer, it returns a probability for
   each option. Until it exists, a **stub** answers with hardcoded probabilities per decision point.
3. **Train** JEV on the user's dataset of past decisions.
4. **Simulate** synthetic patients through the flowchart with JEV making the decisions.
5. **Optimise** the flowchart from what the run revealed, and **rerun** on the same patients.

The Junction entry (lung cancer, Norway check, Finnish scenario) becomes the first two templates on
this platform, not a separate thing.

## 2. How what exists fits

Everything below is on branch `overnight/sim` (77 tests pass). `main` has none of it yet.

| Part of the vision | What exists | Verdict |
|---|---|---|
| Flowchart simulation | `pathway_sim/`: event engine, DAG flowcharts with guards, parallel steps, queues, synthetic patients, metrics, common random numbers | **Reuse.** This is the engine. Needs a JSON document format, structured validation errors, a progress hook |
| Decision points | `choice` nodes; the engine asks a `Policy` for a probability per option | **Reuse the seam.** The `Policy` interface is exactly where JEV plugs in |
| JEV stub with hardcoded probabilities | `RulePolicy` `mix` (fixed shares per choice) and `rules` | **Adapt.** Same idea, but it has to become conditional probability tables behind the JEV contract, with the engine doing the sampling |
| JEV as an API | Nothing. `decision_model/` is a local numpy stand-in, not the team's JEV | **New.** Contract, stub server, HTTP client. `decision_model/` becomes one optional backend behind the same contract |
| Train JEV on a dataset | `decision_model/in_loop.py` trains from run logs; no dataset format, no registry | **Adapt.** Its log-to-examples code is the start of the dataset format |
| Optimise and rerun | `optimiser/`: proposals from revealed records, rerun acceptance, guardrails, held-out report | **Reuse.** Needs "apply a subset of changes" and a job wrapper |
| Online platform | Static dashboard `demo/index.html` fed by a JSON bundle | **New** service and web app. The dashboard is reused as the results view |
| Build your own flowchart | Hand-written YAML | **New** editor |
| Evidence and robustness | `params/` with sources, `calibrate.py`, `sensitivity.py`, validation docs | **Reuse later** as platform features (milestone M8) |

Three gaps the reuse does not cover, in order of risk:

1. **Few real decision points today.** In the Finnish scenario, the nurse's and GP's judgement is
   modelled as a noisy "test" driven by hidden truth, not as a decision. For JEV to power the
   flowchart, those become decision points (fork F1).
2. **Guards are evaluated with Python `eval`.** Fine for our own YAML, unsafe for an online editor.
   A safe expression evaluator is required before anything is hosted (ticket M1-4).
3. **No server, storage or jobs.** A Finnish run is 19k patients and takes seconds; an optimisation
   takes minutes. That needs background jobs, not request/response.

## 3. Architecture

```
web/  (browser app)                  service/  (HTTP API + jobs)                  libraries
┌──────────────────────┐   JSON    ┌──────────────────────────────┐    ┌───────────────────────┐
│ builder  JEV  run    │◄────────►│ projects, worlds, flowcharts  │───►│ pathway_sim  (engine) │
│ optimise  data       │           │ runs, optimisations, datasets │───►│ optimiser             │
└──────────────────────┘           │ models, jobs      (SQLite)    │───►│ jev  (contract, stub, │
                                   └──────────────────────────────┘    │      client, trainer) │
                                                                       └──────────┬────────────┘
                                                                                  │ HTTP, same contract
                                                                       ┌──────────▼────────────┐
                                                                       │ JEV API (team's model)│
                                                                       └───────────────────────┘
```

Rules that keep the parts separable:

- **The engine never knows which decision backend it talks to.** Stub, HTTP JEV and local model all
  implement one contract (spec 02).
- **Documents are JSON, versioned, immutable once run.** A run is fully described by
  (world, flowchart version, decision policy, n, seeds), so every result can be reproduced.
- **The service only orchestrates.** All simulation and optimisation logic stays in the libraries,
  usable from the CLI and tests without a server.
- **Decision backends see revealed information only.** The same boundary the optimiser already has.

## 4. Milestones

Each milestone ends with something Tuomas can run. Specs are in `specs/`, tickets in `tickets.md`.

| # | Milestone | You can test | Spec | Size |
|---|---|---|---|---|
| M0 | Foundation (done) | `python -m pathway_sim demo`, dashboard | – | done |
| M1 | **JEV in the graph**: decision points, stub with hardcoded probabilities, API contract, stub server | CLI run with `--jev stub` and `--jev http://…`; change a probability, see the result move | 01, 02 | M |
| M2 | **Service**: API for flowcharts, runs, optimisations; background jobs | The whole loop with `curl` or the generated API page | 01, 03 | M–L |
| M3 | **Run from the browser**: open a template, see the graph, edit JEV probabilities, run, see results | Browser at `localhost:8000` | 04 | L |
| M4 | **Optimise and rerun in the browser**: suggested changes with evidence, accept, rerun, compare | Same | 04, 05 | M |
| M5 | **Build your own flowchart**: full editor, world editor, import/export | Same | 01, 04 | L |
| M6 | **Train JEV on your dataset**: upload, validate, train, attach; real JEV API hookup | Same; contract tests against the JEV API | 06 | M–L |
| M7 | **Online**: container, access control, deployment | Public URL | 07 | S–M |
| M8 | Evidence ledger, robustness and calibration inside the platform | Same | – | M |

Order rationale: M3 and M4 come before the editor (M5) because a read-only graph plus run and
optimise already gives the complete loop end to end. The editor is the largest single piece of UI
and is worth most once the loop behind it works.

Parallel tracks once M1's contract (ticket M1-1) and M2's API shape (M2-3) are fixed:
engine and JEV (M1), service (M2), web against the API description (M3), dataset library (M6-1..3).

## 5. Forks that need Tuomas

| # | Fork | Options | Lean |
|---|---|---|---|
| F1 | What is a decision point? | (a) only explicit decision nodes; (b) also every clinician judgement now modelled as a noisy test (nurse triage, GP referral) | (a) now so M1 is small, then convert the Finnish nurse/GP steps one at a time (M1-9). (b) is what "JEV powers the flowchart" really means |
| F2 | How the simulator uses JEV's probabilities | sample from them (simulates varied practice) / take the most likely option (deterministic tool) | Sample by default, switchable per run. Hardcoded probabilities only make sense if sampled |
| F3 | JEV API contract | my JSON proposal in spec 02 / whatever the JEV owner already has | Start from spec 02 and ask the JEV owner to mark what does not fit. **Who owns JEV, and does an API exist yet?** |
| F4 | Web stack | React + React Flow with a build step / no-build vanilla JS like the current dashboard | React + React Flow. A graph editor by hand costs more than the build step |
| F5 | Hosting and data | which host; public or team-only; any real data | One container on a host of your choice, shared access token, synthetic data only. I cannot deploy from this session, so this needs your account |
| F6 | Cut for Sunday 10:00 | how far down the milestone list | M1 to M4 as thin slices, then M5. Keep the current dashboard as the fallback demo. M6 beyond the simple trainer and M7 are stretch |
| F7 | `standardise` change under JEV | optimiser may still fix a decision / decisions belong to JEV only | Off by default when a JEV model is attached, available as an explicit option |

A note on F6. The judging weights are actionability 30, insight 25, data quality 20, execution 15,
clarity 10. The platform mostly raises execution and the demo. The independent review's open items
(`docs/review.md`) and the evidence-grounding plan raise the other 75 percent. I would not let the
editor crowd those out before the deadline.

## 6. Risks

- **JEV contract mismatch.** If the real JEV wants embeddings or a different context shape, the
  client adapter changes; the engine does not. The contract test suite (M1-6) makes a mismatch
  visible on day one.
- **HTTP per decision is slow.** A Finnish run makes about 40k decisions. Mitigation in spec 02:
  in-process backend for the stub, connection reuse and caching for HTTP, batch endpoint.
- **Editor scope.** A free-form editor invites flowcharts the engine rejects. Mitigation: structured
  validation with click-to-fix (M2-2) before the editor exists.
- **Learning from decision logs learns practice, including its flaws.** Training by imitation gives
  a model that reproduces the dataset, not better decisions. Spec 06 says where this is stated in
  the UI.
- **Time.** See F6.

## 7. Files in this folder

- `specs/01-flowchart-model.md`: document format, node and edge types, validation, safe guards
- `specs/02-jev-interface.md`: decision contract, stub, HTTP API, sampling, performance
- `specs/03-service-api.md`: resources, jobs, storage, limits
- `specs/04-web-app.md`: screens and the order they get built
- `specs/05-optimise-rerun.md`: optimiser as a service, accepting a subset, behaviour under JEV
- `specs/06-datasets-training.md`: dataset format, trainers, model registry
- `specs/07-deploy-ops.md`: container, access, hosting, CI
- `tickets.md`: every ticket with dependencies and acceptance criteria

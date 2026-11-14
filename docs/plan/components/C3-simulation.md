# C3 Simulation

| | |
|---|---|
| Package | `pathway_sim/` |
| State | Built and tested (engine, flowchart documents, safe conditions, validation, metrics, flow view). Detailed contract: `docs/architecture.md`; document format: `docs/platform/specs/01-flowchart-model.md` |
| Depends on | C1 (patients, reveal), C4 (decisions) |
| Used by | C5, C6 |
| Track | Changes below are platform track. The engine as it is serves the submission |

## Purpose

Move patients through a flowchart of care steps over simulated time: arrivals, queues for limited
resources, steps that take time and reveal facts, decision points, parallel work-up, exits. Log
everything needed to say where time was lost and what each patient's path revealed.

## What exists (do not rebuild)

- Event engine with three resource types (capacity queue, drawn delay, weekly batch), guards,
  decision nodes, retry, parallel prerequisites, fast-track priority, a progress hook.
- Flowcharts as versioned JSON documents with converters to and from YAML; a `decision` node kind.
- Conditions in guards and rules through a safe evaluator (`expr.py`), no `eval`.
- Structured validation with problem codes (`validate.py`, `problems.py`).
- Run log with per-step timing (ready, start, end, result, critical path), choices with the
  backend that answered, and metrics by stage, step and group.
- Flow view (`flow.py`, format `flow/1`) for the canvas layers and playback.
- The Norwegian check (observed pathway reproduces the published 40% within 42 days) and the
  Finnish scenario with calibrated capacities.

## What changes for the vision

The vision's sentence "nodes reveal hidden variables" is today "a node runs a test that returns
yes or no". The changes, in dependency order:

| # | Change | Why | Notes for speccing |
|---|---|---|---|
| S1 | **Typed, multi-output reveals.** A step that performs a catalogue test adds all of the test's outputs to the patient's revealed record (`chest_ct.size_mm = 17`, `chest_ct.location = "peripheral"`), not one boolean | Decision matrices and the optimiser need the actual facts | Keep `positive_when` so existing guards (`when: "cxr"`) still read a boolean. Names in conditions become `step.output`. Unrevealed reads as unknown (`None`), as today |
| S2 | **Patients come from C1 cohorts** through the reveal handle | One patient model for all scenarios | First through C1's adapter (no engine change), then natively |
| S3 | **Step kinds made explicit**: `test` (reveals), `decision`, `admin` (takes time, reveals nothing medical), `milestone`, `exit` | Today visits and paperwork are "tests" | A document-format change (`flowchart/2`) with an automatic upgrade from `flowchart/1`. Validation codes for "admin step claims outputs" |
| S4 | **Clinician judgements become decision nodes** (assumption V4): nurse assessment, GP "image or wait", specialist "work up or discharge", GP second look | The decision layer is supposed to power these; today they are noisy tests driven by hidden truth, which hides them from the decision layer | Recalibrate the Finnish scenario so its published waits and shares still hold (was ticket M1-9). Review required: headline numbers move |
| S5 | **Patient behaviour as its own step kind**: comes back or not, attends or not | Today `symptoms_persist` is a test | From the catalogue's behaviour file (C2 K6) |
| S6 | **Requirements between tests** from the catalogue (`requires:`) checked at validation | A biopsy needs an imaging target | New problem code |
| S7 | **Cost and harm accounting** in metrics: tests done per patient, cost, invasive procedures, complications drawn from catalogue rates | The optimiser must not "win" by testing everyone invasively; reported next to time | Additive metrics |
| S8 | **Hook for state at time of test** | Lets C1 add progression later without an engine change | Pass the simulation day to the reveal call; version 1 ignores it |
| S9 | **Speed at scale** | Criteria optimisation reruns cohorts many times | Profile first. Aim: a 20 000-patient Finnish run in under 2 seconds on one core, or parallel runs across seeds |

S1, S2 and S3 are one coherent package group and should be specced together with C1's P1 and P5.
S4 depends on C4's decision matrix. S7 can run any time.

## Invariants that matter most here

I1 (information boundary), I2 (determinism), I3 (same patient, same result across flowcharts),
I5 (the Norwegian check still holds after every change). Any package touching the engine carries
the existing digest test (`tests/test_expr.py::test_shipped_scenarios_give_identical_results`)
or, when it changes behaviour on purpose, replaces the digests in the same commit with a
statement of what moved and why.

## Sub-wholes (for the spec agent)

| # | Sub-whole | Contains |
|---|---|---|
| E1 | Typed reveals and names in conditions | S1 |
| E2 | Cohorts through the reveal handle | S2, S8 |
| E3 | Document format `flowchart/2` and upgrade | S3, S5, S6 |
| E4 | Judgement steps as decisions; Finnish recalibration | S4 |
| E5 | Cost and harm metrics | S7 |
| E6 | Performance | S9 |

## Known issues to carry into speccing

- The service's Norway template uses the uncalibrated scenario file and shows about 11% where the
  published and calibrated figure is 40% (channel entry 1114-133852). Fix on the submission track:
  the template must load the calibrated world.
- If a "standardised" option is not on offer for a patient, the rule policy takes the first
  option and the stub falls back to uniform. The two should agree.

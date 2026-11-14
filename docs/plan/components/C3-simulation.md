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
| S4 | **Every point where something is decided becomes a decision node** (decision D41): nurse assessment, GP "image or wait", specialist "work up or discharge", GP second look | The decision layer is supposed to power these; today they are noisy tests driven by hidden truth, which hides them from the decision layer | Recalibrate the Finnish scenario so its published waits and shares still hold (was ticket M1-9). Review required: headline numbers move |
| S5 | **Patient behaviour as its own step kind**: comes back or not, attends or not | Today `symptoms_persist` is a test | From the catalogue's behaviour file (C2 K6) |
| S6 | **Requirements between tests** from the catalogue (`requires:`) checked at validation | A biopsy needs an imaging target | New problem code |
| S7 | **Cost and harm accounting** in metrics: tests done per patient, cost, invasive procedures, complications drawn from catalogue rates | The optimiser must not "win" by testing everyone invasively; reported next to time | Additive metrics |
| S8 | **Patient state at the time of a test** | A result depends on which of the patient's conditions are still active (decision D40) | The reveal call takes the patient's current state |
| S10 | **Treatment steps** | A step that treats a working diagnosis: takes time and a resource; if the patient truly has that condition it resolves with the catalogue's response rate and time course, and the patient's state changes | New step kind `treat`. The engine applies the state change; no decision sees whether it "worked" except through later revealed findings |
| S11 | **Episodes: patients who come back** | After an episode ends without a cancer diagnosis, the catalogue's behaviour model decides from the remaining findings whether and when the patient contacts care again; they re-enter at the entry node as a new episode with their whole revealed record | The flowchart stays a graph without cycles: a loop is a new pass, not an edge back. Cap on episodes. The clock for a cancer patient runs from the first contact of the first episode. The run log, metrics and flow view gain an episode number. Today's `symptoms_persist` and `gp_represent` steps are replaced by this |
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
| E8 | Emergent booking leads | S12 (spike, then build; review required: headline numbers) |
| E7 | States, treatment and episodes | S8, S10, S11 (with C1 P11; review required: changes what "time to treatment" and "missed" mean) |

## Booking leads: fixed floors against emergent queues (review feedback, 14 Nov)

Finding, confirmed by `docs/booking_vs_queue.md`: in the Finnish scenario about 57 of 93 waiting
days on a treated cancer patient's critical path are the fixed booking lead (`min_lead_days`,
set so waits match published ones) and about 12 are queueing that the simulation produces. The
floors stand in for a standing backlog the simulation does not build. The accepted reorders gain
their days from paperwork and board waits, not from booking leads, so the reorder claim does not
depend on the floors; the capacity probe does, and is weak for that reason.

Plan: **not before the submission** (a recalibration near full utilisation is sensitive and would
move every Finnish number hours before the freeze); say plainly in the pitch and dashboard that
booking leads are inputs standing in for a backlog. On the platform track it is sub-whole E8:

| # | Change | Notes |
|---|---|---|
| S12 | **Emergent booking leads**: a pre-filled booking book or long warm-up, capacities near demand, floors reduced to what is truly administrative, recalibration to published waits with a stated tolerance, and a stability check (how much the lead moves per slot of capacity) | A design spike first: near 95% utilisation small capacity errors swing the wait, so the calibration target should be a range, and both variants should be kept runnable for comparison |

## Known issues to carry into speccing

- The service's Norway template uses the uncalibrated scenario file and shows about 11% where the
  published and calibrated figure is 40% (channel entry 1114-133852). Fix on the submission track:
  the template must load the calibrated world.
- If a "standardised" option is not on offer for a patient, the rule policy takes the first
  option and the stub falls back to uniform. The two should agree.

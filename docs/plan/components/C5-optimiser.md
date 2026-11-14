# C5 Optimiser

| | |
|---|---|
| Package | `optimiser/` |
| State | Built for the **order of steps**: proposals from revealed records, rerun on the same patients, guardrails, held-out report, applying a subset of changes. To design and build: optimising the **decision criteria**. Detailed spec of what is built: `docs/platform/specs/05-optimise-rerun.md` |
| Depends on | C3 (reruns), C4 (the tables it edits), C1 (cohorts) |
| Used by | C6 |
| Track | Platform. This file is a design to be challenged: the first work package is a design spike, not code |

## The problem, stated exactly

Given a world (catalogue, resources), a starting flowchart and decision policies, find changes
that make patients with cancer start treatment sooner, such that:

- every decision uses only facts revealed before it (invariant I1), and the optimiser's proposal
  step also sees only revealed records, never hidden truth;
- safety guardrails hold: no more missed cancers than the baseline on the same patients, and no
  presentation group worse off;
- capacity is respected (it is enforced by the queues, not by a penalty);
- the result is a pathway people can read: a flowchart and decision tables, not a black box;
- the claimed gain is measured on patients the search never saw.

Decision variables, two families:

| Family | Examples | State |
|---|---|---|
| **Structure** | do a test earlier, run two steps in parallel, remove an unnecessary wait-for, fast-track a group | Built (`edits.py`: detach, relax, standardise, fast_track) |
| **Criteria** | at a decision node, change who gets which option: add a matrix row ("if haemoptysis and age over 40, go straight to CT"), move a threshold, change a probability | To build |

Objective: by default the share of cancer patients treated within the target and the median days
to treatment (assumption V5). Reported next to it, and available as constraints: tests per
patient, cost, invasive procedures, complications, load on each resource.

## What makes this tractable: the simulator is the experiment

In real data you only see the outcome of the option that was chosen. In the simulator every
patient has a pre-drawn result for every test, and any policy can be rerun on the same patients
with the same random numbers. So the optimiser never has to guess a counterfactual from logs: it
proposes from what was revealed, then **measures** by rerunning. Keep this split:

1. **Propose** using revealed records only (what a real health system could know from its own
   logs).
2. **Evaluate** by rerun on the training cohorts with common random numbers. The evaluation may
   use hidden truth to count missed cancers; in real life that step is a pilot. The interface
   says so.
3. **Accept** only if the gain is larger than run-to-run noise on two training cohorts and all
   guardrails hold.
4. **Report** on held-out cohorts, with the optimism (training gain minus held-out gain) shown.

One caveat to respect everywhere: patients share queues, so changing one patient's path changes
others' waits. Per-patient reasoning is only a way to find candidates; acceptance is always a
full rerun.

## Proposed design for criteria optimisation (three stages; challenge it in the spike)

### Stage A. Rule edits by guided search (extends what exists)

Treat a decision matrix edit like a structural edit: a small, named, readable change.

- **Edit operators.** Add a row for a subgroup defined by one or two revealed facts; delete a
  row; change a row's probabilities to favour one option; move a numeric threshold by a step;
  for score policies, change one weight or cut-off.
- **Candidate generation from revealed records.** For each decision and each option, the run log
  gives, per context cell (combinations of revealed facts with enough patients), what followed:
  time to the next milestone, whether the test was decisive (changed what was done next), how
  often it had to be repeated. Rank cells by expected time saved if their patients took a
  different option. To get outcomes for options that current practice rarely chooses, add
  **exploration runs**: a share of patients at the chosen decision get a random option (built on
  `plat/ds` as exploration mode). Exploration data is revealed-side data like any other.
- **Search.** The existing greedy loop with noise-aware acceptance and two-step lookahead, over
  the union of structural and criteria edits. Minimum subgroup size so a rule is not fitted to a
  handful of patients.
- **Why first:** smallest step from the code that exists, every accepted change is one readable
  sentence with its evidence, and it already answers "what should this node do differently".

### Stage B. Fit a small policy per decision, then verify

For each decision node, learn from exploration data which option is best for which revealed
context, in an interpretable form:

- Outcome label per explored decision: downstream time to treatment or to a safe discharge, with
  penalties for a missed cancer, a repeated test and harm (weights are settings, shown).
- Fit a shallow decision tree or a points score (C4 level 2) predicting the best option from
  revealed facts; limit depth and leaves so the result is a table of at most about eight rows.
- Convert the fit to a decision matrix; accept it only through the Stage A acceptance step
  (rerun, guardrails, held-out).
- Iterate over decisions from the first in the pathway to the last, because changing an early
  decision changes who reaches later ones; repeat until no change is accepted.
- **Why:** finds multi-fact rules that single-step edits miss, and gives an ordering of which
  facts matter at each node (a value-of-information readout: "at the GP visit, haemoptysis and
  smoking history decide; CRP does not").

### Stage C. Joint tuning of the numbers

Once the shape of the rules is fixed, tune all numeric parameters together (thresholds,
probabilities, score weights; perhaps 10 to 40 numbers) with a noise-tolerant derivative-free
method: cross-entropy method or Bayesian optimisation, each evaluation a rerun on training
cohorts with common random numbers, constraints handled by rejection. Report the Pareto front
between time and the secondary measures instead of one point, so a person chooses.

- **Why last:** it is the most compute-hungry and the least explainable; it polishes rules that
  A and B found, it does not invent them.

### What the optimiser hands back (contract, extends spec 05)

For each accepted change: a plain sentence, the kind (structure or criteria), the decision or
steps touched, the before and after table rows, the evidence (cells, counts, measured gain on
each training cohort), guardrail values, and the held-out result. Plus the list of rejected
candidates with the guardrail that stopped each. Linked changes are marked so they are accepted
together.

## Guardrails and honesty

- Missed cancers: not more than the baseline on the same patients (exists). Extend to "cancers
  found at a later stage" only if C1 adds progression.
- Equity: no presentation group, and no background group the catalogue marks as equity-relevant
  (region, access), may get worse. The gain per group is reported.
- Over-testing: a change may not raise invasive procedures in people without cancer beyond a
  stated margin; cost and tests per patient are shown for every change.
- Multiple comparisons: the search tries many candidates; acceptance thresholds and the held-out
  report are what keep the claim honest. The number of candidates tried is reported.
- Robustness: an accepted change is rerun under the catalogue's low and high values for the
  parameters it depends on; "holds in X of Y draws" is shown (uses `sensitivity.py`).
- Under JEV: the optimiser does not edit a model's decisions unless switched on (fork F7).

## Other approaches considered

| Approach | Why not first |
|---|---|
| Reinforcement learning over the whole pathway | Produces a policy people cannot read; needs far more runs; hard to constrain. Useful later as a bound on what is achievable |
| Exact stochastic optimisation of the queueing network | Our flowcharts have guards, retries and batches; no closed form. Could inform capacity questions |
| Learning from logs only, without reruns (off-policy evaluation) | Needed for real data one day; in simulation the rerun is exact, so use it |
| Sequential testing theory (value of information per test) | Good lens for Stage B's readout; as the main method it ignores queues |

## Sub-wholes (for the spec agent)

| # | Sub-whole | Outcome | Notes |
|---|---|---|---|
| O1 | **Design spike** | A short design note that tests this file's plan on the Finnish scenario with the current engine: which decisions exist, how many context cells have enough patients, how noisy a rerun is, how long 100 evaluations take; and a recommendation to keep, change or reorder stages A to C | A thinking lane with code experiments, no product code. Do this before ticketing O2 to O5 |
| O2 | Criteria edit operators and the candidate generator | Stage A | Needs C4 J2 (matrix shape). Extends `edits.py`, `analysis.py` |
| O3 | Unified search over structure and criteria; result contract | Stage A | Extends `search.py`, `report.py`, the service result |
| O4 | Fitted policy per decision | Stage B | Needs exploration data (exists on `plat/ds`) |
| O5 | Joint tuning and the Pareto report | Stage C | Needs C3 E6 (speed) |
| O6 | Guardrail extensions: equity by background, over-testing, robustness | | Needs C3 E5 (cost and harm metrics) |

## Open questions

| # | Question | Lean | Who |
|---|---|---|---|
| Q1 | What is the price of a missed cancer against a week of delay, when both move | Never traded: missed cancers are a hard constraint, time is the objective | Tuomas |
| Q2 | May the optimiser propose removing a test | Yes if guardrails hold; report it prominently | Tuomas |
| Q3 | One objective or a front | A front for people to choose from; the demo shows one recommended point | Tuomas |
| Q4 | How much exploration is realistic to claim | Simulation only; say that in real life it is a pilot or a stepped roll-out | C7 |

# Simulator design and open questions (13 Nov 2026)

## What we are building
A Jev-type decision model with our custom architecture, applied to cancer diagnostics, plus a configurable flowchart of the diagnostic pathway. Demo: synthetic patients run through the flowchart; an optimiser proposes a better flowchart using revealed information only; the same patients are rerun and the metrics compared.

## Roles
- Flowchart: the steps that exist, allowed orders, time limits. Human-configurable.
- Decision model: input is the context (history plus the newest result: test, sample, doctor's note, nurse's symptom description). Output is the most likely next decision.
- Optimiser: compares flowchart variants using revealed information only (e.g. A, B, C negative, D diagnostic: should D have come first?).

## Decided
- One flowchart, one region. No regional dimension in the simulator.
- No simulated doctors. The simulation contains only the decision model. In the real world a doctor makes the final call and can override the model; this is a doctor's tool, so the doctor is not simulated.
- No real decision data. Synthetic data only; all code written at the event.
- Goal: shorten time from first contact to diagnosis and treatment start.
- Capacity: about 10 scarce final diagnostic tests and 2 treatment lanes, all low capacity. Intermediate steps filter out healthy patients and sort the rest to the right test.
- Queues: fixed capacity per test, dynamic queue length that emerges from the simulation. Capacities to be calibrated later to reflect the real world more accurately.
- Tests differ in accuracy.
- Synthetic data is generated from causes: each patient first gets a true underlying condition (cancer or a non-cancer condition commonly confused with it, or nothing serious); symptoms and all test results are then drawn from that condition using each test's sensitivity and specificity. Cancer prevalence is kept realistically low.
- Every synthetic patient has all possible test results pre-generated as hidden variables. A rerun may reveal different variables in a different order.
- Optimise by patient group, not by individual patient: estimate each test's yield per context type, order by expected information per unit of time and capacity.
- A proposed reordering counts only if the full rerun improves time without breaching the guardrails.
- Output per variant: time to treatment, share within target time, cancers missed, tests per patient.

## Patient cards
1. Basic starting information (symptoms, background).
2. Cancer or not.
3. Hidden variables: mostly negative and unrelated to cancer, some positive, a few related to a possible cancer diagnosis if the patient has cancer. Includes results of intermediate tests for more likely causes of the symptoms.
- Some cancers are quick to diagnose, others need many alternatives ruled out.
- Non-cancer symptom profiles that are commonly confused with cancer are included.

## Each step
Reveals some hidden variables with an error rate, takes time, uses a resource with fixed capacity.

## OPEN: capacity in the long run
In the long run a queue can sometimes be solved by adding capacity to a test. Whether and how to allow capacity changes is not decided. Idea on the table: a later second mode that asks which test gains most from one more slot.

## OPEN: problems the optimisation algorithm must handle (noted, not solved)
- Bayesian expectation of each test: given context X, which test is most likely to yield the best result.
- Invasive or costly tests: how to simulate their cost so they are not chosen on accuracy alone.
- Non-cancer patients must be documented and counted. Example: 10 patients go to non-cancer test A, 9 resolve, 1 continues to non-cancer B, cancer C, cancer D. A was clearly a good call. Were B or C in the wrong priority, and should D have come sooner, or not? The algorithm must account for the value of steps that resolve non-cancer patients.
- Hindsight bias: a late test's hit rate is observed only on patients who failed earlier tests; earlier negatives may be what keeps its queue short.

## OPEN: consequences of no simulated doctors
- What produces the first run and the first logs (a hand-written starting flowchart, random exploration, or both)? This is also the "before" in the before-and-after comparison.
- With one region and no doctor variation, the simulator itself shows no equity gap. The brief's "identify the gap" step would rest on cited external evidence in the pitch.

## Other points raised, not yet decided
- Guardrails so that "faster" cannot be reached by skipping tests: missed cancers not above baseline, tests within capacity.
- Treatment normally does not start before tissue diagnosis; model a parallel referral or slot reservation instead.
- Circularity: calibrate one scenario to a published pathway (Stokstad et al. 2019, Norway: 40% within 42 days observed, 80% with re-sequencing).

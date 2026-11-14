# Junction submission text

## Project name (pick one)

1. **PathwayLab: Equal Care Across Finland**
2. **Faster Together**
3. **Queue Compass**

## Summary

We built a simulator and optimiser for the lung cancer diagnostic pathway. Synthetic patients run through an editable flowchart of steps; the optimiser proposes a different order of steps using only what steps revealed; the same patients are rerun to accept a change and held-out patients are used to report it. In our synthetic Finnish county the suggested change raises the share treated within 90 days of first contact from 18% to 61%. All data is synthetic.

## Problem

Finland has the weakest lung cancer outcomes in the Nordics, and diagnosis takes longer at the first steps (first appointment about 14 days against 2-7; 40-60% of patients first see a nurse; few primary-care units can perform CT; sources in `docs/pitch/evidence_brief.md`). Goal 3 of the National Cancer Strategy asks for equal care and treatment within target times.

## What we built

- A pathway simulator: an event engine with capacity queues, a weekly tumour board, and published waiting-time distributions.
- A synthetic Finnish county scenario with about 16 177 chest-symptom presenters per cohort and 1.6% lung cancer, in two presentation groups (alarm and vague symptoms).
- An optimiser that proposes and accepts changes under guardrails (no more missed cancers, no extra tests beyond a small tolerance, no longer exits for patients without cancer).
- An offline dashboard: what to change, what it gains, where time is lost, who waits longest.

## How it works

Each flowchart step reveals results, takes time and uses a resource. Proposals are scored from revealed timestamps (which prerequisite held a step back, by how many days). A change is kept only if a rerun of the same patients, with common random numbers, is faster and passes the guardrails. Numbers are reported on held-out patients. In real life the acceptance rerun would be a pilot, because it uses the simulated truth.

## Results (held-out, with sources)

- **Norwegian check** (Stokstad et al. 2019, 100 early-stage patients). Fitted only to the observed pathway: 40% within 42 days (published 40%). Predicted, not fitted: the authors' reordered pathway 80% (published 80%). Faster PET-CT alone: we predict 60%, the paper reports 48%; we over-predict. A blind search finds the authors' three changes plus a fourth (tissue sampling booked at the first visit, needs a clinical check) and reaches 88% with the faster scanner, 67% without new equipment.
- **Finnish synthetic county.** Within 90 days (provisional target; no Finnish first-contact target found): 18% to 61%, median 102 to 80 days. Missed cancers 27.5 to 27.5 per cohort, tests per patient 0.41 to 0.41. The same extra CT and PET capacity without reordering reaches 31%; with reordering 54%.
- **Equity** (assumption-built groups). Vague symptoms 13% to 54%, alarm symptoms 27% to 79%. The gap in points widens; the gap in median days narrows.
- **Decision model.** On a task where the right answer depends on the set of options, a correction model beats a parameter-matched dot-product model: 84.5% against 79.0%. The claim that a second question costs half the compute was not reproduced at our sizes (76-91% of the first). It is not yet in the demo loop.

## What is new, and what is not

Discrete-event simulation of cancer pathways exists, including for lung cancer in the UK and Norway. What we add: (1) a decision-model layer that proposes the next step at each choice point, benchmarked against a baseline; (2) an optimiser that works only from revealed information and treats hindsight bias explicitly, accepting on an exact same-patient rerun and reporting held-out; (3) a published pathway used as a blind test rather than only as calibration.

## Limitations

Synthetic data and one region. Finnish capacities are assumptions calibrated to published waits (18 of 131 parameters). The Finnish target is provisional. The equity gap is built from an assumption. The Norwegian check has one study, 100 patients, a model-based 80%, and only specialist care; the faster-PET prediction misses. No sensitivity analysis yet. A clinician must approve every change.

## Next steps and asks

Real county data; clinical review of the fourth Norwegian change and the GP-first change; a one-county pilot; sensitivity runs; connect the decision model.

## Run the demo

`pip install -r requirements.txt`, `python -m pytest -q`, `python -m pathway_sim demo` (about a minute), then open `demo/index.html` (offline; keys 1-4).

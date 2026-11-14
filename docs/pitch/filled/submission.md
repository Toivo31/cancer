# Junction submission text

## Project name (pick one)

1. **PathwayLab: Equal Care Across Finland**
2. **Faster Together**
3. **Queue Compass**

## Summary

We built a simulator and optimiser for the lung cancer diagnostic pathway. Synthetic patients run through an editable flowchart of steps; the optimiser proposes changes using only what steps revealed; the same patients are rerun to accept a change and held-out patients are used to report it. In our synthetic Finnish county the optimiser's two accepted changes are both reorders (no new equipment, no priority lane) and raise the share treated within 90 days of first contact from 18% to 33%. A larger effect, 61%, appears only if every referred patient could be booked on an urgent track with the shorter booking times we assume; we report that as a conditional finding, not as the result. All data is synthetic.

## Problem

Finland has the weakest lung cancer outcomes in the Nordics, and diagnosis takes longer at the first steps (first appointment about 14 days against 2-7; 40-60% of patients first see a nurse; few primary-care units can perform CT; sources in `docs/pitch/evidence_brief.md`). Goal 3 of the National Cancer Strategy asks for equal care and treatment within target times.

## What we built

- A pathway simulator: an event engine with capacity queues, a weekly tumour board, and published waiting-time distributions.
- A synthetic Finnish county scenario with about 16 177 chest-symptom presenters per cohort and 1.6% lung cancer, in two presentation groups (alarm and vague symptoms).
- An optimiser that proposes and accepts changes under guardrails (no more missed cancers, no fewer tissue-confirmed diagnoses, no extra tests beyond a small tolerance, no longer exits for patients without cancer, no group left slower).
- An offline dashboard: what to change, what it gains, where time is lost, who waits longest.

## How it works

Each flowchart step reveals results, takes time and uses a resource. Proposals are scored from revealed timestamps (which prerequisite held a step back, by how many days). A change is kept only if a rerun of the same patients, with common random numbers, is faster and passes the guardrails. Numbers are reported on held-out patients. In real life the acceptance rerun would be a pilot, because it uses the simulated truth.

## Results (held-out, with sources)

- **Norwegian check** (Stokstad et al. 2019, 100 early-stage patients). Fitted only to the observed pathway: 40% within 42 days (published 40%). Predicted, not fitted: the authors' reordered pathway 80% (published 80%). Caveat: the calibrated observed practice of ordering PET-CT when the referral is triaged is carried into the authors' pathway; if PET-CT were ordered only at the first visit, as the paper describes, the simulated authors' pathway gives 66%. Faster PET-CT alone: we predict 60%, the paper reports 48%; we over-predict. The blind search chose from a menu of about 69 single changes that included each of the authors' changes as one edit; it was not told which ones the authors made. It finds the authors' three changes plus a fourth (plan tissue sampling when the referral is triaged, before the first hospital visit, i.e. before a specialist has seen the patient; needs a clinical check) and reaches 88% with the faster scanner, 67% without new equipment.
- **Finnish synthetic county.** Within 90 days (provisional target; no Finnish first-contact target found): 18% to 33%, median 102 to 94 days. The two accepted changes: (1) Reserve the treatment slot when the case is sent to the tumour board, not after the board has met; (2) Book the specialist visit as soon as the referral arrives, not after it has been handled. No new equipment; missed cancers 27.5 to 27.5 per cohort (unchanged), tests per patient 0.41 to 0.41. Capacity-controlled comparison: the same extra CT and PET capacity with today's order reaches 31%; with the hand-written order-together pathway 54% (it needs 3 PET-CT slots).
- **Conditional finding, not the headline.** Urgent booking for every referred patient gives 18%, 44% or 61% if 0%, 50% or 100% of the assumed booking-lead reduction can be held. It rests entirely on assumed urgent booking leads (everyone urgent means nobody is crowded out, so the gain is exactly the assumed lead reduction), so we do not recommend it until real booking data exist.
- **Equity** (groups built from our assumptions). Under those assumptions the simulation shows both groups gain: vague symptoms 13% to 26%, alarm symptoms 27% to 50%. The gap in percentage points widens (13.6 to 24.6 points); the gap in median days narrows (11.2 to 9.9 days). We do not claim the change closes the gap.
- **Decision model.** On a task where the right answer depends on the set of options, a correction model beats a parameter-matched dot-product model: 84.5% against 79.0%. The claim that a second question costs half the compute was not reproduced at our sizes (76-91% of the first). Inside the simulator loop it matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads a shared queue unless it can see queue state.

## What is new, and what is not

Discrete-event simulation of cancer pathways exists, including for lung cancer in the UK and Norway. What we add: (1) a decision-model layer that proposes the next step at each choice point, benchmarked against a baseline and tried inside the loop; (2) an optimiser that works only from revealed information and treats hindsight bias explicitly, accepting on an exact same-patient rerun and reporting held-out; (3) a published pathway used as a blind test rather than only as calibration.

## Limitations

Synthetic data and one region. The Finnish scenario file has 65 tagged inputs: 21 cite a source and 44 are assumptions, including every capacity, every booking lead and every urgent booking lead; they are calibrated to published waits. (`docs/parameters.md` lists more rows as evidence and calibration targets; most are not simulator inputs.) The Finnish target is provisional, and the equity gap is built from an assumption. The Norwegian check has one study, 100 patients, a model-based 80% that carries the calibrated PET-at-triage practice, and only specialist care; the faster-PET prediction misses; its search menu contained the authors' changes. Sensitivity runs (`docs/sensitivity.md`) cover the hand-written order-together pathway, not the two accepted Finnish reorders, and the Finnish held-out result rests on two cohorts of about 261 cancers each. A clinician must approve every change.

## Next steps and asks

Real county data, especially booking leads; clinical review of the fourth Norwegian change (sampling planned before a specialist has seen the patient) and of the GP-first idea (which failed our safety check on training patients by half a missed cancer per cohort and looked neutral on unseen ones, so it needs a proper paired test); a one-county pilot; sensitivity runs on the accepted Finnish reorders; connect the decision model.

## Run the demo

`pip install -r requirements.txt`, `python -m pytest -q`, `python -m pathway_sim demo` (about 9 minutes; `--quick` about 2.5), then open `demo/index.html` (offline; keys 1-6). The tests take about 35 seconds.

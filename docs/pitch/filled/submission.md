# Junction submission text

> **Safe to claim / do not claim** (numbers from `numbers_sheet.md`; update there first)
>
> **Safe to claim**
> - All patients are synthetic. The Finnish county is a scenario, not calibrated to Finnish capacity data.
> - Norway, fitted: only the observed pathway (40% within 42 days, published 40%).
> - Norway, predicted and not fitted: the authors' pathway, 80% at our best fit against the published 80%; across all 184 settings that fit the observed data, 62 to 86%, typically about 75%; 64% of settings inside the published interval.
> - The ranking (reordering beats a faster scanner beats today) holds in all 184 settings.
> - We over-predict a faster scanner alone: 60% against the published 48%.
> - The search found the authors' three changes plus a fourth that needs a clinical check; it chose from a menu of about 69 changes that contained the authors' changes. 88% with the faster scanner, 67% with no new equipment (best-fit setting).
> - Finland, synthetic: 18% to 33% within 90 days (provisional target), two reorders, no new equipment.
> - The primary-care loop is a demonstrated mechanism with placeholder decision tables, not a result.
>
> **Do not claim**
> - "We predicted 80% exactly", "matches the paper", "78 to 86%".
> - "The optimiser found the authors' answer blind" without the menu caveat; that the fourth change is safe.
> - 61% as a result (conditional on assumed urgent booking times).
> - Any Finnish number as an estimate for real patients; lives saved; that the equity gap closes (in points it widens).
> - That the model-written cards are "leak-free": the independent review found report wording that gives away false alarms; fix and regeneration in progress.
> - Any primary-care loop number as a finding (it fails 7 of 8 consistency checks against the calibrated chain).
> - That a model trained on synthetic cards works on real patients; that the team's decision model (JEV) produced the headline numbers.
> - How the optimiser's Norwegian changes hold on all 184 settings or without the fourth change (check pending).

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
- A synthetic patient engine: a catalogue of 11 chest-symptom conditions, 42 hidden variables and 26 tests (a draft no clinician has read), and patient cards that hold a hidden truth plus the pre-written result of every test. Today: 500 template-written cards and 35 model-written cards, all synthetic (counts change when libraries are regenerated after a review finding on report wording). Decisions see only the revealed record, never the hidden truth.
- A primary-care encounter loop built on those cards. It is a mechanism with placeholder decision tables; it does not yet reproduce the calibrated Finnish chain (it fails 7 of 8 consistency checks), so we show it as a mechanism, not a result.
- The team's fine-tuned decision model (JEV), connected through an adapter and a step-through tool. The simulator runs shown here use placeholder decision tables and rules.

## How it works

Each flowchart step reveals results, takes time and uses a resource. Proposals are scored from revealed timestamps (which prerequisite held a step back, by how many days). A change is kept only if a rerun of the same patients, with common random numbers, is faster and passes the guardrails. Numbers are reported on held-out patients. In real life the acceptance rerun would be a pilot, because it uses the simulated truth.

## Results (held-out, with sources)

- **Norwegian check** (Stokstad et al. 2019, 100 early-stage patients, one hospital). Fitted only to the observed pathway: 40% within 42 days (published 40%). Predicted, not fitted: the authors' reordered pathway. At our best fit it gives 80% (published 80%, itself a model estimate). That best fit is one point in a band: the two fitted numbers act as one constraint, so five inputs the paper does not report are not pinned down. Across all 184 settings that fit the observed pathway the prediction is 62 to 86%, typically about 75%, and 64% of settings fall inside the published interval (72-87%). What holds in every one of the 184 settings is the ranking: reordering beats a faster scanner beats today. A second caveat: the calibrated practice of ordering PET-CT when the referral is triaged is carried into the authors' pathway; if PET-CT were ordered only at the first visit, as the paper describes, the best-fit authors' pathway gives 66%. Faster PET-CT alone: we predict 60% at the best fit (band 50 to 74%), the paper reports 48%; we over-predict. The search chose from a menu of about 69 single changes that included each of the authors' changes as one edit; it was not told which ones the authors made. It finds the authors' three changes plus a fourth (plan tissue sampling when the referral is triaged, before a specialist has seen the patient; needs a clinical check) and reaches 88% with the faster scanner (the authors' 80% also assumes that scanner) and 67% with no new equipment. These two numbers are from the best-fit setting; how they hold on the other settings, and without the fourth change, is being checked and is not yet claimed. The lead over the authors comes from the fourth change.
- **Finnish synthetic county.** Within 90 days (provisional target; no Finnish first-contact target found): 18% to 33%, median 102 to 94 days. The two accepted changes: (1) Reserve the treatment slot when the case is sent to the tumour board, not after the board has met; (2) Book the specialist visit as soon as the referral arrives, not after it has been handled. No new equipment; missed cancers 27.5 to 27.5 per cohort (unchanged), tests per patient 0.41 to 0.41. Capacity-controlled comparison: the same extra CT and PET capacity with today's order reaches 31%; with the hand-written order-together pathway 54% (it needs 3 PET-CT slots).
- **Conditional finding, not the headline.** Urgent booking for every referred patient gives 18%, 44% or 61% if 0%, 50% or 100% of the assumed booking-lead reduction can be held. It rests entirely on assumed urgent booking leads (everyone urgent means nobody is crowded out, so the gain is exactly the assumed lead reduction), so we do not recommend it until real booking data exist.
- **Equity** (groups built from our assumptions). Under those assumptions the simulation shows both groups gain: vague symptoms 13% to 26%, alarm symptoms 27% to 50%. The gap in percentage points widens (13.6 to 24.6 points); the gap in median days narrows (11.2 to 9.9 days). We do not claim the change closes the gap.
- **Our decision-model benchmark** (a small numpy model of ours, separate from the team's JEV). On a task where the right answer depends on the set of options, a correction model beats a parameter-matched dot-product model: 84.5% against 79.0%. The claim that a second question costs half the compute was not reproduced at our sizes (76-91% of the first). Inside the simulator loop it matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads a shared queue unless it can see queue state.

## What is new, and what is not

Discrete-event simulation of cancer pathways exists, including for lung cancer in the UK and Norway. What we add: (1) a decision-model layer that proposes the next step at each choice point, benchmarked against a baseline and tried inside the loop; (2) an optimiser that works only from revealed information and treats hindsight bias explicitly, accepting on an exact same-patient rerun and reporting held-out; (3) a published pathway used as a held-back test rather than only as calibration (with the caveat that the calibration cannot pin its inputs down, so the test gives a band).

## Limitations

Synthetic data and one region. The Finnish scenario file has 49 input blocks (`docs/ledger.md`): 9 cite a source (5 without assumption wording in their own note) and 40 are assumptions, including every capacity, every booking lead and every urgent booking lead; they are calibrated to published waits. (`docs/parameters.md` lists more rows as evidence and calibration targets; most are not simulator inputs.) The Finnish target is provisional, and the equity gap is built from an assumption. The Norwegian check has one study, one hospital, 100 patients, a model-based 80% that carries the calibrated PET-at-triage practice, and only specialist care; its prediction is a band (62 to 86% for the authors' pathway), not a point; the faster-PET prediction misses; its search menu contained the authors' changes. Synthetic patient cards are not validated against real patients, their backgrounds have no population model yet, an independent review found that the wording of test reports in model-written cards gives away false alarms (fix in progress), and no model trained on them has been tested on real patients. The Finnish headline is the mean of two held-out cohorts of about 261 cancers each; across 12 cohorts today's share is 14 to 25% and the suggested change's 24 to 42%, with a gain of 9 to 19 points that is positive in every cohort and in 100% of 16 joint assumption draws (`docs/ranges.md`). Norwegian numbers on 100-patient cohorts (the size of the real study): observed 30 to 51%, the authors' pathway 72 to 87%, optimiser 81 to 94% (without new equipment 56 to 75%). Those cohort ranges are at the best-fit setting; the spread over calibration settings is in `docs/validation.md` (Robustness). The older sensitivity runs (`docs/sensitivity.md`) cover the hand-written order-together pathway. A clinician must approve every change.

## Next steps and asks

Real county data, especially booking leads; clinical review of the fourth Norwegian change (sampling planned before a specialist has seen the patient) and of the GP-first idea (which failed our safety check on training patients by half a missed cancer per cohort and looked neutral on unseen ones, so it needs a proper paired test); a one-county pilot; a sensitivity run with several seeds per variant on the accepted Finnish reorders (one seed per variant so far); a clinician to read and correct the patient catalogue; real decision data to train and test the team's decision model (JEV), which today has only synthetic cards; a primary-care loop whose decision tables are replaced by the JEV and then checked against the calibrated chain.

## Run the demo

`pip install -r requirements.txt`, `python -m pytest -q`, `python -m pathway_sim demo` (about 9 minutes; `--quick` about 2.5), then open `demo/index.html` (offline; keys 1-6). The tests take about 2 minutes.

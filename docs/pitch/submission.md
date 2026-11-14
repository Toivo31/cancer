# Junction submission text

## Project name (pick one)

1. **PathwayLab: Equal Care Across Finland**
2. **Faster Together**
3. **Queue Compass**

## Summary

We built a simulator and optimiser for the lung cancer diagnostic pathway. Synthetic patients run through an editable flowchart of steps; the optimiser proposes changes using only what steps revealed; the same patients are rerun to accept a change and held-out patients are used to report it. In our synthetic Finnish county the optimiser's two accepted changes are both reorders (no new equipment, no priority lane) and raise the share treated within [[f_target]] days of first contact from [[f_share_base]]% to [[f_share_opt]]%. A larger effect, [[f_cond_share_100]]%, appears only if every referred patient could be booked on an urgent track with the shorter booking times we assume; we report that as a conditional finding, not as the result. All data is synthetic.

## Problem

Finland has the weakest lung cancer outcomes in the Nordics, and diagnosis takes longer at the first steps (first appointment about 14 days against 2-7; 40-60% of patients first see a nurse; few primary-care units can perform CT; sources in `docs/pitch/evidence_brief.md`). Goal 3 of the National Cancer Strategy asks for equal care and treatment within target times.

## What we built

- A pathway simulator: an event engine with capacity queues, a weekly tumour board, and published waiting-time distributions.
- A synthetic Finnish county scenario with about [[f_n]] chest-symptom presenters per cohort and [[f_prevalence]]% lung cancer, in two presentation groups (alarm and vague symptoms).
- An optimiser that proposes and accepts changes under guardrails (no more missed cancers, no fewer tissue-confirmed diagnoses, no extra tests beyond a small tolerance, no longer exits for patients without cancer, no group left slower).
- An offline dashboard: what to change, what it gains, where time is lost, who waits longest.

## How it works

Each flowchart step reveals results, takes time and uses a resource. Proposals are scored from revealed timestamps (which prerequisite held a step back, by how many days). A change is kept only if a rerun of the same patients, with common random numbers, is faster and passes the guardrails. Numbers are reported on held-out patients. In real life the acceptance rerun would be a pilot, because it uses the simulated truth.

## Results (held-out, with sources)

- **Norwegian check** (Stokstad et al. 2019, 100 early-stage patients). Fitted only to the observed pathway: [[s_obs_share]]% within 42 days (published [[s_pub_base]]%). Predicted, not fitted: the authors' reordered pathway [[s_auth_share]]% (published [[s_pub_opt]]%). Caveat: the calibrated observed practice of ordering PET-CT when the referral is triaged is carried into the authors' pathway; if PET-CT were ordered only at the first visit, as the paper describes, the simulated authors' pathway gives [[s_auth_pet_first_visit]]%. Faster PET-CT alone: we predict [[s_fast_share]]%, the paper reports [[s_pub_fast]]%; we over-predict. The blind search chose from a menu of about [[s_candidates]] single changes that included each of the authors' changes as one edit; it was not told which ones the authors made. It finds the authors' three changes plus a fourth (plan tissue sampling when the referral is triaged, before the first hospital visit, i.e. before a specialist has seen the patient; needs a clinical check) and reaches [[s_opt_share]]% with the faster scanner, [[s_noeq_share]]% without new equipment.
- **Finnish synthetic county.** Within [[f_target]] days (provisional target; no Finnish first-contact target found): [[f_share_base]]% to [[f_share_opt]]%, median [[f_median_base]] to [[f_median_opt]] days. The two accepted changes: (1) [[f_change_1]]; (2) [[f_change_2]]. No new equipment; missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort (unchanged), tests per patient [[f_tests_base]] to [[f_tests_opt]]. Capacity-controlled comparison: the same extra CT and PET capacity with today's order reaches [[f_capctl_share]]%; with the hand-written order-together pathway [[f_bundle_share]]% (it needs 3 PET-CT slots).
- **Conditional finding, not the headline.** Urgent booking for every referred patient gives [[f_cond_share_0]]%, [[f_cond_share_50]]% or [[f_cond_share_100]]% if 0%, 50% or 100% of the assumed booking-lead reduction can be held. It rests entirely on assumed urgent booking leads (everyone urgent means nobody is crowded out, so the gain is exactly the assumed lead reduction), so we do not recommend it until real booking data exist.
- **Equity** (groups built from our assumptions). Under those assumptions the simulation shows both groups gain: vague symptoms [[f_ns_share_base]]% to [[f_ns_share_opt]]%, alarm symptoms [[f_ss_share_base]]% to [[f_ss_share_opt]]%. The gap in percentage points [[f_gap_pp_widens]] ([[equity_gap_base_pp]] to [[equity_gap_opt_pp]] points); the gap in median days [[f_gap_days_narrows]] ([[f_gap_days_base]] to [[f_gap_days_opt]] days). We do not claim the change closes the gap.
- **Decision model.** On a task where the right answer depends on the set of options, a correction model beats a parameter-matched dot-product model: [[dm_acc_corr]]% against [[dm_acc_dot_wide]]%. The claim that a second question costs half the compute was not reproduced at our sizes ([[dm_second_lo]]-[[dm_second_hi]]% of the first). Inside the simulator loop it matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads a shared queue unless it can see queue state.

## What is new, and what is not

Discrete-event simulation of cancer pathways exists, including for lung cancer in the UK and Norway. What we add: (1) a decision-model layer that proposes the next step at each choice point, benchmarked against a baseline and tried inside the loop; (2) an optimiser that works only from revealed information and treats hindsight bias explicitly, accepting on an exact same-patient rerun and reporting held-out; (3) a published pathway used as a blind test rather than only as calibration.

## Limitations

Synthetic data and one region. The Finnish scenario file has [[f_scn_n]] tagged inputs: [[f_scn_sourced]] cite a source and [[f_scn_assumption]] are assumptions, including every capacity, every booking lead and every urgent booking lead; they are calibrated to published waits. (`docs/parameters.md` lists more rows as evidence and calibration targets; most are not simulator inputs.) The Finnish target is provisional, and the equity gap is built from an assumption. The Norwegian check has one study, 100 patients, a model-based 80% that carries the calibrated PET-at-triage practice, and only specialist care; the faster-PET prediction misses; its search menu contained the authors' changes. Sensitivity runs (`docs/sensitivity.md`) cover the hand-written order-together pathway, not the two accepted Finnish reorders, and the Finnish held-out result rests on two cohorts of about [[f_cancers]] cancers each. A clinician must approve every change.

## Next steps and asks

Real county data, especially booking leads; clinical review of the fourth Norwegian change (sampling planned before a specialist has seen the patient) and of the GP-first idea (which failed our safety check on training patients by half a missed cancer per cohort and looked neutral on unseen ones, so it needs a proper paired test); a one-county pilot; sensitivity runs on the accepted Finnish reorders; connect the decision model.

## Run the demo

`pip install -r requirements.txt`, `python -m pytest -q`, `python -m pathway_sim demo` (about 9 minutes; `--quick` about 2.5), then open `demo/index.html` (offline; keys 1-6). The tests take about 35 seconds.

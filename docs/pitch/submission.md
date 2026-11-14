# Junction submission text

> **Safe to claim / do not claim** (numbers from `numbers_sheet.md`; update there first)
>
> **Safe to claim**
> - All patients are synthetic. The Finnish county is a scenario, not calibrated to Finnish capacity data.
> - Norway, fitted: only the observed pathway ([[s_obs_share]]% within 42 days, published [[s_pub_base]]%).
> - Norway, predicted and not fitted: the authors' pathway, [[s_auth_share]]% at our best fit against the published [[s_pub_opt]]%; across all [[s_ext_n]] settings that fit the observed data, [[s_ext_auth_min]] to [[s_ext_auth_max]]%, typically about [[s_ext_auth_med]]%; [[s_ext_auth_in_ci_pct]]% of settings inside the published interval.
> - The ranking (reordering beats a faster scanner beats today) holds in all [[s_ext_rank_n]] settings.
> - We over-predict a faster scanner alone: [[s_fast_share]]% against the published [[s_pub_fast]]%.
> - The search found the authors' three changes plus a fourth that needs a clinical check; it chose from a menu of about [[s_candidates]] changes that contained the authors' changes. [[s_opt_share]]% with the faster scanner, [[s_noeq_share]]% with no new equipment (best-fit setting).
> - Finland, synthetic: [[f_share_base]]% to [[f_share_opt]]% within [[f_target]] days (provisional target), two reorders, no new equipment.
> - The primary-care loop is a demonstrated mechanism with placeholder decision tables, not a result.
>
> **Do not claim**
> - "We predicted 80% exactly", "matches the paper", "78 to 86%".
> - "The optimiser found the authors' answer blind" without the menu caveat; that the fourth change is safe.
> - [[f_cond_share_100]]% as a result (conditional on assumed urgent booking times).
> - Any Finnish number as an estimate for real patients; lives saved; that the equity gap closes (in points it widens).
> - That the model-written cards are "leak-free": the independent review found report wording that gives away false alarms; fix and regeneration in progress.
> - Any primary-care loop number as a finding (it fails [[e_checks_failed]] of [[e_checks_total]] consistency checks against the calibrated chain).
> - That a model trained on synthetic cards works on real patients; that the team's decision model (JEV) produced the headline numbers.
> - How the optimiser's Norwegian changes hold on all [[s_ext_n]] settings or without the fourth change (check pending).

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
- A synthetic patient engine: a catalogue of 11 chest-symptom conditions, 42 hidden variables and 26 tests (a draft no clinician has read), and patient cards that hold a hidden truth plus the pre-written result of every test. Today: [[lib_ref_n]] template-written cards and [[lib_llm_n]] model-written cards, all synthetic (counts change when libraries are regenerated after a review finding on report wording). Decisions see only the revealed record, never the hidden truth.
- A primary-care encounter loop built on those cards. It is a mechanism with placeholder decision tables; it does not yet reproduce the calibrated Finnish chain (it fails [[e_checks_failed]] of [[e_checks_total]] consistency checks), so we show it as a mechanism, not a result.
- The team's fine-tuned decision model (JEV), connected through an adapter and a step-through tool. The simulator runs shown here use placeholder decision tables and rules.

## How it works

Each flowchart step reveals results, takes time and uses a resource. Proposals are scored from revealed timestamps (which prerequisite held a step back, by how many days). A change is kept only if a rerun of the same patients, with common random numbers, is faster and passes the guardrails. Numbers are reported on held-out patients. In real life the acceptance rerun would be a pilot, because it uses the simulated truth.

## Results (held-out, with sources)

- **Norwegian check** (Stokstad et al. 2019, 100 early-stage patients, one hospital). Fitted only to the observed pathway: [[s_obs_share]]% within 42 days (published [[s_pub_base]]%). Predicted, not fitted: the authors' reordered pathway. At our best fit it gives [[s_auth_share]]% (published [[s_pub_opt]]%, itself a model estimate). That best fit is one point in a band: the two fitted numbers act as one constraint, so five inputs the paper does not report are not pinned down. Across all [[s_ext_n]] settings that fit the observed pathway the prediction is [[s_ext_auth_min]] to [[s_ext_auth_max]]%, typically about [[s_ext_auth_med]]%, and [[s_ext_auth_in_ci_pct]]% of settings fall inside the published interval ([[val_pub_opt_ci]]%). What holds in every one of the [[s_ext_rank_n]] settings is the ranking: reordering beats a faster scanner beats today. A second caveat: the calibrated practice of ordering PET-CT when the referral is triaged is carried into the authors' pathway; if PET-CT were ordered only at the first visit, as the paper describes, the best-fit authors' pathway gives [[s_auth_pet_first_visit]]%. Faster PET-CT alone: we predict [[s_fast_share]]% at the best fit (band [[s_ext_fast_min]] to [[s_ext_fast_max]]%), the paper reports [[s_pub_fast]]%; we over-predict. The search chose from a menu of about [[s_candidates]] single changes that included each of the authors' changes as one edit; it was not told which ones the authors made. It finds the authors' three changes plus a fourth (plan tissue sampling when the referral is triaged, before a specialist has seen the patient; needs a clinical check) and reaches [[s_opt_share]]% with the faster scanner (the authors' 80% also assumes that scanner) and [[s_noeq_share]]% with no new equipment. These two numbers are from the best-fit setting; how they hold on the other settings, and without the fourth change, is being checked and is not yet claimed. The lead over the authors comes from the fourth change.
- **Finnish synthetic county.** Within [[f_target]] days (provisional target; no Finnish first-contact target found): [[f_share_base]]% to [[f_share_opt]]%, median [[f_median_base]] to [[f_median_opt]] days. The two accepted changes: (1) [[f_change_1]]; (2) [[f_change_2]]. No new equipment; missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort (unchanged), tests per patient [[f_tests_base]] to [[f_tests_opt]]. Capacity-controlled comparison: the same extra CT and PET capacity with today's order reaches [[f_capctl_share]]%; with the hand-written order-together pathway [[f_bundle_share]]% (it needs 3 PET-CT slots).
- **Conditional finding, not the headline.** Urgent booking for every referred patient gives [[f_cond_share_0]]%, [[f_cond_share_50]]% or [[f_cond_share_100]]% if 0%, 50% or 100% of the assumed booking-lead reduction can be held. It rests entirely on assumed urgent booking leads (everyone urgent means nobody is crowded out, so the gain is exactly the assumed lead reduction), so we do not recommend it until real booking data exist.
- **Equity** (groups built from our assumptions). Under those assumptions the simulation shows both groups gain: vague symptoms [[f_ns_share_base]]% to [[f_ns_share_opt]]%, alarm symptoms [[f_ss_share_base]]% to [[f_ss_share_opt]]%. The gap in percentage points [[f_gap_pp_widens]] ([[equity_gap_base_pp]] to [[equity_gap_opt_pp]] points); the gap in median days [[f_gap_days_narrows]] ([[f_gap_days_base]] to [[f_gap_days_opt]] days). We do not claim the change closes the gap.
- **Our decision-model benchmark** (a small numpy model of ours, separate from the team's JEV). On a task where the right answer depends on the set of options, a correction model beats a parameter-matched dot-product model: [[dm_acc_corr]]% against [[dm_acc_dot_wide]]%. The claim that a second question costs half the compute was not reproduced at our sizes ([[dm_second_lo]]-[[dm_second_hi]]% of the first). Inside the simulator loop it matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads a shared queue unless it can see queue state.

## What is new, and what is not

Discrete-event simulation of cancer pathways exists, including for lung cancer in the UK and Norway. What we add: (1) a decision-model layer that proposes the next step at each choice point, benchmarked against a baseline and tried inside the loop; (2) an optimiser that works only from revealed information and treats hindsight bias explicitly, accepting on an exact same-patient rerun and reporting held-out; (3) a published pathway used as a held-back test rather than only as calibration (with the caveat that the calibration cannot pin its inputs down, so the test gives a band).

## Limitations

Synthetic data and one region. The Finnish scenario file has [[f_scn_n]] input blocks (`docs/ledger.md`): [[f_scn_sourced]] cite a source ([[f_scn_strict]] without assumption wording in their own note) and [[f_scn_assumption]] are assumptions, including every capacity, every booking lead and every urgent booking lead; they are calibrated to published waits. (`docs/parameters.md` lists more rows as evidence and calibration targets; most are not simulator inputs.) The Finnish target is provisional, and the equity gap is built from an assumption. The Norwegian check has one study, one hospital, 100 patients, a model-based 80% that carries the calibrated PET-at-triage practice, and only specialist care; its prediction is a band ([[s_ext_auth_min]] to [[s_ext_auth_max]]% for the authors' pathway), not a point; the faster-PET prediction misses; its search menu contained the authors' changes. Synthetic patient cards are not validated against real patients, their backgrounds have no population model yet, an independent review found that the wording of test reports in model-written cards gives away false alarms (fix in progress), and no model trained on them has been tested on real patients. The Finnish headline is the mean of two held-out cohorts of about [[f_cancers]] cancers each; across [[r_f_cohorts]] cohorts today's share is [[r_f_base_lo]] to [[r_f_base_hi]]% and the suggested change's [[r_f_sug_lo]] to [[r_f_sug_hi]]%, with a gain of [[r_f_gain_lo]] to [[r_f_gain_hi]] points that is positive in every cohort and in [[r_f_joint_better]]% of [[r_f_joint_draws]] joint assumption draws (`docs/ranges.md`). Norwegian numbers on 100-patient cohorts (the size of the real study): observed [[r_n_obs_lo]] to [[r_n_obs_hi]]%, the authors' pathway [[r_n_auth_lo]] to [[r_n_auth_hi]]%, optimiser [[r_n_opt_lo]] to [[r_n_opt_hi]]% (without new equipment [[r_n_noeq_lo]] to [[r_n_noeq_hi]]%). Those cohort ranges are at the best-fit setting; the spread over calibration settings is in `docs/validation.md` (Robustness). The older sensitivity runs (`docs/sensitivity.md`) cover the hand-written order-together pathway. A clinician must approve every change.

## Next steps and asks

Real county data, especially booking leads; clinical review of the fourth Norwegian change (sampling planned before a specialist has seen the patient) and of the GP-first idea (which failed our safety check on training patients by half a missed cancer per cohort and looked neutral on unseen ones, so it needs a proper paired test); a one-county pilot; a sensitivity run with several seeds per variant on the accepted Finnish reorders (one seed per variant so far); a clinician to read and correct the patient catalogue; real decision data to train and test the team's decision model (JEV), which today has only synthetic cards; a primary-care loop whose decision tables are replaced by the JEV and then checked against the calibrated chain.

## Run the demo

`pip install -r requirements.txt`, `python -m pytest -q`, `python -m pathway_sim demo` (about 9 minutes; `--quick` about 2.5), then open `demo/index.html` (offline; keys 1-6). The tests take about 2 minutes.

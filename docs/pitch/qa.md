# Q&A prep: the 12 hardest questions

Short answers, about 15 seconds each. Numbers are filled from the bundle (`filled/qa.md`). Where an answer depends on a pending team decision (D17, D18, D20) it says so.

**1. Isn't this just synthetic?**
Yes, all of it, and every results screen says so. Two things stand in for real data: every scenario input carries a source tag or is marked as an assumption, and the engine reproduces a published Norwegian pathway. Be plain about the split: the Finnish scenario file has [[f_scn_n]] tagged inputs, [[f_scn_sourced]] sourced and [[f_scn_assumption]] assumptions, and the assumptions include every capacity and booking lead (calibrated to published waits); the Norwegian file has [[s_scn_n]] tags, [[s_scn_assumption]] assumptions. The larger parameter table is evidence and calibration targets, not all simulator inputs. The claim is "worth piloting", not "works in Finland".

**2. Why should Finland trust a Norwegian calibration?**
It does not have to. The Norwegian case tests the engine's reordering logic against one published result, with only the observed pathway fitted. Finnish numbers come from a separate scenario with Finnish sources and assumed capacities. One study, one centre, 100 patients, specialist care only.

**3. Does it match the Norwegian paper?**
Mostly. Fitted: [[s_obs_share]]% against [[s_pub_base]]%. Predicted: [[s_auth_share]]% against [[s_pub_opt]]% for the authors' pathway, with a caveat: the calibrated observed practice (PET-CT ordered when the referral is triaged) is carried into that pathway, and if PET-CT were ordered only at the first visit the simulated authors' pathway gives [[s_auth_pet_first_visit]]%. It also misses on the faster scanner alone: [[s_fast_share]]% against [[s_pub_fast]]%. The authors' 80% is itself a model estimate.

**4. How does it avoid hindsight bias?**
Proposals are scored on groups from revealed timestamps only, not by judging a late test on patients who failed earlier ones. Acceptance is a rerun of the same patients (common random numbers), and we report on held-out patients. Selection optimism: [[s_opt_optimism_pp]] points (Norwegian) and [[f_optimism_pp]] (Finnish; negative means the unseen patients did slightly better). Did the Norwegian search "find" the authors' answer blind? It chose from a menu of about [[s_candidates]] single changes that included each of the authors' changes as one edit, and it was not told which; that is a search over a menu we wrote, not a discovery from nothing.

**5. The acceptance step uses simulated truth. Isn't that cheating?**
It is the one step with no real-world equivalent, and we say so. In practice it is a monitored pilot. Proposals never see the hidden condition.

**6. Where is the AI?**
Three places: the optimiser (search over flowchart changes), the decision model (a transformer-style model that proposes the next step and is benchmarked against a dot-product baseline), and the AI-assisted build. The decision model is not driving the demo runs; a rule policy does. In our in-loop test the model matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads the shared queue unless it can see queue state. We would rather say that than overclaim.

**7. Does the decision model work?**
On a task where the right answer depends on the option set, it scores [[dm_acc_corr]]% against [[dm_acc_dot_wide]]% for a parameter-matched dot-product baseline ([[dm_acc_dot]]% for the smaller d=32 one). On the control task it also wins by [[dm_ctrl_gain_pp]] points, so part of the gain is capacity. The "half the compute for a second question" claim did not reproduce: [[dm_second_lo]]-[[dm_second_hi]]% at our sizes. Task and rule are ours; no public benchmark yet.

**8. What would a hospital do on Monday?**
Pick one lung unit. Reserve the treatment slot when the case is sent to the tumour board and book the specialist visit when the referral arrives, and measure days from first contact to treatment by step, including booking leads. The simulator says these two reorders take our county from [[f_share_base]]% to [[f_share_opt]]% within [[f_target]] days with no new equipment. A bigger hand-written order-together pathway reaches [[f_bundle_share]]% against [[f_capctl_share]]% for the same extra capacity with today's order, but it needs PET-CT capacity, so check the scanner first.

**9. Why a [[f_target]]-day target?**
Provisional (D20). From first contact, every flowchart is at 0% within the Norwegian 42 days, and we found no Finnish first-contact target. Median days ([[f_median_base]] to [[f_median_opt]]) does not depend on the choice.

**10. Does the change widen inequality?**
Under our assumptions both groups gain ([[f_ns_share_base]]% to [[f_ns_share_opt]]% vague, [[f_ss_share_base]]% to [[f_ss_share_opt]]% alarm). The gap in points [[f_gap_pp_widens]] ([[equity_gap_base_pp]] to [[equity_gap_opt_pp]]); the gap in median days [[f_gap_days_narrows]] ([[f_gap_days_base]] to [[f_gap_days_opt]]). The group difference is our assumption (D9), so this shows how a change reaches each group, not how unequal Finland is.

**11. Does speed come at the cost of missed cancers or other patients?**
Not in the model: missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort, tests per patient [[f_tests_base]] to [[f_tests_opt]], non-cancer patients leave in [[f_noncancer_base]] to [[f_noncancer_opt]] days. Guardrails include tissue-confirmed diagnoses, added after the optimiser tried skipping sampling; bronchoscopy and needle biopsy are marked as confirming in the Finnish scenario too, so that guardrail is active there. Crowd-out would depend on how many slots a priority track reserves; our accepted changes use none. (In the Norwegian check every patient has cancer, so the missed-cancer guardrail is vacuous there.)

**12. Isn't adding capacity simpler?**
Sometimes. One more slot at the busiest scanner (the [[f_cap_top_name]]) adds [[f_cap_top_pp]] points; the next best adds [[f_cap_second_pp]] and the rest at most [[f_cap_rest_max_pp]]. Hand-written reordering with extra capacity adds [[f_bundle_gain_pp]] points, and the optimiser's two reorders with no new capacity add [[f_share_gain_pp]] (against [[f_capctl_gain_pp]] for a large capacity increase with today's order). The two are not exclusive; the bigger reorder needs the capacity at the scanner it moves work to. Capacity vs order in our county is a result of our assumptions; the Norwegian study is the independent evidence.

## If pressed

- The Norwegian optimiser's fourth change plans tissue sampling at referral triage, before a specialist has seen the patient. It is beyond the paper and needs clinical review (D18). The headline with the faster scanner is [[s_opt_share]]%; without new equipment [[s_noeq_share]]% (D17).
- GP-first instead of nurse-first was not accepted: it did not pass our safety checks on the training patients (half a missed cancer per cohort more, one patient in one cohort), while on unseen patients it looked neutral to positive. That is noise-level either way, so it needs a paired test with more cohorts, not a verdict.
- "Why not [[f_cond_share_100]]%?": urgent booking for every referred patient gives [[f_cond_share_0]]% / [[f_cond_share_50]]% / [[f_cond_share_100]]% at 0 / 50 / 100% of the assumed lead reduction. It depends entirely on assumed urgent booking leads, so it is a conditional finding that needs real booking data, not a fast lane and not our headline.

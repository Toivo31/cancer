# Q&A prep: the 12 hardest questions

Short answers, about 15 seconds each. Numbers are filled from the bundle (`filled/qa.md`). Where an answer depends on a pending team decision (D17, D18, D20) it says so.

**1. Isn't this just synthetic?**
Yes, all of it, and every results screen says so. Two things stand in for real data: every parameter is traced to a source or marked as an assumption ([[assumption_count]] of [[parameter_count]]), and the engine reproduces a published Norwegian pathway. The claim is "worth piloting", not "works in Finland".

**2. Why should Finland trust a Norwegian calibration?**
It does not have to. The Norwegian case tests the engine's reordering logic against one published result, with only the observed pathway fitted. Finnish numbers come from a separate scenario with Finnish sources and assumed capacities. One study, one centre, 100 patients, specialist care only.

**3. Does it match the Norwegian paper?**
Mostly. Fitted: [[s_obs_share]]% against [[s_pub_base]]%. Predicted: [[s_auth_share]]% against [[s_pub_opt]]% for the authors' pathway. It misses on the faster scanner alone: [[s_fast_share]]% against [[s_pub_fast]]%. The authors' 80% is also a model estimate.

**4. How does it avoid hindsight bias?**
Proposals are scored on groups from revealed timestamps only, not by judging a late test on patients who failed earlier ones. Acceptance is a rerun of the same patients (common random numbers), and we report on held-out patients. Selection optimism: [[s_opt_optimism_pp]] points (Norwegian) and [[f_optimism_pp]] (Finnish).

**5. The acceptance step uses simulated truth. Isn't that cheating?**
It is the one step with no real-world equivalent, and we say so. In practice it is a monitored pilot. Proposals never see the hidden condition.

**6. Where is the AI?**
Three places: the optimiser (search over flowchart changes), the decision model (a transformer-style model that proposes the next step and is benchmarked against a dot-product baseline), and the AI-assisted build. The decision model is not yet driving the demo runs; a rule policy does. We would rather say that than overclaim.

**7. Does the decision model work?**
On a task where the right answer depends on the option set, it scores [[dm_acc_corr]]% against [[dm_acc_dot]]% for a dot-product baseline ([[dm_acc_dot_wide]]% when parameter-matched). On the control task it also wins by [[dm_ctrl_gain_pp]] points, so part of the gain is capacity. The "half the compute for a second question" claim did not reproduce: [[dm_second_lo]]-[[dm_second_hi]]% at our sizes. Task and rule are ours; no public benchmark yet.

**8. What would a hospital do on Monday?**
Pick one lung unit. Order PET-CT, exercise test and the tumour-board slot together at the first specialist visit, book sampling in parallel, and measure days from first contact to treatment by step. The simulator says that order beats capacity in our county ([[f_bundle_share]]% against [[f_capctl_share]]% with the same extra capacity), but it needs PET-CT capacity, so check the scanner first.

**9. Why a [[f_target]]-day target?**
Provisional (D20). From first contact, every flowchart is at 0% within the Norwegian 42 days, and we found no Finnish first-contact target. Median days ([[f_median_base]] to [[f_median_opt]]) does not depend on the choice.

**10. Does the change widen inequality?**
Both groups gain ([[f_ns_share_base]]% to [[f_ns_share_opt]]% vague, [[f_ss_share_base]]% to [[f_ss_share_opt]]% alarm). The gap in points [[f_gap_pp_widens]]; the gap in median days [[f_gap_days_narrows]]. The group difference is our assumption (D9), so this shows how a change reaches each group, not how unequal Finland is.

**11. Does speed come at the cost of missed cancers or other patients?**
Not in the model: missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort, tests per patient [[f_tests_base]] to [[f_tests_opt]], non-cancer patients leave in [[f_noncancer_base]] to [[f_noncancer_opt]] days. Guardrails include tissue-confirmed diagnoses, added after the optimiser tried skipping sampling. Crowd-out depends on how many slots a fast lane reserves.

**12. Isn't adding capacity simpler?**
Sometimes. One more slot at the busiest scanner (the [[f_cap_top_name]]) adds [[f_cap_top_pp]] points; the next best adds [[f_cap_second_pp]] and the rest at most [[f_cap_rest_max_pp]]. Reordering with extra capacity adds [[f_bundle_gain_pp]] points. The two are not exclusive; reordering needs the capacity at the scanner it moves work to. Capacity vs order in our county is a result of our assumptions; the Norwegian study is the independent evidence.

## If pressed

- The Norwegian optimiser's fourth change (booking tissue sampling at the first visit) is beyond the paper and needs clinical review (D18). The headline with the faster scanner is [[s_opt_share]]%; without new equipment [[s_noeq_share]]% (D17).
- Nurse-first to GP-first in the Finnish suggestion is a modelled effect; whether counties can staff it is untested.

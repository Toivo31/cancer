# Q&A prep: the 12 hardest questions

Short answers, about 15 seconds each. Numbers are filled from the bundle (`filled/qa.md`). Where an answer depends on a pending team decision (D17, D18, D20) it says so.

**1. Isn't this just synthetic?**
Yes, all of it, and every results screen says so. Two things stand in for real data: every scenario input carries a source tag or is marked as an assumption, and the engine reproduces a published Norwegian pathway. Be plain about the split: the Finnish scenario file has 65 tagged inputs, 21 sourced and 44 assumptions, and the assumptions include every capacity and booking lead (calibrated to published waits); the Norwegian file has 26 tags, 3 assumptions. The larger parameter table is evidence and calibration targets, not all simulator inputs. The claim is "worth piloting", not "works in Finland".

**2. Why should Finland trust a Norwegian calibration?**
It does not have to. The Norwegian case tests the engine's reordering logic against one published result, with only the observed pathway fitted. Finnish numbers come from a separate scenario with Finnish sources and assumed capacities. One study, one centre, 100 patients, specialist care only.

**3. Does it match the Norwegian paper?**
Mostly. Fitted: 40% against 40%. Predicted: 80% against 80% for the authors' pathway, with a caveat: the calibrated observed practice (PET-CT ordered when the referral is triaged) is carried into that pathway, and if PET-CT were ordered only at the first visit the simulated authors' pathway gives 66%. It also misses on the faster scanner alone: 60% against 48%. The authors' 80% is itself a model estimate.

**4. How does it avoid hindsight bias?**
Proposals are scored on groups from revealed timestamps only, not by judging a late test on patients who failed earlier ones. Acceptance is a rerun of the same patients (common random numbers), and we report on held-out patients. Selection optimism: 1.7 points (Norwegian) and -0.2 (Finnish; negative means the unseen patients did slightly better). Did the Norwegian search "find" the authors' answer blind? It chose from a menu of about 69 single changes that included each of the authors' changes as one edit, and it was not told which; that is a search over a menu we wrote, not a discovery from nothing.

**5. The acceptance step uses simulated truth. Isn't that cheating?**
It is the one step with no real-world equivalent, and we say so. In practice it is a monitored pilot. Proposals never see the hidden condition.

**6. Where is the AI?**
Three places: the optimiser (search over flowchart changes), the decision model (a transformer-style model that proposes the next step and is benchmarked against a dot-product baseline), and the AI-assisted build. The decision model is not driving the demo runs; a rule policy does. In our in-loop test the model matched the hand-written rule rather than beating it, and it showed that a model optimising each patient separately overloads the shared queue unless it can see queue state. We would rather say that than overclaim.

**7. Does the decision model work?**
On a task where the right answer depends on the option set, it scores 84.5% against 79.0% for a parameter-matched dot-product baseline (78.3% for the smaller d=32 one). On the control task it also wins by 2.5 points, so part of the gain is capacity. The "half the compute for a second question" claim did not reproduce: 76-91% at our sizes. Task and rule are ours; no public benchmark yet.

**8. What would a hospital do on Monday?**
Pick one lung unit. Reserve the treatment slot when the case is sent to the tumour board and book the specialist visit when the referral arrives, and measure days from first contact to treatment by step, including booking leads. The simulator says these two reorders take our county from 18% to 33% within 90 days with no new equipment. A bigger hand-written order-together pathway reaches 54% against 31% for the same extra capacity with today's order, but it needs PET-CT capacity, so check the scanner first.

**9. Why a 90-day target?**
Provisional (D20). From first contact, every flowchart is at 0% within the Norwegian 42 days, and we found no Finnish first-contact target. Median days (102 to 94) does not depend on the choice.

**10. Does the change widen inequality?**
Under our assumptions both groups gain (13% to 26% vague, 27% to 50% alarm). The gap in points widens (13.6 to 24.6); the gap in median days narrows (11.2 to 9.9). The group difference is our assumption (D9), so this shows how a change reaches each group, not how unequal Finland is.

**11. Does speed come at the cost of missed cancers or other patients?**
Not in the model: missed cancers 27.5 to 27.5 per cohort, tests per patient 0.41 to 0.41, non-cancer patients leave in 16.8 to 16.8 days. Guardrails include tissue-confirmed diagnoses, added after the optimiser tried skipping sampling; bronchoscopy and needle biopsy are marked as confirming in the Finnish scenario too, so that guardrail is active there. Crowd-out would depend on how many slots a priority track reserves; our accepted changes use none. (In the Norwegian check every patient has cancer, so the missed-cancer guardrail is vacuous there.)

**12. Isn't adding capacity simpler?**
Sometimes. One more slot at the busiest scanner (the PET-CT scanner) adds 9.7 points; the next best adds 3.6 and the rest at most 1.5. Hand-written reordering with extra capacity adds 36 points, and the optimiser's two reorders with no new capacity add 16 (against 13 for a large capacity increase with today's order). The two are not exclusive; the bigger reorder needs the capacity at the scanner it moves work to. Capacity vs order in our county is a result of our assumptions; the Norwegian study is the independent evidence.

## If pressed

- The Norwegian optimiser's fourth change plans tissue sampling at referral triage, before a specialist has seen the patient. It is beyond the paper and needs clinical review (D18). The headline with the faster scanner is 88%; without new equipment 67% (D17).
- GP-first instead of nurse-first was not accepted: it did not pass our safety checks on the training patients (half a missed cancer per cohort more, one patient in one cohort), while on unseen patients it looked neutral to positive. That is noise-level either way, so it needs a paired test with more cohorts, not a verdict.
- "Why not 61%?": urgent booking for every referred patient gives 18% / 44% / 61% at 0 / 50 / 100% of the assumed lead reduction. It depends entirely on assumed urgent booking leads, so it is a conditional finding that needs real booking data, not a fast lane and not our headline.

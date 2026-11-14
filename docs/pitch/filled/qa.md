# Q&A prep: the 12 hardest questions

Short answers, about 15 seconds each. Numbers are filled from the bundle (`filled/qa.md`). Where an answer depends on a pending team decision (D17, D18, D20) it says so.

**1. Isn't this just synthetic?**
Yes, all of it, and every results screen says so. Two things stand in for real data: every parameter is traced to a source or marked as an assumption (18 of 131), and the engine reproduces a published Norwegian pathway. The claim is "worth piloting", not "works in Finland".

**2. Why should Finland trust a Norwegian calibration?**
It does not have to. The Norwegian case tests the engine's reordering logic against one published result, with only the observed pathway fitted. Finnish numbers come from a separate scenario with Finnish sources and assumed capacities. One study, one centre, 100 patients, specialist care only.

**3. Does it match the Norwegian paper?**
Mostly. Fitted: 40% against 40%. Predicted: 80% against 80% for the authors' pathway. It misses on the faster scanner alone: 60% against 48%. The authors' 80% is also a model estimate.

**4. How does it avoid hindsight bias?**
Proposals are scored on groups from revealed timestamps only, not by judging a late test on patients who failed earlier ones. Acceptance is a rerun of the same patients (common random numbers), and we report on held-out patients. Selection optimism: 1.7 points (Norwegian) and -1.4 (Finnish).

**5. The acceptance step uses simulated truth. Isn't that cheating?**
It is the one step with no real-world equivalent, and we say so. In practice it is a monitored pilot. Proposals never see the hidden condition.

**6. Where is the AI?**
Three places: the optimiser (search over flowchart changes), the decision model (a transformer-style model that proposes the next step and is benchmarked against a dot-product baseline), and the AI-assisted build. The decision model is not yet driving the demo runs; a rule policy does. We would rather say that than overclaim.

**7. Does the decision model work?**
On a task where the right answer depends on the option set, it scores 84.5% against 78.3% for a dot-product baseline (79.0% when parameter-matched). On the control task it also wins by 2.5 points, so part of the gain is capacity. The "half the compute for a second question" claim did not reproduce: 76-91% at our sizes. Task and rule are ours; no public benchmark yet.

**8. What would a hospital do on Monday?**
Pick one lung unit. Order PET-CT, exercise test and the tumour-board slot together at the first specialist visit, book sampling in parallel, and measure days from first contact to treatment by step. The simulator says that order beats capacity in our county (54% against 31% with the same extra capacity), but it needs PET-CT capacity, so check the scanner first.

**9. Why a 90-day target?**
Provisional (D20). From first contact, every flowchart is at 0% within the Norwegian 42 days, and we found no Finnish first-contact target. Median days (102 to 80) does not depend on the choice.

**10. Does the change widen inequality?**
Both groups gain (13% to 54% vague, 27% to 79% alarm). The gap in points widens; the gap in median days narrows. The group difference is our assumption (D9), so this shows how a change reaches each group, not how unequal Finland is.

**11. Does speed come at the cost of missed cancers or other patients?**
Not in the model: missed cancers 27.5 to 27.5 per cohort, tests per patient 0.41 to 0.41, non-cancer patients leave in 16.8 to 16.8 days. Guardrails include tissue-confirmed diagnoses, added after the optimiser tried skipping sampling. Crowd-out depends on how many slots a fast lane reserves.

**12. Isn't adding capacity simpler?**
Sometimes. One more slot at the busiest scanner (the PET-CT scanner) adds 9.7 points; the next best adds 3.6 and the rest at most 1.5. Reordering with extra capacity adds 36 points. The two are not exclusive; reordering needs the capacity at the scanner it moves work to. Capacity vs order in our county is a result of our assumptions; the Norwegian study is the independent evidence.

## If pressed

- The Norwegian optimiser's fourth change (booking tissue sampling at the first visit) is beyond the paper and needs clinical review (D18). The headline with the faster scanner is 88%; without new equipment 67% (D17).
- Nurse-first to GP-first in the Finnish suggestion is a modelled effect; whether counties can staff it is untested.

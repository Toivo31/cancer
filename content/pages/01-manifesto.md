# Manifesto

Cancer patients in Finland wait too long for a diagnosis, and most of that time is not spent on tests. It is spent in queues between them. Each step of a care pathway can be reasonable on its own while the order of the steps, and the queues that form in front of scarce tests, keep patients waiting for weeks.

We believe the fastest way to shorten that wait is not always more equipment or more staff. Often it is a better order of steps. A pathway is a process, and processes can be described, tested and improved.

## The idea

We describe a care pathway as a flowchart. Every visit, test and clinical judgement is a step, and every point where someone chooses what happens next is a decision. At each decision our model, Birch, reads what is known about the patient so far and ranks the options the flowchart allows. A doctor always makes the final call.

We then run thousands of synthetic patients through the flowchart, with realistic waits and limited capacity, to see where time is lost. An optimiser tries changes to the pathway and keeps only those that get the same patients to treatment faster without missing more cancers.

## What it gives

**A second opinion for every decision.** The doctor sees what the model recommends and how it ranks the alternatives. This catches outliers and outdated habits, so the quality of care depends less on which doctor a patient happens to meet.

**A safe foundation for automation.** Because every step and decision is explicit, steps can be automated one at a time while the flowchart keeps the process under human control.

**Faster pathways without new resources.** The simulation shows where the queues are, and the optimiser finds a better order of steps. When we rebuilt a published hospital pathway, our optimiser found the same kind of reordering that the hospital's own clinicians had proposed.

## From demo to real care

Today everything runs on synthetic patients, and we say so openly. Each synthetic part can be replaced with a real one: waiting times and capacities from a hospital's booking data, test accuracies from published studies, and decisions learned from a region's own records. The details of how the data is built, the research behind the idea and the hospital case study are in the [Appendix](04-appendix.md).

---

**Infographic:** one loop. Patient → flowchart with decisions (Birch ranks the options, a doctor decides) → simulation shows where queues form → optimiser proposes a better pathway → rerun. The three benefits are marked where they arise on the loop.

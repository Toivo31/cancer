# Introduction

Finland diagnoses cancer more slowly than its Nordic neighbours, and most of that time is not spent on tests. It is spent waiting between them. A patient with lung symptoms may see a nurse, then a GP, then wait for an X-ray, then for a referral, then for a CT, a biopsy and a specialist meeting. Each step is reasonable on its own, but the order in which they happen, and the queues that build up in front of scarce tests, decide how long the whole journey takes.

Our project turns a care pathway into something that can be inspected, tested and improved. We describe the pathway as a flowchart: every visit, test and clinical judgement is a step, and every point where someone chooses what happens next is a decision node. At each decision node our decision model, Birch, reads what is known about the patient so far and scores the options the flowchart allows. Synthetic patients then move through the flowchart in a simulation, with realistic waiting times and limited capacity, so we can see where time is lost.

## How it would be calibrated with real data

Everything in the demo runs on synthetic patients, and we say so openly. The system is built so that the synthetic parts can be replaced one by one with real ones. Waiting times and test capacities come from a hospital's own booking data. Test accuracies come from published studies. The decision model is fine-tuned on a region's own past decisions, using only what was in the record at the time each decision was made. To show that the simulator can stand in for a real hospital, we rebuilt a published Norwegian lung cancer pathway and tuned it until it reproduced the observed result: 40 percent of patients treated within the 42-day target. That case study is described on its own page.

## Three advantages

The same flowchart and decision model give three things at once.

**A second opinion.** At every decision the doctor can see what the model would recommend and how it ranks the alternatives. This catches outliers and outdated habits, and it makes care depend less on which doctor a patient happens to meet. The doctor always makes the final call.

**Infrastructure for automated steps.** Because every step and decision point is explicit, individual steps can be automated safely, one at a time. When a sample is taken by a machine or a result arrives digitally, the model can interpret it and propose the next step, while the flowchart keeps the process under human control.

**Optimising the pathway itself.** The simulation shows where queues form. An optimiser then tries changes to the flowchart, such as ordering a scan earlier or booking treatment while the last test is still being reported, and keeps a change only if the same patients get through faster without missing more cancers. This raises throughput without new equipment or staff.

---

**Infographic:** one loop diagram. Patient → flowchart with decision nodes (Birch scores the options, a doctor decides) → simulation shows queues and waiting time → optimiser proposes a better flowchart → rerun. The three advantages are labelled on the loop where they arise: second opinion at the decision node, automation at the step, optimisation at the flowchart.

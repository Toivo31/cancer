# Birch applied to healthcare

In our simulation every point where someone decides what happens next is a decision node. A nurse deciding whether a patient needs a GP visit, a GP choosing between antibiotics and an X-ray, a specialist choosing a sampling method, and the tumour board choosing a treatment lane are all nodes. At each node, Birch receives two things: the patient's record as it stands at that moment, and the options the flowchart allows from that node. It returns a score for each option, and the highest-scoring option is proposed. In the real world a doctor would see that proposal and make the final decision.

## Only what a clinician could see

The most important rule is that Birch never sees the hidden truth about a patient. Every synthetic patient carries a true diagnosis and the results of every test in advance, but Birch only receives what has been revealed so far: the presenting complaint, the background, earlier visits and the results of tests that have actually been done. Before every request, a check confirms that no hidden field, future result or diagnosis label is included. This makes the simulated decisions honest, and it means the same model could work from a real patient record.

The record is turned into plain text, in the same form a clinician would read it: one entry per visit or result, in time order. The question at the node and the allowed options are taken straight from the flowchart.

## How it was tuned

Birch was fine-tuned from a Nemotron base model by adapting its final layers and training our scoring head to pick the right option among those offered. The simulator can export training examples in exactly the format Birch receives: the visible record at each decision, the options offered, the choice that was made, and how the patient's journey turned out. Because the hidden diagnosis is kept separate from the input, a model trained on these examples has to learn to decide from the record, not from the answer.

We also tested the architecture directly inside the simulator. Trained only on outcomes of past choices, the models rediscovered the sensible rule for choosing a sampling method by lesion location. When the models were also shown how long each option's queue was, they learned to spread patients across sampling methods instead of overloading one of them. Without queue information, a learned policy sent too many patients to the same method and made the pathway much slower, which is a useful warning about training decision models without the context a clinic actually has.

## What is and is not driven by Birch

The headline results on the Simulation and Norway pages come from fixed, hand-written decision rules at the nodes, so they do not depend on the model. Birch can be switched on at the decision nodes and stepped through patient by patient, with every proposal shown for review. Its scores rank the options on offer; they are not disease probabilities.

---

**Infographic:** one decision node, zoomed in. On the left, the patient card with most fields greyed out (hidden) and only the revealed entries visible. In the middle, Birch. On the right, the allowed options with scores, and a doctor icon making the final choice.

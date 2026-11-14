# Birch: our JEV decision model

Birch is a decision model, not a chatbot. You give it a situation and a list of possible answers, and it returns a score for every answer in a single pass. It cannot invent an answer that is not on the list, which makes it a natural fit for any process where the allowed next steps are known in advance, such as a care pathway.

Birch belongs to the JEV family of decision models. It is built on NVIDIA Nemotron 3.5 Super VL, a large open vision-language model. We kept the base model frozen, trained small adapters on its final blocks and added our own scoring head on top. The training mix combined medical and general multiple-choice tasks, including skin-lesion photos; full documentation of the training data is still to come.

## What is new

A plain JEV model reads the situation once, reads each option separately, and scores each option by how well it matches the situation. Each option is judged alone, so the model cannot tell that an option is best only because the others are worse, or that one option's value depends on another option's queue.

Our addition is a small step between reading and scoring in which every option can look at every other option before the final score is given. The order of the options does not matter, and their number can change from question to question. The result is a model that compares options side by side, the way a person does. In a controlled test inside our simulator, a small model with this architecture matched the ideal sampling choice in 92 percent of the cases where the best choice depends on another option's queue, against about 30 percent for a plain per-option model trained on the same 12,000 choices. A plain model given a hand-written summary of the options did nearly as well, and the gain needs plenty of training data.

Birch also encodes the situation, usually the longest part of a question, only once per request and caches it, so asking again about an unchanged record is much faster. And because it only scores the options it is given, it can never propose a step the pathway does not allow.

## How it works in healthcare

In the simulation every point where someone decides what happens next is a decision: a nurse deciding whether a patient needs a GP visit, a GP choosing between antibiotics and an X-ray, a specialist choosing a sampling method. At each one, Birch receives the patient's record as it stands at that moment, written as a clinician would read it, together with the options the flowchart allows. It proposes the highest-scoring option, and in real care a doctor would make the final call.

Birch never sees the hidden truth about a patient. It only receives what has been revealed so far: the complaint, the background, earlier visits and the results of tests that have actually been done. A check before every request makes sure no diagnosis or future result slips in. The simulator can export training examples in exactly this form, so a model trained on them has to learn to decide from the record, not from the answer.

The simulation results on the Simulation page come from fixed decision rules fitted to observed practice, so they do not depend on the model. Birch is built to be switched on at the decisions and stepped through patient by patient, with every proposal shown for review. Its scores rank the options on offer; they are not probabilities of disease.

## Try it

Write a situation and a list of possible answers, one per line, and Birch will score them.

**Example 1: next step at a GP visit.** A 67-year-old woman, former smoker with 30 pack-years, has had a cough for four weeks and a fever since the weekend. CRP is 88 mg/L. A chest X-ray shows consolidation in the right lower lobe and no separate lesion. What should the GP do next? Options: start antibiotics and repeat the X-ray in six weeks; order a chest CT; refer urgently to a lung specialist; no further action.

**Example 2 (illustrative): choosing a sampling method.** A CT has found a 17 mm lesion in the outer part of the right lung, and the tumour board wants a tissue sample. The CT-guided biopsy list is fully booked for the next three weeks, while bronchoscopy has slots this week. Which sampling method should be booked? Options: CT-guided needle biopsy; bronchoscopy; EBUS-guided needle aspiration.

---

**Infographic:** the architecture. Situation text → reader → situation embedding; each option → reader → option embedding; both enter the comparison step, where every option is linked to every other; then one score per option. A small inset shows a patient record with hidden fields greyed out, feeding the situation side.

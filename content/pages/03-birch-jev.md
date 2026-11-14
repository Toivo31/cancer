# Birch: our JEV decision model

Birch is a decision model, not a chatbot. You give it a situation and a list of possible answers, and it returns a score for every answer in a single pass. It cannot invent an answer that is not on the list, which makes it a natural fit for any process where the allowed next steps are known in advance, such as a care pathway.

Birch belongs to the JEV family of decision models. It is built on a large open language model (NVIDIA Nemotron), which we use only to read and understand text. We fine-tuned its final layers and added our own scoring head on top. It runs on a single GPU on Modal.

## What is new in the architecture

A plain JEV model reads the situation once, reads each option separately, and scores each option by how well it matches the situation. The weakness is that each option is judged alone. The model cannot tell that an option is the best one available only because the others are worse, or that one option's value depends on another option's queue.

Our addition is a small interaction step between reading and scoring. After the situation and the options have been read, every option can look at every other option before the final score is given. The order of the options does not matter, and the number of options can change from question to question. The result is a model that judges options relative to each other, the way a person compares choices side by side.

## Advantages

**It compares options.** Questions such as "which of these is the best next test given that this one is fully booked" need the options to be seen together. In a controlled test inside our simulator, a small model with Birch's architecture learned to switch between two sampling methods depending on another method's queue, matching the ideal choice in 92 percent of those cases, where a plain JEV model trained on the same data stayed at around 30 percent.

**It is cheaper to ask again.** The situation, which is usually the long part, is read once and can be reused. A follow-up question about the same patient only needs the new options to be read.

**It stays inside the rules.** Birch only scores the options it is given, so it can never propose a step the flowchart does not allow.

## Try it

Write a situation and a list of possible answers, one per line, and Birch will score them. Scores are relative to the options you give. They are not probabilities of disease.

**Example 1: next step at a GP visit.** A 67-year-old woman, former smoker with 30 pack-years, has had a cough for four weeks and a fever since the weekend. CRP is 88 mg/L. A chest X-ray shows consolidation in the right lower lobe and no separate lesion. What should the GP do next? Options: start antibiotics and repeat the X-ray in six weeks; order a chest CT; refer urgently to a lung specialist; no further action.

**Example 2: choosing a sampling method.** A CT has found a 17 mm lesion in the outer part of the right lung, and the tumour board wants a tissue sample. The CT-guided biopsy list is fully booked for the next three weeks, while bronchoscopy has slots this week. Which sampling method should be booked? Options: CT-guided needle biopsy; bronchoscopy; EBUS-guided needle aspiration.

---

**Infographic:** a simple architecture diagram. Situation text → reader → situation embedding; each option → reader → option embedding; both feed the interaction step, where arrows connect every option to every other; then one score per option. A side note marks that the situation embedding is reused for follow-up questions.

# Synthetic data

All patients in this project are synthetic. No real patient data is used. We built the data so that it behaves like a real primary-care population with lung symptoms: most people have something ordinary, a few have cancer, and many ordinary illnesses look like cancer at first.

## How it was generated

The medical content lives in a catalogue that a non-programmer can read and correct. It lists 11 conditions that bring people to a doctor with lung symptoms, including lung cancer, pneumonia, COPD, asthma, heart failure, tuberculosis, a benign nodule and a lingering post-infection cough. It lists 42 hidden variables, such as symptoms, true lab values and what a scan would truly show, and 26 tests that exist in the pathway, from a patient interview and blood count to chest X-ray, CT, PET-CT, bronchoscopy and biopsy. Each test has a sensitivity, a specificity, a chance of giving an unusable result, a waiting time and a cost. Where a number comes from a published source, the source is recorded; the rest are clearly marked as assumptions.

Each patient is generated in three steps. First a background is drawn: age, sex, smoking history and region. Then a primary condition is drawn with realistic prevalence, so cancer stays rare, and sometimes an ordinary illness is added alongside it. Finally, every hidden variable and the result of every test are generated from that condition. Some patients were written from templates and some by a language model, which also writes the short text reports a radiologist or lab would produce. Every card is then checked against the catalogue so that its numbers stay realistic.

## How a patient card is structured

A patient card has two sides. The visible side holds the basic information a clinic has at the first visit: background and the complaint in the patient's own words, such as "I have had a cough for about a month and a temperature since the weekend."

The hidden side holds everything else. It records the true conditions, the true value of every symptom and finding together with which condition caused it, and a pre-written result for every test the patient could ever receive. These results include realistic mistakes. An X-ray can miss a small lesion, a biopsy can come back non-diagnostic, and a repeat test can find what the first one missed.

## Revealed step by step

As the patient moves through the simulation, each test reveals only its own part of the hidden side. The decision model and the optimiser see nothing else. Because every result exists in advance, the same patient can be run through a different pathway and reveal the same results in a different order. This is what makes a fair before-and-after comparison possible.

After treatment, symptoms caused by the treated condition disappear. If symptoms from another condition remain, the patient comes back to the start of the pathway, as real patients do.

---

**Infographic:** one patient card drawn as two halves. The top half (visible) shows background and complaint. The bottom half (hidden) is a row of locked boxes, one per test. Along the patient's path through the flowchart, boxes unlock one at a time as each test is done.

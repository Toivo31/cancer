# Appendix

## A. How the synthetic patients are made

All patients in this project are synthetic. No real patient data is used. The data is built to behave like a real population with lung symptoms: most people have something ordinary, a few have cancer, and many ordinary illnesses look like cancer at first.

The medical content lives in a catalogue that a non-programmer can read and correct. It lists 11 conditions that bring people to a doctor with lung symptoms, among them lung cancer, pneumonia, COPD, asthma, heart failure, tuberculosis and a benign nodule. It also lists 42 hidden variables, such as symptoms, true lab values and what a scan would truly show, and 26 tests, from a blood count and chest X-ray to CT, PET-CT, bronchoscopy and biopsy. Each test has an accuracy, a chance of giving an unusable result, a waiting time and a cost. Where a number comes from a published source the source is recorded; the rest are marked as assumptions.

Each patient is generated in three steps. A background is drawn first: age, sex, smoking history and region. Then a condition is drawn with realistic prevalence, so cancer stays rare, sometimes with an ordinary illness alongside it. Finally, every hidden variable and the result of every test are generated from that condition, including realistic mistakes: an X-ray can miss a small lesion and a biopsy can come back unusable. Some patients are written from templates and some by a language model, which also writes the short reports a radiologist or lab would produce. Every card is checked against the catalogue.

A patient card has a visible side, with the background and the complaint in the patient's own words, and a hidden side, with the true conditions and a pre-written result for every test. As the patient moves through the pathway, each test reveals only its own result. Because every result exists in advance, the same patient can be run through a different pathway, which makes a fair before-and-after comparison possible.

## B. The research behind the idea

Finland's national cancer strategy for 2026 to 2035 asks for equal and effective care, with patients reaching treatment within target times. Lung cancer is where Finland falls furthest behind its Nordic neighbours. Between 40 and 60 percent of Finnish patients with lung symptoms first see a nurse rather than a doctor, and fewer than 10 percent of primary care units can order a CT scan directly. Finland is slower at every step: about 14 days to a health centre appointment against 2 to 7 days elsewhere in the Nordics, 14 to 28 days to a specialist against 7 to 14, and about 28 days from specialist to diagnosis. In one Satakunta study, most of the delay arose in specialist care, after the referral.

The evidence suggests that the order of steps often matters more than capacity. A Norwegian study found that a faster PET-CT scanner would have raised the share of patients treated on time from 40 to 48 percent, a gain that was not significant, while reordering the steps would have raised it to 80 percent. An English hospital cut the wait for CT from 15 days to 3, yet the time to a treatment decision did not change, because later steps were untouched. Where whole pathways were redesigned, times fell: in Toronto, ordering tests before the first visit cut referral to diagnosis from about 40 to 28 days, and London's Royal Free cut referral to treatment from 66 to 29 days.

Reordering has limits. Some tests are genuinely undersized, and fast tracks can make other patients wait longer. This is why our simulator reports waits for every patient and points out where extra capacity would actually help.

Sources: National Cancer Strategy 2026–2035 (Finland); IHE Cancer Dashboard Finland 2026; University of Helsinki, Nordic lung cancer comparison; Mattila 2025 (Satakunta); Stokstad et al. 2019, BMC Health Services Research; ERJ 2023 on rapid CT access in England; Toronto pre-ordered tests study; Royal Free lung pathway (Pulse); Cooke et al. 2022; Swedish cancer pathway staff interviews. Links are in `docs/master_plan.md`.

## C. Case study: comparing with the original hospital study

The simulation pathway is rebuilt from Stokstad and colleagues' 2019 study of 100 patients with early-stage lung cancer at St Olavs Hospital in Trondheim. Only 40 percent of them started treatment within the 42-day target, with a median of 46.5 days. The authors estimated that a faster PET-CT scanner would have raised this to 48 percent, and that a reordered pathway, with scans ordered at the first visit and the tumour board meeting straight after them, would have raised it to 80 percent.

We built the flowchart from the paper, with waiting times taken from the intervals it reports, such as a median of 20.5 days from PET-CT referral to report. A few quantities needed by the simulation are not reported, such as the wait for bronchoscopy. We tried many combinations of them and kept every one under which our hospital reproduced the real result of about 40 percent on time. That was the only thing we tuned.

We then ran the authors' alternatives without further tuning, and let our optimiser search from today's pathway with no new equipment and without being told the authors' answer.

| Pathway | Original study | Our simulation |
|---|---|---|
| Today's pathway | 40% | 40% (tuned to match) |
| Faster PET-CT scanner | 48% | 60% |
| Authors' reordered pathway | 80% | 80% at the best fit; 62–86% across all settings that fit |
| Our optimiser, no new equipment | not in the study | 67% at the best fit; 48–77% across settings |

The ranking holds in every setting: reordering beats a faster scanner, and a faster scanner beats today's pathway. Our simulation overestimates the effect of the scanner alone. The optimiser arrived at the same three timing changes the authors proposed: order PET-CT on time, order the exercise test early, and hold the tumour board without waiting for the sample. It added one change of its own, planning tissue sampling already at referral, which would need clinical review. It did not improve on the authors' redesign.

The check supports the direction of the optimiser's changes, not the exact size of its predictions. It covers specialist care only, since every patient in the study already had cancer.

---

**Infographic:** a bar chart for section C, the original study's numbers next to ours for the four pathways in the table, with the ranges shown as error bars.

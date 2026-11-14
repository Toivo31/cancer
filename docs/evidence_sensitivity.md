# Evidence sensitivity: does the Finnish conclusion survive if the other number is right?

**Verdict**
1. **Yes for the direction and the size.** The two accepted reorders still help in every cohort in every alternative world that is a fair world. The gain is 13 to 15 points and 6 to 8 days (today's pathway 16% on time, the suggested one 28% to 32%, at a target that moves with the world). The safety and equity checks still pass, and the ranking of pathways holds.
2. **No for the level, and for the 90-day target.** If the lung-specific 65 to 69 days is the right reading of "diagnosis to treatment", today's pathway takes about 140 days, not 105. Then the 90-day target is reached by nobody (0%), and the level must be quoted against a different target or as days. The reading we think more likely is that the study's "diagnosis" is an earlier event than our tissue diagnosis; then nothing changes (table 1).
3. **Delay and survival is a claim, not an input.** We never relied on it, and we should keep it that way. For lung cancer the best recent evidence says four weeks of delay does not change mortality on average. The pitch should say "shorter waits are the goal in themselves", not "faster care saves lives".

All results are in a synthetic Finnish county. Nothing here is about real patients.

## How this was run

Script `scripts/fi_evidence_sensitivity.py`; results in `docs/review_checks/fi_evidence_results.json` and `fi_evidence_worlds.json`; each world is a scenario file in `scenarios/experiments/finland_evidence_*.yaml` (generated; the real scenario and `params/` were not touched).

- **Size.** Four held-out cohorts (seeds 301 to 304) of 18,800 patients each (60 days warm-up and one measured year, about 261 cancers per cohort) for today's pathway and the suggested one. The four hand-written pathways were run on seeds 301 to 303 only. Calibration used separate cohorts (seeds 901, 902).
- **Common random numbers.** Same patients and same per-patient random draws in every world and pathway. Worlds that change test accuracy regenerate the patients with the same seeds, because test results are drawn when patients are made.
- **Suggested pathway.** The optimiser's accepted flowchart from `runs/opt_fi_noft.json`: reserve the treatment slot when the case goes to the tumour board; book the specialist visit as soon as the referral arrives.
- **Check that the control is right.** World A, seeds 301 and 302 only, gives 17.5% and 33.1%, the numbers in the bundle. On all four cohorts it is 16.3% to 30.1%, because cohort 303 and 304 are lower. The level moves about 10 points between cohorts (`docs/ranges.md`). Compare worlds with each other, not with the headline.
- **Equivalent target.** In a slower world 90 days is out of reach. So the share is also given at an "equivalent target": 90 days plus how much the baseline's median moved. This keeps the baseline at about the same place in the distribution.
- **Safety and equity checks.** The optimiser's own `guardrails()` on the means over cohorts: no more missed cancers, no fewer tissue-confirmed diagnoses, no more tests or invasive procedures, no longer waits for patients without cancer, no presentation group slower by more than 1 day or on time less often by more than 1 point.
- **Not done.** Nothing was re-searched. The optimiser's flowchart was found in world A and evaluated unchanged in the others (a re-search might find a better one, so the gains are slightly pessimistic). No capacity was recalibrated in the accuracy worlds.

## Conflict 1: time from diagnosis to treatment

| | |
|---|---|
| **What we use** | 37 days (36 to 38), registry, all cancers, 2018 to 2022 (IHE 2026). Not lung-specific. As built, the model gives a median of 32 to 33 days from tissue diagnosis to treatment, so it is already a little below its own target. |
| **What the other evidence says** | Median 69 days (IQR 53 to 92) for surgical patients and 65 days (IQR 46 to 116) for non-surgical, five Finnish hospitals, diagnosed 2018, 156 potentially operable stage I to IIIA patients (Acta Oncologica 2025). The paper does not say what "diagnosis" and "treatment" mean (checked in the full text on 14 Nov). |
| **Other numbers that bear on it** | First contact to treatment is calibrated to about 99 days (Yle MOT 2025: 41 in primary care and 58 in specialist care) and the model gives 102 to 105. If tissue diagnosis to treatment were 67 days, first contact to treatment would be about 140. The two published numbers cannot both hold with tissue diagnosis as the start. |

**Two readings.**

- **Reading R (no input change).** The study's "diagnosis" is an earlier event, for example the first suspicious scan or the referral. In our model, from specialist referral sent to treatment the median is 74.8 days today (66.8 with the reorders), and from first specialist visit to treatment it is 59.0. That brackets 65 to 69 and matches the 58 days of specialist care in the Yle figure. Under this reading the scenario already agrees with the lung-specific study and nothing needs to change. We cannot prove it, because the paper does not define its start.
- **Reading S (strict).** "Diagnosis" is the tissue diagnosis. Then the model is too fast after diagnosis, and the extra days sit between diagnosis and treatment. We built worlds for this reading by raising the treatment-slot booking lead until the median reached the target. The extra delay is all at the treatment booking step, which is the most direct place; other places could be argued.

Results (four held-out cohorts; "on time" is within the equivalent target; days are medians from first contact):

| World | Lead of treatment slot | Diagnosis to treatment, today | Target used | On time, today | On time, suggested | Gain, points (range over cohorts) | Median days, today to suggested | Positive in |
|---|---|---|---|---|---|---|---|---|
| A: as built | 10 d | 33 d | 90 | 16.3% | 30.1% | 13.7 (9.3 to 16.5) | 105 to 97 | 4 of 4 |
| N37: exactly 37 d | 16.7 d | 40 d | 97 | 16.8% | 31.0% | 14.2 (9.3 to 16.9) | 111 to 104 | 4 of 4 |
| L67: lung-specific 67 d | 46.7 d | 70 d | 127 | 16.2% | 31.2% | 15.0 (9.0 to 18.4) | 142 to 134 | 4 of 4 |
| L92: stress, 92 d | 71.7 d | 95 d | 152 | 16.0% | 31.5% | 15.5 (9.0 to 19.5) | 167 to 159 | 4 of 4 |

(The "diagnosis to treatment" column is the median over the four held-out cohorts; it is 2 to 3 days above the calibration cohorts' 37.1, 67.2 and 92.5.)

What this says.

- **The suggested change still helps, by about the same amount.** 13.7, 14.2, 15.0 and 15.5 points; 7.5 to 8.0 days. This is expected: the reorders save waiting that overlaps (the treatment slot is booked while the board meets; the specialist visit is booked while the referral is handled), and that saving does not depend on how long the slot lead is. The gain in points is not more robust than the cohort spread (about 4 points), so do not read the small rise as a trend.
- **Ranking holds.** All six pathways are in the same order by share in all four worlds (hand-written bundled work-up first, then the fast lane, then the capacity-only control, then the suggested reorders, then direct CT, then today). By median days the order changes only between near-ties in L67 (rank correlation 0.87 with world A).
- **Safety and equity checks pass in every world.** Missed cancers 26.8 and 26.8 per cohort, tests per patient unchanged, waits for patients without cancer unchanged. Both presentation groups gain in every world; the gap between alarm and vague symptoms widens in points (14 to 16 before, 23 to 26 after) and narrows slightly in days (12.0 to 12.4 before, 11.2 to 11.8 after), as in the pitch.
- **The 90-day target is read differently under reading S.** At 90 days today's pathway is 6.4% in N37 and 0% in L67 and L92, for both pathways. So the headline "18% to 33% within 90 days" would not be reproduced. Under S the honest statement is the gain in days (about 7.5) or the share at a target that fits the world. Under R it stands. Statutory limits (21 days to assessment, 180 days to treatment) are not affected.

## Conflict 2: does treatment delay cost lives in lung cancer?

This is a claim, not an input. The simulator has no survival model. Nothing in the results above depends on it.

| | |
|---|---|
| **What we say now** | `docs/pitch/evidence_brief.md` section 1: "Delay costs lives in general ... hazard ratio about 1.06 to 1.08 for surgery ... not significant for lung ... lung-specific 2025 meta-analysis reported as null." Everything else already says we do not claim lives saved. |
| **What the other evidence says** | Hanna 2020, lung surgery: hazard ratio 1.06 per 4 weeks, not significant. Lung-specific 2025 meta-analysis (15 studies): pooled hazard ratio 1.00 (0.99 to 1.02) per 4 weeks, I-squared 97%. Faster care is linked to worse outcomes in advanced disease (the sickest are rushed) and to better outcomes in early-stage surgical patients. |
| **What changes if the other is right** | No input and no result changes. Any sentence that says or implies that a shorter wait saves lives in lung cancer is unsupported. |
| **Size of the effect if one insisted (arithmetic, not a simulation)** | The reorders save 7.5 to 8 median days, which is 0.27 of four weeks. At a hazard ratio of 1.06 per four weeks that is a relative hazard of about 1.016 (1.06 to the power 0.27). At 1.00 it is 1.000, and at the upper bound 1.02 it is 1.005. In either case the effect is too small to be worth a claim. |

Sentences that depend on it, and what may still be said (corrected wording is in the section "Corrected sentences" below):

- `docs/pitch/evidence_brief.md` line 11 opens with "Delay costs lives in general". That is the one sentence that states a general harm. It should open with the lung-specific null result.
- `docs/pitch/deck.md` row 2, `docs/pitch/submission.md` line 37 and `docs/master_plan.md` line 25 put weak survival and long waits side by side. Nothing there says causation. A judge may still hear it. One clause fixes that.
- `docs/pitch/qa.md` Q21, `numbers_sheet.md` G1, `README.md` line 55 and the "do not claim" boxes in `deck.md` and `submission.md` are consistent with the evidence. Keep them.
- May be said: waiting is the indicator in the national strategy (Goal 3: "treatment within target times"), patients and the statute treat long waits as a harm in itself, we measure the indicator directly, and the effect on survival is not shown.
- Do not say: lives saved, "faster care improves survival in lung cancer", any days-to-mortality conversion. If a conversion is shown at all, label it illustrative, curative-intent patients only, and give the null lung-specific result beside it.

## Conflict 3: chest X-ray accuracy

| | |
|---|---|
| **What we use** | Sensitivity 0.754, specificity about 0.90 (BRADLEY2021, all cancers, Leeds). |
| **What the other evidence says** | NSCLC within one year, same cohort: 76% and 95% (Bhartia 2021). Primary-care meta-analysis: 81% and 68% (BJR Open 2021). |
| **How the worlds were built** | Cancer sensitivity set; the false-positive rate of every non-cancer condition multiplied by one factor to reach the specificity (3.9 times for 0.68, 0.49 times for 0.95). Capacities were not changed. |

| World | On time, today | On time, suggested | Gain, points (range) | Median days | Checks | Ranking |
|---|---|---|---|---|---|---|
| X2: 0.76 and 0.95 (target 87) | 16.7% | 29.9% | 13.2 (9.3 to 15.7), 4 of 4 | 101 to 95 | pass | same order as A |
| X1: 0.81 and 0.68 (target 252) | 39.8% | 42.1% | 2.4 (2.3 to 2.6), 4 of 4 | 266 to 259 | pass | changes (rank correlation 0.33) |

- **X2 (the lung-specific figure): the conclusion survives.** The gain is the same size. Fewer false alarms leave the clinic and CT at 55% and 62% use.
- **X1 (the pooled primary-care figure): the world breaks.** Three times as many patients are referred, the specialist clinic reaches 100% use, and the queue grows without limit (median 266 days from first contact). The reorders still help but by only 2 points, and direct CT overtakes them. This repeats what `docs/sensitivity.md` found: reordering is worth little when a step has no spare capacity. X1 is a statement about capacity we did not recalibrate, not about reordering. It is not a fair world. If a judge raises the 0.68, the answer is that the Finnish county would need more clinic slots, and then the X2-like result applies.
- X1 and X2 change the share of non-cancer patients who reach the clinic, which the scenario's 9% X-ray positive predictive value was set to match. The recalibration was not done.

## Conflict 4: PET-CT accuracy

| | |
|---|---|
| **What we use** | GOULD2001 stand-alone PET: sensitivity 0.968, specificity 0.778 (scenario's false-positive rates give 0.90 over all non-cancer conditions). |
| **What the other evidence says** | PET-CT, pulmonary nodules: 0.89 and 0.70 (Li 2018). Finnish practice is PET-CT. |

| World | On time, today | On time, suggested | Gain, points (range) | Missed cancers per cohort | Checks |
|---|---|---|---|---|---|
| A | 16.3% | 30.1% | 13.7 (9.3 to 16.5) | 26.8 and 26.8 | pass |
| P | 16.3% | 30.1% | 13.7 (9.3 to 16.5) | 28.3 and 28.3 | pass |

The PET result does not change anyone's timing. It only changes who is told there is no cancer at the board. So shares and days are the same, and the PET-CT figures add 1.5 missed cancers per cohort (about 0.6 more per 100 cancers) to both pathways equally. The reorders do not change that.

## All lung-specific figures at once

World ALT: L67 (67 days) and X2 (0.76, 0.95) and P (0.89, 0.70).

| | Today | Suggested |
|---|---|---|
| On time (target 123 days) | 15.3% | 28.3% |
| Median days from first contact | 138 | 132 |
| Gain | 13.0 points (9.0 to 15.0), positive in 4 of 4 | |
| Checks | pass; missed cancers 28.3 and 28.3 | |
| Ranking | same except that the suggested reorders (28.2%) rank above the capacity-only control (27.2%), the reverse of world A; within noise | |

## Corrected sentences for the integrator

I did not edit the pitch files. Suggested replacements follow. Numbers come from the tables above (four held-out cohorts); the pitch's own headline uses cohorts 301 and 302.

**`docs/pitch/qa.md` Q22 (replace the answer)**
"We reran it. If tissue diagnosis to treatment is set to 67 days, the midpoint of the lung-specific Finnish medians, the two reorders still help in four of four cohorts, by 15 points (range 9 to 18) and 7.5 days, against 14 points and 7.6 days as built; the safety and equity checks pass and the ranking of pathways is unchanged. What changes is the level. Today's pathway then takes about 140 days from first contact, so the 90-day target is reached by nobody, and we would quote the gain in days. The paper does not define its start date; measured from the specialist referral, our model already gives 75 days today, so the two may not conflict. Synthetic county, four cohorts."

**`docs/pitch/numbers_sheet.md` G2 (replace the sentence and status)**
"Our Finnish waiting times were set to 37 days from diagnosis to treatment (as built the model gives 33), which is not lung-specific; a lung-specific Finnish study gives 65 to 69. We reran the Finnish comparison at 37 and 67 and 92 days: the two reorders still gain 14 to 15 points and about 7.5 days in every cohort, and all checks pass. At 67 days the 90-day share is 0% for both pathways, so the level would be quoted against a later target." Status: simulated. Source: `docs/review_checks/fi_evidence_results.json`.

**`docs/pitch/numbers_sheet.md` C4 (add)** "If the lung-specific 67 days applies after tissue diagnosis, nobody meets 90 days; the target is then a display choice (`docs/evidence_sensitivity.md`)."

**`README.md` line 61 (replace)** "Our Finnish calibration uses 37 days from diagnosis to treatment; a lung-specific Finnish study gives 65 to 69. We reran at 67: the gain from the two reorders stays at about 15 points and 7.5 days, but the 90-day share falls to 0% for every pathway if that reading is right (`docs/evidence_sensitivity.md`)."

**`docs/pitch/evidence_brief.md` line 11 (replace the bullet)**
"Whether delay costs lives in lung cancer is not shown. Across cancers a four-week treatment delay is associated with higher mortality (Hanna et al., BMJ 2020), but for lung surgery the estimate (about 1.06 per four weeks) was not statistically significant, and a lung-specific 2025 meta-analysis found a pooled hazard ratio of 1.00 (95% confidence interval 0.99 to 1.02) with high heterogeneity. The effect probably depends on stage. We argue for shorter waits as the strategy's own indicator, not for lives saved." (I could not check the "1.06 to 1.08 for surgery" range in Hanna against the paper; it is dropped here.)

**`docs/pitch/deck.md` row 2, `docs/pitch/submission.md` line 37 (add one clause)** "... Survival is context for the gap; we do not claim that shorter waits improve survival in lung cancer."

**`docs/master_plan.md` line 25 (add after "lags furthest behind")** "(we do not claim that the waits cause the survival gap; for lung cancer the delay-mortality evidence is null on average)".

**Not affected:** C1 and C2 (18% to 33%, gain 9 to 19 points) as sentences about the model as built; Q21; G1.

## What this does not cover

- One calibration direction only: all extra delay at treatment booking. If it sat earlier, the reorders that act on the specialist visit might gain differently. Not run.
- The optimiser was not re-run in the alternative worlds. It might find other reorders.
- No capacity recalibration after changing test accuracy (X1 breaks because of it).
- Held-out cohorts are four, so a gain of 13 and one of 15 are not different. Gains agree within the cohort spread, not more.
- Other items in `docs/evidence_research.md` (symptom odds ratios, EBUS and CT-biopsy accuracy, stage mix, regional timing) were not run: the scenario does not use them as inputs, or the source could not be read (the registry's regional timing table).

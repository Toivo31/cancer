# Encounter loop: consistency with the calibrated chain, and the primary-care finding (WP-W4-1)

Reproduce: `python scripts/encounter_report.py` (about 110 s on 2 cores; writes `docs/review_checks/encounter_results.json`).
Setup: 4 seeds x 6 000 patients, 44 arrivals a day, 60-day warm-up (patients arriving in the first 60 days are left out,
as in `finland_lung`), intervals are 95% Student-t across seeds. About 45 cancers per seed, so intervals are wide.
**All decisions in the loop are placeholder decision tables (D51: only the JEV decides in the final model; these tables are
the baseline). Every primary-care behaviour number is assumed (no Finnish decision-rate data exists, `care_practice.md` s.10).**

## 1. Consistency check against the calibrated chain (`finland_lung.yaml`, flowchart `baseline`)

Tolerance (set before reading the result, in `scripts/encounter_report.py`): 4 days on the median, 8 percentage points on shares,
3 points on the non-cancer referral share. A metric passes only if the loop mean is within tolerance of the chain mean.

| Metric (cancers unless stated) | Loop | Chain | Within tolerance |
|---|---|---|---|
| Median days first contact to referral | 34.6 [7.7, 61.5] | 26.3 [22.5, 30.0] | no (8.3 d) |
| Referred within 14 d | 14.4% [6.0, 22.9] | 11.2% [3.7, 18.7] | yes |
| Referred within 28 d | 37.2% [17.6, 56.9] | 52.0% [36.9, 67.1] | no (-14.8 pt) |
| Referred within 42 d | 47.2% [21.8, 72.6] | 75.9% [63.4, 88.4] | no (-28.7 pt) |
| Ever referred | 81.1% [72.2, 90.0] | 91.8% [87.4, 96.2] | no (-10.7 pt) |
| Treated | 79.4% [69.3, 89.6] | 88.8% [83.6, 94.0] | no (-9.3 pt) |
| Treated within 90 d | 12.2% [7.7, 16.8] | 25.0% [16.5, 33.5] | no (-12.8 pt) |
| Non-cancer patients referred | 20.1% [19.5, 20.6] | 7.9% [7.2, 8.6] | no (+12.2 pt) |

**The consistency target is not met.** The closest plausible setting found is the one in the repo; the loop is slower and leakier
than the chain for cancers (median to treatment 158 d [95, 221] against 98 d [94, 102]) and refers 2.5 times as many non-cancers.
Why, as far as I could establish:

* **Over-referral of non-cancers (20% against 8%) congests the hospital part**, which keeps the chain's calibrated capacities
  (specialist clinic 7 a day, calibrated to about 6.5% referred). That alone accounts for most of the treatment-time gap, because
  referral timing at the 14-day mark matches. It was not hidden by raising hospital capacity: that would break the calibration.
  About 4.5 points of the non-cancer referrals are false-positive chest X-rays, which use the chain's own false-positive rates
  (catalogue specificities); the rest comes from patients who keep returning (about 1.8 episodes per patient against about 1.1 in
  the chain) because chronic conditions (asthma, COPD, heart failure, untreated pneumonia) and the worried well keep symptoms.
* **Cancers whose first film is negative or who are not X-rayed at the first visit wait for a return** (return delay median 14 d plus
  a 12-day GP lead), which the chain shortcuts with a 10 to 55% "second look" and an immediate re-presentation draw.
* Not tried for lack of time: rows that treat chronic conditions faster (to cut returns and referrals), and a joint search over the
  tables with more seeds. The residual truth-conditioned hospital steps (C8 weakness) are untouched.

## 2. What was tuned (old -> new). Nothing sourced was changed.

| Where | Parameter | Old | New | Why |
|---|---|---|---|---|
| care.yaml behaviour | `return_if_persisting` | 0.7 | 0.95 | persisting cancers re-present as in the chain (symptoms_persist 0.90 to 0.95 x gp_represent 0.95 to 0.98) |
| care.yaml behaviour | `return_delay_days` | median 21, p90 60 | median 14, p90 35 | chain re-presentation extra wait |
| care.yaml behaviour | `give_up_per_episode` | 0.05 | 0.02 | cancers lost to give-up |
| world `natural_course` | `unexplained` | p 0.6, median 30, p90 90 | p 0.98, median 21, p90 60 | with 0.6, 40% of patients kept returning for a year |
| world `natural_course` | `viral_self_limiting` p | 0.95 | 0.99 | a self-limiting illness resolves |
| resources | `gp_appt` capacity (lead 12 d, sourced, unchanged) | 160 a day | 220 | first GP visit queued past the sourced 14 days |
| resources | `xray` capacity | 40 a day | 60 | more films under the suspicion row |
| policy `gp_encounter` default | advice / CRP / X-ray / antibiotics / blood count / follow-up / spirometry / discharge / refer routine | .30 / .25 / .15 / .05 / .05 / .08 / .04 / .05 / .03 | .40 / .05 / .20 / .06 / .05 / .10 / .05 / .05 / .005 (renormalised) | a point-of-care CRP costs a full review visit in this engine, which inflated GP visits |
| policy haemoptysis row | X-ray / urgent referral / CT | .70 / .25 / .05 | .85 / .10 / .05 | "found haemoptysis" is noisy in non-cancers (5%), 0.25 urgent referrals flooded the clinic |
| policy abnormal-film row | urgent / routine / CT / follow-up | .8 / .1 / .1 / 0 | .75 / .10 / .05 / .10 | |
| policy NT-proBNP positive | echo / diuretic / refer | .5 / .25 / .25 | .5 / .45 / .05 | |
| policy negative film, episode >= 2 | refer routine (all) | .4 (needed `reason == result`) | cancer-like (weight loss, or age >= 50 ever-smoker with dyspnoea, fatigue, chest pain, appetite loss or hoarseness): .50; others .02 | section 11 row never fired for a patient returning with an old negative film |
| policy episode >= 3 | refer / X-ray / CT / advice | .45 / .40 / .05 / .10 | .35 / .15 / .02 / .48 | |
| policy NEW rows | X-ray when `weight_loss` or (age >= 50, ever-smoker, and dyspnoea, fatigue, chest pain, appetite loss or hoarseness) and no film yet: X-ray .85 / advice .15; after a CRP without film: X-ray .25 / antibiotics .15 / advice .60 | not in section 11 | | NICE NG12-shaped suspicion rule |
| policy nurse NEW row | same suspicion features: book urgent GP .5 | not in section 11 | | 1-day urgent lead instead of 12 days |

Every row is `source: assumption`. The suspicion rule is the main assumption behind any difference between smokers and never-smokers.

## 3. The finding (placeholder decisions; cancers, loop). Numbers are means over 4 seeds with 95% intervals.

| Quantity | Value |
|---|---|
| Median days first contact to first referral | 36.9 [6.4, 67.3] (chain 26.3 [22.5, 30.0]) |
| of which wait for the first visit / after the first visit | 5.5 [-1.0, 12.1] / 31.1 [0.9, 61.4] d |
| Encounters before referral | 3.7 [2.5, 5.0] |
| Episodes before referral | 1.8 [1.2, 2.4] |
| Share first treated as something else (antibiotics, inhaler, ...) before referral | 16% [8, 24] |
| Median days to referral: with such a treatment / without | 84 [52, 116] / 30 [6, 54] |
| Median days from that treatment to referral | 64 [39, 88] |
| First GP visit orders a chest X-ray | 57% [42, 71] |
| Cancers that leave primary care with symptoms and are never referred | 8.9% [1.3, 16.5] |

Worried well and benign patients (per patient, primary care plus any hospital steps; visit costs EUR 92 nurse, 232 GP, Ephva 2026):

| Group | Tests | Cost EUR | GP visits | Referred |
|---|---|---|---|---|
| Worried well (n about 100 per seed) | 1.6 [1.4, 1.8] | 841 [732, 950] | 7.7 [7.2, 8.3] | 54% [48, 59] |
| Viral self-limiting | 1.0 [0.9, 1.1] | 297 [287, 307] | 2.8 [2.8, 2.9] | 11% [9, 12] |
| Other benign (all) | 1.3 [1.3, 1.4] | 473 [457, 490] | 4.1 [4.0, 4.1] | 19% [18, 20] |

By group (age, sex, smoking, region): cancer counts per seed are 2 to 34 per group and the intervals overlap everywhere
(for example rural 41 d [-2, 84] against urban 29 d [14, 45]; female 31 d [27, 35] against male 38 d [-2, 77]). **No group
difference is established by this run**; the full table is in the report output and the JSON.

### Pitch sentences (each with its number; say "with placeholder decisions")

1. With placeholder primary-care decisions, a lung cancer waits a median of about 37 days [6, 67] from first contact to referral and
   passes through 3.7 [2.5, 5.0] encounters and 1.8 [1.2, 2.4] episodes first.
2. About one cancer in six (16% [8, 24]) is first treated as something else, and those cancers wait a median of 84 days [52, 116] to
   referral against 30 [6, 54] for the rest (large intervals; 45 cancers a seed).
3. A worried-well patient costs the system about 840 EUR [730, 950] and 7.7 GP visits [7.2, 8.3], three times a viral cough (297 EUR).
4. Use these as an illustration of the mechanism, not as Finnish estimates: the loop does not reproduce the calibrated chain
   (section 1), and the second finding is not backed by a passed consistency check.

## 4. Caveats a judge would raise

* The consistency check **fails** on 7 of 8 metrics (only the 14-day referral share passes). The loop is slower than the chain for
  cancers and over-refers non-cancers; the chain and the loop were not made to agree.
* Every decision, return and natural-course number is an assumption; the hospital part still has truth-conditioned steps.
* About 45 cancers per seed: intervals on cancer quantities are wide, group splits are not interpretable.
* A point-of-care CRP is modelled as an order plus a review visit (engine: one action per encounter), inflating GP visits per patient
  (3.4 here); queues start empty (60-day warm-up used, as the chain); the library has 60 reference cards per condition, so about
  60 distinct cancer cards recur across patients.
* Costs: test and visit costs come from three counties and mixed years (`care_practice.md` s.3).
* The tuning used the same seeds 1 and 2 as part of the reporting seeds; the check is therefore not out of sample.

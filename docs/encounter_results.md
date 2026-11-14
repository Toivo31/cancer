# Encounter loop: does it agree with the calibrated chain, and what it says about primary care (WP-W4-1, w7/loop)

**Short answer.** After this round the loop agrees with the calibrated chain on **all 8 metrics on the pre-set seeds
(1 to 4)**, but only just: two metrics sit within half a point of their tolerance. On four fresh seeds (5 to 8) it
agrees on **6 of 8**; the same two metrics miss by a little (cancers referred within 42 days: 8.6 points short against a
tolerance of 8; non-cancers referred: 3.1 points too many against 3). Pooled over all 8 seeds both pass narrowly. Read
this as "the loop reproduces the chain at the edge of the tolerances", not as a clean pass.

Reproduce:

* `python scripts/encounter_report.py` (seeds 1 to 4, about 70 to 110 s; writes `docs/review_checks/encounter_results.json`)
* `python scripts/encounter_report.py --seeds 5 6 7 8 --out docs/review_checks/encounter_results_oos.json` (fresh seeds)
* `python scripts/encounter_diagnose.py --seeds 1 2 3 4 --json docs/review_checks/encounter_diagnosis.json` (the decomposition below)

Setup: 6,000 patients per seed, 44 arrivals a day, the first 60 days left out (as in `finland_lung`). Intervals are 95%
across seeds. About 45 cancers per seed, so every cancer number has a wide interval.

**All primary-care decisions in the loop are placeholder decision tables.** In the final model only the decision model
(the JEV) decides (D51). Every number in the tables, and every return and natural-course number, is an assumption:
no Finnish data on how often GPs X-ray, treat or refer was found.

## 1. Consistency table, before and after

Tolerances were set before any result was read (`scripts/encounter_report.py`, unchanged): 4 days on the median,
8 points on shares, 3 points on the non-cancer referral share. A metric passes if the loop mean is within the
tolerance of the chain mean.

| Metric (cancers unless stated) | Chain (seeds 1-4) | Loop before | Loop after (seeds 1-4) | Pass | Loop after, fresh seeds 5-8 (chain) | Pass |
|---|---|---|---|---|---|---|
| Median days first contact to referral | 26.3 [22.5, 30.0] | 34.6 | 25.4 [24.0, 26.8] | yes (-0.9) | 26.1 (27.2) | yes |
| Referred within 14 d | 11.2% | 14.4% | 4.4% [1.6, 7.3] | yes (-6.8) | 4.5% (9.6%) | yes |
| Referred within 28 d | 52.0% | 37.2% | 56.7% [52.1, 61.2] | yes (+4.7) | 52.9% (48.2%) | yes |
| Referred within 42 d | 75.9% | 47.2% | 68.9% [66.0, 71.8] | yes (-7.0) | 62.9% (71.5%) | **no (-8.6)** |
| Ever referred | 91.8% | 81.1% | 94.4% [89.9, 99.0] | yes | 91.7% (93.7%) | yes |
| Treated | 88.8% | 79.4% | 91.7% [85.6, 97.7] | yes | 87.8% (90.2%) | yes |
| Treated within 90 d | 25.0% | 12.2% | 20.6% [12.7, 28.4] | yes (-4.4) | 17.2% (21.6%) | yes |
| Non-cancer patients referred | 7.9% | 20.1% | 10.7% [9.9, 11.5] | yes (+2.8) | 11.1% (8.1%) | **no (+3.1)** |
| Passing | | 1 of 8 | **8 of 8** | | **6 of 8** | |

Also: median days to treatment, loop 108 [97, 118] against chain 98 [94, 102]. The loop is still about 10 days slower
to treatment; this is not one of the 8 metrics.

Honest caveats on this table:

* The tables were tuned while looking at seeds 1 to 4, so the 8 of 8 is in-sample. Seeds 5 to 8 are the out-of-sample check.
* The two binding metrics pull against each other. Every change that refers more cancers quickly also refers more
  non-cancers. The final setting sits where both are just inside on seeds 1 to 4 (section 4 shows the trade-off).
* Referred within 14 d passes only because its tolerance is wide: the loop refers far fewer cancers in two weeks
  (4% against 11%), because the first GP visit takes about 12 days to book and a film plus a letter take several more.

## 2. Where the gap came from (the decomposition)

`scripts/encounter_diagnose.py` follows every patient's record. It finds which table row fired at the first referral,
what the last chest X-ray showed, which episode it was, and how the days before a cancer's referral were spent.

### 2a. Non-cancer referrals (before: 20.1%, after: 10.7%; chain 7.9%)

Before (seed 1), in points of all non-cancer patients:

| Route | Before | After (seeds 1-4) | Chain |
|---|---|---|---|
| False-positive film, referred on it | 6.2 | 7.0 | 5.3 |
| Returning after a negative film: "cancer-like features" row (refer 0.5); after tuning only the reported red-flag row | 9.6 | 0.9 | 1.9 (re-presentation) |
| Second look at the negative-film result (new row) | - | 0.9 | 0.7 (second look) |
| Other returning rows, episode 3 or more | 2.3 | 0.7 | - |
| Haemoptysis without a film, NT-proBNP and echo rows, default | 2.0 | 1.1 | - |
| **Total** | **20.1** | **10.7** | **7.9** |

What drove the old 20%:

* **Patients kept coming back.** Non-cancers averaged 2.1 episodes (now 1.87; the chain allows at most one return).
  Four things kept them coming back:
  * Nothing ended worried-well symptoms. `natural_course` had no entry for `worried_well`, so these patients returned
    all year (5.7 episodes; 58% were referred).
  * Chronic illness was not treated on return. The rows that act on a result (NT-proBNP, spirometry) fired at every
    later visit. They re-ordered tests instead of treating. No row acted on a positive echo or reversibility test. No
    row read the film's consolidation output. No row used the PPI. The point-of-care CRP row read the wrong test, so it
    never fired.
  * Heart failure (5.0 episodes), asthma (3.6) and reflux (3.8) looped until the horizon. 15% of non-cancers were still
    in the loop after a year (now 4.9%).
* **The "cancer-like features" row was not specific.** At a return visit after a negative film, it referred half of
  patients aged 50 or more who had ever smoked and had breathlessness, tiredness or chest pain. Those features are about
  as common in COPD, asthma and heart failure as in cancer: 47 to 54% of COPD and heart-failure patients against 60% of
  cancers. The symptoms the patient brings up themselves (`reported`) separate far better. Weight loss is reported by
  43% of returning cancers against 3 to 5% of non-cancers.
* **False-positive films are a floor.** The film's specificity is sourced, so these referrals cannot be tuned away.
  The loop films more non-cancers than the chain does, and its condition mix differs (45% viral against the chain's
  34% self-limiting). Its false-positive route is 7.0 points against the chain's 5.3. That leaves about 3.7 points for
  every other route to stay under the 10.9% limit.
* **A library artefact made it worse.** With 60 reference cards per condition, 3 of the 60 viral cards had an abnormal
  first film (5%). The catalogue implies about 1.4%. Because 45% of patients are viral and reuse those 60 cards, this
  inflated false-positive referrals. With 200 cards per condition the rate is close to the catalogue's.

### 2b. Cancer delay (before: median 34.6 d to referral; chain 26.3)

Mean days before a cancer's first referral decision, split by what the patient was waiting for. Seed 1 before;
seeds 1 to 4 after. Both exclude the 3-day letter that rule 9 now adds after the decision.

| Waiting for | Before | After |
|---|---|---|
| First visit | 7.3 | 7.3 |
| Nurse to GP booking | 4.7 | 5.3 |
| Test turnaround | 7.7 | 6.2 |
| Review after a result | 2.5 | 3.3 |
| Planned follow-up | 2.1 | 1.8 |
| Review after a treatment | 5.3 | 3.5 |
| Return after "come back if it persists" | 5.9 | 5.7 |
| Booking after a return | 4.4 | 2.7 |
| **Mean total (median)** | **39.8 (24.1)** | **35.9 (21.0)** |

By first film (after, seeds 1 to 4):

| First film | Cancers | Median days to referral |
|---|---|---|
| Positive | 141 (78%) | 24 |
| Negative | 33 (18%) | 58 |
| None | 6 (3%) | 16 |

In the chain (same seeds):

| Chain route | Share of cancers | Median days to referral |
|---|---|---|
| Positive film | 48% | 21 |
| Second look after a negative film | 4% | 22 |
| Re-presentation (after a negative film or no film) | 39% | 41 |
| Never referred | 8% | - |

What drove the old delay:

* **A quarter of cancers were not X-rayed at the first visit.** A nurse sent 37% of first contacts home. The default GP
  row X-rayed only 21%. An inhaler or spirometry row could fire before the suspicion row in an older smoker.
* **Cancers with a negative film waited for a return.** The return took about 14 days, plus the booking lead. The
  chain shortcuts this: 10 to 55% are referred at a "second look", and the rest re-present and are referred at once.
* **The loop's hospital part was congested by over-referral** (section 2a). It also fast-tracked every urgent
  referral, which the chain's calibrated baseline never does. Once the over-referral stopped, the fast track made the
  loop *faster* to treatment than the chain: 44% against 25% treated within 90 days on seeds 1 and 2.
* **The loop measured referral at the GP's decision.** The chain measures it after the GP has written and sent the
  letter, about 3 days later. The loop skipped that step entirely.

What still separates the loop from the chain: cancers with a negative first film. In the loop they need a planned
review, a repeat film and a letter, which lands at about day 43. That is just past the 42-day mark. This is the main
reason "referred within 42 d" is the binding metric.

## 3. What was changed (old -> new). Nothing sourced was changed; the catalogue hash is unchanged.

Catalogue hash before and after: `2bcb9c78b2e07f6f227615a404375794ec002449e0475ecdaf2256be72c24183`.
`care.yaml` is not part of the hash (only `catalogue.yaml`, `conditions`, `variables`, `tests`, `cooccurrence` are; see
`FILES` in `patient_engine/catalogue.py`). Even so, `care.yaml` was **not edited**. All behaviour changes are in the
scenario files. Every row below is `source: assumption` and carries a `note` with its old value in
`scenarios/finland_encounter_policy.yaml`.

**World settings (`scenarios/finland_encounter.yaml`)**

| Setting | Old | New | Reason (assumption) |
|---|---|---|---|
| `hospital.referral_letter` (new, C8 rule 9) | none | the chain's `gp_referral_letter` wait (median 3 d, p90 7) | the chain's referral clock stops after the letter is sent; the loop skipped this step |
| `hospital.urgent_referral_priority` | true | false | the chain's calibrated baseline fast-tracks nobody; with true, urgent referrals got slots the calibration never saw |
| `natural_course.worried_well` | absent (never ends) | p 0.8, median 21 d, p90 60 | a health worry settles in most after being seen |
| `library.per_condition` | 60 | 200 | 60 cards made the viral false-positive film rate depend on 3 cards |

**Nurse table**

| Row | Old | New | Reason |
|---|---|---|---|
| Default | GP routine 0.6, advice 0.37, GP urgent 0.03 | 0.82 / 0.15 / 0.03 | the chain's nurse passes every patient on |
| Episode 2 or more | GP routine 0.8, GP urgent 0.15, advice 0.05 | 0.45 / 0.5 / 0.05 | a patient back with persisting symptoms gets a quicker slot about half the time |

**GP table, changed rows**

| Row | Old | New | Reason |
|---|---|---|---|
| Default | advice .414, X-ray .207, others as before | advice .22, X-ray .40 | the chain X-rays about 30% of non-cancers and 45% of non-specific cancers |
| Haemoptysis, no film | X-ray .85, urgent referral .10, CT .05 | .90 / .05 / .05 | haemoptysis found on questioning is noisy (3 to 6% of non-cancers) |
| Abnormal film | urgent .75, routine .10, CT .05, follow-up .10 | urgent .80, routine .15, CT .05 | the chain refers every suspicious film |
| NT-proBNP or spirometry positive | fired at every later visit | acts when the result arrives; on a later visit it treats first | the old rows re-ordered tests instead of treating |
| CRP of 50 or more | read only the laboratory CRP | also reads the point-of-care CRP (what `order_crp` orders) | the old row never fired |
| Suspicion, no film: X-ray .85 | features: weight loss, or aged 50+ ever-smoker with breathlessness, tiredness, chest pain, appetite loss or hoarseness | cough added; row moved above the heart-failure and wheeze rows | NG12 counts one unexplained feature, cough included, in an ever-smoker; in an older smoker the cancer question comes first |
| Returning, negative film, older than 3 weeks, cancer-like features | refer .5, CT .05, advice .45 | repeat X-ray .75, advice .25 | a repeat film separates cancer from its look-alikes much better than the features do |
| Returning, negative film, red flag the patient reports (weight loss, haemoptysis, appetite loss, hoarseness) | (inside the row above) | refer .4, CT .02, advice .58 | `reported` symptoms are far more specific than ones found on questioning |
| Returning, negative film, aged 50+ ever-smoker with breathlessness, tiredness or chest pain | (inside the row above) | refer 0, CT .01, advice .99 | these referrals added 2.8 points of non-cancer referrals and no cancer referred within 42 d |

**GP table, new rows**

| New row | Probabilities | Reason |
|---|---|---|
| Consolidation on a new film | antibiotics .85, follow-up .15 | treated as pneumonia |
| Abnormal film with consolidation and fever or a high CRP | antibiotics .7, refer .3 | treated as pneumonia first |
| After those antibiotics | repeat film .8, refer .2 | BTS-style follow-up film |
| Positive echo or reversibility test (also on return) | treat (diuretic .85 or inhaler .9) | a confirmed chronic illness is treated, so it stops bringing the patient back |
| Positive pneumonia film | antibiotics .9 | treat the confirmed pneumonia |
| Treatment review, no symptoms left | advice .9 | the treatment worked |
| Treatment review, symptoms persist, no film | X-ray .7 | NG12-shaped |
| Returning after a negative film with breathlessness and no NT-proBNP | NT-proBNP .6, spirometry .2 | work-up before referral |
| Returning after a negative film with cough or wheeze and no spirometry | spirometry .6 | work-up before referral |
| Chronic cough, normal film and spirometry | PPI trial .5 | the PPI was never used before |
| Negative film plus cancer-like features | planned review in two weeks .5 | safety net; stands in for the chain's second look |
| At that planned review, any symptom persists | repeat film .75 | the review was planned because of the doubt |
| Negative film plus reported weight loss or haemoptysis | refer .3 at once, review .4 | "second look"; the chain's second look refers 10 to 55% |

**Engine (`pathway_sim/encounter.py`)**

* **Rule 9, referral letter.** Documented in `docs/plan/components/C8-encounter-loop.md`, with a test.
* **Library cache.** Generated reference libraries are cached on disk under `runs/libraries/`. The cache is keyed by
  content and gives the same library id, so it changes no result.

**Report tools**

* `scripts/encounter_report.py`: a group missing in one seed no longer crashes the report. The tolerances are unchanged.
* `scripts/encounter_diagnose.py`: new; produces the decomposition above.

**Rows that read age, smoking status or pack-years.** These rows are sensitive to the coming population model:

* the nurse suspicion row;
* the GP "suspicion, no film" X-ray row;
* the returning "cancer-like features" repeat-film row;
* the "negative film plus cancer-like features" safety-net row;
* the returning "older smoker with breathlessness, tiredness or chest pain" row.

Pack-years is not read. Sections 4 and 5 say which numbers move with the population.

## 4. The trade-off (why the result sits at the edge)

Two rows were varied on seeds 1 to 4 with everything else fixed. One is the referral share in the returning red-flag
row; the other is the share in the returning "older smoker with breathlessness" row:

| Setting | Non-cancer referred | Cancers referred within 42 d | Cancers ever referred |
|---|---|---|---|
| Less eager (0.4 / 0) | 9.5% | 67.8% | 93.9% |
| Middle (0.6 / 0.08) | 10.9% | 67.8% | 93.9% |
| More eager (0.8 / 0.2) | 12.3% | 67.8% | 93.9% |

These returning referrals cost non-cancer referrals and buy nothing for cancers within 42 days: the cancers they catch
would be caught anyway, a little later, by a repeat film. The final setting uses the less eager values. It spends the
saved budget on earlier films: the default X-ray share, the nurse passing patients on, the safety-net review and the
second look. That moved "within 42 d" from 67.8% to 68.9% on seeds 1 to 4, and the non-cancer share from 9.5% back
up to 10.7%. The first three of those four changes did not move "within 42 d" at all. Only the second-look row did,
by 2 cancers out of 180.

What limits the loop is information, not tuning. The chain's re-presentation step refers 95% of returning cancers and
15 to 20% of returning non-cancers. That is a likelihood ratio of about 5 to 6, and the step reads the hidden diagnosis.
The loop's decider sees only the record. The best record feature found, weight loss the patient reports themselves,
catches about 43% of returning cancers at 3 to 5% of non-cancers. So the loop can match the chain's referral
*counts*, but it gets there through more films and more time. That is why it sits at the edge and misses slightly on
fresh seeds.

## 5. The primary-care finding, rerun on the tuned loop (placeholder decisions)

Cancers, means over seeds with 95% intervals. Seeds 1 to 4 are the tuned seeds; seeds 5 to 8 are fresh.

| Quantity | Seeds 1-4 | Seeds 5-8 | Before tuning (seeds 1-4) |
|---|---|---|---|
| Median days first contact to referral (letter sent) | 25.4 [24.0, 26.8] | 26.1 [24.4, 27.8] | 36.9 |
| of which: wait for the first visit / after the first visit | 5.7 / 18.9 | 3.4 / 22.5 | 5.5 / 31.1 |
| Encounters before referral | 3.5 [3.0, 4.0] | 4.2 [4.0, 4.4] | 3.7 |
| Episodes before referral | 1.3 [1.2, 1.5] | 1.5 [1.3, 1.6] | 1.8 |
| First treated as something else (antibiotics, inhaler, ...) before referral | 8% [5, 12] | 14% [7, 21] | 16% |
| Median days to referral with such a treatment / without | 70 [51, 89] / 24.6 [23.3, 26.0] | 125 [70, 180] / 24.8 [24.1, 25.5] | 84 / 30 |
| First GP visit orders a chest X-ray | 74% [64, 85] | 75% [65, 85] | 57% |
| Cancers that leave primary care with symptoms and are never referred | 4.4% [-3, 12] | 8.4% [5, 12] | 8.9% |

Non-cancer patients (seeds 1 to 4, primary care plus hospital; visit costs EUR 92 nurse, 232 GP, Ephva 2026):

| Group | Tests | Cost EUR | GP visits | Referred |
|---|---|---|---|---|
| Worried well (about 100 a seed) | 1.6 [1.4, 1.9] | 488 [426, 551] | 4.7 [4.3, 5.1] | 20% [15, 24] |
| Viral self-limiting | 1.2 [1.1, 1.2] | 304 [291, 317] | 3.0 [2.9, 3.1] | 7% [6, 8] |
| All benign | 1.6 [1.5, 1.6] | 443 [436, 449] | 4.1 [4.1, 4.2] | 10% [10, 11] |

**What changed in the finding and why.** The old finding said a cancer waits about 37 days and one in six is first
treated as something else. Both numbers were inflated by the loop's own faults (section 2). Corrected:

* the wait is about **25 days**, the same as the chain;
* about **one cancer in ten** (8% [5, 12] tuned seeds, 14% [7, 21] fresh seeds) is first treated as something else;
* those cancers wait **about three times as long** (70 days or more against 25).

The wrong-treatment share is the most sensitive number here. It moves with the table rows for wheeze, consolidation
and antibiotics, and with the coming population model (more never-smokers and young patients means fewer suspicion-row
films).

**By group.** Seeds 1 to 4 have 3 to 33 cancers per group per seed. Patients under 50 wait longer: 52 days [23, 81]
against 22 to 26 for the older bands. That follows directly from the suspicion rows keying on age 50 and over, so it is
an assumption, not a finding. Never-smokers (3 cancers a seed) are not interpretable. **No group difference is
established**, and the age and smoking numbers will move when the population model lands.

### What may and may not be said in the pitch

Safe, each with its qualifier:

1. "With placeholder primary-care decisions, our visit-by-visit model reproduces the calibrated pathway's referral
   timing and referral volumes within pre-set tolerances. It passes all 8 checks on the seeds we tuned on and 6 of 8
   on fresh seeds, where it misses two by under a point." Say both halves.
2. "In the model, a lung cancer that is first treated as something else (antibiotics, an inhaler) waits about three
   times as long for referral as one that is X-rayed: 70 days or more against about 25." Mechanism, placeholder
   decisions, wide interval.
3. "In the model, about one cancer in ten is first treated as something else." Give the range 5 to 21% across seed sets.
4. "The model shows where the days go: about 7 days to the first visit, a week for the film and its review, and for
   cancers with a negative first film about two months." Placeholder decisions.
5. "A chest X-ray's false positives set a floor of about 7% of non-cancer patients referred." This follows from the
   catalogue's sourced specificity and the model's filming rate.

Not safe:

* Any of these numbers as Finnish estimates. Every decision rate is assumed, and no Finnish decision-rate data exists.
* "The loop is validated" or "the loop matches the chain" without the qualifier. It fails 2 of 8 on fresh seeds.
* Any difference by age, sex, smoking or region. None is established, and the age gap is built into the tables.
* Worried-well costs as a finding. They depend on the assumed natural course (0.8 settle).
* Days to treatment from the loop. It is about 10 days slower than the chain, and that is not checked.
* The old numbers (37 days, one in six, 84 days, worried well 840 EUR). They came from the loop's own faults.

## 6. Caveats a judge would raise

* The check passes in-sample and narrowly misses out of sample. The tuning used seeds 1 to 4.
* Every decision, return and natural-course number is an assumption. The hospital part still has truth-conditioned
  steps (C8 weakness).
* The loop's world allows CT at 4 a day; the chain allows 3 (`finland_encounter_resources.yaml`, care lane). This
  makes the loop's hospital part slightly faster. It was left alone because it is labelled with a source.
* About 45 cancers a seed: intervals on cancer numbers are wide.
* A point-of-care CRP still costs a review visit (engine: one action per encounter).
* The population model (w7/population) changes the age and smoking mix. The rows listed at the end of section 3 key
  on age 50+ and ever-smoking, so the X-ray share, "within 42 d", the wrong-treatment share and the non-cancer referral
  share are expected to move. Rerun `scripts/encounter_report.py` after it merges.

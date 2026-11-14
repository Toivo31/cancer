# Validation against Stokstad et al. 2019

**Question:** can the simulator reproduce a real, published lung-cancer pathway, and does it then
predict the effect of the authors' reorganisation *without being told it*?

Scenario: `scenarios/stokstad.yaml` (all inputs, each with a source id or `assumption`).
Calibration run: `python -m pathway_sim.calibrate scenarios/stokstad.yaml --n 2000 --out docs/validation_results.json`.
Calibrated scenario used downstream: `scenarios/generated/stokstad_calibrated.yaml`.

## Method

1. **Rebuild the observed pathway** as a flowchart: CT → first visit → (tissue sampling ∥ PET-CT ∥
   exercise test) → weekly tumour board → wait for surgery / radiotherapy → treatment. Waits are
   drawn from the paper's reported intervals (delay mode, as the authors re-timed patients), not
   from capacity queues. Practice variation the paper counts is kept: 27 late PET referrals,
   16 of 21 late exercise tests, 15 failed-bronchoscopy repeats, 22 never sampled, 54 treated
   without definitive tissue diagnosis, 8 inadequate CTs, 11–12 extra workups after PET.
2. **Calibrate only what the paper does not report**, on the observed pathway only, to the
   published 40% within 42 days and median 46.5 days. Grid (192 points):
   bronchoscopy wait; tumour-board cutoff; report-not-ready delay at the first visit; share of
   on-time PET-CT referrals made at referral triage (before the visit); share of the published
   referral-to-treatment interval that falls after the tumour board.
3. **Predict** the other two flowcharts with every accepted parameter set and compare with the
   paper. These numbers were not fitted.

## Result

**Read with the Robustness section below: the first grid's ranges are the narrow corner of a wider band.**

11 of 192 grid points reproduce the observed pathway (share 0.40 ± 0.04, median 46.5 ± 2.5 d).

| Flowchart | Published | Simulated (11 accepted sets) | Verdict |
|---|---|---|---|
| Observed (calibrated) | 40%, median 46.5 d | 36–43%, median ~46 d | fitted |
| PET-CT ≤ 7 days only | 48% (95% CI 39–58), n.s. | **55–67%** (median 62%) | over-predicts |
| Authors' optimal pathway | 80% (95% CI 72–87) | **78–86%** (median 83%) on this first grid; **62–86%** (median 75%) on the extended grid, see Robustness | consistent |
| Sampling procedures, optimal / observed | 92 / 112 = 0.82 | 0.80 / 0.98 = 0.82 | matches |

Seed-averaged check on the best fit (50 × 100 patients): observed 40.6%, faster PET 59.4%,
optimal 80.1%.

**Cohort-size uncertainty** (200 simulated cohorts of 100 patients, best-fit parameters; central
95% range), next to the paper's 95% CIs:

| Flowchart | Simulated, 100-patient cohorts | Published (95% CI) |
|---|---|---|
| Observed | 40% (30–49) | 40% (31–50) |
| Faster PET-CT only | 59% (50–69) | 48% (39–58) |
| Authors' optimal | 80% (73–87) | 80% (72–87) |

The observed and optimal intervals overlap the published ones almost exactly. The faster-PET
intervals overlap only at the edge.

## What this shows, and what it does not

- The simulator, calibrated only on the observed pathway, lands on the authors' optimal-pathway
  estimate and on their 16% reduction in sampling procedures. That is the evidence that the
  engine's reordering logic (parallel PET-CT and exercise test, tumour board before sampling,
  sampling while treatment is booked, method chosen by tumour location) behaves like the real one.
- **It over-states the gain from faster PET-CT alone** (62% vs 48%). In the real cohort, PET-CT
  was less often the step holding patients back than in our model, probably because of delays we
  do not represent (39 patients whose CT report was not ready at the first visit, 16 who reached
  the tumour board with incomplete workup and were re-discussed, correlated delays within a
  patient). Our model therefore leans towards "speed up the bottleneck" more than reality, which
  makes the order-versus-capacity conclusion *conservative*: reordering still wins clearly.
- **The fit sits at the edge of the grid**: every accepted set needs a short wait between the
  tumour board and treatment (6–8 days of the published 13-day surgical interval) and most need
  on-time PET-CT ordered at referral triage. The paper's per-step medians, chained one after
  another, add up to more than its 46.5-day median, so some steps must overlap in practice; we
  model the overlap explicitly and label it `assumption`. With the full text's figure 4 the
  overlap could be checked.
- **Disclosure (review M3):** the calibrated observed practice of ordering PET-CT at referral triage (share 1.0, the grid maximum) is carried into the authors' pathway through a shared mix object. With PET-CT ordered at triage for 100%, 50% or 0% of patients, the simulated authors' pathway gives 80%, 73% or 66% (0% = PET-CT ordered at the first visit, as the paper describes; `docs/review_checks/stokstad_pet_triage_result.json`). "Predicted, not fitted" holds, but the 80% is not independent of the fitted practice. Three of the five calibrated parameters sit at the edge of the grid.
- The authors' 80% is itself a model estimate, and all 100 patients had cancer. This validates
  specialist-care ordering, not primary-care filtering.

## Open

- Faster-PET over-prediction: try adding the "incomplete workup at tumour board → re-discussed
  next week" mechanism (16 patients) and within-patient correlation of delays.

## Robustness (14 Nov evening)

Question: was the calibration done correctly, is it overfitted, does it predict, and would an improvement in the simulated
hospital carry over to real outcomes? Everything below is reproduced by `python scripts/norway_robustness.py`
(analyses 1–4, from the cached table `docs/review_checks/norway_grid_table.json`; `--recompute` rebuilds it, about 40 min on 2 cores)
and `python scripts/norway_correlated.py` (analysis 5, about 10 min per setting). Settings: n = 1000 patients per grid point,
seed 1, common random numbers across flowcharts, so differences between flowcharts are not simulation noise. The shipped
`scenarios/stokstad.yaml` and `scenarios/generated/stokstad_calibrated.yaml` are untouched. Simulation noise at n = 1000 is about
±1.5 points of share, so the original grid gives 9 accepted points here and 11 at n = 2000 (`norway_baseline_n2000.json` reproduces
the shipped 55–67% / 78–86%).

### 1. Grid extended past the edges (`norway_grid_extension.json`)

Extended grid, 1920 points: bronchoscopy wait 1/3/6/10; post-board treatment wait (surgery median) 13/10/8/6/4/2 d (radiotherapy
scaled); board cutoff 0/1/2/4; first-visit extra wait 0.01/2/4/6; PET-CT-at-triage share 0/0.5/0.8/0.9/1.0. Cutoff 0 and triage 1.0 are
physical bounds and cannot be extended.

- The accepted set grows from 9 to **184** points; the accepted region moves *further* in the direction of the edge: the post-board
  wait is accepted from 2 to 8 d (none at 10 or 13 d), 82% of accepted points have 2–4 d. The edge was not a boundary of the
  accepted region, it was an artefact of the grid. About 87 accepted points sit on an edge of the extended grid for each of the four non-bound parameters, so the region is still not closed.
- Predictions widen: faster PET-CT **50–74%** (median 60.5%, 10–90%: 55–66%); authors' pathway **62–86%** (median 75%, 10–90%: 66–82%).
  Only 64% of accepted sets give an authors' pathway inside the published 72–87%, and 34% give a faster-PET figure inside 39–58%.
- The original-grid headline (78–86% against 80%) was the corner of this band, not its centre. The best-fit point moves from
  (post-board wait 6 d, extra wait 2 d, triage 1.0) to (2 d, 6 d, 0.8).

### 2. Identifiability (`norway_identifiability.json`)

- The two targets are close to **one** constraint. Regressing share and median on the five parameters over the grid, the singular values of the
  parameter→targets map in tolerance units are 3.9 and 0.16: the share and the median (cohort correlation −0.81 in simulated 100-patient
  cohorts, analysis 4) carry nearly the same information. Share-only calibration accepts 188 points, both targets 184.
- Four directions of the five-dimensional parameter space are essentially free. Over the grid, the post-board wait moves the share by
  26 points and the median by 14 d; extra wait 13 points; triage share 13 points; cutoff 8 points; bronchoscopy wait 7 points. The
  bronchoscopy wait and the cutoff are close to unconstrained (accepted at every level).
- Within the accepted set, the authors'-pathway prediction is driven by the post-board wait (correlation 0.75) and extra wait (−0.81);
  the faster-PET prediction by extra wait (−0.6) and triage share (−0.62). These are exactly parameters the paper does not report.
- Prediction band over all accepted sets: see section 1. A likelihood-weighted band over the whole grid (Gaussian weights from the cohort noise
  below, flat prior over the grid points, which is itself arbitrary): faster PET mean 59% (5–95%: 50–68%), authors' 74% (63–83%).

### 3. Leave one target out (`norway_leave_one_out.json`)

| Calibrated on | accepted | faster PET-CT | authors' pathway |
|---|---|---|---|
| both targets | 184 | 50–74% (median 60.5) | 62–86% (median 75) |
| share only | 188 | 50–74% (60.6) | 62–86% (75) |
| median only | 345 | 47–74% (58) | 58–86% (74) |

Predictions barely change, because the two targets are one constraint (above). That is robustness to dropping a target, but it is
no extra evidence: it does not mean five parameters are pinned by two numbers.

### 4. Target noise (`norway_noise.json`)

The 100-patient cohort has sampling SD of 4.9 points on the share and 1.9 d on the median (from 300 simulated cohorts at the best fit,
correlation −0.81). Resampling the targets within that error (500 draws, joint) and re-accepting with the shipped tolerance:
the mean prediction of the accepted set varies with SD 5.0 points (faster PET, 90% of draws 52–68%) and 3.5 points (authors', 69–80%).
Tolerances of ±1 SE and ±2 SE give nearly identical means (59–60%, 74%). The shipped tolerance (±0.04, ±2.5 d) is about one standard
error of the data: sensible, and the result does not depend on it. The data cannot tell the accepted sets apart (they are all within noise of the targets), so the band is set by the grid and the free parameters, not by the tolerance. Target noise alone moves the authors'-pathway prediction over an 11-point range (69–80%, 90% of draws), the size of its gap to the published 80%.

### 5. The faster-PET miss (`norway_mechanisms.json`)

- Incomplete work-up at the board, discussed again next week: already run on the full grid (`docs/external_checks.md` section 2,
  scenarios `scenarios/experiments/stokstad_incomplete_board_*.yaml`): faster PET 58–64%, best fit 65%; **does not fix** it, because the
  second discussion delays both pathways alike. Not repeated here.
- Within-patient correlated delays (a shared latent slowness on all waits; wrapper in `scripts/norway_correlated.py`, engine untouched),
  recalibrated on a reduced 240-point grid:

| rho | accepted | faster PET-CT (min–median–max) | gain over observed, points | authors' pathway |
|---|---|---|---|---|
| 0 | 38 | 52–61–71% | 15–22–32 | 67–75–86% |
| 0.3 | 46 | 52–61–73% | 15–21–31 | 65–74–85% |
| 0.6 | 52 | 51–59–70% | 12–19–29 | 62–73–83% |

Correlation lowers the faster-PET median by only 2 points at rho 0.6 and the authors' pathway by 2: **it does not fix the over-prediction**
(published 48%). Higher rho (0.9) and the combination with the board mechanism were not run.
- What remains unexplained: the paper reports 8 points for faster PET and the model gives 13–33. The model puts PET-CT on the critical path
  of most patients, and the paper's per-step medians do not show that.

### 6. Verdict

- **Calibration**: correctly executed, but it is a grid search with a box acceptance rule on two targets that are effectively one number; it
  identifies a region, not a point. Three of five parameters were at the edge and the accepted region continues beyond it.
- **Overfitting / predictive power**: the shipped "78–86% vs 80%" is the best corner of a 62–86% band. The 80% match holds up as consistent
  (about two thirds of accepted sets fall in the published CI), not as a sharp out-of-sample hit. Faster PET is over-predicted in most accepted sets.
  The sampling-ratio match (0.82) was not rechecked here.
- **Ranking changes**: supported. In all 184 accepted sets authors' pathway > faster PET-CT > observed (`norway_ranking.json`), and the
  ordering holds at 1028 of 1043 predicted grid points. The authors' reordering gives +24 to +47 points over observed (published +40) and
  beats faster PET alone by 1–29 points.
- **Magnitudes**: not supported to better than about ±12 points on the authors' pathway and ±12 on faster PET-CT; assume gains of
  reordering are real and large, faster-single-step gains are probably overstated by this model.
- **Real outcomes**: the validation is one hospital, 100 cancer patients, delays re-timed from published medians, a published target that is itself a
  model estimate. It supports "reordering beats single-step speed-ups in this setting", not a forecast of real shares within 42 days.

Recommendation (not made): report the prediction band, not 78–86%, in the pitch (authors' pathway 62–86%, central 75%; faster PET 50–74%);
extend the shipped calibration grid at the post-board wait, extra wait and bronchoscopy wait, or report likelihood-weighted
predictions; keep `stokstad_calibrated.yaml` as the best-fit illustration only.

## Optimiser robustness, ablation and structure check (14 Nov night)

Question: the optimiser, started from the observed Norwegian pathway, reached 88.2% treated within 42 days with the faster PET-CT scanner and 67.1% without. It was only ever tested on the 11 settings of the first calibration grid. Does it hold on the 184 accepted settings of the extended grid? Which of its four changes matter? How close is our reconstruction to the paper?

Reproduce: `python scripts/norway_optimiser_robust.py` (tasks 1 and 2) and `python scripts/norway_optimiser_structure.py` (task 3 experiments), both cached in `docs/review_checks/norway_opt_*.json`; `--recompute` reruns (about 50 minutes each on 2 shared cores). Settings: n = 1000 patients, seed 1 per grid setting, the same patients for every flowchart. Observed, faster-PET and authors' pathway are read from the grid table (a spot check re-ran three settings and matched exactly). Best fit: the shipped calibrated scenario, held-out seeds 201 to 203, 3 x 1000 patients, the same cohorts as the dashboard (the run reproduces 88.2% and 67.1%). Noise on a 1000-patient share is about 1.5 points; differences between flowcharts on the same patients are tighter. The optimiser's four changes: (a) tumour board before sampling is finished, (b) PET-CT always ordered early, (c) exercise test always ordered early, (d) tissue sampling ordered at the same time as the first visit (it starts right after the CT). The four-change flowchart was rebuilt from the observed flowchart and checked node by node against the saved `runs/opt_stokstad*.json`. One choice to know: the saved flowcharts carry the best-fit PET-CT-at-triage share (1.0). On each grid setting they get that setting's share, as every other flowchart does.

### 1. The optimiser on the 184 settings

Share treated within 42 days, across the 184 accepted settings (percent):

| Flowchart | min | 10% | median | 90% | max |
|---|---|---|---|---|---|
| Observed | 36.0 | 36.7 | 39.4 | 42.9 | 44.0 |
| Faster PET-CT only | 49.7 | 54.5 | 60.5 | 66.3 | 74.2 |
| Authors' pathway (simulated, with faster scanner) | 61.7 | 66.4 | 74.7 | 82.1 | 85.9 |
| Optimiser, no new equipment | 48.3 | 56.8 | 64.8 | 71.0 | 76.8 |
| Optimiser, with faster scanner | 78.2 | 82.0 | 87.7 | 91.3 | 93.3 |

- Optimiser with scanner beats the authors' pathway in **184 of 184** settings, by 3.6 to 19.0 points (median 12.8). It beats faster-PET-only in 184 of 184.
- Optimiser without equipment beats observed in **184 of 184** (gain 10.6 to 36.0 points, median 24.9).
- Optimiser without equipment beats faster-PET-only in **128 of 184**. It loses in 56. Median gap +5.1 points, range -21.7 to +22.2. The losses are the settings where PET-CT is mostly ordered at the first visit (triage share 0 to 0.5: 34 of the 56) and the wait after the board is short.
- Optimiser without equipment beats the authors' pathway in 22 of 184. That comparison is not fair: the authors' pathway includes the faster scanner.
- The ranking holds. The size does not: the "88.2 / 67.1" of the best fit is a middle value; the no-equipment result ranges over 28 points and the with-scanner result over 15.

### 2. Ablation

Remove one change at a time (leave one out), and add one change at a time to the observed pathway. Best fit in the first columns; median over the 184 in the last.

| Optimiser flowchart | no scanner, best fit | no scanner, 184 median (min to max) | with scanner, best fit | with scanner, 184 median (min to max) |
|---|---|---|---|---|
| All four | 67.1 | 64.8 (48.3 to 76.8) | 88.2 | 87.7 (78.2 to 93.3) |
| Without (a) board before sampling done | 65.7 | 62.7 | 85.8 | 84.6 |
| Without (b) PET-CT always early | 51.3 | 51.4 | 77.7 | 79.1 |
| Without (c) exercise test always early | 62.4 | 60.4 | 81.5 | 82.0 |
| **Without (d) sampling at the first visit** | **64.9** | **60.9 (47.5 to 68.5)** | **85.4** | **82.8 (69.6 to 90.2)** |
| Only (b) and (c) (neither (a) nor (d)) | 56.7 | 52.4 | 73.6 | 71.2 |
| Only (d), on the observed pathway | 46.6 | 46.4 | 69.7 | 70.6 |

Loss when a change is removed, in points (best fit; 184 median): (b) 15.8 and 10.5 (13.2 and 9.2); (c) 4.7 and 6.7 (4.2 and 5.8); (a) 1.4 and 2.4 (1.3 and 1.9); (d) 2.2 and 2.8 (3.1 and 3.8). Removing any change lowers the result in every one of the 184 settings.

**Is the optimiser's lead over the authors' pathway entirely due to (d)? No.**

- Without (d), with the scanner, the optimiser still gives 85.4% at the best fit against 80.1% for the authors' pathway (+5.3). Over the 184 it beats the authors' pathway in 182 and leads by 7.9 points at the median (with (d): 12.8). So (d) is about a third of the lead.
- Without (d) and without the scanner the optimiser equals the three changes (a), (b), (c): 64.9% at the best fit (median 60.9% over the 184). That is above faster-PET-only (60.3%) by 4.6 points at the best fit, and above it in 113 of 184 settings.
- (b), the PET-CT change, is the biggest single piece. It is one of the authors' own three changes.
- (a) and (d) are substitutes. Each takes sampling off the path to the board. Alone, each costs little; removing both costs 10.4 points (no scanner) and 14.6 (scanner) at the best fit.
- The real source of the lead is in the authors' pathway, not in (d) (section 3): our authors' pathway makes treatment wait for the tissue sample, which only starts after the tumour board. Take that wait away and it gives 88.3% at the best fit, the optimiser's 88.2%. Over the 184 the difference is 0.2 to 2.5 points (median 0.3).

### 3. Structure check against the paper

What I could read. The publisher, PMC and NCBI hosts refused or blocked the fetch tool, except the figure caption pages and the Springer article page. The text below comes from a machine summary of the Springer open-access page and of the captions of figures 3 and 4. **I did not see the figure images** and did not read the full text myself, so every row below is "as summarised" and should be checked against the paper before it is used in the pitch. The repo's own earlier note (`params/stokstad.yaml`, `docs/parameters.md`) says the figure 4 timings were also never seen. Summaries only; no passages copied.

What the paper says, as far as I could read it. Figure 3 has three panels: observed, the same patients with a PET-CT wait of 7 days or less, and the reordered pathway with that same PET-CT wait. Figure 4 draws the observed and the proposed pathway with median times. The proposed pathway: CT requested right after the referral letter; PET-CT (fit patients) and exercise test (reduced lung function) requested right after the first consultation; tumour board straight after them, which also chooses the sampling method and the treatment; treatment referral straight after the board, before the final diagnostic results, because PET-CT changed the plan in about 2% of patients; sampling requested after the board. The simulation reordered each patient's observed intervals. It used the 7-day PET-CT wait for everyone, and the observed referral-to-treatment waits (surgery 13 days, radiotherapy 22.5). A discussion passage says PET-CT should ideally be requested even earlier, soon after the CT.

| # | Our flowchart (`scenarios/stokstad.yaml`) | Paper | Likely effect on our numbers | Tested |
|---|---|---|---|---|
| 1 | In the authors' pathway **treatment waits for the tissue sample to finish** (`treat` after the board and `sampling_done`), and sampling only starts after the board | Treatment is referred right after the board; sampling happens while the patient waits for treatment | Large, raises ours when removed: +13.5 points median (+8.2 at the best fit: 80.1 to 88.3). Binding because the fitted wait after the board is only 2 to 8 days, while a sample takes a week or more from request to report in most settings | Yes, below |
| 2 | Fitted practice orders on-time PET-CT at triage (share 1.0 at the best fit, 0.5 to 1.0 in most accepted settings) and carries it into the authors' pathway | Formal definition: PET-CT after the first consultation; the paper's own list of delays counts a PET-CT not requested at the first consultation as late | Large, lowers ours: 80.1 to 66.1 at the best fit; median -14.1 over the 184 | Yes, below |
| 3 | Wait from the board to treatment start is fitted at 6 days (best fit) or 2 to 8 (extended grid) | Observed referral-to-treatment medians, 13 days (surgery) and 22.5 days (radiotherapy), 0 days from board to referral | Large, direction unknown. The paper's step medians chained exceed its 46.5-day median, so something overlaps that the paper does not say; our fit puts the overlap here | Already in section 1 |
| 4 | Waits drawn independently per step (lognormal, p90 assumed) | Each patient's own observed intervals are reused, so a slow patient stays slow | Moderate. Correlation barely moves the faster-PET miss (section 5 above) | Yes, earlier |
| 5 | Faster PET-CT: wait uniform 2 to 4.5 days plus a report of about 2.5, so 5 to 7 days (assumption) | "7 days or less", exact value not given in what I read | Unknown. A slower scanner would lower both faster-PET and authors' numbers; may explain part of the faster-PET over-prediction (62% against 48%) | No |
| 6 | PET-CT for every patient | Fit patients only | Small; PET-CT is on the path for most | No |
| 7 | Weekly board with a cutoff (weekday and cutoff are assumptions); the optimal pathway keeps it | Board "straight after" the tests; whether the simulated pathway also removes the wait for the weekly meeting is not stated in what I read | Unknown; if it removes the weekly wait, the paper's 80% is easier than ours | No |
| 8 | Sampling method chosen by tumour location (central bronchoscopy, peripheral needle) | A method that serves diagnosis and staging; count of procedures 112 to 92 | Small; it reproduces the 0.82 ratio | Earlier, not repeated |
| 9 | 16 patients with an incomplete work-up at the board are not modelled in the observed pathway | Counted as a delay reason in the paper | Small; run before (`scenarios/experiments/stokstad_incomplete_board_*`), no fix of the faster-PET miss | Earlier |
| 10 | Exercise test: 24% ordered early in observed practice, 21% need one, always early after the visit in the authors' pathway | Same idea | Matches | n/a |
| 11 | Not reproduced: the paper's 93% estimate using each step's median interval (figure 4) | Reported | Not a check we can make until the figure 4 timings are known | No |

Experiments (copies under `scenarios/experiments/stokstad_authors_variants.yaml`; the shipped scenarios are untouched). Authors' pathway, share treated within 42 days:

| Variant | Best fit | 184 median (min to max) | In published 72 to 87 | Difference to shipped authors' pathway, 184 median |
|---|---|---|---|---|
| Shipped authors' pathway | 80.1 | 74.7 (61.7 to 85.9) | 118 of 184 | 0 |
| Treatment does not wait for sampling | 88.3 | 88.5 (78.5 to 94.9) | 71 of 184 | +13.5 |
| PET-CT requested at the first consultation | 66.1 | 62.6 (44.1 to 76.2) | 19 of 184 | -14.1 |
| Both (the paper's text read literally) | 77.3 | 79.0 (64.2 to 89.5) | 139 of 184 | +3.9 |

Which is closer to the paper on PET-CT? The paper's formal pathway requests PET-CT at the first consultation, so the literal reading is **PET-CT at the first visit**, not at triage. Alone that gives 66%, which misses the published 80%. But the shipped 80% rests on two errors that offset each other: PET-CT earlier than the paper has it (raises ours), and a treatment wait for sampling that the paper does not have (lowers ours). The literal reading of both gives 77.3% at the best fit and 79.0% median over the 184, closer to 80% than the shipped version, and 139 of 184 settings inside the published interval against 118. It is a better-structured match, not a better fit: the observed pathway was calibrated with the triage share, and I did not recalibrate with the literal reading. In the 40 settings with a triage share of 0 or 0.5, the literal reading gives a median of 84.4%.

### 4. What may be claimed about the optimiser on this test

- The ranking holds. On all 184 settings the optimiser without equipment beats observed, and the optimiser with the faster scanner beats the authors' pathway as we simulate it and faster-PET-only. Say this.
- The size does not hold. Optimiser with scanner: 78 to 93% (median 88); no equipment: 48 to 77% (median 65), against 40% observed. Do not quote 88.2 and 67.1 without the range.
- Without equipment it is not clearly better than the scanner alone: it beats faster-PET-only in 128 of 184, loses in 56. Do not say "reordering beats buying the scanner" from this test without that count.
- The optimiser's lead over the authors' pathway is **not a finding about care**. It comes from our authors' pathway making treatment wait for sampling that starts after the board. With that wait removed the two are within 0.2 to 2.5 points in every setting. The claim "the optimiser improved on the authors' pathway" must not be made.
- The independent evidence is that the optimiser rediscovered, from the observed pathway alone, the authors' three changes (a, b, c) and put the biggest weight on PET-CT (b) and the exercise test (c). The fourth, (d), is not in the paper; it is worth 2 to 4 points here and overlaps with (a). It means ordering the tissue sample at the CT stage. Whether a biopsy can be planned before the first visit is a clinical question the model cannot answer.
- Held-out here means other patients, not other structure. The optimiser, its test and the model share the same assumptions, including the gate in row 1 and the triage share in row 2.

Not done: re-running the optimiser search under each of the 184 settings (the flowcharts are the ones found at the best fit); recalibrating the observed pathway under the literal reading of PET-CT timing; the faster-scanner wait, the board frequency and the 93% estimate (rows 5, 7, 11); reading the figure images or the full text first-hand.

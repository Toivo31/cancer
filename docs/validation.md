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

11 of 192 grid points reproduce the observed pathway (share 0.40 ± 0.04, median 46.5 ± 2.5 d).

| Flowchart | Published | Simulated (11 accepted sets) | Verdict |
|---|---|---|---|
| Observed (calibrated) | 40%, median 46.5 d | 36–43%, median ~46 d | fitted |
| PET-CT ≤ 7 days only | 48% (95% CI 39–58), n.s. | **55–67%** (median 62%) | over-predicts |
| Authors' optimal pathway | 80% (95% CI 72–87) | **78–86%** (median 83%) | **matches** |
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

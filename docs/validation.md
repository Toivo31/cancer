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
| Observed (calibrated) | 40%, median 46.5 d | 37–43%, median ~46 d | fitted |
| PET-CT ≤ 7 days only | 48% (95% CI 39–58), n.s. | **55–67%** (median 62%) | over-predicts |
| Authors' optimal pathway | 80% (95% CI 72–87) | **78–86%** (median 83%) | **matches** |
| Sampling procedures, optimal / observed | 92 / 112 = 0.82 | 0.80 / 0.98 = 0.82 | matches |

Seed-averaged check on the best fit (50 × 100 patients): observed 40.6%, faster PET 59.4%,
optimal 80.1%.

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
- The authors' 80% is itself a model estimate, and all 100 patients had cancer. This validates
  specialist-care ordering, not primary-care filtering.

## Open

- Faster-PET over-prediction: try adding the "incomplete workup at tumour board → re-discussed
  next week" mechanism (16 patients) and within-patient correlation of delays.
- Bootstrap 100-patient cohorts to put a CI on our simulated shares (the paper's CIs are ±9 pp).

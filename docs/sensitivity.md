# Sensitivity of the conclusion to our assumptions (W2, W3 link, F4)

**Question for the judges:** does "reordering the diagnostic steps beats the status quo" survive our assumptions?
Code: `pathway_sim/sensitivity.py`. Raw numbers: `docs/sensitivity_stokstad.json`, `docs/sensitivity_finland_lung.json`,
`docs/sensitivity_finland_lung_capacity_control.json`, `docs/sensitivity_finland_equity.json`.
External checks (England's rapid-CT result, the faster-PET over-prediction): `docs/external_checks.md`.

## Method

- Every numeric parameter tagged `source: assumption` is varied one at a time, low and high: x0.75 and x1.25 (probabilities
  clipped to 0 to 1; a lognormal median keeps its p90/median ratio; integer capacities plus or minus 1 slot when the scenario has 1 to 4,
  plus or minus 25% above, and the same rule is applied to the flowcharts' own capacity overrides; Finnish arrivals only plus or minus 10%).
  For Stokstad we add six parameters (`EXTRA` in the code) whose notes say "assumption" or "calibrated" but whose block carries the paper's source id;
  one of them (the PET-CT wait, 18 d) is derived from the published 20.5 d referral-to-report interval.
- Same patients in every variant (hash-based common random numbers), flowcharts A (status quo) and B (improved) rerun, headline
  metric is the **share treated within target** (42 days Stokstad; 90 days Finland, provisional D20) and the **median days to treatment**.
  The **gain** is B minus A, in percentage points and days (negative days = faster).
- **Joint draws**: all parameters drawn together, uniformly between their low and high values. Reported: how often B still beats A, and the
  spread of the gain. For Stokstad also the subset of draws in which the observed pathway still reproduces the published 40% and 46.5 days
  (the calibration tolerances), because a one-at-a-time change that breaks the fit to the observed pathway is not a plausible world.
- **Seed noise** is reported per scenario (standard deviation of the gain over single seeds). Swings smaller than it are not distinguishable.
- Not varied: service times (0.04 to 0.1 days), costs, non-cancer prevalences (they must sum to 1 with the sourced cancer
  prevalences; the cancer share of presenters is a county-size question, covered by arrivals), the `source`-tagged parameters (tests
  and resources with a literature source), and flowchart structure. Finland: 26 of the roughly 100 assumption parameters, chosen as the
  plausibly influential ones (capacities, booking leads, safety net, clinical-suspicion probabilities, CT/PET false-positive rates, arrivals);
  the list is `SHORTLIST` in the code.

## Verdict in plain language

**Norwegian check (Stokstad, calibrated scenario): yes, it survives.** The authors' optimal pathway beats the observed one by
about 41 percentage points (39% to 80% within 42 days; median 46 to 31 days) at the base setting. Across the 10 assumption parameters
varied one at a time the gain never drops below +33 pp (and +12 days faster); in 80 joint draws the optimal pathway beat the observed one in
all of them (gain 32 to 48 pp, 5th to 95th percentile) and also when only the draws that still reproduce the observed 40% are
kept (35 draws, 32 to 42 pp). Against the stronger comparator "faster PET-CT only" the gain is +22 pp at base, never below +19 pp
one at a time and at least +15 pp in the joint draws. The seed noise of the gain is below 1 pp, so the ranking of parameters is meaningful.
The assumption that moves the gain most is the PET-CT waiting time before the scanner; shorter PET waits make the status quo look better, which is the
"speed up the bottleneck" story. Nothing we vary makes the status quo win.

**Finnish scenario (synthetic): yes for the direction, but the size is an assumption and one condition matters.**
- `baseline` to `bundled_workup`: gain +43 pp (19% to 62% within 90 days) and 29 days faster at the base seed. The gain stays positive in every
  one of 52 one-at-a-time variants (minimum +7 pp) and in 15 of 16 joint draws (5th to 95th percentile +4 to +45 pp). Seed noise is large (single-seed sd 7 pp, 6.7 days; base gain across seeds 1 to 3 is 43, 30, 31 pp),
  so the *size* is uncertain by about 10 pp and 7 days and the tornado ranking below is only reliable for swings larger than that.
- **But this comparison includes the extra PET-CT capacity the bundle needs.** Against the fair control `baseline_plus_capacity` (same extra CT and PET capacity, old order),
  the gain from order alone is +20 pp and 16.5 days at the base seed (noise sd 3 pp, 2 days). It is positive in every one-at-a-time variant except
  when CT or PET-CT capacity is one slot short of what the bundled work-up demands (gain -31 pp with 2 CT slots; -10 pp with 2 PET-CT slots, where demand is 2.3 a day):
  then the queue grows without bound and reordering loses. 10 of 12 joint draws favour reordering. Reordering moves demand to PET-CT (about 2.8 times as many scans), so it only wins if that capacity is provided.
- `baseline` to `fast_track_nonspecific`: gain +20 pp and 7 days at base, positive in all one-at-a-time variants and all 16 joint draws in share, faster in median in 15 of 16 draws.
  The size is small relative to the noise (sd 4.8 pp, 3.2 days).

**What the conclusion is most sensitive to.** Stokstad: PET-CT wait, the wait between tumour board and treatment, the non-diagnostic rate of sampling.
Finland: CT capacity and PET-CT capacity (both as demand-versus-supply questions), the safety net (the chance that a missed cancer's symptoms persist and the patient re-presents), clinic capacity and booking lead, GP imaging at first visit, arrivals (county size).
Timing leads and capacity at the specialist step dominate; test accuracy numbers matter less.

**What we can and cannot say.** We can say the direction (reordering and bundling beat status quo and beat capacity alone) is robust to every
one-at-a-time and (nearly always) joint variation of the assumptions we tagged, in both settings. We cannot say the Finnish effect size: it moves by about 10 pp and a week with seed noise alone, and
by tens of pp when the capacity assumptions change. The Stokstad result is calibrated and checked against published numbers; the Finnish result is not.

## Tornado tables

Top 10 parameters by swing of the gain in percentage points. `flags`: *gain <= 0* = B no longer beats A; *queue blow-up* = a median above 1.5 times its base; *breaks calibration* = in that variant the observed pathway leaves the published 40% / 46.5 d band (Stokstad only), so it is not a plausible world.

### Stokstad (calibrated scenario, n=800 per seed, seeds 1 and 2)

Scenario stokstad  (n=800, seeds=[1, 2], 10 parameters, 344 s)

**observed -> optimal**: base gain +40.7 pp share within target, -14.7 d median. Seed noise (sd of the gain, one seed): 0.73 pp, 0.64 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| PET-CT wait before the scanner, derived from the published 20.5 d referral-to-report (`tests.pet_ct.wait.median`) | 13.5 / 18 / 22.5 | 46.4..31.0 | 79.6..79.6 | +33.1, +48.6 | -12.0, -17.7 | 15.4 | breaks calibration low/high |
| wait from tumour board to surgery / RT start (calibrated, joint) (`treatment_wait_after_board`) | 4.5 / 6 / 7.5 | 43.8..33.1 | 80.8..77.2 | +36.9, +44.1 | -13.6, -15.6 | 7.1 | breaks calibration high |
| non-diagnostic rate of bronchoscopy / needle biopsy (all, joint) (`sampling_nondiagnostic`) | 0.15 / 0.2 / 0.25 | 40.6..37.7 | 79.8..79.4 | +39.2, +41.7 | -14.1, -15.0 | 2.5 |  |
| CT report not ready at first visit, extra wait median (calibrated) (`tests.first_visit.extra_wait.median`) | 1.5 / 2 / 2.5 | 40.1..37.4 | 81.2..77.2 | +41.1, +39.8 | -15.1, -14.5 | 1.4 |  |
| policy pet_on_time: share pet_triage (rest pet_early_route), all flowcharts (`policy.pet_on_time.pet_triage`) | 0.75 / 1.0 / 1.0 | 34.9..38.9 | 76.8..79.6 | +41.8, +40.7 | -14.7, -14.7 | 1.1 | breaks calibration low |
| further_workup: wait median (`tests.further_workup.wait.median`) | 5.25 / 7 / 8.75 | 39.2..38.6 | 80.2..78.8 | +40.9, +40.3 | -14.8, -14.7 | 0.7 |  |
| bronchoscopy wait median (calibrated) (`tests.bronchoscopy.wait.median`) | 2.25 / 3 / 3.75 | 39.7..38.4 | 79.9..79.3 | +40.2, +40.9 | -14.6, -14.8 | 0.7 |  |
| further_workup: report_days median (`tests.further_workup.report_days.median`) | 3.375 / 4.5 / 5.625 | 39.1..38.8 | 79.8..79.1 | +40.7, +40.3 | -14.8, -14.7 | 0.4 |  |
| tumour-board cutoff (days before the meeting, calibrated) (`resources.tumour_board.cutoff_days`) | 0.0 / 0 / 2.0 | 38.9..33.8 | 79.6..74.9 | +40.7, +41.1 | -14.7, -14.9 | 0.4 | breaks calibration high |
| attribute location: share central (rest peripheral) (`attributes.location.central`) | 0.225 / 0.3 / 0.375 | 38.7..39.4 | 79.0..79.8 | +40.3, +40.4 | -14.6, -14.8 | 0.1 |  |

**faster_pet -> optimal**: base gain +22.2 pp share within target, -7.5 d median. Seed noise (sd of the gain, one seed): 0.45 pp, 0.6 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| wait from tumour board to surgery / RT start (calibrated, joint) (`treatment_wait_after_board`) | 4.5 / 6 / 7.5 | 61.6..52.1 | 80.8..77.2 | +19.2, +25.1 | -6.2, -8.4 | 5.9 | breaks calibration high |
| non-diagnostic rate of bronchoscopy / needle biopsy (all, joint) (`sampling_nondiagnostic`) | 0.15 / 0.2 / 0.25 | 59.4..55.3 | 79.8..79.4 | +20.4, +24.1 | -6.4, -8.1 | 3.6 |  |
| policy pet_on_time: share pet_triage (rest pet_early_route), all flowcharts (`policy.pet_on_time.pet_triage`) | 0.75 / 1.0 / 1.0 | 56.4..57.3 | 76.8..79.6 | +20.4, +22.2 | -6.7, -7.5 | 1.9 | breaks calibration low |
| bronchoscopy wait median (calibrated) (`tests.bronchoscopy.wait.median`) | 2.25 / 3 / 3.75 | 58.4..56.6 | 79.9..79.3 | +21.6, +22.7 | -7.2, -7.6 | 1.1 |  |
| further_workup: wait median (`tests.further_workup.wait.median`) | 5.25 / 7 / 8.75 | 57.7..56.9 | 80.2..78.8 | +22.5, +21.9 | -7.5, -7.4 | 0.6 |  |
| further_workup: report_days median (`tests.further_workup.report_days.median`) | 3.375 / 4.5 / 5.625 | 57.5..57.1 | 79.8..79.1 | +22.3, +21.9 | -7.5, -7.4 | 0.3 |  |
| attribute location: share central (rest peripheral) (`attributes.location.central`) | 0.225 / 0.3 / 0.375 | 57.1..58.1 | 79.0..79.8 | +21.9, +21.7 | -7.4, -7.3 | 0.3 |  |
| CT report not ready at first visit, extra wait median (calibrated) (`tests.first_visit.extra_wait.median`) | 1.5 / 2 / 2.5 | 59.1..55.4 | 81.2..77.2 | +22.1, +21.8 | -7.4, -7.6 | 0.2 |  |
| tumour-board cutoff (days before the meeting, calibrated) (`resources.tumour_board.cutoff_days`) | 0.0 / 0 / 2.0 | 57.3..52.5 | 79.6..74.9 | +22.2, +22.4 | -7.5, -7.8 | 0.1 | breaks calibration high |
| PET-CT wait before the scanner, derived from the published 20.5 d referral-to-report (`tests.pet_ct.wait.median`) | 13.5 / 18 / 22.5 | 57.3..57.3 | 79.6..79.6 | +22.2, +22.2 | -7.5, -7.5 | 0.0 | breaks calibration low/high |

**Joint draws (all parameters at once)**

| Pair | subset | draws | B beats A (share) | B faster (median) | gain pp p5 / median / p95 | gain days p5 / median / p95 |
|---|---|---|---|---|---|---|
| observed>optimal | all | 80 | 100% | 100% | 32.2 / 40.3 / 48.3 | -17.7 / -14.5 / -11.8 |
| observed>optimal | calibration_consistent | 35 | 100% | 100% | 32.4 / 36.9 / 42.2 | -15.7 / -13.2 / -11.8 |
| faster_pet>optimal | all | 80 | 100% | 100% | 16.7 / 21.1 / 24.6 | -8.4 / -7.2 / -5.7 |
| faster_pet>optimal | calibration_consistent | 35 | 100% | 100% | 16.1 / 20.2 / 22.7 | -8.1 / -6.8 / -5.5 |

### Finland: status quo against bundled work-up and fast track (n=10,000, seed 1)

Scenario finland_lung  (n=10000, seeds=[1], 26 parameters, 452 s)

**baseline -> bundled_workup**: base gain +43.0 pp share within target, -29.0 d median. Seed noise (sd of the gain, one seed): 7.2 pp, 6.65 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| ct_scanner: slots per day (also the flowchart capacity overrides) (`resources.ct_scanner.capacity_per_day`) | 2 / 3 / 4 | 2.5..19.8 | 9.9..62.0 | +7.4, +42.1 | -20.0, -29.2 | 34.7 | queue blow-up |
| symptoms_persist: P(positive), cancer conditions (`tests.symptoms_persist.p_positive[cancer]`) | 0.7125 / 0.95 / 1.0 | 30.6..17.4 | 61.2..63.6 | +30.6, +46.3 | -22.1, -31.7 | 15.7 |  |
| clinic: slots per day (`resources.clinic.capacity_per_day`) | 5 / 7 / 9 | 5.0..19.0 | 34.7..62.0 | +29.8, +43.0 | -26.1, -29.0 | 13.2 |  |
| pet_scanner: slots per day (also the flowchart capacity overrides) (`resources.pet_scanner.capacity_per_day`) | 1 / 1 / 2 | 19.0..36.4 | 32.2..62.0 | +13.2, +25.6 | -4.7, -18.5 | 12.4 |  |
| gp_assessment: P(positive), cancer conditions (`tests.gp_assessment.p_positive[cancer]`) | 0.7275 / 0.97 / 1.0 | 13.2..16.5 | 51.2..66.1 | +38.0, +49.6 | -24.3, -30.0 | 11.6 |  |
| arrivals per day (county size) (`arrivals.rate_per_day`) | 39.6 / 44 / 48.4 | 24.4..8.6 | 63.8..57.3 | +39.4, +48.7 | -23.4, -31.3 | 9.3 |  |
| clinic: min_lead_days (`resources.clinic.min_lead_days`) | 9.0 / 12 / 15.0 | 24.8..11.6 | 64.5..58.7 | +39.7, +47.1 | -26.5, -29.7 | 7.4 |  |
| specialist_visit: P(positive), non-cancer conditions (`tests.specialist_visit.p_positive[non-cancer]`) | 0.2625 / 0.35 / 0.4375 | 19.0..11.6 | 62.0..61.2 | +43.0, +49.6 | -28.7, -30.4 | 6.6 |  |
| gp_represent: extra_wait median (`tests.gp_represent.extra_wait.median`) | 10.5 / 14 / 17.5 | 15.7..19.0 | 63.6..61.2 | +47.9, +42.2 | -30.2, -30.2 | 5.8 |  |
| treatment_slot: min_lead_days (`resources.treatment_slot.min_lead_days`) | 7.5 / 10 / 12.5 | 25.6..14.9 | 64.5..58.7 | +38.8, +43.8 | -29.3, -29.5 | 5.0 |  |

**baseline -> fast_track_nonspecific**: base gain +19.8 pp share within target, -7.4 d median. Seed noise (sd of the gain, one seed): 4.79 pp, 3.15 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| clinic: slots per day (`resources.clinic.capacity_per_day`) | 5 / 7 / 9 | 5.0..19.0 | 12.4..40.5 | +7.4, +21.5 | -11.1, -9.0 | 14.1 |  |
| clinic: min_lead_days (`resources.clinic.min_lead_days`) | 9.0 / 12 / 15.0 | 24.8..11.6 | 38.8..35.5 | +14.1, +24.0 | -7.5, -10.5 | 9.9 |  |
| arrivals per day (county size) (`arrivals.rate_per_day`) | 39.6 / 44 / 48.4 | 24.4..8.6 | 41.7..35.0 | +17.3, +26.5 | -6.5, -9.4 | 9.2 |  |
| pet_scanner: slots per day (also the flowchart capacity overrides) (`resources.pet_scanner.capacity_per_day`) | 1 / 1 / 2 | 19.0..36.4 | 38.8..47.9 | +19.8, +11.6 | -7.4, -6.3 | 8.3 |  |
| gp_assessment: P(positive), cancer conditions (`tests.gp_assessment.p_positive[cancer]`) | 0.7275 / 0.97 / 1.0 | 13.2..16.5 | 31.4..42.1 | +18.2, +25.6 | -8.8, -9.7 | 7.4 |  |
| treatment_slot: slots per day (`resources.treatment_slot.capacity_per_day`) | 1 / 2 / 3 | 12.4..19.8 | 38.8..38.8 | +26.4, +19.0 | -8.1, -7.4 | 7.4 |  |
| treatment_slot: min_lead_days (`resources.treatment_slot.min_lead_days`) | 7.5 / 10 / 12.5 | 25.6..14.9 | 40.5..36.4 | +14.9, +21.5 | -6.9, -7.5 | 6.6 |  |
| chest_ct: report_days median (`tests.chest_ct.report_days.median`) | 2.25 / 3 / 3.75 | 17.4..19.0 | 40.5..37.2 | +23.1, +18.2 | -11.7, -6.5 | 5.0 |  |
| symptoms_persist: P(positive), cancer conditions (`tests.symptoms_persist.p_positive[cancer]`) | 0.7125 / 0.95 / 1.0 | 30.6..17.4 | 43.0..33.9 | +12.4, +16.5 | -6.7, -8.1 | 4.1 |  |
| clinic: urgent_lead_days (`resources.clinic.urgent_lead_days`) | 3.75 / 5 / 6.25 | 19.0..19.0 | 39.7..36.4 | +20.7, +17.3 | -7.5, -6.0 | 3.3 |  |

**Joint draws (all parameters at once)**

| Pair | subset | draws | B beats A (share) | B faster (median) | gain pp p5 / median / p95 | gain days p5 / median / p95 |
|---|---|---|---|---|---|---|
| baseline>bundled_workup | all | 16 | 94% | 94% | 4.5 / 28.2 / 44.9 | -30.4 / -21.5 / -7.2 |
| baseline>fast_track_nonspecific | all | 16 | 100% | 94% | 5.3 / 10.8 / 21.5 | -11.2 / -7.1 / 1.8 |

### Finland: capacity-only control against bundled work-up (reordering versus capacity alone)

Scenario finland_lung  (n=10000, seeds=[1], 26 parameters, 302 s)

**baseline_plus_capacity -> bundled_workup**: base gain +19.8 pp share within target, -16.5 d median. Seed noise (sd of the gain, one seed): 3.32 pp, 1.93 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| ct_scanner: slots per day (also the flowchart capacity overrides) (`resources.ct_scanner.capacity_per_day`) | 2 / 3 / 4 | 40.5..42.1 | 9.9..62.0 | -30.6, +19.8 | +31.8, -16.2 | 50.4 | gain <= 0, queue blow-up |
| pet_scanner: slots per day (also the flowchart capacity overrides) (`resources.pet_scanner.capacity_per_day`) | 1 / 1 / 2 | 42.1..41.3 | 32.2..62.0 | -9.9, +20.7 | +7.8, -16.3 | 30.6 | gain <= 0 |
| treatment_slot: slots per day (`resources.treatment_slot.capacity_per_day`) | 1 / 2 / 3 | 19.0..42.1 | 53.7..62.0 | +34.7, +19.8 | -15.0, -16.5 | 14.9 |  |
| clinic: min_lead_days (`resources.clinic.min_lead_days`) | 9.0 / 12 / 15.0 | 45.5..31.4 | 64.5..58.7 | +19.0, +27.3 | -15.2, -16.8 | 8.3 |  |
| ct_scanner: min_lead_days (`resources.ct_scanner.min_lead_days`) | 3.0 / 4 / 5.0 | 42.1..35.5 | 62.0..61.2 | +19.8, +25.6 | -16.8, -16.2 | 5.8 |  |
| pet_scanner: min_lead_days (`resources.pet_scanner.min_lead_days`) | 3.0 / 4 / 5.0 | 42.1..34.7 | 62.8..61.2 | +20.7, +26.5 | -16.2, -18.6 | 5.8 |  |
| treatment_slot: min_lead_days (`resources.treatment_slot.min_lead_days`) | 7.5 / 10 / 12.5 | 47.9..36.4 | 64.5..58.7 | +16.5, +22.3 | -16.4, -18.3 | 5.8 |  |
| clinic: slots per day (`resources.clinic.capacity_per_day`) | 5 / 7 / 9 | 9.1..41.3 | 34.7..62.0 | +25.6, +20.7 | -18.1, -17.1 | 5.0 |  |
| chest_ct: report_days median (`tests.chest_ct.report_days.median`) | 2.25 / 3 / 3.75 | 42.1..38.0 | 62.0..62.0 | +19.8, +24.0 | -15.9, -17.1 | 4.1 |  |
| nurse_assessment: P(positive), cancer conditions (`tests.nurse_assessment.p_positive[cancer]`) | 0.3375 / 0.45 / 0.5625 | 38.8..43.0 | 62.0..62.8 | +23.1, +19.8 | -17.4, -16.7 | 3.3 |  |

**Joint draws (all parameters at once)**

| Pair | subset | draws | B beats A (share) | B faster (median) | gain pp p5 / median / p95 | gain days p5 / median / p95 |
|---|---|---|---|---|---|---|
| baseline_plus_capacity>bundled_workup | all | 12 | 83% | 83% | -9.9 / 25.7 / 34.8 | -20.3 / -16.7 / 7.0 |

## Top 5 sensitive assumptions

- Stokstad, observed to optimal: `tests.pet_ct.wait.median`, `treatment_wait_after_board`, `sampling_nondiagnostic`, `tests.first_visit.extra_wait.median`, `policy.pet_on_time.pet_triage`
- Stokstad, faster PET to optimal: `treatment_wait_after_board`, `sampling_nondiagnostic`, `policy.pet_on_time.pet_triage`, `tests.bronchoscopy.wait.median`, `tests.further_workup.wait.median`
- Finland, baseline to bundled: `resources.ct_scanner.capacity_per_day`, `tests.symptoms_persist.p_positive[cancer]`, `resources.clinic.capacity_per_day`, `resources.pet_scanner.capacity_per_day`, `tests.gp_assessment.p_positive[cancer]`
- Finland, baseline to fast track: `resources.clinic.capacity_per_day`, `resources.clinic.min_lead_days`, `arrivals.rate_per_day`, `resources.pet_scanner.capacity_per_day`, `tests.gp_assessment.p_positive[cancer]`
- Finland, capacity-only control to bundled: `resources.ct_scanner.capacity_per_day`, `resources.pet_scanner.capacity_per_day`, `resources.treatment_slot.capacity_per_day`, `resources.clinic.min_lead_days`, `resources.ct_scanner.min_lead_days`

## F4. Equity-gap sensitivity (Finland: non-specific versus site-specific presenters)

Setup: the two groups differ in the scenario **only** in detection (imaging at the first visit, nurse imaging, GP second look after a negative film, whether
symptoms persist and the GP refers at re-presentation). Everything downstream is identical, so the gap is entirely a function of these
assumptions (and of how long each group waits in the same queues). Twelve parameters varied one at a time (low/high) and jointly (16 draws), n=14,000
patients, seed 1; seed noise from seeds 1 to 3. Gap = non-specific minus site-specific median days to treatment (positive = non-specific wait longer),
and site-specific minus non-specific share treated within 90 days.

**Range of the baseline gap over all 41 variants (one at a time and joint):**

| Measure | Non-specific | Site-specific | Gap |
|---|---|---|---|
| Median days to treatment | 97.8 to 117.5 | 90.9 to 105.9 | **-2.2 to 14.5 days** |
| Treated within 90 d | 9.3% to 27.7% | 17.2% to 43.4% | **4.1 to 23.1 pp** |
| Missed cancers (share of group) | 4.7% to 24.2% | 4.3% to 13.6% | |

Base setting: seed 1 gap 8.5 days (non-specific 106.2, site-specific 97.7); seeds 2 and 3 give 14.0 and 13.6 days, so the base gap is about 12 days with a seed noise of about 3 days.
With the detection probabilities of the two groups **set equal** (no gap by construction) the baseline gap is -3.3 days and 1.5 pp: the gap in this model is
produced by the equity assumptions and by nothing else. Its existence in the real Finnish system is supported only by cited evidence (KOO2023 intervals 34 versus 114 days; BRADLEY2021),
its size here is not estimated.

**What changes the baseline gap (one at a time; effects below about 3 days are within seed noise):**

| Parameter (base) | Low / high value | Gap days, low / high | Gap pp (on time), low / high | Missed non-specific %, low / high |
|---|---|---|---|---|
| GP orders imaging at the first visit, non-specific cancers (0.45) | 0.3375 / 0.5625 | 13.9 / 5.3 | 9.3 / 11.2 | 10.7 / 8.0 |
| GP orders imaging at the first visit, site-specific cancers (0.97) | 0.7275 / 1.0 | 3.0 / 8.5 | 7.7 / 14.4 | 10.7 / 10.7 |
| nurse orders imaging, non-specific cancers (0.15) | 0.1125 / 0.1875 | 7.9 / 6.5 | 7.7 / 11.1 | 10.7 / 10.7 |
| nurse orders imaging, site-specific cancers (0.45) | 0.3375 / 0.5625 | 8.1 / 8.5 | 8.6 / 12.7 | 10.7 / 10.7 |
| GP still refers after a negative film, non-specific (0.10) | 0.075 / 0.125 | 8.5 / 8.5 | 13.6 / 12.7 | 10.7 / 10.7 |
| GP still refers after a negative film, site-specific (0.55) | 0.4125 / 0.6875 | 9.6 / 8.6 | 11.9 / 16.2 | 10.7 / 10.7 |
| safety net: symptoms persist, non-specific cancers (0.90) | 0.675 / 1.0 | 3.5 / 8.1 | 12.4 / 12.9 | 22.3 / 5.4 |
| safety net: symptoms persist, site-specific cancers (0.95) | 0.7125 / 1.0 | 8.6 / 9.3 | 12.7 / 12.7 | 10.7 / 10.7 |
| safety net: GP refers at re-presentation, non-specific (0.95) | 0.7125 / 1.0 | 2.7 / 8.5 | 15.2 / 12.7 | 22.3 / 10.7 |
| safety net timing: re-presentation interval median (14 d, x0.5 / x1.5) | 7.0 / 21.0 | 5.3 / 8.5 | 13.6 / 17.2 | 10.7 / 10.7 |
| group shares: site-specific share of lung cancers (31%) | 0.2344 / 0.3906 | 6.6 / 11.3 | 13.6 / 7.6 | 11.9 / 12.2 |
| chest X-ray sensitivity for cancers (0.754, sourced BRADLEY2021; x0.9 / x1.1) | 0.6786 / 0.8294 | 8.9 / 10.1 | 15.3 / 15.3 | 11.6 / 9.8 |

Largest movers beyond noise: how often the GP orders imaging for non-specific presenters at the first visit (and for site-specific ones), the safety net for non-specific
presenters (whether symptoms persist and the GP refers at re-presentation, which also drives the missed-cancer share from 5% to 22%), and the safety-net interval.

**Do the suggested changes narrow or widen the gap?** Change in the gap, flowchart minus baseline, same patients, over all 41 variants:

| Change | Gap in median days (min to max) | Variants where the gap narrows (days) | Gap in on-time share, pp (min to max) | Variants where it narrows (on-time share) |
|---|---|---|---|---|
| Bundled work-up (board before sampling, PET-CT 3 slots) | -3.4 to 13.3 | 7% (joint draws only: 12%) | 2.0 to 27.6 | 0% |
| Fast lane for non-specific presenters | -18.1 to 3.8 | 95% (joint draws only: 88%) | -28.6 to -0.7 | 100% |

Reading:

- **The fast lane narrows the gap, robustly**: in the median days in 95% of variants, in the on-time share in all of them (by 1 to 29 pp). Typical narrowing at base is
  -8.2 days (seed noise about 3 days; seeds 2 and 3: -1.1, -2.6). It is a targeted change, so this is by design; it would also
  *reverse* the gap if there were none to begin with (with the groups at parity the fast lane makes non-specific presenters 14.5 days faster than site-specific ones).
  Its cost is crowding-out at high reservation shares (`docs/finland_scenario.md`).
- **The bundled work-up does not narrow the gap.** It shortens both groups by about 20 days, but the gap in median days is unchanged or wider (narrows in only 7% of
  variants) and the gap in the share treated within 90 days widens in every variant (+2 to +28 pp), because the group that starts nearer the threshold (site-specific) crosses it first. The change is general; it
  does not touch the detection step where the gap arises. `direct_ct` widened the gap in the base-case comparison (`docs/finland_scenario.md`); we did not run it through the sensitivity analysis.
- Missed cancers do not change in any flowchart (no flowchart alters detection), so **none of the changes closes the detection gap itself** (non-specific missed 5 to 24%, site-specific 4 to 14%).

### Recommended wording for the pitch

*Can claim:* "In our synthetic Finnish model, patients with non-specific symptoms wait longer than patients with alarm symptoms. Across a wide range of plausible assumptions the gap is between
roughly zero and two weeks in median time to treatment, and between 4 and 23 percentage points in the share treated within 90 days. A fast lane aimed at non-specific presenters narrows it
in almost every variation we tried; a pathway-wide reorder (bundled work-up) speeds everyone up by about three weeks but leaves the gap in place."

*Cannot claim:* the size of the real Finnish gap (the model's gap is built from assumed detection probabilities, not estimated from Finnish data; with equal detection it disappears), that a fast lane is free (it crowds out others if the
reserved share is large), that any of the changes fixes the missed cancers at the first visit, or that the direction holds for `direct_ct` (not sensitivity-tested).
Say: "which group is slower is an input we took from the literature; what the model adds is which organisational changes would shrink or widen it, and how robust that is to the numbers we had to assume."

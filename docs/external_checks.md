# External qualitative checks (W3, V4)

Code: `pathway_sim/checks.py`. Raw numbers: `docs/sensitivity_external_rapid_ct.json`, `docs/sensitivity_external_v4.json`. Experiment
scenarios (copies, nothing existing was edited): `scenarios/experiments/`.

Reproduce: `python -m pathway_sim.checks rapid-ct --n 10000 --seeds 1,2,3` (about 3 min) and
`python -m pathway_sim.checks v4 --n 1000` (about 3 min).

## 1. England's rapid-CT finding, in the Finnish scenario

**What was published** (NOLCP, ERJ 2023 abstract; `docs/pitch/evidence_brief.md`): the wait from an abnormal chest X-ray to CT
fell from a median 15 to 3 days, but time from the abnormal X-ray to the treatment decision stayed 66 versus 65 days; other
diagnostic and staging delays remain. Conference abstract, not peer reviewed, read only through the viewer.

**What we ran** (Finnish scenario, 10,000 patients per seed, seeds 1 to 3, same patients in every row; medians over cancers
that were treated and had an abnormal X-ray; "decision" = the tumour-board meeting):

- *rapid_ct_only*: the CT step alone is made fast in place: 8 CT slots a day instead of 3, booking lead 1 day instead of 4,
  report in 1 day instead of 3. Flowchart unchanged.
- *rapid_ct_plus_pet_capacity*: the same plus 3 PET-CT slots (the next scarce step).
- *direct_ct*: the closest analogue of the English change. The GP orders CT straight after a suspicious X-ray, before the
  hospital referral (8 CT slots, as the scenario's own flowchart requires). *+ 1 d CT lead and report* speeds it up further.
- *bundled_workup*: reordering (CT and PET-CT ordered together, board before sampling), 3 PET-CT slots.

All presenters:

| Variant | abnormal X-ray to CT result | abnormal X-ray to board decision | abnormal X-ray to treatment | first contact to treatment | treated within 90 d |
|---|---|---|---|---|---|
| baseline | 28.2 | 60.4 | 75.2 | 102.0 | 20% |
| rapid_ct_only | 21.1 | 50.7 | 67.2 | 94.6 | 40% |
| rapid_ct_plus_pet_capacity | 21.1 | 46.6 | 62.2 | 88.2 | 50% |
| direct_ct (8 CT slots) | 8.7 | 60.7 | 75.5 | 98.6 | 30% |
| direct_ct + 1 d CT lead and report | 3.5 | 53.8 | 69.5 | 91.9 | 40% |
| bundled_workup (reorder) | 28.2 | 33.3 | 51.9 | 79.2 | 50% |

(The "treated within 90 d" column is a median over three seeds of single-seed shares, so it is coarse. Seed-to-seed spread of the
overall median is about 3 to 5 days: baseline 100.7 to 104.3, rapid_ct_only 94.0 to 96.7, direct_ct 95.9 to 100.8.)

Non-specific presenters only (the subset where every flowchart has an abnormal X-ray; about 28 cancers per seed, so noisy):

| Variant | abnormal X-ray to CT result | to board decision | to treatment |
|---|---|---|---|
| baseline | 29.4 | 60.8 | 77.2 |
| rapid_ct_only | 21.4 | 53.8 | 68.2 |
| direct_ct (8 CT slots) | **8.7** | **60.7** | 75.5 |
| direct_ct + 1 d CT lead and report | 3.5 | 53.8 | 69.5 |
| bundled_workup | 29.4 | 33.7 | 53.4 |

Mean waiting days per treated cancer on each step (all steps, not only the critical path): CT 5.8 in the baseline, 1.2 with
rapid CT; specialist visit 12.7, bronchoscopy 5.5, PET-CT 9.7, board 4.7 and treatment slot 16.3 are unchanged by rapid CT.

## Result, honestly

- **The English pattern is reproduced for "CT moved forward", not for "CT made faster in place".**
  With `direct_ct` the X-ray-to-CT interval falls by about 20 days (29.4 to 8.7, England: 15 to 3) while the X-ray-to-decision
  interval does not move (60.8 versus 60.7, England: 66 versus 65) and time to treatment moves by about 2 days. The reason in
  the model is visible in the flowchart: the GP waits for the CT report before writing the referral, the hospital steps that
  follow (referral handling, the 12-day specialist booking lead, sampling, PET-CT, the weekly board, the treatment slot) are
  untouched, so the time saved on the CT is spent waiting earlier in the chain.
- **Not reproduced for the in-place speed-up.** Speeding up only the CT step (`rapid_ct_only`) passes through almost
  completely: the CT interval falls 7 days and the decision falls about 10 and treatment 7 days. The downstream waits do not grow when CT
  gets faster (bronchoscopy 5.5 to 5.0, PET-CT 9.7 to 9.8), because in this scenario most waits are fixed booking leads rather than
  queues that a faster upstream would fill. A real system whose downstream steps are saturated could absorb the gain; ours
  is only moderately loaded, so it cannot show that mechanism by itself. We should not claim that the simulator derives the
  English result; we can claim that it shows the same pattern when the CT is pulled in front of the referral.
- **The bottleneck does shift in the way England's authors describe.** After rapid CT the next resource is PET-CT
  (9.7 days of waiting). Adding PET-CT slots on top cuts the decision interval from 50.7 to 46.6 days; both together are still
  worse than reordering alone (33.3).
- **Contrast with reordering**: `bundled_workup` leaves the X-ray-to-CT interval untouched (28.2) and cuts X-ray-to-decision from 60.4 to
  33.3 days and first contact to treatment by about 23 days (per-seed medians 75 to 85 versus 101 to 104 for the baseline).
  That is the claim: where CT is placed relative to the other steps matters more than how fast one step is.
- Caveats: our baseline X-ray-to-decision (60 days) happens to be close to England's 66, but the scenario was not calibrated to it;
  all waits are `assumption`; one county, synthetic patients.

## 2. Stokstad "faster PET only" over-prediction (V4)

**Problem** (`docs/validation.md`): calibrated on the observed pathway only, the simulator predicts 55 to 67% within 42 days when
PET-CT is made faster, against 48% published (95% CI 39 to 58, not significant). Observed (40%) and optimal (80%) match.

**Mechanism tried**: 16 of 100 patients reach the tumour board with an incomplete work-up and are discussed again at the next
weekly board (a week later). Implemented in a copy of the scenario (`board_check` choice after the first board, a second
`tumour_board_again` visit for 16%; `scenarios/experiments/stokstad_incomplete_board_*.yaml`), then the full calibration grid
(192 points) was rerun on the observed flowchart. Two variants: the mechanism in observed and faster_pet only (the authors'
optimal pathway decides with PET-CT in hand, so it should not occur), and in all three.

| | Observed | Faster PET only | Optimal |
|---|---|---|---|
| Published | 40% | **48%** | 80% |
| Before: seed-averaged best fit (50 x 100 patients) | 40.6% | 59.4% | 80.1% |
| With mechanism in observed + faster PET: grid points that fit / range of prediction | 3 of 192 | 58 to 64% (median 63%) | 84 to 87% |
| ... seed-averaged best fit | 39.9% | **64.8%** | 83.6% |
| With mechanism in all flowcharts: range of prediction | 3 of 192 | 58 to 64% | 82 to 84% |
| ... seed-averaged best fit | 39.9% | **64.8%** | 81.1% |

**Result: it does not help.** The faster-PET prediction does not move towards 48%; at the best fit it rises slightly (59% to 65%).
Observed stays at 40% because the calibration compensates (the share of on-time PET ordered at triage moves from 1.0 to 0.8), optimal stays
at 81 to 84%. The reason is structural: a second board discussion adds a week to a patient in every flowchart in which it
occurs, so the *difference* between observed and faster-PET is unchanged (about 25 percentage points, published 8, not significant).
The recalibration then spends its freedom elsewhere. Only 3 grid points fit with the mechanism (11 before), so the extra
mechanism also makes the fit tighter.

**Diagnosis of what drives the over-prediction**: in the calibrated model, PET-CT is on the critical path of 61% of treated
patients in the observed pathway (pet_triage 1082 and pet_late 742 of 3000) and of 24% after the speed-up. The model says PET-CT is the step that holds patients back far more often
than the real cohort suggests. Mechanisms that would reduce this and that we have not built: correlated delays within a patient (a
slow patient is slow everywhere, so removing the PET delay frees less), PET-CT wait overlapping with other waits more than the published
medians chained in series imply, and the unreported figure 4 timings. These need a change to patient generation (decisions.md D19: results and delays are
drawn independently) or per-patient latent "slowness" in the engine; see the engine requests in the final report.

**What to say**: faster-PET is the one out-of-sample check we over-predict (about 59 to 65% against 48%, which is at the edge of the published
interval, 39 to 58%). The conclusion "reordering beats the status quo" is not weakened by it (the check errs towards the faster-the-bottleneck
story), but we do not claim to reproduce that number.

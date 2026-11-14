### finland_lung  (n=18800, seeds=[1], 26 parameters, 870 s)

**baseline -> suggested**: base gain +20.8 pp share within target, -8.5 d median. Seed noise (sd of the gain, one seed): 4.25 pp, 0.95 d.

| Parameter | low / base / high | A share low..high | B share low..high | gain pp (low, high) | gain days (low, high) | swing pp | flags |
|---|---|---|---|---|---|---|---|
| clinic: slots per day (`resources.clinic.capacity_per_day`) | 5 / 7 / 9 | 2.6..16.0 | 5.6..37.2 | +3.0, +21.2 | -8.3, -8.4 | 18.2 |  |
| ct_scanner: slots per day (also the flowchart capacity overrides) (`resources.ct_scanner.capacity_per_day`) | 2 / 3 / 4 | 1.3..23.4 | 1.7..39.0 | +0.4, +15.6 | -5.0, -8.5 | 15.2 | queue blow-up |
| gp_assessment: P(positive), cancer conditions (`tests.gp_assessment.p_positive[cancer]`) | 0.3375 / 0.45 / 0.5625 | 16.9..19.1 | 30.3..40.3 | +13.4, +21.2 | -8.5, -9.3 | 7.8 |  |
| arrivals per day (county size) (`arrivals.rate_per_day`) | 39.6 / 44 / 48.4 | 26.6..14.5 | 38.8..20.3 | +12.2, +5.7 | -8.5, -8.5 | 6.5 |  |
| policy sample_choice: share bronch (rest ttnb), all flowcharts (`policy.sample_choice.bronch`) | 0.2625 / 0.35 / 0.4375 | 16.0..18.2 | 38.5..34.6 | +22.5, +16.4 | -9.1, -7.9 | 6.1 |  |
| ct_scanner: min_lead_days (`resources.ct_scanner.min_lead_days`) | 3.0 / 4 / 5.0 | 22.5..17.3 | 39.4..29.0 | +16.9, +11.7 | -8.8, -7.2 | 5.2 |  |
| ttnb_slot: slots per day (`resources.ttnb_slot.capacity_per_day`) | 1 / 1 / 2 | 16.4..20.8 | 37.2..36.8 | +20.8, +16.0 | -8.5, -8.7 | 4.8 |  |
| gp_represent: extra_wait median (`tests.gp_represent.extra_wait.median`) | 10.5 / 14 / 17.5 | 18.2..16.0 | 32.5..34.6 | +14.3, +18.6 | -9.6, -9.3 | 4.3 |  |
| pet_scanner: slots per day (also the flowchart capacity overrides) (`resources.pet_scanner.capacity_per_day`) | 1 / 1 / 2 | 16.4..26.0 | 37.2..42.4 | +20.8, +16.5 | -8.5, -9.2 | 4.3 |  |
| clinic: min_lead_days (`resources.clinic.min_lead_days`) | 9.0 / 12 / 15.0 | 24.2..14.3 | 41.1..27.7 | +16.9, +13.4 | -8.2, -7.9 | 3.5 |  |
| pet_scanner: min_lead_days (`resources.pet_scanner.min_lead_days`) | 3.0 / 4 / 5.0 | 19.5..15.6 | 40.7..33.8 | +21.2, +18.2 | -8.2, -8.8 | 3.0 |  |
| attribute location: share central (rest peripheral) (`attributes.location.central`) | 0.2625 / 0.35 / 0.4375 | 17.8..19.9 | 36.4..35.9 | +18.6, +16.0 | -9.6, -7.8 | 2.6 |  |
| gp_second_look: P(positive), cancer conditions (`tests.gp_second_look.p_positive[cancer]`) | 0.075 / 0.1 / 0.125 | 16.0..16.9 | 36.8..35.5 | +20.8, +18.6 | -9.0, -8.5 | 2.2 |  |
| nurse_assessment: P(positive), cancer conditions (`tests.nurse_assessment.p_positive[cancer]`) | 0.1125 / 0.15 / 0.1875 | 17.3..18.6 | 35.5..39.0 | +18.2, +20.4 | -9.0, -8.3 | 2.2 |  |
| treatment_booking: extra_wait median (`tests.treatment_booking.extra_wait.median`) | 3.0 / 4 / 5.0 | 19.5..15.6 | 41.1..35.1 | +21.6, +19.5 | -9.8, -7.9 | 2.2 |  |

**Joint draws (all parameters at once)**

| Pair | subset | draws | B beats A (share) | B faster (median) | gain pp p5 / median / p95 | gain days p5 / median / p95 |
|---|---|---|---|---|---|---|
| baseline>suggested | all | 16 | 100% | 100% | 8.0 / 16.5 / 21.4 | -9.6 / -8.6 / -7.4 |

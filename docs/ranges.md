# Ranges next to the headline numbers

Analysis outputs only; no simulation behaviour changed. Scripts: `docs/evidence_checks/` (`finland_suggested.py`, `norway_suggested.py`, `ranges_finland.py`, `ranges_norway.py`, then `render_docs.py`). Raw numbers: `docs/ranges_finland.json`, `docs/ranges_norway.json`. The headline numbers elsewhere are unchanged; this page says how far they move.

## Finland: today 18% to 33% within 90 days

The headline is the mean of two held-out cohorts (seeds 301 and 302, each about 18,800 patients and 254 cancers). Here is the same comparison on 12 independent cohorts (seeds 301 to 312); the accepted flowchart is the one the optimiser found, re-derived and checked against the bundle.

| Cohort | Today | Suggested | Gain, pp |
|---|---|---|---|
| 301 | 20.5% | 37.0% | 16.5 |
| 302 | 14.6% | 29.2% | 14.6 |
| 303 | 14.5% | 23.9% | 9.3 |
| 304 | 15.7% | 30.2% | 14.5 |
| 305 | 21.6% | 38.6% | 17.1 |
| 306 | 14.1% | 31.5% | 17.4 |
| 307 | 22.7% | 42.1% | 19.4 |
| 308 | 20.6% | 36.8% | 16.2 |
| 309 | 18.8% | 29.2% | 10.4 |
| 310 | 17.9% | 27.7% | 9.9 |
| 311 | 23.1% | 39.3% | 16.2 |
| 312 | 25.4% | 40.6% | 15.2 |

- Today ranges from 14% to 25% across cohorts (mean 19.1, sd 3.8 pp). The suggested change ranges from 24% to 42% (mean 33.9).
- The gain is 9.3 to 19.4 pp (mean 14.7, sd 3.2) and positive in 12 of 12 cohorts. By group: vague symptoms 7.0 to 17.2 pp, alarm symptoms 11.2 to 28.0 pp.
- Median days to treatment: today 99 to 108, suggested 92 to 101.
- **Reading.** Say "18% to 33%" only with "two cohorts" next to it. The level of the share moves by about 10 pp from cohort to cohort (cohorts have about 260 cancers); the size of the gain is stabler, about 15 pp. The training cohorts the search used show the same pattern (13% to 29% in the bundle).

### Sensitivity of the accepted Finnish changes (the comparison the older sensitivity files do not cover)

`pathway_sim.sensitivity` with the accepted flowchart as comparison B: 26 shortlisted assumption parameters varied one at a time (x0.75 / x1.25, integer capacities plus or minus one slot), seed 1, then 16 joint draws. Base gain at seed 1 is 20.8 pp and 8.5 days; seed-to-seed sd of the gain 4.25 pp (seeds [1, 2, 3]: [20.8, 15.0, 12.5] pp).

- One at a time: the gain stays positive in 26 of 26 parameters; the smallest is 0.4 pp (`resources.ct_scanner.capacity_per_day`, flagged unstable: True).
- Joint draws: the suggested change beats today in 100% of 16 draws, gain 8.0 to 21.4 pp (5th to 95th percentile; min 4.3, max 23.1), median 16.5 pp; median days -9.6 to -7.4.
- The gain nearly disappears when clinic or CT capacity is one slot lower (resources.ct_scanner.capacity_per_day low: 0.4 pp; clinic capacity low: 3.0 pp), the same capacity dependence the older sensitivity page found for the order-together pathway.
- The urgent booking leads, which carry the conditional 61%, do not move this gain: the accepted changes use no priority lane. What moves it is capacity at the clinic and CT, the share of cancers a GP sends on at first contact, and the arrival rate.

| Parameter (varied one at a time) | Low / base / high | Gain at low, pp | Gain at high, pp |
|---|---|---|---|
| `resources.clinic.capacity_per_day` | 5 / 7 / 9 | 3.0 | 21.2 |
| `resources.ct_scanner.capacity_per_day` | 2 / 3 / 4 | 0.4 | 15.6 |
| `tests.gp_assessment.p_positive[cancer]` | 0.3375 / 0.45 / 0.5625 | 13.4 | 21.2 |
| `arrivals.rate_per_day` | 39.6 / 44 / 48.4 | 12.2 | 5.7 |
| `policy.sample_choice.bronch` | 0.2625 / 0.35 / 0.4375 | 22.5 | 16.4 |
| `resources.ct_scanner.min_lead_days` | 3.0 / 4 / 5.0 | 16.9 | 11.7 |
| `resources.ttnb_slot.capacity_per_day` | 1 / 1 / 2 | 20.8 | 16.0 |
| `tests.gp_represent.extra_wait.median` | 10.5 / 14 / 17.5 | 14.3 | 18.6 |

Caveats: one seed per variant (single-seed noise about the sd above, so ranking among the smaller rows is not reliable); only the 26 default-shortlist assumptions are varied, out of the assumption parameters listed in `docs/ledger.md`; the Finnish scenario is not calibrated to Finnish capacity data, so this is robustness to our assumptions, not to the real county.

## Norway: 40 observed, 80 authors' pathway, 88 optimiser with the faster scanner, 67 without

Two sources of uncertainty, both for the flowcharts the bundle reports (the two optimiser flowcharts were found once, on the best-fit calibration).

| Flowchart | Bundle (3 x 1000 patients) | 100-patient cohorts, central 95% (300 cohorts) | Across the 11 accepted calibration sets (3 x 1000 patients each), min to max |
|---|---|---|---|
| Observed pathway | 40.1% | 30 to 51% | 37 to 43% |
| Faster PET-CT only | 60.3% | 50 to 68% | 55 to 68% |
| Authors' pathway, simulated | 80.1% | 72 to 87% | 78 to 84% |
| Optimiser, faster scanner | 88.2% | 81 to 94% | 86 to 93% |
| Optimiser, no new equipment | 67.1% | 56 to 75% | 56 to 70% |

- A real cohort has 100 patients, so any single-hospital number carries about plus or minus 8 pp (central 95% range 72 to 87% for the authors' pathway); the published 95% intervals (observed 31 to 50, authors' 72 to 87) are of that size and our 100-patient ranges match them.
- Across the 11 calibration sets that all reproduce the observed pathway (37 to 43% in this check; the fit tolerance is plus or minus 4 pp), the authors' pathway is 78 to 84%, the optimiser with the faster scanner 86 to 93%, and without new equipment 56 to 70%. The no-new-equipment number is the less certain of the two optimiser numbers. The ordering (optimiser above the authors' pathway above faster PET-CT above observed) holds in 11 of 11 sets.
- The optimiser flowcharts were found under the best-fit calibration and evaluated under the others unchanged, so these ranges are slightly pessimistic for the optimiser (a re-search per calibration might find a better flowchart).
- Disclosures from the review stand (PET-CT at triage carried into the authors' pathway: 66% if PET-CT is ordered at the first visit; the menu of about 69 changes contained the authors' changes).

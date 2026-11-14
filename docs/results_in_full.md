# Results in full (moved from the README)

This is the long results text that used to sit in `README.md`. It is kept whole. The README now carries a short table instead.
The single source for every number said aloud is `docs/pitch/filled/numbers_sheet.md` (read its wording rules and status column);
if this page and the sheet disagree, the sheet is right. All patients are synthetic. Say "our synthetic Finnish county", not "Finland".

## Headline results so far (held-out patients)

| Norwegian pathway (Stokstad et al. 2019) | Published | Simulated |
|---|---|---|
| Observed pathway (calibrated) | 40% within 42 d | 40% |
| Faster PET-CT only | 48% (not significant) | 60% at the best fit (we over-predict; 50 to 74% across settings) |
| Authors' reordered pathway | 80% (a model estimate) | 80% at the best fit (predicted, not fitted), but 62 to 86% across all 184 settings that fit the observed pathway, typically about 75%; about two thirds of settings fall inside the published 72 to 87%. The ranking (reordering beats a faster scanner beats today) holds in all 184. The calibrated "PET-CT ordered at triage" practice is carried into it; with PET-CT ordered at the first visit it would be 66% (`docs/review_checks/stokstad_pet_triage_result.json`, `docs/validation.md` Robustness) |
| Optimiser, same premise as the authors | n/a | 88% at the best-fit setting: it finds the authors' three changes plus a fourth that needs a clinical check |
| Optimiser, no new equipment | n/a | 67% at the best-fit setting (56 to 70% across the first-grid settings) |

The Norwegian search chose from a menu of about 70 single changes that included each of the authors' changes as one edit; it was
not told which. Its fourth change plans tissue sampling at referral triage, before a specialist has seen the patient, and needs a
clinical check. The lead over the authors' 80% comes from the fourth change. How the optimiser's results hold on all 184 settings and without the fourth change is being checked and is not claimed yet. Numbers for every spoken or shown claim: `docs/pitch/filled/numbers_sheet.md`.

| Finnish synthetic county (held-out, 90-day provisional target) | Within 90 d | Note |
|---|---|---|
| Today | 18% | |
| Optimiser: two reorders, no new equipment, no priority lane | 33% | reserve the treatment slot at tumour-board referral; book the specialist visit on referral arrival |
| Same extra CT and PET-CT capacity, today's order | 31% | capacity-only control |
| Hand-written order-together pathway | 54% | needs 3 PET-CT slots |
| **Conditional:** urgent booking for every referred patient | 18% / 44% / 61% | at 0 / 50 / 100% of the assumed urgent booking-lead reduction; depends entirely on assumed leads, not a recommendation |

Finnish capacities and all booking leads are assumptions calibrated to published waits. The 90-day target is provisional. Counts of
sourced and assumed scenario inputs are in `docs/pitch/filled/data_transparency.md`. The parameter table in the demo lists evidence
and calibration targets, not only simulator inputs.

Ranges (`docs/ranges.md`): the two held-out cohorts are the headline. Across 12 cohorts of the same size today's share is 14% to 25% and the suggested change's 24% to 42%; the gain is 9 to 19 points and positive in all 12 cohorts, and in all 16 joint draws of the assumed inputs. On 100-patient cohorts (the size of the real Norwegian study) the Norwegian numbers are 40% (30 to 51), 80% (72 to 87), 88% (81 to 94) and 67% (56 to 75). The evidence ledger (`docs/ledger.md`, from `python3 params/ledger.py`) counts sourced and assumed scenario inputs from the files; `docs/booking_vs_queue.md` splits booking time from queueing; `docs/capacity_probe.md` has the one-more-slot table with its range.

Missed cancers do not change in any accepted Finnish change; the tissue-confirmed guardrail is active in Finland (bronchoscopy and
needle biopsy count as confirming) and blocks "faster by skipping tissue sampling". In the Norwegian check every patient has cancer
and there is no discharge exit, so the missed-cancer check is vacuous there.


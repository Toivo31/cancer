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
| Optimiser from today's pathway, no new equipment (D68: the only optimiser result reported) | n/a | 67% at the best-fit setting; 48 to 77% across the 184 settings (median 65), against 36 to 44% for today's pathway |

The Norwegian search chose from a menu of about 70 single changes that included each of the authors' changes as one edit; it was
not told which. Its fourth change plans tissue sampling at referral triage, before a specialist has seen the patient, and needs a
clinical check. As a plausibility check (D62, D68): starting from today's pathway, with no new equipment and without being told the answer, the optimiser arrived at the authors' three timing changes plus one overlapping change that needs a clinical check. It did not improve on the authors' redesign. It is not a like-for-like pair with the authors' 80%, which includes the shorter PET-CT wait. Without the fourth change the optimiser still gives 65% at the best fit; the fourth change is worth 2 to 4 points. Without new equipment the optimiser beats today's pathway in 184 of 184 settings but beats the faster scanner alone in only 128 of 184. One sensitivity check: a stricter reading of the paper's text gives a median of 79% over the 184 settings (64 to 90; 139 of 184 inside the published 72 to 87%); we read summaries of the paper, not its figures, the observed pathway was not recalibrated, and the shipped scenario is unchanged (open decision for the human lead). Numbers for every spoken or shown claim: `docs/pitch/filled/numbers_sheet.md`.

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


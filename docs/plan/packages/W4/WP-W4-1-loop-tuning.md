# WP-W4-1: Tune the encounter loop and produce the second finding

| | |
|---|---|
| Component | C8; decision D48 (two findings) |
| Size | M · Model: Sonnet |
| Needs | merged on `overnight/sim`: encounter loop (`pathway_sim/encounter.py`, `scenarios/finland_encounter*.yaml`), care content (`catalogue/lung-primary-care/care.yaml`, `docs/research/catalogue/care_practice.md` section 11 has proposed decision-table numbers) |
| Owned paths | `scenarios/finland_encounter.yaml`, `scenarios/finland_encounter_policy.yaml`, `scenarios/finland_encounter_resources.yaml`, `catalogue/lung-primary-care/care.yaml` (behaviour numbers and notes only), `scripts/encounter_report.py` (new), `docs/encounter_results.md` (new), `docs/review_checks/encounter_*.json`, `tests/test_encounter_results.py` (new) |
| Do not edit | `pathway_sim/` code (post a PROBLEM to claude-code@tuomas/architect if the engine needs a fix), the calibrated Finnish and Norwegian scenarios |
| Review required | yes: headline-adjacent numbers |

## Outcome

1. **Decision tables filled** from `care_practice.md` section 11 (fix ids to match the merged care file), each row with source or `assumption`.
2. **Consistency with the calibrated model.** The calibrated Finnish chain (`scenarios/finland_lung.yaml`, flowchart `baseline`) is our best estimate of what Finnish care produces for cancer patients today. Tune the *assumed* numbers of the loop (decision-table rows, return behaviour, `natural_course`) so that, for cancer patients, the loop reproduces the chain's time from first contact to referral (median and share within 14/28/42 days) and its share treated within the target, within a stated tolerance. Then the loop explains the same delays mechanistically. Never change a sourced number to fit; record every tuned number and what it was before. If it cannot be reached with plausible values, stop and report the gap.
3. **Statistical power.** 26 cancers per 2 000 patients is too noisy. Use larger runs (time them; aim under 2 minutes) or several seeds, and report intervals across seeds. Add a warm-up period if the world supports it, or report that queues start empty.
4. **The second finding** (`docs/encounter_results.md`, `scripts/encounter_report.py` reproduces it with one command): for cancers, the time lost in primary care before referral; how often a cancer was first treated as something else and how much time that cost; visits and episodes before referral; how these differ by patient group (age band, sex, smoking, region), with intervals across seeds and the caveat that primary-care behaviour is assumed. Also the worried-well and benign patients: tests and cost per patient. 3 to 5 headline sentences a pitch can quote, each with its number and interval.
5. A test that pins the tuned run's key numbers within tolerance (fast: small n) so later changes show up in the gate.

## Acceptance

- [ ] `python scripts/encounter_report.py` writes `docs/review_checks/encounter_results.json` and prints the tables; under 3 minutes.
- [ ] Consistency targets met within the stated tolerance, or the gap reported with the closest plausible setting.
- [ ] `scripts/gate.sh` green.

## Report (builder fills in)

# Equal Care Across Finland: lung cancer pathway simulator and optimiser

Junction 2026, AstraZeneca challenge. Synthetic patients run through a configurable diagnostic
flowchart. An optimiser proposes a better order of steps using only information a clinic would
see. The same patients are rerun to accept a change, and held-out patients are used to report it.
Plan: `docs/master_plan.md`. Interface contract: `docs/architecture.md`. Open choices: `docs/decisions.md`.

## Quick start

```bash
pip install -r requirements.txt            # pyyaml, numpy
python -m pytest -q                        # all tests, ~35 s
python -m pathway_sim demo                 # full loop -> demo/data/demo_bundle.json (~9 min; `--quick` ~2.5 min)
open demo/index.html                       # the dashboard (works offline, 6 screens, keys 1-6)
```

## What is where

| Path | What |
|---|---|
| `pathway_sim/` | Event engine, scenario loader, synthetic patients, policies, metrics, calibration, CLI |
| `optimiser/` | Revealed-information proposals → rerun acceptance with guardrails → held-out report |
| `decision_model/` | Jev-type correction model vs dot-product baseline (numpy); `ModelPolicy` |
| `scenarios/` | `stokstad.yaml` (Norwegian validation), `finland_lung.yaml` (Finnish synthetic), `generated/` (calibrated) |
| `params/` | Every number with its source (`sources.yaml`) or tagged `assumption`; `docs/parameters.md` |
| `demo/` | Static dashboard + `export.py` that builds its data from real runs |
| `docs/` | Plan, contract, decisions, validation, parameters, pitch material (`docs/pitch/`) |
| `technique_classifier/` | Separate deliverable (Hostinger / clinical notes); not used here |

## Common commands

```bash
# one flowchart, one cohort: on-time share, median, where the waiting is
python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed --n 1000

# compare all flowcharts in a scenario, averaged over seeds
python -m pathway_sim compare scenarios/generated/stokstad_calibrated.yaml --n 100 --seeds 1-50

# calibrate unsourced parameters on the observed pathway, predict the others
python -m pathway_sim.calibrate scenarios/stokstad.yaml --n 2000 --out docs/validation_results.json

# optimiser, blind, from the observed order with the faster PET-CT scanner
python -m optimiser scenarios/generated/stokstad_calibrated.yaml --start faster_pet --out runs/opt.json

# decision model benchmark (correction model vs dot-product)
python -m decision_model.benchmark --quick
```

## Headline results so far (held-out patients)

| Norwegian pathway (Stokstad et al. 2019) | Published | Simulated |
|---|---|---|
| Observed pathway (calibrated) | 40% within 42 d | 40% |
| Faster PET-CT only | 48% | 60% (we over-predict, see `docs/validation.md`) |
| Authors' reordered pathway | 80% | 80% (predicted, not fitted; the calibrated "PET-CT ordered at triage" practice is carried into it, with PET-CT ordered at the first visit it would be 66%, `docs/review_checks/stokstad_pet_triage_result.json`) |
| Optimiser, same premise as the authors | n/a | 88%: it finds the authors' three changes plus one |
| Optimiser, no new equipment | n/a | 67% |

The Norwegian search chose from a menu of about 70 single changes that included each of the authors' changes as one edit; it was
not told which. Its fourth change plans tissue sampling at referral triage, before a specialist has seen the patient, and needs a
clinical check.

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

Missed cancers do not change in any accepted Finnish change; the tissue-confirmed guardrail is active in Finland (bronchoscopy and
needle biopsy count as confirming) and blocks "faster by skipping tissue sampling". In the Norwegian check every patient has cancer
and there is no discharge exit, so the missed-cancer check is vacuous there.

## How a scenario is written

See `scenarios/stokstad.yaml` (commented) and `docs/architecture.md`. A flowchart is a DAG of
steps with `after` / `after_any` / `after_optional` prerequisites, guards (`when:`) on revealed
results, `choice` nodes decided by a policy, and `exit` nodes. Resources are `server`
(capacity queue), `delay` (published wait distribution) or `batch` (weekly tumour board).

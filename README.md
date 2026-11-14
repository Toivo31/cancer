# Equal Care Across Finland: lung cancer pathway simulator and optimiser

Junction 2026, AstraZeneca challenge. Synthetic patients run through a configurable diagnostic
flowchart. An optimiser proposes a better order of steps using only information a clinic would
see. The same patients are rerun to accept a change, and held-out patients are used to report it.
Plan: `docs/master_plan.md`. Interface contract: `docs/architecture.md`. Open choices: `docs/decisions.md`.

## Quick start

```bash
pip install -r requirements.txt            # pyyaml, numpy
python -m pytest -q                        # all tests, ~3 s
python -m pathway_sim demo                 # full loop -> demo/data/demo_bundle.json (~1 min)
open demo/index.html                       # the dashboard (works offline, keys 1-4)
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
| Authors' reordered pathway | 80% | 80% (predicted, not fitted) |
| Optimiser, blind, same premise as the authors | n/a | 88%: it finds the authors' three changes plus one |
| Optimiser, no new equipment | n/a | 67% |

No missed cancers and no extra tests in any accepted change. The guardrails also block "faster by
skipping tissue sampling".

## How a scenario is written

See `scenarios/stokstad.yaml` (commented) and `docs/architecture.md`. A flowchart is a DAG of
steps with `after` / `after_any` / `after_optional` prerequisites, guards (`when:`) on revealed
results, `choice` nodes decided by a policy, and `exit` nodes. Resources are `server`
(capacity queue), `delay` (published wait distribution) or `batch` (weekly tumour board).

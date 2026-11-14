# Equal Care Across Finland: lung cancer pathway simulator and optimiser

**Start here:** `open demo/start.html` shows the demo in order (six steps, each with the one result its screen proves; numbers are read from the data bundles). Presenter script: `docs/demo_path.md`. After regenerating bundles, run `python demo/export_start.py`.

Junction 2026, AstraZeneca challenge. Synthetic patients run through a configurable diagnostic
flowchart. An optimiser proposes a better order of steps using only information a clinic would
see. The same patients are rerun to accept a change, and held-out patients are used to report it.
Plan: `docs/master_plan.md`. Interface contract: `docs/architecture.md`. Open choices: `docs/decisions.md`.

**Where this is going:** an online platform (build a flowchart, attach the JEV decision model, train, simulate, optimise, rerun). Plan, specs and tickets: `docs/platform/`.

## Quick start

```bash
pip install -r requirements.txt            # pyyaml, numpy
python -m pytest -q                        # all tests, about 2 min (660+ tests)
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

# optimiser, blind to the hidden diagnosis, from the observed order with the faster PET-CT scanner
python -m optimiser scenarios/generated/stokstad_calibrated.yaml --start faster_pet --out runs/opt.json

# decision model benchmark (correction model vs dot-product)
python -m decision_model.benchmark --quick
```

### Decisions through JEV (docs/platform/specs/02-jev-interface.md)

Decision points ask a backend for a probability per option; the simulator draws the choice (`sample`,
default) or takes the most likely one (`argmax`). Without `--jev` the rule policy runs exactly as before.

```bash
# stub with hardcoded probabilities (migrated from the scenario's mix / rules / prefer): same results as today
python -m pathway_sim run scenarios/finland_lung.yaml --n 5000 --jev stub
# change one probability and watch the run move (others in that row are rescaled)
python -m pathway_sim run scenarios/finland_lung.yaml --n 5000 --jev stub --set first_contact.nurse_visit=0.9
python -m pathway_sim run scenarios/finland_lung.yaml --n 5000 --jev stub --decision-mode argmax

# the same through a JEV service: start the stub server, point the run at it
python -m jev.stub_server --scenario scenarios/finland_lung.yaml --flowchart baseline --port 8100 &
python -m pathway_sim run scenarios/finland_lung.yaml --n 5000 --jev http://127.0.0.1:8100
python -m pathway_sim run scenarios/finland_lung.yaml --n 5000 --jev http://127.0.0.1:8100 --on-error fallback_stub

# contract tests against any JEV address (without --jev-url they start the stub server)
python -m pytest tests/test_jev_contract.py --jev-url http://127.0.0.1:8100 --jev-point sample_choice --jev-options bronch,ttnb
```

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
clinical check. The lead over the authors' 80% comes from the fourth change. How the optimiser's results hold on all 184 settings and without the fourth change is being checked and is not claimed yet. Numbers for every spoken or shown claim: `docs/pitch/numbers_sheet.md`.

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

## How a scenario is written

See `scenarios/stokstad.yaml` (commented) and `docs/architecture.md`. A flowchart is a DAG of
steps with `after` / `after_any` / `after_optional` prerequisites, guards (`when:`) on revealed
results, `choice` nodes decided by a policy, and `exit` nodes. Resources are `server`
(capacity queue), `delay` (published wait distribution) or `batch` (weekly tumour board).

## Decision model integration for the demo team

Read [the teammate setup guide](decision_api/README.md) or give
[the integration prompt](decision_api/INTEGRATION_PROMPT.md) to your coding model.
The follow-up [shared-Nemotron refinement handoff](decision_api/REASONING_HANDOFF.md)
adds the optional token-budget and patient-tool design; it is off by default.

```bash
python3 -m decision_api.server
```

Open http://127.0.0.1:8771/decision. Medical-dataset pictures and recorded model
examples work immediately, without credentials, uploads or GPU usage. A backend
key enables an explicit live call to the separately hosted checkpoint1138 model.
The JavaScript client and optional review component can be reused in your own UI.

## Existing project demo

```bash
python3 -m pip install -r requirements.txt
python3 -m note_reader.server
```

Open http://127.0.0.1:8770 for the flowchart demo, `/note` for the note reader,
`/report/` for the dashboard and `/decision` for the decision-model panel.
Simulator estimates and model candidate scores are separate quantities.
All model proposals require human review. See the integration guide for the
prototype's limitations and the difference between live and saved examples.

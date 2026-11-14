# L1 Architecture

Read `00-vision.md` first. This file names the components, draws their boundaries, and lists the
contracts and invariants. Each component has its own file in `components/`.

## Component map

```
                         ┌──────────────────────────────┐
                         │ C2 CLINICAL CATALOGUE (data) │  conditions, hidden variables,
                         │ catalogue/*.yaml + sources   │  tests with accuracy, populations
                         └──────────────┬───────────────┘
                                        │ catalogue contract
                         ┌──────────────▼───────────────┐
                         │ C1 PATIENT ENGINE            │  sample cards, pre-draw every test
                         │ patient_engine/              │  result, store cohorts, narratives
                         └──────────────┬───────────────┘
                                        │ cohort + reveal contract
┌───────────────────┐    ┌──────────────▼───────────────┐    ┌───────────────────────────┐
│ C4 DECISION LAYER │◄──►│ C3 SIMULATION                │───►│ C5 OPTIMISER              │
│ jev/              │    │ pathway_sim/                 │    │ optimiser/                │
│ fixed, matrix,    │    │ flowchart, queues, reveal,   │◄───│ order of steps + decision │
│ score, JEV (HTTP) │    │ run log, metrics, flow view  │    │ criteria, guardrails      │
└───────────────────┘    └──────────────┬───────────────┘    └───────────────────────────┘
   decision contract                    │ run log / flow / metrics contracts
                         ┌──────────────▼───────────────┐
                         │ C6 PLATFORM                  │  service/ (API, jobs, storage),
                         │ service/ web/ deploy/        │  web/ (flowchart canvas, layers),
                         └──────────────┬───────────────┘  datasets and training, deployment
                                        │
                         ┌──────────────▼───────────────┐
                         │ C7 EVIDENCE                  │  sources, ledger, calibration,
                         │ params/ docs/                │  validation, ranges, honesty checks
                         └──────────────────────────────┘
```

| ID | Component | Package | State on 14 Nov | Component file |
|---|---|---|---|---|
| C1 | Patient engine | `patient_engine/` (new) | Not started. Today's generator is `pathway_sim/patients.py` (117 lines) | `components/C1-patient-engine.md` |
| C2 | Clinical catalogue | `catalogue/` (new, data) + `params/sources.yaml` | Partly exists inside scenario YAML and `params/` | `components/C2-clinical-catalogue.md` |
| C3 | Simulation | `pathway_sim/` | Built and tested; needs changes for typed, multi-variable reveals | `components/C3-simulation.md` |
| C4 | Decision layer | `jev/` | Contract, stub tables, HTTP backend built; decision matrix over revealed variables and score policy to add | `components/C4-decision-layer.md` |
| C5 | Optimiser | `optimiser/` | Order-of-steps search built; decision-criteria optimisation to design and build | `components/C5-optimiser.md` |
| C6 | Platform | `service/`, `web/`, `deploy/`, `demo/` | Built in the first wave (see `04-status.md`) | `components/C6-platform.md` |
| C7 | Evidence | `params/`, `docs/` | Exists; ledger and ranges in progress | `components/C7-evidence.md` |

Other people's areas, outside this plan but connected: `technique_classifier/` and `note_reader/`
(Eemeli) read clinical notes, which C1's narratives can supply; `video/dots/` and `live_demo/`
(Eemeli) show flows. See the area map at the top of the agent channel.

## Data flow, with the information boundary

```
catalogue ──► generator ──► PATIENT CARD ─────────────────────────────────────────────┐
                            ├─ background        (visible from arrival)                │
                            ├─ presenting        (what the patient says at first contact)
                            ├─ hidden.condition, hidden.state      ┐                   │
                            ├─ hidden.findings (true symptoms…)    │ HIDDEN SIDE       │ scoring
                            └─ observations[test][attempt]         ┘                   │ only
                                         │                                             │
                              reveal(test, attempt)  ◄── a flowchart step performs it  │
                                         ▼                                             ▼
                            REVEALED RECORD (per patient, per run)                 OUTCOMES
                            background + presenting + revealed observations        missed cancer,
                                         │                                         correct treatment,
                 ┌───────────────────────┼─────────────────────────┐               time, cost, harm
                 ▼                       ▼                         ▼
          decision layer          guards / rules            optimiser proposals
          (C4)                    in the flowchart (C3)     (C5)
```

Everything left of and above the reveal line is the **hidden side**. Everything below it is the
**revealed side**. Code on the revealed side receives objects that do not contain hidden fields at
all (separate types, not a flag), so a leak is a type error or a failed test, not a matter of care.

## Contracts

A contract is a versioned data shape or call signature with a written description, JSON examples
and a contract test. A component may change its insides freely; changing a contract needs the
architect and a decisions-log row.

| Contract | Between | Defined in | State |
|---|---|---|---|
| **Catalogue format** `catalogue/1` | C2 → C1, C3 | `components/C2`, then `catalogue/README.md` | to write |
| **Patient card** `card/1` | C1 → C3, C6, note reader | `components/C1`, then `patient_engine/README.md` | to write |
| **Cohort** `cohort/1` (manifest + storage) | C1 → C3, C6 | `components/C1` | to write |
| **Reveal API** | C1 → C3 | `components/C1`, section "Reveal" | to write; today it is `Patient.results[test][attempt]` |
| **Flowchart document** `flowchart/1`, **world document** | C6 ↔ C3 | `docs/platform/specs/01-flowchart-model.md`, `pathway_sim/documents.py` | built |
| **Decision contract** (`/v1/decide`) | C3 ↔ C4 | `docs/platform/specs/02-jev-interface.md`, `jev/contract.py` | built; context gains typed revealed variables |
| **Run log** and **metrics** | C3 → C5, C6 | `docs/architecture.md` | built |
| **Flow view** `flow/1` | C3 → C6 | `docs/platform/flow-format.md` | built |
| **Problem list** (validation) | C3 → C6 | `pathway_sim/problems.py` | built |
| **Service API** | C6 web ↔ service | `docs/platform/specs/03-service-api.md`, `service/README.md` | built |
| **Dataset rows** and **trainer** | C4 ↔ C6 | `docs/platform/specs/06-datasets-training.md`, `jev/dataset.py` | in progress |
| **Optimisation result** (changes, evidence, held-out numbers) | C5 → C6 | `docs/platform/specs/05-optimise-rerun.md` | built; gains decision-criteria changes |

## Invariants (every change must keep these; reviewers check them)

| # | Invariant | How it is checked |
|---|---|---|
| I1 | No hidden field reaches the decision layer, a guard, the optimiser's proposal step, or a narrative shown before the fact is revealed | Type separation; a test that scrambles hidden truth after a run and gets identical decisions and proposals (exists for the optimiser: `test_proposal_scores_ignore_hidden_truth`) |
| I2 | Same (cohort, flowchart, policy, seeds) gives a byte-identical run log | Determinism tests |
| I3 | Changing the flowchart does not change any patient's card or any pre-drawn draw | Common-random-number tests: a patient who takes the same test in two flowcharts gets the same result |
| I4 | Every number the simulation uses has a source id or the word `assumption`, and a grade | Catalogue validator; the ledger (`params/ledger.py`) |
| I5 | Shipped scenarios keep their published check: Norway observed about 40% within 42 days | `docs/validation.md`, calibration test |
| I6 | The optimiser accepts a change only on training patients and reports it on held-out patients, and never accepts more missed cancers than the baseline | Optimiser tests |
| I7 | No `eval`, `exec`, unsafe YAML load or pickle of user input anywhere | Test in `tests/test_expr.py`; security review |
| I8 | Synthetic data only, and the user interface says so | Review |

## Repo layout (target)

```
catalogue/            C2  conditions.yaml, variables.yaml, tests.yaml, populations/*.yaml, README.md
patient_engine/       C1  card.py, catalogue.py, sample.py, observe.py, cohort.py, narrative.py, adapter.py, checks.py
pathway_sim/          C3  engine, scenario, documents, expr, validate, flow, metrics
jev/                  C4  contract, adapter, stub (tables), matrix, score, http backend, dataset, training
optimiser/            C5  analysis, edits (order), criteria (decision rules), search, report
service/  web/  deploy/  demo/      C6
params/  docs/        C7
scenarios/            shipped worlds and flowcharts (YAML), incl. generated/calibrated ones
tests/                one folder or prefix per component; tests/contracts/ for contract tests
docs/plan/            this framework
```

## Technology choices already made (change only through the decisions log)

Python 3 standard library plus numpy and pyyaml for the libraries; FastAPI, SQLite and gzip JSON
blobs for the service; React, TypeScript and React Flow for the web app; no build step for
`demo/flow.html`; one process per job; an OpenAI-compatible endpoint for language-model calls,
standard library only, always optional with an offline fallback.

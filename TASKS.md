# Overnight task queue (14–15 Nov)

Contract: `docs/architecture.md`. Provisional choices: `docs/decisions.md`.
Blockers: `BLOCKERS.md`. Branch: `overnight/sim`. Each track works on its own
branch and gets merged in. Run all tests with `python -m pytest -q`.

## Track 0: setup
- [x] T0.1 Branch, contract doc, task queue, decisions log, blockers log

## Track A: core simulator (`pathway_sim/`), critical path
- [ ] A1 Distributions with common random numbers (`dists.py`)
- [ ] A2 Scenario + flowchart loader with validation (`scenario.py`)
- [ ] A3 Patient generator with hidden results, deterministic by seed (`patients.py`)
- [ ] A4 Event engine: server / delay / batch resources, guards, choice, retry, parallel (`engine.py`)
- [ ] A5 RunLog + metrics incl. stage/node breakdown and group split (`metrics.py`)
- [ ] A6 RulePolicy + Policy protocol (`policy.py`)
- [ ] A7 CLI `python -m pathway_sim run scenarios/x.yaml --flowchart baseline` (`__main__.py`)
- [ ] A8 Tests: determinism, queue sanity (M/M/1-ish), guards, parallel, missed-cancer accounting

## Track V: Stokstad validation scenario
- [ ] V1 `scenarios/stokstad.yaml`: observed, faster-PET, optimal flowcharts, all cancer, delay mode
- [ ] V2 Calibration script + test: observed ≈ 40% / median ≈ 46.5 d; faster PET ≈ 48%; optimal ≈ 80%
- [ ] V3 Write calibration note (what matched, what was assumed) in `docs/validation.md`

## Track P: parameters and sources (`params/`)
- [ ] P1 `params/sources.yaml`: source registry (id, citation, url, what it supports)
- [ ] P2 Stokstad pathway parameters from accessible sources (abstract, thesis, related papers)
- [ ] P3 Finnish lung pathway parameters: waits, CT access, nurse first contact, prevalence in symptomatic patients
- [ ] P4 Test accuracy table (CXR, LDCT, PET-CT, bronchoscopy, EBUS, TTNB) with sources
- [ ] P5 `docs/parameters.md` human-readable table, every number with source or `assumption`

## Track F: Finnish synthetic scenario
- [ ] F1 `scenarios/finland_lung.yaml`: primary care → referral → diagnostics → treatment, capacity queues, realistic prevalence, two presentation groups
- [ ] F2 Baseline run sanity: queues form where expected, missed cancers plausible
- [ ] F3 Equity split by presentation group in output

## Track O: optimiser (`optimiser/`)
- [ ] O1 Revealed-information log analysis: per (context, test) yield incl. non-cancer resolution
- [ ] O2 Flowchart edit operators: move earlier, parallelise, fast-track, swap choice preference
- [ ] O3 Search: propose → rerun same patients (CRN) → accept if faster within guardrails
- [ ] O4 Held-out evaluation on fresh patients; selection-bias guard
- [ ] O5 Blind Stokstad test: optimiser starts from observed pathway, report what it finds vs authors' pathway
- [ ] O6 Tests

## Track D: decision model (`decision_model/`)
- [ ] D1 Dot-product baseline and correction-model (Jev-type) in numpy or torch
- [ ] D2 Training data from simulator run logs (imitate accepted policy) + synthetic comparison task
- [ ] D3 Benchmark: accuracy vs baseline on a node where comparing options matters; compute cost of a second question
- [ ] D4 `ModelPolicy` implementing `Policy`; plug into simulator
- [ ] D5 Tests + `decision_model/README.md`

## Track UI: demo dashboard (`demo/`)
- [ ] U1 Static `demo/index.html` reading `data/demo_bundle.json` (fixture first)
- [ ] U2 Screen 1: number first (share on time today vs with change), plain words
- [ ] U3 Screen 2: where time is lost by stage (wait vs service), then the change that fixes it
- [ ] U4 Screen 3: flowchart before/after; Norwegian validation vs published numbers
- [ ] U5 Screen 4: equity split + assumptions/sources table
- [ ] U6 `demo/export.py` building the bundle from real runs

## Track E: evidence, pitch, docs
- [ ] E1 `docs/pitch/evidence_brief.md`: sourced claims, Goal 3 indicator, gap located in the pathway
- [ ] E2 Equity section: who waits longer (non-specific symptoms, nurse-first, CT access) with sources
- [ ] E3 National-level recommendation draft (actionable, sourced)
- [ ] E4 Two-minute video script + deck outline aligned with judging criteria
- [ ] E5 Data quality & transparency statement (section 8 OPEN item)

## Track I: integration
- [ ] I1 Merge tracks, full test suite green
- [ ] I2 `python -m pathway_sim demo` end-to-end: generate → run → optimise → rerun → held-out → bundle
- [ ] I3 README with how to run simulator, optimiser, demo
- [ ] I4 Update `docs/master_plan.md` with decisions taken; reflect against judging criteria
- [ ] I5 Push `overnight/sim`, morning summary

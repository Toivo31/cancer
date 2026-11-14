# Overnight task queue (14–15 Nov)

Contract: `docs/architecture.md`. Provisional choices: `docs/decisions.md`.
Blockers: `BLOCKERS.md`. Branch: `overnight/sim`. Each track works on its own
branch and gets merged in. Run all tests with `python -m pytest -q`.

## Track 0: setup
- [x] T0.1 Branch, contract doc, task queue, decisions log, blockers log

## Track A: core simulator (`pathway_sim/`), critical path
- [x] A1 Distributions with common random numbers (`dists.py`)
- [x] A2 Scenario + flowchart loader with validation (`scenario.py`)
- [x] A3 Patient generator with hidden results, deterministic by seed (`patients.py`)
- [x] A4 Event engine: server / delay / batch resources, guards, choice, retry, parallel (`engine.py`)
- [x] A5 RunLog + metrics incl. stage/node breakdown and group split (`metrics.py`)
- [x] A6 RulePolicy + Policy protocol (`policy.py`)
- [x] A7 CLI `python -m pathway_sim run scenarios/x.yaml --flowchart baseline` (`__main__.py`)
- [x] A8 Tests: determinism, queue sanity (M/M/1-ish), guards, parallel, missed-cancer accounting

## Track V: Stokstad validation scenario
- [x] V1 `scenarios/stokstad.yaml`: observed, faster-PET, optimal flowcharts, all cancer, delay mode
- [x] V2 Calibration script + test: observed ≈ 40% / median ≈ 46.5 d; faster PET ≈ 48%; optimal ≈ 80%
- [x] V3 Write calibration note (what matched, what was assumed) in `docs/validation.md`

## Track P: parameters and sources (`params/`)
- [x] P1 `params/sources.yaml`: source registry (id, citation, url, what it supports)
- [x] P2 Stokstad pathway parameters from accessible sources (abstract, thesis, related papers)
- [x] P3 Finnish lung pathway parameters: waits, CT access, nurse first contact, prevalence in symptomatic patients
- [x] P4 Test accuracy table (CXR, LDCT, PET-CT, bronchoscopy, EBUS, TTNB) with sources
- [x] P5 `docs/parameters.md` human-readable table, every number with source or `assumption`

## Track F: Finnish synthetic scenario
- [x] F1 `scenarios/finland_lung.yaml`: primary care → referral → diagnostics → treatment, capacity queues, realistic prevalence, two presentation groups
- [x] F2 Baseline run sanity: queues form where expected, missed cancers plausible
- [x] F3 Equity split by presentation group in output

## Track O: optimiser (`optimiser/`)
- [x] O1 Revealed-information log analysis: per (context, test) yield incl. non-cancer resolution
- [x] O2 Flowchart edit operators: move earlier, parallelise, fast-track, swap choice preference
- [x] O3 Search: propose → rerun same patients (CRN) → accept if faster within guardrails
- [x] O4 Held-out evaluation on fresh patients; selection-bias guard
- [x] O5 Blind Stokstad test: optimiser starts from observed pathway, report what it finds vs authors' pathway
- [x] O6 Tests

## Track D: decision model (`decision_model/`)
- [x] D1 Dot-product baseline and correction-model (Jev-type) in numpy or torch
- [x] D2 Training data from simulator run logs (imitate accepted policy) + synthetic comparison task
- [x] D3 Benchmark: accuracy vs baseline on a node where comparing options matters; compute cost of a second question
- [x] D4 `ModelPolicy` implementing `Policy`; plug into simulator
- [x] D5 Tests + `decision_model/README.md`

## Track UI: demo dashboard (`demo/`)
- [x] U1 Static `demo/index.html` reading `data/demo_bundle.json` (fixture first)
- [x] U2 Screen 1: number first (share on time today vs with change), plain words
- [x] U3 Screen 2: where time is lost by stage (wait vs service), then the change that fixes it
- [x] U4 Screen 3: flowchart before/after; Norwegian validation vs published numbers
- [x] U5 Screen 4: equity split + assumptions/sources table
- [x] U6 `demo/export.py` building the bundle from real runs

## Track E: evidence, pitch, docs
- [x] E1 `docs/pitch/evidence_brief.md`: sourced claims, Goal 3 indicator, gap located in the pathway
- [x] E2 Equity section: who waits longer (non-specific symptoms, nurse-first, CT access) with sources
- [x] E3 National-level recommendation draft (actionable, sourced)
- [x] E4 Two-minute video script + deck outline aligned with judging criteria
- [x] E5 Data quality & transparency statement (section 8 OPEN item)

## Follow-ups found overnight (not blocking the demo)
- [x] D6 (wave 2, track model2) Decision model: add revealed attributes (e.g. tumour location) to the context so it can learn the sampling-method choice; run it as `--policy model` at one choice node vs the rule policy and vs dot-product (the architecture-proof node, open Q12)
- [x] V4 (wave 2, track sens) Stokstad: model "incomplete workup at tumour board -> re-discussed next week" (16 patients) and check whether the faster-PET over-prediction shrinks
- [x] V5 Bootstrap 100-patient cohorts for CIs on simulated shares
- [x] U7 Dashboard: show the capacity probe ("one more slot per day here gains X pp") and the optimiser's step-by-step evidence

- [x] E6 (wave 2, track pitch2) Fill `[[placeholders]]` in `docs/pitch/data_transparency.md` and soften "wait longest" wording in the video script to the simulated numbers
- [x] F4 (wave 2, track sens) Finland: sensitivity run on the equity-gap assumption (non-specific imaging rate) and the 41% safety-net share before quoting numbers
- [x] F5 Engine: `p_positive` by presentation group (done; re-runnable nodes for the safety net not done)
- [x] O7 Finland optimiser: resolved by noise-aware acceptance (GP-first change now rejected)

## Track I: integration
- [x] I1 Merge tracks, full test suite green
- [x] I2 `python -m pathway_sim demo` end-to-end: generate → run → optimise → rerun → held-out → bundle
- [x] I3 README with how to run simulator, optimiser, demo
- [x] I4 Update `docs/master_plan.md` with decisions taken; reflect against judging criteria
- [x] I5 Push `overnight/sim`, morning summary

## Wave 2 (14 Nov morning; budget raised)
- [x] W1 (model2) Decision model in the loop: learns the sampling-method choice from logged exploration (revealed info only), compared with rule / dot-product / random in full simulation
- [x] W2 (sens) Generic sensitivity analysis (`pathway_sim/sensitivity.py`): vary every `assumption` parameter, report effect on headline gains (tornado data) for both scenarios
- [x] W3 (sens) External qualitative check: UK rapid-CT finding (faster CXR->CT, unchanged time to treatment) reproduced in the Finnish scenario
- [x] W4 (ui2) Dashboard: step-by-step optimiser evidence ("why this change"), cumulative change view, capacity-vs-order comparison, sensitivity panel
- [x] W5 (pitch2) `docs/pitch/fill_numbers.py` fills every [[placeholder]] from the bundle; submission text; deck content; video script synced to real numbers
- [x] W6 (me) Optimiser: equity guardrail (no presentation group worse off), noise-aware acceptance (several training cohorts), two-step lookahead when no single change helps
- [x] W7 (me) Engine: p_positive by group; integration, export, master plan sync
- [x] W8 (review) Independent code + claims review of the whole branch before submission

## Platform (direction set 14 Nov)
Plan, specs and tickets for the online platform live in `docs/platform/` (`tickets.md` has the queue: M0 to M8). Not started; waiting on forks F1 to F7.

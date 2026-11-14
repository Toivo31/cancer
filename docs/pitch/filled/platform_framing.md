# Platform framing: what we say, and what is built (M8-5)

Use this when the pitch moves from "the demo" to "where it goes". Status is from `docs/platform/tickets.md` on the integration branch (bundle of 2026-11-14); anything not ticked there is planned, whatever branch it may be on.

## The framing in three sentences (about 20 seconds)

The demo is one scenario, but the engine behind it is a library: you describe a pathway as a flowchart, attach a decision model to its decision points, run synthetic patients through it, let an optimiser propose changes from what the steps revealed, and rerun the same patients on the changed pathway. Today that loop runs from the command line and a service API on our two scenarios (the Norwegian check and the synthetic Finnish county); the hosted editor is the next step, not something we are showing. The decision model sits behind a small contract, so the stub we use now can be replaced by a trained model or an external one without touching the simulator.

## Built and shown, built but not shown, planned

| Piece | Status | Evidence in the repo |
|---|---|---|
| Event engine, scenarios, optimiser with held-out reporting, Norwegian check, Finnish scenario | **Built, shown in the demo** | `pathway_sim/`, `optimiser/`, `demo/index.html` |
| Offline flowchart page: graph, flow, time and decision layers, patient trace, playback | **Built, can be shown** (precomputed logs, no server) | `demo/flow.html`, tickets M3-12, M3-13 |
| Decision contract (probability per option, sample or most-likely), stub backend, HTTP backend, local numpy backend | **Built**, not part of the headline numbers (shipped scenarios reproduce exactly through the stub) | `jev/`, tickets M1-1 to M1-8, M1-10 |
| Service API: projects, flowchart versions, validate, runs, optimisations, apply and rerun, flow endpoint | **Built** (API and tests), no web client yet | `service/`, tickets M2-1 to M2-11 |
| Evidence ledger (counts of sourced and assumed inputs, read from the scenario files) | **Built as a script and a table**, not yet a screen | `params/ledger.py`, `docs/ledger.md` |
| Capacity probe table, ranges next to the headlines | **Built as analysis outputs**, not yet a screen | `docs/capacity_probe.md`, `docs/ranges.md` |
| Dataset upload, trainers, model registry | Partly built on a separate branch, **not merged**; say "in progress" | tickets M6 (not ticked) |
| Web editor: drag-and-drop flowchart, decisions table, run and optimise panels, hosting | **Planned**; do not show mock-ups as working software | tickets M3 (except M3-12, M3-13), M4, M5, M7 |
| Synthetic patient engine: catalogue, cards, reveal handle, audit, training export | **Built**; 500 template-written and 35 model-written cards so far, all synthetic (the new result prompt (g2@2: the engine sets every value, the language model writes report text from the reported values only) has not yet been run on the real model; the 35 model-written cards in the repository use the old prompt g2@1, and their report text is rebuilt from values before any decider sees it); catalogue is a draft no clinician has read | `patient_engine/`, `catalogue/`, `libraries/`, `docs/synthetic_data_for_jev.md` |
| Primary-care encounter loop on those cards | **Built as a mechanism** with placeholder decision tables and assumed behaviour numbers; it reproduces the calibrated chain at the edge of the tolerances: 8 of 8 checks on the seeds it was tuned on, 6 of 8 on fresh seeds, 7 of 8 pooled over eight seeds; not a Finnish estimate | `pathway_sim/encounter.py`, `docs/encounter_results.md` |
| The team's fine-tuned decision model (JEV) connected to the decision nodes | **Connected** through an adapter and a step-through tool (`python -m jev.walk`); its scores are relative to the offered options; no headline number depends on it | `jev/birch.py`, `docs/platform/jev-birch.md` |
| A JEV trained or tested on real decision data | **Planned**; we have no real decision data, only synthetic | tickets M6-6, `docs/platform/README.md` |

## Honest lines for questions

- "Is this a platform?" It is an engine and an API with two scenarios and a read-only flowchart page. The editable web product is planned.
- "Does the decision model drive your results?" No. The headline runs use a rule policy and placeholder decision tables; the stub reproduces them exactly. Our own small decision-model benchmark matched the rule inside the loop. The team's JEV is connected and can be stepped through patient by patient, but we have not used it to produce any number we report.
- "Could a hospital use it with its own pathway?" The flowchart and world documents are plain JSON or YAML, and the validator lists every problem at once; getting real waits, capacities and test accuracies is the hard part, and the evidence ledger shows how little of the Finnish scenario rests on a source today (9 of 49 input blocks).
- "What would you build next?" Real county booking data first (it is the assumption the Finnish numbers lean on most), then the editor.

## What not to claim

- No hosted instance, no multi-user use, no authentication.
- No trained decision model driving a result, and no claim that a model trained on synthetic cards works on real patients.
- No Finnish number from the primary-care loop as a finding.
- No "works on any cancer": the two scenarios are lung cancer only.

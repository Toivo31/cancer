# Equal Care Pathways

Junction 2026, AstraZeneca challenge "Equal Care Across Finland".

We built a simulator of a hospital's lung cancer diagnostic pathway and an optimiser that searches for a better order of
care steps. Synthetic patients move through a **flowchart** of care steps with waits and limited capacity. The optimiser
proposes a change, reruns the same patients with it, keeps the change only if patients reach treatment sooner without
extra tests or missed cancers, and reports the result on **held-out** patients it never searched on. At each decision
point, a decision model (**JEV**, our model Birch) can rank the options from what a clinician would see.

All patients are synthetic. No clinician has reviewed any of it.

## Start here

| What | Where |
|---|---|
| The website (Manifesto, Simulation, JEV, Appendix) | `website/`. Run `python3 -m http.server 8780 --directory website/public` and open <http://localhost:8780> |
| Page text | `website/content/*.md`. After editing, run `python3 website/build_content.py` (needs `pip install markdown`) |
| The headline result, reproduced in about a minute | `python3 -m optimiser scenarios/generated/stokstad_calibrated.yaml --start observed` |
| Every number we quote, with its caveat | `docs/pitch/filled/numbers_sheet.md` |
| How we checked against a published hospital study | `docs/validation.md`, `docs/norway_case_study.md` |
| Design and decisions | `docs/master_plan.md`, `docs/architecture.md`, `docs/decisions.md` |

## The headline result

The pathway is rebuilt from a published Norwegian study (Stokstad et al. 2019, one university hospital). We fitted the
simulator to the study's observed pathway: 40% of patients start treatment within 42 days. Starting from that pathway,
with no new equipment, the optimiser keeps four changes:

1. Order the PET-CT scan at triage or the first visit, never late.
2. Plan tissue sampling when the referral is triaged, before the first hospital visit.
3. Order the exercise test early, together with the other tests.
4. Hold the tumour board while tissue sampling runs alongside.

On held-out patients the share treated within 42 days rises from **40.1% to 67.1%** at the best-fitting setting, and
from 36–44% to 48–77% across the 184 settings that fit today's pathway (median 65%). The study's authors reported 80%
for their own redesign, which also assumed a shorter PET-CT wait, so the two are not a like-for-like pair. Our result does
not improve on theirs.

What the result depends on: the simulator is calibrated to the published study (an uncalibrated run gives different
numbers); the decisions at each choice point follow rule tables fitted to observed practice, **not** JEV; and the
acceptance rerun uses the simulator's hidden truth, which in a real hospital would be a pilot.

## What is in the repository

| Folder | What it is |
|---|---|
| `website/` | The website: static pages, the embedded before-and-after animation (`public/sim/`), the live JEV test area, Modal deploy (`modal_app.py`) |
| `pathway_sim/` | The simulator: a discrete-event engine with appointment capacity, weekly tumour boards and published waiting-time distributions (`engine.py`), plus calibration and metrics |
| `optimiser/` | The search: propose, rerun, accept with guardrails, report on held-out patients (`search.py`, `edits.py`) |
| `scenarios/` | Pathways as YAML: `stokstad.yaml` (Norway), `generated/stokstad_calibrated.yaml` (fitted), `finland_lung.yaml` (a synthetic Finnish county) |
| `params/` | Parameters and their sources (`sources.yaml`) |
| `patient_engine/`, `catalogue/`, `populations/`, `libraries/` | Synthetic patients: hidden truth plus pre-written test results, the care catalogue, and saved patient libraries |
| `jev/` | Connects JEV (Birch) to the simulator's choice nodes (`flow_policy.py`, `birch.py`). Run on JEV: `python3 -m pathway_sim.jev_run --estimate` |
| `decision_api/`, `decision_model/` | The decision model's API and gateway (owned by the JEV owner), and an earlier small numpy model |
| `note_reader/`, `technique_classifier/` | Teammate tools for reading clinical notes and classifying techniques |
| `video/` | The video: script, how it is made |
| `docs/` | Plans, decisions, validation, evidence, pitch material |
| `tests/` | `python3 -m pytest -q` |
| `scripts/` | Helper scripts, including the agent channel `scripts/comms.py` |

**Superseded, kept for reference:** `demo/` (the earlier offline demo site), `web/` and `service/` (the flowchart editor
web app), `live_demo/`. The website in `website/` replaces them.

## JEV status

The simulator calls a pluggable policy at every choice node, and `jev/flow_policy.py` turns the patient's visible state
into a request for Birch, checking that no hidden information is sent. This has been run end to end against a mock of
the gateway. It has **not** yet been run against the real model, so no reported result uses JEV. What Birch was trained
on is not yet documented (`docs/platform/jev-birch.md`).

## Setup

```
pip install -r requirements.txt                  # simulator and optimiser
pip install -r service/requirements.txt          # needed by the service tests
pip install markdown                              # website/build_content.py
python3 -m pytest -q
```

API keys live in `.env` (see `.env.example`) and are never committed.

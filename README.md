# Equal Care Across Finland: lung cancer pathway simulator and optimiser

Junction 2026, AstraZeneca challenge. We built a simulator of the lung cancer diagnostic pathway. Synthetic patients move through a
**flowchart** (an editable diagram of care steps, each with waits and limited capacity). An optimiser proposes a better order of
steps using only what a clinic would see, accepts a change only if a rerun of the same patients is faster, and reports it on
**held-out** patients (patients the search never used). All patients are synthetic. No clinician has reviewed any of it.

## Open this first

| What | How | What it shows |
|---|---|---|
| Offline start page | open `demo/start.html` in a browser (no server) | Six steps, one result each, read from the data behind its screen: the gap, the primary-care loop, what reordering wins, why we trust the engine (Norway), the decision model, data and honesty. Presenter script: `docs/demo_path.md` |
| Web app | `uvicorn service.app:app --port 8000` after building `web/` (`docs/commands.md` section 4), open <http://localhost:8000> | Build or edit a flowchart, run it, optimise, rerun. Needs Node and the API requirements |
| Hosted demo | no address is recorded in this repo; the hosted page is planned as `live_demo/` served by `python3 -m note_reader.server` (see the teammate section below) | The teammate's flowchart demo, note reader and report |

If the start page's "Synthetic patients" card says "pending", run `python demo/export_cards.py` once (under a second).

## Results, with how sure we are

All numbers are from `docs/pitch/filled/numbers_sheet.md`, which also gives the exact sentence each may be used in. Status: **fitted** = tuned to it; **predicted** = computed with the fitted model, not tuned to it; **simulated** = a result inside our synthetic world.

| What | Number | Status | The caveat that goes with it |
|---|---|---|---|
| Norway, today's order (Stokstad et al. 2019, 100 patients, one hospital) | 40% treated within 42 days; paper 40% | fitted | The only thing fitted. A 100-patient cohort in our model gives 30 to 51% |
| Norway, the authors' reordered pathway | 80% at our best fit; 62 to 86% across all 184 settings that fit today's order, typically about 75% | predicted | The 80% is one point in a band, and the paper's 80% is itself a model estimate. With PET-CT ordered only at the first visit the best fit gives 66%. Never "matches" |
| Norway, ranking | reordering beats a faster scanner beats today, in 184 of 184 settings | predicted | Sizes are not supported to better than about 12 points. Trust the ranking, not the size |
| Norway, faster scanner alone | 60% at best fit (50 to 74%); paper 48% | predicted | A miss: we over-predict |
| Norway, optimiser (plausibility check; D62, D68) | From today's pathway with no new equipment: 67% at the best fit, 48 to 77% across all 184 settings (median 65), against 36 to 44% for today's pathway. Not a like-for-like pair with the authors' 80%, which includes the shorter PET-CT wait | simulated | It chose from a menu of about 69 changes that contained the authors' three. It rediscovered their redesign plus one overlapping change (tissue sampling planned at referral triage; worth 2 to 4 points; needs a clinical check) and it does not improve on the authors' redesign. Without new equipment it beats today's pathway in 184 of 184 settings but beats the faster scanner alone in only 128 of 184. Never quote 67% without the range. The optimiser is not run or reported with the faster scanner (D68) |
| Our synthetic Finnish county, optimiser | 18% to 33% treated within 90 days; gain 9 to 19 points over 12 cohorts, positive in all 12 | simulated | Two reorders, no new equipment, two held-out cohorts. The 90-day target is ours. 40 of 49 scenario inputs are assumptions. Not an estimate for real Finnish patients |

Other numbers (equity, capacity, the primary-care loop, model-written cards) are in the sheet and in `docs/results_in_full.md`.
The equity gap in percentage points widens (13.6 to 24.6) while both groups gain; we do not claim it closes.

## What is real and what is synthetic

- **Real, and not ours:** the Norwegian study's published numbers, the published Finnish and Nordic waits and survival figures. Each is cited in `params/sources.yaml` and `docs/pitch/evidence_brief.md`.
- **Synthetic:** every patient, the Finnish county, and its outputs. Of 49 inputs in the Finnish scenario, 9 cite a source; every capacity and booking lead is an assumption (`docs/ledger.md`).
- **Patient cards:** a **card** is one synthetic patient: a hidden truth plus the pre-written result of every test. The decision side sees only what has been revealed. 500 are written from templates. Some are written by a language model; that count is still changing (sheet E2, P3).
- **Care catalogue** (11 conditions, 26 tests): a draft no clinician has read; most of its numbers are our assumptions.
- **JEV**, the team's decision model, scores the offered options at a choice point from the visible record; a person decides. Its scores are relative, not probabilities. The results above come from placeholder tables and rules, not from JEV.

## How it works

1. A **flowchart** lists steps, what each must wait for, and the resource it uses (`docs/architecture.md`, `scenarios/stokstad.yaml`).
2. **Synthetic patients** carry a hidden truth. Decisions see only the revealed record (`patient_engine/`, `docs/synthetic_data_for_jev.md`).
3. A discrete-event run adds queues, a weekly tumour board and published waiting-time distributions (`pathway_sim/`).
4. The **optimiser** proposes changes from revealed timestamps; a change is kept only if a rerun of the same patients is faster and passes the guardrails, such as no more missed cancers (`optimiser/`).
5. Results are reported on **held-out** patients. In real life the rerun would be a pilot (`docs/master_plan.md`).
6. At choice points a decision model proposes and a person decides (`jev/`, `decision_api/`, `docs/platform/jev-birch.md`).

## What we do not claim

Full list: the "safe to claim / do not claim" box in `docs/pitch/filled/deck.md`. Open problems found by the independent review: `docs/review_w7.md`.

- Not a prediction for real patients, not lives saved. Faster care saving lives in lung cancer is not shown: the lung-surgery delay estimate is not significant.
- Not "we predicted 80% exactly", and not the older narrow range "78 to 86%" (the range is 62 to 86%). The optimiser did not beat or improve on the authors, did not find their answer from nothing, and the fourth change is not shown safe; "reordering beats buying the scanner" holds in 128 of 184 settings, not all.
- 61% is conditional on assumed urgent-booking times. It is not a result.
- The primary-care loop uses placeholder decision tables and every behaviour number is an assumption. It reproduces the calibrated chain only at the edge of the tolerances (8 of 8 checks on the tuning seeds, 6 of 8 on fresh seeds, 7 of 8 pooled over eight seeds; the pooled miss is non-cancer patients referred, 11.0% against 8.0%). A cancer waits about 25 days to referral, as in the chain; about one in ten (9%, 4 to 13%) is first treated as something else and those wait about four times as long (wide interval). Not a Finnish estimate; the old 37 days, one in six, 84 days and 840 EUR are withdrawn. Quote it as a mechanism, with the numbers and caveats in `docs/encounter_results.md` (sheet E4).
- Model-written cards are not "leak-free": the review found report wording that gave away false alarms. The fix (result prompt g2@2, reports rebuilt from values for old cards, an audit check) is merged; the new prompt has not yet been run on the real model, so the 35 model-written cards in the repository use the old prompt. Backgrounds now come from a population model whose numbers are mostly assumptions.
- Nothing is validated on real patients, and nothing here is clinically reviewed. The Norwegian check covers specialist care, not primary care.
- Our Finnish calibration uses 37 days from diagnosis to treatment; a lung-specific Finnish study gives 65 to 69. We reran at 67: the gain from the two reorders stays at about 15 points and 7.5 days, but the 90-day share falls to 0% for every pathway if that reading is right (`docs/evidence_sensitivity.md`).

## Where things are

Full table with owners and start points: `docs/repo_map.md`. Reading order for a technical judge: `docs/START_HERE.md`.

| Need | Go to |
|---|---|
| Run commands (install, simulate, optimise, JEV, web app) | `docs/commands.md` |
| Every number and its allowed sentence | `docs/pitch/filled/numbers_sheet.md` |
| Method, Norway robustness, limits | `docs/validation.md`; ranges `docs/ranges.md`; inputs `docs/ledger.md` |
| Plan and status | `docs/master_plan.md`, `docs/plan/README.md`, `docs/plan/04-status.md`, `docs/decisions.md` |
| Pitch text, submission, hard questions | `docs/pitch/filled/` |

Sources and licence: the published sources are listed per parameter in `params/sources.yaml` and `docs/parameters.md`. No licence file is in the repository yet.

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

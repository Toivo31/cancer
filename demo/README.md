# Demo site

Static, offline site for the Equal Care Across Finland demo: plain HTML, CSS and vanilla JS, no build step, no CDN, works
from `file://` with the network off. Since the UI revamp (14 Nov) it is one light "paper" site; read
`docs/plan/ui-revamp/HANDOFF.md` (especially "Do not recreate") before changing it. Presenter script: `docs/demo_path.md`.

## Pages

| Page | Nav entry | What it is | Reads |
|---|---|---|---|
| `start.html` | Overview | Three cards (simulate, optimise, check against a real hospital), one sentence each; everything else below DETAILS | start, flow, encounter, cards, research bundles |
| `flow.html` | Simulator | The pathway graph with simulated patients; OPTIMISE flips the same patients onto the changed pathway; details in drawers | `flow_bundle.js`, `start_bundle.js`, `research_bundle.js` |
| `patients.html` | Patients | Sealed truth vs visible record of one patient; the five-step loop; the two-wordings card below DETAILS | encounter, cards, flow, start, research bundles |
| `evidence.html` | Evidence | Norway check: dot-and-range chart, robustness small multiples below DETAILS | `start_bundle.js` (`evidence` field), `research_bundle.js` |
| `jev.html` | Decision model | Figure of one recorded decision, example cards, model card below DETAILS | `jev_bundle.js`, `research_bundle.js` |
| `research.html` | (not in the nav; marks Evidence) | Research behind the numbers: every claim labelled published / our simulation / our assumption; `research.html#<claim id>` opens a row | `research_bundle.js` |
| `encounter.html` | (marks Simulator) | The primary-care loop, patient by patient | `encounter_bundle.js`, `start_bundle.js` |
| `index.html` | (no site nav) | The six-screen results report ("dashboard"), re-coloured, layout unchanged (D66) | embedded `demo_bundle`, `start_bundle.js`, `research_bundle.js` |

Shared pieces: `theme.css` (tokens, shared classes such as `.page-top`, `.btn--primary`, `.details`, `.basis` tags),
`fonts/` (vendored Inter and Courier Prime), `site.js` (nav, footer, `?theme=night`, `Site.tokens()` for canvas colours),
`_skeleton.html` (page template), `_specimen.html` (every token and class; not linked). A page joins the nav only through
`Site.pages` in `site.js`. `?theme=night` gives the old dark look on every page that loads `site.js`.

Basis tags (D69): every number carries a `.basis` tag linking `research.html#<claim id>`; ids come from
`docs/research_claims.yaml` and are never renamed. `tests/test_demo_claim_links.py` checks that every such link resolves.

Tests: `pytest -q tests/test_demo_*.py` (per-page tests plus the shared checks in `tests/demo_pages.py`). Screenshots and
console errors: `bash scripts/ui_shots.sh <out-dir> [url-list]` (1440×900 and 1920×1080; file names keep the query and hash).

## Results report (`index.html`)

- Double-click `demo/index.html` (it then uses the bundle embedded in the page), or serve the folder:
  `python -m http.server -d demo 8000` and open <http://localhost:8000/>. The page fetches `data/demo_bundle.json` and
  falls back to the embedded copy if the file is missing.

Keys: `1`-`6` or the left/right arrows switch screens. The scenario switcher is under the tabs. Deep link: `index.html#finland_lung/3`.

Screens: 1 what to change and what it gains (Norway: headline is the optimiser's reordering with no new equipment, with its range, framed as a plausibility check (D62, D68); the authors' published 80% and the scanner alone beside it), 2 where time is lost (with claim tags under the headline), 3 why these changes (step chart of held-out on-time share after 0, 1, 2 ... changes; per change what the records said, what the rerun confirmed, honesty box; optional sensitivity tornado), 4 capacity or order (same patients: more capacity vs the suggested reorder; one-slot probe table; claim tags under the headline), 5 before/after pathway and Norwegian validation vs published 40/48/80, 6 who waits longest plus sources and assumptions.

## Rerunning the exports

One command rebuilds every bundle the pages read: `python demo/export_all.py` (or name some: `python demo/export_all.py encounter start`). Run it from the repo root, then reload the pages. Times on the shared 2-core machine, 14 Nov evening:

| Command | Writes | Time |
|---|---|---|
| `python demo/export_cards.py` | `data/cards_bundle.js` (synthetic-patient card on the Patients page; counts every folder in `libraries/` that has a manifest) | under 1 s |
| `python demo/export_start.py` | `data/start_bundle.js` (Norway ranges, optimiser bands and structure check from `docs/review_checks/norway_opt_*.json`, ledger, encounter report and its pass counts) | under 1 s |
| `python demo/export_encounter.py` | `data/encounter_bundle.js` (runs `scenarios/finland_encounter.yaml` now) | 15 s earlier, 87 s after the population model (shared machine) |
| `python demo/export_flow.py` | `data/flow_bundle.js` (held-out cohorts of both scenarios) | 37 to 63 s |

Order does not matter between them. `data/demo_bundle.json` (dashboard) comes from `demo/export.py` and `python demo/embed_bundle.py` and is only needed when the optimiser results change; the flow export prints each share next to the dashboard's and flags a difference.

## Data

The input is the demo bundle described in `docs/architecture.md` ("Demo bundle" and "Metrics JSON").

- `demo/data/demo_bundle.json`: the real bundle, produced by `demo/export.py` (another track) from real simulator runs.
- `demo/data/demo_bundle.fixture.json`: hand-made illustrative fixture (`"fixture": true`, shows an "Illustrative data" badge). Use it until the real bundle exists.
- The page also carries an embedded copy in `<script id="bundle">`. After producing a new bundle, refresh it with `python demo/embed_bundle.py` (uses `demo_bundle.json` if present, else the fixture), so the demo still works when opened from disk at the venue.

Optional fields the page tolerates when missing: `published`, `by_group`, `node_breakdown`, `flowchart_*`, `assumptions`, `fixture`.

Extra fields the page reads beyond the contract (all optional): scenario `description`; flowchart node `label` (plain text shown in the drawing; falls back to the id), node `stage`, `kind: "exit"` (drawn as a rounded end step), `after`/`after_any`; assumption `url`. The suggested change is the variant that has `changes`.

Tests: `pytest -q tests/test_demo_*.py`.

## Fields added in wave 2 (all optional for the page)

Per scenario, written by `export.py`:

- `optimiser` (and `optimiser_no_new_equipment` in stokstad): `steps` (raw), `selection_optimism_pp`, `candidates_evaluated`, `guardrails_heldout`, plus
  - `details[]`: `label` (plain wording, see `POLISHED` and `polish_change` in export.py), `raw` (optimiser text), `kind`, `records_said`, `rerun_said`, `predicted_days_saved`, `train_on_time_before/after`, `train_median_before/after`, `heldout_on_time_after` (cumulative, unseen patients);
  - `cumulative[]`: held-out `share`, `median_days`, `missed_cancers`, `tests_per_patient` after 0, 1, 2 ... changes (`kind` is `lead` for rows before the search start, e.g. the observed pathway in stokstad, `start`, or `change`);
  - `n_train`, `n_heldout` (per cohort), `heldout_cohorts`.
- `capacity_vs_order.rows[]`: `kind` (`today`, `capacity`, `order`, `both`), `label`, `share`, `median_days`; stokstad also has `capacity_label`.
- `headline_no_new_equipment` (stokstad): `share`, `median_days` of the reordering found from today's pathway without new equipment (the headline; the optimiser is not run from the faster-scanner pathway, D68).
- `wait_basis` (both scenarios): where the baseline's waiting days come from (`demo/wait_basis.py`): `waiting_share`, and per group `published` / `assumption` the days, share of waiting and steps with their source; `statement` is the sentence the pages show under screen 2.
- `capacity_vs_order.n_patients`, `n_cohorts`; rows may carry `published_share` (Norway, scanner alone) or `what_if: true` (capacity values chosen by us).
- `variants[].flowchart_id` on hand-written variants; `capacity_probe[].label` is plain wording.

## Sensitivity (optional)

`export.py` reads `docs/sensitivity_<scenario id>.json` (for example `docs/sensitivity_finland_lung.json`) if it exists and copies it to `scenario.sensitivity`. Accepted file shapes: a list of rows, `{"rows": [...]}`, or `{"scenarios": {"<id>": [...]}}`. A row:

```json
{"parameter": "CT slots a day", "low_gain_pp": 38.0, "high_gain_pp": 47.5, "low_label": "2", "high_label": "4"}
```

`parameter` is shown as written, so use plain words. The gain is the suggested change's gain in percentage points of patients treated on time, with that one input at its low and high value. The page draws a tornado (widest bar first, dashed line at the central estimate) on screen 3. If the field is absent, the panel is hidden.

## Simulator (`flow.html`)

The main screen of the product, offline: the pathway as a graph with simulated patients moving through it. Data: `data/flow_bundle.js` (and `data/start_bundle.js` for the Norway ranges), written by `python demo/export_flow.py` (about 40 s; same held-out cohorts and optimiser results as the dashboard, and the script prints each share next to the dashboard's).

- Default view (D67): names on steps, edge strength by thickness, a big DAY counter, the pathway dropdown (its last entry opens `encounter.html`), a headline card (whole-run numbers) and one OPTIMISE button. Optimise types out the saved run's changes, outlines the steps they touch and flips the same patients onto the changed pathway (TODAY / AFTER THE CHANGE).
- DETAILS: layers (Flow, Time, Queues, Decisions), change per step, draw larger, side by side, and drawers: Where time is lost, Check against the published study (Norway), Compare other pathways, All results, Counts now, Decisions, About this simulation.
- Keys: Space plays and pauses, arrow keys step, `r` restarts, `+`/`-` draw larger; hover a step for its numbers (click pins, Esc closes); click a dot for that patient's path.
- URL options: `?s=finland|norway`, `?compare` (opens with Optimise applied), `?left=observed&right=authors`, `?view=both|left|right`, `?layer=time`, `?paused&day=60`, `?large`, `?speed=` (days per second), `?numbers` (all numbers on the graph). Data shape: `docs/platform/flow-format.md`; library: `pathway_sim/flow.py`.

## Encounter loop page (`encounter.html`)

The primary-care loop (first contact, nurse and GP encounters, tests, treatment, discharge and return, referral, hospital steps) as a graph with simulated patients moving through it, a patient panel with the record, and the run's results tables. Open `demo/encounter.html` from disk (no server, no build), or from the Simulator's pathway dropdown. Counters, results tables and caveats sit below DETAILS. Data: `data/encounter_bundle.js`, written by `python demo/export_encounter.py` (about 30 s: it runs `scenarios/finland_encounter.yaml` at run time with seed 1 and enough patients for about 50 cancers, so whatever the scenario files hold when you run it is what the page shows; about 1 MB). Options: `--n`, `--seed`, `--sample` (dots drawn, default 320), `--out`.

- Graph: nodes come from the care model (roles, test groups from the order actions, treatment, referral, discharge) and from the hospital flowchart of the world; edge thickness is the number of patients (of all simulated) who took that transition; the dashed arc is the return to first contact. Layers: Flow (counts) and Time at step (median days per visit).
- Dots: a stratified sample (all cancers up to about 50, the rest random, plus the example patients). Time is days since each patient's first contact. Speeds 0.5 to 8 days/s (default 2). Space plays and pauses, arrows step, `r` restarts, `t` toggles the teaching view. URL options: `?paused&day=60`, `?p=<patient id>` (selects the patient and scrolls the side column to its record; the Patients page links here), `?layer=time`, `?truth`.
- Patient panel: click a dot or pick an example. The record is `patient_engine.record_text.render` lines (with the repeated history/examination lists folded away by the exporter). Mechanical log lines (typewriter, solid rule) and assessment lines (italic, dashed rule) look different; lines after the current day are dimmed; click a line to expand it.
- Hidden truth: stored under `truth` in the bundle and read by the page only after "Reveal truth (teaching view)" is on. It then shows the true conditions, whether each primary-care treatment matches one of them, brown rings on cancer dots and teaching captions for the examples. Default captions and all default fields describe only what the record shows. The results tables are the run's own report (outcomes and by-group) and are shown by default; the "treatments matching the truth" score is left out of them.
- Example patients (picked from the whole run by what happened): a cancer first treated as an infection (the median-delay case), the quickest correct referral, the longest loop that still reads on one screen, a worried-well patient investigated anyway, a benign patient sent through hospital steps, a cancer that left and never came back. A category with no candidate is skipped.
- Tests: `pytest tests/test_demo_encounter.py` (bundle integrity, the truth split; the slow test re-exports a small run). The page was also opened in headless Chrome (`google-chrome --headless=new --screenshot ... "file://.../demo/encounter.html?paused&day=120"`) with no console errors.

The patient panel has a labelled slot "Decision model proposals": if a patient in the bundle has `proposals` (`[{decision_point, options[{id,label,score}], proposed, chosen, delivery: live|saved|placeholder}]`) they are drawn per decision; otherwise it says none yet. `export_encounter.py --proposals file.json` fills it from `{patient id: [...]}`.

## Decision model page (`jev.html`)

The team's decision model at one node: a figure on top (the record → the decision → the allowed answers with their scores → a person accepts or overrides), drawn from the one recording of the deployed model in the bundle; then example cards with context, allowed answers and the model's output, and a free-text card; the model card (architecture, inputs and outputs, use and limits, training data, a Hugging Face placeholder) sits below DETAILS. Open `demo/jev.html` from disk. Data: `data/jev_bundle.js`, written by `python demo/export_jev.py` (25 to 75 s; it reruns the encounter loop once, so run it after `export_encounter.py`; `export_all.py jev` does).

- **Where outputs come from.** Every output carries a label read from the answer itself (`backend.mode`): *Recorded · deployed model* (the owner's recordings, copied into `data/jev_recorded.json` from `decision_api/web` and `decision_api/validation` on main; refresh with `--refresh-recorded origin/main`), *Live call · deployed model*, *scripted fixture, not the model*, *mock, not the model*. Nothing is scored offline and nothing is invented: a card without an answer says so. Today only the reasoning card has a recorded model output.
- **Live calls** start only on a button press. The bar "Answers come from" picks the endpoint: the team's hosted gateway (works from disk, CORS), this server's `/api/decision` (run `python demo/serve_jev.py`, which serves `demo/` and the local proxy on one origin, because the proxy refuses other origins), or any URL. URL option: `?api=hosted|same|<url>`; `#gp_visit`, `#reasoning`, `#triage`, `#screening`, `#compare`, `#own` open a card and scroll to the examples. Polls 202 jobs once a second, never resubmits, shows errors as they are.
- **Recording real outputs for the presets:** `python demo/export_jev.py --record <base url ending in /api/decision>` makes one call per preset (GPU time) and keeps only answers whose `backend.mode` is `model` in `data/jev_preset_outputs.json`; the page then shows them as recorded.
- **The default card is a real node:** the GP visit of the encounter-loop example "treated as an infection" (patient and day from `data/encounter_bundle.js`), built with `jev.birch.BirchPolicy.request_for` and `map_request`, the code the simulator calls. The placeholder table's numbers at that visit are shown next to it, labelled. The gateway takes at most 8 answers per question (the model 16); the GP node offers 24, so the card offers 8 (all the table weighs, plus common next steps).
- **Hugging Face link:** set `HF_URL` at the top of `demo/jev.js`.
- Tests: `pytest tests/test_demo_jev.py`. Checked in headless Chrome at 1440x900 and 1920x1080 with no console errors.

# Demo dashboard

Static, offline dashboard for the Equal Care Across Finland demo. One file (`index.html`), inline CSS and vanilla JS, no build step, no CDN.

## Open it

- Double-click `demo/index.html` (works from `file://`; it then uses the bundle embedded in the page), or
- serve the folder: `python -m http.server -d demo 8000` and open <http://localhost:8000/>. The page fetches `data/demo_bundle.json` and falls back to the embedded copy if the file is missing.

Keys: `1`-`6` or the left/right arrows switch screens. The scenario switcher is top right. Deep link: `index.html#finland_lung/3`.

Screens: 1 what to change and what it gains (Norway: headline with the faster scanner plus the no-new-equipment number beside it), 2 where time is lost, 3 why these changes (step chart of held-out on-time share after 0, 1, 2 ... changes; per change what the records said, what the rerun confirmed, honesty box; optional sensitivity tornado), 4 capacity or order (same patients: more capacity vs the suggested reorder; one-slot probe table), 5 before/after pathway and Norwegian validation vs published 40/48/80, 6 who waits longest plus sources and assumptions.

## Rerunning the exports

One command rebuilds every bundle the pages read: `python demo/export_all.py` (or name some: `python demo/export_all.py encounter start`). Run it from the repo root, then reload the pages. Times on the shared 2-core machine, 14 Nov evening:

| Command | Writes | Time |
|---|---|---|
| `python demo/export_cards.py` | `data/cards_bundle.js` (synthetic-patient card on the start page; counts every folder in `libraries/` that has a manifest) | under 1 s |
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

Tests: `pytest tests/test_demo_fixture.py tests/test_demo_start.py tests/test_demo_cards.py`.

## Fields added in wave 2 (all optional for the page)

Per scenario, written by `export.py`:

- `optimiser` (and `optimiser_no_new_equipment` in stokstad): `steps` (raw), `selection_optimism_pp`, `candidates_evaluated`, `guardrails_heldout`, plus
  - `details[]`: `label` (plain wording, see `POLISHED` and `polish_change` in export.py), `raw` (optimiser text), `kind`, `records_said`, `rerun_said`, `predicted_days_saved`, `train_on_time_before/after`, `train_median_before/after`, `heldout_on_time_after` (cumulative, unseen patients);
  - `cumulative[]`: held-out `share`, `median_days`, `missed_cancers`, `tests_per_patient` after 0, 1, 2 ... changes (`kind` is `lead` for rows before the search start, e.g. the observed pathway in stokstad, `start`, or `change`);
  - `n_train`, `n_heldout` (per cohort), `heldout_cohorts`.
- `capacity_vs_order.rows[]`: `kind` (`today`, `capacity`, `order`, `both`), `label`, `share`, `median_days`; stokstad also has `capacity_label`.
- `headline_no_new_equipment` (stokstad): `share`, `median_days` of the reordering found without the faster scanner.
- `variants[].flowchart_id` on hand-written variants; `capacity_probe[].label` is plain wording.

## Sensitivity (optional)

`export.py` reads `docs/sensitivity_<scenario id>.json` (for example `docs/sensitivity_finland_lung.json`) if it exists and copies it to `scenario.sensitivity`. Accepted file shapes: a list of rows, `{"rows": [...]}`, or `{"scenarios": {"<id>": [...]}}`. A row:

```json
{"parameter": "CT slots a day", "low_gain_pp": 38.0, "high_gain_pp": 47.5, "low_label": "2", "high_label": "4"}
```

`parameter` is shown as written, so use plain words. The gain is the suggested change's gain in percentage points of patients treated on time, with that one input at its low and high value. The page draws a tornado (widest bar first, dashed line at the central estimate) on screen 3. If the field is absent, the panel is hidden.

## Flowchart simulation page (`flow.html`)

The main screen of the product, offline: the pathway as a graph with simulated patients moving through it. Open `demo/flow.html` from disk (no server, no build). Data: `data/flow_bundle.js` (and `data/start_bundle.js` for the Norway ranges in the side panel), written by `python demo/export_flow.py` (about 40 s; same held-out cohorts and optimiser results as the dashboard, and the script prints each share next to the dashboard's). Layers: Flow (counts), Time (median wait per step), Queues (waiting over the simulated year), Decisions (shares chosen); Compare shows the change per step against the left pathway. Space plays and pauses, arrow keys step, `r` restarts; click a dot for that patient's trace. URL options: `?s=finland`, `?layer=time`, `?compare`, `?paused&day=60`, `?view=both|left|right`, `?left=observed&right=authors`. Data shape: `docs/platform/flow-format.md`; library: `pathway_sim/flow.py`.

## Encounter loop page (`encounter.html`)

The primary-care loop (first contact, nurse and GP encounters, tests, treatment, discharge and return, referral, hospital steps) as a graph with simulated patients moving through it, a patient panel with the record, and the run's results tables. Open `demo/encounter.html` from disk (no server, no build); same look as `flow.html` (its own copy of the CSS). Data: `data/encounter_bundle.js`, written by `python demo/export_encounter.py` (about 30 s: it runs `scenarios/finland_encounter.yaml` at run time with seed 1 and enough patients for about 50 cancers, so whatever the scenario files hold when you run it is what the page shows; about 1 MB). Options: `--n`, `--seed`, `--sample` (dots drawn, default 320), `--out`.

- Graph: nodes come from the care model (roles, test groups from the order actions, treatment, referral, discharge) and from the hospital flowchart of the world; edge thickness is the number of patients (of all simulated) who took that transition; the coral arc is the return to first contact. Layers: Flow (counts) and Time at step (median days per visit).
- Dots: a stratified sample (all cancers up to about 50, the rest random, plus the example patients). Time is days since each patient's first contact. Space plays and pauses, arrows step, `r` restarts, `t` toggles the teaching view. URL options: `?paused&day=60`, `?p=<patient id>`, `?layer=time`, `?truth`.
- Patient panel: click a dot or pick an example. The record is `patient_engine.record_text.render` lines (with the repeated history/examination lists folded away by the exporter). Mechanical log lines (blue, mono) and assessment lines (coral, dashed, italic) look different; lines after the current day are dimmed; click a line to expand it.
- Hidden truth: stored under `truth` in the bundle and read by the page only after "Reveal truth (teaching view)" is on. It then shows the true conditions, whether each primary-care treatment matches one of them, red rings on cancer dots and teaching captions for the examples. Default captions and all default fields describe only what the record shows. The results tables are the run's own report (outcomes and by-group) and are shown by default; the "treatments matching the truth" score is left out of them.
- Example patients (picked from the whole run by what happened): a cancer first treated as an infection (the median-delay case), the quickest correct referral, the longest loop that still reads on one screen, a worried-well patient investigated anyway, a benign patient sent through hospital steps, a cancer that left and never came back. A category with no candidate is skipped.
- Tests: `pytest tests/test_demo_encounter.py` (bundle integrity, the truth split; the slow test re-exports a small run). The page was also opened in headless Chrome (`google-chrome --headless=new --screenshot ... "file://.../demo/encounter.html?paused&day=120"`) with no console errors.

The patient panel has a labelled slot "Decision model proposals": if a patient in the bundle has `proposals` (`[{decision_point, options[{id,label,score}], proposed, chosen, delivery: live|saved|placeholder}]`) they are drawn per decision; otherwise it says none yet. `export_encounter.py --proposals file.json` fills it from `{patient id: [...]}`.

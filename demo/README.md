# Demo dashboard

Static, offline dashboard for the Equal Care Across Finland demo. One file (`index.html`), inline CSS and vanilla JS, no build step, no CDN.

## Open it

- Double-click `demo/index.html` (works from `file://`; it then uses the bundle embedded in the page), or
- serve the folder: `python -m http.server -d demo 8000` and open <http://localhost:8000/>. The page fetches `data/demo_bundle.json` and falls back to the embedded copy if the file is missing.

Keys: `1`-`6` or the left/right arrows switch screens. The scenario switcher is top right. Deep link: `index.html#finland_lung/3`.

Screens: 1 what to change and what it gains (Norway: headline with the faster scanner plus the no-new-equipment number beside it), 2 where time is lost, 3 why these changes (step chart of held-out on-time share after 0, 1, 2 ... changes; per change what the records said, what the rerun confirmed, honesty box; optional sensitivity tornado), 4 capacity or order (same patients: more capacity vs the suggested reorder; one-slot probe table), 5 before/after pathway and Norwegian validation vs published 40/48/80, 6 who waits longest plus sources and assumptions.

## Data

The input is the demo bundle described in `docs/architecture.md` ("Demo bundle" and "Metrics JSON").

- `demo/data/demo_bundle.json`: the real bundle, produced by `demo/export.py` (another track) from real simulator runs.
- `demo/data/demo_bundle.fixture.json`: hand-made illustrative fixture (`"fixture": true`, shows an "Illustrative data" badge). Use it until the real bundle exists.
- The page also carries an embedded copy in `<script id="bundle">`. After producing a new bundle, refresh it with `python demo/embed_bundle.py` (uses `demo_bundle.json` if present, else the fixture), so the demo still works when opened from disk at the venue.

Optional fields the page tolerates when missing: `published`, `by_group`, `node_breakdown`, `flowchart_*`, `assumptions`, `fixture`.

Extra fields the page reads beyond the contract (all optional): scenario `description`; flowchart node `label` (plain text shown in the drawing; falls back to the id), node `stage`, `kind: "exit"` (drawn as a rounded end step), `after`/`after_any`; assumption `url`. The suggested change is the variant that has `changes`.

Tests: `pytest tests/test_demo_fixture.py`.

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

The main screen of the product, offline: the pathway as a graph with simulated patients moving through it. Open `demo/flow.html` from disk (no server, no build). Data: `data/flow_bundle.js`, written by `python demo/export_flow.py` (about 40 s; same held-out cohorts and optimiser results as the dashboard, and the script prints each share next to the dashboard's). Layers: Flow (counts), Time (median wait per step), Queues (waiting over the simulated year), Decisions (shares chosen); Compare shows the change per step against the left pathway. Space plays and pauses, arrow keys step, `r` restarts; click a dot for that patient's trace. URL options: `?s=finland`, `?layer=time`, `?compare`, `?paused&day=60`, `?view=both|left|right`, `?left=observed&right=authors`. Data shape: `docs/platform/flow-format.md`; library: `pathway_sim/flow.py`.

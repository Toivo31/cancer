# Demo dashboard

Static, offline dashboard for the Equal Care Across Finland demo. One file (`index.html`), inline CSS and vanilla JS, no build step, no CDN.

## Open it

- Double-click `demo/index.html` (works from `file://`; it then uses the bundle embedded in the page), or
- serve the folder: `python -m http.server -d demo 8000` and open <http://localhost:8000/>. The page fetches `data/demo_bundle.json` and falls back to the embedded copy if the file is missing.

Keys: `1`-`4` or the left/right arrows switch screens. The scenario switcher is top right. Deep link: `index.html#finland_lung/3`.

Screens: 1 what to change and what it gains, 2 where time is lost (waiting vs served per stage, the change that fixes it), 3 before/after pathway and Norwegian validation vs published 40/48/80, 4 who waits longest plus sources and assumptions.

## Data

The input is the demo bundle described in `docs/architecture.md` ("Demo bundle" and "Metrics JSON").

- `demo/data/demo_bundle.json`: the real bundle, produced by `demo/export.py` (another track) from real simulator runs.
- `demo/data/demo_bundle.fixture.json`: hand-made illustrative fixture (`"fixture": true`, shows an "Illustrative data" badge). Use it until the real bundle exists.
- The page also carries an embedded copy in `<script id="bundle">`. After producing a new bundle, refresh it with `python demo/embed_bundle.py` (uses `demo_bundle.json` if present, else the fixture), so the demo still works when opened from disk at the venue.

Optional fields the page tolerates when missing: `published`, `by_group`, `node_breakdown`, `flowchart_*`, `assumptions`, `fixture`.

Extra fields the page reads beyond the contract (all optional): scenario `description`; flowchart node `label` (plain text shown in the drawing; falls back to the id), node `stage`, `kind: "exit"` (drawn as a rounded end step), `after`/`after_any`; assumption `url`. The suggested change is the variant that has `changes`.

Tests: `pytest tests/test_demo_fixture.py`.

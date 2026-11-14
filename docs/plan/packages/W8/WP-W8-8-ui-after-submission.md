# WP-W8-8: UI revamp packages WP5 to WP9 (tickets only; the plan lives in `docs/plan/ui-revamp/`)

| | |
|---|---|
| Component | UI revamp plan (`w8/ui-plan`, merged); D60 (judges see `demo/`), D61 (UI choices) |
| Status | not started |
| Size | per row below (sizes are the plan's own estimates) |
| Needs | WP1 (tokens and fonts, `demo/theme.css`) merged for every row; WP2 to WP4 merged before WP7's flip view |
| Owned paths | as stated per package in `docs/plan/ui-revamp/06-execution-plan.md` (file ownership table, lines 9 to 22) |
| Do not edit | `docs/plan/ui-revamp/**` (the UI planning lane writes lane briefs there for WP1 to WP4 now). This file adds no scope: each ticket points to the plan's description, which wins if they differ |
| Review required | WP5 and WP6 yes (claims about patients and evidence); WP7 to WP9 no |
| Track | after submission. Exception per the plan: WP5 is a stretch before freeze "if there is room" (line 5); D61 pauses other lanes while WP1 and WP2 run |

WP1 to WP4 are planned and briefed in `docs/plan/ui-revamp/`; they get no tickets here.

## Tickets

| | ID | Ticket | Size | Owner | Needs | Done when (from the plan) | Plan description |
|---|---|---|---|---|---|---|---|
| [ ] | W8-UI-T5 | WP5: "How the patients work" page `demo/patients.html` | 2 to 3 h | agent (review lane reads claims) | WP1 | new test: no typed digits, links exist (copy `tests/test_demo_start.py`'s parser) | `06-execution-plan.md` line 18 and the WP5 section (line 72 on) |
| [ ] | W8-UI-T6 | WP6: "Does it hold up" page and Norway case-study paper (`demo/evidence.html`, `demo/norway_case.html`, print CSS) | 4 to 6 h + review | agent + review lane | WP1; any new robustness figure exported into `start_bundle.js` first | same kind of test as WP5; review lane read. Source text: `docs/norway_case_study.md` (merged, D62 framing) and `docs/evidence_sensitivity.md` | lines 19 and 82 |
| [ ] | W8-UI-T7 | WP7: web app theme and simplification (`web/src/theme.css` + `theme.ts`, replace literals, one Optimise entry, Details menu, three headline numbers, slower clock, flip view after apply) | 1 h tokens only; 1 to 2 days full | agent | WP1 | gate "web" step green; `web/scripts/shots.mjs` labels updated | lines 20 and 83. Note D60: the React app is out of the judges' path, so this is platform track |
| [ ] | W8-UI-T8 | WP8: one simulator renderer: decide with Eemeli whether `live_demo/flow.html`, `demo/flow.html` and the web canvas converge | design 2 h | **human decision (Tuomas and Eemeli)**, then agent | WP2 merged | a written decision (options: keep three; converge on `demo/flow.*`; converge on the web canvas) in `docs/decisions.md` | line 84 |
| [ ] | W8-UI-T9 | WP9: `scripts/ui_shots.sh`: fixed URL list at two sizes into `runs/ui_shots/<commit>/`, console-error check, optional pixel diff, offline check for every page | 1 to 2 h | agent | – (useful before WP5 to WP7: it turns their manual acceptance into a command) | one command produces shots and fails on a console error | line 85 |

Also from D61 and not in the plan's WP list as a row: "white paper page after submission". Check with the UI planning lane
whether that is WP6's paper or a separate page before ticketing it; not ticketed here to avoid a duplicate.

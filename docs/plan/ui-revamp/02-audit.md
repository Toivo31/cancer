# Audit of the current UI (14 Nov, 20:48 UTC, `84cb335`)

**In one line:** there are three visual languages and three implementations of the same flowchart simulation.
Every default view shows the detailed statistics at once. The simulator's before/after comparison does not
show both sides on a 1440-px laptop.

Screenshots at 1440×900 are in `current/` (headless Chrome, pages opened from disk or the mock/live servers).

## Summary table

| Surface | What it is | Opens without a server | Look | Words on load | Verdict |
|---|---|---|---|---|---|
| `demo/start.html` | "The demo in order": 6 numbered rows (problem, primary care, reordering, Norway, decision model, honesty) and a synthetic-patients card | yes | dark navy, neon mint/amber, blue grid | ~1,340; 2 screens tall | Keep as the **Overview**, rewritten to a third of the text |
| `demo/flow.html` | Flowchart simulator: Norway or Finland, layers, Compare, patient trace, side cards | yes | same dark neon | 750 to 1,150 | Keep as **the Simulator**; biggest redesign |
| `demo/encounter.html` | Primary-care loop: nurse/GP/tests/home graph, example patients, record panel, reveal-truth toggle, results tables | yes | same | ~750 + results below | Keep. Re-theme. Link from Simulator and Patients pages. Reuse its record + reveal-truth view on the Patients page |
| `demo/index.html` | Dashboard: 6 screens × 2 scenarios (headline, time lost, why these changes, capacity vs order, before/after, who waits) | yes | same | ~320 per screen, very large type | Off the main path. Link as "Full results report" at the bottom of the Evidence page. Its charts are the source for Evidence infographics |
| `demo/jev.html` (merged 21:00 UTC; `current/09_jev.jpg`) | Model card with architecture diagram on top, endpoint picker, six example cards (context, allowed answers, model output with provenance) | yes | same (copied CSS) | dense; model card first | Becomes the **Decision model** page: the infographic and examples go first, the model card below DETAILS |
| `web/` React app | Projects → project screen: canvas, toolbar, run panel, Optimise, Decisions editor, diff dialog | needs `service/` (or `?mock=1`) | same dark neon | lighter; many controls | The real platform. Stays out of the judges' default path until after the submission |
| `live_demo/` (Eemeli) | Hosted demo: paper-grey pathway with dot piles, Today / Suggested / Fast lane / Norway buttons; `/note` reader; `/report` light copy of the dashboard; `/decision` panel | needs `note_reader.server` | **paper, greyscale, Inter** (= the video) | moderate | Closest to the target look already. Not ours to edit; converge with Eemeli after the submission |
| `/note` (note reader) | Note text in, flagged words and next step out | needs server | black terminal, green mono | low | A fourth look. Eemeli's; re-theme would be his call |
| `decision_api` `/decision` | Toivo's model panel | needs server | its own | | Not ours; link only |

## Page by page: what is on screen, what is clutter

### `demo/start.html` (`current/01_start.jpg`)

On screen: eyebrow, a 15-word H1, a two-line subtitle about "pending" files, a badge; then rows of
`[title + 2-3 sentences] [big mint number + 3-8 lines of caption] [buttons]`. Row 4 (Norway) alone has six bold
lead-ins and a fold, about 300 words. Row 5 shows two shell commands. The honesty paragraph and the synthetic-patients
card are below the fold.

- Clutter: the subtitle explains the page's own mechanics ("pending means the file is not there yet"). The captions
  repeat the caveats that the target pages also carry. Shell commands and `.md` links are presenter material, not
  judge material. Fourteen buttons, all styled alike.
- What works and must survive: every number is bound from bundles (tested). Each row has exactly one number. The
  honesty box exists.
- Order problem: the reader meets the primary-care loop (row 2, an assumed-behaviour model) before the main result (row 3).

### `demo/flow.html` (`current/02_flow_finland_compare.jpg`, `03_flow_norway_compare.jpg`)

Header: back link, eyebrow, H1, subtitle, 2 scenario buttons, 4 layer buttons (Flow/Time/Queues/Decisions),
Compare, Large, View, Simulated-patients badge. Pane: "After the change" label, `+15.6 pp vs left` chip, variant
dropdown, a 6-item counter row (waiting/served/treated on time/late/discharged/missed, all 0 at day 1), a big
`33.1%` plus three more stats. Side column: "Layer: Flow" help card, "Where time is lost" (7 paired bars), "What you
are looking at" (method text). On Norway, "Check against the published study" (table + ~250 words, structure check).
Footer: Pause, Restart, Patient day, slider, Speed dropdown, 5-item legend.

- **Before/after is not visible at 1440 px.** `S.view` is `both` only when `innerWidth >= 1700`
  (`flow.js` line 694). At 1440 the page opens on the right pane alone, labelled "+15.6 pp vs left", but no left
  pane is on screen. Compare mode then marks per-step deltas, and most steps read "0.0 d on path".
- Speed: options are 0.5×, 1×, 2×, 4× of `H/40` days/s (line 668). For Finland (H ≈ 168) the slowest is about
  2.1 days/s and the default 4.2; for Norway about 2.0 and 4.0. Tuomas wants slower.
- Queues: the "Queues" layer draws a calendar-year sparkline per step and tints the step blue. Waiting dots shift
  amber to orange with their own waited days. No step changes colour as its pile grows.
- Clutter: the counter row, the layer help card and "What you are looking at" are open by default. The Norway check
  repeats the start page's row 4 almost word for word. "Large", "View" and "Compare" are three toggles for one
  question ("how do I see before and after").
- Works and must survive: one shared clock for both panes; the union layout (`layoutUnion`) puts every step at the
  same place in both pathways (this is what makes a flip comparison cheap); the click-a-dot trace; URL parameters
  used by `start.js`, `docs/demo_path.md` and the README (`?s=`, `?compare`, `?left=`, `?right=`, `?view=`,
  `?layer=`, `?paused`, `?day=`, `?large`).

### `demo/encounter.html` (`current/04_encounter.jpg`)

Header with Flow / Time at step / Reveal truth / badge; a 9-item counter row; the graph; side: six example patients
and a patient-record panel; results tables below the graph; footer like flow.html.
- Clutter: the counter row; the results tables directly under the graph; the long run note.
- Strong: the two-layer record (mechanical log vs clinician assessments) and the Reveal-truth toggle. This is the best
  existing illustration of the hidden-variable idea. The Patients page should reuse it.

### `demo/index.html` (`current/05_dashboard.jpg`)

Six numbered tabs plus a scenario switch. The H1 of screen 1 is a 22-word sentence with two ranges in it. The
40% → 88% numbers are about 130 px tall (14 Nov night, D68: the headline is now the no-equipment result, 40% → 67% with its range; no optimiser-with-scanner number is shown). Text-heavy explanations ("Read with the range") follow. Screen 5 draws
before and after pathways as two stacked DAGs. **Tuomas, 14 Nov: this page ("Before and after: what the suggested change does to the pathway") is good as it is. Keep its layout, wording and content; the revamp only re-themes it (D66).**
- It overlaps start rows 1, 3, 4 and flow.html's side panel. Keep it as the "full report" for the few who want
  everything, and for us.
- 6,750 lines, including the embedded bundle (`<script id="bundle">`) that `tests/test_demo_fixture.py` compares with
  `data/demo_bundle.json`. Restyling its CSS is safe; reformatting that script block is not.

### `web/` React app (`current/06_web_project.jpg`, mock mode)

Top bar; crumb with flowchart and version dropdowns; Flowchart / Decisions subtabs; toolbar: Structure / Flow / Time /
Queues / Decisions, **Optimise…**, Edit, Reset layout, Hide panel; zoom controls; side tabs: Run / **Optimise** /
Where time is lost / Patient; playback bar with 0.5×–8× and six counters; a dot-sample footnote.
- Two Optimise entries; five layers; four side tabs; at "fit" zoom on 1440 px the Norway graph's node labels are
  about 5 px and unreadable.
- Optimise is a form (patients, at most N changes) → run → pick changes → apply → rerun → compare. That is right
  for the platform but too much for a two-minute demo.
- Colours: `styles.css` has variables, but 41 hex/rgba literals sit in TSX (`FlowCanvas` 16, `DiffView` 10,
  `layers.ts` 8, `PlaybackLayer` 7).

### `live_demo/` (`current/07_live_demo.jpg`, `08_note_reader.jpg`)

Off-white `#fdfcf8`, near-black `#1f1f1d`, Inter, greyscale canvas (`filter: grayscale(1)`), `DAY 000` counter, centred
"TODAY'S PATHWAY", thin grey lines, black and grey dot piles. This is the look of the reference frames. Its footer
text overlaps the dot piles at 1440×900. It loads Inter from Google Fonts (no network, no Inter). Its dashboard copy
greys everything with a CSS filter.

## Duplication

| Thing | Implementations | Proposal |
|---|---|---|
| Animated flowchart with dot piles | `demo/flow.js`, `web/src/graph/*`, `live_demo/flow.html`, `video/dots/*.js`, plus `demo/encounter.js` (different graph) | Tonight: `demo/flow.html` is the one judges use. After: converge (WP8) |
| Norway validation story | start row 4, flow.html side card, index screens 1 and 5, `live_demo` "Norway check", `docs/validation.md` | One place: the Evidence page top, plus the one-line result on the Overview |
| "Where time is lost" | flow.html side card, index screen 2, web side tab | Detail level in the Simulator only |
| Dashboard | `demo/index.html`, `live_demo/report/` (light copy) | Bottom link only |
| Colour definitions | `start.css`, `flow.css`, `encounter.css`, `jev.css` (each "copied, so pages can change on their own"), inline in `index.html`, `flow.js` `C`, `encounter.js`, `web/src/styles.css` + 4 TSX files | One `demo/theme.css` and one `web/src/theme.css` (05-theme.md) |

## Which surface judges should see

Lean: the `demo/` site, opened from `demo/start.html`. Reasons: it opens from disk (venue Wi-Fi does not matter);
its results are the held-out ones that the pitch numbers sheet reads; it is covered by tests; the status file
already leans that way for the AstraZeneca page. The React app is the better long-term product but needs the service
and mostly shows controls. `live_demo/` already has the target look and is the natural hosted URL. Converging it is a
conversation with Eemeli, not something to do tonight.

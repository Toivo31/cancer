# Execution plan: small packages, demoable after every merge

> Update 21:30 UTC: with everything else paused, the packages run as parallel lanes. See [07-parallel-lanes.md](07-parallel-lanes.md); its cut line replaces the one below. The file map, guards and rollback below still apply.

**In one line:** nine work packages, each one branch, one merge and one revert. Tokens first, because they are new
files and break nothing. The simulator next, because it carries the most demo value and no other lane is in its files.
The start page only after `w8/jev-demo` merges. New info pages last. Before the 04:00 UTC freeze: WP1 to WP4, and WP5 if there is room.

## File map: what the revamp touches, what guards it, who else is there

| File(s) | Touched by | Guarded by | Coupled to | Other lanes now (channel, 20:48 UTC) |
|---|---|---|---|---|
| `demo/theme.css`, `demo/fonts/*` (new) | WP1 | new test (WP1) | every page that links it | none |
| `demo/flow.html`, `flow.js`, `flow.css` | WP2 | **no browser test**; `tests/test_demo_start.py::test_norway_links_built_in_script_name_real_variants` reads URLs from `start.js` and checks `left`/`right` keys against `flow_bundle.js` | URL params used by `start.js`, `docs/demo_path.md`, README; reads `data/flow_bundle.js` fields `variants[].label/role/changes/note`, `flow.metrics`, `cohort`, `queues`, `published`, and `data/start_bundle.js` (Norway ranges) | none claimed (`w5/demo-path` and `w7/demo` merged) |
| `demo/data/flow_bundle.js` | **not touched** | `tests/test_flow.py` (format), the start test above | `demo/export_flow.py` (37–63 s), `docs/platform/fixtures/flow_*.json` (web mock) | status "Next" step 3 regenerates bundles after jev-demo / fi-sens merge |
| `demo/start.html`, `start.js`, `start.css` | WP3 | `tests/test_demo_start.py`: no digit in page text outside `<code>`/`.cmd`; ≥10 links, all targets exist; `start.js` numerals ⊆ {0,1,2,16,100}; Norway pairs; ranges equal `docs/review_checks/norway_opt_summary.json` via the bundle. `tests/test_demo_jev.py` asserts `href="jev.html"` in `start.html` | `data/start_bundle.js`, `cards_bundle.js`, `flow_bundle.js`, `encounter_bundle.js`; `docs/demo_path.md` speaks of "row 1 … row 6"; `docs/pitch/fill_numbers.py` reads `start_bundle.js` (data only) | **`w8/jev-demo` is editing `start.html` row 5 now** |
| `demo/encounter.html/.js/.css` | WP4 | `tests/test_demo_encounter.py` (bundle only; the HTML is not parsed) | `?p=` URL used by `jev.js` (tested in `test_demo_jev.py`) and `start.js` example links | none (w4/demo-loop released) |
| `demo/jev.html/.js/.css` | WP4 (after merge) | `tests/test_demo_jev.py` | | `w8/jev-demo` owns it until merged |
| `demo/index.html` | WP4 (CSS only, optional) | `tests/test_demo_fixture.py` compares `<script id="bundle">` with `data/demo_bundle.json` | `demo/embed_bundle.py` rewrites that block | none |
| `demo/patients.html` (new) | WP5 | new test: no typed digits, links exist (copy `test_demo_start.py`'s parser) | `cards_bundle.js`, `encounter_bundle.js`, `demo_bundle.json` (selection optimism) | none |
| `demo/evidence.html`, `demo/norway_case.html` (new) | WP6 | same kind of test; review-lane read | `start_bundle.js`, `docs/validation.md`, `docs/review_checks/norway_*` | `w7/norway-opt` merged; any new robustness file must be exported into `start_bundle.js` first |
| `web/src/**` | WP7 | `scripts/gate.sh` "web" step: `npm run typecheck && npm test` (vitest: `DiffView`, `OptimisePanel`, `EditPanel`, `DecisionsTable`, `layers`, `layout`, `playback`, `graphDiff`, …; text queries such as "Keep it", "Add a step") | `web/scripts/shots.mjs` clicks tabs by label; `service/` serves `web/dist` | w6/web merged; nobody claimed now |
| `docs/demo_path.md` | WP2, WP3 (same commit as the UI change) | none | the presenter's words | demo lane (merged) |
| `README.md` "Open this first" | WP3 (one row) | `test_review_w7_demo_numbers.py` greps README for the stale 78–86 band | pitch lane owns headline numbers | w7/pitch merged |
| `live_demo/`, `note_reader/`, `decision_api/`, `video/` | **not touched** | | | Eemeli, Toivo |

Hard rules for every package: numbers are never typed into HTML or JS, only bound from bundles (the start-page
tests enforce this for `start.*`; new pages copy those tests). Bundles are not regenerated as part of a UI package.
Caveats move below DETAILS but are not deleted. URL parameters stay backwards compatible.

## Work packages

Effort is agent time on the shared 2-core machine. "Parallel" means safe to run at the same time as the other packages listed.

### Before the freeze

**WP1: Tokens and fonts** · 30–45 min · risk low · parallel with anything
- Scope: `demo/theme.css` (tokens, aliases for old variable names, `?theme=night` alias block via a `data-theme`
  attribute set by a 3-line inline script, base type, `.card .inset .stamp .chip .btn .nav .num`), `demo/fonts/` (Inter,
  Courier Prime woff2 + `OFL.txt`), a test `tests/test_demo_theme.py`: theme.css parses, every `@font-face` url exists,
  no `http(s)://` in any `demo/*.html` `<link>`/`<script>`.
- Not in scope: linking it from any page.
- Acceptance: test passes; a scratch HTML page renders the specimen (all tokens, both faces) offline in headless Chrome.
- If fonts cannot be downloaded through the proxy: ship the stacks only and note it; the look holds.

**WP2: Simulator view** · 2.5–3.5 h · risk **medium-high** (most visible page, no browser CI) · parallel with WP1 (after it lands, rebase), WP5
- Scope: `demo/flow.{html,js,css}`; `docs/demo_path.md` lines on flow.html; `demo/README.md` flow section.
- Steps, each committed separately so any can be reverted alone:
  1. Link `theme.css`; read `C` from tokens; dots and steps in the new colours; drop the background grid (pure theme, no layout change).
  2. Speed: absolute 0.5/1/2/4/8 days/s, default 2, `?speed=`.
  3. Queue colouring (04-sim-view.md rules) with the "N waiting" label; legend line.
  4. Default view: nav, `DAY` counter, headline card with three numbers, Details menu, drawers holding the old side
     cards unchanged in content.
  5. Optimise: Today-only start, changes card, Today/After toggle on the shared clock, stamp; `?compare` opens on
     After; side by side when `view=both` or width ≥1600.
- Acceptance: headless Chrome, no console errors, screenshots at 1440×900 and 1920×1080 for
  `flow.html`, `?s=finland`, `?s=finland&compare`, `?s=norway&compare`, `?s=norway&compare&left=authors&right=suggested_faster_pet`,
  `?paused&day=60`, `?layer=time`, `?theme=night`. Every Norway pair link built by `start.js` opens. Gate fast tests
  pass. A person who has not seen it finds Optimise and reads the before/after in under 30 s.
- Rollback: revert the merge commit; or, on the night, `?theme=night` for colours only.

**WP3: Overview page** · 1.5–2 h · risk medium (guarded and contended) · **only after `w8/jev-demo` merges**; parallel with WP2
- Scope: `demo/start.{html,js,css}`; `docs/demo_path.md` (rows → cards); README "Open this first" row text.
- Three-card top (03-information-architecture.md), one primary button, everything else below DETAILS; keep every
  existing number binding and every link (test needs ≥10 links; `jev.html` link must stay; Norway pair links must stay in `start.js`).
- Acceptance: `pytest tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_cards.py`; screenshots; top of
  page ≤ ~80 words; no number lost compared with the old page (diff the list of bound fields used by `start.js`).

**WP4: Theme on the remaining demo pages** · 45–60 min · risk low · after WP1; `jev.*` after jev-demo merges
- Scope: link `theme.css` in `encounter.html`, `jev.html`, `index.html` (CSS only; `<script id="bundle">` untouched);
  replace literal colours in `encounter.js`; speed options as in WP2; nav bar on each.
- Acceptance: `pytest tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_jev.py`; screenshots; Reveal truth still works.

**WP5 (stretch): How the patients work** · 2–3 h · risk low-medium (new file, but its claims need care) · parallel with WP2–4
- Scope: `demo/patients.html/.js` (new), a test like `test_demo_start.py`, one nav entry.
- Content per 03-information-architecture.md, including the two precision points (step 4 is a simulator privilege
  and a pilot in real life; hindsight bias). Numbers bound from `cards_bundle.js` and `demo_bundle.json`.
- Acceptance: test passes; a read by the review lane or Tuomas before it goes into the nav. If unread at 03:30 UTC, it ships unlinked.

### After the submission

| WP | What | Effort | Notes |
|---|---|---|---|
| WP6 | "Does it hold up" page + Norway case-study paper (`evidence.html`, `norway_case.html`, print CSS) | 4–6 h + review | Export any robustness figure not yet in `start_bundle.js` first (`export_start.py`); review lane reads the paper |
| WP7 | Web app: `web/src/theme.css` + `theme.ts`, replace 41 literals, one Optimise entry, Details menu, three headline numbers, slower clock, flip view after apply | 1 h tokens only; 1–2 days full | Update `web/scripts/shots.mjs` labels; gate "web" step |
| WP8 | One simulator: decide with Eemeli whether `live_demo/flow.html`, `demo/flow.html` and the web canvas converge on one renderer | design 2 h | Not ours alone |
| WP9 | `scripts/ui_shots.sh`: fixed URL list × two sizes into `runs/ui_shots/<commit>/`, console-error check, optional pixel diff; offline check (`--disable-network`) for every page | 1–2 h | Turns tonight's manual acceptance into a command |

## Order and parallelism tonight (from ~21:15 UTC)

```
21:15 ─ WP1 tokens ──────┐
21:15 ─ WP2.1 theme ─────┴─ WP2.2 speed ─ WP2.3 queues ─ WP2.4 default view ─ WP2.5 optimise ─┐   (one lane)
        (w8/jev-demo merges) ─ WP3 overview ─────────────────────────┐                        │
                         WP4 encounter / jev / index theme ───────────┤                        │
        WP5 patients page (stretch, separate lane) ──────────────────┤                        │
01:00 UTC checkpoint: what is merged is what ships; anything half-done stays on its branch ────┘
03:30 UTC last merge; 03:30–04:00 screenshots, gate, presenter run-through with docs/demo_path.md
```

Every merge goes through `scripts/gate.sh` and the screenshot pass. The integrator merges one package at a time and
reloads the three demo pages after each.

## Rollback

- Each package is one branch merged with `--no-ff`; rollback = `git revert -m 1 <merge>`; packages do not depend on
  each other except through `theme.css` (WP1), which stays harmless when nothing links it.
- WP2's five steps are separate commits; a single step can be reverted.
- During the night, `?theme=night` restores the old colours on any page linking `theme.css`, without a deploy.
- Bundles are never part of a UI package, so a UI revert never changes a number.
- If the simulator is broken at 03:30 UTC and the cause is not obvious in 10 minutes: revert WP2, ship the old page.
  The old page is known to work.

## What would make me stop a package

- Any change needed in an exporter or bundle to make the UI work: stop; it belongs to the data lanes.
- A caveat that does not fit anywhere: keep the old text, below DETAILS.
- A test that would need relaxing (for example the start page's no-digits rule): stop and ask Tuomas.

# Running the revamp in parallel lanes (everything else paused)

**In one line:** one short foundation lane lands the shared contract (tokens, classes, nav, page skeleton, test
helper, screenshot script) and freezes it. Six page lanes then run at the same time, each owning its own files and
nothing else. One integrator merges them and is the only one to touch shared docs. The critical path is foundation part A, then the
simulator lane, then integration: about 5 hours. If the pause starts by 22:00 UTC, all six page lanes fit before 04:00 UTC.

Assumption (Tuomas): while the revamp runs, no other agent touches the repository. The pause protocol is in
[08-pause-and-handoff.md](08-pause-and-handoff.md). Lane briefs, each ready to hand to a fresh agent, are in [lanes/](lanes/).
Merging `overnight/sim` at 21:10 UTC brought in `w8/jev-demo`: `demo/jev.html` exists and is linked from `start.html` row 5.
The plan treats it as an existing page to restructure (lane L5). Tuomas's decisions D60 to D63 (`docs/decisions.md`) are built into the briefs: D60/D61 settle the README's former open questions; D62 fixes the Norway framing for L4 (`docs/norway_case_study.md`, which now exists); D63 keeps the JEV page's model wording for L5.

## Lanes

| Lane | Goal | Owns exclusively (create/edit) | Depends on | Effort | Before freeze? |
|---|---|---|---|---|---|
| **L0 Foundation** | The shared contract, in two parts. **A** (frozen first): `theme.css`, fonts, class names. **B**: `site.js` nav/footer, page stubs, skeleton, test helper, screenshot script, handoff folder | `demo/theme.css`, `demo/fonts/**`, `demo/site.js`, `demo/_skeleton.html`, `demo/patients.html` + `demo/evidence.html` (**stubs only**; ownership passes to L3/L4 at merge), `tests/demo_pages.py`, `tests/test_demo_site.py`, `scripts/ui_shots.sh`, `docs/plan/ui-revamp/handoff/README.md` | snapshot | A 30 min, B 45 min | yes (first) |
| **L1 Simulator** | 04-sim-view.md: default view, Optimise flip, queue colours, speed, Details menu | `demo/flow.html`, `demo/flow.js`, `demo/flow.css`, `tests/test_demo_flow_page.py` (new) | L0-A (tokens), L0-B (nav) only for the nav step | 3–3.5 h | yes, **critical path** |
| **L2 Overview** | `start.html` as the Overview: three-card top, one primary button, the rest below DETAILS | `demo/start.html`, `demo/start.js`, `demo/start.css` | L0-A, L0-B | 1.5–2 h | yes |
| **L3 Patients** | New page: hidden truth, reveal, the five-step loop, why it is not overfitting | `demo/patients.html/.js/.css` (after L0's stub), `tests/test_demo_patients.py` | L0-A, L0-B | 2–3 h | yes |
| **L4 Evidence** | New page: Norway dot-and-range chart and robustness small multiples. The case-study paper comes after the submission | `demo/evidence.html/.js/.css` (after stub), `tests/test_demo_evidence.py`, **additive** fields in `demo/export_start.py`, and regenerating `demo/data/start_bundle.js` (under 1 s) | L0-A, L0-B | 2.5–3.5 h | yes, top and robustness; paper after |
| **L5 Decision model** | Re-theme `jev.html` and restructure it to the template: infographic and examples first, model card below DETAILS | `demo/jev.html/.js/.css` | L0-A, L0-B | 1.5–2 h | yes |
| **L6 Secondary pages** | Re-theme `encounter.html` (plus slower speed) and `index.html` (theme only; screen 5 "Before and after" keeps its layout and content, D66, script colours may change, the bundle block may not) | `demo/encounter.html/.js/.css`, the `<style>` part of `demo/index.html` | L0-A, L0-B | 1–1.5 h | yes |
| L7 Web tokens | `web/src/theme.css` + `theme.ts`, replace the 41 colour literals; no layout change | `web/src/**` | L0-A (copies token values) | 1 h | **no** (D60/D61: no React restyle for Sunday); brief ready for after the submission |
| **L8 Integrator** (the coordinator session) | Pause, snapshot, merges, shared docs, final handoff | `docs/demo_path.md`, `demo/README.md`, `README.md`, `CLAUDE.md`, `docs/plan/04-status.md`, `docs/master_plan.md` (one line), `docs/plan/ui-revamp/HANDOFF.md`, all merges | everything | running | yes |

**Nobody edits** during the revamp: `demo/export_*.py` (except L4, additive in `export_start.py`), `demo/export_all.py`,
`demo/embed_bundle.py`, any `demo/data/*` bundle (except L4's `start_bundle.js`), `pathway_sim/`, `optimiser/`,
`patient_engine/`, `jev/`, `decision_api/`, `live_demo/`, `note_reader/`, `video/`, `service/`, `scenarios/`, `params/`,
`docs/pitch/`, existing tests other than the lane's own (see below). Data is frozen at the snapshot. That way a UI
merge can never change a number.

### Existing tests and who may touch them

| Test | Lane | Rule |
|---|---|---|
| `tests/test_demo_start.py` | L2 | Must pass unchanged. No digits in page text; at least 10 links; `start.js` numerals within `{0,1,2,16,100}`; Norway pair links |
| `tests/test_demo_jev.py` | L5 | Must pass unchanged. `href="jev.html"` stays in `start.html` (L2), page text has no digits, the `jev.js` numeral whitelist holds, there is one `HF_URL` |
| `tests/test_demo_encounter.py`, `tests/test_demo_fixture.py` | L6 | Must pass unchanged; `<script id="bundle">` in `index.html` is not touched |
| `tests/test_demo_cards.py`, `tests/test_flow.py`, golden tests | nobody | data tests; must stay green |

If a lane thinks an existing assertion has to change, it stops and asks the integrator, who asks Tuomas. The numeral
whitelists are a design constraint: put design constants (thresholds, speeds) in CSS custom properties, `data-*`
attributes or `site.js`, not as numerals in `start.js`/`jev.js`. `flow.js` has no whitelist.

## The shared contract (lands first, then frozen)

L0 writes it; after L0-A merges, the integrator announces "contract frozen" on the channel. A later contract change
goes only through the integrator, is additive (new names, never renamed or removed ones), and is announced; lanes
merge `ui/main` into their branch to pick it up.

**Part A (frozen first, about 30 min):**
- Tokens in `demo/theme.css` `:root`, exactly the names in [05-theme.md](05-theme.md):
  `--paper --card --inset --ink --ink-2 --ink-3 --faint --line --mustard --mustard-ink --mustard-tint --brick --brick-tint --brown --carbon`,
  spacing `--s1`…`--s9` (4, 8, 12, 16, 24, 32, 48, 64, 96 px), type `--font-sans --font-mono`.
- Aliases for the old page variables (`--night`, `--p1`, `--p2`, `--text`, `--muted`, `--dim`, `--mint`, `--amber`, `--coral`,
  `--blue`, `--red`, `--violet`, `--line`, `--mono`, `--sans`) so an old page re-themes when it links `theme.css` after its
  own CSS. `html[data-theme="night"]` restores the old values.
- Shared classes: `.page`, `.page-top`, `.page-title`, `.lede`, `.figure`, `.caption`, `.details` (the DETAILS section),
  `.details-rule`, `.finding` (sentence headings below DETAILS), `.card`, `.inset`, `.stamp`, `.stamp--brick`, `.chip`, `.btn`,
  `.btn--primary`, `.btn--secondary`, `.num`, `.num--big`, `.label`, `.cmd`, `.footer-strip`, `.drawer`, `.drawer--open`.
  Lanes may add page-specific classes in their own CSS with a page prefix (`.sim-…`, `.ov-…`, `.pt-…`, `.ev-…`, `.jev-…`,
  `.enc-…`), never in `theme.css`.
- Fonts: `demo/fonts/` with Inter and Courier Prime `woff2` and `OFL.txt`, or none (stacks only) if they cannot be
  fetched. The decision is recorded in L0's handoff.

**Part B (about 45 min, can merge while page lanes are starting):**
- `demo/site.js` (no build, works from `file://`): `Site.nav(pageId)` fills `<nav class="site-nav" data-page="…">` with
  the five entries below; `Site.tokens()` returns the resolved token values for canvas/SVG code; `Site.footer(text)`
  fills `.footer-strip`; it reads `?theme=night` and sets `data-theme`.
- Page ids and files (fixed): `overview` → `start.html` · `simulator` → `flow.html` · `patients` → `patients.html` ·
  `evidence` → `evidence.html` · `model` → `jev.html`. Labels: Overview · Simulator · Patients · Evidence · Decision model.
  Brand on the left: EQUAL CARE PATHWAYS. Stamp on the right: SYNTHETIC PATIENTS.
- `demo/_skeleton.html`: the page template from 03-information-architecture.md (nav, `.page-top` with title, lede, figure,
  caption, one primary button; `.details`; footer strip; load order `theme.css` → page CSS → bundles → `site.js` → page JS).
- `demo/patients.html`, `demo/evidence.html`: stubs from the skeleton ("in preparation" text, no digits), so nav links
  resolve from the first merge.
- `tests/demo_pages.py`: a shared HTML parser and checks used by every lane's test: links/assets exist; no digit in page
  text outside `<code>`/`.cmd`; no `http(s)://` in `<link>`/`<script src>`; `theme.css` and `site.js` are linked; a
  `nav.site-nav[data-page]` exists. `tests/test_demo_site.py` runs the checks on every page that links `site.js`, and
  checks `theme.css` (font files exist, token names present).
- `scripts/ui_shots.sh <out-dir> [url-list-file]`: headless Chrome at 1440×900 and 1920×1080 for a fixed list of
  URLs (all pages and the simulator URL variants in 06-execution-plan.md WP2), writes PNGs and a `console.txt` with any
  console errors (via `web/scripts/` puppeteer-core or `/tmp`-installed puppeteer-core; plain `google-chrome --screenshot`
  as a fallback without console capture). Exit code 1 on console errors.
- `docs/plan/ui-revamp/handoff/README.md`: how lanes fill their part (template in 08-pause-and-handoff.md).

**Unchanged rules every lane inherits:** numbers come from bundles, never typed; caveats move below DETAILS but are
not deleted; existing URL parameters keep working; no "CLINICIAN-VALIDATED" anywhere; every page works from `file://`
with no network.

## Branches and merge order

```
overnight/sim ──tag ui-revamp-base──► ui/main (integration branch, integrator only)
                                        ├─ ui/l0-foundation   merge A, then B
                                        ├─ ui/l1-sim          ┐
                                        ├─ ui/l2-overview     │ each branched from ui/main after L0-A,
                                        ├─ ui/l3-patients     │ merges ui/main once after L0-B,
                                        ├─ ui/l4-evidence     │ then merged back by the integrator
                                        ├─ ui/l5-model        │ as soon as it is green
                                        ├─ ui/l6-secondary    ┘
                                        └─ (ui/l7-web after the submission)
ui/main ──(single --no-ff merge, after final checks)──► overnight/sim
```

One worktree per lane: `git worktree add /home/claude/wt/ui-lN -b ui/lN-name ui/main`.

Order: L0-A → L0-B → then **whichever lane is green first**, because the files are disjoint and merges cannot conflict.
Suggested if several are ready together: L6, L5, L3, L4, L2, L1 (lowest risk first, so the simulator merges onto a stable site).
The integrator runs `scripts/gate.sh` and `scripts/ui_shots.sh` after every merge into `ui/main`, and reloads all pages.

### Where conflicts could still come from, and the rule for each

| Shared thing | Rule |
|---|---|
| Navigation | Lives only in `site.js` (L0). No page hard-codes nav links. A page adds itself by having the right `data-page` |
| `start.html` (links to every page) | L2 only. Links to `patients.html`/`evidence.html` point at L0's stubs, so L2 does not wait for L3/L4. The synthetic-patients card moves to the Patients page: L3 renders it there (copying the rendering code from `start.js` at the base commit); L2 replaces it on the Overview with one link |
| `docs/demo_path.md`, `demo/README.md`, `README.md` | Integrator only, at the end, from the lanes' handoff notes. Lanes write presenter notes into their handoff file |
| Export scripts and bundles | Frozen; L4's additive `export_start.py` change is the one exception and is regenerated by L4 alone |
| Tests | New test files per lane; shared helper `tests/demo_pages.py` owned by L0 and frozen; existing tests unchanged |
| `HANDOFF.md` | Each lane writes only `docs/plan/ui-revamp/handoff/<lane>.md`; the integrator assembles `HANDOFF.md` |
| Theme changes a lane wants | Ask the integrator; additive only; never edit `theme.css` in a page lane |

## Machine and time budget

The machine is a shared 2-core box. Six lanes running headless Chrome and pytest at once will be slow. So: lanes run
only their own tests plus `pytest -q tests/test_demo_*.py` (seconds), and `ui_shots.sh` on their own URLs. The full gate
runs only in the integrator, once per merge. No lane runs exporters (except L4's under-a-second one).

## Critical path and what fits before 04:00 UTC

```
21:45 pause + snapshot (20 min)
22:05 L0-A ─ 22:35 contract frozen ─ L0-B ─ 23:20
22:35 ─ L1 simulator ──────────────────────────────────────── ~02:15 ─┐
22:35 ─ L2 · L3 · L4 · L5 · L6 ──────────────── 00:30–02:00 ─────────┤ rolling merges into ui/main
01:00 checkpoint: Tuomas looks at the screenshots of what is merged    │
02:15 L1 merged ─ 02:15–03:15 integrator: demo_path.md, README, HANDOFF.md, final gate + shots, rehearsal
03:15 merge ui/main → overnight/sim ─ 03:15–04:00 buffer
```

- **Critical path:** L0-A (30 min) → L1 (3–3.5 h) → integration (about 1 h). About 5 h. It has slack only if the pause
  starts by about 22:00 UTC. Each 30 min of delay comes out of the buffer, then out of L1's last step (Optimise animation polish).
- **Fits before the freeze now:** L0, L1, L2, L3, L4 (page top + robustness; links the existing `docs/norway_case_study.md`; the printable white-paper page comes after), L5, L6. Six page agents plus the foundation agent and the integrator.
- **Still after the submission:** the Norway case-study paper, the full React-app revamp (WP7 beyond tokens), one
  simulator for all surfaces (WP8, with Eemeli), pixel-diff regression.
- **Cut order if the night runs late** (drop from the bottom): L4 robustness small multiples (keep the one chart)
  → L3's reveal interaction (keep the static figure) → L1 step 5 animation (keep the plain toggle). Do not cut L0, L1 1–4, or L2.
- **Stop rule at 03:15 UTC:** anything not merged into `ui/main` stays on its branch. `ui/main` ships as it is, or, if the
  final shots show a broken simulator, `ui/main` without L1 (revert L1's merge) ships.

# UI revamp handoff (read before touching demo/, web/src/ or the presenter script)

Merged into `overnight/sim` at `49f96d0` (14 Nov, 22:47 UTC; gate PASS). Rollback point: tag `ui-revamp-base` (`ad7e386`);
the whole revamp is one `--no-ff` merge, so `git revert -m 1 49f96d0` undoes it. Follow-ups (this file, claim links on the
dashboard, `encounter.html?p=` landing, `.basis` tags, `ui_shots.sh` names) are on `w9/ui-followups`.
The lane notes this file is assembled from are in [handoff/](handoff/) (L0, L1-simulator, l2 to l6, l9); they hold the
full tables, tests and screenshots. Plan: [07-parallel-lanes.md](07-parallel-lanes.md), [08-pause-and-handoff.md](08-pause-and-handoff.md).

**Coming next (FYI 14 Nov 23:07):** branch `content/pages` holds copy for a slimmed site of seven pages (Introduction,
Simulation, Birch JEV, Birch in healthcare, Synthetic data, Research, Case study Norway); Tuomas wants the site cut to these.
When that lands, the nav (`Site.pages`) and the page list below change; the "Do not recreate" rules still apply.

## What a resumed agent does

1. Merge `overnight/sim` into your branch. Expect conflicts only if you edited a file listed under "Owned by the revamp" below.
2. Read "Do not recreate" and "Renamed and moved".
3. Before merging, grep your diff for the removed names (classes, URL parameters, element ids, page names) listed here.
4. New UI elements: use the tokens and shared classes in `demo/theme.css`; add a page to the nav only through `demo/site.js`;
   keep detail below the DETAILS rule; numbers bound from bundles, never typed.
5. If your work needs something the revamp removed, ask on the channel. Do not put it back on your own.

**Owned by the revamp** (edited by the UI lanes): `demo/theme.css`, `demo/fonts/`, `demo/site.js`, `demo/_skeleton.html`,
`demo/_specimen.html`, `demo/{start,flow,patients,evidence,jev,encounter,research}.{html,js,css}`, the `<style>` and drawing
colours of `demo/index.html` (not its `<script id="bundle">`), `tests/demo_pages.py`, `tests/test_demo_{site,flow_page,overview,
patients,evidence,jev_page,encounter_page,research_page,claim_links}.py`, `scripts/ui_shots.{sh,js}`, the additive
`evidence` field in `demo/export_start.py` / `data/start_bundle.js`.

## What the site is now

A light "paper" site of five pages in one nav (`site.js`): **Overview** `start.html` · **Simulator** `flow.html` ·
**Patients** `patients.html` · **Evidence** `evidence.html` · **Decision model** `jev.html`. Brand EQUAL CARE PATHWAYS on the
left, SYNTHETIC PATIENTS stamp on the right. Each page: title, one sentence, one figure, a caption, one filled button;
everything else below the DETAILS rule. Two pages are reached from others, not the nav: `research.html` (Research behind
the numbers, D69; nav marks Evidence) and `encounter.html` (primary-care loop; nav marks Simulator). `index.html`, the
six-screen results report, is re-coloured only (layout and text unchanged, D66) and has no site nav. Every number on a page
carries a basis tag (published research / our simulation / our assumption) that opens its row on `research.html#<claim id>`.
`?theme=night` restores the old dark look on every page that loads `site.js` (presenter fallback).

| Page | Lane | Top of the page now |
|---|---|---|
| `start.html` Overview | L2 | Three cards: Simulate (Finland median days), Optimise (Finland 18 → 33%), Check against a real hospital (Norway 40 → 67% best fit with range, PLAUSIBILITY CHECK); OPEN THE SIMULATOR |
| `flow.html` Simulator | L1 | Graph, big DAY counter, pathway dropdown, headline card (whole-run numbers), OPTIMISE flips the same patients onto the changed pathway (TODAY / AFTER THE CHANGE); everything else in DETAILS drawers |
| `patients.html` Patients | L3 | One example patient: sealed truth (Lift the seal) beside the visible record; the five-step loop with the reported Norway number |
| `evidence.html` Evidence | L4 | Norway headline today → reordered (no new equipment, best fit + range); dot-and-range chart of four rows; robustness small multiples below DETAILS |
| `jev.html` Decision model | L5 | Figure record → decision → allowed answers with scores → a person accepts or overrides (one real recording); examples; model card below DETAILS |
| `research.html` | L9 | Counts of the three bases with a bar, worked example of the waiting split, framing sentence; every claim as an expandable row |
| `encounter.html` | L6 | Primary-care loop graph and record, "Assumed behaviour" stamp; counters, results and caveats below DETAILS |
| `index.html` | L6 | Unchanged screens, paper colours; claim lines on screens 2 and 4 (follow-up) |

## Removed

| What | Where it was | Replacement |
|---|---|---|
| Dark theme: page `:root` palettes, blue background grid, gradients, glow, corner brackets, scanlines, mint/amber/blue/coral/violet accents | every page's CSS, `index.html` `<style>` | tokens and aliases in `theme.css`; `?theme=night` for the old look |
| Colour literal objects (`C = {...}` hexes) | `flow.js`, `encounter.js`, `index.html` script | `Site.tokens()` / CSS tokens (hex only as fallbacks inside the `C` block of `encounter.js` and `index.html`) |
| "← Demo start" back links, eyebrows, "Synthetic data only" / "Simulated patients" badges in page headers | `flow`, `jev`, `encounter`, `start` headers | site nav (brand links to the Overview) and its SYNTHETIC PATIENTS stamp |
| Six numbered rows of the start page (`.row .proof .go .btn.main .btn.sm .big .cap .honest .badge .eyebrow .card-block .pcol* details.more details.hidden-side`, row ids `s-*`) | `start.html/.css` | three `.ov-card`s; old content below DETAILS (ids `p-problem p-order p-trust p-primary p-honest ex-links go-order honest p-cards` kept) |
| Synthetic-patients card | start page | `patients.html`, DETAILS → "The same hidden facts, written two ways" |
| Simulator header: title, subtitle, scenario chips `#scn .chip.sc`, layer chips `#layers`, buttons `#cmp` `#zoom` `#view` | `flow.html` | nav; `<select id="scn">`; DETAILS → "Show on the graph", "Show change per step", "Draw larger and scroll", "Side by side" |
| Per-pane header `.phead` (variant select, big %, kv list, "vs left" chip), live counter row `.counters`, side column `aside.side` (Layer / Where time is lost / Check against the published study / Decisions / What you are looking at / trace), note strip `#note`, restart button `#restart`, 5-item legend `#legend` | `flow.html` | headline card `#head`; DETAILS → Counts now; one right-hand `.drawer` at a time; About; `r` key; three-item legend |
| Numbers on edges and second line on steps by default (D67) | simulator graph | hover/click readout; DETAILS → "Show all numbers on the graph" (`?numbers`) |
| Speeds as multiples of a horizon base; auto side-by-side at ≥1700 px | `flow.js`, `encounter.js` | absolute 0.5 / 1 / 2 / 4 / 8 days/s, default 2; side by side only via DETAILS or `?view=both` |
| Fixed bottom playback bar `footer.bar .play .clock .spd`; header sub-line ("amber waiting, blue being seen") | `encounter.html` | control row `.enc-controls` above the graph (same ids `#play #restart #day #slider #speed`); legend under the graph |
| Unprefixed page classes (`.card .lede .box .lane .facts .preset .cols .col .bar .prov .btn.main .eyebrow .badge .honest …` on jev; `.card .ln .ex .sum .x .key .rec .mk .truthbox .res .obar .olg .gt .prop .po .tip .gwrap .hit .legend` on encounter) | `jev`, `encounter` | `.jev-*`, `.enc-*` |
| Long "honest" footer paragraph | `jev.html` | DETAILS `#honest`; footers are the short `.footer-strip` |
| L0 "in preparation" stubs | `patients.html`, `evidence.html` | the real pages |

## Renamed and moved

| Old | New | Notes |
|---|---|---|
| "Left pathway" / "Right pathway", "vs left" | "Today" / "After the change" (or short pair names) | `sideName()` in `flow.js` |
| `S.compare`, `S.view`, `S.rate`, `.tip` | `S.deltas`, `S.split` + `S.side`, `S.speed` (days/s), `.sim-tip` | `?compare` now means "Optimise applied, toggle on After" |
| `#day` in the bar | `#day` as the big `DAY 021` counter | |
| Start rows 1–6 | DETAILS findings (problem, reordering, trust, primary care, decision model, data and honesty) | text kept; the 80%/80% line uses "·" not an arrow and a PREDICTED, NOT FITTED stamp |
| Model card at the top of `jev.html` | DETAILS `#model-card` (ids `hf d-enc arch-short arch-text facts diagram` kept) | wording unchanged (D63) |
| Encounter counters `#counters`, results `#results`, note `#note` | below DETAILS | still live |
| Encounter layer chips `.chip.on` | theme `.chip[aria-pressed]` | |
| Overview / Patients / Evidence claim tags (`.ov-basis__link` dotted links, `.pt-basis` grey boxes, `.ev-claim__basis` grey/brown boxes) | shared `.basis .basis--published|simulation|assumption` (theme.css), same looks as the research page legend | follow-up; page classes kept for layout |
| Dashboard brand "Equal care across Finland" | "Equal care pathways" (links to the Overview) | follow-up |

## Do not recreate

- No second filled button on any view: one `.btn--primary` per page (Overview: Open the simulator; Simulator: OPTIMISE, which turns secondary after it runs; Patients: Lift the seal; Evidence: Read the case study; Decision model: Try the examples; Research: Browse every claim).
- No hard-coded nav links or back links in pages: the nav comes only from `Site.pages` in `site.js`. Research is not in the nav (D60; Tuomas's call to change).
- No `:root` palette, hex colour, gradient, background grid, glow or scanline in page CSS; no colour literals in `flow.js`/`flow.css`/`evidence.css`/`jev.css`; no page-specific classes in `theme.css`; unprefixed page classes are gone.
- No web fonts or CDN links; fonts live in `demo/fonts/`. Every page works from `file://` with the network off.
- No digits typed in page HTML text (CSS counters for "1 SIMULATE", step numbers; numbers bound from bundles); numeral whitelists in `start.js`, `jev.js`, `evidence.js`, `research.js` hold. No digits in footer text written in HTML.
- No counters, layer/compare/large/view/scenario chips in the simulator header; no numbers on edges or steps by default (D67); no green, mint, blue or amber dots.
- No optimiser-with-faster-scanner row, band, pair, count or wording anywhere (D68); no faster-scanner number above DETAILS on the Overview; no optimiser best fit without its range beside it.
- No arrow between a published value and a simulated one (reads as before → after). No "beats/improves on the authors", "matches", "predicted exactly", "78 to 86%".
- No synthetic-patients card on the Overview (it lives on Patients). No truth in the static Patients page (`#pt-truth` empty and hidden until the seal is lifted).
- No model card, architecture diagram or fact table above DETAILS on `jev.html`; the figure shows only a `model`-mode recording, never a fixture, mock or the placeholder table.
- No counter row or results tables above DETAILS on `encounter.html`; brick only for "wrong" (truth ring and truth box are brown).
- No copy of the research register in JS or HTML (`research.js` reads `research_bundle.js`); no basis shown by colour alone (the tag carries the word; assumption tags are dashed).
- Do not remove `h += waitBasisNote();` from `lostCard` in `flow.js` (`tests/test_no_scanner_claims.py`).
- Do not edit `<script id="bundle">` in `index.html`; caveats moved below DETAILS are not to be deleted.
- No stamp or text claiming clinical validation anywhere.

## URL parameters

| Page | Parameter | Still works? | Behaviour now |
|---|---|---|---|
| all with `site.js` | `?theme=night` / `?theme=paper` | new | old dark values / clear; nav links carry `night` along. Not on `index.html` (no `site.js`) |
| `flow.html` | `?s=norway|finland` | yes | scenario |
| | `?compare` | yes, changed | opens with Optimise applied, toggle on After (no change card) |
| | `?left=` `?right=` | yes | the pair; implies Optimise applied. `start.js` uses `?s=norway&compare&left=observed&right=suggested` |
| | `?view=both|left|right` | yes | both = side by side; left/right = toggle position |
| | `?layer=flow|time|queues|decisions`, `?paused`, `?day=`, `?large` | yes | DETAILS layer; paused; day; draw larger |
| | `?speed=` (days/s), `?numbers` | new | speed; dense view with all numbers |
| `encounter.html` | `?p=<id>` | yes, improved | selects the patient and scrolls the side column to the record (follow-up; used by Patients and Decision model) |
| | `?paused`, `?day=`, `?layer=time`, `?truth` | yes | unchanged |
| `patients.html` | `?truth`, `?p=<id>` | new | seal lifted; that patient from `encounter_bundle.js` (default `cancer_as_infection`) |
| `jev.html` | `?api=hosted|same|recorded|<url>`, `#gp_visit #reasoning #triage #screening #compare #own` | yes | unchanged; the hash also scrolls to Examples |
| `research.html` | `#<claim id>` / `#<unsupported id>` | new | scrolls to the row, opens and outlines it; also on `hashchange` |
| `start.html` | `#details` | new | jumps to DETAILS |
| `index.html` | `#<scenario>/<screen>` | yes | unchanged |

## Data and bundles

- No bundle was regenerated by the UI lanes except L4's additive `START_DATA.evidence` (rows, ranking, grid, targets_as_one,
  noise, scanner_miss, optimiser counts/gains/ablation, structure) from `docs/review_checks/norway_*.json` via
  `demo/export_start.py`. Existing fields unchanged.
- New readers of `data/research_bundle.js` (D69): `start`, `patients`, `evidence`, `jev`, `flow`, `research`, and (follow-up)
  `index.html`. Claim ids are the contract: `research.html#<claim id>`, ids from `docs/research_claims.yaml`, never renamed.
  `tests/test_demo_claim_links.py` checks every id written in page code and every rendered link against the register.
- No longer read on the Overview: `CARDS_DATA.example.*` and `CARDS_DATA.libraries` (moved with the card to Patients).
- Known data issue (register frozen): two theme titles in `docs/research_claims.yaml` contain a comma inside a YAML flow
  mapping and are split; `research.js` joins them back. Fix after the freeze by quoting the titles and regenerating.
- `selection_optimism_pp` exists only in `demo_bundle.json`, so the Patients page explains it in words and links the dashboard.

## Tests and tools

- Per page: `test_demo_site.py` (contract), `test_demo_flow_page.py`, `test_demo_overview.py`, `test_demo_patients.py`,
  `test_demo_evidence.py`, `test_demo_jev_page.py`, `test_demo_encounter_page.py`, `test_demo_research_page.py`; shared
  checks in `tests/demo_pages.py` (`check_page`). Follow-up: `test_demo_claim_links.py`.
- Pre-revamp tests pass unchanged: `test_demo_start.py`, `test_demo_jev.py`, `test_demo_encounter.py`, `test_demo_fixture.py`, `test_demo_cards.py`.
- Screenshots: `bash scripts/ui_shots.sh <out> [url-list]` (1440×900 and 1920×1080, network off, `console.txt`, exit 1 on
  console errors). File names keep query and hash (`jev.html#gp_visit` → `jev_h_gp_visit_1440x900.png`); a `#` in the list
  file starts a comment only at the start of a line or after a space.

## Judgement calls for Tuomas

Collected from the lane notes; each is built one way and easy to flip.

1. **Overview card 3** shows the D68 Norway headline (no new equipment, best fit + range) with a PLAUSIBILITY CHECK stamp;
   the authors' 80 vs 80 is the head of a DETAILS finding. Alternative: 80 vs 80 on the card. Title repeats the brand
   (EQUAL CARE PATHWAYS); alternative "Overview". Top is about 105 words (plan: about 80) because the captions carry qualifiers. (L2)
2. **Simulator queue tint** thresholds (4% building, 10% piled up of the 300-dot sample, > 2 days waited); headline numbers
   are whole-run values, not live; missed cancers per cohort (27.5) where the old pane showed 55 over two cohorts; Finland's
   17-layer graph is about 9–10 px text at 1440×900 (use `+` / "Draw larger" on a projector). Group boxes and the return path
   are found by hard-coded node ids / short names. (L1)
3. **Patients**: example card under DETAILS comes from `gemini_s2_30` (old leaking results prompt) and its history
   contradicts its complaint ("no cough" vs "coughing constantly"); step five uses the Norway no-equipment number with claim
   `sim-no-noequipment-vs-scanner` (no claim id for the 40 → 67 number itself); the redacted bars are illustrative labels. (L3)
4. **Evidence** lede leads with the D62/D68 plausibility framing rather than the ranking sentence; published 95% intervals are
   not drawn (ring only); brick marks the scanner miss. If space is short, cut small multiples 3 and 4 first. (L4)
5. **Decision model** figure is the only `model`-mode recording: a synthetic skin-lesion intake, not lung cancer. Recording
   the GP-visit card (`export_jev.py --record`) would replace it automatically. (L5)
6. **Encounter / dashboard colours**: "left, symptoms persist" in brick (a second accent beside mustard; alternative `--ink-3`);
   truth ring brown; dashboard screen 4 keeps mustard for "more capacity, same order". `index.html` has no site nav (adding it
   means a second header above the tabs). (L6)
7. **Research page** chip colours (published solid ink, simulation mustard tint, assumption brick tint dashed; brick bends
   "brick means wrong"); rows start collapsed; Research not in the nav. These looks are now the shared `.basis` tag used on
   Overview, Patients, Evidence and the dashboard (follow-up); `flow.js` and `jev.js` still draw their own tag style. (L9, follow-up)
8. **Fonts vendored** (Inter, Courier Prime, latin subset, about 120 KB); alias values differ from the theme sketch where old
   pages used the colour as text (`--amber` → `--mustard-ink`, `--coral` → `--ink-3`). (L0)

## Presenter notes

Moved into [`docs/demo_path.md`](../../demo_path.md).

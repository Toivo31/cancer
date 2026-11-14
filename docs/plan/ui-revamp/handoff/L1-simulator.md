# Handoff: L1 Simulator (demo/flow.html)

Branch / merge commit: ui/l1-sim / see the RELEASE post (last code commit 0253e28)   Agent: claude-code@tuomas/l1   Finished: 14 Nov, about 23:50 UTC

## Summary (3 lines)
The Simulator opens on the graph, a big DAY counter, the pathway dropdown, three headline numbers and one filled
OPTIMISE button. Optimise types out the saved run's changes, outlines the steps they touch in mustard and flips the
same patients onto the changed pathway (TODAY | AFTER THE CHANGE). Everything else is under one DETAILS menu.

## Removed
| What | Where it was | Why | Replacement, if any |
|---|---|---|---|
| Header with title "Where time is lost: …", subtitle, "← Demo start" link | `header.top` in flow.html | nav + default view (04-sim-view.md) | `Site.nav('simulator')`; page `<title>`; one-sentence lede `#lede` in the left column |
| Scenario chips `#scn .chip.sc` | header | one dropdown | `<select id="scn">` (third entry opens encounter.html) |
| Layer chips `#layers` (Flow/Time/Queues/Decisions) | header | progressive disclosure | Details → "Show on the graph" radios (same `S.layer` values, `?layer=` unchanged) |
| Buttons `#cmp` Compare, `#zoom` Large, `#view` View | header | | Details → "Show change per step", "Draw larger and scroll" (`+`/`-` keys), "Side by side" |
| Pane header per graph (`.phead`: variant `<select>`, big %, kv list, "+15.6 pp vs left" chip) | each pane | headline card shows today → after | `#head` card; pair choice in Details → "Compare other pathways" |
| Live counter row `.counters` above each graph | each pane | | Details → "Counts now" (live, both sides) |
| Side column `aside.side` with cards Layer / Where time is lost / Check against the published study / Decisions / What you are looking at / patient trace | right of graph | | one right-hand drawer (`.drawer` from theme.css), one at a time, Esc closes. Card code and text kept (`lostCard`, `validationCard`, `decisionsCard`, `aboutCard`, `traceCard`); the "Layer: …" help card is now one line under the layer radios |
| Note strip `#note` under the graph | page bottom | | Details → "About this simulation" (same `renderNote()` text, now returned as a string); the pair caveat for authors-vs-optimiser and observed-vs-faster-scanner shows in `#pairnote` in the left column |
| Restart button `#restart` | bar | | `r` key, or drag the slider to the start |
| Legend `#legend` in the bar (5 coloured items) | bar | | three-item legend in the left column; full key in About |
| Numbers on edges and the second line on steps (patients, decisions) | graph, default | D67 | hover/click readout; Details → "Show all numbers on the graph" (`?numbers`) restores the dense view |
| Colour literal object `C = {night:…, mint:…}`, mint/amber/blue/coral dot colours, `.pane` gradients and corner brackets, background grid | flow.js / flow.css | theme | `C` is filled from `Site.tokens()`; flow.css has no `:root` and no hex colours |
| Speed options as multiples of `H/40` | `#speed` | D61 | absolute 0.5 / 1 / 2 / 4 / 8 days/s, default 2, `?speed=` |
| Auto side-by-side at ≥1700 px | `S.view` default | flip is the decided default (D60) | side by side only via Details or `?view=both` |

## Renamed or moved
| Old | New | Notes |
|---|---|---|
| "Left pathway" / "Right pathway", "vs left" | "Today" / "After the change" (or short names for other pairs: Optimiser, Authors' pathway, Faster scanner) | `sideName()` |
| `S.compare` (delta labels) | `S.deltas` (Details → Show change per step) | `?compare` now means "Optimise already applied, toggle on After" |
| `S.view` both/left/right | `S.split` + `S.side` | `?view=both|left|right` still read |
| `S.rate` (multiplier) | `S.speed` (days/s) | |
| `.tip` | `.sim-tip` (one card for steps, connections and dots; click pins it) | |
| Patient day `#day` in the bar | `#day` as the big `DAY 021` counter, top left | zero-padded to three digits |

## Added
| What | Where | Contract or page-local |
|---|---|---|
| Optimise button `#optimise`, change card `#optcard`, flip `#flip` (`.sim-toggle`), stamp "Saved optimiser run · held-out patients" (Finland) / "· best fit" (Norway) / "Saved simulation" (pairs without changes) | flow.html/js | page-local |
| Quiet link "See both pathways drawn step by step" → `index.html#stokstad/5` or `#finland_lung/5` (D66) | `#flip-link` | page-local |
| Headline card `#head`: treated within target, median days, cancers missed per cohort (row only when any variant has missed cancers, so not for Norway); Norway sub-line with the best-fit range across fitting settings from `START_DATA.norway.optimiser.bands`; basis chip "Our simulation" + link `research.html#<claim id>` (D69) | `.sim-head` | page-local |
| Queue tint: `QUEUE` constant in flow.js | steps | page-local |
| Return path (brown, the word "return") into and out of "Re-presents to GP"; dashed group boxes "Hospital" and "Tests" (`GROUPS` constant) | graph | page-local (D67). The base page had neither; they are new, not restyled |
| Details menu `#menu` and drawers: Where time is lost, Check against the published study (Norway), Compare other pathways, All results, Counts now, Decisions, About this simulation (with key), links to encounter.html, evidence.html, research.html | | page-local |
| `?speed=`, `?numbers` | | |
| `tests/test_demo_flow_page.py` | | |

## Do not recreate
- No counters, layer chips, compare/large/view chips or scenario chips in a header: they live in Details.
- No second filled button: OPTIMISE is the only `.btn--primary`; after it runs it turns secondary ("Show the changes").
- No numbers on edges or steps by default (D67); numbers come on hover/click or from "Show all numbers on the graph".
- No colour literals in flow.js/flow.css: colours come from `Site.tokens()` / theme tokens (the test checks this).
- No optimiser-with-faster-scanner pair or wording (D68); Norway offers observed, suggested, faster_pet, authors only.
- No green, mint, blue or amber: dots are ink/grey, mustard and brick only for queues, brick ring for a missed cancer.
- Do not remove `h += waitBasisNote();` from `lostCard` (tests/test_no_scanner_claims.py checks it).

## URL parameters
| Parameter | Still works? | Behaviour now |
|---|---|---|
| `?s=norway|finland` | yes | scenario |
| `?compare` | yes | opens with Optimise applied, toggle on After (no change card) |
| `?left=` `?right=` | yes | the pair; also opens with Optimise applied. start.js's `?s=norway&compare&left=observed&right=suggested` opens that pair (tested) |
| `?view=both|left|right` | yes | both = side by side; left/right = toggle position (both imply Optimise applied) |
| `?layer=flow|time|queues|decisions` | yes | Details layer |
| `?paused` `?day=` | yes | |
| `?large` | yes | draw larger and scroll |
| `?theme=night` | yes | via site.js; canvas colours follow |
| `?speed=` (new) | yes | days per second; values outside the list are added to the dropdown |
| `?numbers` (new) | yes | dense view (all numbers on the graph) |

## Data and bundles
Read: `FLOW_DATA` (graph, steps, decisions, exits, queues, time_lost, cohort, metrics, totals, variants[].changes/label/note, published, wait_basis), `START_DATA.norway` (all_settings, optimiser.bands/counts/structure/n_settings), `START_DATA.validation.published`. No longer read: nothing dropped. No export change.

## Tests
New: `tests/test_demo_flow_page.py` (8 tests): shared page checks (theme.css first, site.js, nav `data-page="simulator"`, no digits, offline assets); no colour literals in flow.js/flow.css; every `flow.html?…left/right` link in start/evidence/index exists in the bundle; every old URL parameter is still read; no optimiser-with-scanner variant; caveat strings kept; puppeteer smoke (8 URLs, no console errors with networking off; headline numbers at `day=999` on Finland equal `flow.metrics` of both variants, formatted; pairs, split, side, layer and speed taken from the URL). Skips the browser part if node/Chrome/puppeteer-core are missing.
Run and passing: test_demo_flow_page, test_demo_site, test_demo_start, test_demo_jev, test_demo_encounter, test_demo_fixture, test_demo_cards, test_no_scanner_claims (61 passed).

## Screenshots
`runs/ui_shots/l1/` (not committed; `scripts/ui_shots.sh runs/ui_shots/l1 <list>`), 1440×900 and 1920×1080 for: flow.html, ?s=finland, ?s=finland&compare, ?s=norway&compare, the authors/suggested and observed/faster_pet pairs, ?paused&day=60, ?layer=time, ?s=finland&view=both, ?theme=night; plus playback (`play_fin_after_t1/t2`, `play_nor_today_t2`) and interactions (`i_menu`, `i_drawer_check`, `i_drawer_lost`, `i_hover_node`, `i_pin_node`, `i_trace`). Console errors: none (ui_shots runs with `--host-resolver-rules="MAP * ~NOTFOUND"`, so this is also the offline check).

Skim test: I looked only at the default 1440×900 shot as a first-time reader: DAY counter, "Each dot is a simulated patient moving through the lung-cancer pathway. Where dots pile up, patients wait.", a graph with two or three tinted steps labelled "N waiting", the headline share, and one black OPTIMISE button. The one-sentence message I read off it: "simulated patients wait at a few steps; press Optimise to see what a reorder does to the share treated in time". After Optimise the card lists the changes and the headline reads today → after.

## Presenter notes
- Open `flow.html?s=finland`. Say: every dot is a simulated patient; piles are waiting; steps turn mustard then brick as a queue forms.
- Press OPTIMISE: the two changes type out; the steps they touch get a dashed mustard outline; the view flips to After. Headline: share within 90 days today → after, median days, cancers missed unchanged (the guardrail). Say "saved optimiser run, held-out patients; this page does not search live".
- Flip TODAY / AFTER THE CHANGE to show the same day on both pathways. Speed 0.5–8 days/s at the bottom; Space plays/pauses, arrows step, r restarts.
- Hover a step for its numbers (click pins, Esc closes); click a dot for that patient's path.
- Norway: `flow.html?s=norway&compare` opens on After with the best-fit range under the headline. Details → "Check against the published study" holds the table and all caveats. "See both pathways drawn step by step" opens dashboard screen 5.

## Open issues and judgement calls
- **Queue thresholds**: 4% building, 10% piled up of the 300-dot sample (12 / 30 dots), waited > 2 days, smoothed over 3 playback days, leave at 80% of the threshold; same for both scenarios and both sides. Sampled every 10 days, about two to five steps are tinted at a time and the After view clears earlier (Norway After has no tinted steps from day 50, Today still has). Norway's piles are not smaller than Finland's (its sample is all cancer patients), so one rule fits both. Early steps (Finland GP appointment, Norway first visit) go brick within days because the whole sample starts on day 0; that is real waiting (median waits of 10–14 days), not the day-0 artefact, which the 2-day rule removes.
- **Headline numbers are whole-run values** (`flow.metrics`), not live counts: they are the same at every playback day, labelled "whole run". Live sample counts are in Details → Counts now.
- **Missed cancers** use `metrics.missed_cancers` (per cohort, 27.5) as the numbers sheet does; the old pane showed `totals.missed_cancers` (55 over two cohorts). Row hidden for Norway (always 0); in All results.
- **Touched steps** = steps where a connection newly arrives or no longer arrives, plus choices whose shares moved by > 2 points (Finland: specialist visit, waiting for treatment slot; Norway: six). Added connections are not coloured by default (only in "Show change per step", dashed); the mustard outline is the one change cue.
- **Delta labels** ("−2.5 d on path") only under "Show change per step" and only |Δ| ≥ 0.5 d.
- **Horizons**: the clock runs to the longer variant; After simply finishes first. No caption line was added for that; consider one.
- **Group boxes** are hard-coded by node id (`GROUPS`), Hospital and Tests for Finland, Tests only for Norway (the whole Norwegian pathway is in hospital). The return path is found by the step's short name ("Re-presents …"). If the exporter renames those, the boxes or the return colour silently disappear.
- **Side by side** at 1920 makes each graph about 600 px wide with small labels; it stays optional.
- Graph text at 1440×900 for Finland's 17-layer graph is about 9–10 px after fitting; "Draw larger and scroll" (`+`) helps on a projector. A horizontal layout would read better at 16:9 but was not attempted tonight.
- `research.html#<claim id>` links point at L9's page; they resolve once L9 is merged.
- `encounter.js` still has the old speed code (lane L6's file).
- The handoff file name follows the lane brief (`L1-simulator.md`); the integrator's message said `l1.md`.

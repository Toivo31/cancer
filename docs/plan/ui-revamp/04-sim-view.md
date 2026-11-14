# The Simulator view (`demo/flow.html`)

**In one line:** by default you see the graph, a big day counter, three numbers and one Optimise button. Pressing
Optimise lists the changes and flips the same patients onto the new pathway. Steps where patients pile up turn
mustard, then brick. Everything else sits under one Details menu.

## Default view at 1440×900

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ EQUAL CARE PATHWAYS   Overview · Simulator · Patients · Evidence · Decision model  [SYNTHETIC]│  nav 44px
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ DAY 021                 FINLAND (SYNTHETIC COUNTY) ▾                        ┌──────────────┐ │
│ days since first contact                                                     │ TREATED ≤ 90 D│ │
│                                                                              │ 18%  →  33%  │ │
│                 [ TODAY | AFTER THE CHANGE ]  (appears after Optimise)       │ median 102→94│ │
│                                                                              │ missed 28→28 │ │
│                                                                              └──────────────┘ │
│                         the graph, full width, thin grey lines,                              │
│                         black/grey dots, piles above steps;                                  │
│                         steps tinted mustard or brick by pile size                           │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▶  ───────●──────────────────  speed 2 d/s ▾      [ OPTIMISE ]                   DETAILS ▾  │  bar 56px
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Default-visible vs moved

| Element today | Default view | Where it goes |
|---|---|---|
| Graph with moving dots and piles | **visible**, full width | |
| Patient day | **visible**, large top-left (`DAY 021` as in the video) | |
| Scenario switch (Norway / Finland) | **visible**, one dropdown under the title; third entry opens the primary-care loop page | |
| Headline numbers | **visible**: 3 (below) | |
| Play/Pause, slider | **visible** | Restart moves to the slider's start (click 0) and the `r` key |
| Speed | **visible**, compact | |
| Optimise / before-after | **visible**: one primary button, then a two-way toggle | |
| Layer buttons Flow / Time / Queues / Decisions | hidden | Details → "Show on the graph: patients (default) · waiting time per step · queue over the year · decisions" |
| Compare, Large, View toggles | hidden | Details → "Side by side", "Show change per step", zoom with the browser or `+`/`-` |
| Counter row (waiting / served / on time / late / discharged / missed, live) | hidden | Details → "Counts now" (and the legend tooltips) |
| "+15.6 pp vs left" chip, variant dropdown | hidden | Headline card shows today → after; the variant list is in Details → "Compare other pathways" (Norway's five variants) |
| Side card "Layer: …" help | removed | Each Details layer item has one line of help |
| Side card "Where time is lost" | hidden | Details → "Where time is lost" (drawer from the right) |
| Side card "What you are looking at" | shortened | One caption line under the graph; full text in Details → "About this simulation" |
| Norway "Check against the published study" | hidden | Details → "Check against the published study", plus a link to the Evidence page |
| Click-a-dot patient trace | on demand, unchanged | drawer from the right, closes on Esc |
| Legend (5 items) | 3 items inline in the caption: "● moving or being seen · ○ waiting (grey) · steps tint as patients pile up" | full legend in Details |
| "Simulated patients" badge | stamp in the nav | |

## The three headline numbers, and why these

1. **Treated within the target** (`metrics.share_within_target`, 42 days Norway, 90 days Finland). This is the
   brief's own indicator (Goal 3, indicator 3.1) and the pitch headline. It is the number Optimise moves.
2. **Median days to treatment** (`metrics.median_days_to_treatment`). A time in days is easier to picture than a
   share. It also shows when the share moves a lot but the median moves little (Finland: 102 → 94).
3. **Cancers missed** (`metrics.missed_cancers`, "sent home"). This is the guardrail: the change must not buy speed
   with missed cancers. It is the first question a clinician asks.

Left out: tests per patient, invasive procedures, cost, patient counts, "cancers sent home" for Norway (always 0 there;
show the row only where the scenario has non-zero values). They stay in Details → "All results".
Numbers keep the run's own precision rules from the numbers sheet (one decimal for shares, as today).

## Optimise and the before/after comparison

**Interaction (lean):**
1. The page opens on **Today** only. The headline card shows one column. The bottom bar shows **OPTIMISE**, the only
   filled (ink) button on the page.
2. Pressing it opens a small card over the graph. It lists the changes from `variant.changes` (Finland 2, Norway 4)
   one per line at about 0.6 s intervals, typed in Courier Prime. The steps each change touches are outlined in
   mustard on the graph.
3. The card collapses into the toggle `[ TODAY | AFTER THE CHANGE ]`. The view flips to After, the dots continue
   from the same day, and the headline card shows `today → after` for all three numbers.
4. A stamp beside the toggle: "SAVED OPTIMISER RUN · results on held-out patients". The offline page replays the
   saved result. It does not search live (Q3). For Norway the default pair stays as today (observed vs the
   no-new-equipment optimiser), and Details lists the other pairs (authors' pathway, faster scanner, with scanner).

**Comparison options, weighed against what the code already does:**

| Option | What it is | In code today | For | Against | Lean |
|---|---|---|---|---|---|
| **Flip (toggle)** | One canvas; Today and After share the layout (`layoutUnion`) and the clock (`S.t`), so a step sits at the same pixel in both | layout and clock: yes; toggle: new (small) | Full-width graph at 1440; flip reveals exactly what moved (motion is pre-attentive); works on a projector | Cannot see both at the same instant | **Default** |
| Side by side | Two panes, same layout | yes (`view=both`), but only ≥1700 px | Simultaneous view | At 1440 each pane is ~600 px and labels go unreadable; today it silently shows one pane | Offer in Details; auto when width ≥1600 |
| Delta overlay | After pane, each step annotated `−2.5 d on path`, removed links dashed | yes (`compare`) | Shows *where* the gain is | Most steps read `0.0 d`, which is noise; numeric clutter on the graph | Details toggle "Show change per step"; hide `0.0 d` labels (show only \|Δ\| ≥ 0.5 d) |
| Diff of structure only | Today vs After drawn statically, added/removed in colour | web `DiffView`; dashboard screen 5 | Explains the change itself | No patients moving, so no queues | Belongs on the Evidence/Patients pages, not here |

Horizons differ between variants (Norway: 161 vs 93 days). The shared clock should run to the larger one. The After view
then shows everyone treated while Today still has piles. That is the point, and a single caption line can say it.

## Queue colouring

**What drives it (lean, Q5):** the number of *sampled* dots waiting at a step at the current playback day (`groups[nid]`
with state `w` in `drawDots`). The thresholds are fixed per scenario and shared by Today and After, so the flip compares like with like:

| State | Rule (proposal; tune by eye on both scenarios) | Look |
|---|---|---|
| calm | fewer than 4% of the sample waiting there (12 of 300) | card fill, 1 px ink outline |
| building | 4% to 10% (12 to 30 dots) | mustard tint `#F1E4BD`, 2 px mustard `#B8902F` outline, label "18 waiting" in mustard-ink |
| piled up | over 10% (30+ dots) | brick tint `#E8CFC4`, 2 px brick `#9E3B2A` outline, label "41 waiting" in brick |

- **The day-0 artefact.** Every patient starts at day 0, so at the start all 300 dots sit on the first steps
  (visible in `current/02_flow_finland_compare.jpg`). A plain count would turn the entry steps brick at once. Count only
  dots that have already waited more than about 2 days at that step (`t − t_ready > 2`). The colour then means "a queue
  has formed", not "everyone has just arrived".
- Smooth over about 3 playback days and use hysteresis (enter at the threshold, leave at 80% of it), so steps do
  not flicker.
- Not colour alone: the outline weight changes, and the "N waiting" label appears only in the two warm states.
- Be honest in the legend: playback runs on each patient's own day since first contact, not on the calendar, so a
  pile is "sampled patients who are waiting here at the same point in their own pathway". This matches the video's
  "piles are waiting". The calendar-year queue (`flow.queues`, peak and mean) stays as the Details layer "Queue over the
  year".
- Alternatives considered: waited time of the dots at a step (≥7 d mustard, ≥21 d brick). It is meaningful clinically,
  but a single long-waiter turns a step red, and the dot colour already encodes it. Static colouring from
  `steps.wait_median` (all patients) is stable and exact, but does not "turn" as the run plays, which is what Tuomas asked for.
- Dots: moving or being served = ink `#1E1D1A`; waiting = grey `#9C978C`, darkening slightly with waited days
  (replaces today's amber→orange); treated in time = ink, resting at the exit; treated late = hollow ink ring; cancer
  missed = brick ring. Five states on two hues.

## Speed

Today: multipliers of `H/40` days/s, so the slowest is about 2 days/s. Proposal: absolute options
**0.5, 1, 2, 4, 8 days/s**, default 2 (Q9). Finland's ~168-day run then takes about 85 s at the default and 5½ min at
the slowest. Keep `?speed=` as a new URL option for the presenter. The same change applies to `encounter.js`
(same `S.base` code) and, after the submission, to the web clock (`Clock(horizon, seconds = 45)`).

## Details menu (one button, bottom right)

```
DETAILS ▾
  Show on the graph   ( ) patients  ( ) waiting time per step  ( ) queue over the year  ( ) decisions
  [ ] Show change per step          [ ] Side by side
  Where time is lost  ›             Check against the published study  ›   (Norway only)
  Compare other pathways  ›         All results  ›
  Counts now  ›                     About this simulation  ›
  Primary-care loop (other page) ›  Evidence page ›
```
Drawers open from the right over the graph (one at a time) and close on Esc. Their content is today's side cards,
restyled, not rewritten. That keeps the honesty text intact and the change small.

## URL compatibility (must hold after WP2)

`?s=norway|finland`, `?compare` (opens with Optimise already applied and the toggle on After), `?left=` / `?right=`
(the pair), `?view=both|left|right` (both = side by side; left/right = toggle position), `?layer=` (Details layer),
`?paused`, `?day=`, `?large`. New: `?speed=`, `?theme=night` (old palette, until after the submission).
Used by: `demo/start.js` (Norway pairs, tested), `docs/demo_path.md`, README.

## The React app (after the submission, WP7)

Apply the same rules: one Optimise entry (keep the side tab, drop the toolbar button, or the reverse); layers into
a Details menu; three headline numbers in the playback bar instead of six counters; fit the graph to readable label
size rather than to the window; the run → optimise → apply → rerun → compare flow stays, but ends on the same flip
view. `web/scripts/shots.mjs` clicks `.toolbar .tab` by label (Flow, Time, Queues, Decisions, Structure) and must
be updated with it.

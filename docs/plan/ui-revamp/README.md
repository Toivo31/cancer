# UI revamp plan (start here)

**In one line:** one quiet paper-coloured site with five pages, and a simulator whose default view shows the
graph, a day counter, three numbers and one Optimise button. Everything else moves one click down.

Status: plan only, written Sat 14 Nov ~21:00 UTC on branch `w8/ui-plan`. No product code has changed.
Submission Sun 10:00 Helsinki; code freeze 04:00 UTC.

| Proposal | Where it is argued |
|---|---|
| **Which surface the judges see:** the offline `demo/` pages are the site. `demo/flow.html` is the simulator. The React app (`web/`) is "the platform behind it": it stays out of the default path until after the submission | [02-audit.md](02-audit.md) |
| **Five pages:** Overview, Simulator, How the patients work (data cards and hidden variables), Does it hold up (Norway and robustness, with the case-study paper), Decision model (JEV demo and model card). The dashboard (`index.html`) and the encounter loop stay reachable, but from page bottoms, not the nav | [03-information-architecture.md](03-information-architecture.md) |
| **Simulator default view:** graph, `DAY 021` counter, three numbers (treated within target, median days to treatment, cancers missed), Play, speed, **Optimise**. Before/after is a flip between two views on one layout and one clock. Side by side and per-step deltas are options. Nodes turn mustard, then brick, as patients pile up. Slowest speed 0.5 days/s, down from about 2 | [04-sim-view.md](04-sim-view.md) |
| **Theme:** warm off-white paper, near-black ink, Inter for headings (caps) and body, Courier Prime for labels, stamps and command chips. Mustard and brick appear only where something is waiting or wrong. Fonts are vendored so the pages work offline. Implemented as one tokens file per surface | [05-theme.md](05-theme.md) |
| **Execution:** nine small work packages. Four fit before the freeze (tokens, simulator, Overview, theme on the remaining pages), plus one stretch (patients page). Each package is one branch and can be reverted with one merge revert | [06-execution-plan.md](06-execution-plan.md) |
| Principles and what each one changes here | [01-principles.md](01-principles.md) |

Evidence used: screenshots at 1440×900 of every surface as it is today (`current/`, taken 20:48 to 20:50 UTC), and
Tuomas's six reference frames from the pitch video (`reference/`).

## The cut line

| Before the 04:00 UTC freeze (in this order) | After the submission |
|---|---|
| WP1 tokens and vendored fonts (new files only) | WP6 "Does it hold up" page and the Norway case-study paper |
| WP2 simulator: theme, default view, Optimise flip, queue colours, slower speed (`demo/flow.*`) | WP7 web app: tokens, the same default-view rules, one Optimise entry |
| WP3 Overview: restyle `start.html` with the three-card top (after `w8/jev-demo` merges) | WP8 one simulator instead of three (`demo/flow`, `web/`, `live_demo/`), with Eemeli |
| WP4 theme on `encounter.html` and `jev.html` (token swap only) | WP9 screenshot regression script and an offline test for every page |
| *Stretch:* WP5 "How the patients work" page | |
| Presenter script `docs/demo_path.md` updated inside WP2 and WP3, not afterwards | |

Rough total before the freeze: 5 to 7 focused hours of agent time plus about 1 hour of Tuomas's review, against
about 7 hours left. The other lanes merge at the same time (status "Next": jev-demo, fi-sens, bundle regeneration),
so the realistic target is **WP1 + WP2**, with WP3 and WP4 if they go cleanly. WP2 is the one with the most demo value.

## Riskiest parts

1. **`demo/flow.js` (737 lines, untested in the browser by CI).** No automated test opens the page. A broken
   simulator is the worst outcome of the night. Mitigation: URL parameters stay backwards compatible, there is a
   headless-Chrome console-error check and a screenshot pass per package, and the old palette stays one URL away
   (`?theme=night`) until after the submission.
2. **`demo/start.html` is guarded and contended.** `tests/test_demo_start.py` forbids typed digits in the page text and limits
   numbers in `start.js`. `w8/jev-demo` is editing row 5 right now. `docs/demo_path.md` refers to rows by number.
   Do it only after jev-demo merges, and update the script in the same package.
3. **Honesty drift while rewriting text.** Shorter text tempts rounding and dropping caveats. Every number stays
   bound from a bundle, caveats move down the page but are not deleted, and the video's "CLINICIAN-VALIDATED" stamp
   must not appear on the site (no clinician has reviewed anything).
4. **Fonts offline.** Inter and Courier Prime are loaded from Google Fonts today (video, `live_demo/`). The site must
   vendor them (SIL OFL allows that). If the files cannot be fetched tonight, the fallback stacks still look right.
5. **Mustard and brick at the queues read as a judgement.** A node marked brick says "problem here". The thresholds
   are ours and the playback clock is patient days, not calendar days. The legend has to say what drives the colour.

## Decisions for Tuomas (short; each with my lean)

| # | Question | Lean |
|---|---|---|
| Q1 | Judges' main surface: offline `demo/` site, or the hosted `live_demo/` (Eemeli), or the React app? | `demo/` site, with `flow.html` as the simulator. It works from disk, its results are the held-out ones and it has tests. `live_demo/` stays the hosted URL if Eemeli wants that, restyled to match later |
| Q2 | Five pages (Overview, Simulator, Patients, Evidence, Decision model) or three (Overview, Simulator, Evidence)? | Five. You asked for the patients page explicitly. Three only if the night runs short |
| Q3 | Optimise in the offline simulator replays the saved optimiser result. It does not search live. OK to label it "Optimiser result (saved run)"? | Yes. A live search needs the service and minutes of compute. The React app keeps the live one for later |
| Q4 | Before/after: flip (default), side by side, or deltas overlaid? | Flip by default, side by side on screens 1600 px and wider, deltas as a toggle. All three exist in code today |
| Q5 | Queue colour driven by how many sampled patients are waiting at a step (pile size), or by how long they have waited? | Pile size, with fixed thresholds per scenario shared by before and after. Waiting time stays in the "Time" detail layer |
| Q6 | Paper tint: near-neutral like the video (`#F8F7F2`) or more yellow "80s paper" (`#F4F0E4`)? | `#F4F0E4`. Check it next to the reference frames on the projector |
| Q7 | Reuse the video's DEFINE / AUTOMATE / VALIDATE three cards on the Overview? | Reuse the look, not the words. Our three are "Simulate", "Optimise", "Check against a real hospital". In the video, VALIDATE means clinicians approve a pipeline, and nobody has done that here |
| Q8 | Norway white paper before the freeze? | No, after. Before the freeze, link `docs/validation.md`. Written fast at night it is where overclaiming would slip in |
| Q9 | Default playback speed | 2 days/s (Finland's whole run about 85 s); slowest 0.5 |
| Q10 | Does the React app need restyling for Sunday? | No, unless it is shown live. Then WP7's token swap alone (about 1 h) |

Open item: compare the proposed palette and type against the reference frames on the actual presentation screen.
They were read from compressed video frames, and their tint differs from the video's own CSS (`#fbf9ef`, see 05-theme.md).

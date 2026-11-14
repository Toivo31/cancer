# Lane L1: Simulator (demo/flow.html) — critical path

A self-contained brief for one coding agent. Branch `ui/l1-sim`, worktree `/home/claude/wt/ui-l1`.

## Goal

Turn `demo/flow.html` into the Simulator described in `04-sim-view.md`. By default: the graph, a large day counter,
three headline numbers (treated within the target, median days to treatment, cancers missed), Play/slider/speed and one
**Optimise** button. Everything else sits under one Details menu. Optimise shows the saved optimiser result: the changes,
then a Today / After-the-change flip on the same layout and clock. Steps where patients pile up turn mustard, then
brick. Speed goes down to 0.5 days/s. You are on the critical path. Keep each step a separate, working commit so the
integrator can merge part of it if time runs out.

## You own (create or edit only these)

`demo/flow.html`, `demo/flow.js`, `demo/flow.css`, new `tests/test_demo_flow_page.py`, your handoff file.

## You must not touch

`demo/data/*` (`flow_bundle.js`, `start_bundle.js` are read-only), `demo/export_flow.py`, other pages, `theme.css`,
`site.js`, `tests/demo_pages.py`, existing tests, `docs/demo_path.md` and READMEs (write presenter notes into your
handoff instead).

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

Suggested order of commits (each one a working page): (1) link `theme.css` and `site.js`, take canvas/SVG colours from
`Site.tokens()` instead of the `C` literal at the top of `flow.js`, remove the background grid; (2) speed in absolute
days/s (0.5/1/2/4/8, default 2, `?speed=`); (3) queue colouring; (4) default view and Details menu (the existing side
cards move into drawers, content unchanged); (5) Optimise and the flip. Judgement is yours on:
- Layout of the headline card and the day counter at 1440×900 (look at `reference/06_pathway_dots.png`), and how
  Details drawers and the patient trace share the right edge.
- Queue colouring: `04-sim-view.md` proposes counting sampled dots that have waited more than about 2 days at a
  step, thresholds fixed per scenario and shared by Today and After, with smoothing and hysteresis. Try it on both scenarios
  and both variants; consider whether the thresholds look right (entry steps at day 0, Norway's smaller piles), and
  record the values you chose and why. Show it not by colour alone ("N waiting" label, outline weight).
- Optimise: how the list of `variant.changes` appears and how the changed steps are highlighted; how to label it
  honestly as a saved run reported on held-out patients; Norway's other variant pairs under Details. Weigh flip vs side by side
  at different widths (side by side today only turns on at ≥1700 px, see `02-audit.md`).
- **Link to the dashboard's Before and after page (D66):** after Optimise, one quiet link "See both pathways drawn step by step" to `index.html#<scenario>/5` (the dashboard reads `#<scenario>/<screen>`; check the scenario keys it accepts). That page is not yours to change.
- **Graph drawing (decided, D67, Tuomas): read `04-sim-view.md`, "Graph drawing".** Edge strength by thickness only, numbers on hover; nodes show only their name, with the activity number on hover or click; keep the return path in its own colour with the word "return" and the dashed boxes around tests and the hospital (both are in the current page: find them in `flow.js` and `current/` screenshots before restyling, and do not lose them); use colour only where it aids reading. Your judgement: the hover card design, which colours, and the wording of the Details switch for the dense view.
- Whether the per-step delta labels ("−2.5 d on path") should hide small values.
- Variants have different horizons (Norway 161 vs 93 days); consider how the shared clock and the "end" of playback behave.
Be careful with: the click-a-dot trace, keyboard keys (Space, arrows, r), and every existing URL parameter
(`?s= ?compare ?left= ?right= ?view= ?layer= ?paused ?day= ?large`). `demo/start.js` builds Norway links with
`?s=norway&compare&left=…&right=…` and a test checks them, so they must keep opening the right pair.

## Context (read this even if you know the project)

This is a Junction 2026 hackathon repository (AstraZeneca challenge "Equal Care Across Finland"). It is a simulator
of the lung-cancer care pathway with synthetic patients, an optimiser that reorders steps, a check against a published
Norwegian hospital study (Stokstad et al. 2019), and a decision model called JEV. Submission is Sunday 15 Nov 10:00
Helsinki; **code freeze 04:00 UTC**. A UI revamp is running in parallel lanes. **All other work in the repository is
paused**, and you are one of the lanes. Tuomas (team lead) wants: info pages that can be understood from the top of
the page (one sentence and one picture), details at the bottom; a simulator with very few things visible by default; a
quiet "80s paper" look (warm off-white, near-black ink, Inter and Courier Prime, mustard and brick used rarely).

Plan documents, all in `docs/plan/ui-revamp/`: `README.md` (summary), `01-principles.md`, `02-audit.md` (what is on
screen today; screenshots in `current/`), `03-information-architecture.md` (the five pages), `04-sim-view.md`,
`05-theme.md` (palette, type), `07-parallel-lanes.md` (lanes, **the shared contract**, merge rules),
`08-pause-and-handoff.md` (handoff template). Reference frames from the pitch video: `reference/*.png`; look at them.

## Decided by Tuomas (D60, D61 in `docs/decisions.md`; not open for this lane)

The offline `demo/` site is what judges see and the main submission page. It has five pages (Overview, Simulator,
Patients, Evidence, Decision model). Before/after in the simulator is a flip on one layout (side by side optional). The
paper tint is `#F4F0E4`. Queue colour is driven by pile size. Default speed is 2 days/s. The site uses the video's
three-card look, not its words (no "clinician-validated" stamp). Offline Optimise is labelled a saved run. The white-paper
page comes after the submission. The React app is not restyled for Sunday.

## Rules that hold for every lane (firm)

- **Honesty.** Every patient is synthetic and nothing has been clinically reviewed. Numbers on pages are **read from the
  data bundles at load time, never typed** into HTML or JS. The numbers sheet `docs/pitch/filled/numbers_sheet.md` gives
  the sentence each number may be used in; keep the qualifiers (ranges, "best fit", "predicted, not fitted",
  "simulated", "assumed"). Caveats may move below the DETAILS rule; they are not deleted. Never show
  "CLINICIAN-VALIDATED" or anything implying clinical approval.
- **Offline.** Every page opens from `file://` with no network: no CDN, no web fonts from the internet.
- **Ownership.** Edit only the files listed under "You own". If you need a change elsewhere (theme tokens, `site.js`,
  the test helper, a bundle, an exporter, another page, the docs), post a QUESTION on the channel to the integrator and
  continue with what you can do. Do not edit it yourself.
- **Data is frozen.** Do not run exporters or regenerate bundles (`demo/data/*`). (Lane L4 has one stated exception.)
- **Existing tests pass unchanged.** Do not relax an assertion; ask instead.
- **Shared contract.** Use the tokens and shared classes from `demo/theme.css`, the nav and token helpers from
  `demo/site.js`, and the page skeleton `demo/_skeleton.html` (all described in `07-parallel-lanes.md`, "The shared
  contract"). Page-specific classes go in your own CSS with your prefix. Do not edit the contract files.

## Setup

```bash
cd /home/claude/cancer   # any checkout; the integration branch is ui/main
git fetch -q || true
git worktree add /home/claude/wt/ui-l1 -b ui/l1-sim ui/main
cd /home/claude/wt/ui-l1
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l1 --type CLAIM "ui/l1-sim: simulator: demo/flow.html, flow.js, flow.css, tests/test_demo_flow_page.py"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_flow_page.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l1 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `flow.html`, `?s=finland`, `?s=finland&compare`, `?s=norway&compare`, `?s=norway&compare&left=authors&right=suggested`, `?s=norway&compare&left=observed&right=faster_pet`, `?paused&day=60`, `?layer=time`, `?view=both` at 1920, `?theme=night`; plus a few seconds of playback (screenshots at two different virtual times) so queue colours are visible.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.
5. Your new test should at least check: the page links `theme.css` and `site.js`; no digits in the static HTML text;
   every `left`/`right` key used anywhere in `demo/start.js` exists in the flow bundle (the existing start test does
   part of this); and, if you can do it cheaply, a puppeteer smoke check that the page renders with no console errors.
6. The three headline numbers at day "end" equal `flow.metrics` of the shown variant (check by reading the bundle in a test or by hand, and say which).

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L1-simulator.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l1-sim` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l1 --type RELEASE "ui/l1-sim ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L1-simulator.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

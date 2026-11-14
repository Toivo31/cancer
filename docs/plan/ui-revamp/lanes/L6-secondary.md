# Lane L6: Secondary pages: encounter loop and dashboard

A self-contained brief for one coding agent. Branch `ui/l6-secondary`, worktree `/home/claude/wt/ui-l6`.

## Goal

Bring `demo/encounter.html` (primary-care loop) and `demo/index.html` (the old dashboard, now the "full results
report") into the new look so that every page linked from the site matches. On the encounter page: theme, the site
nav, slower speed options like the simulator (0.5/1/2/4/8 days/s, default 2), and a lighter default view (the plan
suggests moving the counter row and the results tables below the graph into a Details area). On the dashboard: CSS
only.

## You own (create or edit only these)

`demo/encounter.html`, `demo/encounter.js`, `demo/encounter.css`, the CSS (`<style>`) of `demo/index.html`, your handoff file.

## You must not touch

The `<script id="bundle" type="application/json">` block in `demo/index.html`: `tests/test_demo_fixture.py` compares it
byte-for-byte in effect with `data/demo_bundle.json`, and `demo/embed_bundle.py` rewrites it. Do not reformat it or
move it. Also off limits: bundles and exporters, other pages, `theme.css`, `site.js`, existing tests.

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

The encounter page's record panel (blue mechanical log, coral assessments) and the Reveal-truth teaching view are
its strongest parts. Consider how to keep the two record layers distinct with the quiet palette (for example ink vs
`--ink-3` italic, or Inter vs Courier Prime) instead of blue and coral, and how the truth view is marked (brick is
reserved for "wrong", so think about whether a revealed cancer ring should be brick). Keep `?p=`, `?paused`, `?day=`,
`?layer=time`, `?truth` and the keys (Space, arrows, r, t). `demo/jev.js` and `demo/start.js` link to
`encounter.html?p=<id>`. For `index.html`, the theme can probably be applied by linking `theme.css` after the inline
`<style>` (the aliases do most of the work); the dashboard draws charts with fixed colours in its script, so look at what
still clashes. **Decided (D66, Tuomas): screen 5, "Before and after: what the suggested change does to the pathway" (the stacked before and after pathway drawings, `screen3()` / `flowSvg`), is good as it is. Do not change its layout, wording or content; re-theme it only.** That includes the colours `flowSvg` and the other drawing helpers set in the script: replace those colour literals with the theme's values (or CSS variables) so the page matches the other pages, keeping the drawing logic and every output identical. Do not touch the `<script id="bundle">` block. Check with a screenshot of screen 5 for both scenarios before and after; the geometry and text must be unchanged. The other dashboard screens get the same colour treatment where it is a small change; anything larger is an open issue.

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
git worktree add /home/claude/wt/ui-l6 -b ui/l6-secondary ui/main
cd /home/claude/wt/ui-l6
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l6 --type CLAIM "ui/l6-secondary: secondary pages: demo/encounter.html/.js/.css, <style> of demo/index.html"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l6 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `encounter.html`, `encounter.html?paused&day=120`, `encounter.html?truth&paused&day=120`, `index.html`, `index.html#stokstad/5`, `index.html#finland_lung/3`.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L6-secondary.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l6-secondary` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l6 --type RELEASE "ui/l6-secondary ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L6-secondary.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

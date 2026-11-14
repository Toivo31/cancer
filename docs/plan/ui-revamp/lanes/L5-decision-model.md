# Lane L5: Decision model (demo/jev.html)

A self-contained brief for one coding agent. Branch `ui/l5-model`, worktree `/home/claude/wt/ui-l5`.

## Goal

Re-theme `demo/jev.html` and restructure it to the page template. The page was merged from `w8/jev-demo` this
evening (screenshot `current/09_jev.jpg`). Today the model card with the architecture diagram opens the page. The
plan wants the message and one picture on top instead: record in → the decision → allowed answers with scores → a person
accepts or overrides, with a stamp saying where the answer came from (recorded, live, fixture, mock). The example cards
follow, and the model card (architecture, training data, evaluation, limits, Hugging Face placeholder) moves below
DETAILS.

## You own (create or edit only these)

`demo/jev.html`, `demo/jev.js`, `demo/jev.css`, your handoff file.

## You must not touch

`demo/export_jev.py`, `demo/serve_jev.py`, `demo/data/jev_bundle.js`, `demo/data/jev_recorded.json`, `jev/`,
`decision_api/`, other pages, `theme.css`, `site.js`, existing tests.

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

Firm, from `tests/test_demo_jev.py`: links and assets exist; no digit in page text; `jev.js` numerals stay within
the test's whitelist; exactly one `var HF_URL = ` line; recorded outputs remain the model's own; `serve_jev.py` still
serves the page. Keep the provenance labels on every output ("Recorded · deployed model", "Live call", "scripted fixture,
not the model", "mock, not the model") and the rule that live calls start only on a button press. Keep the URL options
(`?api=hosted|same|<url>`, hashes `#gp_visit #reasoning #triage #screening #compare #own`) and the `encounter.html?p=`
links. Judgement is yours on the top picture (consider a simplified version of the existing diagram, or one worked
example as the picture), on which example card opens by default, and on how much of the model card stays visible. Scores
are relative candidate scores, not probabilities. The page has to keep saying so. **Decided (D63):** the page's wording about
how the model works stays as built; training data stays "not documented" and the Hugging Face link stays a placeholder.
Restructure and restyle, but do not rewrite those statements.

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
git worktree add /home/claude/wt/ui-l5 -b ui/l5-model ui/main
cd /home/claude/wt/ui-l5
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l5 --type CLAIM "ui/l5-model: decision model page: demo/jev.html, jev.js, jev.css"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_jev.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l5 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `jev.html`, `jev.html#gp_visit`, `jev.html#reasoning`, full-page 1440×2400.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L5-decision-model.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l5-model` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l5 --type RELEASE "ui/l5-model ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L5-decision-model.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

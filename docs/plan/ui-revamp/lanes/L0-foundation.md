# Lane L0: Foundation: the shared contract

A self-contained brief for one coding agent. Branch `ui/l0-foundation`, worktree `/home/claude/wt/ui-l0`.

## Goal

Build the shared contract that every other UI lane builds on, in two parts, and keep it small and boring.
**Part A** (merge first, target 30 minutes): `demo/theme.css` with the tokens, old-name aliases, the `night` alias block,
base typography and the shared classes; `demo/fonts/` with vendored fonts. **Part B** (target 45 more minutes):
`demo/site.js`, `demo/_skeleton.html`, the two stub pages, the test helper and site test, the screenshot script and the
handoff folder README. The exact names are fixed in `07-parallel-lanes.md`, "The shared contract". Implement those names
exactly, because six lanes are coding against them.

## You own (create or edit only these)

`demo/theme.css`, `demo/fonts/**` (with `OFL.txt`), `demo/site.js`, `demo/_skeleton.html`, `demo/patients.html` and
`demo/evidence.html` (**stubs only**: after your merge they belong to L3 and L4), `tests/demo_pages.py`,
`tests/test_demo_site.py`, `scripts/ui_shots.sh` (and a small node script beside it if you need puppeteer for console
capture), `docs/plan/ui-revamp/handoff/README.md`, `docs/plan/ui-revamp/handoff/L0-foundation.md`.

## You must not touch

Every existing page (`demo/start.*`, `flow.*`, `encounter.*`, `jev.*`, `index.html`), all bundles and exporters,
`web/`, every existing test, all docs outside `docs/plan/ui-revamp/handoff/`. Do not link `theme.css` from existing pages;
the page lanes do that.

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

Things to think about, where judgement is yours:
- Fonts: try to fetch Inter (400/600/700 or the variable file) and Courier Prime (400/700) as `woff2` from their official
  open-source releases through the proxy (see `~/.ccr/README.md` if a download fails). Look at size: about 0.4 MB is
  fine. If it does not work quickly, ship without fonts and say so; the fallback stacks in `05-theme.md` keep the look.
- `theme.css`: consider how the old-name aliases interact with pages that define their own `:root` (aliases only win if
  `theme.css` loads after the page's CSS; rewritten pages load it first and drop their `:root`). Document both cases in
  a comment at the top.
- `site.js`: keep it dependency-free and tolerant (a page without a nav element should not throw). Think about
  `Site.tokens()` returning resolved hex values for canvas code, and whether it should cache.
- `ui_shots.sh`: consider a default URL list covering every page and the simulator variants
  (`flow.html`, `?s=finland`, `?s=finland&compare`, `?s=norway&compare`, `?s=norway&compare&left=authors&right=suggested_faster_pet`,
  `?paused&day=60`, `?layer=time`, `?theme=night`), plus an option to pass a list. Console-error capture needs puppeteer;
  `puppeteer-core` exists in `web/node_modules` when it is installed, and `/usr/bin/google-chrome` is present. Exit
  non-zero on console errors.
- `tests/demo_pages.py`: generalise the parser in `tests/test_demo_start.py` (text outside `<code>`/`.cmd`, links,
  assets). Keep the checks listed in the contract; the site test should only check pages that link `site.js`, so old pages do not fail before their lane reaches them.
- Specimen: a throwaway HTML (not committed, or committed as `demo/_specimen.html` if useful to others) showing every
  token, both faces, a card, an inset, a stamp, buttons. Look at it next to `reference/05_three_cards.png`.

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
git worktree add /home/claude/wt/ui-l0 -b ui/l0-foundation ui/main
cd /home/claude/wt/ui-l0
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l0 --type CLAIM "ui/l0-foundation: foundation: demo/theme.css, demo/fonts, demo/site.js, demo/_skeleton.html, stubs patients.html/evidence.html, tests/demo_pages.py, tests/test_demo_site.py, scripts/ui_shots.sh, handoff/README.md"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_site.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l0 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `_skeleton.html`, `patients.html`, `evidence.html`, and your specimen page.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.
5. Post "contract part A ready at <sha>" as soon as A is committed, so the integrator can merge it and freeze it,
   before you start B. After A is merged, changing a name in it needs the integrator's OK.

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L0-foundation.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l0-foundation` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l0 --type RELEASE "ui/l0-foundation ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L0-foundation.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

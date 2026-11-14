# Lane L3: How the patients work (demo/patients.html)

A self-contained brief for one coding agent. Branch `ui/l3-patients`, worktree `/home/claude/wt/ui-l3`.

## Goal

Build the page that explains the synthetic patient cards and why the optimisation is realistic and not overfitting
(`03-information-architecture.md`, page 3). Top: one sentence and one picture. A patient as a sealed hidden truth
(condition, every test's pre-drawn result) next to the visible record that fills as steps reveal it. Then the loop:
run on training patients with the truth hidden → read the records (which step held patients back, which tests were not
needed in hindsight) → propose a change → rerun the same patients and keep it only if faster and no more cancers are
missed → test on new patients, truth hidden again, which is the number reported. Below DETAILS: the catalogue, the
template-written and model-written cards (the synthetic-patients card moves here from the Overview), audits, limits.

## You own (create or edit only these)

`demo/patients.html` (replace the L0 stub), `demo/patients.js`, `demo/patients.css`, `tests/test_demo_patients.py`, your handoff file.

## You must not touch

`demo/start.*` (L2 removes the card there; you render it here by **copying** the rendering code from
`demo/start.js` at the base commit), `demo/encounter.*` (you may link to it, e.g. `encounter.html?p=<id>&truth`),
bundles and exporters, `theme.css`, `site.js`, existing tests, docs.

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

Two precision points the page has to carry, because they make the method credible: (1) rerunning the *same*
patients is something only a simulator can do; in real life that step is a pilot (`docs/master_plan.md`, section 6);
(2) judging a test in hindsight is biased: a test run only on patients who failed earlier tests looks better than it
is (master plan, section 4 and open question 8). Sources for content: `docs/synthetic_data_for_jev.md`,
`catalogue/README.md`, `libraries/README.md`, `docs/master_plan.md` sections 5 to 6, `demo/README.md` (encounter
page). Data you can read: `data/cards_bundle.js` (counts, one example card), `data/encounter_bundle.js` (patients
with `lines` and a `truth` split, example patients), `data/demo_bundle.json` (optimiser details, for example
`selection_optimism_pp`, held-out cohorts). Judgement is yours on the reveal interaction (a toggle on one example
patient is the plan's lean; the encounter page's record view is a good model) and on how to draw the loop with almost
no colour. If a number you want is not in any bundle, leave it out and note it; do not compute results in the page.

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
git worktree add /home/claude/wt/ui-l3 -b ui/l3-patients ui/main
cd /home/claude/wt/ui-l3
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l3 --type CLAIM "ui/l3-patients: patients page: demo/patients.html/.js/.css (from the L0 stub), tests/test_demo_patients.py"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_patients.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l3 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `patients.html` (default and with the reveal on), full-page 1440×2400.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.
5. Your test uses `tests/demo_pages.py` (links exist, no digits in text, offline, theme and site linked) and checks that
   the hidden side is not shown until the reader asks (for example, the truth container is empty or hidden in the static HTML).
6. Ask Tuomas or the integrator to read the text before RELEASE. If nobody has read it by 03:00 UTC, say so in the RELEASE note.

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L3-patients.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l3-patients` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l3 --type RELEASE "ui/l3-patients ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L3-patients.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

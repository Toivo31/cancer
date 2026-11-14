# Lane L4: Does it hold up? (demo/evidence.html)

A self-contained brief for one coding agent. Branch `ui/l4-evidence`, worktree `/home/claude/wt/ui-l4`.

## Goal

Build the Evidence page (`03-information-architecture.md`, page 4). Top: the message that the model, fitted only to
the Norwegian hospital's observed pathway, ranks the authors' redesign above a faster scanner, and both above today, in every
fitting setting, so trust the ranking, not the exact size. Then one dot-and-range chart: per pathway, the published value
(hollow ring), the model at best fit (dot), and the range over the fitting settings (thin bar), plus the optimiser rows.
The faster-scanner over-prediction stays visible. Below DETAILS: the robustness tests as small multiples, each with
a finding as its heading, then data and limits, and a link to the full results report (`index.html`) and
`docs/validation.md`. The case-study paper is **not** in tonight's scope.

## You own (create or edit only these)

`demo/evidence.html` (replace the L0 stub), `demo/evidence.js`, `demo/evidence.css`, `tests/test_demo_evidence.py`,
**additive** new fields in `demo/export_start.py` and the regenerated `demo/data/start_bundle.js` (it takes under a
second; you are the only lane allowed to regenerate it), your handoff file.

## You must not touch

Existing fields and logic in `export_start.py` (add, do not change), every other exporter and bundle,
`docs/review_checks/*` and `docs/validation.md` (read only), other pages, `theme.css`, `site.js`, existing tests
(`tests/test_demo_start.py` reads `start_bundle.js` and must still pass).

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`, `?theme=night`), `demo/_skeleton.html` (page template: nav, top with title, one-sentence lede, figure, caption, one primary button; `.details`; footer strip), `tests/demo_pages.py` (shared checks). Exact names: `07-parallel-lanes.md`, section "The shared contract". Page ids: overview, simulator, patients, evidence, model. Page-specific classes use your own prefix in your own CSS.

## Design guidance (open: your judgement, Tuomas decides)

Sources: `docs/validation.md` (sections "Robustness" 1–6 and "Optimiser robustness, ablation and structure check"
1–4), `docs/review_checks/norway_*.json`, `docs/pitch/filled/numbers_sheet.md` (the allowed sentence for each number;
the README's "What we do not claim" list). `start_bundle.js` already holds `validation`, `norway_robustness` and the
optimiser bands; look at what is there before adding anything. Judgement is yours on chart form (the plan leans to
a dot-and-range chart without gridlines, ink for the model, a brown ring for published values, grey for today) and on how
many robustness tests earn a small multiple. If a test has no single honest number, a one-sentence finding is enough.
**Framing is decided (D62):** lead with the plausibility framing of `docs/norway_case_study.md` (a paper-style write-up that now
exists): from the hospital's structure at the 40% starting point the optimiser found the authors' three changes; always
give ranges; never "beats the authors"; the stricter structure reading (79%) is a sensitivity result, not the headline.
Read that document first; it is also what the page's "Read the case study" link points to (the markdown file tonight; a
printable page comes after the submission). Wording traps to avoid: "matches", "predicted exactly", the superseded
"78 to 86%" band, "beats the authors". Also read "What we do not claim" in `README.md`.

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
git worktree add /home/claude/wt/ui-l4 -b ui/l4-evidence ui/main
cd /home/claude/wt/ui-l4
python scripts/comms.py open          # read the channel first
python scripts/comms.py post --as claude-code@tuomas/ui-l4 --type CLAIM "ui/l4-evidence: evidence page: demo/evidence.html/.js/.css (from the L0 stub), tests/test_demo_evidence.py, additive fields in demo/export_start.py + regenerated demo/data/start_bundle.js"
```
If `ui/main` does not yet contain the contract (`demo/theme.css`, and for most lanes `demo/site.js`), wait for the
integrator's "contract frozen" post, or start with the parts that do not need it and merge `ui/main` in when it lands.

## Checks before you report done (firm)

1. Your own tests and the demo tests: `python -m pytest -q tests/test_demo_evidence.py tests/test_review_w7_demo_numbers.py tests/test_demo_site.py tests/test_demo_start.py tests/test_demo_jev.py tests/test_demo_encounter.py tests/test_demo_fixture.py tests/test_demo_cards.py -p no:cacheprovider`
   (all must pass; the shared machine has 2 cores, so do not run the full gate; the integrator does).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l4 <your url list>` at 1440×900 and 1920×1080 with
   **no console errors**; look at every screenshot yourself. Your URL list: `evidence.html`, full-page 1440×2400.
   Fallback without the script: `google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 --virtual-time-budget=4000 --screenshot=<out>.png "file://$PWD/demo/<page>"`.
3. Offline: open your pages with networking off (`--host-resolver-rules="MAP * ~NOTFOUND"` on the Chrome command line)
   and check they look the same.
4. Skim test: someone who has never seen the page reads only the part above DETAILS (or, for the simulator, the default
   view) and can say the page's message in one sentence. Write down how you checked this.
5. Your test checks the new bundle fields equal the values in their `docs/review_checks/*.json` sources (the way
   `test_start_bundle_norway_ranges_match_the_review_files` in `tests/test_demo_start.py` does), plus the shared page checks.
6. Run `python demo/export_start.py` twice and confirm the output is identical (deterministic) before committing the bundle.

## Report back

- Fill in `docs/plan/ui-revamp/handoff/L4-evidence.md` using the template in `08-pause-and-handoff.md`, section 4. Be
  specific under "Removed", "Renamed or moved" and "Do not recreate". Later agents use it to avoid rebuilding what you removed.
- Commit on `ui/l4-evidence` (end the message with the attribution lines your session gives you), then post:
  `python scripts/comms.py post --as claude-code@tuomas/ui-l4 --type RELEASE "ui/l4-evidence ready at <sha>: <one line>. Handoff: docs/plan/ui-revamp/handoff/L4-evidence.md. Shots: <dir>."`
- In your final message: what changed, the screenshot paths, test results, judgement calls Tuomas should look at,
  and anything you could not finish.

## When blocked

- Post `--type QUESTION` (or `PROBLEM`) naming the file and the decision you need, then carry on with the next part
  of your scope. Do not wait idle, and do not edit outside your files.
- If an existing test seems to forbid something the plan asks for, keep the test passing and record the conflict in
  your handoff's "Open issues".
- If you are not merged by 03:15 UTC, your branch stays as it is. Make sure what is committed is in a working state
  at every commit (small commits, each one demoable).

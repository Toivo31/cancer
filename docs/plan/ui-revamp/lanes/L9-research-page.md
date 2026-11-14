# Lane L9: Research behind the numbers (demo/research.html)

A self-contained brief for one coding agent. Branch `ui/l9-research`, worktree `/home/claude/wt/ui-l9`.
Small lane: 1 to 1.5 h. Depends on L0 part A only (tokens and shared classes); `site.js` from L0-B is used if it is
there. **Cut candidate**: if the night runs late, it is cut after L4's small multiples (see `07-parallel-lanes.md`).

## Goal

Tuomas (14 Nov, D69): "It is fine for a claim to be shown if it is research evidence based. Put this and other research
claims on a research literature page." Every reader should be able to tell, for each claim on our pages, whether it
comes from **published research**, from **our simulation**, or from **our own assumption**. The trigger was the
dashboard headline "90% of the time to treatment is spent waiting": a simulation result whose per-step waits are inputs,
partly set from published figures and partly assumed.

Build `demo/research.html`, `demo/research.js`, `demo/research.css` from `demo/data/research_bundle.js`
(`window.RESEARCH_DATA`). Title: **Research behind the numbers**. Page message in one sentence: *the research tells us
where time is lost; our simulation tests changes on top of it; here is which is which.*

1. **Top infographic (above DETAILS).** One picture showing the three kinds of basis with their counts from
   `RESEARCH_DATA.counts` (published / simulation / assumption), labels from `basis_labels`. Your judgement on form
   (three stacked blocks, a single proportional bar, three cards in the video's look). Below it, the waiting-basis
   split as the worked example: for Finland, the share of waiting days set from published figures versus assumed
   (`waiting_split.values.fi_matched_pct`, `fi_assumed_pct`; finer split in `waiting_split.finland.by_basis_share`:
   published / tuned to a published figure / assumption), and the same for Norway (`no_matched_pct`). Caption: these
   are our inputs, not evidence. Then the **framing sentence** (`RESEARCH_DATA.framing`), verbatim.
2. **Claims as expandable rows** (below the infographic or below DETAILS, your call), grouped by `themes` in the
   bundle's order. Each row: the claim text, a **basis chip** (`.chip` plus your `.rs-chip--published` /
   `--simulation` / `--assumption` modifier; never colour alone, the chip carries the word), and when expanded:
   published → source id, citation, year, figure, kind of source, how we read it (`access`: full text / abstract /
   secondary), link (`url`); simulation → `run`, `inputs`; assumption → `where`, `reason`; for all: `strength`
   and `shown_on`. Each row's element id is the claim id (`id="<claim id>"`) so `research.html#<claim id>` opens and
   expands that row (read `location.hash` on load and on `hashchange`).
3. **Waiting split table** (below DETAILS): `waiting_split.finland.owners` and `.norway.owners` (input, basis, source,
   days, share, why).
4. **What we could not support** (`RESEARCH_DATA.unsupported`): visible, not hidden in a fold; this is where the
   delay-and-survival caveat and the lung-specific 65 to 69 day conflict live.
5. **Sources table** (below DETAILS): every entry of `RESEARCH_DATA.sources`: citation, year, how we read it
   (full text / abstract / secondary), link; mark the ones used in the register (`used_in_register`).

**Links in.** From the Evidence page (L4 owns it: ask the integrator to add one link "Research behind the numbers",
or L4 adds it if it is still open), and from claim chips elsewhere: a "where does this come from" link of the form
`research.html#<claim id>`. Claim ids are stable slugs (`docs/research_claims.yaml` never renames one); the list is
in the bundle. Adding those links on other pages belongs to the lanes that own those pages, after the merge, through
the integrator. This lane only makes the targets work.

**Navigation.** The nav stays five pages (D60). Research is reached from Evidence and from claim links, not from the
nav. Reason: it is a reference page that supports every other page, not a step of the demo story, and a sixth entry
would crowd the nav that L0 has frozen. If Tuomas wants it in the nav later, that is an additive `site.js` change
through the integrator (page id `research`).

## You own (create or edit only these)

`demo/research.html`, `demo/research.js`, `demo/research.css`, `tests/test_demo_research_page.py`, your handoff file
`docs/plan/ui-revamp/handoff/L9-research.md`.

## You must not touch

`demo/data/research_bundle.js` and `demo/export_research.py` (data frozen; regenerated only by the integrator),
`docs/research_claims.yaml` / `.md` (the register; wording changes go there, through the integrator),
`tests/test_demo_research.py` (the data test), every other page, exporter and bundle, `theme.css`, `site.js`.

## The shared contract you build on

`demo/theme.css` (tokens and shared classes), `demo/site.js` (`Site.nav(pageId)`, `Site.tokens()`, `Site.footer()`,
`?theme=night`), `demo/_skeleton.html` (page template), `tests/demo_pages.py` (shared checks). Exact names:
`07-parallel-lanes.md`, "The shared contract". There is no `research` page id in the nav: call `Site.nav("evidence")`
so the nav marks Evidence as the current section (or `Site.nav()` with no id if L0's helper allows it; check).
Page-specific classes use the prefix `.rs-`.

## Design guidance (open: your judgement, Tuomas decides)

Read `docs/research_claims.md` first: it is the same content as the bundle, rendered as text. The basis chips should be
readable in greyscale and on the projector: the word on the chip carries the meaning; colour (for example ink for
published, mustard for simulation, brick-tint for assumption) only helps. Keep the top short: the infographic, the
worked waiting example and the framing sentence. Wording traps: do not call a simulation result "evidence"; do not
call the 80% "observed" (it is the authors' model estimate); do not write "Finland" where the bundle says "synthetic
county"; do not drop the strength line when a row is expanded (it carries the conflicts).

## Context (read this even if you know the project)

Junction 2026 hackathon repository (AstraZeneca challenge "Equal Care Across Finland"): a simulator of the lung-cancer
pathway with synthetic patients, an optimiser that reorders steps, a check against a published Norwegian hospital study
(Stokstad et al. 2019), and a decision model (JEV). Submission Sunday 15 Nov 10:00 Helsinki; **code freeze 04:00 UTC**.
The UI revamp runs in parallel lanes; plan documents in `docs/plan/ui-revamp/` (`README.md`, `01-principles.md`,
`03-information-architecture.md`, `05-theme.md`, `07-parallel-lanes.md`, `08-pause-and-handoff.md`).

## Decided by Tuomas (not open for this lane)

D60/D61 (five-page nav, paper look, offline site), D69 (this page: every claim is labelled published / simulation /
assumption with a link to it), and the framing sentence's meaning: the research establishes where time is lost and
which ideas have been proposed; our tool adds that such changes can be simulated from a Finnish or the Norwegian
hospital and searched for and tested on the graph; the size of any gain is an estimate resting on the inputs.

## Rules that hold for every lane (firm)

- **Honesty.** Every patient is synthetic. Numbers come from the bundle at load time, **never typed** into HTML or JS
  (the page text has no digits outside `<code>`/`.cmd`). Keep every qualifier the register carries. Never show
  "CLINICIAN-VALIDATED". No source may be described as read in full unless its `access` is `full_text`.
- **Offline.** Opens from `file://`; external source links are ordinary `<a href>` that open in a new tab; no CDN.
- **Ownership.** Only your files. Need something else: post a QUESTION to the integrator and continue.
- **Data is frozen.** Do not run exporters.
- **Existing tests pass unchanged**, including `tests/test_demo_research.py`.

## Setup

```bash
cd /home/claude/cancer
git worktree add /home/claude/wt/ui-l9 -b ui/l9-research ui/main
cd /home/claude/wt/ui-l9
python scripts/comms.py open
python scripts/comms.py post --as claude-code@tuomas/ui-l9 --type CLAIM "ui/l9-research: research page demo/research.html/.js/.css, tests/test_demo_research_page.py"
```
If `ui/main` does not yet have `research_bundle.js` (branch `w8/research-page`), ask the integrator to merge it first.

## Checks before you report done (firm)

1. `python -m pytest -q tests/test_demo_research_page.py tests/test_demo_research.py tests/test_demo_site.py -p no:cacheprovider`.
   Your test, at least: shared page checks from `tests/demo_pages.py`; no digit in page text; `research.js` reads
   `window.RESEARCH_DATA` and does not contain the claim texts (no copy of the register in JS); every claim id in the
   bundle is a valid HTML id and appears as a row id when the page is rendered (check the JS builds rows with
   `id = claim.id`, for example by asserting the code path, or with a headless render if you have one).
2. Headless-Chrome pass: `scripts/ui_shots.sh /tmp/ui_shots/ui-l9 <url list>` with `research.html`,
   `research.html#in-fi-waits-half-published` and `research.html#fi-diagnosis-to-treatment-37d` at 1440×900, full page
   1440×2400; **no console errors**; look at every screenshot.
3. Offline check (`--host-resolver-rules="MAP * ~NOTFOUND"`).
4. Skim test: someone who reads only the top can say "some numbers are from research, some from the simulation, some
   are assumptions, and here is how many of each". Write down how you checked.

## Report back

Fill `docs/plan/ui-revamp/handoff/L9-research.md` (template in `08-pause-and-handoff.md`, section 4), commit on
`ui/l9-research`, post RELEASE with the sha, and in your final message list judgement calls for Tuomas (infographic
form, whether rows start collapsed, chip colours) and what links other pages still need.

## When blocked

Post QUESTION or PROBLEM naming the file and the decision; carry on with the rest of the scope. If not merged by
03:15 UTC the branch stays as it is; keep every commit working.

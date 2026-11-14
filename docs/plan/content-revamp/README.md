# Content revamp (start here for what our pages and pitch may say)

**In one line:** every claim on our pages says where it comes from (published research, our simulation, or our
assumption); the Norway story is about reordering the pathway, not equipment; and wording can be changed in one place
per page without touching data or layout.

Status: plan, written Sat 14 Nov ~23:55 UTC from Tuomas's content notes during the evening. It runs beside the UI
revamp (`docs/plan/ui-revamp/`, which is about look and layout); this plan is about **what the pages say**.
Decisions it rests on: D62 (Norway framing), D66 (Before and after page kept), D68 (no optimiser-with-scanner result),
D69 (research page, claim labels); D68 and D69 are being written by the lanes named below.

## 1. Principles (each one a rule an agent can check a page against)

1. **Every claim has a basis, shown where the claim is.** Three kinds, always named the same way:
   *Published* (a source in `params/sources.yaml`, with how we read it: full text, abstract, secondary),
   *Our simulation* (computed from simulated patients; says which inputs drive it), *Our assumption* (our choice, with
   the reason). A claim that is a simulation output but really restates an input is labelled as such: the "90% of the
   time is waiting" line is computed from our model, and the waits are inputs set from published figures (about half
   of the waiting days) or assumed (about half), so it is a consequence of the inputs, not a measurement.
2. **Research establishes the problem; our tool shows what can be simulated.** The framing, in Tuomas's words: we can
   simulate these changes, starting from a Finnish or the Norwegian hospital, and investigate how they improve the
   graph. The size of a gain is an estimate that rests on the inputs.
3. **Norway: only the graph optimisation.** The optimiser's result with no new equipment (about 67% at the best fit,
   48 to 77% across settings) is the one we report. We do not report an optimiser run with the faster scanner (the
   authors did not either). We keep the authors' published figures (40%, 48% scanner alone, 80% reordered) and our
   simulation of the scanner alone and of their pathway, framed as a plausibility check (D62), never "beats the authors".
4. **Ranges, never single points,** for anything that depends on fitted or assumed inputs.
5. **No number is typed in a page.** Numbers come from bundles; wording lives in one text block per page.
6. **Not repetitive.** Each fact has one home page; other pages give one line and a link ("where does this come from"
   links to the research page, `research.html#<claim-id>`).
7. **Synthetic stays visible.** Data is synthetic; the Finnish county is synthetic; "clinician-validated" is never said.

## 2. What is decided so far (Tuomas, 14 Nov)

| Topic | Decision | Where it lands |
|---|---|---|
| Faster-scanner optimiser result | Removed from every page, bundle and pitch file; headline becomes the no-equipment result | agent branch `w8/no-scanner-claims` (D68) |
| Step cards "what the records said, what the rerun confirmed" (Norway) | Must come from the no-equipment run, not the 58 to 88% chain | same branch |
| "Capacity or order" screen | Kept: it shows untargeted capacity vs efficient flow. Norway loses its fourth bar; every bar says where it comes from; no repeat of screens 1, 3, 5 | same branch |
| "Before and after" screen | Kept as built, re-themed only (D66) | UI lane L6 |
| "Where time is lost" and the 90% line | Reworded as "in our model"; provenance strip: simulation / published / assumption, with the computed split | same branch |
| Research literature page | New page `research.html`: claims register (published / simulation / assumption), sources table, framing sentence; linked from Evidence and from claim chips | agent branch `w8/research-page`; UI lane L9 builds the page |
| Norway case study | Plausibility framing, scanner combination dropped, authors' method described, "overstates" removed (2,133 words) | `docs/norway_case_study.md` (merged) |
| Simulator graph | Less on screen by default (D67); this is UI, listed for completeness | UI lane L1 |

## 3. Page by page: what each page says

| Page | One message | Content rules |
|---|---|---|
| Overview (`start.html`) | Waiting, not tests, sets the time to treatment, and our tool lets you simulate changes and search for better order | Headline numbers carry a basis chip; Norway line is the plausibility check; the synthetic-patients card moves to Patients |
| Simulator (`flow.html`) | You can watch the pathway, press Optimise, and see the graph change | Three numbers; Norway shows the no-equipment optimiser (saved run, held-out patients, labelled); authors' pathway shown only as a published reference marker, not a like-for-like bar (their 80% includes the faster scanner) |
| Patients | What a synthetic patient is and how the decider sees them | Counts from the cards bundle; model-written cards counted from manifests; no typed counts |
| Evidence | What we checked and how far to trust it | Norway case study top; robustness charts; the waiting-basis split; link to Research |
| Decision model | What the JEV model does with the patients | Wording kept (D63); model card below Details |
| Research (new) | Where each claim comes from | Register from `docs/research_claims.yaml`; weak spots listed ("what we could not support") |
| Dashboard (`index.html`) | Full results for those who want everything | Screens 1 to 6 keep their roles; every screen's numbers show a basis line; Norway headline is the no-equipment run |

The pitch (deck, video script, Q&A, submission text) follows the same rules; its numbers come from
`docs/pitch/numbers_sheet.md` through `fill_numbers.py`. The 320-word voiceover trim (W8-H1) and Eemeli's stale
61% and 80% figures (W8-H2) are content tasks in this plan.

## 4. Can content change on the fly? Yes, if we keep to this

Today wording is scattered: typed in `start.js`, `flow.js`, `index.html`, `jev.js`, the pitch templates, and the docs, with tests
that forbid typed digits on some pages. A wording change is easy only when it follows this contract, which the UI lanes
are asked to keep:

- Each page keeps its visible text in **one `TEXT` block at the top of its script** (strings with `{placeholders}`,
  no digits), and fills numbers from its bundle. Editing words means editing that block and running the page's test:
  no re-export, no layout work.
- Which number a page shows, or a new number, needs an exporter change and a re-export (about a minute for the
  site bundles, longer for the dashboard bundle). So content decisions that need new numbers are made first.
- Pitch text is edited in `docs/pitch/*.md` with `[[placeholders]]`, then `python docs/pitch/fill_numbers.py --strict`.
- Claims and their basis live in one file, `docs/research_claims.yaml`; the research page, the claim chips and the
  claims register are generated from it, so correcting a claim's basis is a one-file edit.

## 5. Sequence (before the 04:00 UTC freeze)

1. Content agents finish on their branches (scanner removal and provenance labels; research claims register and
   bundle). The architect merges and gates them **before** the UI pause, because bundles freeze at the pause.
2. UI lanes build the new pages from the frozen bundles; lane L9 builds the research page; lane briefs already carry
   the content rules above (D66, D67; add D68 and D69 when merged).
3. Content check at the 01:00 UTC screenshot look: read every page's text against the seven principles
   (a human read of Patients, Evidence and Research text before they enter the nav).
4. After the freeze (not before submission 10:00): wording polish through the `TEXT` blocks only, no data changes.

## 6. Success criteria

- No page, bundle or filled pitch file contains the optimiser-with-scanner result (a test guards it).
- Every number or causal claim visible on the five pages and the dashboard carries a basis chip or a link to
  its claim on the research page; the register lists each claim exactly once with one basis.
- The "time is waiting" headline says "in our model" and shows the computed published / assumed split.
- A reader can click from any claim to its source in two clicks.
- Changing a sentence on a page needs no data re-export (checked by changing one sentence in one `TEXT` block).
- Gate passes; pitch placeholders all filled; Norway wording matches `docs/norway_case_study.md`.

## 7. Open points for Tuomas

| # | Question | Lean |
|---|---|---|
| C1 | Is the scanner-alone result (our 60% against the authors' published 48%) kept on pages? | Yes, as the authors reported it, with the cohort-difference explanation |
| C2 | Does the Research page get a nav entry, or is it reached from Evidence and claim links only? | Evidence and claim links only; five pages stay |
| C3 | The all-cancers 37-day booking calibration conflicts with lung-specific Finnish figures (65 to 69 days, `docs/evidence_research.md`); show both on the research page | Yes, as a flagged weak spot |
| C4 | Voiceover and video files carry the old numbers | Eemeli and the pitch lane update from the filled numbers sheet |

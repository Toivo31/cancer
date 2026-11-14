# Information architecture: which pages exist and what each says

**In one line:** five pages. Overview, Simulator, How the patients work, Does it hold up, Decision model. One nav
bar, the same on every page. Each page opens with one sentence and one picture that are enough on their own.

```
 OVERVIEW ─────────────┬──────────────┬──────────────────┬─────────────────
 (start.html)          │              │                  │
   SIMULATOR        HOW THE PATIENTS   DOES IT HOLD UP    DECISION MODEL
   (flow.html)      WORK (new)         (new; Norway,      (jev.html, incoming)
     └ primary-care    └ links          robustness,         └ model card at
       loop            encounter.html   case-study paper)     the bottom
       (encounter.html)                  └ full report
                                           (index.html)
```

## Page template (all info pages)

```
┌ nav: EQUAL CARE PATHWAYS   Overview · Simulator · Patients · Evidence · Decision model   [SYNTHETIC PATIENTS] stamp
│
│ PAGE TITLE IN CAPS (Inter 700)
│ One sentence, at most ~25 words, that is the page's message.
│
│ ┌─────────── the infographic (one picture, numbers bound from bundles) ───────────┐
│ └──────────────────────────────────────────────────────────────────────────────────┘
│ One caption line: what is synthetic, what is predicted, where the number comes from.
│ [one primary button]   secondary link
│
│ ──────────────────────────────── DETAILS ────────────────────────────────
│ Short sections, each with a finding as its heading; ranges, methods, caveats, file links, commands.
└ footer strip: Synthetic patients only · not clinically reviewed · numbers read from <bundle> at <time>
```

Rule of thumb: everything above DETAILS fits in 900 px at 1440 width and holds at most ~80 words. Everything below
can be long. Nothing is deleted in the rewrite: text that leaves the top moves below DETAILS or to the doc it came from.

## Site maps considered

| Option | Pages | For | Against |
|---|---|---|---|
| **S1 tiny** | Overview, Simulator, Evidence (patients + Norway + model card as sections) | Least to build and keep in sync; tonight-proof | The patients page Tuomas asked for becomes a section; Evidence gets long; the JEV demo has no home |
| **S2 five (lean)** | Overview, Simulator, Patients, Evidence, Decision model | One message per page; maps to the three judging stories (actionability = Simulator, insight/data = Patients + Evidence, clarity = Overview); the JEV page is being built anyway | Two new pages to write (Patients, Evidence) |
| S3 seven | S2 + Primary-care loop + Data and honesty as pages | Every existing thing has a nav entry | More to read and maintain; honesty on its own page is honesty nobody reads; the loop is an assumed-behaviour model and should not look like a peer of the Norway check |
| S4 one scroll + Simulator | A single long story page with sections, and the Simulator | One URL to skim | Fights "details at the bottom": every section's details sit between the next section's top |

S2 with S1 as the fallback if time runs out: the Patients and Evidence content can start as sections on the Overview
and be split out later without changing the nav labels.

## The pages

### 1. Overview (`demo/start.html`, rewritten)

- **Message:** "Lung-cancer patients in Finland wait longest in the Nordics. We simulate the pathway, let an
  optimiser reorder it, and check the method against a real hospital."
- **Top infographic:** three outlined cards in the video's style (`reference/05_three_cards.png`), one number each, bound:
  1. **SIMULATE.** A mini pathway (5 dots on a line, as in the DEFINE card), with "x% of cancers treated within 90 days today
     (synthetic county)".
  2. **OPTIMISE.** Two bars, today vs after the change, from the Finland held-out result, with "two reorders, no new capacity".
  3. **CHECK AGAINST A REAL HOSPITAL.** Norway: published 40 / 80 against model 40 / best fit with range. Stamp:
     "PREDICTED, NOT FITTED".
  One primary button: **Open the simulator**.
- **Below DETAILS:** the primary-care loop row (with its "assumed behaviour" caveat), the decision-model row, the
  honesty paragraph, the synthetic-patients card (or move it to the Patients page), presenter commands.
- On reusing DEFINE / AUTOMATE / VALIDATE (decided, D61: the look, not the words): reuse the card look so video and site feel like one thing. Change
  the words where ours mean something else. The video's VALIDATE card says "clinician-validated". Here, validate
  would mean the Norway check, and no clinician has validated anything. Keep the video's stamp off the site.

### 2. Simulator (`demo/flow.html`)

- **Message:** "Watch simulated patients move through today's pathway, press Optimise, and see the same patients on
  the reordered one." Details: [04-sim-view.md](04-sim-view.md).
- Primary-care loop (`encounter.html`) is reachable from the Simulator's scenario switch as a third entry
  ("Primary care (assumed behaviour)") that opens the other page. Its results are a separate, labelled model.

### 3. How the patients work (new: `demo/patients.html`)

- **Message:** "Every simulated patient carries a hidden truth. The system only sees what each test reveals, so the
  optimiser learns from the record, not from the answer."
- **Top infographic:** one patient card drawn in two layers, then the loop.
  ```
  [ SEALED: condition · every test's pre-drawn result ]   [ VISIBLE RECORD: fills as steps reveal ]
        1 RUN today's pathway on training patients (truth hidden)
        2 READ the records: which step held each patient back, which tests turned out not to be needed
        3 PROPOSE a change (order or structure of steps, from a fixed menu)
        4 RERUN the same patients: keep it only if faster and no more cancers missed
        5 TEST on new patients, truth hidden again: this is the number we report
  ```
  A Reveal toggle on one example patient (reuse `encounter.html`'s record and truth split) lets the reader lift the seal.
- **Why this is not overfitting** (the one paragraph above DETAILS): proposals use revealed information only; a change
  is kept only if it helps the same patients on a rerun; the reported number comes from patients the search never saw.
  The bound number "selection optimism" (Norway, 1.7 points between training and held-out) shows the size of the gap.
- **Be precise where Tuomas's description goes further than the method.** Step 4 is a simulator privilege: rerunning
  the same patients is an exact counterfactual. In real life that step is a pilot (master plan, section 6). Step 2 has
  a known bias: a test run only on patients who failed earlier tests looks better in hindsight than it is (master plan,
  section 4, "Hindsight bias"). The page should say both. They are what makes the method credible.
- **Below DETAILS:** the catalogue (11 conditions, 26 tests, draft, no clinician has read it), template-written vs
  model-written cards and their counts (bound from `cards_bundle.js`), the report-leak finding and its fix, the audit,
  links to `docs/synthetic_data_for_jev.md` and `catalogue/README.md`.

### 4. Does it hold up? (new: `demo/evidence.html`)

- **Message:** "Fitted only to a Norwegian hospital's observed pathway, the model ranks the authors' redesign above
  a faster scanner, and both above today, in every setting that fits. Trust the ranking, not the exact size."
- **Top infographic:** a dot-and-range chart with three rows (today, faster scanner alone, authors' reordered pathway)
  and a fourth for our optimiser. Each row has the published value (hollow ring), the model at best fit (filled dot), and
  the range over the 184 fitting settings (thin bar). The faster-scanner row shows the miss in plain sight. Numbers come
  from `start_bundle.js` (already exported).
- **Robustness as the main driver of the page** (Tuomas's idea): below the chart, five small multiples, one per
  test in `docs/validation.md` "Robustness" (grid extension, identifiability, leave one out, target noise, the
  faster-PET miss), then the optimiser on 184 settings, ablation and the structure check. Each gets a finding as its
  heading and a single small chart or number.
- **The case-study paper:** it now exists as `docs/norway_case_study.md` (merged 14 Nov evening, paper-style, with the
  plausibility framing of D62). Tonight the Evidence page links it. After the submission (D61) it becomes a printable HTML
  (`demo/norway_case.html`, print CSS → PDF) that cites the Stokstad paper and does not attach it.
- **Below DETAILS:** data and honesty (ledger counts, what is sourced vs assumed), and the "Full results report" link to
  `index.html`.

### 5. Decision model (`demo/jev.html`, merged from `w8/jev-demo`; restructure in lane L5; wording kept per D63)

- **Message:** "At each clinical decision the model scores the allowed next steps from the visible record; a person
  decides."
- **Top infographic:** record → node → options with score bars → human Accept / Override, with a stamp on the
  answer: LIVE or SAVED EXAMPLE.
- **Below DETAILS:** the model card (what it was trained on, held-out set, scores are relative not probabilities,
  known failure modes, live vs saved), commands, links to `decision_api/` and the note reader.

## What leaves the nav (still reachable)

| Page | Reached from |
|---|---|
| `encounter.html` | Simulator scenario switch; Patients page |
| `index.html` dashboard | Evidence page, DETAILS: "Full results report" |
| `live_demo/`, `/note`, `/decision` | Decision model page, DETAILS (need their servers) |
| React app | Overview DETAILS: "The platform behind it" with the run command |
| Markdown docs | DETAILS sections only |

# C1 Patient engine

| | |
|---|---|
| Package | `patient_engine/` (new) |
| State | Not started. Replaces `pathway_sim/patients.py` through an adapter |
| Depends on | C2 catalogue (reference content), a language-model endpoint, `pathway_sim/dists.py` (keyed random numbers) |
| Used by | C3 simulation (reveal, episodes), C6 platform (card viewer, libraries), Eemeli's note reader (notes) |
| Contracts it owns | `card/1`, `library/1`, `cohort/1`, the reveal API |
| Track | In scope for the Sunday submission as a thin slice (section "Sunday slice"); the rest is platform track |

Revised 14 Nov after Tuomas's answers: **the language model generates the whole patient card and
the results of all tests** (decision D39); a patient has one primary condition and may also have
a co-existing ordinary illness, which makes patients return after treatment (D40).

## Purpose

Generate realistic synthetic patients whose truth is hidden, in a form the simulation can reveal
piece by piece. A patient is a **patient card**: background information, a hidden primary
condition (a cancer, another illness, or healthy), optionally a co-existing illness, hidden
variables derived from them (symptoms, findings), and the result that every test in the catalogue
would give for this patient. The card is written by a language model, conditioned on the
catalogue and checked against it.

## What exists today and why it is not enough

`pathway_sim/patients.py` draws a condition, a presentation group, an age, one hidden attribute
and a yes/no result per test and attempt from fixed probabilities. Results are keyed by
(seed, patient, test, attempt), so the same patient gets the same result in every flowchart: the
property to keep. Limits: no symptoms or measured values, one thing revealed per test, process
steps counted as tests, nothing readable, one illness only, no return after treatment.

## Design

### Roles: who produces what

| Thing | Produced by | Why |
|---|---|---|
| Which condition(s) each patient has; how many patients of each | The engine, from the cohort's design and the catalogue's prevalence, with keyed random numbers | The mix of conditions is the experiment's design. It has to be exact and reproducible |
| Everything on the card: background, symptoms and findings, what the patient reports, the results of every test, notes | **The language model**, in structured form | Tuomas's decision D39. Gives coherent, varied, realistic patients that a table of independent probabilities cannot |
| Whether a given test result is right, a miss, a false alarm or a failed sample | Setting `error_source`: `guided` (the engine draws it from the catalogue's rates and the model writes a result that fits) or `free` (the model decides) | Language models do not draw calibrated random numbers. See "Error rates" |
| Whether a card is acceptable; whether a set of cards has realistic rates | The engine: validation per card, audit per library | Realism has to be measured, not assumed |

### The card (`card/1`)

Sections have different visibility and are different types in code, so code on the revealed side
cannot hold a hidden field (invariant I1).

| Section | Contents | Visible |
|---|---|---|
| `background` | age, sex, smoking, known long-term conditions, region and other equity-relevant facts | From arrival |
| `presenting` | What the patient says at first contact, per episode | From first contact of that episode |
| `hidden.conditions` | A list: exactly one with `role: primary`, optionally one or more with `role: coexisting`; each with attributes (for a cancer: stage, histology, location) | Scoring only |
| `hidden.findings` | Every hidden variable of the catalogue, **with the condition that causes it** | Scoring only |
| `observations` | For every state, test and attempt: the values the test reports (below) | Hidden until a step reveals that (test, attempt) in the current state |
| `notes` | Readable text: the patient's account, a nurse note, a referral letter | Each note is tied to the facts it may mention; shown only when those are revealed |
| `provenance` | Library id, model, prompt version, generation mode, validation result | Always |

Illustrative shape (names for the spec agent to fix; values show structure, not medical content):

```json
{
  "format": "card/1", "id": "L_9c1e:000217",
  "background": {"age": 67, "sex": "f", "smoking": {"status": "former", "pack_years": 30}, "region": "rural_east"},
  "hidden": {
    "conditions": [
      {"id": "lung_cancer", "role": "primary", "attributes": {"stage": "II", "location": "peripheral"}},
      {"id": "pneumonia", "role": "coexisting"}
    ],
    "findings": {
      "cough_3wk":   {"value": true, "caused_by": ["lung_cancer", "pneumonia"]},
      "fever":       {"value": true, "caused_by": ["pneumonia"]},
      "weight_loss": {"value": true, "caused_by": ["lung_cancer"]},
      "crp_true":    {"value": 85.0, "caused_by": ["pneumonia"], "without": {"pneumonia": 9.0}}
    }
  },
  "states": ["all_active", "pneumonia_resolved"],
  "presenting": {"all_active": {"reported": ["cough_3wk", "fever"]},
                 "pneumonia_resolved": {"reported": ["cough_3wk", "weight_loss"]}},
  "observations": {
    "all_active": {
      "chest_xray": [{"abnormal": true, "report": "Right lower lobe consolidation."}],
      "blood_basic": [{"crp": 88, "hb": 128}]
    },
    "pneumonia_resolved": {
      "chest_xray": [{"abnormal": false, "report": "Consolidation resolved."},
                     {"abnormal": true, "report": "Residual 18 mm opacity, right lower lobe."}],
      "blood_basic": [{"crp": 11, "hb": 126}],
      "chest_ct":   [{"nodule_seen": true, "size_mm": 17, "location": "peripheral"}]
    }
  },
  "provenance": {"library": "L_9c1e", "model": "…", "prompt": "card-author@2", "error_source": "guided"}
}
```

### More than one illness, and patients who come back (D40)

A patient has one **primary** condition. Some also have a **co-existing** ordinary illness (the
catalogue gives how often which pairs occur). This is how a cancer hides behind a pneumonia.

- **Findings carry their cause.** A symptom is present if any active condition causes it.
- **States.** A condition is active or resolved. With at most one co-existing illness a patient
  has two or three states (`all_active`, `<illness>_resolved`, rarely both resolved). The card
  holds findings, the presenting complaint and test results **for each state**, written by the
  model in one coherent story.
- **Treatment** is a step in the flowchart (C3): it targets a working diagnosis. If the patient
  truly has that condition, it resolves (with the catalogue's response rate and time course) and
  the findings caused only by it disappear. If the patient does not have it, nothing changes.
- **Return.** After an episode ends without a cancer diagnosis, the patient's remaining findings
  decide, through the catalogue's behaviour model, whether and when they contact care again.
  They re-enter at first contact as a new **episode**, in the new state, with everything
  revealed in earlier episodes still on record, including "treated for pneumonia, symptoms
  persist".
- **What it shows.** Time lost to a wrong or incomplete first diagnosis, counted from the very
  first contact. This is the delay the equity evidence points at (vague symptoms explained by an
  ordinary illness), and it gives decision nodes a real reason to use history.

A patient with only an ordinary illness is treated, resolves and does not return: the correct
discharge. A patient with only a cancer who is treated for a presumed infection does not improve
and returns.

Disease progression while waiting (a tumour growing) is still out of version 1; the state
mechanism above is what it would later use.

### Generation pipeline

```
G0 skeleton ─► G1 patient author (LLM) ─► G2 result author (LLM) ─► G3 validate + repair ─► card
                                                                            │
                         library ◄── G4 audit against the catalogue ◄───────┘
                            │
                            └─► G5 cohort assembly (no LLM): draw cards to the wanted mix and size
```

| Stage | Does | LLM |
|---|---|---|
| G0 Skeleton | Per card: the condition(s) and attributes class from the library design (how many cards of each condition, which pairs); a variation brief (age band, region, a persona hint) from keyed random numbers so cards differ; in `guided` mode the error plan for each test and attempt | no |
| G1 Patient author | Writes background, hidden findings with causes for each state, and what the patient reports per state. Input: skeleton, the catalogue's variable list with reference frequencies, the population description | yes |
| G2 Result author | Writes the result of **every test in the catalogue**, for each state and attempt, from the hidden findings, the test's reference accuracy and the error plan. Also writes the short report text | yes |
| G3 Validate and repair | Schema, types, ranges, catalogue constraints, consistency rules (a result marked "miss" must not show the finding; a resolved illness leaves no finding caused only by it). On failure: ask again with the errors, at most twice; then discard and log | repair only |
| G4 Audit | Over the library: frequencies of findings by condition, realised sensitivity and specificity of every test output, share of failed samples, diversity (near-duplicates), all against the catalogue's reference values with tolerances. Report stored with the library | no |
| G5 Cohort assembly | A simulation cohort of any size is drawn from a library with keyed random numbers to the prevalence of the scenario; each drawn patient gets an arrival time | no |

Two model calls per card (G1, G2) instead of one: the result author works from fixed findings, so
its errors can be audited separately, and each can use a different model or temperature. Output
is JSON against a schema generated from the catalogue. Notes (history, referral letter) are a
third, optional call per card or are written by G1; the spec agent decides.

### Error rates: `guided` or `free`

The vision asks for realistic accuracy, variation and true and false positive rates.

- **`guided` (lean, default).** For each test and attempt the engine draws, from the catalogue's
  rates and a keyed random number, one of: correct, miss, false alarm, non-diagnostic. The model
  writes a concrete result that fits both the plan and the patient ("the 14 mm lesion lies behind
  the heart shadow and is not seen"). Rates are right by construction and the content is the
  model's.
- **`free`.** The model is given the reference accuracy and decides itself. The audit then
  measures what it produced. Expect drift: models tend to make tests too accurate and patients
  too typical.

Both modes are built; the audit runs on both; the library records which was used. **Open for
Tuomas (Q1):** `guided` keeps the model as the author of every result but lets the engine roll
the dice. If "the LLM generates the results" must mean `free`, the audit and its tolerances
become the only control.

### Libraries, cohorts and reproducibility

Generation by a language model is not repeatable from a seed, costs money and takes time. So:

- A **library** (`library/1`) is an immutable, stored set of validated cards with its audit
  report, identified by a content hash. It keeps prompts, model id, settings and raw responses.
  Small libraries are committed to the repo so the demo runs with no network and no key.
- A **cohort** (`cohort/1`) is `(library id, scenario prevalence, n, seed)`: fully reproducible
  without a model. A 19 000-patient run draws from a library of a few hundred to a few thousand
  cards. Cancers are rare among presenters, so a library is stratified: enough cards of each
  condition and pair (the spec agent sets counts; a first guide is at least 150 per condition
  and 300 for the cancer).
- Stated limit: a large cohort repeats cards. Queues and waits come from volume and are
  unaffected; variety of patients is bounded by the library. Every result says which library and
  how many distinct cards it used.
- Everything that must hold between runs still holds: the same card gives the same result for
  the same (state, test, attempt) in every flowchart (invariant I3).

Storage: one JSON-lines file of cards per library (gzip) plus a manifest, and a compact array
form for the simulator built at load. The spec agent sizes it: 2 000 cards × about 20 tests ×
up to 3 states × up to 3 attempts.

### The language-model client

An OpenAI-compatible endpoint from `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, standard library
only, as `technique_classifier/llm.py` does (copy the small client, do not import Eemeli's
package). Needs: structured JSON output with schema check, bounded concurrency, retry with
backoff, a hard budget per library (calls and tokens), a cache keyed by prompt hash so a rerun
continues where it stopped, and a log of every call. **The build environment of the architect
session has no endpoint and cannot reach one; generation runs where a key exists** (Tuomas's or
Eemeli's machine, or the hosted box).

### Without a network: the reference generator

A small rule-based generator produces `card/1` cards straight from the catalogue's reference
numbers (independent draws, template report texts). It is not the product; it exists so that
tests and continuous integration run offline, so the pipeline can be built before a key is
available, and as the baseline the audit compares model libraries against.

### Reveal

The simulation never reads a card. It holds a handle:

```
visible(patient, episode)                    -> background + presenting for the current state
reveal(patient, test, attempt, state)        -> {output: value | "non_diagnostic"}, report text
truth(patient)                               -> conditions            (scoring only, after the run)
```

### Compatibility with today's simulator

1. **Adapter.** A cohort becomes `pathway_sim.Patient` objects: each test's boolean comes from
   the catalogue's `positive_when` rule, attributes from revealed outputs, first state only.
   Shipped scenarios are untouched.
2. **Comparison.** A library generated for the current Finnish scenario's conditions and tests is
   run through the current flowcharts next to the current generator; the differences in headline
   numbers are reported and explained. The published Norway check stays on the calibrated
   scenario and does not use model-written patients.
3. **Switch.** C3 learns typed outputs, states and episodes; scenarios use catalogue tests.

### Honesty

A library is labelled "written by a language model, audited against sourced reference rates"
wherever its patients or results appear, with the audit one click away. Headline numbers move to
model-written cohorts only after the audit passes and Tuomas says so; until then they stay on
the current generator and the model-written patients are shown as patients (cards, traces,
notes), not as the source of the headline.

## Sunday slice (what can ship by the freeze)

| # | Piece | Gate |
|---|---|---|
| 1 | `card/1` contract and validator | tests |
| 2 | A first catalogue: the current Finnish scenario's conditions and tests plus symptoms and basic bloodwork, reference rates marked by source or `assumption` | loader validates |
| 3 | Generator G0 to G3 in `guided` mode, the client, the reference generator | offline tests on the reference generator; a real library of about 300 cards generated where a key exists |
| 4 | Audit report | generated for that library; shown, pass or fail |
| 5 | Adapter, and the card shown in the patient trace of the flow page or the web app (background, what was revealed, the notes; hidden truth only in a teaching view) | a run on a model-written cohort completes; the Norway golden check still passes |

Not in the slice unless time remains: co-existing illness with states and return episodes (it
needs engine changes in C3), `free` mode, libraries above a few hundred cards.

## Sub-wholes (for the spec agent; one work package each unless noted)

| # | Sub-whole | Outcome | Notes for speccing |
|---|---|---|---|
| P1 | **Card, library and cohort contracts** | Types (hidden and revealed separate), JSON Schema generated from a catalogue, examples, contract tests | Contract-first; fix names here. Sunday slice |
| P2 | **Catalogue loader and validator** | Typed catalogue, version hash, problems list | Shared format with C2 K1. Sunday slice |
| P3 | **Model client** | Structured output, concurrency, retries, budget, cache, call log; a fake client for tests | No dependency on the rest. Sunday slice |
| P4 | **Skeleton and error plan** (G0) | Library design to per-card skeletons with keyed random numbers | Small. Sunday slice |
| P5 | **Authors** (G1, G2) | Prompts, schemas, the two calls, notes | Prompt versions are data. Review required (information boundary: G2 sees hidden findings and is hidden-side code; note text must not leak). Sunday slice |
| P6 | **Validate and repair** (G3) | Rules, repair loop, discard log | Sunday slice |
| P7 | **Audit** (G4) | Report in JSON and Markdown; tolerances from the catalogue | Sunday slice |
| P8 | **Reference generator** | Offline cards from catalogue numbers | Enables tests for everything else. Sunday slice |
| P9 | **Library store and cohort assembly** (G5) | Write, load, hash; draw cohorts; array form | Sunday slice (simple form) |
| P10 | **Adapter and comparison** | Cohort to today's `Patient`; comparison report | Review required (headline numbers). Sunday slice |
| P11 | **States, treatment response and return** | Multi-state cards, behaviour model use, episode support in the reveal handle | With C3 E7. Platform track |
| P12 | **Platform exposure** | Library and card routes; card viewer; generation as a job with a budget | With C6 |
| P13 | **Command line** | `python -m patient_engine design|generate|audit|show|cohort` | Fold into the packages above |

Order: P1, P2, P3 and P8 first and in parallel (P1 publishes the contract in its first ticket);
then P4, P5, P6; then P7, P9, P10. P11 and P12 after.

## Open questions

| # | Question | Lean | Who |
|---|---|---|---|
| Q1 | `guided` or `free` error rates as the default | `guided` | Tuomas |
| Q2 | Which endpoint, model and budget; who runs generation | The team's OpenAI-compatible endpoint; a cap per library | Tuomas, Eemeli |
| Q3 | Background variables for equity (region, access to care) | Region and one access variable | Tuomas, C2 |
| Q4 | Do headline numbers move to model-written cohorts for Sunday | No: show the patients, keep the headline on the calibrated generator, unless the audit passes early | Tuomas |
| Q5 | Notes in Finnish | English first; Finnish as a setting | Tuomas |
| Q6 | How many co-existing illnesses at once | One | Tuomas |

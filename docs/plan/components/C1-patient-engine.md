# C1 Patient engine

| | |
|---|---|
| Package | `patient_engine/` (new) |
| State | Not started. Replaces `pathway_sim/patients.py` through an adapter |
| Depends on | C2 catalogue (content), `pathway_sim/dists.py` (common random numbers) |
| Used by | C3 simulation (reveal), C6 platform (card viewer, cohorts), Eemeli's note reader (narratives) |
| Contracts it owns | `card/1`, `cohort/1`, the reveal API |
| Track | Platform |

## Purpose

Generate realistic synthetic patients whose truth is hidden, in a form the simulation can reveal
piece by piece. A patient is a **patient card**: background information, a hidden primary
condition, hidden variables derived from it (symptoms, findings, true values), and the result that
every test in the catalogue would give for this patient, drawn in advance.

## What exists today and why it is not enough

`pathway_sim/patients.py` draws a condition from a prevalence table, a presentation group, an age,
one hidden attribute (tumour location) and, for each test in the scenario, a yes/no result for
four attempts from `p_positive[condition]`. Draws use common random numbers keyed by
(seed, patient, test, attempt), which is the property to keep. Limits:

- No symptoms, findings or measured values: a test can only say yes or no about "the condition".
- Tests and process steps are one list: a nurse visit and a referral letter are "tests".
- A test reveals at most one thing. A CT report cannot say "nodule, 18 mm, peripheral".
- The presentation group is sampled directly instead of following from the patient's symptoms.
- Nothing a person can read: no history, no note. The note reader has to use hand-written examples.
- The patient model lives inside each scenario file, so two scenarios cannot share patients.

## Design

### The card (`card/1`)

A card has five sections with different visibility. The sections are different types in code, so
revealed-side code cannot hold a hidden field (invariant I1).

| Section | Contents | Who can see it, when |
|---|---|---|
| `background` | age, sex, smoking history, known long-term conditions, home region and other equity-relevant facts the catalogue defines | Everyone, from arrival |
| `presenting` | The complaint the patient brings to first contact: which symptoms they mention and for how long | Everyone, from first contact. Derived from the hidden findings through a reporting model (patients under-report) |
| `hidden.condition` | Primary condition id and its attributes (for a cancer: stage, histology, location) | Scoring only |
| `hidden.findings` | The true value of every hidden variable in the catalogue: symptoms present or not, true laboratory values, what imaging would truly show | Scoring only |
| `observations` | For every test in the catalogue and each attempt: the values the test would report | Hidden until a flowchart step reveals that (test, attempt) |

Illustrative shape (field names are for the spec agent to fix; values here are made up to show
the structure, not medical content):

```json
{
  "format": "card/1",
  "id": "c_7f3a:000017",
  "cohort": "c_7f3a",
  "background": {"age": 67, "sex": "f", "smoking": {"status": "former", "pack_years": 30},
                 "long_term": ["copd"], "region": "rural_east"},
  "presenting": {"reported": {"cough_3wk": true, "weight_loss": false}, "duration_days": 40,
                 "group": "non_specific"},
  "hidden": {
    "condition": {"id": "lung_cancer", "attributes": {"stage": "II", "location": "peripheral"}},
    "findings": {"cough_3wk": true, "haemoptysis": false, "weight_loss": true,
                 "crp_true": 22.0, "nodule_size_mm": 18.0}
  },
  "observations": {
    "chest_xray": [{"abnormal": false}, {"abnormal": true}],
    "blood_basic": [{"crp": 24.1, "hb": 128, "platelets": 410}],
    "chest_ct":   [{"nodule_seen": true, "size_mm": 17.0, "location": "peripheral"}]
  },
  "provenance": {"catalogue": "lung-primary-care@3:9c1e", "generator": "1.0", "seed": 301, "index": 17}
}
```

The **revealed record** is not on the card. It belongs to a run: background, presenting, and the
observations that the run's steps have revealed so far, each with the day it became known.

### Variable types

The catalogue (C2) declares each hidden variable with a type. The engine supports:

| Type | Example | Observation model |
|---|---|---|
| `binary` | haemoptysis present | sensitivity and specificity, optionally depending on other hidden values |
| `categorical` | tumour location | confusion matrix |
| `ordinal` | stage | confusion matrix with near-miss structure |
| `continuous` | CRP in mg/L, nodule size in mm | true value plus measurement noise; reporting limits; reference range gives a derived flag |
| `count` / `duration` | symptom duration in days | noise model as for continuous |

Every test output can also come back **non-diagnostic** (failed sample, unreadable image) with a
rate that may depend on hidden values (a peripheral lesion and bronchoscopy).

### Generation pipeline

```
G1 background ─► G2 condition ─► G3 condition attributes ─► G4 findings ─► G5 observations ─► G6 presenting
                                                                                                  │
                                                         G8 checks ◄── cohort ◄── G7 narrative (optional, lazy)
```

| Stage | What it draws | From |
|---|---|---|
| G1 | Background, from a named population | `catalogue/populations/*.yaml` |
| G2 | Primary condition given background (prior among people who present, not the general population) | conditions: prevalence with modifiers by background |
| G3 | Attributes of the condition (stage, histology, location; severity for other illnesses) | the condition's entry |
| G4 | Every hidden variable given condition, attributes and background | variables: a distribution per condition with optional modifiers |
| G5 | For every test, every output, every attempt: the reported value | tests: the observation model per output |
| G6 | What the patient reports at first contact, and the presentation group derived from it | reporting model in the catalogue |
| G7 | Text: history, nurse note, referral letter | a renderer over the card's visible parts (below) |
| G8 | Cohort-level checks against the catalogue and against published marginals | below |

Dependency structure for version 1: variables are independent given (condition, attributes,
background). Where two variables must move together, the catalogue declares one as a modifier of
the other (stage modifies weight loss; nodule size modifies X-ray sensitivity). That is a
directed acyclic graph the validator checks. A full joint model is a later step.

### Common random numbers and time

Each draw uses a uniform number keyed by `(seed, patient index, stage, variable or test, output,
attempt)` through `pathway_sim/dists.py`. Consequences to keep:

- Adding a test or a variable to the catalogue does not change any other draw.
- The same patient gives the same result for the same (test, attempt) in every flowchart
  (invariant I3).

Version 1 materialises observation values at generation. **Store the design so that an
observation is a function of the keyed uniform and the hidden state**, not an independent random
value: then a later version can let hidden state change with waiting time (tumour growth, a
symptom that resolves) and compute the observation at the day of the test, without changing how
cohorts are identified. Do not build progression now (assumption V6).

Repeat attempts: independent draws per attempt in version 1, with one catalogue option,
`persistent_miss`, for the share of misses that repeat because the cause is in the patient, not
the measurement. The spec agent should confirm with C2 whether sources support a value; default off.

### Reveal

The simulation never reads a card. It holds a handle with two operations:

```
visible(patient)                      -> background + presenting              (revealed side type)
reveal(patient, test, attempt)        -> {output: value | "non_diagnostic"}   (revealed side type)
```

and, separately, for scoring after the run only: `truth(patient) -> condition, attributes`.
The adapter to today's engine maps these onto `Patient.results` and `Patient.attributes` so the
shipped scenarios keep running (next section).

### Compatibility with today's simulator

Three steps, each shippable:

1. **Adapter.** A cohort from the patient engine can be turned into `pathway_sim.Patient` objects:
   each test gets a boolean "positive" derived from its outputs by the catalogue's interpretation
   rule (for example `abnormal == true`), attributes come from revealed outputs. Shipped scenarios
   are untouched.
2. **Equivalence.** A catalogue that encodes exactly today's Finnish and Norwegian scenarios
   reproduces their headline numbers within sampling error (it cannot be byte-identical, the draw
   keys differ). This is the proof the new engine is at least as good as the old.
3. **Switch.** C3 learns typed, multi-output reveals (`components/C3-simulation.md`), and
   scenarios reference catalogue tests instead of defining their own.

### Cohorts and storage (`cohort/1`)

A cohort is immutable and identified by a hash of its manifest:

```json
{"format": "cohort/1", "id": "c_7f3a", "catalogue": "lung-primary-care@3:9c1e",
 "generator": "1.0", "population": "finland_adults_presenting", "seed": 301, "n": 18800,
 "arrivals": {"rate_per_day": 51.5}, "checks": "passed", "created": "2026-11-14T16:40:00Z"}
```

- **Regenerable.** The manifest alone reproduces every card. Stored data is a cache; a test
  regenerates a sample and compares hashes.
- **Columnar for the simulator, documents for people.** The simulator needs arrays (one per
  variable and per test output), not 19 000 JSON objects. The card JSON is rendered on request
  for the viewer and exports. Lean for the store: compressed numpy arrays plus the manifest under
  the service's data folder, card JSON on demand. Parquet only if a later need justifies the
  dependency.
- **Narratives are stored apart**, keyed by a hash of (card visible content, template version,
  model id, style settings), because they are expensive, optional and not reproducible from the
  seed.
- **Size guide.** 20 000 patients × about 40 variables × about 20 tests × up to 4 attempts must
  load in well under a second and stay under about 50 MB.

### Narratives with a language model (G7)

Role of the language model, exactly (principle 2, assumption V3):

| Use | Input | Output | Safeguards |
|---|---|---|---|
| **A. Render a card as text**: the patient's own account, a nurse's note, a GP's referral letter, in Finnish or English | Only the fields visible at that point in the pathway (background, presenting, revealed observations so far), plus style settings | JSON with the text and the list of facts it used | See below |
| **B. Draft catalogue entries** for C2 (symptom profiles, look-alike conditions) | Clinical knowledge prompt | A YAML draft | Graded `llm_draft`; a human or a sourced reference must upgrade it before it counts as sourced; the ledger shows the count |
| **C. Plausibility critic** (later) | A sample of cards | Comments on implausible combinations | Advice to catalogue authors only; never edits data |

Safeguards for use A:

1. **The model never sees hidden fields.** The renderer's input type is the revealed-side type.
2. **Round-trip check.** A second pass (rules first, model if needed) extracts the facts from the
   text and compares them with the input facts. Missing or contradicting facts: regenerate, then
   fall back to the template renderer.
3. **Leak check.** The text must not name the hidden condition or any unrevealed finding (word
   list from the catalogue plus the extraction pass).
4. **Offline fallback.** A deterministic template renderer produces usable text with no network.
   Tests run on the fallback. The model is an upgrade, never a requirement.
5. **Budget.** Narratives are generated only for cards someone opens or exports, with a cap per
   cohort and a cache.
6. **Style settings are data.** Documentation quality and known documentation flaws (the
   classifier's `clinical_notes` taxonomy: for example a red flag noted without action) can be
   switched on per note, recorded in the note's metadata, so Eemeli's classifier has labelled
   examples. Coordinate the shape with Eemeli's side on the channel before building.
7. **Adapter.** Reuse the approach of `technique_classifier/llm.py`: an OpenAI-compatible endpoint
   from `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, standard library only. Do not import from
   Eemeli's package; copy the small client or agree a shared module with his side.

### Checks (G8)

A cohort is usable only if these pass; the report is stored with the cohort and shown in the UI.

| Check | Example |
|---|---|
| Marginals match the catalogue | condition shares within sampling error of prevalence |
| Derived quantities match published ones | positive predictive value of a chest X-ray among presenters near the published value already used in `scenarios/finland_lung.yaml` |
| Each test's realised sensitivity and specificity match its entry | per test output |
| No impossible cards | catalogue constraints (a stage without a tumour) |
| Information boundary | the revealed-side view of a sample of cards contains no hidden key |
| Determinism | regenerate 100 cards from the manifest; hashes equal |

## Sub-wholes (for the spec agent; one work package each unless noted)

| # | Sub-whole | Outcome | Notes for speccing |
|---|---|---|---|
| P1 | **Card and cohort contracts** | Types for the five card sections, the revealed record, the cohort manifest; JSON examples; contract tests | Contract-first package; everything else needs it. Fix field names here. Hidden and revealed must be separate types |
| P2 | **Catalogue loader and validator** | Load `catalogue/*.yaml` into typed objects; validate (types, modifier graph is acyclic, probabilities in range, every number has a source or `assumption`); version hash | Shares the format with C2: agree it with the C2 spec agent first. Reuse `pathway_sim/problems.py` for the problem list |
| P3 | **Sampler** (G1 to G4, G6) | `sample_cohort(catalogue, population, n, seed)` returns arrays and can render any card | Keyed uniforms; vectorise with numpy; a 20 000-patient cohort in a few seconds |
| P4 | **Observation models and reveal** (G5) | Every output type in the table above; non-diagnostic; attempts; the reveal handle | The function-of-uniform design above. Property tests: realised sensitivity and specificity converge to the entry |
| P5 | **Adapter and equivalence** | Cohort to `pathway_sim.Patient`; a catalogue encoding of the two shipped scenarios; headline numbers within sampling error | Review required (headline numbers). Do not change shipped scenarios |
| P6 | **Cohort store** | Write, load, regenerate, hash; integrate with the service's data folder | Needs P1; small |
| P7 | **Narratives** | Template renderer, model renderer, round-trip and leak checks, cache | Needs P1; coordinate with Eemeli's side. Review required (information boundary) |
| P8 | **Checks and report** (G8) | The check table as code; a cohort report in JSON and Markdown | Needs P3 and P4 |
| P9 | **Command line** | `python -m patient_engine sample|show|check` | Small; can be folded into P3 and P8 |
| P10 | **Platform exposure** | Service routes for cohorts and cards; a card viewer in the web app with a hidden/revealed split; the run's patient trace shows what was revealed when | Belongs with C6; ticket after P1 and P6. In the viewer, hidden truth is shown only in an explicit "teaching view" |

Suggested order: P1 and P2 first (contracts), then P3, P4, P6, P7 in parallel, then P5 and P8,
then P10.

## Open questions

| # | Question | Lean | Who |
|---|---|---|---|
| Q1 | Background variables for equity: which ones (region, distance to hospital, language, income proxy)? They matter for the challenge's theme | region and one access variable in version 1, sourced from Finnish statistics | Tuomas, C2 |
| Q2 | How does the patient decide to seek care and to come back (today: a `symptoms_persist` "test")? | A patient-behaviour model in the catalogue (probability of re-presenting given findings), revealed like a test | C2 and C3 spec agents |
| Q3 | Should a cohort include healthy people who never present? | No: the cohort is "people who contact primary care with these complaints"; say so in the UI | Tuomas (assumption V2) |
| Q4 | Finnish-language narratives in version 1? | English first, Finnish as a style setting once the checks pass in English | Tuomas |
| Q5 | Which model and budget for narratives | whatever the team's endpoint serves; cap per cohort | Tuomas, Eemeli |

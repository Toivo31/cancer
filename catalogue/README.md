# The clinical catalogue format (`catalogue/1`)

A catalogue holds the medical content of the simulated world, separate from any pathway: which
conditions people who present have, which hidden facts (symptoms, signs, true lab values, imaging
truth) each condition brings, and which tests exist, what each reveals and how accurately. It is
data that people who are not programmers can read and correct. The patient engine
(`patient_engine/`) loads it, checks it, generates the JSON Schema of a patient card from it, and
uses its numbers to guide and audit the patients a language model writes.

**Everything here is synthetic-world content. Until a clinician has read a catalogue it is a
draft** (`status: draft`), and the user interface says so.

Load and check one:

```
python -c "from patient_engine.catalogue import load_catalogue; c = load_catalogue('catalogue/_examples/tiny'); print(c.version_hash, len(c.tests))"
```

`load_catalogue` raises `CatalogueError` with the list of problems (file, path, message, hint) if
anything is wrong; warnings are kept on `catalogue.problems`.

## Files

One catalogue = one folder = one clinical setting.

| File | Required | Holds |
|---|---|---|
| `catalogue.yaml` | yes | id, version, title, status, scope, `max_attempts`, the `background` fields |
| `conditions.yaml` | yes | primary conditions with prevalence and attributes |
| `variables.yaml` | yes | hidden variables with a distribution per condition |
| `tests.yaml` | yes | tests with typed outputs, accuracy, timing, cost, harm |
| `cooccurrence.yaml` | no | which ordinary illness occurs next to which primary condition |
| `populations/`, `behaviour.yaml`, `treatments.yaml`, `constraints.yaml` | no | planned (C2 K3, K6); not read by `catalogue/1` yet |

Examples: `catalogue/_examples/tiny/` (every feature once; numbers are placeholders) and
`catalogue/_examples/broken/` (one deliberate mistake per file, used by the tests).

All ids are snake_case: lower-case letters, digits and `_`, starting with a letter. Ids must be
unique across variables, tests, background fields and condition attribute names, so that a name
in `by:`, `only_if` or a note's `mentions` means one thing.

## Rules for numbers (apply everywhere)

1. **Every reference number is an object**, never a bare number:

   ```yaml
   sensitivity: {value: 0.754, source: BRADLEY2021, grade: B, note: "symptomatic over-50s"}
   ```

   | Key | Meaning |
   |---|---|
   | `value` | a single number (a probability, a time, a cost) |
   | `p` | only in `given` of a **binary** variable: the probability that it is true |
   | `dist` + parameters | a distribution, same vocabulary as the simulator (`pathway_sim/dists.py`): `{dist: fixed, value}`, `{dist: lognormal, median, p90}`, `{dist: uniform, low, high}`, `{dist: exponential, mean}`, `{dist: empirical, values: [...]}` |
   | `values` | a categorical distribution: `{level: share, ...}`, shares add up to 1 |
   | `source` | **required**: an id in `params/sources.yaml`, or `assumption` |
   | `grade` | optional: `A` (systematic review or large study in a comparable population), `B` (single study or related population), `C` (expert statement, guideline text, derived), `assumption` (chosen by us; say why in `note`), `llm_draft` (proposed by a language model, not yet checked) |
   | `note` | optional: population it was measured in, how it was derived |
   | `low`, `high` | optional range for sensitivity analysis of a `value` or `p` (for `dist: uniform` they are the distribution's own bounds) |
   | `by` | optional: how the number changes with another fact (below) |

2. **Probabilities** (`p`, sensitivity, specificity, accuracy, non-diagnostic rates, prevalence,
   shares) must lie in 0..1. Times, costs and error standard deviations must not be negative.
3. **Prevalence is among presenters** in the setting the scope statement names, not in the
   general population. Prevalences of all conditions should add up to 1 (a warning otherwise).
4. **Tests describe medicine, not logistics.** Accuracy, report time, cost, harm. Waiting for a
   slot comes from resources in the world (`resource_kind` only names the kind). Referral letters,
   triage, boards and bookings are flowchart steps, not tests. Clinician judgements are decision
   nodes.
5. **History taking and examination are tests**: they reveal symptoms and signs with their own
   sensitivity (patients forget; clinicians do not ask).
6. **Accuracy is stated for the population it was measured in** (`note`); applied to a different
   one, the grade drops by one.
7. Numbers that only describe the format (`max_attempts`, `range`, `version`) are plain numbers.

### `by:`: a number that depends on another fact

```yaml
p: 0.6
by:
  stage: {IV: 0.75}                     # replaces 0.6 when the cancer's stage is IV
```

- The key under `by` names what the number reads: `condition` (the patient's primary condition
  id), a condition attribute (`stage`, `location`), a variable id (`lesion_size_mm`), or a
  background field (`smoking_status`).
- Each level **replaces** the number when the fact has that level; facts without a listed level
  keep the base number. A level is a number (it replaces `value` or `p`), or a mapping of the
  leaf's own keys that replaces just those keys (`{median: 18, p90: 28}` for a distribution,
  `{values: {...}}` for a categorical one). A mapping level may have its own `by` (nesting, for
  "by location, then by size").
- Levels are the fact's values: category names, `true`/`false` for a binary variable, condition
  ids for `condition`, or **numeric bands** for a continuous or size variable: `"..10"` (below 10),
  `"10..20"` (10 or more and below 20), `"20.."` (20 or more). Bands must not overlap.
- Several keys under one `by` are applied in the order written; with the rule above that order
  only matters if two keys set the same parameter, so avoid that.
- Dependencies must be acyclic: the loader builds the graph from `by:` and `only_if` and reports a
  loop as `by_cycle`. Prevalence may depend only on background fields.

## `catalogue.yaml`

```yaml
format: catalogue/1          # required, exactly this
id: lung_primary_care        # snake_case
version: 1                   # bump on any content change you want people to notice
title: Lung symptoms in primary care
status: draft                # example | draft | reviewed
scope: >                     # who presents, in which setting; what prevalence is a share of
  Adults contacting primary care with chest or general symptoms ...
max_attempts: 3              # attempts per test written on a card (default 3)
background:                  # visible facts about a patient, known from arrival
  - {id: age, label: Age, type: continuous, unit: years, range: {min: 18, max: 100}}
  - {id: sex, label: Sex, type: categorical, values: [f, m]}
  - {id: smoking_status, type: categorical, values: [never, former, current]}
```

Background field: `id`, `label` (optional), `type` (`continuous`, `categorical`, `binary`),
`unit` (continuous), `values` (categorical), `range: {min, max}` (optional bounds). Their
distributions per population belong to `populations/` (not yet read). On a card, background holds
every field listed here, and nothing hidden.

## `conditions.yaml`

```yaml
- id: lung_cancer
  label: Lung cancer
  class: cancer                       # cancer | other_illness | healthy
  prevalence: {value: 0.016, source: assumption, by: {smoking_status: {current: 0.03}}}
  attributes:                         # optional; each a categorical distribution
    stage:    {values: {I: 0.25, II: 0.15, III: 0.25, IV: 0.35}, source: assumption}
    location: {values: {central: 0.35, peripheral: 0.65}, source: assumption}
```

| Field | Meaning |
|---|---|
| `class` | `cancer`, `other_illness` (an ordinary illness that can also co-exist with another condition), `healthy` (no disease found) |
| `prevalence` | share of presenters with this as their primary condition |
| `attributes` | properties of the condition (for a cancer: stage, histology group, location), each a `values` distribution |

## `variables.yaml`

```yaml
- id: lesion_size_mm
  label: Size of the largest lung lesion
  kind: imaging_true          # symptom | sign | lab_true | imaging_true | function_true | tissue_true
  type: size_mm               # binary | continuous | categorical | size_mm
  unit: mm                    # continuous (size_mm is always mm)
  values: [..]                # categorical: the levels
  range: {min: 1, max: 150}   # optional plausibility bounds (continuous, size_mm); used in the card schema
  only_if: "lung_lesion"      # optional: exists only when this expression over other variables holds; else null
  given:                      # distribution per primary condition id; `default` covers the rest
    lung_cancer: {dist: lognormal, median: 30, p90: 60, source: assumption, by: {stage: {I: {median: 18, p90: 28}}}}
    default:     {dist: lognormal, median: 8, p90: 15, source: assumption}
```

`given` entries by type: binary `{p}`; continuous and size_mm a `dist`; categorical `values`.
Inside `given.<condition>`, an attribute name (`stage`) in `by` means that condition's attribute.
Every condition must be covered, by its own entry or by `default` (`missing_given` otherwise).
A finding on a card records which conditions cause it (`caused_by`); the catalogue gives the
reference frequency per condition that the audit checks against.

## `tests.yaml`

```yaml
- id: chest_ct
  label: CT of the chest
  category: imaging           # history | examination | bloodwork | imaging | endoscopy | tissue | function | molecular
  max_attempts: 2             # optional, at most the catalogue's
  outputs:                    # what a result reports; each output measures one variable
    - {id: nodule_seen, type: binary, measures: lung_lesion,
       sensitivity: {value: 0.95, source: assumption}, specificity: {value: 0.8, source: assumption}}
    - {id: size_mm, type: size_mm, measures: lesion_size_mm, only_if: "nodule_seen",
       error_sd: {value: 2.0, source: assumption}}
    - {id: location, type: categorical, measures: lesion_location, only_if: "nodule_seen",
       accuracy: {value: 0.95, source: assumption}}
  nondiagnostic: {value: 0.02, source: assumption}   # optional: share of attempts with no usable result
  positive_when: "nodule_seen"                         # yes/no reading for today's simulator (adapter)
  timing:
    service_days: {value: 0.04, source: assumption}    # optional, value or dist
    report_days: {dist: lognormal, median: 3, p90: 7, source: assumption}
  resource_kind: ct           # which kind of resource performs it; capacity belongs to the world
  cost_eur: {value: 250, source: assumption}
  invasive: false
  harm: {complication_rate: {value: 0.001, source: assumption}}
  requires: [history]         # tests (or test.output) whose results should be known before ordering this
```

Output types and their accuracy model:

| `type` | Measures a variable of type | Value on a card | Accuracy fields |
|---|---|---|---|
| `binary` | binary | `true` / `false` | `sensitivity` (true reported true), `specificity` (false reported false) |
| `continuous` | continuous | number in `unit` | `error_sd` (optional; measurement error, same unit) |
| `size_mm` | size_mm | number, mm | `error_sd` (optional) |
| `categorical` | categorical (same levels) | one of the levels | `accuracy` (share reported as the true level) |

An output with `only_if` (an expression over the test's own output ids) is `null` on a card when
the expression is false. `positive_when` is an expression over the test's output ids, read by the
safe evaluator `pathway_sim/expr.py` (`and`, `or`, `not`, comparisons such as `crp >= 50`; no
function calls). The adapter to today's simulator turns each result into a yes/no with it. A test
without `positive_when` gets a warning.

Accuracy that differs by condition (false alarms from pneumonia on a chest X-ray) is written with
`by: {condition: {pneumonia: 0.8}}` on `specificity`; by tumour location or size with
`by: {location: ...}` or `by: {lesion_size_mm: {"..20": 0.34, "20..": 0.63}}`.

## `cooccurrence.yaml` (optional)

```yaml
- primary: lung_cancer          # any condition
  coexisting: pneumonia         # a condition of class other_illness
  share: {value: 0.10, source: assumption}   # share of `primary` patients who also have it
```

At most one co-existing illness per patient: the shares of one primary must add up to at most 1.

## What a card contains (generated from the catalogue)

`patient_engine.card.card_schema(catalogue)` gives the JSON Schema (draft 2020-12) of a complete
`card/1` card for this catalogue: every background field; for each state, every variable's
finding with its `caused_by`; every test's attempts (1 to `max_attempts`) with every output typed
as above; notes whose `mentions` name variables, tests or `test.output`. An example is
`tests/fixtures/patient_engine/card_example.json` (valid for the tiny catalogue).

## Version hash

`catalogue.version_hash` is a SHA-256 over the normalised content of all files read (entries
sorted by id, mapping keys sorted, numbers as floats). Reordering entries or keys does not change
it; changing any number, note or source does. Libraries record the hash of the catalogue they
were generated from.

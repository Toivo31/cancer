# C2 Clinical catalogue

| | |
|---|---|
| Package | `catalogue/` (new, data only) plus `params/sources.yaml` (the source registry, exists) |
| State | Partly exists, scattered: conditions, tests and accuracy numbers sit inside `scenarios/*.yaml` and `params/test_accuracy.yaml` |
| Depends on | Published evidence. No code dependency |
| Used by | C1 (generation), C3 (which tests a step can perform, timing, resources), C7 (ledger) |
| Contract it owns | `catalogue/1` |
| Track | Platform. Review required for all medical content |

## Purpose

One place that holds the medical content of the simulated world, separate from any pathway:
which conditions exist and how common they are among people who present, which hidden variables
a patient has and how they depend on the condition, and which tests exist in real healthcare,
what each reveals and how accurately. Every number carries a source or the word `assumption`,
and a grade. The catalogue is data: people who are not programmers must be able to read and
correct it.

## What exists today

- `scenarios/finland_lung.yaml`: seven conditions with prevalence among presenters (two lung
  cancer presentations, pneumonia, COPD exacerbation, benign nodule, other benign,
  self-limiting), one hidden attribute (tumour location), about ten real tests and about ten
  process steps modelled as tests, each with a `source` and a `note`.
- `params/test_accuracy.yaml`: sourced accuracy for chest X-ray, low-dose CT, PET-CT,
  bronchoscopy, needle biopsy and others; several entries are marked `assumption` (diagnostic CT
  sensitivity and specificity, for example).
- `params/sources.yaml`: 21 sources with citation and what each supports.
- `docs/parameters.md`: the human-readable table.

The catalogue gathers these, adds what the vision needs (symptoms, findings, bloodwork, typed
test outputs), and removes process steps from the list of tests.

## Design

### Files

```
catalogue/
  README.md                 the format (catalogue/1), written for clinicians and agents
  lung-primary-care/        one catalogue = one clinical setting
    catalogue.yaml          id, version, title, scope statement, population references
    conditions.yaml         primary conditions
    variables.yaml          hidden variables (symptoms, signs, true values, imaging truth)
    tests.yaml              tests: what they reveal, how accurately, how long, what they cost
    populations/*.yaml      who presents: background distributions
    behaviour.yaml          patient behaviour: what is reported, who comes back
    constraints.yaml        combinations that cannot occur
```

### Entry shapes (illustrative; the spec agent fixes names; numbers below are placeholders, not content)

```yaml
# conditions.yaml
- id: lung_cancer
  label: Lung cancer
  class: cancer                    # cancer | other_illness | healthy
  prevalence: {value: 0.016, by: {smoking.status: {current: 2.1, never: 0.4}}, source: …, grade: B}
  attributes:
    stage:    {values: {I: …, II: …, III: …, IV: …}, source: …}
    location: {values: {central: …, peripheral: …}, source: …}

# variables.yaml
- id: haemoptysis
  label: Coughing up blood
  kind: symptom                    # symptom | sign | lab_true | imaging_true | function_true
  type: binary
  given:                           # distribution per condition, with optional modifiers
    lung_cancer: {p: …, by: {stage: {IV: …}}, source: …, grade: B}
    pneumonia:   {p: …, source: …}
    default:     {p: …, source: assumption}
- id: crp_true
  kind: lab_true
  type: continuous
  unit: mg/L
  given:
    pneumonia: {dist: lognormal, median: …, p90: …, source: …}
    default:   {dist: lognormal, median: …, p90: …, source: …}

# tests.yaml
- id: chest_xray
  label: Chest X-ray
  category: imaging                # history | examination | bloodwork | imaging | endoscopy | tissue | function | molecular
  outputs:
    - id: abnormal
      measures: imaging_true.lung_lesion
      model: {type: binary, sensitivity: {value: …, by: {nodule_size_mm: …}}, specificity: …,
              source: BRADLEY2021, grade: A}
  nondiagnostic: {p: …}
  positive_when: "abnormal"        # interpretation rule for the adapter to the current engine
  timing: {service_days: …, report_days: {dist: lognormal, median: …, p90: …}, source: …}
  resource_kind: xray              # which kind of resource performs it; capacity belongs to the world, not here
  cost_eur: {value: …, source: …}
  invasive: false
  harm: {complication_rate: …, source: …}
  requires: []                     # facts that must be revealed before the test makes sense
```

### Rules of the format

1. **Every leaf number is an object** with `value` (or distribution parameters), `source` (an id
   in `params/sources.yaml`, or `assumption`), optional `grade`, optional `note`, optional `low`
   and `high` for sensitivity analysis.
2. **Grades.** A: systematic review or large study in a comparable population. B: single study or
   a different but related population. C: expert statement, guideline text, or derived from
   another number. `assumption`: chosen by us, with the reasoning in `note`. `llm_draft`:
   proposed by a language model, not yet checked; never shipped as anything else.
3. **Prevalence is among presenters** in the stated setting, not in the general population, and
   the scope statement says so.
4. **Tests describe medicine, not logistics.** Accuracy, turnaround of the report, cost, harm.
   Waiting time for a slot comes from resources in the world document (C3), because that is what
   the optimiser and capacity changes act on.
5. **Process steps are not tests.** Referral letters, triage of referrals, board meetings and
   bookings live in the flowchart as administrative steps. Clinician judgements become decision
   nodes (assumption V4).
6. **History taking and examination are tests**: they reveal symptoms and signs with their own
   sensitivity (patients forget; clinicians do not ask).
7. **Dependencies are explicit and acyclic** (`by:` modifiers). The validator draws the graph.
8. **Accuracy is stated for the population it was measured in**, in `note`; if we apply it to a
   different one, the grade drops by one.

### Scope of the first catalogue: `lung-primary-care`

Adults contacting primary care with chest or general symptoms, where lung cancer is one of
several explanations. The spec agent and the research lane fix the exact lists; the architect's
starting point, to be pruned by what can be sourced:

**Conditions (about 8 to 12).** Lung cancer (with stage, histology group, location);
pneumonia; COPD exacerbation; asthma; heart failure; tuberculosis; benign nodule found
incidentally; reflux or post-infectious cough; anxiety or no disease found; self-limiting
viral illness. Keep the current seven mappable (the two "lung cancer" presentation variants
become one condition whose presentation follows from its symptoms).

**Hidden variables (about 25 to 40).**
- Symptoms: cough over three weeks, haemoptysis, breathlessness, chest pain, weight loss,
  fatigue, fever, hoarseness, repeated chest infections, appetite loss.
- Signs: finger clubbing, abnormal chest sounds, enlarged neck nodes.
- True laboratory values: haemoglobin, platelets, CRP, calcium, alkaline phosphatase, LDH.
- Imaging truth: lung lesion present, size, location, enlarged mediastinal nodes, distant spread,
  consolidation.
- Function: FEV1 as percent of predicted, exercise capacity.
- Tissue truth: malignant or not, histology group, marker status (only if the pathway uses it).

**Tests (about 15 to 20), by category.** These are the real steps of a Finnish and Nordic lung
pathway and of primary care work-up:

| Category | Tests |
|---|---|
| History and examination | structured history (reveals symptoms), physical examination (reveals signs) |
| Bloodwork | basic blood count, CRP, chemistry (calcium, ALP, LDH) |
| Imaging | chest X-ray, CT of the chest with contrast, low-dose CT, PET-CT, brain MRI for staging |
| Function | spirometry, exercise test |
| Endoscopy and tissue | bronchoscopy with biopsy, EBUS needle sampling of nodes, CT-guided needle biopsy, sputum cytology |
| Pathology and molecular | histology report, marker panel |

Already sourced in `params/` and to be carried over unchanged: chest X-ray, low-dose CT, PET-CT,
bronchoscopy by location, needle biopsy, and the timing numbers from the Norwegian study and the
Pirkanmaa pathway description. Everything else needs the research lane.

### How content gets in (workflow)

1. **Research lane** (agent with web access): for each entry, find the best available source,
   record it in `params/sources.yaml`, fill the entry with value, grade and note, and list what
   could not be sourced. Symptom frequencies by condition are the hardest part: primary-care
   symptom studies for lung cancer exist (positive predictive values of symptoms in primary
   care); for the look-alike conditions use guideline or review figures and grade them honestly.
2. **Drafting with a language model** is allowed to produce first versions of symptom profiles
   and look-alike conditions, marked `llm_draft`. The research lane then replaces or confirms
   each one. The ledger reports how many entries are still `llm_draft` or `assumption`.
3. **Validation** by C1's loader: format, ranges, acyclic dependencies, every number sourced or
   marked.
4. **Calibration check** by C1's cohort checks: derived quantities that are published (for
   example the positive predictive value of an abnormal chest X-ray among symptomatic adults)
   come out near their published values. If not, an `assumption` entry is adjusted and the
   adjustment is recorded, never a sourced one.
5. **Clinical review**: a human with medical knowledge reads the rendered catalogue
   (`python -m patient_engine catalogue --render`) before it is called anything but a draft. The
   UI shows "draft, not clinically reviewed" until then. For the hackathon this stays a draft and
   the pitch says so.

## Sub-wholes (for the spec agent)

| # | Sub-whole | Outcome | Notes |
|---|---|---|---|
| K1 | **Format `catalogue/1`** | `catalogue/README.md`, a JSON Schema or equivalent, two tiny example catalogues for tests | Agree with C1's P2 (the loader). Contract-first |
| K2 | **Migration of existing content** | The current Finnish and Norwegian scenario content expressed in the format, with sources carried over | Enables C1's equivalence check (P5). No new numbers |
| K3 | **Conditions and prevalence** for `lung-primary-care` | `conditions.yaml`, `populations/` | Research lane. Review required |
| K4 | **Hidden variables** | `variables.yaml` with a distribution per condition | Research lane; the largest piece; can be split by variable kind |
| K5 | **Tests** | `tests.yaml`: outputs, accuracy, timing, cost, harm | Research lane; carry over sourced entries first |
| K6 | **Behaviour and constraints** | `behaviour.yaml`, `constraints.yaml` | What patients report and when they come back (C1 question Q2) |
| K7 | **Rendered catalogue and ledger** | A readable Markdown or HTML rendering; counts of sourced, assumed and draft entries | With C7 (`params/ledger.py`) |

K1 and K2 first. K3 to K6 in parallel by different research lanes once K1 is fixed (they own
different files). K7 last.

## Open questions

| # | Question | Lean | Who |
|---|---|---|---|
| Q1 | How far to go beyond lung in the first catalogue | Stay with lung-symptom presenters; prove the format with one tiny second catalogue in tests only | Tuomas |
| Q2 | Finnish prevalence among presenters is poorly published | Use the existing calibrated values, graded as they are, and show the range | C7 |
| Q3 | Are costs in scope | Yes as reported quantities with sources; not as an objective until Tuomas says so (assumption V5) | Tuomas |
| Q4 | Who gives the clinical read-through | Ask the challenge mentors (AstraZeneca) or a clinician contact; until then "draft" | Tuomas |

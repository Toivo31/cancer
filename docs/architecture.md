# Architecture and interface contract

This file is the contract between the parallel work tracks. If you change an
interface, update this file in the same commit.

```
scenarios/*.yaml ──► pathway_sim.load_scenario ──► Scenario
                                                   │
patients = generate_patients(scenario, n, seed) ◄──┘
run = simulate(scenario, flowchart, patients, policy, seed) ──► RunLog (JSON)
metrics = compute_metrics(run) ──► dict (JSON)
optimiser.propose(scenario, flowchart, run) ──► [Edit]
optimiser.search(...) ──► accepted edits, before/after metrics on train + held-out
demo/export.py ──► demo/data/demo_bundle.json ──► demo/index.html
build_flow(run log) ──► flow document (docs/platform/flow-format.md); demo/export_flow.py ──► demo/data/flow_bundle.js ──► demo/flow.html
```

## Packages

| Path | Owner track | What |
|---|---|---|
| `pathway_sim/` | core | event engine, scenario loader, patient generator, policies, metrics, CLI |
| `optimiser/` | optimiser | revealed-information yield estimates, flowchart edits, accept-by-rerun search |
| `decision_model/` | decision model | Jev-type correction model + dot-product baseline; implements `Policy` |
| `scenarios/` | core + params | scenario YAML (`stokstad_observed`, `stokstad_optimal`, `finland_lung`) |
| `params/` | params | sourced parameter tables (`sources.yaml`, `*.yaml`), each number traceable |
| `demo/` | demo | static dashboard `index.html` + `data/demo_bundle.json`; flowchart simulation page `flow.html` (+ `flow.js`, `flow.css`, `data/flow_bundle.js` from `export_flow.py`; `pathway_sim/flow.py` builds the data) |
| `docs/pitch/` | pitch | evidence brief, equity framing, video script, deck outline |
| `technique_classifier/` | separate deliverable | **do not modify** |

## Time

Time is in **calendar days** (float) from the patient's clock start. Each
scenario names its clock start (`clock_start: referral_received` for Stokstad,
`first_contact` for Finland). Day 0 of the simulation is a Monday; `day % 7 in
{5, 6}` are weekend days (used only by `batch` resources and `server` resources
with `weekdays_only: true`).

## Scenario YAML

```yaml
id: finland_lung
description: ...
clock_start: first_contact          # or referral_received
target_days: 42                     # share-within-target threshold
arrivals: {rate_per_day: 20}        # Poisson arrivals; omit for a single cohort at t=0..spread_days
conditions:                          # hidden truth; prevalence sums to 1
  - {id: lung_cancer, cancer: true, prevalence: 0.03, source: SRC_ID}
  - {id: pneumonia, cancer: false, prevalence: 0.20, source: SRC_ID}
  - {id: benign, cancer: false, prevalence: 0.77, source: assumption}
groups:                              # presentation groups, used for equity split
  - {id: site_specific, share_by_condition: {lung_cancer: 0.6, pneumonia: 0.5, benign: 0.3}}
  - {id: non_specific}               # remainder
resources:
  ct:      {type: server, capacity_per_day: 8, weekdays_only: true, source: ...}
  pet_ct:  {type: delay, wait: {dist: lognormal, median: 20.5, p90: 35}, source: STOKSTAD2019}
  mdt:     {type: batch, weekdays: [2], cutoff_days: 1}     # weekly tumour board on Wednesday
  gp:      {type: server, capacity_per_day: 30}
tests:                               # what a step reveals
  ct_chest:
    resource: ct
    service_days: {dist: fixed, value: 0.1}
    report_days: {dist: lognormal, median: 2, p90: 5}      # turnaround after service
    p_positive: {lung_cancer: 0.95, pneumonia: 0.4, default: 0.05}
    p_nondiagnostic: 0.0
    invasive: false
    cost_eur: 250
    stage: diagnosis                 # one of detection | referral | diagnosis | treatment_start
    source: SRC_ID
flowcharts:
  baseline: { ... see below ... }
```

Distributions (`pathway_sim/dists.py`): `fixed{value}`, `lognormal{median,p90}`,
`uniform{low,high}`, `empirical{values}`. All sampling goes through
pre-drawn uniforms per (patient, node, attempt) so reruns of the same
patients use common random numbers.

## Flowchart

A flowchart is a DAG of nodes with prerequisites and guards. This expresses
sequence, branching and **parallel** steps (needed for the Stokstad optimal
pathway, where PET-CT and the exercise test are ordered together).

```yaml
flowcharts:
  baseline:
    nodes:
      - {id: gp_visit, test: gp_assessment}                       # no `after` -> starts at clock start
      - {id: cxr, test: chest_xray, after: [gp_visit]}
      - {id: discharge_cxr, kind: exit, outcome: discharged, after: [cxr], when: "not cxr"}
      - {id: referral, test: specialist_referral, after: [cxr], when: "cxr"}
      - {id: sample, kind: choice, after: [referral], options: [bronch, ttnb]}
      - {id: bronch, test: bronchoscopy, retry: {max: 1, on: nondiagnostic, fallback: ttnb}}
      - {id: ttnb, test: ttnb}
      - {id: diagnosis, kind: milestone, milestone: diagnosis, after_any: [bronch, ttnb], when: "bronch or ttnb"}
      - {id: treat, kind: exit, outcome: treatment, test: surgery, after: [diagnosis, mdt]}
```

Node fields:
- `id` (unique), `test` (id in `tests`, optional for pure logic nodes)
- `kind`: `step` (default) | `choice` | `milestone` | `exit`
- `after`: all of these must be done (if one is skipped, this node is skipped too);
  `after_any`: at least one must be done (skipped when all are skipped);
  `after_optional`: wait for these only if they run (done or skipped both satisfy it)
- `when`: guard expression over revealed information: node ids (value `True` positive,
  `False` negative, `None` not revealed / nondiagnostic), revealed attributes, `group`,
  `age`, `t`. Evaluated by the safe evaluator `pathway_sim/expr.py` (no `eval`): `and`, `or`, `not`,
  parentheses, `==  !=  <  <=  >  >=`, `is` / `is not` with `True`, `False` or `None`, `in` / `not in`
  with a list of constants, and text, number, `True`, `False`, `None` constants. Calls, attributes,
  indexing, arithmetic, lambdas, comprehensions and names starting with `_` are rejected when the
  scenario loads. Unknown names are rejected when the scenario loads. A node whose prerequisites are met but whose guard is False is **skipped**.
- `availability` on a choice node: `{option: {p_available, weekdays}}` restricts the offer.
- `test_overrides` / `resource_overrides` on a flowchart change a test or resource for that
  flowchart only (e.g. a faster PET-CT scanner).
- `choice` nodes: the `Policy` picks one of `options`; the others are skipped.
- `exit` nodes end the pathway: `outcome` in `treatment | discharged | diagnosis_only`.
  The first exit reached ends the patient.
- `milestone: diagnosis` marks time to diagnosis; `exit outcome: treatment` marks time to treatment.
- `fast_track: true` on a node gives the patient priority in every `server` queue from then on.
- `book_in_parallel: [node]` (optional): reserves a slot at that node's resource
  as soon as this node starts (treatment slot reservation while sampling runs).

A patient whose cancer truth is True but who reaches `discharged` is a **missed cancer**.

## Validation

`pathway_sim/validate.py` returns every problem at once as `{"ok", "problems": [...]}`; the codes, severities
and the problem object (`code, severity, message, flowchart, node, edge, field, hint`) are defined in
`pathway_sim/problems.py`. `validate_scenario_dict(raw)` checks the world tables and every flowchart;
`validate(world, flowchart_dict)` one flowchart. `deep=False` is the cheap error-only subset that
`scenario.validate_flowchart` wraps (it still raises `ValueError` on the first error: CLI and optimiser
unchanged). Warnings (`unreachable`, `possible_dead_end`, `missing_probabilities`) never block loading.
A wrongly shaped document raises `MalformedDocument` (a `ValueError`).

## Patient card (`pathway_sim.patients.Patient`)

```python
@dataclass
class Patient:
    id: int
    condition: str            # hidden
    cancer: bool              # hidden
    group: str                # presentation group (visible)
    age: int                  # visible
    arrival: float            # day
    results: dict[str, list[bool | None]]   # hidden, per test id, one per attempt (pre-drawn)
    uniforms: np.ndarray      # pre-drawn uniforms for timing (common random numbers)
```
`generate_patients(scenario, n, seed)` is deterministic in `seed`.

## Policy

```python
class Policy(Protocol):
    def choose(self, view: PatientView, options: list[str]) -> dict[str, float]:
        """Probability per option id. The simulator takes the argmax."""
```
`PatientView` holds only revealed information: `group`, `age`, `history`
(list of `(node_id, test_id, result, t)`), and `t_now`. Never the condition.
`RulePolicy` (core) uses per-choice-node rules from YAML (`policy: {sample: {prefer: bronch}}`)
or uniform priority order.

## RunLog JSON

```json
{
  "scenario": "finland_lung", "flowchart": "baseline", "seed": 1, "n_patients": 1000,
  "patients": [
    {"id": 0, "group": "non_specific", "condition": "benign", "cancer": false,
     "arrival": 0.4, "outcome": "discharged", "t_diagnosis": null, "t_treatment": null, "t_exit": 12.3,
     "events": [{"node": "cxr", "test": "chest_xray", "resource": "xray", "stage": "detection",
                 "t_ready": 1.0, "t_start": 3.2, "t_end": 3.3, "t_result": 4.0,
                 "result": false, "attempt": 0}]}
  ],
  "resources": {"ct": {"type": "server", "utilisation": 0.83, "queue": [[0.0, 0], [1.0, 4]]}}
}
```
`t_*` are absolute sim days; per-patient durations are `t - arrival`.
Waiting = `t_start - t_ready`; service = `t_result - t_start`.

## Metrics JSON (`compute_metrics(run, scenario)`)

```json
{
  "n": 1000, "n_cancer": 30,
  "median_days_to_treatment": 46.5, "share_within_target": 0.40,
  "median_days_to_diagnosis": 30.0,
  "missed_cancers": 1, "tests_per_patient": 3.1, "invasive_per_patient": 0.4, "cost_per_patient": 900,
  "median_days_to_exit_noncancer": 9.0,
  "stage_breakdown": {"detection": {"wait": 5.1, "service": 0.5}, "referral": {...}, "diagnosis": {...}, "treatment_start": {...}},
  "node_breakdown": {"pet": {"wait": 18.0, "service": 2.0, "n": 100}},
  "by_group": {"non_specific": {"median_days_to_treatment": 60, "share_within_target": 0.2, "n_cancer": 12}},
  "utilisation": {"ct": 0.83}
}
```
Stage and node breakdowns are **mean days per cancer patient** (waiting vs
service), so they add up to the time to treatment. Same fields for all patients
under `stage_breakdown_all`.

## Demo bundle (`demo/data/demo_bundle.json`)

```json
{
  "generated_at": "...",
  "scenarios": [
    {"id": "stokstad", "title": "Norwegian validation", "target_days": 42,
     "baseline": {"label": "Observed pathway", "metrics": {...}},
     "variants": [{"label": "Faster PET only", "metrics": {...}},
                  {"label": "Optimiser proposal", "metrics": {...}, "changes": ["..."]}],
     "published": {"baseline_share": 0.40, "faster_pet_share": 0.48, "optimal_share": 0.80, "source": "STOKSTAD2019"},
     "flowchart_before": {"nodes": [...]}, "flowchart_after": {"nodes": [...]}}
  ],
  "assumptions": [{"parameter": "...", "value": "...", "source": "...", "status": "sourced|assumption"}]
}
```

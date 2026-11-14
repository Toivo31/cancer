# Spec 01: Flowchart model (document format v1)

Milestones M1, M2, M5. Depends on nothing. Everything else depends on this.

## Purpose

Today one scenario YAML bundles the population, the test catalogue, the resources and several
flowcharts, and edges are implicit in node fields (`after`, `after_any`, `after_optional`,
`options`). A visual editor and an API need (a) separate documents with their own lifetimes and
(b) edges as first-class objects. The engine's internal classes do not change.

## Documents

All JSON, each with `schema_version: 1`. YAML scenarios remain importable.

### World
What the simulation is about; changes rarely. Equals today's scenario minus `flowcharts`.

```json
{
  "schema_version": 1, "id": "finland_lung", "name": "Finnish lung pathway (synthetic)",
  "clock_start": "first_contact", "target_days": 90,
  "arrivals": {"rate_per_day": 44}, "warmup_days": 60, "default_n": 18800,
  "conditions": [{"id": "lung_cancer", "cancer": true, "prevalence": 0.016, "source": "KOO2023"}],
  "groups": [{"id": "site_specific", "share_by_condition": {"lung_cancer": 0.3}}, {"id": "non_specific"}],
  "attributes": {"location": {"values": {"central": 0.3, "peripheral": 0.7}, "source": "assumption"}},
  "resources": {"ct_scanner": {"type": "server", "capacity_per_day": 6, "min_lead_days": 3, "source": "assumption"}},
  "tests": {"ct_chest": {"resource": "ct_scanner", "stage": "diagnosis", "p_positive": {"lung_cancer": 0.95, "default": 0.05},
                         "reveals": ["location"], "invasive": false, "cost_eur": 250, "source": "assumption"}},
  "constraints": {"needs": {"tumour_board": ["pet_ct"]}, "protected": []}
}
```
`constraints` is today's `optimiser:` block (clinical facts the optimiser may not break).

### Flowchart (versioned)

```json
{
  "schema_version": 1, "id": "baseline", "version": 3, "parent_version": 2, "world_id": "finland_lung",
  "name": "Today's pathway",
  "nodes": [
    {"id": "gp_visit", "kind": "step", "label": "GP appointment", "test": "gp_assessment", "ui": {"x": 120, "y": 80}},
    {"id": "sample_method", "kind": "decision", "label": "Choose sampling method", "when": "ct",
     "availability": {"ttnb": {"weekdays": [0, 1, 2]}}},
    {"id": "bronch", "kind": "step", "label": "Bronchoscopy", "test": "bronchoscopy",
     "retry": {"max": 0, "on": "nondiagnostic", "fallback": "ttnb"}},
    {"id": "treat", "kind": "exit", "outcome": "treatment", "label": "Treatment starts"}
  ],
  "edges": [
    {"from": "ct", "to": "sample_method", "type": "required"},
    {"from": "sample_method", "to": "bronch", "type": "option", "index": 0},
    {"from": "sample_method", "to": "ttnb", "type": "option", "index": 1}
  ],
  "decision_policy": {"backend": "stub", "mode": "sample", "points": {}},
  "test_overrides": {}, "resource_overrides": {},
  "edits_from_parent": []
}
```

Node kinds:

| Kind | Meaning | Engine mapping |
|---|---|---|
| `step` | Something happens to the patient (test, visit, booking); has a `test` | `step` with `test` |
| `decision` | JEV (or stub) picks one outgoing option | `choice` |
| `join` | Pure logic: "continue when these are finished" | `step` without `test` |
| `milestone` | Marks time to diagnosis | `milestone` |
| `exit` | Ends the pathway: `treatment`, `discharged`, `diagnosis_only` | `exit` |

Edge types:

| Type | Meaning | Engine mapping |
|---|---|---|
| `required` | target waits for source; if source is skipped, target is skipped | `after` |
| `any` | target needs at least one of its `any` sources | `after_any` |
| `optional` | target waits for source only if it runs | `after_optional` |
| `option` | source is a decision; target is one of its options (`index` gives the order) | `options` |

`ui` holds canvas positions; the engine ignores it. `decision_policy` is specified in spec 02.

### Versions
A flowchart version is immutable once it has been used in a run. Saving in the editor creates
version n+1 with `parent_version` n. The optimiser's output is a new version whose
`edits_from_parent` lists the accepted changes, so a diff view needs no graph comparison.

## Library work (`pathway_sim/documents.py`)

- `scenario_to_documents(scenario) -> (world, [flowchart])` and `load_yaml_as_documents(path)`.
- `documents_to_scenario(world, flowcharts) -> Scenario` (engine objects).
- `flowchart_to_document(fc)` and `document_to_flowchart(doc)`: pure, lossless both ways.
- Acceptance: for every shipped scenario and flowchart, YAML → documents → engine gives
  byte-identical metrics to loading the YAML directly (same patients, same seed).

## Validation (`pathway_sim/validate.py`)

Today validation raises on the first problem. The editor needs all problems at once, each tied to
a node or edge.

```json
{"ok": false, "problems": [
  {"severity": "error", "code": "guard_unknown_name", "node": "referral", "message": "The condition reads 'cxrr', which is not a step or attribute", "hint": "Did you mean 'cxr'?"},
  {"severity": "warning", "code": "unreachable", "node": "ebus", "message": "No patient can reach this step"}
]}
```

Codes: `unknown_reference`, `duplicate_id`, `cycle`, `no_exit`, `decision_needs_two_options`,
`option_of_two_decisions`, `unknown_test`, `unknown_resource`, `guard_syntax`, `guard_unknown_name`,
`information_not_available` (a condition reads a result that is not upstream; reuse
`optimiser.edits.information_ok`), `needs_violated` (world constraints), `policy_unknown_option`,
and warnings `unreachable`, `possible_dead_end` (a patient can finish every started step without
reaching an exit; today this shows up only at run time as `stuck`), `missing_probabilities`.

`validate_scenario` keeps raising for the CLI by wrapping the new function.

## Safe conditions (required before hosting)

Guards and policy rules are Python expressions evaluated with `eval` (`pathway_sim/engine.py`,
`pathway_sim/policy.py`). With user-supplied flowcharts that is a code-execution hole even with
empty builtins.

- New `pathway_sim/expr.py`: parse with `ast`, accept only `BoolOp`, `UnaryOp(Not)`, `Compare`
  (`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`), `Name`, `Constant`, tuples of constants; evaluate with a
  small interpreter. Unknown names evaluate to `None` as today.
- Replace every `eval` and `compile` of scenario text in `pathway_sim`, `optimiser`, `jev`.
- Acceptance: all existing scenarios give identical results; a test feeds known sandbox-escape
  strings and each is rejected at load.

The editor stores a condition both as the expression and as a structured form the guard builder can
edit: `{"all": [{"step": "cxr", "is": "positive"}, {"attribute": "location", "equals": "central"}]}`.
The expression is generated from the structure; hand-written expressions stay possible in an
"advanced" field.

## Build order

1. `expr.py` and swap out `eval` (M1-4).
2. `documents.py` with round-trip tests (M2-1).
3. `validate.py` with the problem list (M2-2).
4. `decision` as the document name for `choice` nodes; engine accepts both.

## Out of scope for v1

Loops (a step that can run again), sub-flowcharts, time limits on steps (the plan's "time limits"
are represented by `target_days` only), several cancers in one world.

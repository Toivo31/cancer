# WP-C1-1: Card, library, cohort and catalogue contracts

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P1, P2) and C2 `components/C2-clinical-catalogue.md` (K1) |
| Status | built on branch `w2/pe-contracts`; awaiting integration and the I1 review |
| Size | M |
| Needs | – |
| Provides | `card/1`, `library/1` (manifest only), `cohort/1` (spec only), `catalogue/1` with loader and validator |
| Owned paths | `patient_engine/__init__.py`, `patient_engine/card.py`, `patient_engine/catalogue.py`, `patient_engine/schema.py`, `catalogue/README.md`, `catalogue/_examples/`, `tests/test_pe_contract*.py`, `tests/test_pe_catalogue*.py`, `tests/fixtures/patient_engine/` |
| May create | the files above; `patient_engine/problems.py` if a shared problem type is useful |
| Review required | yes: invariant I1 (hidden and revealed are different types) |
| Track | submission (Sunday slice item 1 and the format half of item 2) |

## Outcome

`python -c "from patient_engine.catalogue import load_catalogue; c = load_catalogue('catalogue/_examples/tiny'); print(c.version_hash, len(c.tests))"`
loads and validates a small example catalogue. `patient_engine.card` defines the card types; a
JSON Schema for a card is generated from any loaded catalogue (`card_schema(catalogue)`), and an
example card in `tests/fixtures/patient_engine/card_example.json` validates against it. Every
later package (generator, authors, validator, audit, store, adapter) builds on these names.

## Why

Six packages in waves 2b and 2c depend on these names. Fix them once, small and clear, so those
packages can be written in parallel. This is the only package of wave 2 that makes design calls
others must live with: keep the surface minimal and write down every decision.

## Interfaces

**Provides**

- `patient_engine.catalogue`: `load_catalogue(path) -> Catalogue` (raises `CatalogueError`
  carrying a list of problems), `validate_catalogue(raw) -> list[Problem]`, `Catalogue` with
  `conditions`, `variables`, `tests`, `cooccurrence` (may be empty), `version_hash` (stable hash
  of the normalised content), `sources_used()`. Numbers are leaf objects `{value | dist params,
  source, grade?, note?, low?, high?}` as in C2 "Rules of the format".
- `patient_engine.card`: frozen dataclasses (or pydantic if already a dependency; check
  `requirements.txt`, prefer the standard library) for `Card` with sections from C1 "The card":
  `background`, `presenting` (per state), `hidden` (`conditions`, `findings` with `caused_by`),
  `states`, `observations` (state -> test id -> list of attempts -> output values + `report`
  text + `status` in {ok, non_diagnostic}), `notes` (each with `mentions`: the finding or
  observation keys it may reveal), `provenance`. **Revealed-side types** (`PublicView`,
  `RevealedObservation`) are separate classes with no field that can hold hidden data. Plus
  `card_from_json`, `card_to_json`, `card_schema(catalogue) -> dict` (JSON Schema, draft 2020-12).
- `library/1` manifest shape (id = content hash, catalogue id and hash, generator, model, prompt
  versions, error_source, card count by condition, created) and `cohort/1` spec shape
  (`library_id, prevalence, n, seed`) as typed dicts or dataclasses only; storage is WP-C1-6.
- `catalogue/README.md`: the format for clinicians and agents, with every field explained.

**Consumes**: `params/sources.yaml` (source ids must resolve), `pathway_sim/dists.py`
(`sample`, `validate` for distribution specs: reuse its distribution vocabulary so the
catalogue and the simulator speak one language).

## Acceptance (all machine-checkable)

- [x] `load_catalogue('catalogue/_examples/tiny')` succeeds; the tiny catalogue has at least 3
      conditions (one cancer with a `stage` attribute, one other illness, healthy), 5 variables
      (binary symptom, continuous lab value, imaging truth with size), 4 tests (history, blood
      count, chest X-ray, CT), one cooccurrence pair.
- [x] A second example `catalogue/_examples/broken/` (or inline fixtures) produces specific
      problems: unknown source id, number without source, `by:` cycle, test output measuring an
      unknown variable, probability outside 0..1, unknown condition in `given`. One test per problem.
- [x] `version_hash` is equal for two loads and for a reordered but equal file; differs after
      changing one number (test).
- [x] The example card validates against `card_schema(tiny)`; removing a required field or adding
      a test id the catalogue does not have makes it fail (tests).
- [x] I1: a test asserts `PublicView` and `RevealedObservation` have no attribute named in the
      hidden section (`hidden`, `conditions`, `findings`, `caused_by`), so adding one fails the test.
- [x] `card_to_json(card_from_json(x)) == x` for the example (round trip).
- [x] Fast: all tests of this package run in under 10 seconds; `python -m pytest -q tests/test_pe_*` green.

## Out of scope

Generating cards, the reveal handle's behaviour, storage of libraries, the real lung catalogue
content (WP-C2-1), the LLM client (WP-C1-2), anything in `pathway_sim/`.

## Things to look at and weigh

- `scenarios/finland_lung.yaml` (conditions, tests with `source` and `note`) and
  `params/test_accuracy.yaml`: WP-C2-1 will migrate these into your format; make sure it can
  express them (sensitivity by tumour location, process steps that are *not* tests).
- `pathway_sim/patients.py` (`p_positive`, keyed draws) and `pathway_sim/dists.py`: the card must
  give the adapter (WP-C1-8) a boolean per test via the catalogue's `positive_when` rule; keep
  that rule a small expression evaluated by `pathway_sim/expr.py` (safe evaluator, no `eval`, I7).
- Observations keyed by state even though the Sunday slice uses one state (`all_active`); D40
  needs more later. Do not build state transitions now.
- Size: 2 000 cards x 20 tests x 3 states x 3 attempts must stay loadable. Keep the per-observation
  shape small (output values dict, status, report).
- Test outputs are typed: `binary`, `continuous` (unit), `categorical` (values), `size_mm`. The
  JSON Schema for observations is generated per test from these.

## Decisions for the builder (leans)

- Standard-library dataclasses; JSON Schema produced as a plain dict; use `jsonschema` only if it
  is already installed (check), else write a small validator for the subset you generate and say so.
- Names: snake_case ids; `card/1` field names as in the C1 example unless you find a reason.
- YAML files per C2 "Files" (`catalogue.yaml`, `conditions.yaml`, `variables.yaml`, `tests.yaml`,
  `cooccurrence.yaml` optional); the others in that list are optional and may be absent.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [x] | C1-1-T1 | **Publish the contract early**: `card.py` types, the example card JSON, the tiny catalogue YAML, `catalogue/README.md` first draft. Commit, then post an FYI on the channel with the commit and the type names | S | – | commit exists within ~40 min of start; FYI posted |
| [x] | C1-1-T2 | Catalogue loader: parse YAML, leaf-number objects, resolve sources against `params/sources.yaml`, build typed `Catalogue` | M | T1 | tiny loads; unknown source is a problem (test) |
| [x] | C1-1-T3 | Catalogue validator: ranges, `by:` dependency graph acyclic, references resolve, `positive_when` parses with `pathway_sim.expr` | M | T2 | one test per problem kind listed above |
| [x] | C1-1-T4 | `version_hash` over normalised content | S | T2 | hash tests above |
| [x] | C1-1-T5 | `card_schema(catalogue)` and card (de)serialisation; validate the example card | M | T1, T2 | schema tests and round trip |
| [x] | C1-1-T6 | I1 type-separation test; `library/1` manifest and `cohort/1` spec shapes with examples | S | T1 | I1 test fails if a hidden field is added to a public type |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| Standard-library dataclasses, frozen; mappings inside are plain dicts | No new dependency; dicts keep `card_to_json(card_from_json(x)) == x` exact and cheap | Swap to `MappingProxyType` in `card_from_json` if mutation becomes a problem |
| Own JSON Schema validator for the generated subset (`patient_engine/schema.py`, `schema_problems`); `jsonschema` (installed here, not in `requirements.txt`) only cross-checks in tests | Root `requirements.txt` is integrator-only; the engine must run without it | Use `jsonschema` in `schema_problems` once the integrator adds it to requirements |
| Every card section is keyed by state: `presenting[state]`, `hidden.findings[state][var]`, `observations[state][test][attempt]`; `states[0]` must be `all_active` | One shape for D40 later; the Sunday slice uses one state | Allowed state names: `Catalogue.states()` (`all_active`, `<other_illness>_resolved`, `all_resolved`) |
| Attempt = `{status: ok|non_diagnostic, values: {output: value}, report}`; `values` is `{}` when non-diagnostic; an output with `only_if` may be `null` | Output ids cannot collide with `report`/`status`; small and typed | – |
| Non-diagnostic attempts are allowed only for tests with a `nondiagnostic` rate (schema) | Strict schema catches model drift | Give the test a `nondiagnostic` rate |
| Every catalogue test and every variable is required on a complete card; attempts 1..`max_attempts` (catalogue default 3, per-test override) | D39: the model writes every test; the reveal handle never meets a hole | Reveal handle (WP-C1-6) decides what an attempt beyond the stored ones returns |
| `hidden.error_plan` (optional, `null` in `free` mode): per state, test, attempt a `status` and an outcome per output from `correct, miss, false_alarm, wrong` | Lets the validator (WP-C1-4) and audit (WP-C1-7) check guided cards against the plan | Extend `OUTCOMES` in `card.py` |
| Notes carry `kind`, `state`, `text`, `mentions`; mention keys are a variable id, a test id or `test.output` | Variable ids, test ids and background/attribute names are one namespace (validator `ambiguous_name`), so a key means one thing | – |
| Revealed side = `PublicView`, `RevealedObservation`, `RevealedNote`, `Presenting`; `HIDDEN_FIELD_NAMES` = hidden, conditions, findings, caused_by, error_plan, truth; the I1 test walks type hints of `PUBLIC_TYPES` | I1 by type separation; `RevealedNote` has no `mentions` (the list itself names hidden facts) | Adding a public type: add it to `PUBLIC_TYPES` |
| Background on a card is flat (`smoking_status`, `pack_years`), declared in `catalogue.yaml` `background:` (type, unit, values, range) | The card schema needs typed background fields; populations/ (distributions) is later | Add fields in the catalogue |
| `provenance`: library, catalogue_id (const in schema), catalogue_hash (any text in schema), generator (`reference`/`llm`), model, prompts {role: version}, error_source, validation | The schema should not reject cards when a catalogue note changes; the library manifest pins the hash | Make `catalogue_hash` const if strict pinning is wanted |
| Leaf objects: `value` (any single number), `p` (only in `given` of a binary variable), `dist` + params (the `pathway_sim/dists.py` vocabulary), `values` (categorical); `source` required (`params/sources.yaml` id or `assumption`); `grade` in A, B, C, assumption, llm_draft; `low`/`high` are sensitivity bounds except in `dist: uniform` where they are the distribution's | Follows C2 "Rules of the format"; reuses the simulator's distribution language | – |
| `by:` replaces (does not multiply); a level is a number or a partial mapping of the leaf's keys, may nest its own `by`; keys read `condition`, an attribute, a variable or a background field; numeric levels are bands `..a`, `a..b`, `b..` (no overlap) | Matches the scenario's `p_positive {by: location}`; nesting expresses "by location, then size" (RIVERA2013 bronchoscopy) | Add a `times:` multiplier form later if needed |
| Every test output `measures` one variable of the same type; per-condition accuracy is `by: {condition: ...}` | Keeps one truth per output for the audit; migration of per-condition `p_positive` works through `specificity.by.condition` | – |
| Dependency graph nodes: condition, attributes, variables; edges from `by:` and `only_if`; the primary condition implicitly decides attributes and variables, so a prevalence that reads a variable is a cycle | Acyclic by construction, and gives `Catalogue.generation_order(condition)` | – |
| Structural numbers (`max_attempts`, `range`, `version`) are plain numbers, not sourced | They describe the format, not the world | – |
| `version_hash` = SHA-256 hex over all files read: list entries with an `id` sorted by id, co-occurrence pairs sorted, keys sorted, numbers as floats, bool keys as `true`/`false`; notes and sources count | "reordered but equal" must hash equal; any content change must not | – |
| `sources_used()` returns `{source id or assumption: count}` including sources given inside `by:` levels | Counts feed the ledger (C2 K7) | – |
| Problems mirror `pathway_sim/problems.py` (`severity, code, message, hint`) plus `file` and `path`; codes in `patient_engine/problems.py` `CODES`; warnings (`unknown_field`, `prevalence_sum`, `no_positive_when`) never block loading | One problem list shape for the service and the editor | Later packages add codes to `CODES` |
| `positive_when` optional (warning) and evaluated by `pathway_sim.expr` over the test's output ids (`Test.is_positive(values)`) | History-only tests may not need a yes/no; no eval (I7) | – |
| `cooccurrence.yaml` entries: `primary`, `coexisting` (must be `other_illness`), `share` (value leaf); shares of one primary at most 1 | At most one co-existing illness (C1 Q6 lean) | – |
| `requires` (on a test) lists test ids or `test.output` keys, checked to exist | C2 shape | – |
| `Test` dataclass has `__test__ = False` | pytest would otherwise try to collect it where imported | – |

## Report (builder fills in at the end)

**What was built** (branch `w2/pe-contracts`, commits from `ab15530`; contract tag `contract/pe-card/1` = `ab15530`):

| File | Contents |
|---|---|
| `patient_engine/card.py` | `card/1` types, JSON round trip, `library/1` and `cohort/1` shapes, `card_schema`, `card_schema_problems` |
| `patient_engine/catalogue.py` | `catalogue/1` loader, validator, version hash, typed catalogue |
| `patient_engine/schema.py` | card JSON Schema generator (draft 2020-12) and a validator for the subset it generates |
| `patient_engine/problems.py` | `Problem` shape and codes |
| `patient_engine/__init__.py` | docstring only (no imports); later packages add one line each |
| `catalogue/README.md` | the format for clinicians and agents |
| `catalogue/_examples/tiny/` | 3 conditions (cancer with stage and location, pneumonia, healthy), 9 variables, 4 tests, 1 co-occurrence pair |
| `catalogue/_examples/broken/` | one mistake per required problem kind |
| `tests/fixtures/patient_engine/` | `card_example.json`, `library_manifest_example.json`, `cohort_spec_example.json` |
| `tests/test_pe_contract.py`, `tests/test_pe_contract_schema.py`, `tests/test_pe_catalogue.py` | 82 tests, about 2 s |

**Public API**

- `patient_engine.catalogue`: `load_catalogue(path, sources=None) -> Catalogue` (raises `CatalogueError` with `.problems`);
  `read_catalogue(path) -> (raw, problems)`; `validate_catalogue(raw, sources=None) -> list[Problem]`;
  `build_catalogue(raw, sources=None, path=None) -> Catalogue`; `version_hash(raw) -> str`.
  `Catalogue` fields `id, version, title, status, scope, max_attempts, background, conditions, variables, tests,
  cooccurrence, version_hash, problems` (warnings); methods `states()`, `leaves()`, `sources_used()`,
  `cooccurring(primary)`, `generation_order(condition)`. `Condition(id, label, cls, prevalence, attributes)`,
  `Variable(id, label, kind, type, given, unit, values, range, only_if)` with `given_for(condition)`,
  `Test(id, label, category, outputs, max_attempts, positive_when, nondiagnostic, timing, resource_kind, cost_eur,
  invasive, harm, requires)` with `output(id)`, `output_ids`, `is_positive(values)`,
  `TestOutput(id, type, measures, unit, values, only_if, sensitivity, specificity, accuracy, error_sd)`,
  `Cooccurrence(primary, coexisting, share)`, `BackgroundField`, `Leaf(kind, params, source, grade, note, low, high, by)`
  with `resolve(facts)` (float, dist spec for `pathway_sim.dists.sample`, or `{level: share}`).
- `patient_engine.card`: `Card` (hidden side) with `Hidden(conditions, findings, error_plan)`, `ConditionTruth`,
  `Finding(value, caused_by)`, `PlannedAttempt`, `Attempt(status, values, report)`, `Note(id, kind, state, text, mentions)`,
  `Provenance`; revealed side `PublicView`, `RevealedObservation`, `RevealedNote`, `Presenting` (`PUBLIC_TYPES`,
  `HIDDEN_FIELD_NAMES`); `card_to_json`, `card_from_json`, `card_schema(catalogue)`, `card_schema_problems(data, catalogue)`;
  `LibraryManifest` and `CohortSpec` with `to_json`/`from_json`; constants `CARD_FORMAT`, `INITIAL_STATE`, `STATUSES`,
  `OUTCOMES`, `NOTE_KINDS`, `GENERATORS`, `ERROR_SOURCES`.
- `patient_engine.schema`: `card_schema(catalogue) -> dict`, `schema_problems(instance, schema) -> list[Problem]`.
- `patient_engine.problems`: `Problem(code, message, path, file, hint, severity)`, `CODES`, `errors()`, `report()`.

**How later packages use it**

- Skeleton / reference generator (WP-C1-3): draw the primary condition from `prevalence.resolve(background)`, then walk
  `catalogue.generation_order(condition)`, resolving each attribute's and variable's leaf with
  `given_for(condition).resolve(facts)` where `facts = {"condition": ..., **background, **attributes, **variables so far}`;
  `only_if` false -> `None`. Test outputs: `sensitivity`/`specificity`/`accuracy`/`error_sd` `.resolve(facts)`;
  `nondiagnostic.resolve(facts)` per attempt; `test.max_attempts` attempts. Build the JSON dict and check it with
  `card_schema_problems`.
- Authors (WP-C1-5): send `card_schema(catalogue)` (or its sub-schemas under `$defs`) as the structured-output schema.
- Validator (WP-C1-4): run `card_schema_problems` first, then semantic rules; add its codes to `problems.CODES`.
- Store / reveal (WP-C1-6): cards are `card_to_json` dicts (one per JSON line); `LibraryManifest`, `CohortSpec` are the
  manifest and spec; the reveal handle returns only `PublicView`/`RevealedObservation`/`RevealedNote`.
- Audit (WP-C1-7): reference values come from `catalogue.leaves()` and the typed objects; `error_plan` gives guided intent.
- Adapter (WP-C1-8): `test.is_positive(attempt.values)` for an `ok` attempt, `None` for non-diagnostic.
- Catalogue content (WP-C2-1): follow `catalogue/README.md`; check with `load_catalogue`.

**Not done / limits**

- No semantic card checks (states equal the keys of `presenting`/`findings`/`observations`, exactly one primary,
  findings consistent with conditions): WP-C1-4.
- `populations/`, `behaviour.yaml`, `treatments.yaml`, `constraints.yaml` are not read yet.
- Size: a full card (20 tests x 3 attempts x 3 states) is roughly 50 kB of JSON, mostly report text; 2 000 cards
  about 100 MB raw before gzip, and our schema check takes about 4-5 ms per full card (measured 0.3 ms on the tiny card).
  The compact array form for the simulator (WP-C1-6) should drop report texts.
- `jsonschema` is installed here but not in `requirements.txt` (integrator-only file); the engine does not need it.
- The shipped `params/test_accuracy.yaml` and `scenarios/finland_lung.yaml` were read, not migrated (WP-C2-1). Checked
  that their shapes are expressible: per-condition false positives via `specificity.by.condition`, bronchoscopy yield by
  location and size via nested `by:` on `nondiagnostic`/`sensitivity`, process steps and clinician decisions left out.

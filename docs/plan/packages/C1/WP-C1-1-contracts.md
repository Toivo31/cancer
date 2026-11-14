# WP-C1-1: Card, library, cohort and catalogue contracts

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P1, P2) and C2 `components/C2-clinical-catalogue.md` (K1) |
| Status | not started |
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

- [ ] `load_catalogue('catalogue/_examples/tiny')` succeeds; the tiny catalogue has at least 3
      conditions (one cancer with a `stage` attribute, one other illness, healthy), 5 variables
      (binary symptom, continuous lab value, imaging truth with size), 4 tests (history, blood
      count, chest X-ray, CT), one cooccurrence pair.
- [ ] A second example `catalogue/_examples/broken/` (or inline fixtures) produces specific
      problems: unknown source id, number without source, `by:` cycle, test output measuring an
      unknown variable, probability outside 0..1, unknown condition in `given`. One test per problem.
- [ ] `version_hash` is equal for two loads and for a reordered but equal file; differs after
      changing one number (test).
- [ ] The example card validates against `card_schema(tiny)`; removing a required field or adding
      a test id the catalogue does not have makes it fail (tests).
- [ ] I1: a test asserts `PublicView` and `RevealedObservation` have no attribute named in the
      hidden section (`hidden`, `conditions`, `findings`, `caused_by`), so adding one fails the test.
- [ ] `card_to_json(card_from_json(x)) == x` for the example (round trip).
- [ ] Fast: all tests of this package run in under 10 seconds; `python -m pytest -q tests/test_pe_*` green.

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
| [ ] | C1-1-T1 | **Publish the contract early**: `card.py` types, the example card JSON, the tiny catalogue YAML, `catalogue/README.md` first draft. Commit, then post an FYI on the channel with the commit and the type names | S | – | commit exists within ~40 min of start; FYI posted |
| [ ] | C1-1-T2 | Catalogue loader: parse YAML, leaf-number objects, resolve sources against `params/sources.yaml`, build typed `Catalogue` | M | T1 | tiny loads; unknown source is a problem (test) |
| [ ] | C1-1-T3 | Catalogue validator: ranges, `by:` dependency graph acyclic, references resolve, `positive_when` parses with `pathway_sim.expr` | M | T2 | one test per problem kind listed above |
| [ ] | C1-1-T4 | `version_hash` over normalised content | S | T2 | hash tests above |
| [ ] | C1-1-T5 | `card_schema(catalogue)` and card (de)serialisation; validate the example card | M | T1, T2 | schema tests and round trip |
| [ ] | C1-1-T6 | I1 type-separation test; `library/1` manifest and `cohort/1` spec shapes with examples | S | T1 | I1 test fails if a hidden field is added to a public type |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

# WP-C1-6: Library store, cohort assembly, the reveal handle, command line

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P9, P13, "Reveal"); C3 consumes the handle |
| Status | not started |
| Size | M |
| Needs | WP-C1-1 (merged). Test data: the fixture card and the tiny catalogue (WP-C1-3 reference cards optional) |
| Provides | `library/1` storage, `cohort/1` assembly, `RevealHandle`, `python -m patient_engine` |
| Owned paths | `patient_engine/library.py`, `patient_engine/cohort.py`, `patient_engine/reveal.py`, `patient_engine/__main__.py`, `patient_engine/commands/__init__.py`, `patient_engine/commands/library.py`, `tests/test_pe_library*.py`, `tests/test_pe_cohort*.py`, `tests/test_pe_reveal*.py` |
| Review required | yes: invariants I1 (information boundary) and I3 (same patient same result) |
| Track | submission |

## Outcome

- `write_library(cards, catalogue, path, meta) -> LibraryManifest` writes a gzip JSON-lines file of
  cards plus `manifest.json` (id = content hash); `load_library(path)` reads and verifies the hash.
- `draw_cohort(library, spec: CohortSpec) -> Cohort`: n patients drawn from the library to the
  scenario's condition prevalence with keyed random numbers, each with an arrival time; fully
  reproducible without a model. Reports `distinct_cards`.
- `RevealHandle(card)` is the only way the simulation touches a card:
  `visible(episode)` -> `PublicView` (background, presenting for the current state, nothing
  hidden); `reveal(test, attempt, state) -> RevealedObservation`; `notes_visible(revealed_keys)`;
  `truth()` -> hidden conditions, **only callable from scoring code** (name it `truth_for_scoring`).
- `python -m patient_engine <command>`: `__main__.py` discovers `patient_engine/commands/*.py`
  (each exposes `register(subparsers)`), so other packages add commands without editing it. You
  provide `library-info` (manifest and counts), `cohort` (draw and print marginals), `show`
  (print one card: public view by default, `--hidden` for the whole card).

## Acceptance

- [ ] Round trip: write then load gives equal cards and the same hash; editing one byte of the
      file makes `load_library` raise (test).
- [ ] Cohort reproducible: two calls with the same spec give equal cohorts; changing `n` from 1000
      to 2000 keeps the first 1000 patients' cards identical (I2, test).
- [ ] Prevalence: with a library of at least 30 fixture-derived cards per condition (build them in
      the test by copying the fixture with changed ids and primary conditions), a cohort of 20 000
      has condition shares within 0.5 pp of the spec's prevalence (test).
- [ ] I1: a test walks everything `RevealHandle.visible` and `.reveal` return and asserts no
      hidden key or string appears (conditions' ids as keys, `caused_by`, `findings`, `error_plan`);
      the handle's public methods never return a `Card` or a `Hidden`.
- [ ] I3: `reveal(test, attempt, state)` returns equal results on repeated calls and from two handles on
      the same card, and attempt 2 does not depend on whether attempt 1 was asked (test).
- [ ] Notes: a note is returned only when every key in its `mentions` has been revealed (test with
      the example card's two notes).
- [ ] Compact array form: `cohort.to_arrays()` returns what the simulator needs (condition id,
      arrival day, per-test per-attempt booleans from `test.is_positive`) **without report text**, and its size for
      20 000 patients x 20 tests x 3 attempts is under 50 MB (measure and report).
- [ ] CLI: `python -m patient_engine library-info PATH`, `cohort`, `show` run on a library built in a test (subprocess test).
- [ ] Fast: under 20 s.

## Out of scope

Generating cards, validating them (WP-C1-4), states other than `all_active`, return episodes,
the adapter to `pathway_sim.Patient` (WP-C1-8), any service route.

## Things to look at and weigh

- `pathway_sim/patients.py` `_arrival` for how arrival times are drawn today; use the same idea and
  keep keys (`seed`, patient index, "arrival").
- How to draw "to the scenario's prevalence" when the library's own mix differs: stratified draw
  by primary condition, then a card within the stratum by keyed number.
- Reveal handle across episodes (D40) is later; make `state` an explicit argument now so it does not change.
- Do not import anything from `pathway_sim` that pulls in the service.

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [ ] | C1-6-T1 | `write_library`, `load_library`, hash, tamper test | S | round trip and tamper tests |
| [ ] | C1-6-T2 | `draw_cohort` with arrivals; reproducibility and prevalence tests | M | tests pass |
| [ ] | C1-6-T3 | `RevealHandle` with I1 and I3 tests | M | tests pass |
| [ ] | C1-6-T4 | `to_arrays` and size measurement | S | measured and reported |
| [ ] | C1-6-T5 | `__main__` with command discovery; `library-info`, `cohort`, `show` | S | subprocess test |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

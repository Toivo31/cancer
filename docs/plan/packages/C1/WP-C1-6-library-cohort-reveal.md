# WP-C1-6: Library store, cohort assembly, the reveal handle, command line

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md` (P9, P13, "Reveal"); C3 consumes the handle |
| Status | built on branch `w2/libreveal`; awaiting integration and the I1/I3 review |
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

- [x] Round trip: write then load gives equal cards and the same hash; editing one byte of the
      file makes `load_library` raise (test).
- [x] Cohort reproducible: two calls with the same spec give equal cohorts; changing `n` from 1000
      to 2000 keeps the first 1000 patients' cards identical (I2, test).
- [x] Prevalence: with a library of at least 30 fixture-derived cards per condition (build them in
      the test by copying the fixture with changed ids and primary conditions), a cohort of 20 000
      has condition shares within 0.5 pp of the spec's prevalence (test).
- [x] I1: a test walks everything `RevealHandle.visible` and `.reveal` return and asserts no
      hidden key or string appears (conditions' ids as keys, `caused_by`, `findings`, `error_plan`);
      the handle's public methods never return a `Card` or a `Hidden`.
- [x] I3: `reveal(test, attempt, state)` returns equal results on repeated calls and from two handles on
      the same card, and attempt 2 does not depend on whether attempt 1 was asked (test).
- [x] Notes: a note is returned only when every key in its `mentions` has been revealed (test with
      the example card's two notes).
- [x] Compact array form: `cohort.to_arrays()` returns what the simulator needs (condition id,
      arrival day, per-test per-attempt booleans from `test.is_positive`) **without report text**, and its size for
      20 000 patients x 20 tests x 3 attempts is under 50 MB (measure and report).
- [x] CLI: `python -m patient_engine library-info PATH`, `cohort`, `show` run on a library built in a test (subprocess test).
- [x] Fast: under 20 s.

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
| [x] | C1-6-T1 | `write_library`, `load_library`, hash, tamper test | S | round trip and tamper tests |
| [x] | C1-6-T2 | `draw_cohort` with arrivals; reproducibility and prevalence tests | M | tests pass |
| [x] | C1-6-T3 | `RevealHandle` with I1 and I3 tests | M | tests pass |
| [x] | C1-6-T4 | `to_arrays` and size measurement | S | measured and reported |
| [x] | C1-6-T5 | `__main__` with command discovery; `library-info`, `cohort`, `show` | S | subprocess test |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| Library = a directory: `manifest.json` (the `library/1` manifest plus `file: {name, bytes, sha256}`) and `cards.jsonl.gz` (one `card_to_json` dict per line, sorted by card id, canonical JSON, gzip level 6 with `mtime=0`) | Reproducible bytes; `LibraryManifest.from_json` ignores the extra `file` key, so the contract type is unchanged | `library.py` `CARDS_FILE`, `_GZIP_LEVEL` |
| Library id = `L_` + 16 hex of SHA-256 over catalogue id and hash, generator, model, prompt versions, error source and every card line (not `created`, not counts). `load_library` checks the file hash from the manifest, the gzip header, the id, and the card counts | Editing any byte of either file raises; a forger who also fixes the file hash is still caught by the id; the same cards written twice get the same id whatever `created` says | `_library_id` |
| Cards inside a library file keep `provenance.library = None` | The id is computed from the cards, so it cannot be inside them | The library object knows its id |
| `write_library` sorts cards by id, refuses duplicates, a first state other than `all_active`, a wrong `catalogue_id`, a `catalogue_hash` that differs from `catalogue.version_hash` (`check_catalogue_hash=False` to allow) and a schema problem (`validate=False` to skip; semantic checks are WP-C1-4) | A stored library should never hold a card the catalogue cannot have produced | Arguments of `write_library` |
| Libraries are immutable: writing the same id again returns the existing manifest and writes nothing; another library at the same path raises | "immutable, stored set" | `write_library` |
| Cohort condition draw is **stratified in blocks of 1000**, not independent per patient: quota = prevalence x 1000 with an unbiased keyed rounding offset, positions in a keyed random order, a partial last block takes the first positions. The card within the condition is `floor(uniform(seed, i, "card") * m)` | Independent draws give 0.3 pp standard deviation at 25 % and n = 20 000, so the 0.5 pp acceptance would fail one run in ten; blocks give under 0.06 pp, keep each patient a function of `(spec, i)` and keep earlier patients when `n` grows (I2). Measured: largest share error 0.0006 over four seeds | `BLOCK` in `cohort.py` (changing it changes every cohort) |
| Arrival model is an argument of `draw_cohort` (`{"spread_days": s}` default 365, or `{"rate_per_day": r}`), stored on the cohort and in `fingerprint()`; same keys as `pathway_sim.patients` (`"arrival"`, `"interarrival"`) | `CohortSpec` (card.py, not mine) has no arrival field | Add an arrivals field to `cohort/1` later |
| `Cohort` is hidden-side (it knows the card and condition of each patient); the decision layer gets `cohort.handle(i)` only, labelled `P000042` | A repeated card is several patients, and a card id could carry the condition | `Cohort.handle` |
| `RevealHandle` is stateless; the caller keeps the list of `(test, attempt)` it asked and passes it to `visible(revealed=...)` or `revealed_keys(...)` | I3 holds by construction: `reveal` is a pure function of card and arguments | - |
| Method names: `visible(state, revealed)`, `reveal(test, attempt, state)`, `revealed_keys(revealed, state)`, `notes_visible(revealed_keys, state)`, `max_attempts(test, state)`, `tests`, `card_id`, `truth_for_scoring()`. `state` defaults to `all_active` and is explicit; the plan's `episode` argument of `visible` is left out (return episodes are out of scope) | Names fixed early (STATUS on the channel) | Add `episode` to `visible` when D40 is built |
| The handle's default `card_id` is opaque (`C` + 10 hex of a hash of the card id), not the card's id | A generator may name cards `lung_cancer_017`; my own test helper did, and the I1 walk caught it | `RevealHandle(card, public_id=...)` |
| Only `all_active` is served. Any other state raises one and the same `RevealError` for every card | Asking for `pneumonia_resolved` would otherwise tell the caller whether the patient has pneumonia | D40: decide how the state is derived, then relax `_check_state` |
| An attempt beyond the stored ones raises `RevealError` (also negative, non-int, bool); nothing is invented | Resolves the open point in WP-C1-1 ("what an attempt beyond the stored ones returns") | The simulator keeps within `max_attempts(test)` |
| Notes: shown only if `mentions` is non-empty and every mention is revealed. Revealed = variable id in `presenting.reported` of the state, `test` / `test.output` of a revealed `ok` attempt (`test.output` needs a value that is not `None`), or given by the caller. A variable id is **not** revealed by a test that measures it | A noisy or wrong result must not unlock a note that states the truth; a note with no mentions says nothing about what it reveals | `notes_visible`, `revealed_keys` |
| Returned dicts are copies | A caller changing a result must not change the next answer (I3) or the card | - |
| `RevealHandle` uses `__slots__` with the card in `_card`, `repr` shows the label only, and the public surface is pinned exactly by a test | Python cannot hide an attribute; the test makes any new public name a review event | `PUBLIC_SURFACE` in `tests/test_pe_reveal.py` |
| A source tripwire test fails if `truth_for_scoring` appears in a `.py` file outside `patient_engine/`, `tests/`, `docs/` or a file whose name contains `scor` | The decision layer, guards, optimiser and request builder must not call it (I1) | `ALLOWED_PREFIXES` in `tests/test_pe_reveal.py`; a scoring module should be named `*scoring*.py` |
| Compact form `Cohort.to_arrays(catalogue=None, state="all_active") -> CohortArrays`: `results` is one byte per (patient, test, attempt): 0 negative, 1 positive (`test.is_positive` on the attempt's outputs), 2 non-diagnostic, 3 no such attempt, 4 ok but the test has no `positive_when`; plus condition index, arrival day, library card position per patient; computed once per distinct card | Small, no report text, and the same value `is_positive` gives the adapter | `CohortArrays`, codes `NEGATIVE`..`NO_RULE` |
| CLI: discovery in `commands/__init__.py` (`register_all`); modules starting with `_` are skipped, a module that fails to import or register is reported on stderr and the rest keep working; a command sets `set_defaults(func=run)` and returns an exit code | Other packages add commands (`design`) without editing `__main__.py` | - |
| Test card ids in my helper carry the condition (`T:lung_cancer:0003`) on purpose | It makes the I1 tests prove the handle hides ids | `tests/test_pe_library_support.py` |

## Report (builder fills in at the end)

**What was built** (branch `w2/libreveal`, base `c50bbe7`):

| File | Contents |
|---|---|
| `patient_engine/library.py` | `write_library`, `load_library`, `Library`, `LibraryError` |
| `patient_engine/cohort.py` | `draw_cohort`, `Cohort`, `CohortArrays`, `CohortError`, code constants |
| `patient_engine/reveal.py` | `RevealHandle`, `RevealError`, `opaque_id` |
| `patient_engine/__main__.py`, `commands/__init__.py`, `commands/library.py` | `python -m patient_engine`, discovery, `library-info`, `cohort`, `show` |
| `tests/test_pe_library.py`, `test_pe_cohort.py`, `test_pe_reveal.py`, `test_pe_library_cli.py`, `test_pe_library_support.py` | 93 tests, about 4 s |

**Measured size** of the compact form, 20 000 patients x 20 tests x 3 attempts (a 20-test catalogue made from the tiny one; test
`test_size_of_20000_patients_x_20_tests_x_3_attempts`): 1 480 000 bytes (1.48 MB): results 1 200 000 B (one byte per cell),
condition index 40 000 B, arrival days 160 000 B, library card position 80 000 B; gzip of all arrays 188 kB. The plan's ceiling is 50 MB.
Building it takes well under a second (codes are computed once per distinct card).

**What a consumer on the revealed side can get from the handle** (all of it, and nothing else):

- `visible(state, revealed)` -> `PublicView(card_id, state, background, presenting, observations, notes)`; `background` is the card's
  background dict (age, sex, smoking_status, pack_years, region on the tiny catalogue); `presenting.reported` are variable ids the
  patient mentions and `presenting.text` the complaint in words.
- `reveal(test, attempt, state)` -> `RevealedObservation(test, attempt, state, status, values, report)`: `values` has every output of the
  test when `ok` (an output may be `None`), is `{}` when `non_diagnostic`; `report` is the text.
- `revealed_keys(revealed)` / `notes_visible(keys)` -> the keys revealed so far and the `RevealedNote(id, kind, text)` they unlock.
- `tests`, `max_attempts(test)`, `card_id` (opaque label).
- Not available: conditions, attributes (stage, location), findings, `caused_by`, error plan, note `mentions`, the card id, the state names.
  `truth_for_scoring()` returns the conditions for scoring code only.

**How later packages use it**

- Adapter (WP-C1-8): `cohort.to_arrays(catalogue)` for booleans and arrivals; `cohort.card(i)` for hidden attributes the simulator needs for
  its world (hidden side); `cohort.handle(i)` to give to the decision layer.
- Decision layer / JEV request builder: hold a `RevealHandle`, keep the list of `(test, attempt)` asked, call `visible(revealed=list)`.
- Scoring: `handle.truth_for_scoring()` or `cohort.card(i).hidden`, in a file named `*scoring*.py`.
- Generators: `write_library(cards, catalogue, path, meta)` after validation.

**Not done / limits**

- States other than `all_active`, return episodes, any service route, the adapter (WP-C1-8): out of scope.
- `cohort/1` has no arrival field, so arrivals are an argument; C1 "Libraries, cohorts" and the master plan do not say it yet.
- The plan's C1 "Reveal" sketch has `visible(patient, episode)`, `truth(patient)`; the names here follow this package (see decisions). Not edited in the component file (not an owned path).
- `Cohort` holds the library; libraries of a few thousand cards load eagerly (about 50 kB of JSON per full card): not measured here beyond the 90-card test library.
- The handle is not a security boundary: `handle._card` is reachable by code that wants it. The tests and the source tripwire are the control.

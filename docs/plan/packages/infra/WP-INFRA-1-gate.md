# WP-INFRA-1: Fast and slow test tiers, contract tests, one gate command, golden checks

| | |
|---|---|
| Component | cross-cutting; `02-execution-strategy.md` "The gate" and problems A6, A11 |
| Status | done (builder), awaiting merge |
| Size | S–M |
| Needs | – |
| Provides | `scripts/gate.sh` (one command for the integrator), the `slow` marker, `tests/contracts/` |
| Owned paths | `pytest.ini`, `tests/conftest.py`, `tests/slow_tests.txt` (new), `tests/contracts/` (new), `tests/test_golden_*.py`, `scripts/gate.sh` (new), the section "The gate" in `docs/plan/02-execution-strategy.md` |
| May create | the files above |
| Review required | no |
| Track | both |

## Outcome

`scripts/gate.sh` runs, in order and with a summary line per step: fast tests (`-m "not slow"`,
target under 2 minutes), contract tests (`tests/contracts`), golden checks, the web checks if
`web/node_modules` exists (else prints "skipped: run npm install in web/"). `scripts/gate.sh --slow`
adds the slow tier. Exit code is non-zero if any step fails. The integrator runs only this.

## Why

The full suite takes 4 to 7 minutes on a loaded machine and every merge waits on it (A6). The
demo path had no end-to-end check until a lane found the Norway template bug by chance (A11).

## Acceptance (machine-checkable)

- [x] Slow tests are marked **without editing other lanes' test files**: `tests/conftest.py`
      reads `tests/slow_tests.txt` (one node id or file per line, comments allowed) in
      `pytest_collection_modifyitems` and adds the `slow` marker; `pytest.ini` registers the
      marker. Choose entries by measuring: `python -m pytest -q --durations=40` (record the
      measurement in the report). Target: `-m "not slow"` under 2 minutes on this machine.
- [x] `python -m pytest -q -m "not slow"` and `python -m pytest -q -m slow` together run every
      test that `python -m pytest -q` runs (a test in `tests/contracts/` or a script check proves
      the two tiers partition the suite: compare collected node ids).
- [x] `tests/contracts/`: move nothing; add thin tests that call existing contract checks: the
      JEV contract against the stub server (see `tests/test_jev_contract.py`, `jev/`), the
      `flow/1` format (`pathway_sim/flow.py`, `docs/platform/flow-format.md`), the service
      OpenAPI shape (response models exist for the documented routes). Later packages add
      `card/1` and `catalogue/1` here.
- [x] Golden checks (extend `tests/test_golden_templates.py` or add `tests/test_golden_cli.py`):
      Norway observed within 42 days is 0.34 to 0.46 through the CLI path
      (`python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed`,
      or the same through its Python function) and through the service template; the Finnish
      headline numbers in `demo/data/` bundles match `docs/pitch/fill_numbers.py --check` if that
      script exists (read it; if it has no `--check`, assert the numbers the pitch states against
      the bundle in a test and say so). Golden checks are *not* slow-marked; keep each under 30 s
      with a reduced n if needed, with tolerance chosen and justified.
- [x] `pytest.ini` keeps `--ignore=tests/security` (WP-C6-SEC1 is fixing that folder in parallel;
      the integrator removes the ignore after merging it).
- [x] The gate section of `02-execution-strategy.md` names `scripts/gate.sh` and the tiers.

## Out of scope

Changing test logic of other lanes, speeding up the simulator, CI workflow files.

## Notes

- Other agents run tests on this machine at the same time; measure durations twice and use the
  lower value. Load may be high.
- `tests/__init__.py` exists and `pythonpath = . tests`; keep both.

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [x] | INFRA-1-T1 | Measure durations; write `tests/slow_tests.txt`; conftest hook; marker registered | S | fast tier under 2 min, partition check passes |
| [x] | INFRA-1-T2 | `tests/contracts/` with JEV, flow/1, OpenAPI checks | S | `pytest tests/contracts` green, under 1 min |
| [x] | INFRA-1-T3 | Golden checks for Norway (CLI + service) and pitch numbers | S | tests green; fail if the template is switched back to the uncalibrated file (show by a one-off local experiment, described in the report) |
| [x] | INFRA-1-T4 | `scripts/gate.sh` with summary and exit code; doc section updated | S | `scripts/gate.sh` exits 0 on the current tree |

## Report (builder fills in at the end)

**Branch** `w2/infra1`, base 7e77f47. Files: `pytest.ini` (slow marker registered, `--ignore=tests/security` and `pythonpath` kept),
`tests/conftest.py` (hook), `tests/slow_tests.txt`, `tests/contracts/` (4 files), `tests/test_golden_cli.py`, `scripts/gate.sh`,
the gate section of `docs/plan/02-execution-strategy.md`. No other lane's file touched (`service/templates.py` was edited for the
one-off experiment below and restored with `git checkout`).

**Measurements** (pytest with `--durations=70`, whole suite 718 passed, 2 skipped, 161 s on a quiet machine, load 0.2).
Twenty-one tests or families over about 2 s (call or fixture setup) are in `tests/slow_tests.txt`; the biggest are
`test_in_loop_stokstad_small` 14 s, `test_same_changes_and_heldout_numbers_under_rule_and_stub` 8 s, `test_http_url_and_failure` 7 s,
`test_shipped_scenarios_give_identical_results` 6 s, `test_comparison_experiment_quick` 6 s. Moving a test out can move a module-scoped
fixture's cost onto the next test in the file, so a few 2 to 5 s setups remain in the fast tier (`test_service_loop`, `test_service_apply`).
Result: fast tier 83 s and 88 s (two runs), 91 s inside the gate under load average 1.9; slow tier (30 tests) 90 s; contracts 7 s; golden 6 s.
`scripts/gate.sh --slow` end to end: 3 min 10 s; without `--slow`: 1 min 44 s. Exit code 0 on this tree; non-zero when a step fails
(checked with `PYTHON=/bin/false`).

**Golden checks** (all not slow-marked):
- Norway observed share within 42 days, mean of two seeds (301, 302) of 1000 patients, between 0.34 and 0.46: through the CLI
  (`python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed`, parsed from its output, about 0.40);
  through the service API (project from template `norway_check`, run, `headline.on_time`); and the existing `prepare_run` test.
  Tolerance: published 40% +- 6 points; sampling error of that mean is about 1.1 points (1 sd), so the band is over 5 sd and only a
  change of the world file leaves it.
- Pitch: `docs/pitch/fill_numbers.py` has no `--check`, so `test_pitch_templates_fill_completely_and_the_committed_copies_are_current`
  imports its `build_values()` and checks (read-only) that no placeholder in `docs/pitch/*.md` is unfillable and that the committed
  `docs/pitch/filled/*.md` equal a fresh fill (exact text). It fails after any bundle or template change until the script is rerun.
- Bundle sanity: Norway baseline share in 0.34 to 0.46 with target 42 d; Finnish target 90 d, optimiser share above baseline, baseline
  share in 0.10 to 0.30 (loose; the fill check above is what pins the stated numbers).

**One-off experiment (INFRA-1-T3).** Pointing the `norway_check` source in `service/templates.py` at `stokstad.yaml` only (uncalibrated)
made `test_norway_template_observed_through_the_service_api` and `test_golden_templates.py::test_norway_template_observed_is_near_the_published_40_percent`
fail with a share of 0.1085; reverted afterwards. The CLI test is unaffected by the template (it names the calibrated file).

**Decisions made.** (1) Slow list is a text file of node ids with prefix matching (a file, class, test, or test with any parameters), so
nothing in other lanes' files changes. (2) `tests/contracts/test_jev_stub.py` re-exports the checks of `tests/test_jev_contract.py`
instead of copying them, so the JEV owner's file stays the single source; those tests therefore run twice in a full run (about 1 s).
(3) Contracts and golden tests are also in the fast tier (not slow), so the gate runs them twice (about 13 s). (4) The OpenAPI contract
pins the 18 routes that have response models and checks 11 routes without one exist; the runs, datasets, models and optimisation routes have
no response models yet (follow-up for the service lane, then move them to `WITH_SCHEMA`). (5) The interpreter: this worktree's `python` has no
fastapi; `gate.sh` falls back to the main checkout's `.venv`.

**Not done / caveats.** Web step not run (`web/node_modules` absent here; the skip line was verified). `card/1` and `catalogue/1`
contracts are for later packages. `docs/pitch/fill_numbers.py` was not given a `--check` (not my path). `tests/security` still ignored.

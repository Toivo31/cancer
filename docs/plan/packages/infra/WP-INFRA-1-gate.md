# WP-INFRA-1: Fast and slow test tiers, contract tests, one gate command, golden checks

| | |
|---|---|
| Component | cross-cutting; `02-execution-strategy.md` "The gate" and problems A6, A11 |
| Status | not started |
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

- [ ] Slow tests are marked **without editing other lanes' test files**: `tests/conftest.py`
      reads `tests/slow_tests.txt` (one node id or file per line, comments allowed) in
      `pytest_collection_modifyitems` and adds the `slow` marker; `pytest.ini` registers the
      marker. Choose entries by measuring: `python -m pytest -q --durations=40` (record the
      measurement in the report). Target: `-m "not slow"` under 2 minutes on this machine.
- [ ] `python -m pytest -q -m "not slow"` and `python -m pytest -q -m slow` together run every
      test that `python -m pytest -q` runs (a test in `tests/contracts/` or a script check proves
      the two tiers partition the suite: compare collected node ids).
- [ ] `tests/contracts/`: move nothing; add thin tests that call existing contract checks: the
      JEV contract against the stub server (see `tests/test_jev_contract.py`, `jev/`), the
      `flow/1` format (`pathway_sim/flow.py`, `docs/platform/flow-format.md`), the service
      OpenAPI shape (response models exist for the documented routes). Later packages add
      `card/1` and `catalogue/1` here.
- [ ] Golden checks (extend `tests/test_golden_templates.py` or add `tests/test_golden_cli.py`):
      Norway observed within 42 days is 0.34 to 0.46 through the CLI path
      (`python -m pathway_sim run scenarios/generated/stokstad_calibrated.yaml --flowchart observed`,
      or the same through its Python function) and through the service template; the Finnish
      headline numbers in `demo/data/` bundles match `docs/pitch/fill_numbers.py --check` if that
      script exists (read it; if it has no `--check`, assert the numbers the pitch states against
      the bundle in a test and say so). Golden checks are *not* slow-marked; keep each under 30 s
      with a reduced n if needed, with tolerance chosen and justified.
- [ ] `pytest.ini` keeps `--ignore=tests/security` (WP-C6-SEC1 is fixing that folder in parallel;
      the integrator removes the ignore after merging it).
- [ ] The gate section of `02-execution-strategy.md` names `scripts/gate.sh` and the tiers.

## Out of scope

Changing test logic of other lanes, speeding up the simulator, CI workflow files.

## Notes

- Other agents run tests on this machine at the same time; measure durations twice and use the
  lower value. Load may be high.
- `tests/__init__.py` exists and `pythonpath = . tests`; keep both.

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [ ] | INFRA-1-T1 | Measure durations; write `tests/slow_tests.txt`; conftest hook; marker registered | S | fast tier under 2 min, partition check passes |
| [ ] | INFRA-1-T2 | `tests/contracts/` with JEV, flow/1, OpenAPI checks | S | `pytest tests/contracts` green, under 1 min |
| [ ] | INFRA-1-T3 | Golden checks for Norway (CLI + service) and pitch numbers | S | tests green; fail if the template is switched back to the uncalibrated file (show by a one-off local experiment, described in the report) |
| [ ] | INFRA-1-T4 | `scripts/gate.sh` with summary and exit code; doc section updated | S | `scripts/gate.sh` exits 0 on the current tree |

## Report (builder fills in at the end)

# WP-C6-SEC1: Close the open security findings before any public URL

| | |
|---|---|
| Component | C6 platform; `docs/platform/security-review.md`; triage in `docs/plan/04-status.md` ("Security review") |
| Status | done (commit 18cec7e) |
| Size | M |
| Needs | – |
| Provides | nothing new; safer service |
| Owned paths | `service/`, `jev/factory.py`, `jev/http.py`, `tests/security/`, `tests/test_service_security.py`, `docs/platform/security-review.md` (status column only) |
| May create | new tests under `tests/security/`; `service/limits.py` if useful |
| Review required | yes: security |
| Track | submission (anything exploitable on the hosted demo) |

## Outcome

Every finding marked open in `04-status.md` is fixed or explicitly accepted with a reason, and
`python -m pytest -q tests/security` passes as one command in under 3 minutes with no
`xfail(strict=True)` left that now passes. The integrator can then drop
`--ignore=tests/security` from `pytest.ini` (you do not edit `pytest.ini`; WP-INFRA-1 owns it).

## Findings to close (read each in `docs/platform/security-review.md` first)

| Finding | What to do (lean; better idea allowed, say why) |
|---|---|
| **F16 (high)** flow endpoint re-simulates in the API process | Serve the stored flow for the default sample; any non-default `sample`, `sample_seed` or `seeds` either runs as a job through the existing job runtime (`service/jobs.py`, `service/runtime.py`) or is refused with 422 and a clear message. If a job is too much work for the time, refuse, and keep a bounded in-process path only if it has a semaphore of 1 and a wall-time limit. Test: 8 parallel requests do not start 8 simulations |
| F2 rest / F5 | Server-side cap on JEV timeout (max 5 s regardless of the client's value), response size cap 1 MiB in `jev/http.py`, slow JEV calls cannot stall the API event loop (calls run off the loop or with the cap) |
| F3 | Reject NaN and Infinity at ingest (world, flowchart, decision policy, datasets) with 422 `invalid_document` and a problem pointing at the field; a project that already holds one does not make `GET /runs` answer 500 |
| F6 | Job and run errors stored and returned without tracebacks or server file paths; full traceback goes to the server log only |
| F7 | Deleting a project cancels its queued and running jobs (terminate the child process) and their results are not written afterwards |
| F14, F18 | If a small fix exists (per-client concurrent job cap already exists? check), do it; otherwise mark "accepted for the hackathon" with the reason in the status column |
| Low ones | Fix the trivial ones; list the rest as accepted |

## Acceptance

- [ ] `python -m pytest -q tests/security` passes in one run (no hang); every test that used to be
      `xfail(strict=True)` for a fixed hole is now a normal test; five tests that need the JEV
      allowlist configure it for their local stub server via environment in a fixture.
- [ ] `python -m pytest -q tests/test_service_*.py` still green.
- [ ] Each fixed finding has at least one test that fails on the old code (say which in the report).
- [ ] `docs/platform/security-review.md` has a status line per finding (fixed in commit, or accepted + reason).
- [ ] No behaviour change for the web app's normal path (default flow sample still served, same JSON shape).

## Out of scope

Accounts, per-user auth, WAF, deployment files (`deploy/`, `Dockerfile`), `web/`.

## Things to look at

- `service/routes/runs.py` `get_flow` and `service/runs_core.py` `compute_flow` (F16).
- `service/security.py` (access middleware from the deployment lane), `jev/factory.py` (allowlist).
- Another lane (WP-INFRA-1) edits `tests/conftest.py` and `pytest.ini`; do not touch them. If you
  need a fixture, put a `conftest.py` inside `tests/security/`.

## Tickets

| | ID | Ticket | Size | Done when |
|---|---|---|---|---|
| [x] | SEC1-T1 | Make `tests/security` runnable as one command; convert passing xfails; allowlist fixture | S | one run, no hang; list of real remaining failures |
| [x] | SEC1-T2 | F16 flow endpoint bounded | M | parallel-request test passes; default flow unchanged |
| [x] | SEC1-T3 | F3 non-finite numbers rejected; old poisoned project readable | S | tests pass |
| [x] | SEC1-T4 | F2 rest and F5 caps in `jev/http.py`, off-loop calls | S | tests pass |
| [x] | SEC1-T5 | F6 errors without tracebacks; F7 delete cancels jobs | S | tests pass |
| [x] | SEC1-T6 | Status column in the review; triage of F14, F18 and the low ones | S | every finding has a status |

## Report (builder fills in at the end)

Commit range `7e77f47..18cec7e` on `w2/sec1` (plus the report commit after it). Per-finding status and the proving tests are in
`docs/platform/security-review.md` ("Status").

- Fixed: F16, F3, F5, F6, F7, F9, F10, F11, and the parts of F4 that were still open (`/decide` with an unreachable JEV is 502;
  non-string `backend`/`url` and non-object `points` are 422). F1, F2, F13 were already fixed by the deployment lane; their tests are normal tests now.
- Accepted: F8 (Docker PID 1; `PR_SET_PDEATHSIG` tried, no effect because the parent is the forkserver), F12 (one shared token),
  F14 and F18 (existing rate and active-job limits plus hosted settings), F15 (`pathway_sim.validate` is not in this package's paths),
  F17 (`jev/stub_server.py` is a dev tool and not in this package's paths).
- Tests: `python -m pytest -q tests/security` passes in one run (150 passed, 5 xfailed in about 80 s); `tests/test_service_*.py` and `tests/test_jev*.py` green.
  The five remaining `xfail(strict=True)` are F8, F12, F15 (two) and F17. The fuzzer's `KNOWN_500` is empty and its xfail reminder is deleted.
  Every fixed finding has a test that failed on the old code (checked by running the new tests against `7e77f47`'s `service/` and `jev/`).
- JEV allowlist in tests: `tests/security/conftest.py` has an `allow_jev` fixture; `internal_server` uses it. Tests whose job process needs the variable
  use `PATHWAY_JOB_START=spawn` (the shared forkserver keeps the environment it started with).

### Decisions made

- F16: a rebuild is a job and the request waits (not 422), so the web app's `?sample=...&seeds=...` calls and `tests/test_service_runs.py` keep working.
  At most `max_jobs` rebuilds may wait at once (429 `flow_busy`); the job has a 60 s limit; its output is a temporary blob that the request deletes.
- F5: calls that run while a request waits use a 1 s timeout and no retry (the review test wants a 2.5 s policy timeout to answer in under 2 s);
  jobs keep the policy's timeout up to the 5 s cap. These routes are now `async def` and use `service.limits.offload` (4 threads, 16 places).
- F3: one ASGI middleware (`RejectNonFinite`) buffers bodies of up to the 1 MB document limit; `run_view` also scrubs stored non-finite values.
- F11: key patterns no longer allow dots, so blob keys with a dot are refused (none exist).

### What others must know

- Web app: no JSON shape changed. New refusals: 422 `invalid_document` for NaN/Infinity, 422 for versions outside 1..10**6 and ids starting with `.` or `-`,
  429 `flow_busy` and 429 `busy` under load, 502 `backend_unavailable` from `/decide`.
- Flowchart ids that started with `_`, `.` or `-` are no longer accepted (none in the templates).
- Not run: a real uvicorn instance behind a proxy; only `TestClient` and local servers.

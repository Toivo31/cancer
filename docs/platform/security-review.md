# Security review of the platform service (f0bca56)

Reviewer lane `plat/secreview`, Saturday 14 Nov 2026. Scope: `service/`, `jev/`, `pathway_sim/expr.py`, `pathway_sim/documents.py`, YAML
loading, the routers merged at `f0bca56`. No source code was changed. Evidence is in `tests/security/` (run with
`python -m pytest -q tests/security`). Every confirmed exploit is an `xfail(strict=True)` test: it passes today and turns red
when the hole is fixed, which is the cue to delete the `xfail` marker. Tests marked as plain passes pin down properties that are safe now.

All probing used a local `TestClient`, 127.0.0.1 servers started by the tests, and synthetic data. Link-local and private
addresses were only given to the URL parser of `HttpBackend` (its constructor does not connect). Nothing external was contacted.

## Summary

| Severity | Count | Findings |
|---|---|---|
| High | 3 | F1 no access control, F2 SSRF through the `http` decision backend, F16 unbounded re-simulation inside the API process |
| Medium | 7 | F3 NaN/Infinity poison a project, F4 500s on `/decide` and on typed-wrong policies, F5 client-chosen JEV timeout and unbounded JEV response, F6 tracebacks and server paths in job errors, F7 jobs outlive a deleted project, F14 no per-client quotas, F18 memory near the patient limit |
| Low | 8 | F8, F9, F10, F11, F12, F13, F15, F17 |
| Info | 6 | see the end |

F1 and F2 are known gaps (ticket M7-2 is open; spec 03 and 07 name the allowlist). They are listed because nothing in the code
enforces them yet and a public hosting without them is not safe. F16 was not known.

## Top three, with the one-line fix

1. **F2 SSRF.** Fix: check the destination in `jev.factory._make_backend` before `HttpBackend` exists (see F2 for the details).
2. **F1 open API.** Fix: one ASGI middleware that compares a header with `PATHWAY_ACCESS_TOKEN` (constant-time compare, `/api/health` exempt), refused when the variable is set and the header is wrong.
3. **F16 flow rebuild in the API process.** Fix: serve only the stored flow, or run the rebuild as a job; at minimum a semaphore of 1 and a time limit.

## Status (WP-C6-SEC1, branch `w2/sec1`; the commit is in the package report)

Every test marked `xfail(strict=True)` for a fixed hole is now a normal test; `python -m pytest -q tests/security` runs as one command (about 80 s on a loaded 2-CPU machine). Five tests stay `xfail(strict=True)` for the accepted findings (F8, F12, F15 twice, F17).

| Finding | Status | Evidence |
|---|---|---|
| F1 access token | Fixed by the deployment lane (`service/security.py`) | `test_access_and_web.py::test_requests_without_the_access_token_are_rejected` |
| F2 outbound host | Fixed: allowlist, no credentials, no response text in errors (deployment lane); timeout and size caps (SEC1, see F5) | `test_ssrf_jev.py` |
| F3 NaN and Infinity | Fixed: `service/limits.py` `RejectNonFinite` refuses them (also `1e999`, JSON-lines uploads) with 422 `invalid_document` and the field path; stored non-finite values are shown as null so `GET /runs` answers 200 | `test_input_limits.py` (4), `test_sec1_fixes.py` |
| F4 wrong-typed policy, unreachable JEV | Fixed: `/decide` answers 502 for `BackendError`; `jev.prepare` rejects non-string `backend` and `url` and non-object `points` with a ValueError (422) | `test_ssrf_jev.py::test_wrong_typed_decision_policy_is_a_422`, `test_decide_with_unreachable_jev_is_a_client_error`, the fuzzer (`KNOWN_500` is empty) |
| F5 JEV timeout, size, stall | Fixed: `HttpBackend` caps timeout at 5 s and retries at 1, rejects non-positive or non-finite timeouts, reads at most 1 MiB; calls made while a request waits (`/decide`, `POST /runs`, `POST /optimisations`) run in a dedicated pool of 4 threads (16 places, then 429) with a 1 s timeout and no retry, so the event loop and the shared thread pool stay free | `test_ssrf_jev.py` (3), `test_sec1_fixes.py` |
| F6 tracebacks | Fixed: the traceback goes to the server log (`pathway.jobs`), job and run errors carry `code` and a message with server paths replaced by `<path>` | `test_jobs_resources.py` (2), `test_sec1_fixes.py` |
| F7 deleted project's jobs | Fixed: `DELETE /projects/{p}` cancels its queued and running jobs and waits for their processes to end before removing rows and files | `test_jobs_resources.py::test_deleting_a_project_stops_its_running_jobs`, `test_sec1_fixes.py` |
| F8 orphan job after SIGKILL | Accepted: in Docker the container ends with PID 1. `PR_SET_PDEATHSIG` was tried and did not help (the worker's parent is the forkserver, which does not end with the service); a bare VM should run the service under a supervisor that kills the process group | still `xfail` |
| F9 integer overflow | Fixed: versions limited to 1..10**6 in bodies, paths and queries | `test_input_limits.py` (2) |
| F10 `.` and `..` ids | Fixed: ids must start with a letter or digit | `test_input_limits.py` (3) |
| F11 blob key pattern | Fixed: `fullmatch` on `[A-Za-z0-9][A-Za-z0-9_-]{0,79}` in `service/store.py` and `service/runs_core.py` | `test_paths_and_static.py` (3) |
| F12 global job list | Accepted: one shared token, one team; revisit when projects belong to people | still `xfail` |
| F13 headers | Fixed by the deployment lane | `test_basic_security_headers_are_set` |
| F14 quotas | Accepted for the hackathon: the deployment lane already limits job starts per client per minute (`PATHWAY_JOB_STARTS_PER_MIN`, 6), queued plus running jobs (`PATHWAY_MAX_ACTIVE_JOBS`) and requests per minute, all active outside open mode. Set `PATHWAY_JOB_SECONDS=120` on the hosted instance. No run count per project (about 1.8 MB per 19k-patient seed; the disk guard `PATHWAY_MIN_FREE_MB` stops writes) | policy, no test |
| F15 validator gaps | Accepted here: the fix is in `pathway_sim.validate` (not in this package's paths). Such a world fails alone, at the job, with a clean error (F6) | still `xfail` |
| F16 flow re-simulation | Fixed: the stored flow is served as before; any other `sample`, `sample_seed` or `seeds` is rebuilt by a job (own process, 60 s limit, counted against the job slots) and the request waits for it. At most one waiting rebuild per job slot, others get 429 `flow_busy`. Same JSON shape | `test_jobs_resources.py::test_flow_rebuild_is_bounded_by_the_job_limit`, `test_flow_rebuild_runs_as_a_job_and_the_default_flow_does_not` |
| F17 stub server negative length | Accepted: `jev/stub_server.py` is a dev tool bound to 127.0.0.1 and outside this package's paths; do not expose it | still `xfail` |
| F18 memory | Accepted: configuration, not code. Hosted: `PATHWAY_MAX_PATIENTS=20000`, `PATHWAY_MAX_SEEDS=3`, `PATHWAY_MAX_JOBS=1` or 2, container of 2 GB. Flow rebuilds also use job slots, so they are inside these limits | no test |

## Findings

Effort: S under an hour, M a few hours, L a day.

### F1 (High, S/M) Nothing authenticates or limits callers
- Repro: `GET /api/projects` then `DELETE /api/projects/{p}` with no header: 200 and 204. `grep -rn ACCESS_TOKEN service jev` finds nothing.
- Why it matters: anyone who reaches the port can delete every project, start jobs up to the queue limit, and read all results. Ids are `p_` plus 8 hex digits (32 bits), and `GET /api/projects` lists them anyway, so "per-project isolation by id" (spec 03) is not isolation.
- Fix: token middleware as above; later per-project ids with 128 bits (`secrets.token_urlsafe(16)`). A request rate limit per token (spec 07) is not implemented either.
- Tests: `test_access_and_web.py::test_requests_without_the_access_token_are_rejected` (xfail), `test_today_anybody_...`, `test_project_and_job_ids_are_only_32_bits`.
- Note for the web lane: there is no CORS middleware, which is the safe default (cross-site pages cannot read responses, preflighted methods are refused, and the simple content types of a cross-site form are refused with 422; see the passing tests). If CORS is added later, do not combine `*` with a token in a cookie.

### F2 (High, M) The `http` decision backend can be pointed at any host
- Repro (two lines): `POST /api/projects/{p}/runs {"flowchart":{"id":"observed"},"decision_policy":{"backend":"http","url":"http://127.0.0.1:PORT/admin","model":"m"}}`. The service sends `GET /admin/v1/models` to that address.
- What the attacker gets:
  - a request from inside the network to any host and port (loopback, 10.x, 169.254.169.254, `[::1]`); the check `HttpBackend.__init__` only wants `http(s)` and a hostname;
  - a read channel: when the target answers 4xx, the first 300 bytes of its body come back in the 422 message (`JEV at ... rejected the request (404): {...}`); when it answers a JSON `models` list, the model ids come back; timing and error text distinguish open from closed ports;
  - `user:password@` in the URL is accepted and then repeated in error messages;
  - the same policy can be stored in a flowchart document (`POST /flowcharts` does not check non-stub policies), so the call also happens from jobs.
- `JEV_ALLOWED_HOSTS` (spec 03, 07) is read nowhere. Redirects are not followed (`http.client`), which is good (passing test).
- Fix: before building the backend, parse the URL, reject userinfo, resolve the host once, refuse loopback/private/link-local/multicast/unspecified addresses unless the host is in `JEV_ALLOWED_HOSTS` (the team's real JEV goes in the list), and connect to the address that was checked (this also closes DNS rebinding, which does not exist while there is no check at all, but appears the moment a name allowlist is added). Never put response text in an error message; say the status code. Do the check in `_make_backend` so stored policies, `/decide`, `/runs` and per-point overrides all pass through it.
- Tests: `test_ssrf_jev.py` (10 xfail parametrised addresses, reflection, credentials, allowlist; passing: no redirect following, no caller headers forwarded).

### F16 (High, S/M) `GET .../runs/{r}/flow` re-simulates inside the API process
- Repro: finish any run, then `GET /api/projects/{p}/runs/{r}/flow?sample_seed=1`, `=2`, `=3`, ... Each call runs `compute_flow` in a request thread: up to 60,000 patients (`FLOW_MAX_PATIENTS`), no job, no time limit, no bound on how many run at once.
- Measured: 8 parallel requests ran as 8 simultaneous simulations in the API process (the test counts them). A 19k-patient seed holds about 200 MB and takes about 40 s; the thread pool allows 40 requests. One visitor can exhaust memory and take the service and all its jobs down; a crash here is not isolated the way a job crash is.
- Fix: refuse everything except the stored default flow (sample 300, seed 0), or submit the rebuild as a job and poll it; if kept synchronous, a global semaphore of 1 and a wall-time limit.
- Test: `test_jobs_resources.py::test_flow_rebuild_is_bounded_by_the_job_limit` (xfail).

### F3 (Medium, S) NaN and Infinity are stored and poison the project
- Repro: `PUT /api/projects/{p}/world` with `"target_days": NaN` (valid for Python's JSON parser, not for JSON) returns 200. A run then succeeds with NaN metrics, and `GET /api/projects/{p}/runs` and `GET .../runs/{r}` answer 500 from then on, even after the world is repaired (the stored run keeps its NaN). `?brief=true` still works.
- Same for flowchart documents (`test_overrides` is free-form).
- Fix: reject non-finite numbers where the body is parsed (a `parse_constant` that raises, in the body-limit middleware or a custom `Request.json`), or `allow_inf_nan=False` in `_Loose`; and make `run_view` robust.
- Tests: four xfails in `test_input_limits.py`.

### F4 (Medium, S) Avoidable 500s
- `POST /decide` with an unreachable JEV: 500 (`BackendError` is a `RuntimeError`, the route catches `ValueError` and `DocumentError`). Fix: catch `jev.BackendError`, answer 502.
- `decision_policy.backend` or `.url` of the wrong type (`5`, `null`, a list): 500 on `/decide` and `/runs` (`dp.get("backend")` gets a non-string and `.startswith` fails in `jev.prepare`). Fix: validate the policy shape in the pydantic model (`backend: Literal[...]`, `url: str`).
- Tests: `test_ssrf_jev.py::test_decide_with_unreachable_jev_...`, `test_wrong_typed_decision_policy_is_a_422` (10 cases).

### F5 (Medium, S) Client-chosen JEV timeout, unbounded JEV response
- `timeout` comes from the policy (`float(cfg.get("timeout", 2.0))`); `/decide` and the validation call in `POST /runs` call the JEV synchronously in a request thread, with one retry. A silent server plus `timeout: 2.5` holds a thread for 5 s; 48 of those make `/api/health` take 3.1 s because the 40-thread pool is full (a larger timeout makes it as long as the attacker wants). Tests: `test_client_cannot_choose_a_long_jev_timeout`, `test_slow_jev_calls_cannot_stall_the_whole_api`.
- `HttpBackend._call` does `r.read()` with no limit: a JEV that answers 40 MB is read whole (`test_oversized_jev_response_is_cut_off`). Inside a job this kills only the job; in `/decide` it is the API process.
- Fix: cap `timeout` at 5 s and retries at 1; read at most 1 MiB (`r.read(MAX+1)`); do not call the JEV in the request thread for `/runs` validation beyond a short `GET /v1/health`-style probe, or run the check in an executor with its own small pool.

### F6 (Medium, S) Tracebacks and file paths in job and run errors
- Repro: any failing job: `GET /api/jobs/{j}` and `GET .../runs/{r}` return `error.traceback` with lines such as `File "/home/claude/wt/.../service/jobs.py"`. Reveals the install path, library versions and code structure.
- Fix: keep `traceback` in the server log (and the `jobs` table if wanted), never in API output; give clients `code` and a short `message`.
- Tests: two xfails in `test_jobs_resources.py`. The ordinary error handler is fine: the fuzzer found no stack trace or path in any 4xx/5xx body.

### F7 (Medium, S) A deleted project's jobs keep running
- Repro: start a run, `DELETE /api/projects/{p}` while it runs: 204, the job stays `running` until it ends (up to the 15-minute limit), using a worker slot. When it ends, the supervisor deletes the files it wrote (verified, passing test), leaving empty directories.
- Fix: in `delete_project`, cancel jobs whose `owner.project` matches before removing rows.
- Tests: `test_deleting_a_project_stops_its_running_jobs` (xfail); `test_deleting_a_project_leaves_no_files_behind` and `test_store_recreates_blob_directory_of_a_deleted_project` (pass; the second documents the mechanism).

### F14 (Medium, M) No fairness or per-client quotas
- A world that passes validation can make a job use its whole time limit (`capacity_per_day: 1e12`, `min_lead_days: 1e15`, `arrivals.rate_per_day: 1e-300` or huge waits all do; the limit stopped each at 20 s in the probe, passing test `test_a_hostile_but_accepted_world_fails_alone_at_the_time_limit`). The queue holds 100 jobs; with 2 workers and `PATHWAY_JOB_SECONDS=900` that is about 12 hours of lock-out from one client. There is no limit on runs per project (disk: about 1.8 MB per 19k-patient seed, plus rows) or on the size of `GET .../runs` (all runs with full metrics).
- Fix: per-token limits of running and queued jobs (for example 2 and 5), a run count per project, a lower default `PATHWAY_JOB_SECONDS` for the hosted instance (120 s is plenty for a Finnish seed on 2 CPUs; measured 40 s), a rate limit.
- Not a test: it is a policy decision. Isolation holds: a crashing, hanging or timed-out job failed alone in every case (passing tests).

### F18 (Medium, S) Memory at the limits
- Measured here (2 CPUs, other lanes running): Finnish 18,800 patients x 1 seed, peak 212 MB, 40 s, 1.8 MB on disk. 50,000 x 2 seeds: peak 802 MB for one job, 230 s. At the defaults (50,000 patients, 5 seeds, workers = CPUs) two jobs can need 2 GB; spec 07 says "well under 1 GB". A kernel OOM kill picks any process, including the service.
- Fix: for the hosted instance set `PATHWAY_MAX_PATIENTS=20000`, `PATHWAY_MAX_SEEDS=3`, `PATHWAY_MAX_JOBS=1` or 2 depending on the container size, and size the container at 2 GB. No test (a memory test is not reliable in CI).

### Low
- **F8** A job process outlives a service that was killed (SIGKILL, OOM). It runs to its end, then writes blobs and flips a row that `reconcile` had marked failed. In Docker the container dies with PID 1, so this matters for a bare VM. Fix: `prctl(PR_SET_PDEATHSIG)` in the worker, or a parent-liveness check in `ctx.check_cancel()` and in the progress callback (the job only notices a dead parent when it sends a message). Test `test_job_process_does_not_outlive_a_killed_service` (xfail).
- **F9** Integers above 2**63 in `{v}` or `flowchart.version` overflow SQLite and give 500. Fix: `Field(ge=1, le=10**6)`. Two xfails.
- **F10** Flowchart and world ids may be `.` or `..` (the pattern allows dots only). A browser normalises `.../flowcharts/..` to the parent URL, so a UI that builds URLs from ids turns "delete flowchart `..`" into "delete project" (found by accident: the fuzz client did exactly that). Fix: pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`. Three xfails.
- **F11** Latent: `_KEY` in `service/store.py` and `BLOB_KEY` in `service/runs_core.py` accept `..` as a whole part and a trailing newline (`$`). Not reachable today because every part comes from the database or a constant. Fix: `^[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z` (and `fullmatch`). Three xfails. Slashes, spaces, NUL and unicode are refused (passing).
- **F12** `GET /api/jobs`, `GET /api/jobs/{j}` and `POST /api/jobs/{j}/cancel` are global: they show other projects' labels and ids and cancel any job. Harmless with one shared token, wrong once projects belong to people. Fix: filter by project or drop the list. One xfail.
- **F13** No `X-Content-Type-Options`, frame or CSP headers; Swagger UI (`/docs`) loads scripts from a CDN and `/openapi.json` is public. Fix: a small header middleware; consider disabling `/docs` on the hosted instance. One xfail. Names with markup come back as JSON with `application/json` (passing).
- **F15** The world validator lets values through that fail every run: `arrivals.rate_per_day: 0` (ZeroDivisionError), text in a distribution (`ValueError`). They fail alone, but late. Fix: check numeric fields in `pathway_sim.validate`. Two xfails.
- **F17** `jev.stub_server` with `Content-Length: -1` blocks its handler thread (`rfile.read(-1)`). It is a dev tool bound to 127.0.0.1 by default; do not expose it with `--host 0.0.0.0` on the hosted instance. Fix: reject negative lengths. One xfail.

### Info
- `ENGINE_VERSION` hashes `pathway_sim/*.py` and `jev/*.py` only (not subpackages, not `service/runs_core.py` that writes the decisions export and the bundle). A change there does not invalidate cached runs.
- `GET .../patients` carries `condition` and `cancer` (the truth). That is right for the analyst and must never feed the training export or a JEV; the decisions export and the requests sent to the JEV were checked and carry none (passing tests).
- `reconcile` marks leftover runs failed but does not remove their partial `.tmp` files.
- `service/requirements.txt` has `fastapi>=0.110` unpinned. The review ran on the venv's version, which nests routers lazily, so `app.routes` no longer lists the routes (use `app.openapi()`). Pin for the deploy.
- The web app (`web/`) is not in this checkout; the dashboards under `demo/` render names through an `esc()` helper (spot check, not an audit).
- Raw SQL: every value is bound; `_Base.update` interpolates column names, but they come from code.

## What is solid (and pinned by passing tests)

- Conditions: `pathway_sim/expr.py` is an AST whitelist with no `eval`, `exec` or `compile`; 50 hostile strings (dunder access, calls, lambdas, comprehensions, huge exponents, deep nesting, null bytes, fullwidth unicode names) are rejected or harmless; conditions sent through the API never run (marker-file test). A repository scan finds no `yaml.load`, `pickle`, `eval`, `exec`, `os.system` or format-from-client-text in server code.
- Paths: every file name is generated by the server (`p_`, `r_`, `o_` ids); client text is only ever a dictionary key or a bound SQL value; hostile ids (traversal, NUL, RTL marks, 3000 characters) give 404 or 422; the static mount refuses `..` and symlinks that leave the web directory.
- SQL: injection strings in names, labels and query parameters are stored or ignored as data.
- Limits: patients, seeds, duplicate seeds, projects, versions, body size (also streamed bodies without Content-Length), nesting depth, huge integers and digit strings.
- Jobs: time limit enforced (also against a job that ignores SIGTERM), cancel stops the process, a crashing worker fails only itself, the queue is bounded, restart marks leftover work failed and allows a retry, cancel-right-after-start never leaves a run stuck (10 races), 12 simultaneous identical requests make one run.
- Integrity: a locked version cannot be replaced or deleted; a client cannot write `metrics`, `status`, `headline`, `source`, `engine_version` or ids into a run; the identical-run cache is per project and per full input (world, flowchart version, policy, n, seeds, engine); a stored run does not change when the world is edited; no project can read another's run by id.
- Hidden truth: the decisions export rows contain only revealed context (attributes limited to what the tests in the history reveal) and no condition or cancer field; the same holds for every request body the `http` backend sent to a recording JEV server.
- Browser: no CORS headers (cross-site reads fail), cross-site form content types are refused.

## What was not checked

- The web app (not in this worktree), the real JEV service, `optimiser/` internals beyond the routes that call it, datasets and training (spec 06 is not built), the Dockerfile and host (M7-1/3 not merged).
- `POST .../optimisations/{o}/apply` was fuzzed only on the body of one finished optimisation; `apply` validates the new version against the world snapshot of the optimisation, not the project's current world (may save a version that does not fit a world edited since; not tested).
- Real network behaviour: DNS rebinding, IPv6 scope ids, proxies, TLS (`https` JEV URLs use the default context; not exercised), slow-loris against uvicorn itself, HTTP/2.
- Concurrency beyond the cases written here (multi-process uvicorn is not supported by design: the runner is in memory).
- Dependency vulnerabilities (no audit of installed package versions).
- Memory figures come from one machine with other work running.

## Fuzzer

`tests/security/test_fuzz_routes.py` reads every operation from `app.openapi()`, fills path parameters with real and hostile values, sends query fuzz to GET routes, and sends 5 raw-body variants (invalid JSON, NaN, duplicate keys, 2000-deep list, BOM, empty) plus about 40 structural mutations per body route (key dropped, replaced by null, -1, 10**30, a 5000-character string, list, nested object, true, unicode, NaN, Infinity; nested objects one level down). About 2,000 requests, 35 to 50 s. It fails on any new 5xx and on any response showing a traceback, a `/home/` path or SQL. Known 500s are listed in `KNOWN_500` (three routes: F4, F9); the strict xfail `test_known_500s_are_fixed` goes red when the list can be emptied.
NaN/Infinity were left out of the world-edit mutations so that one poisoned project did not mask other findings (F3 has its own tests).

## Test inventory

| File | Content |
|---|---|
| `test_fuzz_routes.py` | route fuzzer, known 500 list |
| `test_ssrf_jev.py` | F2, F4, F5; redirect and header-forwarding properties |
| `test_input_limits.py` | F3, F9, F10, F15; parsing limits, limits enforcement, SQL |
| `test_jobs_resources.py` | F6, F7, F8, F14, F16; time limit, crash isolation, cancel races, restart, cache races |
| `test_paths_and_static.py` | F11; traversal in ids, blob names, static files |
| `test_access_and_web.py` | F1, F12, F13; CORS and cross-site form checks |
| `test_integrity.py` | locked versions, forged results, cache isolation, hidden truth (decisions export and JEV requests) |
| `test_code_paths.py` | condition language attacks, repository scan, F17 |

Helpers: `sec_helpers.py`, `conftest.py`, `sec_jobfuncs.py`, `sec_orphan_child.py`, `sec_stall_child.py`. Run each file on its own if the whole directory is slow (a combined run once hung before the stall test was moved to a subprocess). Total run time about 3 minutes on a busy 2-CPU machine (the fuzzer, the SSRF stall tests and the job tests dominate).

# service/

FastAPI service for the flowchart platform. Spec: `docs/platform/specs/03-service-api.md`. It has no simulation
logic; it stores documents and calls `pathway_sim`, `optimiser`, `jev`.

```
pip install -r requirements.txt -r service/requirements.txt
uvicorn service.app:app --port 8000          # API page: http://localhost:8000/docs
PATHWAY_DATA_DIR=/tmp/pw uvicorn service.app:app   # where the SQLite file and result blobs go (default ./data)
python -m pytest -q tests/test_service_projects.py
```

```
curl -s localhost:8000/api/templates | head -c 300
curl -s -X POST localhost:8000/api/projects -H 'content-type: application/json' \
     -d '{"name": "Finland", "template": "finland_lung"}'            # -> {"id": "p_1a2b3c4d", ...}
curl -s localhost:8000/api/projects/p_1a2b3c4d/flowcharts/baseline/versions/latest
```

## For other routers (svc-b, web)

* Add `service/routes/<name>.py` with a module-level `router = APIRouter(tags=[...], responses=ERROR_RESPONSES)`
  and paths relative to `/api` (e.g. `/projects/{p}/runs`). `service/app.py` mounts every module in that package;
  no existing file needs editing. Optional `on_startup(app)` / `on_shutdown(app)` hooks run with the app (job pool).
* `service/deps.py`: `get_store`, `get_settings`, `get_project` (path `p` or 404), `get_templates`.
* `service/store.py`: `Store.ensure_schema(sql)` for your tables (reference `projects(id) ON DELETE CASCADE`),
  `query`, `query_one`, `execute`, `connection(write=True)`; `put_blob/get_blob(project_id, kind, key, obj)` for gzip
  JSON results (removed with the project); `new_id("r")`. A worker process builds its own `Store(data_dir)`.
* **A run or optimisation must fetch its flowchart with `store.get_version_for_run(p, flowchart_id, version)`**: it
  returns `(document, version)` and locks the version (`409 version_locked` on later edits). `store.get_world(p)` returns
  `(world, rev)`; keep `pathway_sim.documents.doc_hash(world)` with the run.
* Errors: `raise ApiError(status, code, message, problems=None)` (`service/errors.py`); body is always
  `{"error": {"code", "message", "problems"?}}`. Documents: `pathway_sim.documents` (`documents_to_scenario(world, [flowchart])`
  gives engine objects; `decision_policy` backend `rule` is today's `RulePolicy` config).

## Response shapes (stable; see `/openapi.json` for the full types)

Ids: projects `p_xxxxxxxx`. Flowchart ids are chosen by the client (`[A-Za-z0-9_.-]`), versions are 1, 2, 3 ...

| Request | Response |
|---|---|
| `GET /api/templates` | `[{id, name, description, world_id, flowcharts: [{id, name, description, nodes}]}]` |
| `GET /api/templates/{t}` | summary plus `world` and `flowchart_documents` |
| `POST /api/projects {name, template}` 201 | `ProjectDetail` |
| `GET /api/projects` | `[{id, name, template, world_id, world_rev, created_at, updated_at}]` |
| `GET /api/projects/{p}` | summary plus `flowcharts: [{id, name, latest_version, versions: [{version, parent_version, created_at, locked}]}]` |
| `PATCH /api/projects/{p} {name}`, `DELETE` | summary; 204 |
| `GET /api/projects/{p}/world` | `{world, rev, problems: []}` |
| `PUT /api/projects/{p}/world?if_rev=n` (body = world document) | `{world, rev, problems}`; `problems` lists flowcharts the new world breaks (saved anyway); 409 `stale_revision` |
| `GET /api/projects/{p}/flowcharts` | `[FlowchartSummary + latest: <document>]` |
| `POST /api/projects/{p}/flowcharts` (body = document) 201 | the document as version 1; 409 `duplicate_flowchart` |
| `GET .../flowcharts/{f}` | summary plus `latest` |
| `GET .../flowcharts/{f}/versions`, `.../versions/{v}` (`v` = number or `latest`) | version list; the document (header `X-Version-Locked`) |
| `POST .../flowcharts/{f}/versions` (body = document) 201 | the document as version n+1, `parent_version` n |
| `PUT .../flowcharts/{f}/versions/{v}` | overwrite an unlocked version; 409 `version_locked` |
| `DELETE .../flowcharts/{f}` | 204, or 409 `version_locked` if any version has been run |
| `POST /api/projects/{p}/validate {world?, flowchart}` | `{ok, problems: [{severity, code, message, node?, hint?}]}`; stores nothing |

Saving a document with errors gives `422 {"error": {"code": "invalid_document", "problems": [...]}}`; a body that does
not fit the shape gives `422 invalid_request` with the same problem list. Over the size limit: `413 payload_too_large`.
Duplicate project names get " (2)" appended (the response has the kept name).

Documents: `docs/platform/specs/01-flowchart-model.md` (nodes `{id, kind, label, test?, when?, ui?}`, edges
`{from, to, type, index?}`, `decision_policy`). Unknown keys are kept as sent.

## Runs, jobs and optimisations (svc-b)

Run the service as **one process** (`uvicorn service.app:app`, no `--workers`): jobs are child processes of it and the
queue is in memory. Whole loop with `curl`, copy-paste ready: `bash service/walkthrough.sh http://localhost:8000`
(needs `curl` and `jq`; creates a project, runs, optimises, applies, reruns and compares; about 15 seconds).

Test it: `python -m pytest -q tests/test_service_jobs.py tests/test_service_runs.py tests/test_service_loop.py`.

### How it works

* A **job** is one OS process (`service/jobs.py`). At most `PATHWAY_MAX_JOBS` run at once, the rest wait (`429 queue_full`
  past 100 waiting). A job that raises, is killed, runs out of memory or exceeds `PATHWAY_JOB_SECONDS` fails alone
  (`error.code`: the exception class, `worker_died`, `timeout`); the service and other jobs go on. Cancel stops the process.
* A job reaches a final state in `GET /jobs/{j}` only after the run or optimisation row says the same, so polling the
  job and then reading the run is safe.
* A **run** is identified by (world, flowchart version, decision policy, n, seeds, engine version). Asking for the same
  again returns the existing run, also while it is still running (`cached: true`, HTTP 200 instead of 202), so two users
  starting the same run share one. Failed and cancelled runs are not reused.
* "Same patients" = same world, n and seeds (`patients_key`). `POST /compare` refuses anything else with `409 different_patients`.
* A run keeps a snapshot of its world and flowchart, so later edits cannot change it. Results live under the data directory:
  metrics and bundle (gzip JSON), patient log and decision rows (gzip JSON lines per seed), the flow document.
* Memory: one seed at a time, about 160 MB for a Finnish seed (18,800 patients, about 10 s). Logs are streamed to disk.
* On start-up, anything still `queued` or `running` from a previous process is marked failed (`service_restarted`).
* Patients: the Finnish template has a 60-day warm-up at 44 arrivals a day, so it needs at least 2,690 patients per
  seed (`422 n_too_small` says the number); the Norway check needs no warm-up.

### Shapes (stable; `/docs` has the full types)

Start a run `POST /api/projects/{p}/runs`:
```json
{"flowchart": {"id": "observed", "version": 1}, "n": 300, "seeds": [301, 302], "label": "today", "decision_policy": null}
```
`version` omitted = latest; `n` omitted = the world's `default_n`; `seeds` omitted = `[1]`; `decision_policy` overrides the
flowchart's own for this run (for example `{"backend": "stub", "mode": "sample", "points": {...}}`; a table that does not
fit the flowchart is `422 invalid_decision_policy`). Limits: `n` up to `PATHWAY_MAX_PATIENTS` (50,000), up to
`PATHWAY_MAX_SEEDS` (5) distinct seeds, else `429 limit_exceeded`. A flowchart with problems is `422 invalid_document`.
Answer `202` (or `200` when cached) is the **run object**:
```json
{"id": "r_8f2c1a90", "run_id": "r_8f2c1a90", "project_id": "p_…", "label": "today",
 "flowchart": {"id": "observed", "version": 1}, "n": 300, "seeds": [301, 302], "decision_policy": null,
 "status": "queued|running|succeeded|failed|cancelled", "job_id": "j_41", "progress": 0.0, "message": "",
 "created_at": "…", "started_at": null, "finished_at": null, "error": null,
 "headline": null, "per_seed": null, "engine_version": "…", "world_rev": 1, "patients_key": "…",
 "source": null, "cached": false}
```
`GET /runs/{r}` adds `metrics` (mean over seeds: the metrics JSON of `docs/architecture.md`, with `node_breakdown`,
`stage_breakdown`, `by_group`, `utilisation`) and `resources`; `headline` is `{on_time, median_days, missed_cancers,
tests_per_patient, n, n_cancer, stuck}`; `per_seed` is the same per seed. `GET /runs?flowchart=id&brief=true` lists newest
first (`brief` drops `metrics`). `source` is `{"optimisation": "o_…", "role": "baseline|rerun"}` for runs made by `apply`.

| Request | Answer |
|---|---|
| `POST /projects/{p}/runs/{r}/cancel` | the run object (status `cancelled`) |
| `GET /projects/{p}/runs/{r}/bundle[?compare_to=r2]` | dashboard bundle (`demo/README.md`) of one scenario; with `compare_to` that run is the "before" and this run the variant. `409 run_not_finished` until succeeded |
| `GET /projects/{p}/runs/{r}/decisions[?seed=&point=&measured_only=true]` | JSON lines, one decision each: `{decision_point, patient_id, t_days, context: {group, age, t_days, fast_track, attributes, history: [{step, test, result, t_days}]}, offered, chosen, probs, measured}` (spec 06 rows) |
| `GET /projects/{p}/runs/{r}/patients?offset=0&limit=100[&seed=]` | `{seed, offset, limit, total, patients: [{id, group, age, arrival, outcome, t_exit, events: [...], choices: [...], seed}]}`; times in events are absolute days, `t_exit` and `choices[].t` relative to arrival |
| `GET /projects/{p}/runs/{r}/flow[?sample=300&sample_seed=0&seeds=…]` | `flow/1` document (`docs/platform/flow-format.md`) pooled over the run's seeds, `meta.pooled_seeds` says which. The stored one (sample 300, seed 0) is instant; other parameters re-simulate (same patients, seconds) |
| `POST /projects/{p}/compare {"runs": [a, b]}` | `{same_patients, n, seeds, a: {id, label, flowchart, headline}, b: {...}, headline: {metric: {a, b, delta}}, by_group: {group: {metric: {a, b, delta}}}, stages: {stage: {wait, service}}, nodes: {node: {wait, service}}, utilisation: {resource: {a, b, delta}}}`; delta is b minus a |
| `GET /jobs/{j}` | `{id, kind: "run"|"optimisation", status, state, progress 0..1, message, error: {code, message}|null, log_tail: [...], result, owner: {project, kind, id}, created, started, finished}`. Poll about once a second |
| `POST /jobs/{j}/cancel`, `GET /jobs[?status=]` | the job; `{counts, jobs}` |

Optimise `POST /api/projects/{p}/optimisations` (202, the optimisation object below without results):
```json
{"flowchart": {"id": "observed", "version": 1}, "n": 300, "train_seeds": [101, 102], "heldout_seeds": [301, 302],
 "max_changes": 6, "allow": ["detach", "relax", "standardise"], "safety": {"tests_tolerance": 0.02, "equity": true}}
```
Defaults: `n` the world's `default_n`, seeds 101, 102 and 301, 302, `max_changes` 6, `allow` detach, relax, standardise (only
detach and relax when the flowchart's decision backend is not `rule`: `standardise` would compete with the decision model, F7;
`allow_standardise_under_jev: true` overrides). Training and held-out seeds must differ (`422`). Optimising the Finnish
template at its default n takes minutes; the job time limit is 15 minutes, so lower `n` if it times out.
`GET .../optimisations/{o}` (also `GET .../optimisations`, light, and `POST .../{o}/cancel`):
```json
{"id": "o_17", "status": "succeeded", "job_id": "j_52", "progress": 1.0, "flowchart": {"id": "observed", "version": 1},
 "settings": {...}, "error": null, "applied": [{"accepted": [0], "flowchart": {...}, "run_id": "r_…"}],
 "changes": [{"index": 0, "kind": "relax", "target": "…", "other": "…", "label": "Plain wording for a clinician",
              "raw": "optimiser text", "records_reading": "In the records, …", "predicted_days_saved": 4.5,
              "linked_with": [], "train": {"on_time_before": 0.41, "on_time_after": 0.51, "median_before": 46.5, "median_after": 42.0},
              "heldout_after_this_change": {"on_time": 0.57, "median_days": 39.7, "missed_cancers": 0, "tests_per_patient": 2.3}}],
 "blocked": [{"label": "…", "raw": "…", "gain_pp": 2.6, "blocked_by": ["more missed cancers"]}],
 "heldout": {"before": {...metrics...}, "after": {...metrics...}}, "train": {"before": {...}, "after": {...}},
 "selection_optimism_pp": 0.4, "guardrails_heldout": [], "candidates_evaluated": 120,
 "n_train": 300, "n_heldout": 300, "train_seeds": [101, 102], "heldout_seeds": [301, 302],
 "honesty": "Suggestions come from what a clinic's records would show. …",
 "proposed_flowchart": {...flowchart document, all changes applied...}}
```
`linked_with` lists changes the search only accepted together. `POST .../{o}/apply {"accept": [0, 2], "rerun": true, "label": "…"}`
(`accept` omitted = all) saves a new version of the same flowchart (`edits_from_parent` lists the accepted changes; node
positions are kept) and, with `rerun`, runs the new version and its parent on the held-out seeds (the parent's run is reused
if it exists):
```json
{"flowchart": {"id": "observed", "version": 2}, "based_on": {"id": "observed", "version": 1}, "accepted": [0, 2],
 "edits_from_parent": [...], "run_id": "r_a", "baseline_run_id": "r_b", "run": {...run object}, "baseline_run": {...}}
```
Then `POST /compare {"runs": [baseline_run_id, run_id]}`. Errors: `409 linked_change` (`problems[0].needs` = the partner
changes to accept too), `409 not_applicable`, `409 unknown_change`, `409 optimisation_not_finished`.

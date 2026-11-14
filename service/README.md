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

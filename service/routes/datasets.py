"""Datasets of past decisions (spec 06): upload, decisions of a run, exploration runs, validation report, rows."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import jev
from jev import dataset as D

from ..datasets_core import MAX_ROWS, execute_dataset_from_run, execute_exploration, finish_dataset, report_for
from ..datasets_db import FINAL, Datasets, Models, read_lines, rows_path
from ..deps import get_project, get_store
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..jobs import QueueFull
from ..runs_core import min_patients
from ..runtime import Runtime, get_runtime
from ..store import NotFound, Store
from .runs import FlowchartRef

router = APIRouter(tags=["datasets"], responses=ERROR_RESPONSES)

SYNTHETIC_NOTICE = ("Synthetic data only on this instance. The format has no free-text fields, so identifiable text has nowhere to go; "
                    "real patient data needs a data protection assessment that is outside this tool.")


def on_startup(app) -> None:
    store = app.state.services.store
    err = {"code": "service_restarted", "message": "The service restarted while this was running; start it again"}
    for t, status in ((Datasets(store), "processing"), (Models(store), "queued"), (Models(store), "running")):
        for r in t.unfinished():
            t.update(r["id"], status="failed", error_json=err)


class FromRunRequest(BaseModel):
    run: str
    name: str | None = None
    seed: int | None = Field(None, description="Only this seed of the run")
    point: str | None = Field(None, description="Only this decision point")
    measured_only: bool = Field(False, description="Leave out warm-up patients")


class ExploreRequest(BaseModel):
    flowchart: FlowchartRef
    points: list[str] | None = Field(None, description="Decision points that choose at random; omit for all of them")
    n: int | None = Field(None, description="Patients per seed; default the world's default_n")
    seeds: list[int] | None = None
    name: str | None = None


class ValidateRequest(BaseModel):
    flowchart: FlowchartRef
    context_fields: list[str] | None = None


def dataset_view(row: dict, full: bool = True, rt: Runtime | None = None) -> dict:
    row = _reconcile(row, rt)
    d = {"id": row["id"], "dataset_id": row["id"], "name": row["name"], "status": row["status"], "job_id": row["job_id"],
         "progress": row["progress"], "message": row.get("message") or "", "source": row["source"],
         "flowchart": None if not row["flowchart_id"] else {"id": row["flowchart_id"], "version": row["flowchart_version"]},
         "rows": row["n_rows"], "patients": row["n_patients"], "content_hash": row["content_hash"],
         "trainable": None if row["trainable"] is None else bool(row["trainable"]), "created_at": row["created_at"],
         "finished_at": row["finished_at"], "error": row["error"], "synthetic_notice": SYNTHETIC_NOTICE}
    rep = row["report"]
    if rep:
        d["summary"] = {"n_errors": rep["n_errors"], "n_warnings": rep["n_warnings"]}
        if full:
            d["report"] = rep
    return d


def _reconcile(row: dict, rt: Runtime | None) -> dict:
    """A job that ended without updating the row (cancelled, crashed worker): say so."""
    if rt is None or row["status"] in FINAL + ("stored",) or not row.get("job_id"):
        return row
    j = rt.job_view(row["job_id"])
    if j and j["status"] in ("failed", "cancelled"):
        err = j.get("error") or {"code": j["status"], "message": f"The job {j['status']}"}
        Datasets(rt.store).update(row["id"], status="failed" if j["status"] == "failed" else "cancelled", error_json=err)
        row = Datasets(rt.store).get(row["project_id"], row["id"])
    return row


def _get(store: Store, p: str, d: str) -> dict:
    row = Datasets(store).get(p, d)
    if row is None:
        raise not_found("dataset", d)
    return row


def _name(store_rows: list[dict], name: str | None, default: str) -> str:
    return (name or default)[:80]


def _flowchart_ref(store: Store, p: str, fid: str | None, version: int | None) -> tuple[str | None, int | None]:
    if fid is None:
        return None, None
    try:
        _doc, info = store.get_version(p, fid, version)
    except NotFound:
        raise not_found("flowchart version", f"{fid}/{version or 'latest'}") from None
    return fid, info["version"]


@router.post("/projects/{p}/datasets", status_code=201)
async def upload_dataset(request: Request, name: str = Query("uploaded dataset", max_length=80), flowchart: str | None = Query(None, description="Flowchart id to check against"),
                         version: int | None = Query(None, description="Its version; default the latest"),
                         format: str | None = Query(None, description="jsonl or csv; default: guessed from the first character"),
                         project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Upload rows as the request body: JSON lines (one decision per line) or CSV (``decision_point, patient_id, t_days, offered,
    chosen``, context as ``ctx.<name>``, earlier steps as ``step.<id>`` with ``+``, ``-``, ``?`` or empty). Always stored; the
    ``report`` lists every problem and ``trainable`` says whether training is allowed. Synthetic data only.
    Uploads are limited by the service's document limit (1 MB by default); larger sets come from a run or an exploration."""
    raw = await request.body()
    try:
        ds = D.Dataset.read(raw.decode("utf-8", "replace"), format)
    except D.DatasetError as e:
        raise ApiError(422, "invalid_dataset", str(e)) from None
    if not len(ds) and not ds.read_problems:
        raise ApiError(422, "invalid_dataset", "The body holds no rows")
    fid, ver = _flowchart_ref(store, project["id"], flowchart, version)
    row = Datasets(store).create(project["id"], name=name, status="processing", flowchart_id=fid, flowchart_version=ver,
                                 source_json={"kind": "upload", "format": format or ("jsonl" if raw.lstrip()[:1] == b"{" else "csv")})
    try:
        finish_dataset(store, project["id"], row["id"], ds, fid, ver, {"kind": "upload", "format": format or "guessed"})
    except ValueError as e:
        Datasets(store).delete(row["id"])
        raise ApiError(422, "invalid_dataset", str(e)) from None
    return dataset_view(Datasets(store).get(project["id"], row["id"]))


def _submit(rt: Runtime, row: dict, fn, args: dict, label: str) -> dict:
    try:
        job = rt.runner.submit("dataset", fn, {"data_dir": str(rt.store.data_dir), "project_id": row["project_id"], "dataset_id": row["id"], **args},
                               label=label, owner={"project": row["project_id"], "kind": "dataset", "id": row["id"]})
    except QueueFull as e:
        Datasets(rt.store).update(row["id"], status="failed", error_json={"code": "queue_full", "message": "too many jobs are waiting"})
        raise ApiError(429, "queue_full", f"Too many jobs are waiting ({e}); try again in a minute") from None
    Datasets(rt.store).update(row["id"], job_id=job.id)
    return Datasets(rt.store).get(row["project_id"], row["id"])


@router.post("/projects/{p}/datasets/from-run", status_code=202)
def dataset_from_run(body: FromRunRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Decisions of a finished run as a dataset (the export of ``GET /runs/{r}/decisions``, without the chooser's probabilities)."""
    run = rt.runs.get(project["id"], body.run)
    if run is None:
        raise not_found("run", body.run)
    if run["status"] != "succeeded":
        raise ApiError(409, "run_not_finished", f"Run {body.run} is {run['status']}; its decisions exist only for a succeeded run")
    if body.seed is not None and body.seed not in run["seeds"]:
        raise ApiError(404, "not_found", f"Run {body.run} has no seed {body.seed}")
    row = Datasets(rt.store).create(project["id"], name=_name([], body.name, f"decisions of {run['label'] or body.run}"), status="processing",
                                    flowchart_id=run["flowchart_id"], flowchart_version=run["flowchart_version"],
                                    source_json={"kind": "run", "run": body.run})
    row = _submit(rt, row, execute_dataset_from_run, {"run_id": body.run, "seed": body.seed, "point": body.point, "measured_only": body.measured_only},
                  f"dataset from run {body.run}")
    return dataset_view(row, full=False, rt=rt)


@router.post("/projects/{p}/datasets/explore", status_code=202)
def explore_dataset(body: ExploreRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Exploration run: the chosen decision points pick at random among what is on offer, the rest follow the flowchart's decision
    policy, and every row is labelled with what happened afterwards. Gives data on options practice rarely takes."""
    store, s = rt.store, rt.settings
    world, _ = store.get_world(project["id"])
    fid, ver = _flowchart_ref(store, project["id"], body.flowchart.id, body.flowchart.version)
    doc, _ = store.get_version(project["id"], fid, ver)
    decisions = {n["id"] for n in doc["nodes"] if n.get("kind") in ("decision", "choice")}
    bad = [p for p in body.points or [] if p not in decisions]
    if bad:
        raise ApiError(422, "unknown_decision_point", f"Not decision points of '{fid}': {bad}; it has {sorted(decisions)}")
    n = int(body.n if body.n is not None else world.get("default_n") or 1000)
    seeds = [int(x) for x in (body.seeds or [1])]
    if n > s.max_patients or len(seeds) > s.max_seeds or len(set(seeds)) != len(seeds) or n < 1:
        raise ApiError(429, "limit_exceeded", f"At most {s.max_patients} patients and {s.max_seeds} different seeds")
    if n < min_patients(world):
        raise ApiError(422, "n_too_small", f"With this world's arrival rate and warm-up, ask for at least {min_patients(world)} patients")
    row = Datasets(store).create(project["id"], name=_name([], body.name, f"exploration of {fid}"), status="processing", flowchart_id=fid,
                                 flowchart_version=ver, source_json={"kind": "exploration"})
    row = _submit(rt, row, execute_exploration, {"fid": fid, "version": ver, "points": body.points, "n": n, "seeds": seeds}, f"exploration {fid} v{ver}")
    return dataset_view(row, full=False, rt=rt)


@router.get("/projects/{p}/datasets")
def list_datasets(project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    return [dataset_view(r, full=False, rt=rt) for r in Datasets(rt.store).list(project["id"])]


@router.get("/projects/{p}/datasets/{d}")
def get_dataset(d: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Metadata and the validation report: per decision point rows, share of each option and of each context value, problems
    (errors stop training, warnings do not), unknown names, duplicates, patients and time range."""
    return dataset_view(_get(rt.store, project["id"], d), rt=rt)


@router.post("/projects/{p}/datasets/{d}/validate")
def validate_dataset(d: str, body: ValidateRequest, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Check the dataset against another flowchart (or version): does it still fit? Nothing is changed."""
    row = _get(store, project["id"], d)
    if row["status"] != "stored":
        raise ApiError(409, "dataset_not_ready", f"The dataset is {row['status']}")
    fid, ver = _flowchart_ref(store, project["id"], body.flowchart.id, body.flowchart.version)
    ds = D.Dataset.from_jsonl(read_lines(store, project["id"], d))
    from ..datasets_core import scenario_for_version
    _, _, _, sc, fc = scenario_for_version(store, project["id"], fid, ver)
    return {"flowchart": {"id": fid, "version": ver}, "report": D.validate(ds, sc, fc, body.context_fields)}


@router.get("/projects/{p}/datasets/{d}/rows")
def dataset_rows(d: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), project: dict = Depends(get_project),
                 store: Store = Depends(get_store)):
    row = _get(store, project["id"], d)
    if row["status"] != "stored":
        raise ApiError(409, "dataset_not_ready", f"The dataset is {row['status']}")
    import json
    out = []
    for i, line in enumerate(read_lines(store, project["id"], d)):
        if i >= offset + limit:
            break
        if i >= offset:
            out.append(json.loads(line))
    return {"offset": offset, "limit": limit, "total": row["n_rows"], "rows": out}


@router.get("/projects/{p}/datasets/{d}/download")
def download_dataset(d: str, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """All rows as JSON lines."""
    row = _get(store, project["id"], d)
    if row["status"] != "stored":
        raise ApiError(409, "dataset_not_ready", f"The dataset is {row['status']}")
    return StreamingResponse(read_lines(store, project["id"], d), media_type="application/x-ndjson")


@router.delete("/projects/{p}/datasets/{d}", status_code=204)
def delete_dataset(d: str, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    row = _get(store, project["id"], d)
    used = store.query_one("SELECT id FROM models WHERE project_id=? AND dataset_id=? LIMIT 1", (project["id"], d))
    if used:
        raise ApiError(409, "dataset_in_use", f"Model {used['id']} was trained on this dataset; delete the model first")
    Datasets(store).delete(row["id"])
    rows_path(store, project["id"], d).unlink(missing_ok=True)

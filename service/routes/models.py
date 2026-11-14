"""Trained models (spec 06): train from a dataset (job), registry, attach to a flowchart as a new version."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

import jev
from pathway_sim.documents import DocumentError, doc_hash, normalise_flowchart_doc

from ..config import Settings
from ..datasets_core import attach, scenario_for_version
from ..datasets_db import FINAL, Datasets, Models
from ..deps import get_project, get_settings, get_store
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..jobs import QueueFull
from ..runtime import Runtime, get_runtime
from ..store import Conflict, NotFound, Store
from ..validation import has_errors, validate_documents
from .runs import FlowchartRef

router = APIRouter(tags=["models"], responses=ERROR_RESPONSES)

TRAINERS = [
    {"id": "frequency", "name": "Counting", "available": True, "output": "stub table",
     "description": "Estimates the probability of each option per context cell by counting (add-one smoothing). The result is a probability "
                    "table you can read and edit on the Decisions screen. Cells with fewer rows than min_cell get no rule of their own.",
     "options": {"context_fields": "group, fast_track, attributes.<name>, history.<step>; default: group and revealed categorical attributes",
                 "min_cell": 30, "smoothing": 1.0}},
    {"id": "local", "name": "Local model (numpy)", "available": True, "output": "model",
     "description": "The small neural model of this repository, trained to imitate the chosen option. It also sees queue state when the rows have it.",
     "options": {"epochs": 25, "model": "dot or correction", "d": 16, "hidden": 32, "max_seconds": 60}},
    {"id": "jev", "name": "JEV", "available": False, "output": "model",
     "description": "Sends the dataset to the team's JEV service. Waits for the JEV API (fork F3)."},
]


def on_startup(app) -> None:      # nothing to start; the module is mounted by its router
    return None


class TrainRequest(BaseModel):
    dataset: str
    trainer: str = "frequency"
    name: str | None = None
    flowchart: FlowchartRef | None = Field(None, description="Train against this flowchart version; default the dataset's")
    context_fields: list[str] | None = None
    decision_points: list[str] | None = None
    settings: dict[str, Any] | None = Field(None, description="Trainer settings, see GET /trainers (min_cell, smoothing, holdout, seed, epochs, ...)")


class AttachRequest(BaseModel):
    model: str
    decision_points: list[str] | None = Field(None, description="Use the model at these decision points; default all it was trained on")
    base_version: int | None = Field(None, description="The version you edited; 409 if it is no longer the latest")


def model_view(rt: Runtime, row: dict, full: bool = True) -> dict:
    row = _reconcile(rt, row)
    d = {"id": row["id"], "model_id": row["id"], "name": row["name"], "trainer": row["trainer"], "kind": row["kind"],
         "dataset": row["dataset_id"], "dataset_hash": row["dataset_hash"], "flowchart": {"id": row["flowchart_id"], "version": row["flowchart_version"]},
         "decision_points": row["decision_points"], "config": row["config"], "status": row["status"], "job_id": row["job_id"],
         "progress": 1.0 if row["status"] == "ready" else (_live(rt, row) or row["progress"]), "message": row.get("message") or "",
         "created": row["created_at"], "finished_at": row["finished_at"], "error": row["error"], "warnings": row["warnings"] or [],
         "evaluation": row["evaluation"], "notice": jev.IMITATION_NOTICE}
    if full and row["status"] == "ready":
        art = rt.store.get_blob(row["project_id"], "models", row["id"])
        if art.get("points") is not None:
            d["table"] = art["points"]                      # a stub table: shown and editable on the Decisions screen
            d["table_info"] = art.get("info")
        else:
            d["artifact_summary"] = {"kind": art.get("kind"), "arch": art.get("arch"), "options": art["layout"]["options"]}
    return d


def _live(rt: Runtime, row: dict):
    j = rt.runner.get(row["job_id"]) if row.get("job_id") else None
    return j.progress if j and row["status"] not in FINAL else None


def _reconcile(rt: Runtime, row: dict) -> dict:
    if row["status"] in FINAL or not row.get("job_id"):
        return row
    j = rt.job_view(row["job_id"])
    if j and j["status"] in ("failed", "cancelled"):
        err = j.get("error") or {"code": j["status"], "message": f"The job {j['status']}"}
        Models(rt.store).update(row["id"], status="failed" if j["status"] == "failed" else "cancelled", error_json=err)
        return Models(rt.store).get(row["project_id"], row["id"])
    return row


def _get(rt: Runtime, p: str, m: str) -> dict:
    row = Models(rt.store).get(p, m)
    if row is None:
        raise not_found("model", m)
    return row


@router.get("/trainers")
def list_trainers():
    """Trainers and whether they are available, with the imitation notice the screen shows next to the train button."""
    return {"trainers": TRAINERS, "notice": jev.IMITATION_NOTICE, "evaluation_label": jev.training.EVAL_LABEL}


@router.post("/projects/{p}/models", status_code=202)
def train_model(body: TrainRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Start a training job. The dataset must have no validation errors. Evaluation is by patient (80/20), labelled agreement with past
    decisions. Learning from decision logs reproduces practice, including its flaws."""
    store, pid = rt.store, project["id"]
    tr = next((t for t in TRAINERS if t["id"] == body.trainer), None)
    if tr is None:
        raise ApiError(422, "unknown_trainer", f"Unknown trainer '{body.trainer}'; use one of {[t['id'] for t in TRAINERS]}")
    if not tr["available"]:
        raise ApiError(422, "trainer_unavailable", tr["description"])
    ds = Datasets(store).get(pid, body.dataset)
    if ds is None:
        raise not_found("dataset", body.dataset)
    if ds["status"] != "stored":
        raise ApiError(409, "dataset_not_ready", f"The dataset is {ds['status']}")
    ref = body.flowchart
    fid = ref.id if ref else ds["flowchart_id"]
    if fid is None:
        raise ApiError(422, "flowchart_needed", "This dataset was stored without a flowchart; say which flowchart to train against")
    try:
        doc, info = store.get_version(pid, fid, ref.version if ref else (ds["flowchart_version"] if fid == ds["flowchart_id"] else None))
    except NotFound:
        raise not_found("flowchart version", fid) from None
    if fid == ds["flowchart_id"] and info["version"] == ds["flowchart_version"] and not ds["trainable"]:
        raise ApiError(409, "dataset_has_errors", "The dataset has validation errors and cannot be trained on; see its report",
                       [{"severity": "error", "code": g["code"], "message": g["message"]} for g in ds["report"]["problems"] if g["severity"] == "error"])
    try:
        cfg = jev.TrainConfig.from_dict({**(body.settings or {}), **({"context_fields": body.context_fields} if body.context_fields is not None else {}),
                                         **({"decision_points": body.decision_points} if body.decision_points is not None else {})})
        cfg = cfg.to_dict()
    except TypeError as e:
        raise ApiError(422, "invalid_request", f"Bad trainer settings: {e}") from None
    row = Models(store).create(pid, name=(body.name or f"{body.trainer} on {ds['name']}")[:80], trainer=body.trainer, dataset_id=ds["id"],
                               dataset_hash=ds["content_hash"], flowchart_id=fid, flowchart_version=info["version"], flowchart_hash=doc_hash(doc),
                               config_json=cfg, status="queued")
    try:
        from ..datasets_core import execute_training
        job = rt.runner.submit("training", execute_training, {"data_dir": str(store.data_dir), "project_id": pid, "model_id": row["id"]},
                               label=f"train {body.trainer}", owner={"project": pid, "kind": "model", "id": row["id"]})
    except QueueFull as e:
        Models(store).update(row["id"], status="failed", error_json={"code": "queue_full", "message": "too many jobs are waiting"})
        raise ApiError(429, "queue_full", f"Too many jobs are waiting ({e}); try again in a minute") from None
    Models(store).update(row["id"], job_id=job.id)
    return model_view(rt, Models(store).get(pid, row["id"]), full=False)


@router.get("/projects/{p}/models")
def list_models(project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    return [model_view(rt, r, full=False) for r in Models(rt.store).list(project["id"])]


@router.get("/projects/{p}/models/{m}")
def get_model(m: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Status, evaluation (agreement with past decisions: log-loss against uniform and option-frequency baselines, calibration in
    bins, per decision point) and, for the counting trainer, the stub ``table``."""
    return model_view(rt, _get(rt, project["id"], m))


@router.get("/projects/{p}/models/{m}/artifact")
def get_artifact(m: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    row = _get(rt, project["id"], m)
    if row["status"] != "ready":
        raise ApiError(409, "model_not_ready", f"The model is {row['status']}")
    return rt.store.get_blob(project["id"], "models", m)


@router.post("/projects/{p}/models/{m}/cancel")
def cancel_model(m: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    row = _get(rt, project["id"], m)
    if row.get("job_id") and row["status"] in ("queued", "running"):
        rt.runner.cancel(row["job_id"])
        try:
            rt.runner.wait(row["job_id"], timeout=5)
        except TimeoutError:
            pass
    return model_view(rt, _get(rt, project["id"], m), full=False)


@router.delete("/projects/{p}/models/{m}", status_code=204)
def delete_model(m: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    row = _get(rt, project["id"], m)
    if row["status"] in ("queued", "running"):
        raise ApiError(409, "model_in_use", "The model is still training; cancel it first")
    Models(rt.store).delete(m)
    rt.store.delete_blob(project["id"], "models", m)


@router.post("/projects/{p}/flowcharts/{f}/attach-model", status_code=201)
def attach_model(f: str, body: AttachRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime),
                 settings: Settings = Depends(get_settings)):
    """Use a trained model at decision points: writes the flowchart's ``decision_policy`` and saves a new version.

    The attach step revalidates against the flowchart as it is now and lists mismatches (options added or removed since training).
    A point with an error is skipped; the call fails if nothing could be attached. The result reproduces the practice in the
    training data, including its flaws; compare it with the current version before relying on it."""
    store, pid = rt.store, project["id"]
    row = _get(rt, pid, body.model)
    if row["status"] != "ready":
        raise ApiError(409, "model_not_ready", f"The model is {row['status']}")
    try:
        doc, info = store.get_version(pid, f, None)
    except NotFound:
        raise not_found("flowchart", f) from None
    if body.base_version is not None and body.base_version != info["version"]:
        raise ApiError(409, "stale_version", f"The latest version of '{f}' is {info['version']}, not {body.base_version}; reload and attach again")
    artifact = store.get_blob(pid, "models", row["id"])
    new, mismatches, attached, skipped = attach(doc, row, artifact, body.decision_points)
    if not attached:
        raise ApiError(422, "model_mismatch", "The model fits none of the requested decision points of this flowchart", mismatches)
    world, _ = store.get_world(pid)
    try:
        new = normalise_flowchart_doc({**new, "world_id": world["id"]})
    except DocumentError as e:
        raise ApiError(422, "invalid_document", str(e), e.problems) from None
    problems = validate_documents(world, [new])
    if has_errors(problems):
        raise ApiError(422, "invalid_document", "The flowchart with the model attached has problems", problems)
    try:
        saved = store.add_version(pid, f, new, settings.max_versions_per_flowchart)
    except Conflict as e:
        raise ApiError(429, e.code, str(e)) from None
    return {"flowchart": {"id": f, "version": saved["version"]}, "parent_version": info["version"], "attached": attached, "skipped": skipped,
            "mismatches": mismatches, "problems": [p for p in problems if p.get("severity") != "error"],
            "trained_on_other_version": (row["flowchart_id"], row["flowchart_version"]) != (f, info["version"]),
            "notice": jev.IMITATION_NOTICE}

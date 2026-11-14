"""Optimisations: start a search, read suggested changes with evidence, apply a subset (spec 05)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from optimiser import ChangeError, apply_changes
from pathway_sim.documents import flowchart_to_document

from ..deps import get_project
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..run_service import start_optimisation, start_run
from ..runs_core import _scenario_for
from ..runtime import Runtime, get_runtime
from ..store import NotFound
from ..validation import has_errors, validate_documents
from .runs import FlowchartRef, run_view

router = APIRouter(tags=["optimisations"], responses=ERROR_RESPONSES)


class Safety(BaseModel):
    tests_tolerance: float = Field(0.02, ge=0, le=1, description="Tests (and invasive procedures) per patient may rise at most this share")
    equity: bool = Field(True, description="No presentation group may get slower or less often on time")


class OptimiseRequest(BaseModel):
    flowchart: FlowchartRef
    allow: list[str] | None = Field(None, description="Change kinds: detach, relax, standardise, fast_track")
    n: int | None = Field(None, description="Patients per cohort; default is the world's default_n")
    train_seeds: list[int] | None = None
    heldout_seeds: list[int] | None = None
    max_changes: int | None = Field(None, description="At most this many accepted changes (default 6)")
    safety: Safety | None = None
    allow_standardise_under_jev: bool = False


class ApplyRequest(BaseModel):
    accept: list[int] | None = Field(None, description="Change numbers to accept; omit for all")
    rerun: bool = Field(True, description="Also run the new version, and its parent, on the held-out patients")
    label: str | None = None


def _get(rt: Runtime, p: str, o: str) -> dict:
    row = rt.opts.get(p, o)
    if row is None:
        raise not_found("optimisation", o)
    return row


def opt_view(rt: Runtime, row: dict, full: bool = True) -> dict:
    live = rt.runner.get(row["job_id"]) if row.get("job_id") else None
    final = row["status"] in ("succeeded", "failed", "cancelled")
    d = {"id": row["id"], "optimisation_id": row["id"], "project_id": row["project_id"], "status": row["status"],
         "job_id": row["job_id"], "flowchart": {"id": row["flowchart_id"], "version": row["flowchart_version"]},
         "settings": row["settings"],
         "progress": 1.0 if row["status"] == "succeeded" else (live.progress if live and not final else row["progress"]),
         "message": (live.message if live and not final else row.get("message")) or "",
         "created_at": row["created_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
         "error": row["error"], "summary": row["summary"], "applied": row["applied"] or []}
    if full and row["status"] == "succeeded":
        try:
            d.update(rt.store.get_blob(row["project_id"], "optimisations", row["id"])["report"])
        except NotFound:
            pass
    return d


@router.post("/projects/{p}/optimisations", status_code=202)
def post_optimisation(body: OptimiseRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Start an optimisation job: search on training patients, report on held-out patients the search never saw."""
    settings = body.model_dump(exclude={"flowchart"}, exclude_none=True)
    row = start_optimisation(rt, project["id"], body.flowchart.id, body.flowchart.version, settings)
    return opt_view(rt, row, full=False)


@router.get("/projects/{p}/optimisations")
def list_optimisations(project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    return [opt_view(rt, r, full=False) for r in rt.opts.list(project["id"])]


@router.get("/projects/{p}/optimisations/{o}")
def get_optimisation(o: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Status; when succeeded also ``changes`` (label, evidence, held-out number after each), ``blocked``,
    ``heldout`` before and after, ``selection_optimism_pp``, ``honesty`` and ``proposed_flowchart``."""
    return opt_view(rt, _get(rt, project["id"], o))


@router.post("/projects/{p}/optimisations/{o}/cancel")
def cancel_optimisation(o: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    row = _get(rt, project["id"], o)
    if row.get("job_id") and row["status"] in ("queued", "running"):
        rt.runner.cancel(row["job_id"])
        try:
            rt.runner.wait(row["job_id"], timeout=5)
        except TimeoutError:
            pass
    return opt_view(rt, _get(rt, project["id"], o), full=False)


@router.post("/projects/{p}/optimisations/{o}/apply")
def apply_optimisation(o: str, body: ApplyRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """New flowchart version from the accepted changes (all by default). Changes that were found together must
    be accepted together (409 ``linked_change`` names the partner). With ``rerun`` (default) the new version and its
    parent are run on the held-out patients; compare the two runs with ``POST /compare``."""
    pid = project["id"]
    row = _get(rt, pid, o)
    if row["status"] != "succeeded":
        raise ApiError(409, "optimisation_not_finished", f"Optimisation {o} is {row['status']}; there is nothing to apply yet")
    saved = rt.store.get_blob(pid, "optimisations", o)
    spec = rt.store.get_blob(pid, "optspec", o)
    sc, fc0, parent_doc = _scenario_for(spec)
    steps, report = saved["steps"], saved["report"]
    try:
        new_fc = apply_changes(sc, fc0, steps, body.accept, new_id=parent_doc["id"])
    except ChangeError as e:
        raise ApiError(409, e.code, e.message, [e.to_dict()]) from None
    world = spec["world"]
    doc = flowchart_to_document(new_fc, world.get("id"))
    ui = {n["id"]: n["ui"] for n in parent_doc.get("nodes", []) if n.get("ui")}
    for n in doc["nodes"]:
        if n["id"] in ui:
            n["ui"] = ui[n["id"]]
    for k in ("name", "description"):
        if parent_doc.get(k):
            doc[k] = parent_doc[k]
    if (parent_doc.get("decision_policy") or {}).get("backend", "rule") != "rule":
        doc["decision_policy"] = parent_doc["decision_policy"]      # structural changes only; the JEV tables stay as they were
    accepted = sorted(set(range(len(steps)) if body.accept is None else body.accept))
    doc["edits_from_parent"] = [{"index": i, "kind": steps[i]["kind"], "target": steps[i]["target"], "other": steps[i]["other"],
                                 "label": report["changes"][i]["label"], "optimisation": o} for i in accepted]
    problems = validate_documents(world, [doc])
    if has_errors(problems):
        raise ApiError(422, "invalid_document", "The accepted changes give a flowchart with problems", problems)
    fid = parent_doc["id"]
    try:
        saved_doc = rt.store.add_version(pid, fid, doc, max_versions=rt.settings.max_versions_per_flowchart)
    except NotFound:
        raise not_found("flowchart", fid) from None
    version = saved_doc["version"]
    out: dict[str, Any] = {"flowchart": {"id": fid, "version": version}, "based_on": {"id": fid, "version": row["flowchart_version"]},
                           "accepted": accepted, "edits_from_parent": doc["edits_from_parent"]}
    if body.rerun:
        s = spec["settings"]
        common = dict(n=s["n"], seeds=s["heldout_seeds"], policy=None)
        base_run, _ = start_run(rt, pid, fid, row["flowchart_version"], label="before (held-out patients)",
                                source={"optimisation": o, "role": "baseline"}, **common)
        new_run, _ = start_run(rt, pid, fid, version, label=body.label or f"after {len(accepted)} accepted change(s)",
                               source={"optimisation": o, "role": "rerun", "accepted": accepted}, **common)
        out.update({"run_id": new_run["id"], "baseline_run_id": base_run["id"], "run": run_view(rt, new_run, full=False),
                    "baseline_run": run_view(rt, base_run, full=False)})
    applied = (row["applied"] or []) + [{"accepted": accepted, "flowchart": out["flowchart"], "run_id": out.get("run_id")}]
    rt.opts.update(o, applied_json=json.dumps(applied))
    return out

"""Runs: start, list, get, cancel; metrics, dashboard bundle, decisions export, patient log, flow; compare (spec 03).

A run is fully described by (world, flowchart version, decision policy, n, seeds, engine version). Asking for
the same thing twice returns the first run (``cached: true``), also while it is still running.
"""

from __future__ import annotations

import gzip
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..deps import get_project
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..run_service import start_run
from ..runs_core import (FLOW_DEFAULT_SAMPLE, FLOW_MAX_PATIENTS, _scenario_for, build_bundle, compute_flow, read_lines,
                         stream_path)
from ..runtime import Runtime, drop_runtime, ensure_runtime, get_runtime
from ..store import NotFound

router = APIRouter(tags=["runs"], responses=ERROR_RESPONSES)


def on_startup(app) -> None:
    ensure_runtime(app)


def on_shutdown(app) -> None:
    drop_runtime(app)


class FlowchartRef(BaseModel):
    id: str
    version: int | None = Field(None, description="Version number; omit for the latest")


class RunRequest(BaseModel):
    flowchart: FlowchartRef
    n: int | None = Field(None, description="Patients per seed; default is the world's default_n")
    seeds: list[int] | None = Field(None, description="One cohort per seed; default [1]")
    decision_policy: dict[str, Any] | None = Field(None, description="Overrides the policy stored in the flowchart version, for this run only")
    label: str | None = None


class CompareRequest(BaseModel):
    runs: list[str] = Field(min_length=2, max_length=2, description="[baseline run id, other run id]")


# ------------------------------------------------------------------------------------------ views
def run_view(rt: Runtime, row: dict, full: bool = True) -> dict:
    live = rt.runner.get(row["job_id"]) if row.get("job_id") else None
    final = row["status"] in ("succeeded", "failed", "cancelled")
    d = {"id": row["id"], "run_id": row["id"], "project_id": row["project_id"], "label": row["label"] or "",
         "flowchart": {"id": row["flowchart_id"], "version": row["flowchart_version"]},
         "n": row["n"], "seeds": row["seeds"], "decision_policy": row["policy"], "status": row["status"], "job_id": row["job_id"],
         "progress": 1.0 if row["status"] == "succeeded" else (live.progress if live and not final else row["progress"]),
         "message": (live.message if live and not final else row.get("message")) or "",
         "created_at": row["created_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
         "error": row["error"], "headline": row["headline"], "per_seed": row["per_seed"],
         "engine_version": row["engine_version"], "world_rev": row["world_rev"], "patients_key": row["patients_key"],
         "source": row["source"]}
    if full:
        d["metrics"] = row["metrics"]
        d["resources"] = row["resources"]
    return d


def _get_run(rt: Runtime, p: str, r: str) -> dict:
    row = rt.runs.get(p, r)
    if row is None:
        raise not_found("run", r)
    return row


def _finished(row: dict) -> dict:
    if row["status"] != "succeeded":
        raise ApiError(409, "run_not_finished", f"Run {row['id']} is {row['status']}; results exist only for a succeeded run")
    return row


# ------------------------------------------------------------------------------------------ routes
@router.post("/projects/{p}/runs", status_code=202)
def post_run(body: RunRequest, response: Response, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Start a run (202), or return the identical run that already exists (200, ``cached: true``)."""
    row, created = start_run(rt, project["id"], body.flowchart.id, body.flowchart.version, body.n, body.seeds,
                             body.decision_policy, body.label)
    if not created:
        response.status_code = 200
    return {**run_view(rt, row, full=False), "cached": not created}


@router.get("/projects/{p}/runs")
def list_runs(flowchart: str | None = Query(None, description="Only runs of this flowchart id"),
              brief: bool = Query(False, description="Leave out the full metrics (the headline stays)"),
              project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    return [run_view(rt, r, full=not brief) for r in rt.runs.list(project["id"], flowchart)]


@router.get("/projects/{p}/runs/{r}")
def get_run(r: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    return run_view(rt, _get_run(rt, project["id"], r))


@router.post("/projects/{p}/runs/{r}/cancel")
def cancel_run(r: str, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    row = _get_run(rt, project["id"], r)
    if row.get("job_id") and row["status"] in ("queued", "running"):
        rt.runner.cancel(row["job_id"])
        try:
            rt.runner.wait(row["job_id"], timeout=5)
        except TimeoutError:
            pass
    return run_view(rt, _get_run(rt, project["id"], r), full=False)


@router.get("/projects/{p}/runs/{r}/bundle")
def get_bundle(r: str, compare_to: str | None = Query(None, description="Run id to use as the dashboard's 'before'"),
               project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """The result in the dashboard bundle format (``demo/README.md``). With ``compare_to`` that run is the baseline
    and this run the variant, so the dashboard's before and after screens show the comparison."""
    pid = project["id"]
    row = _finished(_get_run(rt, pid, r))
    if compare_to is None:
        try:
            return rt.store.get_blob(pid, "bundles", r)
        except NotFound:
            raise not_found("bundle", r) from None
    other = _finished(_get_run(rt, pid, compare_to))
    sc, fc, _ = _scenario_for(rt.store.get_blob(pid, "runspec", r))
    osc, ofc, _ = _scenario_for(rt.store.get_blob(pid, "runspec", compare_to))
    return build_bundle(sc, fc, row["label"] or r, row["metrics"], title=sc.raw.get("name"),
                        baseline={"label": other["label"] or compare_to, "metrics": other["metrics"], "sc": osc, "fc": ofc})


def _gunzip_lines(path):
    with gzip.open(path, "rb") as f:
        yield from f


@router.get("/projects/{p}/runs/{r}/decisions")
def get_decisions(r: str, seed: int | None = None, point: str | None = None, measured_only: bool = False,
                  project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Every decision in the run as dataset rows (spec 06), JSON lines. Filter by seed or decision point."""
    pid = project["id"]
    row = _finished(_get_run(rt, pid, r))
    seeds = [s for s in row["seeds"] if seed is None or s == seed]
    if not seeds:
        raise ApiError(404, "not_found", f"Run {r} has no seed {seed}")

    def gen():
        for s in seeds:
            for line in _gunzip_lines(stream_path(rt.store, pid, "decisions", f"{r}_s{s}")):
                if point is None and not measured_only:
                    yield line
                    continue
                d = json.loads(line)
                if (point is None or d["decision_point"] == point) and (not measured_only or d.get("measured")):
                    yield line
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.get("/projects/{p}/runs/{r}/patients")
def get_patients(r: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), seed: int | None = None,
                 project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Patient-level log (events with times and results, choices with the offered probabilities), paged, one seed."""
    pid = project["id"]
    row = _finished(_get_run(rt, pid, r))
    seed = row["seeds"][0] if seed is None else seed
    if seed not in row["seeds"]:
        raise ApiError(404, "not_found", f"Run {r} has no seed {seed}")
    path = stream_path(rt.store, pid, "runlogs", f"{r}_s{seed}")
    return {"run_id": r, "seed": seed, "offset": offset, "limit": limit, "total": row["n"],
            "patients": list(read_lines(path, offset, limit))}


@router.get("/projects/{p}/runs/{r}/flow")
def get_flow(r: str, sample: int | None = Query(None, ge=1, le=2000, description="Patients in the playback cohort (default 300)"),
             sample_seed: int | None = Query(None, ge=0, description="Seed of the playback sample (default 0)"),
             seeds: list[int] | None = Query(None, description="Only these seeds of the run"),
             project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Flow document (``flow/1``, ``docs/platform/flow-format.md``): per-step and per-edge counts, waits, critical-path
    share, queues, decision shares and a sampled cohort of patient traces for playback. Counts cover every measured
    patient of the run's seeds, so the totals equal the run's metrics. The stored document (sample 300, seed 0) is
    served as is; another sample size, sample seed or seed subset re-simulates the run (same patients, a few seconds,
    refused above 60,000 patients)."""
    pid = project["id"]
    row = _finished(_get_run(rt, pid, r))
    default = sample in (None, FLOW_DEFAULT_SAMPLE) and sample_seed in (None, 0) and not seeds
    if default:
        try:
            return rt.store.get_blob(pid, "flows", r)
        except NotFound:
            pass   # a run too large to keep in memory: fall through to the resimulation (which will refuse)
    use = [s for s in row["seeds"] if not seeds or s in seeds]
    if not use:
        raise ApiError(404, "not_found", f"Run {r} has none of the seeds {seeds}")
    if len(use) * row["n"] > FLOW_MAX_PATIENTS:
        raise ApiError(422, "flow_too_large", f"The flow of {len(use) * row['n']} patients is too large to rebuild on request "
                                              f"(limit {FLOW_MAX_PATIENTS}); ask for fewer seeds")
    spec = rt.store.get_blob(pid, "runspec", r)
    return compute_flow(spec, sample or FLOW_DEFAULT_SAMPLE, sample_seed or 0, use)


# ------------------------------------------------------------------------------------------ compare
def _delta(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return {"a": a, "b": b, "delta": round(b - a, 4)}
    return {"a": a, "b": b, "delta": None}


METRICS = ("share_within_target", "median_days_to_treatment", "median_days_to_diagnosis", "mean_days_to_treatment",
           "missed_cancers", "untreated_cancers", "stuck", "tests_per_patient", "invasive_per_patient", "cost_per_patient",
           "median_days_to_exit_noncancer")


def compare_metrics(ma: dict, mb: dict) -> dict:
    out = {"headline": {k: _delta(ma.get(k), mb.get(k)) for k in METRICS},
           "by_group": {}, "stages": {}, "nodes": {}, "utilisation": {}}
    for g in sorted(set(ma.get("by_group") or {}) | set(mb.get("by_group") or {})):
        ga, gb = (ma.get("by_group") or {}).get(g) or {}, (mb.get("by_group") or {}).get(g) or {}
        out["by_group"][g] = {k: _delta(ga.get(k), gb.get(k))
                              for k in ("n_cancer", "median_days_to_treatment", "share_within_target", "median_days_to_diagnosis", "missed_cancers")}
    for st in sorted(set(ma.get("stage_breakdown") or {}) | set(mb.get("stage_breakdown") or {})):
        sa, sb = (ma.get("stage_breakdown") or {}).get(st) or {}, (mb.get("stage_breakdown") or {}).get(st) or {}
        out["stages"][st] = {k: _delta(sa.get(k), sb.get(k)) for k in ("wait", "service")}
    for nd in sorted(set(ma.get("node_breakdown") or {}) | set(mb.get("node_breakdown") or {})):
        na, nb = (ma.get("node_breakdown") or {}).get(nd) or {}, (mb.get("node_breakdown") or {}).get(nd) or {}
        out["nodes"][nd] = {k: _delta(na.get(k, 0.0 if nb else None), nb.get(k, 0.0 if na else None)) for k in ("wait", "service")}
    for rid in sorted(set(ma.get("utilisation") or {}) | set(mb.get("utilisation") or {})):
        out["utilisation"][rid] = _delta((ma.get("utilisation") or {}).get(rid), (mb.get("utilisation") or {}).get(rid))
    return out


@router.post("/projects/{p}/compare")
def compare(body: CompareRequest, project: dict = Depends(get_project), rt: Runtime = Depends(get_runtime)):
    """Metric deltas between two finished runs (b minus a). Refuses runs on different patients with 409."""
    pid = project["id"]
    a, b = (_finished(_get_run(rt, pid, x)) for x in body.runs)
    if a["patients_key"] != b["patients_key"]:
        why = []
        if a["n"] != b["n"]:
            why.append(f"different n ({a['n']} and {b['n']})")
        if a["seeds"] != b["seeds"]:
            why.append(f"different seeds ({a['seeds']} and {b['seeds']})")
        if a["world_rev"] != b["world_rev"] or not why:
            why.append("a different world (its tables were edited between the runs)" if a["world_rev"] != b["world_rev"] else "a different engine version")
        raise ApiError(409, "different_patients",
                       "These runs simulate different patients, so a difference could be noise: " + "; ".join(why))
    return {"same_patients": True, "n": a["n"], "seeds": a["seeds"],
            "a": {**run_view_min(a)}, "b": {**run_view_min(b)}, **compare_metrics(a["metrics"], b["metrics"])}


def run_view_min(row: dict) -> dict:
    return {"id": row["id"], "label": row["label"] or "", "flowchart": {"id": row["flowchart_id"], "version": row["flowchart_version"]},
            "headline": row["headline"]}

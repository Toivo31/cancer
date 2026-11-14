"""Jobs: status, progress, log tail and cancel for any background job (spec 03)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..errors import ERROR_RESPONSES, not_found
from ..runtime import Runtime, get_runtime

router = APIRouter(tags=["jobs"], responses=ERROR_RESPONSES)


@router.get("/jobs")
def list_jobs(status: str | None = Query(None, description="queued, running, succeeded, failed or cancelled"),
              rt: Runtime = Depends(get_runtime)):
    """Jobs known to this service process (newest first), plus counts."""
    jobs = sorted(rt.runner.list(status), key=lambda j: -j.created)
    return {"counts": rt.runner.counts(), "jobs": [j.to_dict(include_result=False) for j in jobs]}


@router.get("/jobs/{j}")
def get_job(j: str, rt: Runtime = Depends(get_runtime)):
    """``{id, kind, status, state, progress 0..1, message, error, log_tail, result, owner}``. Poll about once a second."""
    d = rt.job_view(j)
    if d is None:
        raise not_found("job", j)
    return d


@router.post("/jobs/{j}/cancel")
def cancel_job(j: str, rt: Runtime = Depends(get_runtime)):
    """Cancel a queued or running job (idempotent; a finished job is returned unchanged)."""
    if rt.runner.get(j) is None:
        d = rt.job_view(j)
        if d is None:
            raise not_found("job", j)
        return d
    rt.runner.cancel(j)
    try:
        rt.runner.wait(j, timeout=5)
    except TimeoutError:
        pass
    return rt.job_view(j)

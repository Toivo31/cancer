"""The job side of the service: one runner per app, run/optimisation tables, hooks that keep rows honest.

``get_runtime(request)`` is the dependency routes use. The runner lives in memory, so run the service
as ONE process (uvicorn without ``--workers``); job processes are children of that process. On start-up
anything left ``queued`` or ``running`` by a previous process is marked failed (``service_restarted``).
"""

from __future__ import annotations

import json
import shutil
import threading

from fastapi import Request

from .deps import Services
from .jobs import Job, JobRunner
from .runs_db import JobRows, Optimisations, Runs
from .store import now

_LOCK = threading.Lock()
PARTIAL_KINDS = ("runlogs", "decisions", "bundles", "metrics", "flows")


class Runtime:
    def __init__(self, services: Services):
        self.services = services
        self.store = services.store
        self.settings = services.settings
        self.runs = Runs(self.store)
        self.opts = Optimisations(self.store)
        self.jobrows = JobRows(self.store)
        self.runner = JobRunner(max_workers=self.settings.max_jobs, default_timeout=self.settings.job_seconds,
                                persist=self.jobrows.save, on_finish=self._on_finish)
        self.reconcile()

    # ------------------------------------------------------------------ start-up and shutdown
    def reconcile(self) -> None:
        reason = "The service restarted while this was running; start it again"
        err = json.dumps({"code": "service_restarted", "message": reason})
        for r in self.runs.unfinished():
            self.runs.update(r["id"], status="failed", finished_at=now(), error_json=err)
        for o in self.opts.unfinished():
            self.opts.update(o["id"], status="failed", finished_at=now(), error_json=err)
        self.jobrows.fail_unfinished(reason)

    def shutdown(self) -> None:
        self.runner.shutdown()

    # ------------------------------------------------------------------ job hook
    def _on_finish(self, job: Job) -> None:
        """Runs in the supervisor thread when a job ends. The job function marks its own success; this
        covers everything it cannot: failure, cancel, timeout, a crashed worker."""
        owner = job.owner or {}
        pid, oid = owner.get("project"), owner.get("id")
        if not pid or not oid:
            return
        err = json.dumps(job.error) if job.error else None
        if owner.get("kind") == "run":
            row = self.runs.get(pid, oid)
            if row and row["status"] != "succeeded":
                status = "cancelled" if job.status == "cancelled" else "failed"
                self.runs.update(oid, status=status, finished_at=now(), error_json=err, message=job.message)
                self.clean_partial(pid, oid)
            elif row is None:
                self.clean_partial(pid, oid)
        elif owner.get("kind") == "optimisation":
            row = self.opts.get(pid, oid)
            if row and row["status"] != "succeeded":
                status = "cancelled" if job.status == "cancelled" else "failed"
                self.opts.update(oid, status=status, finished_at=now(), error_json=err, message=job.message)

    def clean_partial(self, project_id: str, run_id: str) -> None:
        base = self.store.blob_dir / project_id
        for kind in PARTIAL_KINDS:
            d = base / kind
            if d.exists():
                for f in d.glob(f"{run_id}*"):
                    f.unlink(missing_ok=True)

    # ------------------------------------------------------------------ views
    def job_view(self, job_id: str) -> dict | None:
        j = self.runner.get(job_id)
        if j is not None:
            return j.to_dict()
        return self.jobrows.get(job_id)


def ensure_runtime(app) -> Runtime:
    with _LOCK:
        rt = getattr(app.state, "runtime", None)
        if rt is None:
            rt = app.state.runtime = Runtime(app.state.services)
        return rt


def drop_runtime(app) -> None:
    with _LOCK:
        rt = getattr(app.state, "runtime", None)
        if rt is not None:
            rt.shutdown()
            app.state.runtime = None


def get_runtime(request: Request) -> Runtime:
    return ensure_runtime(request.app)


def purge_project_files(store, project_id: str) -> None:   # pragma: no cover - used by project deletion tooling
    shutil.rmtree(store.blob_dir / project_id, ignore_errors=True)

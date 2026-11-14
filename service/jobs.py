"""Background job runner: one OS process per job, with progress, cancel, time limits and crash isolation.

Why a process per job rather than a ``ProcessPoolExecutor``: a pool cannot cancel or time out a
running task, and a worker that dies (out of memory, segfault) breaks the whole pool and fails every
other job. Here a job is a ``multiprocessing`` process started from a *forkserver* (clean, fast, safe
with the service's threads); at most ``max_workers`` run at once, the rest wait in a queue.

Usage::

    runner = JobRunner(max_workers=2)
    job = runner.submit("run", my_function, {"n": 100}, label="demo")
    runner.get(job.id).to_dict()          # status, progress 0..1, message, log tail, result, error
    runner.cancel(job.id)

``my_function(ctx, **args)`` must be a module-level function (it is pickled by name) and ``args`` and
the return value must be small JSON-able dicts. Large outputs are written to disk by the job itself
and referred to from the result. ``ctx.progress(done, total, message=None)`` reports progress,
``ctx.log(line)`` adds a log line. Raising in the function fails that job only.

States: ``queued`` -> ``running`` -> ``succeeded`` | ``failed`` | ``cancelled``.

The runner keeps jobs in memory and calls ``persist(job_dict)`` on every state change and
``on_finish(job)`` once when a job reaches a final state, so the service can mirror rows into its
store and update the run or optimisation that owns the job.
"""

from __future__ import annotations

import collections
import multiprocessing as mp
import os
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

FINAL = ("succeeded", "failed", "cancelled")
LOG_TAIL = 40
PROGRESS_MIN_INTERVAL = 0.1   # seconds between progress messages sent by a job


class QueueFull(Exception):
    """Too many jobs waiting (the service answers 429)."""


class JobCancelled(Exception):
    """Raised inside a job when ``ctx.check_cancel()`` finds the cancel flag (cooperative cancel)."""


@dataclass
class Job:
    id: str
    kind: str
    label: str = ""
    status: str = "queued"
    progress: float = 0.0
    message: str = ""
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    error: dict | None = None            # {"code", "message", "traceback"?}
    result: dict | None = None
    log: collections.deque = field(default_factory=lambda: collections.deque(maxlen=LOG_TAIL))
    owner: dict = field(default_factory=dict)   # free-form back-reference, e.g. {"project": p, "run": r}
    published: bool = True   # False between reaching a final state and the on_finish hook returning

    @property
    def shown(self) -> str:
        """Status as clients see it: a final state is shown only after ``on_finish`` has updated the owner's row,
        so "job finished" always means "the run row says so too"."""
        return self.status if self.published or self.status not in FINAL else "running"

    def to_dict(self, include_result: bool = True) -> dict:
        shown = self.shown
        d = {"id": self.id, "kind": self.kind, "label": self.label, "status": shown, "state": shown,
             "progress": round(self.progress if shown in FINAL else min(self.progress, 0.999), 4), "message": self.message,
             "created": self.created, "started": self.started, "finished": self.finished if shown in FINAL else None,
             "error": self.error if shown in FINAL else None, "log_tail": list(self.log), "owner": self.owner}
        if include_result:
            d["result"] = self.result if shown in FINAL else None
        return d


class JobContext:
    """Handed to the job function inside the worker process."""

    def __init__(self, conn, cancel_event=None):
        self._conn = conn
        self._last = 0.0
        self._cancel_event = cancel_event

    def _send(self, msg: tuple) -> None:
        try:
            self._conn.send(msg)
        except (BrokenPipeError, OSError):
            os._exit(1)   # the parent is gone; nothing left to report to

    def progress(self, done: float, total: float = 1.0, message: str | None = None, force: bool = False) -> None:
        now = time.monotonic()
        if not force and done < total and now - self._last < PROGRESS_MIN_INTERVAL:
            return
        self._last = now
        frac = 0.0 if not total else max(0.0, min(1.0, done / total))
        self._send(("progress", frac, message))

    def log(self, line: str) -> None:
        self._send(("log", str(line)[:500]))

    def check_cancel(self) -> None:
        if self._cancel_event is not None and self._cancel_event.is_set():
            raise JobCancelled()


def _worker(conn, cancel_event, fn: Callable, args: dict) -> None:
    ctx = JobContext(conn, cancel_event)
    try:
        result = fn(ctx, **args)
        ctx._send(("result", result if isinstance(result, dict) else {"value": result}))
    except JobCancelled:
        ctx._send(("cancelled",))
    except BaseException as e:   # noqa: BLE001 - any failure is reported, never raised into the pool
        code = getattr(e, "code", None) or type(e).__name__
        ctx._send(("error", {"code": str(code), "message": str(e)[:2000],
                             "traceback": traceback.format_exc()[-4000:]}))
    finally:
        try:
            conn.close()
        except OSError:
            pass


class JobRunner:
    def __init__(self, max_workers: int | None = None, max_queued: int = 100, default_timeout: float = 15 * 60,
                 start_method: str | None = None, persist: Callable[[dict], None] | None = None,
                 on_finish: Callable[[Job], None] | None = None, kill_grace: float = 2.0,
                 preload: tuple[str, ...] = ("numpy", "pathway_sim", "optimiser")):
        self.max_workers = max(1, int(max_workers or os.cpu_count() or 1))
        self.max_queued = max_queued
        self.default_timeout = default_timeout
        self.kill_grace = kill_grace
        self.persist = persist
        self.on_finish = on_finish
        method = start_method or os.environ.get("PATHWAY_JOB_START", "forkserver")
        if method not in mp.get_all_start_methods():
            method = "spawn"
        self._ctx = mp.get_context(method)
        if method == "forkserver":
            try:
                self._ctx.set_forkserver_preload(list(preload))
            except Exception:   # noqa: BLE001 - preload is an optimisation only
                pass
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._queue: collections.deque = collections.deque()    # (job, fn, args, timeout)
        self._procs: dict[str, Any] = {}
        self._cancel_requested: set[str] = set()
        self._closed = False

    # ------------------------------------------------------------------ public API
    def submit(self, kind: str, fn: Callable, args: dict | None = None, label: str = "",
               timeout: float | None = None, owner: dict | None = None) -> Job:
        with self._lock:
            if self._closed:
                raise RuntimeError("job runner is shut down")
            if len(self._queue) >= self.max_queued:
                raise QueueFull(f"{len(self._queue)} jobs are already waiting")
            job = Job(id="j_" + uuid.uuid4().hex[:8], kind=kind, label=label, owner=dict(owner or {}))
            self._jobs[job.id] = job
            self._queue.append((job, fn, dict(args or {}), timeout or self.default_timeout))
            self._save(job)
        self._pump()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, status: str | None = None) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if status is None or j.shown == status]

    def cancel(self, job_id: str) -> Job | None:
        """Queued job: cancelled at once. Running job: its process is stopped. Finished job: unchanged."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in FINAL:
                return job
            if job.status == "queued":
                self._queue = collections.deque(q for q in self._queue if q[0].id != job_id)
                self._finish(job, "cancelled", message="cancelled before it started")
                return job
            self._cancel_requested.add(job_id)
        return job

    def wait(self, job_id: str, timeout: float = 60.0, poll: float = 0.02) -> Job:
        """Block until the job is final (for tests and scripts)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            job = self.get(job_id)
            if job is None or job.shown in FINAL:
                return job
            time.sleep(poll)
        raise TimeoutError(f"job {job_id} still {self.get(job_id).status} after {timeout}s")

    def counts(self) -> dict:
        with self._lock:
            c = collections.Counter(j.shown for j in self._jobs.values())
        return {s: c.get(s, 0) for s in ("queued", "running", "succeeded", "failed", "cancelled")}

    def shutdown(self, cancel_running: bool = True) -> None:
        with self._lock:
            self._closed = True
            for job, *_ in list(self._queue):
                self._finish(job, "cancelled", message="service shut down")
            self._queue.clear()
            ids = list(self._procs)
        if cancel_running:
            for jid in ids:
                self.cancel(jid)
            end = time.monotonic() + self.kill_grace + 3
            while time.monotonic() < end and self._procs:
                time.sleep(0.02)

    # ------------------------------------------------------------------ internals
    def _save(self, job: Job) -> None:
        if self.persist:
            try:
                self.persist(job.to_dict())
            except Exception:   # noqa: BLE001 - a store problem must not kill the supervisor
                pass

    def _finish(self, job: Job, status: str, error: dict | None = None, result: dict | None = None,
                message: str | None = None) -> None:
        with self._lock:
            if job.status in FINAL:
                return
            job.published = self.on_finish is None
            job.status, job.finished = status, time.time()
            if error:
                job.error = error
            if result is not None:
                job.result = result
            if status == "succeeded":
                job.progress = 1.0
            if message is not None:
                job.message = message
        if self.on_finish:
            try:
                self.on_finish(job)
            except Exception as e:   # noqa: BLE001
                job.log.append(f"on_finish hook failed: {e}")
            job.published = True
        self._save(job)

    def _pump(self) -> None:
        with self._lock:
            while self._queue and len(self._procs) < self.max_workers and not self._closed:
                job, fn, args, timeout = self._queue.popleft()
                if job.status != "queued":
                    continue
                parent, child = self._ctx.Pipe(duplex=False)
                cancel_event = self._ctx.Event()
                proc = self._ctx.Process(target=_worker, args=(child, cancel_event, fn, args),
                                         name=f"job-{job.id}", daemon=True)
                try:
                    proc.start()
                except Exception as e:   # noqa: BLE001 - e.g. the function is not picklable
                    child.close()
                    parent.close()
                    self._finish(job, "failed", error={"code": "start_failed", "message": str(e)[:500]})
                    continue
                child.close()
                job.status, job.started = "running", time.time()
                self._procs[job.id] = proc
                self._save(job)
                threading.Thread(target=self._supervise, args=(job, proc, parent, cancel_event, timeout),
                                 name=f"supervise-{job.id}", daemon=True).start()

    def _supervise(self, job: Job, proc, conn, cancel_event, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        outcome: tuple | None = None
        killed_for: str | None = None
        try:
            while True:
                try:
                    if conn.poll(0.05):
                        msg = conn.recv()
                        kind = msg[0]
                        if kind == "progress":
                            job.progress = float(msg[1])
                            if msg[2] is not None:
                                job.message = msg[2]
                        elif kind == "log":
                            job.log.append(msg[1])
                        else:
                            outcome = msg
                            break
                        continue
                except (EOFError, OSError):
                    break   # the process ended without a final message
                if job.id in self._cancel_requested:
                    cancel_event.set()
                    killed_for = "cancelled"
                    break
                if time.monotonic() > deadline:
                    killed_for = "timeout"
                    break
                if not proc.is_alive() and not conn.poll(0):
                    break
            if killed_for:
                self._stop(proc)
            else:
                proc.join(self.kill_grace)
                if proc.is_alive():
                    self._stop(proc)
            code = proc.exitcode
            if killed_for == "cancelled":
                self._finish(job, "cancelled", message="cancelled")
            elif killed_for == "timeout":
                self._finish(job, "failed", error={"code": "timeout", "message": f"stopped after the {int(timeout)} s time limit"})
            elif outcome is None:
                self._finish(job, "failed", error={"code": "worker_died",
                                                   "message": f"the worker process ended unexpectedly (exit code {code})"})
            elif outcome[0] == "result":
                self._finish(job, "succeeded", result=outcome[1])
            elif outcome[0] == "cancelled":
                self._finish(job, "cancelled", message="cancelled")
            else:
                self._finish(job, "failed", error=outcome[1])
        except Exception as e:   # noqa: BLE001 - the supervisor itself must always reach a final state
            self._finish(job, "failed", error={"code": "supervisor_error", "message": str(e)[:500]})
        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self._lock:
                self._procs.pop(job.id, None)
                self._cancel_requested.discard(job.id)
            self._pump()

    def _stop(self, proc) -> None:
        if proc.is_alive():
            proc.terminate()
            proc.join(self.kill_grace)
        if proc.is_alive():
            proc.kill()
            proc.join(2)

"""Tables for runs, optimisations and job rows (added to the store with ``Store.ensure_schema``).

All access goes through short transactions, so request threads and job processes can use it at the
same time. The unique partial index on ``runs`` is what makes two users starting the same run end up
with one run: the second insert finds the first (``Runs.create_or_get``).
"""

from __future__ import annotations

import json
import sqlite3

from .store import Store, new_id, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_key TEXT NOT NULL, patients_key TEXT NOT NULL, label TEXT,
    flowchart_id TEXT NOT NULL, flowchart_version INTEGER NOT NULL,
    n INTEGER NOT NULL, seeds_json TEXT NOT NULL, policy_json TEXT,
    status TEXT NOT NULL, job_id TEXT, progress REAL NOT NULL DEFAULT 0, message TEXT,
    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
    error_json TEXT, metrics_json TEXT, headline_json TEXT, per_seed_json TEXT, resources_json TEXT,
    engine_version TEXT NOT NULL, world_rev INTEGER, source_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS runs_live_key ON runs(project_id, run_key)
    WHERE status IN ('queued', 'running', 'succeeded');
CREATE INDEX IF NOT EXISTS runs_by_project ON runs(project_id, created_at);
CREATE TABLE IF NOT EXISTS optimisations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    flowchart_id TEXT NOT NULL, flowchart_version INTEGER NOT NULL,
    settings_json TEXT NOT NULL, status TEXT NOT NULL, job_id TEXT, progress REAL NOT NULL DEFAULT 0, message TEXT,
    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error_json TEXT, summary_json TEXT,
    applied_json TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, project_id TEXT, kind TEXT NOT NULL, label TEXT, status TEXT NOT NULL,
    progress REAL, message TEXT, created REAL, started REAL, finished REAL,
    error_json TEXT, result_json TEXT, log_json TEXT, owner_json TEXT);
"""

RUN_JSON = ("seeds_json", "policy_json", "error_json", "metrics_json", "headline_json", "per_seed_json",
            "resources_json", "source_json")


def _loads(row: dict, cols) -> dict:
    out = dict(row)
    for c in cols:
        if c in out:
            v = out.pop(c)
            out[c[:-5]] = json.loads(v) if v else None
    return out


class _Base:
    table = ""

    def __init__(self, store: Store):
        self.store = store

    def update(self, ident: str, **cols) -> None:
        if not cols:
            return
        sets = ", ".join(f"{k}=?" for k in cols)
        self.store.execute(f"UPDATE {self.table} SET {sets} WHERE id=?", (*cols.values(), ident))


class Runs(_Base):
    table = "runs"

    def __init__(self, store: Store):
        super().__init__(store)
        store.ensure_schema(SCHEMA)

    def create_or_get(self, project_id: str, run_key: str, row: dict) -> tuple[dict, bool]:
        """Insert ``row`` unless a live run (queued, running or succeeded) with the same key exists.
        Returns (run row, created)."""
        with self.store.connection(write=True) as con:
            hit = con.execute("SELECT * FROM runs WHERE project_id=? AND run_key=? AND status IN ('queued','running','succeeded')",
                              (project_id, run_key)).fetchone()
            if hit:
                return _loads(dict(hit), RUN_JSON), False
            rid = new_id("r")
            cols = {"id": rid, "project_id": project_id, "run_key": run_key, "status": "queued", "created_at": now(), **row}
            for k in RUN_JSON:
                if k in cols and not isinstance(cols[k], str) and cols[k] is not None:
                    cols[k] = json.dumps(cols[k])
            try:
                con.execute(f"INSERT INTO runs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
            except sqlite3.IntegrityError:   # lost a race to another process: return the winner
                hit = con.execute("SELECT * FROM runs WHERE project_id=? AND run_key=? AND status IN ('queued','running','succeeded')",
                                  (project_id, run_key)).fetchone()
                return _loads(dict(hit), RUN_JSON), False
            return _loads(dict(con.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()), RUN_JSON), True

    def get(self, project_id: str, run_id: str) -> dict | None:
        row = self.store.query_one("SELECT * FROM runs WHERE project_id=? AND id=?", (project_id, run_id))
        return _loads(row, RUN_JSON) if row else None

    def list(self, project_id: str, flowchart_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM runs WHERE project_id=?", [project_id]
        if flowchart_id:
            sql += " AND flowchart_id=?"
            args.append(flowchart_id)
        rows = self.store.query(sql + " ORDER BY created_at DESC, rowid DESC", tuple(args))
        return [_loads(r, RUN_JSON) for r in rows]

    def unfinished(self) -> list[dict]:
        return [_loads(r, RUN_JSON) for r in self.store.query("SELECT * FROM runs WHERE status IN ('queued','running')")]


OPT_JSON = ("settings_json", "error_json", "summary_json", "applied_json")


class Optimisations(_Base):
    table = "optimisations"

    def __init__(self, store: Store):
        super().__init__(store)
        store.ensure_schema(SCHEMA)

    def create(self, project_id: str, row: dict) -> dict:
        oid = new_id("o")
        cols = {"id": oid, "project_id": project_id, "status": "queued", "created_at": now(), **row}
        for k in OPT_JSON:
            if k in cols and not isinstance(cols[k], str) and cols[k] is not None:
                cols[k] = json.dumps(cols[k])
        self.store.execute(f"INSERT INTO optimisations ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
        return self.get(project_id, oid)

    def get(self, project_id: str, oid: str) -> dict | None:
        row = self.store.query_one("SELECT * FROM optimisations WHERE project_id=? AND id=?", (project_id, oid))
        return _loads(row, OPT_JSON) if row else None

    def list(self, project_id: str) -> list[dict]:
        rows = self.store.query("SELECT * FROM optimisations WHERE project_id=? ORDER BY created_at DESC, rowid DESC", (project_id,))
        return [_loads(r, OPT_JSON) for r in rows]

    def unfinished(self) -> list[dict]:
        return [_loads(r, OPT_JSON) for r in self.store.query("SELECT * FROM optimisations WHERE status IN ('queued','running')")]


class JobRows:
    """Mirror of the runner's in-memory jobs, so ``GET /jobs/{id}`` still answers after a restart."""

    def __init__(self, store: Store):
        self.store = store
        store.ensure_schema(SCHEMA)

    def save(self, d: dict) -> None:
        owner = d.get("owner") or {}
        self.store.execute(
            "INSERT OR REPLACE INTO jobs (id, project_id, kind, label, status, progress, message, created, started, finished, "
            "error_json, result_json, log_json, owner_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["id"], owner.get("project"), d["kind"], d.get("label"), d["status"], d.get("progress"), d.get("message"),
             d.get("created"), d.get("started"), d.get("finished"), json.dumps(d.get("error")),
             json.dumps(d.get("result")), json.dumps(d.get("log_tail")), json.dumps(owner)))

    def get(self, job_id: str) -> dict | None:
        row = self.store.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            return None
        d = _loads(row, ("error_json", "result_json", "log_json", "owner_json"))
        d["log_tail"], d["owner"] = d.pop("log") or [], d["owner"] or {}
        d["state"] = d["status"]
        d.pop("project_id", None)
        return d

    def fail_unfinished(self, reason: str) -> int:
        rows = self.store.query("SELECT id FROM jobs WHERE status IN ('queued','running')")
        for r in rows:
            self.store.execute("UPDATE jobs SET status='failed', finished=?, error_json=? WHERE id=?",
                               (now_ts(), json.dumps({"code": "service_restarted", "message": reason}), r["id"]))
        return len(rows)


def now_ts() -> float:
    import time
    return time.time()

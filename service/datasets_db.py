"""Tables for datasets and trained models (spec 06), added with ``Store.ensure_schema``; rows are gzip JSON lines in blobs."""

from __future__ import annotations

import contextlib
import gzip
import json
import os
from pathlib import Path

from .store import Store, new_id, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL, source_json TEXT, flowchart_id TEXT, flowchart_version INTEGER,
    status TEXT NOT NULL, job_id TEXT, progress REAL NOT NULL DEFAULT 0, message TEXT,
    n_rows INTEGER, n_patients INTEGER, content_hash TEXT, trainable INTEGER,
    report_json TEXT, error_json TEXT, created_at TEXT NOT NULL, finished_at TEXT);
CREATE INDEX IF NOT EXISTS datasets_by_project ON datasets(project_id, created_at);
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT, trainer TEXT NOT NULL, dataset_id TEXT NOT NULL, dataset_hash TEXT,
    flowchart_id TEXT NOT NULL, flowchart_version INTEGER NOT NULL, flowchart_hash TEXT,
    config_json TEXT, decision_points_json TEXT, kind TEXT,
    status TEXT NOT NULL, job_id TEXT, progress REAL NOT NULL DEFAULT 0, message TEXT,
    evaluation_json TEXT, warnings_json TEXT, error_json TEXT,
    created_at TEXT NOT NULL, finished_at TEXT);
CREATE INDEX IF NOT EXISTS models_by_project ON models(project_id, created_at);
"""
DATASET_JSON = ("source_json", "report_json", "error_json")
MODEL_JSON = ("config_json", "decision_points_json", "evaluation_json", "warnings_json", "error_json")
FINAL = ("ready", "failed", "cancelled")


def _loads(row: dict | None, cols) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for c in cols:
        if c in out:
            v = out.pop(c)
            out[c[:-5]] = json.loads(v) if v else None
    return out


class _Table:
    table = ""
    json_cols: tuple = ()
    prefix = ""

    def __init__(self, store: Store):
        self.store = store
        store.ensure_schema(SCHEMA)

    def create(self, project_id: str, **cols) -> dict:
        ident = new_id(self.prefix)
        cols = {k: (json.dumps(v) if k in self.json_cols else v) for k, v in cols.items()}
        cols.update(id=ident, project_id=project_id, created_at=now())
        names = ", ".join(cols)
        self.store.execute(f"INSERT INTO {self.table} ({names}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
        return self.get(project_id, ident)

    def get(self, project_id: str, ident: str) -> dict | None:
        return _loads(self.store.query_one(f"SELECT * FROM {self.table} WHERE project_id=? AND id=?", (project_id, ident)), self.json_cols)

    def get_any(self, ident: str) -> dict | None:
        return _loads(self.store.query_one(f"SELECT * FROM {self.table} WHERE id=?", (ident,)), self.json_cols)

    def list(self, project_id: str) -> list[dict]:
        return [_loads(r, self.json_cols) for r in
                self.store.query(f"SELECT * FROM {self.table} WHERE project_id=? ORDER BY created_at DESC, rowid DESC", (project_id,))]

    def update(self, ident: str, **cols) -> None:
        if not cols:
            return
        cols = {k: (json.dumps(v) if k in self.json_cols else v) for k, v in cols.items()}
        self.store.execute(f"UPDATE {self.table} SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), ident))

    def delete(self, ident: str) -> None:
        self.store.execute(f"DELETE FROM {self.table} WHERE id=?", (ident,))

    def unfinished(self) -> list[dict]:
        done = ", ".join(f"'{s}'" for s in FINAL + ("stored",))
        return [_loads(r, self.json_cols) for r in self.store.query(f"SELECT * FROM {self.table} WHERE status NOT IN ({done})")]


class Datasets(_Table):
    table, json_cols, prefix = "datasets", DATASET_JSON, "d"


class Models(_Table):
    table, json_cols, prefix = "models", MODEL_JSON, "m"


# ---------------------------------------------------------------------------------- row files
def rows_path(store: Store, project_id: str, dataset_id: str) -> Path:
    store._blob_path(project_id, "datasets", dataset_id)           # validates the parts
    return store.blob_dir / project_id / "datasets" / f"{dataset_id}.jsonl.gz"


def write_rows(store: Store, project_id: str, dataset_id: str, rows) -> int:
    path = rows_path(store, project_id, dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    n = 0
    try:
        with gzip.open(tmp, "wb", compresslevel=5) as f:
            for r in rows:
                f.write(json.dumps(r, separators=(",", ":")).encode() + b"\n")
                n += 1
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    return n


def read_lines(store: Store, project_id: str, dataset_id: str):
    """Raw lines (bytes) of a stored dataset."""
    with gzip.open(rows_path(store, project_id, dataset_id), "rb") as f:
        yield from f

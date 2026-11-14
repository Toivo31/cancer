"""SQLite metadata store plus gzip JSON blobs (spec 03).

* Metadata and small documents (world, flowchart versions) live in ``<data_dir>/pathway.sqlite3``.
* Large results (run logs, bundles, patient logs) are gzip JSON files under
  ``<data_dir>/blobs/<project_id>/<kind>/<key>.json.gz``; deleting a project removes its directory.
* Every operation opens its own short connection (WAL mode), so the store is safe to use from request
  threads and from job worker processes: build ``Store(data_dir)`` in the worker.

Other routers add their own tables with :meth:`Store.ensure_schema` (idempotent ``CREATE TABLE IF NOT
EXISTS`` scripts; give them ``project_id TEXT REFERENCES projects(id) ON DELETE CASCADE`` so deleting a
project cleans up). Flowchart versions that a run uses must be locked: call
:meth:`Store.get_version_for_run` (returns the document and locks it) rather than reading and locking separately.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, template TEXT,
    world_json TEXT NOT NULL, world_rev INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS flowcharts (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    id TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, id));
CREATE TABLE IF NOT EXISTS flowchart_versions (
    project_id TEXT NOT NULL, flowchart_id TEXT NOT NULL, version INTEGER NOT NULL,
    parent_version INTEGER, doc_json TEXT NOT NULL, doc_hash TEXT NOT NULL,
    created_at TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (project_id, flowchart_id, version),
    FOREIGN KEY (project_id, flowchart_id) REFERENCES flowcharts(project_id, id) ON DELETE CASCADE);
"""

_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


class StoreError(Exception):
    """Base for store-level conflicts; the routes translate these to API errors."""


class NotFound(StoreError):
    pass


class Conflict(StoreError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class Store:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.blob_dir = self.data_dir / "blobs"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "pathway.sqlite3"
        self.ensure_schema(_SCHEMA)

    # ------------------------------------------------------------------ low level

    @contextlib.contextmanager
    def connection(self, write: bool = False):
        """A connection with foreign keys on. ``write=True`` starts the transaction immediately
        (BEGIN IMMEDIATE) so read-then-write sequences cannot interleave; commit on exit."""
        con = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            if write:
                con.execute("BEGIN IMMEDIATE")
            yield con
            if write:
                con.execute("COMMIT")
        except BaseException:
            if write and con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def ensure_schema(self, script: str) -> None:
        with self.connection() as con:
            con.executescript(script)

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict]:
        with self.connection() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params: tuple | dict = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple | dict = ()) -> None:
        with self.connection(write=True) as con:
            con.execute(sql, params)

    # ------------------------------------------------------------------ blobs

    def _blob_path(self, project_id: str, kind: str, key: str) -> Path:
        for part in (project_id, kind, key):
            if not _KEY.match(part):
                raise ValueError(f"bad blob path part {part!r}")
        return self.blob_dir / project_id / kind / f"{key}.json.gz"

    def put_blob(self, project_id: str, kind: str, key: str, obj) -> str:
        """Write ``obj`` as gzip JSON atomically; returns the path relative to the data directory."""
        path = self._blob_path(project_id, kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
                gz.write(json.dumps(obj, separators=(",", ":")).encode())
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise
        return str(path.relative_to(self.data_dir))

    def get_blob(self, project_id: str, kind: str, key: str):
        path = self._blob_path(project_id, kind, key)
        try:
            with gzip.open(path, "rb") as f:
                return json.loads(f.read())
        except FileNotFoundError:
            raise NotFound(f"{kind} {key}") from None

    def has_blob(self, project_id: str, kind: str, key: str) -> bool:
        return self._blob_path(project_id, kind, key).exists()

    def delete_blob(self, project_id: str, kind: str, key: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._blob_path(project_id, kind, key).unlink()

    # ------------------------------------------------------------------ projects

    @staticmethod
    def _project(row: dict) -> dict:
        return {"id": row["id"], "name": row["name"], "template": row["template"], "world_id": json.loads(row["world_json"]).get("id"),
                "world_rev": row["world_rev"], "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def unique_project_name(self, con, name: str) -> str:
        taken = {r["name"].lower() for r in con.execute("SELECT name FROM projects")}
        if name.lower() not in taken:
            return name
        i = 2
        while f"{name} ({i})".lower() in taken:
            i += 1
        return f"{name} ({i})"

    def create_project(self, name: str, world: dict, flowcharts: list[dict], template: str | None = None,
                       max_projects: int | None = None) -> dict:
        """New project with its world and each flowchart as version 1. Duplicate names get ' (2)' appended."""
        pid, t = new_id("p"), now()
        with self.connection(write=True) as con:
            if max_projects is not None and con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] >= max_projects:
                raise Conflict("too_many_projects", f"At most {max_projects} projects are kept; delete one first")
            name = self.unique_project_name(con, name)
            con.execute("INSERT INTO projects VALUES (?,?,?,?,1,?,?)", (pid, name, template, json.dumps(world), t, t))
            for doc in flowcharts:
                self._insert_flowchart(con, pid, doc, 1, None, t)
        return self.get_project(pid)

    def list_projects(self) -> list[dict]:
        return [self._project(r) for r in self.query("SELECT * FROM projects ORDER BY created_at DESC, rowid DESC")]

    def get_project(self, pid: str) -> dict:
        row = self.query_one("SELECT * FROM projects WHERE id=?", (pid,))
        if row is None:
            raise NotFound(f"project {pid}")
        return self._project(row)

    def rename_project(self, pid: str, name: str) -> dict:
        with self.connection(write=True) as con:
            if con.execute("UPDATE projects SET name=?, updated_at=? WHERE id=?", (self.unique_project_name(con, name), now(), pid)).rowcount == 0:
                raise NotFound(f"project {pid}")
        return self.get_project(pid)

    def delete_project(self, pid: str) -> None:
        with self.connection(write=True) as con:
            if con.execute("DELETE FROM projects WHERE id=?", (pid,)).rowcount == 0:
                raise NotFound(f"project {pid}")
        shutil.rmtree(self.blob_dir / pid, ignore_errors=True)

    # ------------------------------------------------------------------ world

    def get_world(self, pid: str) -> tuple[dict, int]:
        row = self.query_one("SELECT world_json, world_rev FROM projects WHERE id=?", (pid,))
        if row is None:
            raise NotFound(f"project {pid}")
        return json.loads(row["world_json"]), row["world_rev"]

    def put_world(self, pid: str, world: dict, if_rev: int | None = None) -> int:
        """Replace the world; returns the new revision. ``if_rev`` guards against overwriting a newer edit."""
        with self.connection(write=True) as con:
            row = con.execute("SELECT world_rev FROM projects WHERE id=?", (pid,)).fetchone()
            if row is None:
                raise NotFound(f"project {pid}")
            if if_rev is not None and if_rev != row["world_rev"]:
                raise Conflict("stale_revision", f"The world is at revision {row['world_rev']}, not {if_rev}; reload it first")
            rev = row["world_rev"] + 1
            con.execute("UPDATE projects SET world_json=?, world_rev=?, updated_at=? WHERE id=?", (json.dumps(world), rev, now(), pid))
            return rev

    # ------------------------------------------------------------------ flowcharts and versions

    @staticmethod
    def _insert_flowchart(con, pid: str, doc: dict, version: int, parent: int | None, t: str) -> dict:
        from pathway_sim.documents import doc_hash
        doc = {**doc, "version": version, "parent_version": parent}
        con.execute("INSERT INTO flowcharts VALUES (?,?,?)", (pid, doc["id"], t))
        con.execute("INSERT INTO flowchart_versions VALUES (?,?,?,?,?,?,?,0)",
                    (pid, doc["id"], version, parent, json.dumps(doc), doc_hash(doc), t))
        return doc

    def create_flowchart(self, pid: str, doc: dict, max_versions: int | None = None) -> dict:
        """New flowchart with ``doc`` as version 1. Raises Conflict(duplicate_flowchart) if the id is taken."""
        with self.connection(write=True) as con:
            if con.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone() is None:
                raise NotFound(f"project {pid}")
            if con.execute("SELECT 1 FROM flowcharts WHERE project_id=? AND id=?", (pid, doc["id"])).fetchone():
                raise Conflict("duplicate_flowchart", f"The project already has a flowchart '{doc['id']}'; save a new version of it instead")
            out = self._insert_flowchart(con, pid, doc, 1, None, now())
            con.execute("UPDATE projects SET updated_at=? WHERE id=?", (now(), pid))
        return out

    def list_flowcharts(self, pid: str) -> list[dict]:
        """Each flowchart with its version list (no documents) and ``latest_version``."""
        self.get_project(pid)
        out: dict[str, dict] = {}
        for r in self.query("SELECT flowchart_id, version, parent_version, created_at, locked, doc_json FROM flowchart_versions "
                            "WHERE project_id=? ORDER BY flowchart_id, version", (pid,)):
            d = out.setdefault(r["flowchart_id"], {"id": r["flowchart_id"], "versions": []})
            d["versions"].append({"version": r["version"], "parent_version": r["parent_version"], "created_at": r["created_at"],
                                  "locked": bool(r["locked"])})
            d["latest_version"] = r["version"]
            d["name"] = json.loads(r["doc_json"]).get("name") or r["flowchart_id"]
        return list(out.values())

    def _version_row(self, pid: str, fid: str, version: int | None, con=None):
        sql = "SELECT * FROM flowchart_versions WHERE project_id=? AND flowchart_id=? "
        args: tuple = (pid, fid)
        if version is None:
            sql += "ORDER BY version DESC LIMIT 1"
        else:
            sql += "AND version=?"
            args += (version,)
        row = self.query_one(sql, args) if con is None else con.execute(sql, args).fetchone()
        if row is None:
            raise NotFound(f"flowchart {fid}" + (f" version {version}" if version else ""))
        return dict(row)

    def get_version(self, pid: str, fid: str, version: int | None = None) -> tuple[dict, dict]:
        """(document, info) for a version; ``None`` means the latest. info = version, parent_version, locked, created_at."""
        r = self._version_row(pid, fid, version)
        return json.loads(r["doc_json"]), {"version": r["version"], "parent_version": r["parent_version"],
                                           "locked": bool(r["locked"]), "created_at": r["created_at"]}

    def add_version(self, pid: str, fid: str, doc: dict, max_versions: int | None = None) -> dict:
        """Save ``doc`` as version n+1 (the server sets ``version`` and ``parent_version``)."""
        with self.connection(write=True) as con:
            top = con.execute("SELECT MAX(version) FROM flowchart_versions WHERE project_id=? AND flowchart_id=?", (pid, fid)).fetchone()[0]
            if top is None:
                raise NotFound(f"flowchart {fid}")
            if max_versions is not None and top >= max_versions:
                raise Conflict("too_many_versions", f"A flowchart keeps at most {max_versions} versions")
            from pathway_sim.documents import doc_hash
            doc = {**doc, "version": top + 1, "parent_version": top}
            con.execute("INSERT INTO flowchart_versions VALUES (?,?,?,?,?,?,?,0)",
                        (pid, fid, top + 1, top, json.dumps(doc), doc_hash(doc), now()))
            con.execute("UPDATE projects SET updated_at=? WHERE id=?", (now(), pid))
        return doc

    def replace_version(self, pid: str, fid: str, version: int, doc: dict) -> dict:
        """Overwrite an unlocked version in place (editor autosave before the first run)."""
        from pathway_sim.documents import doc_hash
        with self.connection(write=True) as con:
            r = self._version_row(pid, fid, version, con)
            if r["locked"]:
                raise Conflict("version_locked", f"Version {version} of '{fid}' has been used in a run and cannot change; save a new version")
            doc = {**doc, "version": version, "parent_version": r["parent_version"]}
            con.execute("UPDATE flowchart_versions SET doc_json=?, doc_hash=? WHERE project_id=? AND flowchart_id=? AND version=?",
                        (json.dumps(doc), doc_hash(doc), pid, fid, version))
            con.execute("UPDATE projects SET updated_at=? WHERE id=?", (now(), pid))
        return doc

    def lock_version(self, pid: str, fid: str, version: int) -> None:
        with self.connection(write=True) as con:
            con.execute("UPDATE flowchart_versions SET locked=1 WHERE project_id=? AND flowchart_id=? AND version=?", (pid, fid, version))

    def get_version_for_run(self, pid: str, fid: str, version: int | None = None) -> tuple[dict, int]:
        """Read a version *and lock it* in one step: the way a run (or optimisation) must fetch its flowchart.
        Returns (document, version)."""
        with self.connection(write=True) as con:
            r = self._version_row(pid, fid, version, con)
            con.execute("UPDATE flowchart_versions SET locked=1 WHERE project_id=? AND flowchart_id=? AND version=?", (pid, fid, r["version"]))
        return json.loads(r["doc_json"]), r["version"]

    def delete_flowchart(self, pid: str, fid: str) -> None:
        with self.connection(write=True) as con:
            if con.execute("SELECT 1 FROM flowcharts WHERE project_id=? AND id=?", (pid, fid)).fetchone() is None:
                raise NotFound(f"flowchart {fid}")
            if con.execute("SELECT 1 FROM flowchart_versions WHERE project_id=? AND flowchart_id=? AND locked=1", (pid, fid)).fetchone():
                raise Conflict("version_locked", f"A version of '{fid}' has been used in a run, so the flowchart cannot be deleted")
            con.execute("DELETE FROM flowcharts WHERE project_id=? AND id=?", (pid, fid))

"""Consistent copy of the SQLite database (projects, worlds, flowchart versions, run rows), pruned to the newest N.

    docker compose exec -T platform python /app/deploy/backup.py            # -> /data/backups/pathway-<utc>.sqlite3
    python deploy/backup.py --data-dir ./data --keep 14

Result files under blobs/ are reproducible from the stored documents and are not copied. Uses SQLite's online
backup, so it is safe while the service is running. Exit code 1 when the copy fails its integrity check.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def backup(data_dir: Path, keep: int = 7, out_dir: Path | None = None) -> Path:
    src = data_dir / "pathway.sqlite3"
    if not src.exists():
        raise SystemExit(f"no database at {src}")
    out_dir = out_dir or data_dir / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"pathway-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    tmp = dest.with_suffix(".partial")
    a, b = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30), sqlite3.connect(tmp)
    try:
        a.backup(b)
        ok = b.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        a.close()
        b.close()
    if ok != "ok":
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"backup failed its integrity check: {ok}")
    os.replace(tmp, dest)
    for old in sorted(out_dir.glob("pathway-*.sqlite3"))[:-keep] if keep > 0 else []:
        old.unlink()
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path(os.environ.get("PATHWAY_DATA_DIR", "/data")))
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--keep", type=int, default=7)
    a = ap.parse_args()
    print(backup(a.data_dir, a.keep, a.out))
    sys.exit(0)

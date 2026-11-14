"""Copy the team dashboard (branch overnight/sim) into live_demo/report/ for our demo server.

The team's own files are never changed: this only reads them and writes a copy here.

    python live_demo/build_report.py                       # reads origin/overnight/sim with git
    python live_demo/build_report.py --sim ../cancer-sim   # or from a checkout of that branch

The copy is served at /report/ with live_demo/report/light.css added (see note_reader/server.py).
Rerun after the team regenerates the dashboard or its bundle.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "report"
FILES = ["index.html", "data/demo_bundle.json"]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", help="checkout of overnight/sim (default: read origin/overnight/sim with git)")
    ap.add_argument("--ref", default="origin/overnight/sim")
    a = ap.parse_args(argv)
    for f in FILES:
        dst = OUT / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        if a.sim:
            data = (Path(a.sim) / "demo" / f).read_bytes()
        else:
            data = subprocess.run(["git", "show", f"{a.ref}:demo/{f}"], cwd=HERE.parent,
                                  capture_output=True, check=True).stdout
        dst.write_bytes(data)
        print(f"wrote {dst.relative_to(HERE.parent)} ({len(data) // 1024} kB)")


if __name__ == "__main__":
    main()

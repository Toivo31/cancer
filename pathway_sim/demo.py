"""`python -m pathway_sim demo [--quick]`: the whole loop end to end.

Generates patients, runs the starting flowcharts, lets the optimiser propose changes, reruns
the same patients, evaluates on held-out patients, and writes demo/data/demo_bundle.json
(also embedded into demo/index.html so the page works offline). Then open demo/index.html.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cmd_demo(a) -> None:
    args = [sys.executable, str(ROOT / "demo" / "export.py")] + (["--quick"] if a.quick else [])
    subprocess.run(args, check=True)
    subprocess.run([sys.executable, str(ROOT / "demo" / "embed_bundle.py")], check=True)
    print(f"open {ROOT / 'demo' / 'index.html'}")


def add_cli(sub) -> None:
    d = sub.add_parser("demo", help="end-to-end: simulate, optimise, evaluate on held-out patients, build the dashboard")
    d.add_argument("--quick", action="store_true", help="smaller cohorts (smoke test)")
    d.set_defaults(f=cmd_demo)

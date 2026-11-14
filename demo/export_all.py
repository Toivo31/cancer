#!/usr/bin/env python3
"""Rerun every export that feeds the offline pages, in dependency order, and print how long each took.

    python demo/export_all.py                 # cards, start, encounter, flow (about 1 to 2 minutes on a busy 2-core machine)
    python demo/export_all.py encounter       # only the named ones (cards | start | encounter | flow)

Each one is also a command of its own:
  demo/export_cards.py      demo/data/cards_bundle.js      synthetic-patient libraries  (under 1 s)
  demo/export_start.py      demo/data/start_bundle.js      Norway ranges, ledger, tuned report; re-simulates one Norway pathway (about 10 s)
  demo/export_encounter.py  demo/data/encounter_bundle.js  runs the encounter loop with whatever the scenario files hold now (about 15 s)
  demo/export_flow.py       demo/data/flow_bundle.js       reruns the held-out cohorts of both scenarios (about 40 to 60 s)
demo_bundle.json (the dashboard, demo/export.py) is a separate, slower job and is only needed when the optimiser results change.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = {"cards": "export_cards.py", "start": "export_start.py", "encounter": "export_encounter.py", "flow": "export_flow.py"}


def main(argv: list[str]) -> int:
    want = argv or list(STEPS)
    bad = [w for w in want if w not in STEPS]
    if bad:
        print("unknown:", ", ".join(bad), "| choose from", ", ".join(STEPS))
        return 2
    rc, t_all = 0, time.time()
    for name in want:
        t0 = time.time()
        r = subprocess.run([sys.executable, str(HERE / STEPS[name])])
        print(f"== {name}: {'ok' if r.returncode == 0 else 'FAILED'} in {time.time() - t0:.1f} s", flush=True)
        rc = rc or r.returncode
    print(f"== all done in {time.time() - t_all:.1f} s")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""CLI.

    python -m pathway_sim run scenarios/stokstad.yaml --flowchart observed --n 100 --seed 1
    python -m pathway_sim compare scenarios/stokstad.yaml --n 100 --seeds 1-20
    python -m pathway_sim run scenarios/finland_lung.yaml --flowchart baseline --out runs/fi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from . import compute_metrics, generate_patients, load_scenario, simulate, summary_line


def _seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def _n(sc, n):
    return n if n else int(sc.raw.get("default_n", 1000))


def cmd_run(a) -> None:
    sc = load_scenario(a.scenario)
    pts = generate_patients(sc, _n(sc, a.n), a.seed)
    run = simulate(sc, a.flowchart, pts, seed=a.seed)
    m = compute_metrics(run, sc)
    print(summary_line(m))
    print("stage (critical path, mean days per treated cancer patient):")
    for s, v in m["stage_breakdown"].items():
        print(f"  {s:<16} wait {v['wait']:6.1f}  service {v['service']:6.1f}")
    top = sorted(m["node_breakdown"].items(), key=lambda kv: -kv[1]["wait"])[:5]
    print("steps with most waiting:", ", ".join(f"{k} {v['wait']:.1f}d" for k, v in top))
    if m["utilisation"]:
        print("utilisation:", ", ".join(f"{k} {v:.0%}" for k, v in m["utilisation"].items()))
    if m["stuck"]:
        print(f"WARNING: {m['stuck']} patients stuck (flowchart has no exit for them)", file=sys.stderr)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"run": run.to_dict(), "metrics": m}))
        print("wrote", a.out)


def cmd_compare(a) -> None:
    sc = load_scenario(a.scenario)
    fcs = a.flowcharts.split(",") if a.flowcharts else list(sc.flowcharts)
    seeds = _seeds(a.seeds)
    print(f"{sc.id}: {len(seeds)} seeds x {_n(sc, a.n)} patients, target {sc.target_days:g} d")
    for fid in fcs:
        ms = []
        for s in seeds:
            pts = generate_patients(sc, _n(sc, a.n), s)
            ms.append(compute_metrics(simulate(sc, fid, pts, seed=s), sc))
        avg = lambda k: mean(m[k] for m in ms if m[k] is not None)
        print(f"{fid:<24} on-time {100*avg('share_within_target'):5.1f}%  median {avg('median_days_to_treatment'):6.1f} d"
              f"  missed {avg('missed_cancers'):5.2f}  tests/pt {avg('tests_per_patient'):.2f}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="pathway_sim")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one flowchart")
    r.add_argument("scenario")
    r.add_argument("--flowchart", default="baseline")
    r.add_argument("--n", type=int, default=0)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out")
    r.set_defaults(f=cmd_run)
    c = sub.add_parser("compare", help="compare flowcharts averaged over seeds")
    c.add_argument("scenario")
    c.add_argument("--flowcharts")
    c.add_argument("--n", type=int, default=0)
    c.add_argument("--seeds", default="1-10")
    c.set_defaults(f=cmd_compare)
    try:
        from .demo import add_cli  # optional, added by integration
        add_cli(sub)
    except ImportError:
        pass
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()

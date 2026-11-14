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


def _sets(items) -> dict:
    out = {}
    for it in items or []:
        try:
            key, val = it.split("=")
            point, option = key.split(".")
            out[(point, option)] = float(val)
        except ValueError:
            raise SystemExit(f"--set expects point.option=probability, e.g. sample_choice.bronch=0.5 (got {it!r})")
    return out


def _decision_policy(a, sc, fid, seed):
    """``(flowchart, policy, backend)`` for the JEV flags; without them the rule policy runs as before."""
    if not (a.jev or a.decision_mode or a.set):
        return sc.flowcharts[fid], None, None
    import jev                                   # imported only when asked for; the engine never imports it
    opts = {k: v for k, v in (("model", a.jev_model), ("on_error", a.on_error), ("timeout", a.jev_timeout)) if v is not None}
    try:
        fc, pol = jev.prepare(sc, sc.flowcharts[fid], backend=a.jev or "stub", mode=a.decision_mode,
                              seed=seed, sets=_sets(a.set), **opts)
    except (ValueError, jev.BackendError) as e:
        raise SystemExit(f"error: {e}")
    return fc, pol, (pol.backend if hasattr(pol, "backend") else None)


def _describe_decisions(pol, run) -> dict:
    n = sum(len(p.choices) for p in run.patients)
    info = {"decisions": n, "backend": getattr(pol, "backend_name", "RulePolicy"), "model": getattr(pol, "model_id", None),
            "mode": getattr(pol, "decision_mode", "argmax")}
    fn = getattr(pol, "run_summary", None)
    if fn:
        info.update(fn())
    return info


def cmd_run(a) -> None:
    sc = load_scenario(a.scenario)
    pts = generate_patients(sc, _n(sc, a.n), a.seed)
    fc, pol, _ = _decision_policy(a, sc, a.flowchart, a.seed)
    try:
        run = simulate(sc, fc, pts, policy=pol, seed=a.seed)
    except Exception as e:                                   # a JEV that fails mid-run stops the run clearly
        if type(e).__name__ in ("BackendError", "ContractError"):
            raise SystemExit(f"error: the run stopped, the decision backend failed: {e}")
        raise
    if pol is not None:
        d = _describe_decisions(pol, run)
        extra = {k: v for k, v in d.items() if k not in ("decisions", "backend", "model", "mode")}
        print(f"decisions: {d['decisions']} via {d['backend']} ({d['model']}), mode {d['mode']}"
              + "".join(f", {k} {v}" for k, v in extra.items()))
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
        out = {"run": run.to_dict(), "metrics": m}
        if pol is not None:
            out["decisions"] = _describe_decisions(pol, run)
        Path(a.out).write_text(json.dumps(out))
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
            fc, pol, _ = _decision_policy(a, sc, fid, s)
            ms.append(compute_metrics(simulate(sc, fc, pts, policy=pol, seed=s), sc))
        avg = lambda k: mean(m[k] for m in ms if m[k] is not None)
        print(f"{fid:<24} on-time {100*avg('share_within_target'):5.1f}%  median {avg('median_days_to_treatment'):6.1f} d"
              f"  missed {avg('missed_cancers'):5.2f}  tests/pt {avg('tests_per_patient'):.2f}")


def _jev_flags(p) -> None:
    g = p.add_argument_group("decision backend (JEV)", "Without these flags the scenario's rule policy runs exactly as before.")
    g.add_argument("--jev", metavar="stub|rule|URL", help="stub: probability tables (migrated from the scenario's policy); "
                   "rule: the rule policy; http://host:port: a JEV service")
    g.add_argument("--decision-mode", choices=["sample", "argmax"], help="draw each choice from the probabilities (default) or take the most likely option")
    g.add_argument("--set", action="append", metavar="POINT.OPTION=P", help="override one stub probability, e.g. sample_choice.bronch=0.5; repeatable")
    g.add_argument("--jev-model", help="model id to ask the JEV service for")
    g.add_argument("--on-error", choices=["fail", "fallback_stub"], help="when the JEV service fails: stop (default) or use the stub and count")
    g.add_argument("--jev-timeout", type=float, help="seconds before a JEV call times out (default 2)")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="pathway_sim")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one flowchart")
    r.add_argument("scenario")
    r.add_argument("--flowchart", default="baseline")
    r.add_argument("--n", type=int, default=0)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out")
    _jev_flags(r)
    r.set_defaults(f=cmd_run)
    c = sub.add_parser("compare", help="compare flowcharts averaged over seeds")
    c.add_argument("scenario")
    c.add_argument("--flowcharts")
    c.add_argument("--n", type=int, default=0)
    c.add_argument("--seeds", default="1-10")
    _jev_flags(c)
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

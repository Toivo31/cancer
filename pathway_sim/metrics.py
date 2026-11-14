"""Metrics from a run: the four headline numbers plus where the time goes.

Stage and step breakdowns use each patient's **critical path**, so waiting +
service add up exactly to the time to treatment (or exit). Parallel steps that
were not on the critical path are reported separately (``*_all``).
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from .engine import RunLog
from .scenario import STAGES, Scenario


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(median(xs), 2) if xs else None


def _share(xs, target):
    xs = [x for x in xs]
    if not xs:
        return None
    return round(sum(1 for x in xs if x is not None and x <= target) / len(xs), 4)


def _breakdown(prs, critical_only: bool):
    stage = {s: {"wait": 0.0, "service": 0.0} for s in STAGES}
    node: dict[str, dict] = defaultdict(lambda: {"wait": 0.0, "service": 0.0, "n": 0, "test": None, "stage": None})
    n = max(len(prs), 1)
    for pr in prs:
        seen = set()
        for e in pr.events:
            if critical_only and not e.critical:
                continue
            w = e.t_start - e.t_ready
            s = e.t_result - e.t_start
            stage[e.stage]["wait"] += w
            stage[e.stage]["service"] += s
            nd = node[e.node]
            nd["wait"] += w
            nd["service"] += s
            nd["test"], nd["stage"] = e.test, e.stage
            if e.node not in seen:
                nd["n"] += 1
                seen.add(e.node)
    st = {k: {"wait": round(v["wait"] / n, 2), "service": round(v["service"] / n, 2)} for k, v in stage.items()}
    nb = {k: {"wait": round(v["wait"] / n, 2), "service": round(v["service"] / n, 2), "n": v["n"],
              "test": v["test"], "stage": v["stage"]} for k, v in node.items()}
    return st, nb


def queue_series(run: RunLog, resource: str, step: float = 1.0) -> list[list[float]]:
    """Number of patients waiting (ready, not yet started) at ``resource`` sampled every ``step`` days."""
    iv = [(e.t_ready, e.t_start) for pr in run.patients for e in pr.events if e.resource == resource]
    if not iv:
        return []
    t0, t1 = min(a for a, _ in iv), max(b for _, b in iv)
    out, t = [], t0
    while t <= t1:
        out.append([round(t, 2), sum(1 for a, b in iv if a <= t < b)])
        t += step
    return out


def compute_metrics(run: RunLog, sc: Scenario | None = None, include_warmup: bool = False) -> dict:
    target = run.target_days
    prs = [pr for pr in run.patients if include_warmup or pr.patient.arrival >= run.warmup_days]
    cancer = [pr for pr in prs if pr.patient.cancer]
    noncancer = [pr for pr in prs if not pr.patient.cancer]

    def rel(pr, x):
        return None if x is None else x - pr.patient.arrival

    ttt = [rel(pr, pr.t_treatment) for pr in cancer]
    ttd = [rel(pr, pr.t_diagnosis) for pr in cancer]
    tests = invasive = cost = 0
    for pr in prs:
        for e in pr.events:
            spec = sc.tests.get(e.test, {}) if sc else {}
            if spec.get("kind", "test") == "test":
                tests += 1
            if spec.get("invasive"):
                invasive += 1
            cost += float(spec.get("cost_eur", 0) or 0)
    n = max(len(prs), 1)
    treated = [pr for pr in cancer if pr.t_treatment is not None]
    stage_bd, node_bd = _breakdown(treated, critical_only=True)
    stage_all, node_all = _breakdown(treated, critical_only=False)
    stage_every, _ = _breakdown([pr for pr in prs if pr.t_exit is not None], critical_only=True)
    by_group = {}
    for g in sorted({pr.patient.group for pr in prs}):
        gc = [pr for pr in cancer if pr.patient.group == g]
        ga = [pr for pr in prs if pr.patient.group == g]
        by_group[g] = {
            "n": len(ga), "n_cancer": len(gc),
            "median_days_to_treatment": _med([rel(pr, pr.t_treatment) for pr in gc]),
            "share_within_target": _share([rel(pr, pr.t_treatment) for pr in gc], target),
            "median_days_to_diagnosis": _med([rel(pr, pr.t_diagnosis) for pr in gc]),
            "missed_cancers": sum(1 for pr in gc if pr.outcome == "discharged"),
            "median_days_to_exit_all": _med([rel(pr, pr.t_exit) for pr in ga]),
        }
    util = {rid: r.get("utilisation") for rid, r in run.resources.items() if r.get("utilisation") is not None}
    return {
        "scenario": run.scenario, "flowchart": run.flowchart, "seed": run.seed,
        "n": len(prs), "n_cancer": len(cancer), "target_days": target,
        "median_days_to_treatment": _med(ttt),
        "share_within_target": _share(ttt, target),
        "median_days_to_diagnosis": _med(ttd),
        "mean_days_to_treatment": round(sum(x for x in ttt if x is not None) / max(1, len([x for x in ttt if x is not None])), 2) if treated else None,
        "missed_cancers": sum(1 for pr in cancer if pr.outcome == "discharged"),
        "untreated_cancers": sum(1 for pr in cancer if pr.outcome != "treatment"),
        "stuck": sum(1 for pr in prs if pr.outcome == "stuck"),
        "false_treatments": sum(1 for pr in noncancer if pr.outcome == "treatment"),
        "tests_per_patient": round(tests / n, 3),
        "invasive_per_patient": round(invasive / n, 3),
        "cost_per_patient": round(cost / n, 1),
        "median_days_to_exit_noncancer": _med([rel(pr, pr.t_exit) for pr in noncancer]),
        "stage_breakdown": stage_bd,
        "node_breakdown": node_bd,
        "stage_breakdown_all": stage_all,
        "node_breakdown_all": node_all,
        "stage_breakdown_everyone": stage_every,
        "by_group": by_group,
        "utilisation": util,
    }


def summary_line(m: dict) -> str:
    def f(x, fmt="{:.1f}"):
        return "-" if x is None else fmt.format(x)
    return (f"{m['flowchart']:<24} on-time {f(m['share_within_target'] and 100*m['share_within_target'], '{:5.1f}%')}"
            f"  median {f(m['median_days_to_treatment']):>6} d  diag {f(m['median_days_to_diagnosis']):>6} d"
            f"  missed {m['missed_cancers']:>3}  tests/pt {m['tests_per_patient']:.2f}"
            f"  noncancer exit {f(m['median_days_to_exit_noncancer'])} d")

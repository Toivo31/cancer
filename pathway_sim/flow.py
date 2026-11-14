"""Flow data: what the flowchart screen draws from a run.

``build_flow(log, scenario, flowchart)`` turns a run log (or several cohorts of the same flowchart)
into one JSON-ready document: the display graph, per-step and per-edge counts, waits, service times,
critical-path share, queue series, decision shares, and a sampled cohort of patient traces for
playback. The shape is documented in ``docs/platform/flow-format.md``.

Everything is read from the run log; nothing is simulated here. Counts use every patient measured
after the warm-up, exactly the population of ``compute_metrics``; only the playback cohort is a
sample. Critical-path numbers reuse ``metrics._breakdown`` so they equal ``node_breakdown``.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean

import numpy as np

from .engine import RunLog
from .metrics import _breakdown, compute_metrics
from .scenario import Flowchart, Scenario

FORMAT = "flow/1"
HEADLINE = ("n", "n_cancer", "target_days", "median_days_to_treatment", "share_within_target",
            "median_days_to_diagnosis", "missed_cancers", "tests_per_patient", "invasive_per_patient",
            "cost_per_patient", "median_days_to_exit_noncancer")


# ------------------------------------------------------------------ display graph
def _short(label: str) -> str:
    return label.split(" (")[0].strip()


def display_graph(sc: Scenario, fc: Flowchart) -> dict:
    """The graph a person sees: steps, decisions, the diagnosis milestone and exits.

    Plumbing nodes (joins and guards without a test) are collapsed and their connections joined
    through. Each node has a ``layer`` (longest path from a start) for left-to-right layout.
    """
    option_of = {o: n.id for n in fc.nodes.values() if n.kind == "choice" for o in n.options}
    kept = [n.id for n in fc.nodes.values()
            if n.kind in ("choice", "exit", "milestone") or n.test or n.id in option_of]
    kept_set = set(kept)

    def direct_preds(n):
        out = [(p, "then") for p in n.after] + [(p, "maybe") for p in n.after_any + n.after_optional]
        if n.id in option_of:
            out.append((option_of[n.id], "option"))
        return out

    memo: dict[str, dict] = {}

    def kept_preds(nid: str) -> dict[str, str]:
        if nid in memo:
            return memo[nid]
        memo[nid] = {}
        res: dict[str, str] = {}
        for p, k in direct_preds(fc.nodes[nid]):
            subs = {p: k} if p in kept_set else {q: ("then" if (k == "then" and kk == "then") else "maybe")
                                                 for q, kk in kept_preds(p).items()}
            for q, kk in subs.items():
                if q == nid:
                    continue
                res[q] = kk if q not in res or res[q] != "then" else "then" if kk == "then" else res[q]
        memo[nid] = res
        return res

    edges = {}
    for v in kept:
        for u, k in kept_preds(v).items():
            edges[(u, v)] = k
    succ: dict[str, set] = defaultdict(set)
    for (u, v) in edges:
        succ[u].add(v)

    reach_memo: dict[str, set] = {}

    def reach(x: str) -> set:
        if x in reach_memo:
            return reach_memo[x]
        reach_memo[x] = set()
        s = set()
        for y in succ[x]:
            s.add(y)
            s |= reach(y)
        reach_memo[x] = s
        return s

    shortcut = {(u, v) for (u, v) in edges if any(w != v and v in reach(w) for w in succ[u])}

    layer: dict[str, int] = {}

    def depth(x: str) -> int:
        if x not in layer:
            layer[x] = 0
            ps = [u for (u, v) in edges if v == x]
            layer[x] = 1 + max((depth(u) for u in ps), default=-1)
        return layer[x]

    for x in kept:
        depth(x)

    nodes = []
    for nid in kept:
        n = fc.nodes[nid]
        label = n.label or (n.test or nid).replace("_", " ")
        kind = {"choice": "decision", "exit": "exit", "milestone": "milestone"}.get(n.kind, "step")
        d = {"id": nid, "label": label, "short": _short(label), "kind": kind, "stage": sc.stage_of(n),
             "layer": layer[nid]}
        if n.test:
            d["test"] = n.test
            rid = sc.tests[n.test].get("resource", "none")
            if rid and rid != "none":
                d["resource"] = rid
        if kind == "decision":
            d["options"] = list(n.options)
        if kind == "exit":
            d["outcome"] = n.outcome
        if n.when:
            d["when"] = n.when
        if n.id in option_of:
            d["option_of"] = option_of[n.id]
        if n.fast_track:
            d["fast_track"] = True
        nodes.append(d)
    elist = [{"id": f"{u}>{v}", "source": u, "target": v, "kind": k, **({"shortcut": True} if (u, v) in shortcut else {})}
             for (u, v), k in edges.items()]
    return {"nodes": nodes, "edges": elist, "stages": list(dict.fromkeys(n["stage"] for n in nodes))}


# ------------------------------------------------------------------ helpers
def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


def _pct(a, q):
    return _r(np.percentile(a, q)) if len(a) else None


def _visited(pr, node_ids: set, option_of: dict, milestone_ids: set) -> set:
    """Display nodes a patient passed through (steps with events, decisions made, options taken, the exit)."""
    v = {e.node for e in pr.events if e.node in node_ids}
    for c in pr.choices:
        if c["node"] in node_ids:
            v.add(c["node"])
        if c["chosen"] in node_ids:
            v.add(c["chosen"])
    if pr.exit_node in node_ids:
        v.add(pr.exit_node)
    return v


def _queue_series(logs: list[RunLog], node_ids: list[str], points: int) -> dict:
    """Patients waiting (ready, not yet started) at each step, sampled on an even grid over the measured window,
    averaged over cohorts. x is days since the measured window began."""
    out = {}
    for nid in node_ids:
        acc = None
        for run in logs:
            ivs = [(e.t_ready, e.t_start) for pr in run.patients for e in pr.events if e.node == nid]
            if not ivs:
                continue
            t0 = run.warmup_days
            t1 = max(pr.patient.arrival for pr in run.patients)
            grid = np.linspace(t0, t1, points)
            a = np.sort(np.array([x for x, _ in ivs]))
            b = np.sort(np.array([y for _, y in ivs]))
            q = np.searchsorted(a, grid, side="right") - np.searchsorted(b, grid, side="right")
            acc = q.astype(float) if acc is None else acc + q
            span = (t0, t1)
        if acc is None:
            continue
        acc = acc / len(logs)
        xs = np.linspace(0, span[1] - span[0], points)
        out[nid] = {"x": [_r(x, 1) for x in xs], "y": [_r(y, 2) for y in acc],
                    "peak": _r(acc.max(), 1), "mean": _r(acc.mean(), 2)}
    return out


def _sample(prs, k: int, cancer_share: float, rng: np.random.Generator):
    cancer = [x for x in prs if x[1].patient.cancer]
    other = [x for x in prs if not x[1].patient.cancer]
    kc = min(len(cancer), int(round(k * cancer_share)) if other else k)
    ko = min(len(other), k - kc)
    kc = min(len(cancer), k - ko)
    pick = []
    for pool, kk in ((cancer, kc), (other, ko)):
        if kk and pool:
            idx = sorted(rng.choice(len(pool), size=kk, replace=False))
            pick += [pool[i] for i in idx]
    return pick, {"cancer": kc, "other": ko, "cancer_total": len(cancer), "other_total": len(other)}


def _trace(pr, seed) -> dict:
    a = pr.patient.arrival

    def rel(x):
        return None if x is None else _r(x - a)
    evs = sorted(pr.events, key=lambda e: (e.t_ready, e.t_start))
    return {
        "id": pr.patient.id, "cohort": seed, "g": pr.patient.group, "age": pr.patient.age,
        "cancer": int(pr.patient.cancer), "out": pr.outcome, "exit": pr.exit_node,
        "t_exit": rel(pr.t_exit), "t_diag": rel(pr.t_diagnosis), "t_treat": rel(pr.t_treatment),
        "ft": int(bool(pr.priority)),
        # [node, t_ready, t_start, t_end, t_result, result (1 positive, 0 negative, null not diagnostic), critical]
        "v": [[e.node, rel(e.t_ready), rel(e.t_start), rel(e.t_end), rel(e.t_result),
               None if e.result is None else int(bool(e.result)), int(bool(e.critical))] for e in evs],
        # [node, t, chosen, offered, probabilities offered]
        "c": [[c["node"], _r(c["t"]), c["chosen"], c["offered"], c["probs"]] for c in pr.choices],
    }


# ------------------------------------------------------------------ main
def build_flow(log, scenario: Scenario, flowchart: Flowchart | str | None = None, sample: int = 300,
               seed: int = 0, cancer_share: float = 0.5, queue_points: int = 120,
               meta: dict | None = None) -> dict:
    """Build the flow document for one run (``RunLog``) or several cohorts of the same flowchart (list).

    ``sample``: patients in the playback cohort. They are drawn from the patients measured after the
    warm-up, ``cancer_share`` of them with cancer (so that a pathway with 3% cancer still shows
    patients reaching treatment); the sample sizes are recorded in ``cohort.strata``.
    ``seed`` makes the sample reproducible. ``meta`` is copied into the document (titles, published values).
    """
    logs = list(log) if isinstance(log, (list, tuple)) else [log]
    if flowchart is None:
        flowchart = logs[0].flowchart
    fc = scenario.flowcharts[flowchart] if isinstance(flowchart, str) else flowchart
    g = display_graph(scenario, fc)
    node_ids = {n["id"] for n in g["nodes"]}
    node_by = {n["id"]: n for n in g["nodes"]}
    option_of = {n["id"]: n["option_of"] for n in g["nodes"] if "option_of" in n}
    milestone_ids = {n["id"] for n in g["nodes"] if n["kind"] == "milestone"}

    measured = [(run.seed, pr) for run in logs for pr in run.patients if pr.patient.arrival >= run.warmup_days]
    n_all = len(measured)

    # reachability for the nearest-visited-predecessor rule
    succ = defaultdict(set)
    preds = defaultdict(list)
    for e in g["edges"]:
        succ[e["source"]].add(e["target"])
        preds[e["target"]].append(e["source"])
    rmemo: dict = {}

    def reach(x):
        if x not in rmemo:
            rmemo[x] = set()
            s = set()
            for y in succ[x]:
                s |= {y} | reach(y)
            rmemo[x] = s
        return rmemo[x]

    visits = defaultdict(int)
    visits_cancer = defaultdict(int)
    edge_n = defaultdict(int)
    waits = defaultdict(list)
    svc = defaultdict(list)
    res_count = defaultdict(lambda: [0, 0, 0])      # positive, negative, not diagnostic
    attempts = defaultdict(int)
    wait_days = defaultdict(float)
    exit_n = defaultdict(int)
    exit_cancer = defaultdict(int)
    dec = {n["id"]: {"n": 0, "chosen": defaultdict(int), "offered": defaultdict(int), "p": defaultdict(float),
                     "pn": defaultdict(int), "g": defaultdict(lambda: defaultdict(int)), "gn": defaultdict(int)}
           for n in g["nodes"] if n["kind"] == "decision"}
    stuck = 0
    for _, pr in measured:
        V = _visited(pr, node_ids, option_of, milestone_ids)
        for m in milestone_ids:
            if pr.t_diagnosis is not None and any(u in V for u in preds[m]):
                V.add(m)
        for v in V:
            visits[v] += 1
            if pr.patient.cancer:
                visits_cancer[v] += 1
            P = [u for u in preds[v] if u in V]
            P = [u for u in P if not any(w != u and w in reach(u) for w in P)]
            for u in P:
                edge_n[(u, v)] += 1
        for e in pr.events:
            if e.node not in node_ids:
                continue
            w = e.t_start - e.t_ready
            waits[e.node].append(w)
            svc[e.node].append(e.t_result - e.t_start)
            wait_days[e.node] += w
            attempts[e.node] += 1
            res_count[e.node][2 if e.result is None else (0 if e.result else 1)] += 1
        for c in pr.choices:
            d = dec.get(c["node"])
            if not d:
                continue
            d["n"] += 1
            d["chosen"][c["chosen"]] += 1
            for o in c["offered"]:
                d["offered"][o] += 1
            for o, p in c["probs"].items():
                d["p"][o] += p
                d["pn"][o] += 1
            d["g"][pr.patient.group][c["chosen"]] += 1
            d["gn"][pr.patient.group] += 1
        if pr.exit_node in node_ids:
            exit_n[pr.exit_node] += 1
            if pr.patient.cancer:
                exit_cancer[pr.exit_node] += 1
        if pr.outcome == "stuck":
            stuck += 1

    # edges: structure plus counts; shortcuts nobody used are dropped
    edges = []
    for e in g["edges"]:
        n = edge_n.get((e["source"], e["target"]), 0)
        if e.get("shortcut") and n == 0:
            continue
        edges.append({**e, "n": n})
    g["edges"] = edges

    # critical path: same code as compute_metrics -> equals node_breakdown (pooled over cohorts)
    treated = [pr for run in logs for pr in run.patients
               if pr.patient.arrival >= run.warmup_days and pr.patient.cancer and pr.t_treatment is not None]
    _, crit = _breakdown(treated, critical_only=True)
    total_crit = sum(v["wait"] + v["service"] for v in crit.values()) or 1.0

    steps = {}
    for n in g["nodes"]:
        nid = n["id"]
        if n["kind"] == "decision":
            continue
        s = {"n": visits.get(nid, 0), "n_cancer": visits_cancer.get(nid, 0)}
        if nid in waits:
            w, sv = np.array(waits[nid]), np.array(svc[nid])
            c = crit.get(nid, {"wait": 0.0, "service": 0.0, "n": 0})
            s.update({
                "events": attempts[nid],
                "wait_mean": _r(w.mean()), "wait_median": _r(np.median(w)), "wait_p90": _pct(w, 90),
                "service_mean": _r(sv.mean()), "service_median": _r(np.median(sv)),
                "wait_days": _r(wait_days[nid], 1),
                "positive": res_count[nid][0], "negative": res_count[nid][1], "nondiagnostic": res_count[nid][2],
                "critical_n": c["n"], "critical_wait": _r(c["wait"], 2), "critical_service": _r(c["service"], 2),
                "critical_share": _r((c["wait"] + c["service"]) / total_crit, 4),
                "critical_wait_share": _r(c["wait"] / total_crit, 4),
            })
        steps[nid] = s

    resources = {}
    for rid, r in logs[0].resources.items():
        spec = scenario.resources.get(rid, {})
        label = spec.get("label") or rid.replace("_", " ").capitalize()
        util = [lg.resources.get(rid, {}).get("utilisation") for lg in logs]
        util = [u for u in util if u is not None]
        resources[rid] = {"label": label, "type": r.get("type", spec.get("type", "server")),
                          **({"capacity_per_day": r["capacity_per_day"]} if "capacity_per_day" in r else {}),
                          **({"utilisation": _r(mean(util), 3)} if util else {})}
    for n in g["nodes"]:
        rid = n.get("resource")
        if rid and rid not in resources:
            resources[rid] = {"label": rid.replace("_", " ").capitalize(), "type": scenario.resources.get(rid, {}).get("type", "server")}

    decisions = {}
    for nid, d in dec.items():
        if not d["n"]:
            decisions[nid] = {"n": 0, "options": list(node_by[nid]["options"]), "chosen": {}, "share": {}, "mean_probability": {}, "by_group": {}}
            continue
        opts = list(node_by[nid]["options"])
        decisions[nid] = {
            "n": d["n"], "options": opts,
            "offered": {o: d["offered"][o] for o in opts},
            "chosen": {o: d["chosen"][o] for o in opts},
            "share": {o: _r(d["chosen"][o] / d["n"], 4) for o in opts},
            "mean_probability": {o: _r(d["p"][o] / d["pn"][o], 4) if d["pn"][o] else None for o in opts},
            "by_group": {gr: {"n": d["gn"][gr], "share": {o: _r(d["g"][gr][o] / d["gn"][gr], 4) for o in opts}}
                         for gr in sorted(d["g"])},
        }

    exits = {nid: {"n": exit_n.get(nid, 0), "n_cancer": exit_cancer.get(nid, 0), "outcome": node_by[nid].get("outcome")}
             for nid in node_ids if node_by[nid]["kind"] == "exit"}

    # headline metrics: mean over cohorts, as the dashboard does; totals: pooled counts
    ms = [compute_metrics(run, scenario) for run in logs]

    def avg(k):
        xs = [m[k] for m in ms if m.get(k) is not None]
        return _r(mean(xs), 4) if xs else None
    metrics = {k: avg(k) for k in HEADLINE}
    groups = sorted({pr.patient.group for _, pr in measured})
    by_group = {}
    for gr in groups:
        rows = [m["by_group"].get(gr) for m in ms if gr in m["by_group"]]
        by_group[gr] = {"n": sum(r["n"] for r in rows), "n_cancer": sum(r["n_cancer"] for r in rows),
                        **{k: _r(mean([r[k] for r in rows if r[k] is not None]), 4) if any(r[k] is not None for r in rows) else None
                           for k in ("median_days_to_treatment", "share_within_target", "median_days_to_diagnosis")},
                        "missed_cancers": sum(r["missed_cancers"] for r in rows)}
    totals = {"n": sum(m["n"] for m in ms), "n_cancer": sum(m["n_cancer"] for m in ms),
              "missed_cancers": sum(m["missed_cancers"] for m in ms),
              "untreated_cancers": sum(m["untreated_cancers"] for m in ms),
              "treated_cancers": len(treated), "stuck": stuck, "cohorts": len(logs)}

    rng = np.random.default_rng(seed)
    pick, strata = _sample(measured, sample, cancer_share, rng)
    cohort = [_trace(pr, s) for s, pr in pick]
    cohort.sort(key=lambda t: (t["cohort"], t["id"]))
    horizon = max([t["t_exit"] for t in cohort if t["t_exit"] is not None] + [1.0])

    lost = sorted(({"node": nid, "label": node_by[nid]["short"], "wait": s["critical_wait"], "service": s["critical_service"],
                    "share": s["critical_share"], "wait_share": s["critical_wait_share"], "n_critical": s["critical_n"],
                    "wait_median": s.get("wait_median"), "wait_p90": s.get("wait_p90")}
                   for nid, s in steps.items() if s.get("critical_wait") is not None and s.get("critical_n")),
                  key=lambda x: -x["wait"])

    return {
        "format": FORMAT,
        "scenario": logs[0].scenario, "flowchart": fc.id, "policy": logs[0].policy,
        "seeds": [lg.seed for lg in logs], "synthetic": True,
        "clock_start": scenario.raw.get("clock_start"), "target_days": logs[0].target_days,
        "warmup_days": logs[0].warmup_days,
        "totals": totals, "metrics": metrics, "by_group": by_group,
        "graph": g, "steps": steps, "resources": resources,
        "queues": _queue_series(logs, [n["id"] for n in g["nodes"] if n["kind"] == "step" and n["id"] in waits], queue_points),
        "decisions": decisions, "exits": exits, "time_lost": lost,
        "cohort": {"seed": seed, "size": len(cohort), "horizon": _r(horizon, 1), "strata": strata,
                   "time_zero": "each patient's own first contact (day 0)", "patients": cohort},
        "meta": meta or {},
    }

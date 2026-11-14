"""Export per-patient timelines from the pathway simulator for the dot animation.

Runs the same held-out cohorts that demo/export.py uses, so the on-time shares the
animation counts match the dashboard numbers exactly (checked at export time and
printed). Only cancer patients measured after the warm-up are exported, the same
population as `share_within_target`.

Needs a checkout of the simulator code (branch overnight/sim):

    python video/dots/export_dots.py --sim /path/to/checkout-of-overnight-sim

Writes video/dots/dots_data.js (a plain script, so index.html works from file://).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

STAGE_LABEL = {
    "detection": "Detection",
    "referral": "Referral",
    "diagnosis": "Diagnosis",
    "treatment_start": "Treatment start",
}
STAGE_ORDER = ["detection", "referral", "diagnosis", "treatment_start"]


def patient_rows(sc, run):
    rows = []
    for pr in run.patients:
        p = pr.patient
        if not p.cancer or p.arrival < run.warmup_days:
            continue
        a = p.arrival
        evs = [e for e in pr.events if e.critical] or list(pr.events)
        evs.sort(key=lambda e: (e.t_ready, e.t_start))
        path = []
        for e in evs:
            path.append([e.node, e.stage, round(e.t_ready - a, 3), round(e.t_start - a, 3), round(e.t_result - a, 3)])
        tt = None if pr.t_treatment is None else round(pr.t_treatment - a, 3)
        tx = None if pr.t_exit is None else round(pr.t_exit - a, 3)
        rows.append({"g": p.group, "tt": tt, "tx": tx, "out": pr.outcome, "ft": bool(pr.priority), "path": path})
    return rows


def layout(sc, fc, rows):
    """Place every node that appears on a critical path: stage zone, then order by median ready time."""
    ready = defaultdict(list)
    stage = {}
    for r in rows:
        for node, st, t_ready, _, _ in r["path"]:
            ready[node].append(t_ready)
            stage[node] = st
    nodes = []
    for node, ts in ready.items():
        n = fc.nodes.get(node) if hasattr(fc, "nodes") else None
        label = (getattr(n, "label", None) or getattr(n, "test", None) or node) if n else node
        nodes.append({"id": node, "stage": stage[node], "label": str(label).replace("_", " "),
                      "order": statistics.median(ts), "count": len(ts)})
    stages = [s for s in STAGE_ORDER if any(n["stage"] == s for n in nodes)]
    stages += sorted({n["stage"] for n in nodes} - set(stages))
    nodes.sort(key=lambda n: (stages.index(n["stage"]), n["order"]))
    return [{"id": s, "label": STAGE_LABEL.get(s, s.replace("_", " ").capitalize())} for s in stages], nodes


def variant(sc, fc, held, label, key, expect=None):
    from pathway_sim import compute_metrics, simulate
    rows, shares = [], []
    for seed, pts in held:
        run = simulate(sc, fc, pts, seed=seed)
        rows += patient_rows(sc, run)
        shares.append(compute_metrics(run, sc)["share_within_target"])
    stages, nodes = layout(sc, fc, rows)
    target = sc.target_days
    on_time = sum(1 for r in rows if r["tt"] is not None and r["tt"] <= target) / max(len(rows), 1)
    share_mean = round(statistics.mean(shares), 4)
    print(f"  {key:<14} dots {len(rows):5d}  on time (pooled) {on_time:.3f}  mean of cohorts {share_mean:.4f}"
          + (f"  dashboard {expect:.4f}" if expect is not None else ""))
    if expect is not None and abs(share_mean - expect) > 0.0015:
        print(f"  WARNING: {key} share {share_mean} does not match the dashboard bundle {expect}")
    return {"key": key, "label": label, "share": share_mean, "stages": stages, "nodes": nodes, "patients": rows}


def bundle_share(bundle, sid, pick):
    for s in bundle["scenarios"]:
        if s["id"] != sid:
            continue
        if pick == "baseline":
            return s["baseline"]["metrics"]["share_within_target"]
        for v in s["variants"]:
            if v.get("role") == pick or v.get("flowchart_id") == pick:
                return v["metrics"]["share_within_target"]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", required=True, help="checkout of the simulator (branch overnight/sim)")
    ap.add_argument("--out", default=str(HERE / "dots_data.js"))
    a = ap.parse_args(argv)
    sim = Path(a.sim).resolve()
    sys.path.insert(0, str(sim))
    from optimiser.search import cohorts
    from pathway_sim import load_scenario
    from pathway_sim.scenario import parse_flowchart

    bundle = json.loads((sim / "demo" / "data" / "demo_bundle.json").read_text())
    out = {"generated_from": "pathway_sim, held-out cohorts as in demo/export.py", "scenarios": []}

    print("finland_lung")
    sc = load_scenario(sim / "scenarios" / "finland_lung.yaml")
    held = cohorts(sc, (301, 302), int(sc.raw.get("default_n", 2000)))
    opt = parse_flowchart("suggested", json.loads((sim / "runs" / "opt_finland.json").read_text())["flowchart_after"])
    fi = [
        variant(sc, sc.flowcharts["baseline"], held, "Today's pathway", "baseline",
                bundle_share(bundle, "finland_lung", "baseline")),
        variant(sc, opt, held, "Optimiser's change: priority after the hospital handles the referral", "optimiser",
                bundle_share(bundle, "finland_lung", "optimiser")),
        variant(sc, sc.flowcharts["bundled_workup"], held, "CT and PET-CT ordered together at the specialist visit",
                "bundled", bundle_share(bundle, "finland_lung", "bundled_workup")),
    ]
    out["scenarios"].append({"id": "finland", "title": "Synthetic Finnish county, lung cancer",
                             "target_days": sc.target_days, "synthetic": True, "variants": fi})

    print("stokstad")
    sc = load_scenario(sim / "scenarios" / "generated" / "stokstad_calibrated.yaml")
    held = cohorts(sc, (201, 202, 203), 1000)
    sug = parse_flowchart("suggested", json.loads((sim / "runs" / "opt_stokstad_fastpet.json").read_text())["flowchart_after"])
    st = [
        variant(sc, sc.flowcharts["observed"], held, "Observed pathway (Stokstad et al. 2019)", "observed",
                bundle_share(bundle, "stokstad", "baseline")),
        variant(sc, sc.flowcharts["optimal"], held, "Authors' reordered pathway, simulated", "authors",
                bundle_share(bundle, "stokstad", "authors_pathway")),
        variant(sc, sug, held, "Optimiser, found blind (with the faster PET-CT)", "optimiser",
                bundle_share(bundle, "stokstad", "optimiser")),
    ]
    out["scenarios"].append({"id": "norway", "title": "Norwegian hospital, rebuilt from Stokstad et al. 2019",
                             "target_days": sc.target_days, "synthetic": False, "variants": st})

    Path(a.out).write_text("window.DOTS_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print("wrote", a.out, f"{Path(a.out).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

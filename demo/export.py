"""Build demo/data/demo_bundle.json from real simulator and optimiser runs.

    python demo/export.py                 # all scenarios that exist
    python demo/export.py --quick         # smaller cohorts, for a smoke test

Every number in the bundle comes from a run in this script; nothing is typed in by hand except
the published Stokstad figures (with their source). Metrics are reported on held-out cohorts
the optimiser never saw.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optimiser import Config, search  # noqa: E402
from optimiser.search import cohorts, evaluate  # noqa: E402
from pathway_sim import load_scenario  # noqa: E402
from pathway_sim.scenario import Flowchart, Scenario  # noqa: E402

OUT = ROOT / "demo" / "data" / "demo_bundle.json"


# ---------------------------------------------------------------- display flowchart
def _preds(fc: Flowchart, nid: str) -> list[str]:
    n = fc.nodes[nid]
    ps = list(n.after) + list(n.after_any) + list(n.after_optional)
    for c in fc.nodes.values():
        if c.kind == "choice" and nid in c.options:
            ps.append(c.id)
    return ps


def _clean(label: str) -> str:
    return label.split(" (")[0].strip()


def display_flowchart(sc: Scenario, fc: Flowchart) -> dict:
    """Collapse logic nodes (choices, joins) into the steps a patient experiences.
    Display node id = test id (alternative timings of the same test merge into one step)."""
    disp_of = {}
    labels: dict[str, list[str]] = defaultdict(list)
    for n in fc.nodes.values():
        if n.test and sc.tests[n.test].get("kind", "test") != "treatment" or (n.kind == "exit"):
            did = n.test if n.kind != "exit" else n.id
            if n.test and sc.tests[n.test].get("kind") == "admin" and n.test == "baseline_ct":
                did = n.test
            disp_of[n.id] = did
            labels[did].append(n.label or n.id.replace("_", " "))
    memo: dict[str, dict] = {}

    def nearest(nid: str) -> dict:
        """display predecessor -> True if reached only through optional prerequisites."""
        if nid in memo:
            return memo[nid]
        memo[nid] = {}
        n = fc.nodes[nid]
        out: dict[str, bool] = {}
        for p in _preds(fc, nid):
            opt = p in n.after_optional
            sub = {disp_of[p]: False} if p in disp_of else nearest(p)
            for d, o in sub.items():
                out[d] = out.get(d, True) and (o or opt)
        memo[nid] = out
        return out

    edges: dict[str, dict] = defaultdict(dict)
    for nid, did in disp_of.items():
        for p, opt in nearest(nid).items():
            if p != did:
                edges[did][p] = edges[did].get(p, True) and opt

    def reach(a: str, seen=None) -> set:
        """ancestors through required edges only (an optional step never makes another redundant)."""
        seen = seen if seen is not None else set()
        for p, opt in edges.get(a, {}).items():
            if not opt and p not in seen:
                seen.add(p)
                reach(p, seen)
        return seen

    nodes = []
    for did in dict.fromkeys(disp_of.values()):
        prs = edges.get(did, {})
        reduced = [p for p in prs if not any(p in reach(q) for q, o in prs.items() if q != p and not o)]
        any_node = next(n for n in fc.nodes.values() if disp_of.get(n.id) == did)
        stage = sc.stage_of(any_node)
        node = {"id": did, "label": min(labels[did], key=len), "stage": stage}
        if reduced:
            node["after"] = sorted(reduced)
        if any_node.kind == "exit":
            node["kind"] = "exit"
        nodes.append(node)
    return {"id": fc.id, "nodes": nodes}


def rekey_nodes(m: dict, sc: Scenario, fc: Flowchart) -> dict:
    """node_breakdown keyed by display node (test id), summing alternative timings."""
    m = dict(m)
    for key in ("node_breakdown", "node_breakdown_all"):
        agg: dict[str, dict] = {}
        for nid, v in (m.get(key) or {}).items():
            did = v.get("test") or nid
            a = agg.setdefault(did, {"wait": 0.0, "service": 0.0, "n": 0, "stage": v.get("stage")})
            a["wait"] = round(a["wait"] + v["wait"], 2)
            a["service"] = round(a["service"] + v["service"], 2)
            a["n"] += v["n"]
        m[key] = agg
    return m


# ---------------------------------------------------------------- assumptions table
def short_cite(s: dict) -> str:
    c = s.get("citation", s["id"])
    first = c.split(",")[0].split(" ")[0].strip(".")
    if "," in c and first and first[0].isupper() and len(first) > 2 and " et al" in c:
        return f"{first} et al. {s.get('year', '')}".strip()
    return c.split(".")[0][:70]


def assumptions() -> list[dict]:
    src = {}
    raw = yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())
    items = raw.get("sources", raw) if isinstance(raw, dict) else raw
    for s in items:
        src[s["id"]] = s
    rows = []
    for f in sorted((ROOT / "params").glob("*.yaml")):
        if f.name == "sources.yaml":
            continue
        data = yaml.safe_load(f.read_text()) or {}
        for section, params in data.items():
            if not isinstance(params, dict):
                continue
            for name, p in params.items():
                if not isinstance(p, dict) or "source" not in p:
                    continue
                val = p.get("value")
                unit = p.get("unit", "")
                s = src.get(p["source"])
                rows.append({
                    "parameter": name.replace("_", " "),
                    "value": f"{val} {unit}".strip() if unit not in ("fraction",) else (f"{round(100 * val)}%" if isinstance(val, (int, float)) else str(val)),
                    "source": short_cite(s) if s else "Our assumption",
                    "url": s.get("url") if s else None,
                    "status": "assumption" if p["source"] == "assumption" else "sourced",
                    "file": f"params/{f.name}",
                })
    return rows


# ---------------------------------------------------------------- scenarios
def metrics_on(sc, fc, held):
    m, _ = evaluate(sc, fc, held)
    return m


def build_stokstad(quick: bool) -> dict:
    sc = load_scenario(ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml")
    n = 300 if quick else 1000
    cfg = Config(n_train=n, heldout_seeds=(201, 202, 203), n_heldout=n)
    held = cohorts(sc, cfg.heldout_seeds, n)
    obs, fpet, opt = (sc.flowcharts[k] for k in ("observed", "faster_pet", "optimal"))
    res_fast = search(sc, "faster_pet", cfg, log=lambda *a: None)
    res_noeq = search(sc, "observed", cfg, log=lambda *a: None)
    from pathway_sim.scenario import parse_flowchart
    after_fast = parse_flowchart("suggested", res_fast["flowchart_after"])
    from pathway_sim.scenario import validate_flowchart
    validate_flowchart(sc, after_fast)
    m_obs = rekey_nodes(metrics_on(sc, obs, held), sc, obs)
    pub = sc.raw["published"]
    return {
        "id": "stokstad",
        "title": "Norwegian check: does the model reproduce a real hospital?",
        "description": "100 early-stage lung cancer patients at one Norwegian centre (Stokstad et al. 2019), rebuilt step by step. "
                       "Calibrated on the observed pathway only; everything else is a prediction.",
        "target_days": sc.target_days,
        "baseline": {"label": "Observed pathway", "metrics": m_obs},
        "variants": [
            {"label": "Suggested change (found without seeing the authors' answer)",
             "metrics": rekey_nodes(res_fast["heldout"]["after"], sc, after_fast),
             "changes": ["Use the faster PET-CT scanner (the same assumption the authors made)"] + [s["plain"] for s in res_fast["steps"]],
             "role": "optimiser"},
            {"label": "Faster PET-CT scan only", "metrics": rekey_nodes(metrics_on(sc, fpet, held), sc, fpet), "role": "faster_pet"},
            {"label": "Authors' reordered pathway, simulated", "metrics": rekey_nodes(metrics_on(sc, opt, held), sc, opt), "role": "authors_pathway"},
            {"label": "Suggested change without any new equipment",
             "metrics": rekey_nodes(res_noeq["heldout"]["after"], sc, obs),
             "changes_detail": [s["plain"] for s in res_noeq["steps"]], "role": "optimiser_no_new_equipment"},
        ],
        "published": {"baseline_share": pub["observed"]["share_within_target"],
                      "faster_pet_share": pub["faster_pet"]["share_within_target"],
                      "optimal_share": pub["optimal"]["share_within_target"],
                      "source": "Stokstad et al. 2019, BMC Health Services Research"},
        "flowchart_before": display_flowchart(sc, obs),
        "flowchart_after": display_flowchart(sc, after_fast),
        "optimiser": {k: res_fast[k] for k in ("steps", "selection_optimism_pp", "candidates_evaluated", "guardrails_heldout")},
        "optimiser_no_new_equipment": {k: res_noeq[k] for k in ("steps", "selection_optimism_pp", "candidates_evaluated")},
    }


def capacity_probe(sc: Scenario, fc: Flowchart, held, base: dict) -> list[dict]:
    """One more slot per day at each capacity-limited step: which helps most? (open question 4)"""
    rows = []
    for rid, r in sc.resources.items():
        if r.get("type", "server") != "server":
            continue
        new = fc.copy(fc.id)
        new.resource_overrides = {**new.resource_overrides, rid: {"capacity_per_day": int(r["capacity_per_day"]) + 1}}
        m = metrics_on(sc, new, held)
        rows.append({"resource": rid, "label": r.get("label", rid.replace("_", " ")),
                     "capacity_per_day": r["capacity_per_day"],
                     "delta_share_pp": round(100 * (m["share_within_target"] - base["share_within_target"]), 1),
                     "delta_median_days": round(m["median_days_to_treatment"] - base["median_days_to_treatment"], 1),
                     "utilisation": base["utilisation"].get(rid)})
    return sorted(rows, key=lambda x: -x["delta_share_pp"])


def build_capacity_scenario(path: Path, quick: bool, start: str = "baseline", compare: list[str] | None = None) -> dict:
    sc = load_scenario(path)
    n = int(sc.raw.get("default_n", 2000))
    n = max(300, n // 3) if quick else n
    cfg = Config(n_train=n, heldout_seeds=(301, 302) if not quick else (301,), n_heldout=n,
                 allow=("detach", "relax", "standardise", "fast_track"), max_steps=6)
    held = cohorts(sc, cfg.heldout_seeds, n)
    fc0 = sc.flowcharts[start]
    res = search(sc, start, cfg, log=lambda *a: None)
    from pathway_sim.scenario import parse_flowchart, validate_flowchart
    after = parse_flowchart("suggested", res["flowchart_after"])
    validate_flowchart(sc, after)
    base = metrics_on(sc, fc0, held)
    variants = [{"label": "Suggested change", "metrics": rekey_nodes(res["heldout"]["after"], sc, after),
                 "changes": [s["plain"] for s in res["steps"]] or ["No change passed the safety checks"], "role": "optimiser"}]
    for fid in compare or [k for k in sc.flowcharts if k != start]:
        fc = sc.flowcharts[fid]
        variants.append({"label": fc.description or fid.replace("_", " "), "metrics": rekey_nodes(metrics_on(sc, fc, held), sc, fc),
                         "role": "hand_written"})
    return {
        "id": sc.id, "title": sc.raw.get("title", "Finnish lung pathway (synthetic)"),
        "description": sc.description, "target_days": sc.target_days,
        "baseline": {"label": fc0.description or "Today's pathway", "metrics": rekey_nodes(base, sc, fc0)},
        "variants": variants,
        "flowchart_before": display_flowchart(sc, fc0), "flowchart_after": display_flowchart(sc, after),
        "optimiser": {k: res[k] for k in ("steps", "selection_optimism_pp", "candidates_evaluated", "guardrails_heldout")},
        "capacity_probe": capacity_probe(sc, fc0, held, base),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    scenarios = []
    print("stokstad ...", flush=True)
    scenarios.append(build_stokstad(a.quick))
    fi = ROOT / "scenarios" / "finland_lung.yaml"
    if fi.exists():
        print("finland_lung ...", flush=True)
        scenarios.append(build_capacity_scenario(fi, a.quick))
    bundle = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "fixture": False, "scenarios": scenarios, "assumptions": assumptions()}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(bundle, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()

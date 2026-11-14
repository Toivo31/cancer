"""Generate the mock-mode fixtures (spec 01 document shapes) from the shipped scenario YAML.

Run from the repo root:  .venv/bin/python web/scripts/make_fixtures.py
Writes web/src/mock/fixtures/templates.json. This is a stand-in for the service's own converter
(`pathway_sim/documents.py`); the web app only relies on the document shape, so when the service is
running the app reads the real documents instead. No numbers are invented: every value is copied from
the YAML, and probabilities come from the YAML's `mix` and `rules` (spec 02 migration).
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "src" / "mock" / "fixtures" / "templates.json"

TEMPLATES = [
    ("norway_check", "stokstad", "Norway check (Stokstad 2019)",
     "Stokstad et al. 2019, St Olavs Hospital: 100 stage I-II lung cancer patients, clock from referral to treatment, 42-day target."),
    ("finland_lung", "finland_lung", "Finnish lung cancer pathway (synthetic)",
     "Synthetic Finnish lung pathway in one wellbeing services county, clock from first contact to treatment, 90-day provisional target."),
]


def world_doc(s: dict, new_id: str, name: str) -> dict:
    resources = {}
    for rid, r in (s.get("resources") or {}).items():
        resources[rid] = {k: r[k] for k in ("type", "capacity_per_day", "min_lead_days", "weekdays", "cutoff_days") if k in r}
        resources[rid]["source"] = r.get("source", "assumption")
    tests = {}
    for tid, t in (s.get("tests") or {}).items():
        tests[tid] = {k: t[k] for k in ("kind", "resource", "stage", "invasive", "cost_eur") if k in t}
        tests[tid]["source"] = t.get("source", "assumption")
    w = {
        "schema_version": 1, "id": new_id, "name": name,
        "clock_start": s.get("clock_start"), "target_days": s.get("target_days"),
        "default_n": s.get("default_n"), "arrivals": s.get("arrivals"),
        "resources": resources, "tests": tests,
    }
    if s.get("published"):
        w["published"] = s["published"]
    return w


def stub_points(policy: dict, nodes: list[dict], options: dict) -> dict:
    """Migrate engine policy (mix / rules / default) to the stub's tables (spec 02)."""
    by_id = {n["id"]: n for n in nodes}
    points = {}
    for pid, pol in (policy or {}).items():
        node = by_id.get(pid)
        if not node or node["kind"] != "decision":
            continue
        opts = list(options[pid])
        entry: dict = {}
        if "mix" in pol:
            entry["default"] = dict(pol["mix"])
        elif "default" in pol:
            entry["default"] = {o: (1.0 if o == pol["default"] else 0.0) for o in opts}
        else:
            entry["default"] = {o: round(1 / len(opts), 6) for o in opts}
        rules = []
        for r in pol.get("rules", []):
            if "choose" in r:
                rules.append({"when": r["when"], "probs": {o: (1.0 if o == r["choose"] else 0.0) for o in opts}})
        if rules:
            entry["rules"] = rules
        entry["source"] = pol.get("source", "assumption")
        points[pid] = entry
    return points


def flowchart_doc(world_id: str, fid: str, fc: dict, tests: dict) -> dict:
    nodes, edges, options = [], [], {}
    for n in fc["nodes"]:
        kind = n.get("kind", "step")
        if kind == "choice":
            kind = "decision"
        elif kind == "step" and not n.get("test"):
            kind = "join"
        node = {"id": n["id"], "kind": kind, "label": n.get("label") or n["id"]}
        for k in ("test", "when", "outcome", "milestone", "retry", "availability", "fast_track"):
            if n.get(k):
                node[k] = n[k]
        nodes.append(node)
        if kind == "decision":
            options[n["id"]] = list(n.get("options", []))
        for s in n.get("after", []):
            edges.append({"from": s, "to": n["id"], "type": "required"})
        for s in n.get("after_any", []):
            edges.append({"from": s, "to": n["id"], "type": "any"})
        for s in n.get("after_optional", []):
            edges.append({"from": s, "to": n["id"], "type": "optional"})
        for i, o in enumerate(n.get("options", []) if n.get("kind") == "choice" else []):
            edges.append({"from": n["id"], "to": o, "type": "option", "index": i})
    doc = {
        "schema_version": 1, "id": fid, "version": 1, "parent_version": None, "world_id": world_id,
        "name": fc.get("description") or fid, "nodes": nodes, "edges": edges,
        "decision_policy": {"backend": "stub", "mode": "sample", "points": stub_points(fc.get("policy"), nodes, options)},
        "test_overrides": fc.get("test_overrides", {}), "resource_overrides": fc.get("resource_overrides", {}),
        "edits_from_parent": [],
    }
    return doc


def main() -> int:
    out = []
    for tid, src, name, desc in TEMPLATES:
        s = yaml.safe_load((ROOT / "scenarios" / f"{src}.yaml").read_text())
        w = world_doc(s, tid, name)
        fcs = [flowchart_doc(tid, fid, fc, s.get("tests") or {}) for fid, fc in s["flowcharts"].items()]
        out.append({"id": tid, "name": name, "description": desc, "world": w, "flowcharts": fcs})
    # Real headline numbers for the unedited flowcharts, from the shipped demo bundle (mean of its seeds).
    # The mock service returns these for an unedited flowchart; it cannot recompute edited ones.
    bundle = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
    metrics = {}
    for sc in bundle["scenarios"]:
        tid = {"stokstad": "norway_check", "finland_lung": "finland_lung"}.get(sc["id"])
        for v in [sc["baseline"], *sc["variants"]]:
            m = v["metrics"]
            metrics[f"{tid}/{m['flowchart']}"] = {k: m.get(k) for k in ("n", "share_within_target", "median_days_to_treatment", "missed_cancers")}
    (OUT.parent / "mock_metrics.json").write_text(json.dumps(metrics, indent=1))
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT, OUT.stat().st_size, "bytes;", [(t["id"], [f["id"] for f in t["flowcharts"]]) for t in out])
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Export flow data for the offline flowchart page (demo/flow.html).

    python demo/export_flow.py                 # full export: demo/data/flow_*.json and demo/data/flow_bundle.js
    python demo/export_flow.py --fixtures      # small fixtures: docs/platform/fixtures/flow_{norway,finland}.json

Uses the same held-out cohorts and the same optimiser results as demo/export.py (runs/opt_*.json, which
record the changes the optimiser accepted), so the shares on the page match the dashboard bundle. The
script prints each variant's share next to the dashboard's and warns when they differ.

flow_bundle.js is a plain script (``window.FLOW_DATA = ...``) so flow.html opens from file:// with no server.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optimiser.search import cohorts  # noqa: E402
from pathway_sim import load_scenario, simulate  # noqa: E402
from pathway_sim.flow import build_flow  # noqa: E402
from pathway_sim.scenario import parse_flowchart, validate_flowchart  # noqa: E402

DATA = ROOT / "demo" / "data"
FIXTURES = ROOT / "docs" / "platform" / "fixtures"


def dashboard_share(bundle: dict, sid: str, role: str | None):
    for s in bundle["scenarios"]:
        if s["id"] != sid:
            continue
        if role in (None, "baseline"):
            return s["baseline"]["metrics"]["share_within_target"]
        for v in s["variants"]:
            if v.get("role") == role:
                return v["metrics"]["share_within_target"]
    return None


def opt_flowchart(sc, name: str, fid: str):
    d = json.loads((ROOT / "runs" / f"{name}.json").read_text())
    fc = parse_flowchart(fid, {**d["flowchart_after"], "id": fid})
    validate_flowchart(sc, fc)
    return fc, [s["plain"] for s in d["steps"]]


def make(sc, fc, held, key, label, role, note="", conditional=False, changes=None, sample=300, check=None, meta=None):
    logs = [simulate(sc, fc, pts, seed=s) for s, pts in held]
    flow = build_flow(logs, sc, fc, sample=sample, seed=7, meta={"variant": key, "label": label, **(meta or {})})
    share = flow["metrics"]["share_within_target"]
    line = f"  {key:<22} n={flow['totals']['n']:6d}  on time {share:.4f}"
    if check is not None:
        line += f"  dashboard {check:.4f}"
        if abs(share - check) > 0.0015:
            line += "  <-- DIFFERS"
    print(line, flush=True)
    return {"key": key, "label": label, "role": role, "note": note, "conditional": conditional,
            "changes": changes or [], "flow": flow}


def build(quick: bool = False, sample: int = 300) -> list[dict]:
    bundle = json.loads((DATA / "demo_bundle.json").read_text())
    out = []

    print("norway")
    sc = load_scenario(ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml")
    n = 300 if quick else 1000
    held = cohorts(sc, (201, 202, 203), n)
    pub = sc.raw["published"]
    no_eq, ch_no = opt_flowchart(sc, "opt_stokstad", "suggested_no_equipment")
    fast, ch_fast = opt_flowchart(sc, "opt_stokstad_fastpet", "suggested_faster_pet")
    variants = [
        make(sc, sc.flowcharts["observed"], held, "observed", "Observed pathway", "baseline",
             "Calibrated to the published observed pathway (Stokstad et al. 2019). Published: 40% treated within 42 days.",
             check=dashboard_share(bundle, "stokstad", "baseline"), sample=sample),
        make(sc, no_eq, held, "suggested", "Suggested change, no new equipment", "optimiser_no_new_equipment",
             "Found by the optimiser from the observed pathway only, on cohorts it never saw. No new equipment.",
             changes=ch_no, check=dashboard_share(bundle, "stokstad", "optimiser_no_new_equipment"), sample=sample),
        make(sc, sc.flowcharts["faster_pet"], held, "faster_pet", "Faster PET-CT scanner only", "faster_pet",
             "Same order, only the faster scanner (7-day wait). Published: 48%, not statistically significant.",
             check=dashboard_share(bundle, "stokstad", "faster_pet"), sample=sample),
        make(sc, fast, held, "suggested_faster_pet", "Suggested change with the faster PET-CT scanner", "optimiser",
             "Same search, starting from the authors' faster-scanner assumption. Needs the new scanner.",
             changes=ch_fast, check=dashboard_share(bundle, "stokstad", "optimiser"), sample=sample),
        make(sc, sc.flowcharts["optimal"], held, "authors", "Authors' reordered pathway (simulated)", "authors_pathway",
             "The reordering Stokstad et al. propose, run in our simulator. Their own estimate is 80%, a model estimate, not an observed result.",
             check=dashboard_share(bundle, "stokstad", "authors_pathway"), sample=sample),
    ]
    out.append({"id": "norway", "title": "Norwegian hospital, rebuilt from Stokstad et al. 2019", "synthetic": False,
                "target_days": sc.target_days, "default_pair": ["observed", "suggested"],
                "description": "100 early-stage lung cancer patients at one Norwegian centre, rebuilt step by step and calibrated on the "
                               "observed pathway only. Patients are simulated; the pathway and its waits are published.",
                "published": {"observed_share": pub["observed"]["share_within_target"],
                              "faster_pet_share": pub["faster_pet"]["share_within_target"],
                              "authors_estimate_share": pub["optimal"]["share_within_target"],
                              "source": "Stokstad et al. 2019, BMC Health Services Research (80% is the authors' model estimate)"},
                "variants": variants})

    print("finland")
    sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
    n = 6000 if quick else int(sc.raw.get("default_n", 18800))
    held = cohorts(sc, (301, 302), n)
    sug, ch = opt_flowchart(sc, "opt_fi_noft", "suggested")
    variants = [
        make(sc, sc.flowcharts["baseline"], held, "baseline", "Today's pathway", "baseline",
             "Synthetic Finnish county. Every number here is simulated from sourced and assumed parameters.",
             check=dashboard_share(bundle, "finland_lung", "baseline"), sample=sample),
        make(sc, sug, held, "suggested", "Suggested change (reorder only, no new capacity)", "optimiser",
             "Two reorderings found by the optimiser: reserve the treatment slot when the case goes to the tumour board; "
             "book the specialist visit as soon as the referral arrives. No fast lane, no new equipment.",
             changes=ch, check=dashboard_share(bundle, "finland_lung", "optimiser"), sample=sample),
    ]
    out.append({"id": "finland", "title": "Synthetic Finnish county, lung cancer", "synthetic": True,
                "target_days": sc.target_days, "default_pair": ["baseline", "suggested"],
                "description": "Synthetic patients with chest symptoms followed from first contact in primary care to treatment, "
                               "against a provisional 90-day target.",
                "published": None, "variants": variants})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="smaller cohorts")
    ap.add_argument("--fixtures", action="store_true", help="write the small fixtures in docs/platform/fixtures/")
    a = ap.parse_args(argv)
    if a.fixtures:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        scs = build(quick=True, sample=40)
        for sid, name in (("norway", "flow_norway"), ("finland", "flow_finland")):
            sc = next(s for s in scs if s["id"] == sid)
            # fixture = the observed/today variant's flow document; its sibling shows the optimised shape
            (FIXTURES / f"{name}.json").write_text(json.dumps(sc["variants"][0]["flow"], indent=1))
            (FIXTURES / f"{name}_optimised.json").write_text(json.dumps(sc["variants"][1]["flow"], indent=1))
        print("wrote fixtures in", FIXTURES)
        return
    scs = build(quick=a.quick)
    bundle = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "format": "flow-bundle/1",
              "scenarios": scs}
    DATA.mkdir(parents=True, exist_ok=True)
    for s in scs:
        for v in s["variants"]:
            (DATA / f"flow_{s['id']}_{v['key']}.json").write_text(json.dumps(v["flow"], separators=(",", ":")))
    (DATA / "flow_bundle.js").write_text("window.FLOW_DATA = " + json.dumps(bundle, separators=(",", ":")) + ";\n")
    print("wrote", DATA / "flow_bundle.js", f"{(DATA / 'flow_bundle.js').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

"""M8-4 capacity probe: "one more slot a day here gains X", with the spread across cohorts, on today's pathway and on the
suggested (accepted) pathway. Same method as demo/export.py::capacity_probe (resource_overrides, +1 slot a day), but over
6 cohorts (seeds 301-306) so each gain carries its cohort-to-cohort range.  Needs finland_suggested_flowchart.json.
    python3 docs/evidence_checks/capacity_probe.py       # ~5-8 min, writes docs/capacity_probe.json
"""
import json
import statistics as st
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import generate_patients, simulate  # noqa: E402
from pathway_sim.metrics import compute_metrics  # noqa: E402
from pathway_sim.scenario import scenario_from_dict  # noqa: E402

raw = yaml.safe_load((ROOT / "scenarios" / "finland_lung.yaml").read_text())
raw["flowcharts"]["suggested"] = json.loads((Path(__file__).parent / "finland_suggested_flowchart.json").read_text())["flowchart"]
sc = scenario_from_dict(raw)
n = int(raw["default_n"])
seeds = range(301, 307)
cohorts = {s: generate_patients(sc, n, s) for s in seeds}
servers = [r for r, v in sc.resources.items() if v.get("type", "server") == "server"]


def share(fid, over=None):
    out = {}
    for s in seeds:
        fc = sc.flowcharts[fid].copy(fid)
        if over:
            fc.resource_overrides = {**fc.resource_overrides, **over}
        sc.flowcharts["_probe"] = fc
        m = compute_metrics(simulate(sc, "_probe", cohorts[s], seed=s), sc)
        out[s] = (m["share_within_target"], m["median_days_to_treatment"])
    return out


result = {}
for fid in ("baseline", "suggested"):
    base = share(fid)
    rows = []
    for rid in servers:
        cap = int(sc.resources[rid]["capacity_per_day"])
        alt = share(fid, {rid: {"capacity_per_day": cap + 1}})
        d = [100 * (alt[s][0] - base[s][0]) for s in seeds]
        dm = [alt[s][1] - base[s][1] for s in seeds]
        rows.append({"resource": rid, "slots_now": cap, "delta_share_pp_mean": st.mean(d), "delta_share_pp_min": min(d), "delta_share_pp_max": max(d),
                     "delta_share_pp_by_cohort": dict(zip(seeds, d)), "delta_median_days_mean": st.mean(dm)})
        print(fid, rid, round(st.mean(d), 1), round(min(d), 1), round(max(d), 1), flush=True)
    result[fid] = {"base_share_by_cohort": {s: base[s][0] for s in seeds}, "rows": sorted(rows, key=lambda r: -r["delta_share_pp_mean"])}
(ROOT / "docs" / "capacity_probe.json").write_text(json.dumps(result, indent=1))

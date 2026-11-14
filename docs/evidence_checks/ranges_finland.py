"""Ranges next to the Finnish headline (18% -> 33%), from cohorts and from the existing sensitivity code.

Part A: baseline and the accepted flowchart on 12 independent cohorts (seeds 301-312; 301 and 302 are the held-out
        cohorts behind the headline, the rest are unseen by the search). Same n as the bundle.
Part B: pathway_sim.sensitivity on the accepted changes: every shortlisted assumption varied one at a time (x0.75 /
        x1.25, integer capacities +-1 slot) and 16 joint draws; comparison is baseline vs suggested (not the
        hand-written order-together pathway the older sensitivity files cover).
Needs finland_suggested_flowchart.json.
    python3 docs/evidence_checks/ranges_finland.py [--skip-sensitivity]     # A: ~2 min, B: ~10-20 min
"""
import argparse
import json
import statistics as st
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import generate_patients, load_scenario, simulate  # noqa: E402
from pathway_sim.metrics import compute_metrics  # noqa: E402
from pathway_sim.scenario import parse_flowchart  # noqa: E402
from pathway_sim import sensitivity as S  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--skip-sensitivity", action="store_true")
a = ap.parse_args()

doc = json.loads(Path(__file__).with_name("finland_suggested_flowchart.json").read_text())
assert doc["check_matches_bundle"], "saved flowchart does not reproduce the bundle"
raw = yaml.safe_load((ROOT / "scenarios" / "finland_lung.yaml").read_text())
raw["flowcharts"]["suggested"] = doc["flowchart"]

# ---- Part A
from pathway_sim.scenario import scenario_from_dict  # noqa: E402
sc = scenario_from_dict(raw)
n = int(raw["default_n"])
rows = []
for seed in range(301, 313):
    pts = generate_patients(sc, n, seed)
    r = {"seed": seed}
    for fid in ("baseline", "suggested"):
        m = compute_metrics(simulate(sc, fid, pts, seed=seed), sc)
        r[fid] = {"share": m["share_within_target"], "median": m["median_days_to_treatment"], "n_cancer": m["n_cancer"],
                  "groups": {g: v["share_within_target"] for g, v in m["by_group"].items()}}
    rows.append(r)
    print(seed, round(100 * r["baseline"]["share"], 1), round(100 * r["suggested"]["share"], 1), flush=True)


def spread(xs):
    return {"mean": st.mean(xs), "sd": st.stdev(xs), "min": min(xs), "max": max(xs)}


A = {"seeds": [r["seed"] for r in rows], "per_cohort": rows,
     "baseline_share": spread([r["baseline"]["share"] for r in rows]),
     "suggested_share": spread([r["suggested"]["share"] for r in rows]),
     "gain_pp": spread([100 * (r["suggested"]["share"] - r["baseline"]["share"]) for r in rows]),
     "baseline_median": spread([r["baseline"]["median"] for r in rows]),
     "suggested_median": spread([r["suggested"]["median"] for r in rows]),
     "gain_pp_by_group": {g: spread([100 * (r["suggested"]["groups"][g] - r["baseline"]["groups"][g]) for r in rows]) for g in ("non_specific", "site_specific")},
     "cohorts_where_suggested_beats_baseline": sum(1 for r in rows if r["suggested"]["share"] > r["baseline"]["share"])}
print("A gain pp", {k: round(v, 2) for k, v in A["gain_pp"].items()})
out = {"cohort_spread": A}

# ---- Part B
if not a.skip_sensitivity:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(raw, f)
        tmp = f.name
    res = S.run_sensitivity(tmp, [("baseline", "suggested")], seeds=[1], draws=16, noise_seeds=[1, 2, 3], log=lambda *x: print(*x, flush=True))
    out["sensitivity_suggested_vs_baseline"] = res
    Path(ROOT / "docs" / "evidence_checks" / "sensitivity_finland_suggested.md").write_text(S.markdown(res, 15))
(ROOT / "docs" / "ranges_finland.json").write_text(json.dumps(out, indent=1, default=str))
print("wrote docs/ranges_finland.json")

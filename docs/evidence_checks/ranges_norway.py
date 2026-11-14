"""Ranges next to the Norwegian numbers (observed 40, authors' pathway 80, optimiser 88 with the faster scanner, 67 without).

A: 100-patient cohorts (the size of the real study), 300 cohorts, central 95% range, for observed, faster PET-CT only,
   authors' pathway, and the two optimiser flowcharts (found once, on the best-fit calibration).
B: the same five flowcharts under each of the 11 accepted calibration sets (docs/validation_results.json), n=1000 x 3 seeds
   (201-203, the held-out seeds). The optimiser flowcharts were found under the best fit, so this is "how much of
   the 88 / 67 survives if another calibration that also reproduces the observed 40% is the truth".
Needs norway_suggested_flowcharts.json.     python3 docs/evidence_checks/ranges_norway.py    (~5 min)
"""
import copy
import json
import statistics as st
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import generate_patients, simulate  # noqa: E402
from pathway_sim.calibrate import apply_param  # noqa: E402
from pathway_sim.metrics import compute_metrics  # noqa: E402
from pathway_sim.scenario import scenario_from_dict  # noqa: E402

here = Path(__file__).parent
fl = json.loads((here / "norway_suggested_flowcharts.json").read_text())
assert fl["check_matches_bundle"]
cal = yaml.safe_load((ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml").read_text())
cal["flowcharts"]["opt_fast"] = fl["faster_pet_optimised"]
cal["flowcharts"]["opt_noeq"] = fl["observed_optimised"]
FL = {"observed": "observed", "faster_pet": "faster_pet", "authors": "optimal", "optimiser_faster_scanner": "opt_fast", "optimiser_no_new_equipment": "opt_noeq"}


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k)
    return xs[f] + (xs[min(f + 1, len(xs) - 1)] - xs[f]) * (k - f)


# ---- A
sc = scenario_from_dict(cal)
A = {k: [] for k in FL}
for seed in range(1, 301):
    pts = generate_patients(sc, 100, seed)
    for k, fid in FL.items():
        A[k].append(compute_metrics(simulate(sc, fid, pts, seed=seed), sc)["share_within_target"])
A = {k: {"mean": st.mean(v), "p2_5": pct(v, .025), "p97_5": pct(v, .975)} for k, v in A.items()}
print("A", {k: (round(100 * v["p2_5"]), round(100 * v["mean"]), round(100 * v["p97_5"])) for k, v in A.items()})

# ---- B  (accepted sets were fitted on scenarios/stokstad.yaml; apply them to the calibrated file, which carries the same grid keys)
val = json.loads((ROOT / "docs" / "validation_results.json").read_text())
B = []
for s in val["accepted_sets"]:
    raw = copy.deepcopy(cal)
    for k, v in s["params"].items():
        apply_param(raw, k, v)
        if k == "pet_triage_share":   # the found flowcharts carry their own copy of the mix
            for fid in ("opt_fast", "opt_noeq"):
                mix = raw["flowcharts"][fid]["policy"].get("pet_on_time", {}).get("mix")
                if mix is not None:
                    mix["pet_triage"], mix["pet_early_route"] = v["flowcharts.observed.policy.pet_on_time.mix.pet_triage"], v["flowcharts.observed.policy.pet_on_time.mix.pet_early_route"]
    sc2 = scenario_from_dict(raw)
    row = {}
    for k, fid in FL.items():
        vals = []
        for seed in (201, 202, 203):
            vals.append(compute_metrics(simulate(sc2, fid, generate_patients(sc2, 1000, seed), seed=seed), sc2)["share_within_target"])
        row[k] = st.mean(vals)
    B.append(row)
    print("B", {k: round(100 * v) for k, v in row.items()}, flush=True)
Bs = {k: {"min": min(r[k] for r in B), "median": st.median(r[k] for r in B), "max": max(r[k] for r in B)} for k in FL}
(ROOT / "docs" / "ranges_norway.json").write_text(json.dumps({"cohorts_of_100": A, "accepted_calibration_sets": {"n_sets": len(B), "per_set": B, "range": Bs}}, indent=1))
print("wrote docs/ranges_norway.json")

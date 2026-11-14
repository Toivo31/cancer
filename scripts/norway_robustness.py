"""Robustness of the Stokstad (Norway) validation. One command reproduces everything:

    python scripts/norway_robustness.py            # uses cached grid table if present (docs/review_checks/norway_grid_table.json)
    python scripts/norway_robustness.py --recompute  # rebuild the table from scratch (~40 min on 2 cores)

Stages: (1) table  = observed flowchart on an extended grid (n=1000, seed 1) and, for points that are
plausible under any analysis below, faster_pet + optimal; (2) analyses 1-4 filter that table (no new runs);
(3) analysis 5 (correlated delays, experiment scenarios) is in scripts/norway_correlated.py.
Nothing here edits scenarios/stokstad.yaml or the calibrated scenario.
"""
from __future__ import annotations
import itertools, json, math, sys
from multiprocessing import Pool
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pathway_sim.calibrate import evaluate  # noqa: E402

BASE = ROOT / "scenarios" / "stokstad.yaml"
TABLE = ROOT / "docs" / "review_checks" / "norway_grid_table.json"
N, SEED = 1000, 1
FCS = ["observed", "faster_pet", "optimal"]
TARGET = {"share": 0.40, "median": 46.5}
TOL = {"share": 0.04, "median": 2.5}

PET = "flowcharts.observed.policy.pet_on_time.mix."
# original grid values are a subset (marked in ORIG); the rest extends past the edges
G_BRONCH = [1, 3, 6, 10]
G_TREAT = [(13, 22.5), (10, 17), (8, 14), (6, 10.5), (4, 7.0), (2, 3.5)]
G_CUT = [0, 1, 2, 4]
G_EXTRA = [0.01, 2, 4, 6]
G_PET = [0.0, 0.5, 0.8, 0.9, 1.0]
ORIG = {"bronch": {3, 6, 10}, "treat": {13, 10, 8, 6}, "cut": {0, 2}, "extra": {0.01, 2}, "pet": {0.0, 0.5, 0.8, 1.0}}


def grid_points():
    pts = []
    for b, (s, r), c, e, p in itertools.product(G_BRONCH, G_TREAT, G_CUT, G_EXTRA, G_PET):
        pts.append({"bronch": b, "surg": s, "rt": r, "cut": c, "extra": e, "pet": p})
    return pts


def to_params(pt):
    return {"tests.bronchoscopy.wait.median": pt["bronch"],
            "treatment_wait_after_board": {"tests.surgery_booking.wait.median": pt["surg"],
                                           "tests.radiotherapy_booking.wait.median": pt["rt"]},
            "resources.tumour_board.cutoff_days": pt["cut"],
            "tests.first_visit.extra_wait.median": pt["extra"],
            "pet_triage_share": {PET + "pet_triage": pt["pet"], PET + "pet_early_route": round(1 - pt["pet"], 4)}}


def in_orig(pt):
    return (pt["bronch"] in ORIG["bronch"] and pt["surg"] in ORIG["treat"] and pt["cut"] in ORIG["cut"]
            and pt["extra"] in ORIG["extra"] and pt["pet"] in ORIG["pet"])


_RAW = None


def _work(args):
    global _RAW
    if _RAW is None:
        _RAW = yaml.safe_load(BASE.read_text())
    i, pt, fcs, n, seeds = args
    out = evaluate(_RAW, to_params(pt), fcs, n, seeds)
    return i, out


def run_parallel(jobs, procs=2):
    with Pool(procs) as p:
        return dict(p.imap_unordered(_work, jobs, chunksize=4))


def build_table(recompute=False):
    if TABLE.exists() and not recompute:
        return json.loads(TABLE.read_text())
    pts = grid_points()
    print(f"screening {len(pts)} grid points on observed (n={N}, seed {SEED})", flush=True)
    scr = run_parallel([(i, pt, ["observed"], N, [SEED]) for i, pt in enumerate(pts)])
    rows = [{"i": i, "pt": pt, "in_orig_grid": in_orig(pt), "observed": scr[i]["observed"]} for i, pt in enumerate(pts)]
    # predictions wherever the fit is within a wide box (covers single-target, tolerance and noise analyses)
    need = [r for r in rows if abs(r["observed"]["share_within_target"] - TARGET["share"]) <= 0.12
            or abs(r["observed"]["median_days_to_treatment"] - TARGET["median"]) <= 8]
    print(f"predicting faster_pet+optimal at {len(need)} points", flush=True)
    pr = run_parallel([(r["i"], r["pt"], ["faster_pet", "optimal"], N, [SEED]) for r in need])
    for r in rows:
        if r["i"] in pr:
            r.update(pr[r["i"]])
    t = {"n": N, "seed": SEED, "rows": rows}
    TABLE.write_text(json.dumps(t))
    return t


if __name__ == "__main__":
    t = build_table("--recompute" in sys.argv)
    print(len(t["rows"]), "rows")
    from norway_analyses import run_all  # noqa: E402
    run_all(t)

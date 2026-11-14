"""Analysis 5: does a mechanism that damps the faster-PET gain fix the over-prediction? Experiment only.

(a) within-patient correlated delays: every waiting-time draw of a patient shares a latent 'slowness' z_p
    (u' = Phi(rho z_p + sqrt(1-rho^2) Phi^-1(u)), marginals unchanged). Implemented by wrapping engine.uniform here;
    the engine and scenarios/stokstad.yaml are not touched.
(b) the 'incomplete work-up at the board, discussed again next week' mechanism (16%), existing experiment
    scenario scenarios/experiments/stokstad_incomplete_board_observed_and_faster_pet.yaml (see docs/external_checks.md).
Each variant is recalibrated on the observed flowchart over a reduced grid; predictions are for faster_pet and optimal.

    python scripts/norway_correlated.py
"""
from __future__ import annotations
import itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
from statistics import NormalDist, median
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import pathway_sim.engine as eng  # noqa: E402
from pathway_sim.calibrate import evaluate  # noqa: E402
from norway_robustness import to_params  # noqa: E402

_N = NormalDist()
_orig = eng.uniform
RHO = 0.0


def _wrapped(seed, pid, *key):
    u = _orig(seed, pid, *key)
    if RHO > 0 and key and key[0] in ("wait", "extra"):
        z = _N.inv_cdf(_orig(seed, pid, "slowness"))
        return _N.cdf(RHO * z + (1 - RHO * RHO) ** 0.5 * _N.inv_cdf(u))
    return u


eng.uniform = _wrapped

N, SEED = 1000, 1
G = dict(bronch=[3, 6], surgrt=[(10, 17), (8, 14), (6, 10.5), (4, 7.0), (2, 3.5)], cut=[0, 2], extra=[0.01, 2, 4], pet=[0.0, 0.5, 0.8, 1.0])
TGT = {"share": (0.40, 0.04), "median": (46.5, 2.5)}
SCEN = {"base": "scenarios/stokstad.yaml", "board": "scenarios/experiments/stokstad_incomplete_board_observed_and_faster_pet.yaml"}
_raw = {}


def pts():
    return [{"bronch": b, "surg": s, "rt": r, "cut": c, "extra": e, "pet": p}
            for b, (s, r), c, e, p in itertools.product(G["bronch"], G["surgrt"], G["cut"], G["extra"], G["pet"])]


def work(a):
    scen, rho, i, pt, fcs = a
    global RHO
    RHO = rho
    if scen not in _raw:
        _raw[scen] = yaml.safe_load((ROOT / SCEN[scen]).read_text())
    return i, evaluate(_raw[scen], to_params(pt), fcs, N, [SEED])


def run(scen, rho):
    P = pts()
    with Pool(2) as p:
        scr = dict(p.imap_unordered(work, [(scen, rho, i, pt, ["observed"]) for i, pt in enumerate(P)], chunksize=4))
        acc = [i for i, o in scr.items() if abs(o["observed"]["share_within_target"] - 0.40) <= 0.04 and abs(o["observed"]["median_days_to_treatment"] - 46.5) <= 2.5]
        pr = dict(p.imap_unordered(work, [(scen, rho, i, P[i], ["faster_pet", "optimal"]) for i in acc], chunksize=2))
    def band(fc):
        xs = [pr[i][fc]["share_within_target"] for i in acc]
        return None if not xs else {"min": round(min(xs), 3), "median": round(median(xs), 3), "max": round(max(xs), 3)}
    err = lambda o: ((o["share_within_target"] - .4) / .04) ** 2 + ((o["median_days_to_treatment"] - 46.5) / 2.5) ** 2
    bi = min(scr, key=lambda i: err(scr[i]["observed"]))
    gains = [pr[i]["faster_pet"]["share_within_target"] - scr[i]["observed"]["share_within_target"] for i in acc]
    return {"scenario": scen, "rho": rho, "grid_points": len(P), "accepted": len(acc), "faster_pet": band("faster_pet"), "optimal": band("optimal"),
            "faster_pet_gain_over_observed_pts": None if not gains else [round(100 * min(gains)), round(100 * median(gains)), round(100 * max(gains))],
            "best_fit_point": {"pt": P[bi], "observed": scr[bi]["observed"]},
            "accepted_pet_share_levels": sorted({P[i]["pet"] for i in acc}), "accepted_surg_levels": sorted({P[i]["surg"] for i in acc})}


if __name__ == "__main__":
    out = []
    for scen, rho in (("base", 0.0), ("base", 0.3), ("base", 0.6), ("base", 0.9), ("board", 0.0), ("board", 0.6)):
        r = run(scen, rho)
        print(json.dumps(r), flush=True)
        out.append(r)
    (ROOT / "docs" / "review_checks" / "norway_mechanisms.json").write_text(json.dumps(
        {"n": N, "seed": SEED, "grid": {k: v for k, v in G.items()}, "runs": out}, indent=1))

"""Analyses 1-4 of the Norway robustness check; pure filters over the cached grid table (no new simulation
except the cohort-noise draw in analysis 4). Called from scripts/norway_robustness.py."""
from __future__ import annotations
import json, sys
from pathlib import Path
from statistics import median
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "review_checks"
TARGET = {"share": 0.40, "median": 46.5}
TOL = {"share": 0.04, "median": 2.5}
PARAMS = ["bronch", "surg", "cut", "extra", "pet"]
EDGE = {"bronch": (1, 10), "surg": (2, 13), "cut": (0, 4), "extra": (0.01, 6), "pet": (0.0, 1.0)}
ORIG_EDGE = {"bronch": (3, 10), "surg": (6, 13), "cut": (0, 2), "extra": (0.01, 2), "pet": (0.0, 1.0)}


def sh(r, fc="observed"):
    return r[fc]["share_within_target"]


def md(r, fc="observed"):
    return r[fc]["median_days_to_treatment"]


def accepted(rows, use=("share", "median"), tol=TOL, tgt=TARGET):
    out = []
    for r in rows:
        ok = True
        if "share" in use:
            ok &= abs(sh(r) - tgt["share"]) <= tol["share"] + 1e-12
        if "median" in use:
            ok &= abs(md(r) - tgt["median"]) <= tol["median"] + 1e-12
        if ok:
            out.append(r)
    return out


def band(rows, fc):
    xs = [sh(r, fc) for r in rows if fc in r]
    if not xs:
        return None
    return {"n": len(xs), "min": round(min(xs), 3), "p10": round(float(np.percentile(xs, 10)), 3), "median": round(float(median(xs)), 3),
            "p90": round(float(np.percentile(xs, 90)), 3), "max": round(max(xs), 3)}


def gain_band(rows, fc):
    xs = [sh(r, fc) - sh(r) for r in rows if fc in r]
    return None if not xs else {"min": round(min(xs), 3), "median": round(float(median(xs)), 3), "max": round(max(xs), 3)}


def param_ranges(rows):
    return {p: [min(r["pt"][p] for r in rows), max(r["pt"][p] for r in rows)] for p in PARAMS} if rows else None


def at_edge(rows, edges):
    return {p: sum(1 for r in rows if r["pt"][p] in edges[p]) for p in PARAMS}


def err(r):
    return ((sh(r) - TARGET["share"]) / TOL["share"]) ** 2 + ((md(r) - TARGET["median"]) / TOL["median"]) ** 2


def a1(rows):
    orig = [r for r in rows if r["in_orig_grid"]]
    acc_o, acc_e = accepted(orig), accepted(rows)
    best_o, best_e = min(orig, key=err), min(rows, key=err)
    res = {
        "n_grid_original_subset": len(orig), "n_grid_extended": len(rows),
        "accepted_original_subset": len(acc_o), "accepted_extended": len(acc_e),
        "accepted_in_extension_only": len(acc_e) - len(acc_o),
        "pred_original_subset": {fc: band(acc_o, fc) for fc in ("faster_pet", "optimal")},
        "pred_extended": {fc: band(acc_e, fc) for fc in ("faster_pet", "optimal")},
        "gain_extended": {fc: gain_band(acc_e, fc) for fc in ("faster_pet", "optimal")},
        "param_range_accepted_original": param_ranges(acc_o), "param_range_accepted_extended": param_ranges(acc_e),
        "n_accepted_at_extended_grid_edge": at_edge(acc_e, EDGE),
        "n_accepted_at_original_grid_edge": at_edge(acc_o, ORIG_EDGE),
        "best_fit_original": {"pt": best_o["pt"], "observed": best_o["observed"]},
        "best_fit_extended": {"pt": best_e["pt"], "observed": best_e["observed"]},
        "note": "cut=0 and pet=1.0 are physical bounds (no negative cutoff; share cannot exceed 1), so 'at the edge' there is not extendable.",
    }
    # accepted set restricted to interior of every extendable parameter
    res["accepted_interior_of_extendable_params"] = sum(1 for r in acc_e if r["pt"]["bronch"] not in (1, 10) and r["pt"]["surg"] not in (2, 13)
                                                          and r["pt"]["cut"] != 4 and r["pt"]["extra"] != 6)
    (OUT / "norway_grid_extension.json").write_text(json.dumps(res, indent=1))
    return res, acc_e


def a2(rows, acc):
    X = np.array([[r["pt"][p] for p in PARAMS] for r in rows], float)
    Z = (X - X.mean(0)) / X.std(0)
    Y = np.array([[sh(r), md(r)] for r in rows], float)
    res = {"standardised_coef": {}, "r2": {}}
    for j, name in enumerate(["share", "median"]):
        y = Y[:, j]
        A = np.c_[np.ones(len(Z)), Z]
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        pred = A @ beta
        res["standardised_coef"][name] = {p: round(float(b), 4) for p, b in zip(PARAMS, beta[1:])}
        res["r2"][name] = round(1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum(), 3)
    # how much each parameter moves each target (range of marginal means across its levels)
    marg = {}
    for p in PARAMS:
        levels = sorted({r["pt"][p] for r in rows})
        marg[p] = {"share_range_pts": round(100 * (max(np.mean([sh(r) for r in rows if r["pt"][p] == l]) for l in levels)
                                                     - min(np.mean([sh(r) for r in rows if r["pt"][p] == l]) for l in levels)), 1),
                   "median_range_days": round(max(np.mean([md(r) for r in rows if r["pt"][p] == l]) for l in levels)
                                              - min(np.mean([md(r) for r in rows if r["pt"][p] == l]) for l in levels), 1)}
    res["marginal_effect_over_grid"] = marg
    # linear map params -> (share, median): singular values show effective constraints
    C = np.array([[res["standardised_coef"][t][p] for p in PARAMS] for t in ("share", "median")])
    C[0] /= TOL["share"]; C[1] /= TOL["median"]   # in tolerance units
    sv = np.linalg.svd(C, compute_uv=False)
    res["constraint_singular_values_in_tolerance_units"] = [round(float(s), 2) for s in sv]
    res["constraints_note"] = "2 targets can pin at most 2 combinations of 5 parameters; 3 directions are unconstrained by construction."
    # accepted-set spread per parameter and prediction vs parameter
    res["accepted_n"] = len(acc)
    res["accepted_param_levels"] = {p: {str(l): sum(1 for r in acc if r["pt"][p] == l) for l in sorted({r["pt"][p] for r in rows})} for p in PARAMS}
    res["prediction_band_accepted"] = {fc: band(acc, fc) for fc in ("faster_pet", "optimal")}
    res["corr_prediction_with_param_within_accepted"] = {
        fc: {p: (None if len({r["pt"][p] for r in acc}) < 2 else round(float(np.corrcoef([r["pt"][p] for r in acc if fc in r], [sh(r, fc) for r in acc if fc in r])[0, 1]), 2))
             for p in PARAMS} for fc in ("faster_pet", "optimal")}
    (OUT / "norway_identifiability.json").write_text(json.dumps(res, indent=1))
    return res


def a3(rows):
    res = {}
    for name, use in (("both_targets", ("share", "median")), ("share_only", ("share",)), ("median_only", ("median",))):
        a = accepted(rows, use)
        res[name] = {"accepted": len(a), "pred": {fc: band(a, fc) for fc in ("faster_pet", "optimal")},
                     "observed_share_band": band(a, "observed"),
                     "observed_median_band": [round(min(md(r) for r in a), 1), round(float(median(md(r) for r in a)), 1), round(max(md(r) for r in a), 1)],
                     "gain": {fc: gain_band(a, fc) for fc in ("faster_pet", "optimal")}}
        fo = [sh(r, "optimal") for r in a if "optimal" in r]
        res[name]["optimal_in_published_ci_72_87"] = round(sum(1 for x in fo if 0.72 <= x <= 0.87) / len(fo), 2) if fo else None
        ff = [sh(r, "faster_pet") for r in a if "faster_pet" in r]
        res[name]["faster_pet_in_published_ci_39_58"] = round(sum(1 for x in ff if 0.39 <= x <= 0.58) / len(ff), 2) if ff else None
    (OUT / "norway_leave_one_out.json").write_text(json.dumps(res, indent=1))
    return res


def cohort_noise(n_draws=300):
    """Joint sampling distribution of (share within 42 d, median) in 100-patient cohorts, from the model at the best fit."""
    from pathway_sim import compute_metrics, generate_patients, simulate
    from pathway_sim.scenario import scenario_from_dict
    raw = yaml.safe_load((ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml").read_text())
    sc = scenario_from_dict(raw)
    out = []
    for s in range(1000, 1000 + n_draws):
        m = compute_metrics(simulate(sc, "observed", generate_patients(sc, 100, s), seed=s), sc)
        out.append((m["share_within_target"], m["median_days_to_treatment"]))
    return np.array(out)


def a4(rows, n_resample=500, seed=7):
    rng = np.random.default_rng(seed)
    cn = cohort_noise()
    dev = cn - cn.mean(0)
    se = cn.std(0, ddof=1)
    res = {"cohort_noise_sd": {"share": round(float(se[0]), 4), "median_days": round(float(se[1]), 2)},
           "cohort_noise_corr": round(float(np.corrcoef(cn.T)[0, 1]), 2), "n_cohorts": len(cn), "n_resamples": n_resample,
           "note": "targets resampled as published value + a random 100-patient cohort deviation from the model's own best fit (joint share/median)."}
    for label, mult in (("tolerance_as_shipped_0.04_2.5", None), ("tolerance_1_SE", 1.0), ("tolerance_2_SE", 2.0)):
        tol = TOL if mult is None else {"share": mult * se[0], "median": mult * se[1]}
        meds = {"faster_pet": [], "optimal": []}
        nacc, empty = [], 0
        for _ in range(n_resample):
            d = dev[rng.integers(len(dev))]
            tgt = {"share": TARGET["share"] + d[0], "median": TARGET["median"] + d[1]}
            a = accepted(rows, tol=tol, tgt=tgt)
            a = [r for r in a if "optimal" in r]
            if not a:
                empty += 1
                continue
            nacc.append(len(a))
            for fc in meds:
                meds[fc].append(float(np.mean([sh(r, fc) for r in a])))
        res[label] = {"tolerance": {k: round(float(v), 3) for k, v in tol.items()}, "no_accepted_in_resamples": empty,
                      "median_accepted_sets": int(median(nacc)) if nacc else 0,
                      "pred_of_accepted_mean_across_resamples": {fc: {"mean": round(float(np.mean(v)), 3), "sd": round(float(np.std(v)), 3),
                                                                      "p5": round(float(np.percentile(v, 5)), 3), "p95": round(float(np.percentile(v, 95)), 3)} for fc, v in meds.items() if v}}
    # likelihood-weighted band over the whole grid (flat prior over grid points): weight = Gaussian likelihood of the two targets
    w = []; have = []
    for r in rows:
        if "optimal" not in r:
            continue
        z = ((sh(r) - TARGET["share"]) / se[0]) ** 2 + ((md(r) - TARGET["median"]) / se[1]) ** 2   # ignores corr
        w.append(np.exp(-0.5 * z)); have.append(r)
    w = np.array(w); wn = w / w.sum()
    totw = sum(np.exp(-0.5 * (((sh(r) - TARGET["share"]) / se[0]) ** 2 + ((md(r) - TARGET["median"]) / se[1]) ** 2)) for r in rows)
    res["likelihood_weighted"] = {"weight_mass_with_predictions": round(float(w.sum() / totw), 3), "effective_n": round(float(1 / (wn ** 2).sum()), 1)}
    for fc in ("faster_pet", "optimal"):
        v = np.array([sh(r, fc) for r in have]); o = np.argsort(v); cw = np.cumsum(wn[o])
        q = lambda p: float(v[o][np.searchsorted(cw, p)])
        res["likelihood_weighted"][fc] = {"mean": round(float((wn * v).sum()), 3), "p5": round(q(0.05), 3), "p50": round(q(0.5), 3), "p95": round(q(0.95), 3)}
    (OUT / "norway_noise.json").write_text(json.dumps(res, indent=1))
    return res


def run_all(t):
    rows = t["rows"]
    r1, acc = a1(rows)
    print("A1", json.dumps({k: r1[k] for k in ("accepted_original_subset", "accepted_extended", "pred_original_subset", "pred_extended")}, indent=1))
    print("A2", json.dumps(a2(rows, acc), indent=1))
    print("A3", json.dumps(a3(rows), indent=1))
    print("A4", json.dumps(a4(rows), indent=1))

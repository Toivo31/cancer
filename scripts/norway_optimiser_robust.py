"""Optimiser flowcharts and their ablations on the Norway (Stokstad) validation scenario.

    python scripts/norway_optimiser_robust.py              # uses cached results in docs/review_checks/norway_opt_*.json
    python scripts/norway_optimiser_robust.py --recompute  # rerun the simulations (about 25-40 min on 2 busy cores)

Task 1: the two saved optimiser flowcharts (runs/opt_stokstad.json = no new equipment,
runs/opt_stokstad_fastpet.json = with the faster PET-CT scanner) on the 184 accepted settings of the extended
grid (docs/review_checks/norway_grid_table.json, same acceptance rule as scripts/norway_analyses.py).
Task 2: leave-one-out and add-one-in ablation of the optimiser's four changes, at the best-fit calibration
(scenarios/generated/stokstad_calibrated.yaml, held-out seeds 201-203, n=1000 each, as in demo/export_flow.py)
and across the 184 settings.

Settings per grid point: n=1000 patients, seed 1 (the seed of the grid table), common random numbers (same
patients for every flowchart). Observed, faster-PET and authors' pathway are read from the grid table
(same n and seed); a spot check re-runs them. The optimiser flowcharts were saved with the PET-CT-at-triage
share of the best fit (1.0). On a grid point they are given that point's triage share, like the other flowcharts
(the share is a calibrated property of practice, shared through the 'pet_on_time' policy).
Nothing here edits shipped scenarios or the optimiser.
"""
from __future__ import annotations
import copy, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from pathway_sim.calibrate import evaluate  # noqa: E402
from norway_robustness import to_params, TABLE  # noqa: E402
from norway_analyses import accepted  # noqa: E402

OUT = ROOT / "docs" / "review_checks"
F_GRID, F_BEST, F_SUM = OUT / "norway_opt_grid.json", OUT / "norway_opt_bestfit.json", OUT / "norway_opt_summary.json"
BASE = ROOT / "scenarios" / "stokstad.yaml"
CAL = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"
N, SEED = 1000, 1
BEST_SEEDS = [201, 202, 203]
PLAIN = {"a": "tumour board before sampling finished", "b": "PET-CT always ordered early", "c": "exercise test always early",
         "d": "sampling ordered at the first visit stage (before the visit)"}
FAST = {"pet_ct": {"wait": {"dist": "uniform", "low": 2, "high": 4.5}}, "pet_ct_late": {"wait": {"dist": "uniform", "low": 2, "high": 4.5}}}


def apply_changes(base_fc: dict, ch: set) -> dict:
    """Observed flowchart (raw dict) plus a subset of the optimiser's four changes a, b, c, d."""
    fc = copy.deepcopy(base_fc)
    nodes = {n["id"]: n for n in fc["nodes"]}
    if "a" in ch:
        nodes["diagnosis"]["after"] = ["pet"]
        nodes["treat"]["after_optional"] = list(nodes["treat"]["after_optional"]) + ["sampling_done"]
    if "d" in ch:
        nodes["sample_plan"]["after"] = ["ct"]
    if "b" in ch:
        fc["policy"]["pet_timing"] = {"prefer": ["pet_on_time"], "note": "standardised by optimiser"}
    if "c" in ch:
        fc["policy"]["ex_timing"] = {"prefer": ["ex_early"], "note": "standardised by optimiser"}
    return fc


def variants_for(raw: dict) -> dict:
    """Extra flowcharts to inject, keyed by name. The pet_on_time policy object is shared with 'observed' so a grid
    setting's triage share reaches them too."""
    obs = raw["flowcharts"]["observed"]
    v = {}
    sets = {"full": set("abcd"), "no_a": set("bcd"), "no_b": set("acd"), "no_c": set("abd"), "no_d": set("abc"),
            "only_a": {"a"}, "only_b": {"b"}, "only_c": {"c"}, "only_d": {"d"}, "only_bc": set("bc"), "none": set()}
    for scan, ov in (("nofast", None), ("fast", FAST)):
        for k, ch in sets.items():
            if k == "none" and scan == "nofast":
                continue  # 'none' without scanner is the observed flowchart; with scanner it is faster_pet
            if k == "none":
                continue
            fc = apply_changes(obs, ch)
            fc["description"] = f"optimiser ablation {k} ({scan})"
            if ov:
                fc["test_overrides"] = copy.deepcopy(ov)
            fc["policy"]["pet_on_time"] = obs["policy"]["pet_on_time"]  # shared object
            v[f"{k}_{scan}"] = fc
    return v


def check_equivalence(raw):
    """The 'full' reconstruction must equal the saved optimiser flowcharts (nodes and policy up to the pet mix)."""
    for name, key in (("opt_stokstad", "full_nofast"), ("opt_stokstad_fastpet", "full_fast")):
        saved = json.loads((ROOT / "runs" / f"{name}.json").read_text())["flowchart_after"]
        mine = variants_for(raw)[key]
        sn = {n["id"]: {k: v for k, v in n.items() if k != "kind" or v != "step"} for n in saved["nodes"]}
        mn = {n["id"]: {k: v for k, v in n.items() if k != "kind" or v != "step"} for n in mine["nodes"]}
        norm = lambda d: {i: {k: (sorted(v) if isinstance(v, list) and k.startswith("after") else v) for k, v in n.items()} for i, n in d.items()}
        assert norm(sn) == norm(mn), (name, [i for i in sn if norm(sn)[i] != norm(mn).get(i)])
        for p in ("sample_plan", "after_bronch", "pet_timing", "ex_timing"):
            a = {k: v for k, v in saved["policy"][p].items() if k not in ("note", "source")}
            b = {k: v for k, v in mine["policy"][p].items() if k not in ("note", "source")}
            assert a == b, (name, p, a, b)
        assert (saved.get("test_overrides") or {}) == (mine.get("test_overrides") or {}), name
    return True


_RAW = {}


def load(path):
    if path not in _RAW:
        _RAW[path] = yaml.safe_load(Path(path).read_text())
    return copy.deepcopy(_RAW[path])


def _work(args):
    key, base, pt, fcs, n, seeds = args
    raw = load(base)
    vs = variants_for(raw)
    raw["flowcharts"].update(vs)
    return key, evaluate(raw, to_params(pt) if pt else {}, fcs, n, seeds)


def run(jobs, procs=2):
    with Pool(procs) as p:
        return dict(p.imap_unordered(_work, jobs, chunksize=2))


NEWV = [f"{k}_{s}" for s in ("nofast", "fast") for k in ("full", "no_a", "no_b", "no_c", "no_d", "only_a", "only_b", "only_c", "only_d")]


def grid_run(recompute):
    if F_GRID.exists() and not recompute:
        return json.loads(F_GRID.read_text())
    tab = json.loads(TABLE.read_text())
    acc = accepted(tab["rows"])
    print(len(acc), "accepted settings", flush=True)
    jobs = [(r["i"], str(BASE), r["pt"], NEWV, N, [SEED]) for r in acc]
    res = run(jobs)
    # spot check: re-run observed/faster_pet/optimal at 3 settings and compare with the table
    chk = run([(("chk", r["i"]), str(BASE), r["pt"], ["observed", "faster_pet", "optimal"], N, [SEED]) for r in acc[:3]])
    for r in acc[:3]:
        for f in ("observed", "faster_pet", "optimal"):
            a, b = chk[("chk", r["i"])][f]["share_within_target"], r[f]["share_within_target"]
            assert abs(a - b) < 1e-9, (r["i"], f, a, b)
    rows = []
    for r in acc:
        d = {"i": r["i"], "pt": r["pt"]}
        for f in ("observed", "faster_pet", "optimal"):
            d[f] = r[f]
        for v in NEWV:
            d[v] = res[r["i"]][v]
        rows.append(d)
    out = {"n": N, "seed": SEED, "note": "extended grid accepted settings; table flowcharts read from norway_grid_table.json (spot check on 3 settings reproduced exactly)", "rows": rows}
    F_GRID.write_text(json.dumps(out))
    return out


def best_run(recompute):
    if F_BEST.exists() and not recompute:
        return json.loads(F_BEST.read_text())
    out = {"seeds": BEST_SEEDS, "n": N, "note": "shipped best-fit calibration (scenarios/generated/stokstad_calibrated.yaml), held-out seeds as in demo/export_flow.py"}
    r = _work(("best", str(CAL), None, ["observed", "faster_pet", "optimal"] + NEWV, N, BEST_SEEDS))[1]
    out["shipped_best_fit"] = r
    F_BEST.write_text(json.dumps(out))
    return out


def stats(xs):
    xs = np.array(xs) * 100
    return {"min": round(float(xs.min()), 1), "p10": round(float(np.percentile(xs, 10)), 1), "median": round(float(np.median(xs)), 1),
            "p90": round(float(np.percentile(xs, 90)), 1), "max": round(float(xs.max()), 1)}


def summarise(g, b):
    rows = g["rows"]
    sh = lambda r, f: r[f]["share_within_target"]
    names = ["observed", "faster_pet", "optimal", "full_nofast", "full_fast"] + [f"{k}_{s}" for s in ("nofast", "fast") for k in ("no_a", "no_b", "no_c", "no_d", "only_a", "only_b", "only_c", "only_d")]
    S = {"n_settings": len(rows), "bands_percent": {f: stats([sh(r, f) for r in rows]) for f in names}}
    cnt = lambda a, c, m=0.0: sum(1 for r in rows if sh(r, a) - sh(r, c) > m)
    S["counts"] = {
        "opt_fast_beats_authors": cnt("full_fast", "optimal"), "opt_fast_beats_authors_by_>1.5pt": cnt("full_fast", "optimal", 0.015),
        "opt_nofast_beats_fasterpet": cnt("full_nofast", "faster_pet"), "opt_nofast_beats_observed": cnt("full_nofast", "observed"),
        "opt_nofast_beats_authors": cnt("full_nofast", "optimal"),
        "opt_fast_beats_fasterpet": cnt("full_fast", "faster_pet"),
        "no_d_fast_beats_authors": cnt("no_d_fast", "optimal"), "no_d_nofast_beats_authors": cnt("no_d_nofast", "optimal"),
        "no_d_fast_vs_authors_within_1.5pt": sum(1 for r in rows if abs(sh(r, "no_d_fast") - sh(r, "optimal")) <= 0.015),
        "no_d_nofast_vs_authors_within_1.5pt": sum(1 for r in rows if abs(sh(r, "no_d_nofast") - sh(r, "optimal")) <= 0.015),
    }
    gap = lambda a, c: stats([sh(r, a) - sh(r, c) + 0 for r in rows]) if False else {k: round(v, 1) for k, v in zip(("min", "p10", "median", "p90", "max"), np.percentile([100 * (sh(r, a) - sh(r, c)) for r in rows], [0, 10, 50, 90, 100]))}
    S["differences_pts"] = {
        "full_fast - authors": gap("full_fast", "optimal"), "no_d_fast - authors": gap("no_d_fast", "optimal"),
        "full_nofast - faster_pet": gap("full_nofast", "faster_pet"), "no_d_nofast - faster_pet": gap("no_d_nofast", "faster_pet"),
        "full_nofast - observed": gap("full_nofast", "observed"), "no_d_nofast - observed": gap("no_d_nofast", "observed"),
        "full_nofast - no_d_nofast (value of d)": gap("full_nofast", "no_d_nofast"), "full_fast - no_d_fast (value of d)": gap("full_fast", "no_d_fast"),
        "only_d_nofast - observed": gap("only_d_nofast", "observed"),
        "full_nofast - no_a_nofast": gap("full_nofast", "no_a_nofast"), "full_nofast - no_b_nofast": gap("full_nofast", "no_b_nofast"),
        "full_nofast - no_c_nofast": gap("full_nofast", "no_c_nofast"),
    }
    bf = b["shipped_best_fit"]
    S["best_fit_shipped_percent"] = {f: round(100 * v["share_within_target"], 1) for f, v in bf.items()}
    S["best_fit_shipped_median_days"] = {f: v["median_days_to_treatment"] for f, v in bf.items()}
    # extended-grid best fit = closest to both targets, by the normalised distance used in the robustness work
    ext = min(rows, key=lambda r: ((sh(r, "observed") - .40) / .04) ** 2 + ((r["observed"]["median_days_to_treatment"] - 46.5) / 2.5) ** 2)
    S["extended_grid_closest_setting"] = {"pt": ext["pt"], **{f: round(100 * sh(ext, f), 1) for f in names}}
    return S


if __name__ == "__main__":
    rc = "--recompute" in sys.argv
    raw = load(BASE)
    print("equivalence with saved optimiser flowcharts:", check_equivalence(raw), flush=True)
    g = grid_run(rc)
    b = best_run(rc)
    S = summarise(g, b)
    F_SUM.write_text(json.dumps(S, indent=1))
    print(json.dumps(S, indent=1))

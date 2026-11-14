"""Calibrate unsourced parameters on one flowchart; report what the others then predict.

The scenario's ``calibration`` block names the flowchart to calibrate on, the
targets and a grid over parameters tagged ``assumption``:

```yaml
calibration:
  flowchart: observed
  targets: {share_within_target: [0.40, 0.05], median_days_to_treatment: [46.5, 3.0]}
  predict: [faster_pet, optimal]
  grid:
    resources.first_visit_wait.wait.median: [3, 5, 7, 9]
```

Every grid point whose calibration-flowchart metrics fall inside the target
tolerances is *accepted*. The other flowcharts are then run with each accepted
parameter set, and the report gives the range of their predictions. Only the
calibration flowchart is fitted; the predictions are out-of-sample checks
against the published numbers. A lognormal ``median`` keeps its original
p90/median ratio when it is varied.

    python -m pathway_sim.calibrate scenarios/stokstad.yaml --n 1000 --out docs/validation_results.json
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path
from statistics import median

import yaml

from .engine import simulate
from .metrics import compute_metrics
from .patients import generate_patients
from .scenario import scenario_from_dict


def set_path(raw: dict, path: str, value) -> None:
    keys = path.split(".")
    d = raw
    for k in keys[:-1]:
        d = d[k]
    if keys[-1] == "median" and "p90" in d and d.get("median"):
        ratio = float(d["p90"]) / float(d["median"])
        d["p90"] = value * ratio
    d[keys[-1]] = value


def apply_param(raw: dict, key: str, value) -> None:
    """A grid value is either a scalar for dotted path ``key`` or a dict of path -> value
    (a joint setting, e.g. two mix weights that must move together)."""
    if isinstance(value, dict):
        for p, v in value.items():
            set_path(raw, p, v)
    else:
        set_path(raw, key, value)


def evaluate(raw: dict, params: dict, flowcharts: list[str], n: int, seeds: list[int]) -> dict:
    r = copy.deepcopy(raw)
    for k, v in params.items():
        apply_param(r, k, v)
    sc = scenario_from_dict(r)
    out = {}
    for fid in flowcharts:
        ms = []
        for s in seeds:
            pts = generate_patients(sc, n, s)
            ms.append(compute_metrics(simulate(sc, fid, pts, seed=s), sc))
        out[fid] = {
            "share_within_target": round(sum(m["share_within_target"] for m in ms) / len(ms), 4),
            "median_days_to_treatment": round(sum(m["median_days_to_treatment"] for m in ms) / len(ms), 2),
            "sampling_per_patient": round(sum(sum(v["n"] for k, v in m["node_breakdown_all"].items()
                                                  if v["test"] in ("bronchoscopy", "bronchoscopy_repeat", "ttnb")) for m in ms)
                                          / sum(m["n"] for m in ms), 3),
        }
    return out


def calibrate(path: str, n: int = 1000, seeds: list[int] | None = None) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    cal = raw["calibration"]
    seeds = seeds or [1]
    grid = cal["grid"]
    keys = list(grid)
    targets = cal["targets"]
    fc_cal = cal["flowchart"]
    accepted, scored = [], []
    for combo in itertools.product(*(grid[k] for k in keys)):
        params = dict(zip(keys, combo))
        m = evaluate(raw, params, [fc_cal], n, seeds)[fc_cal]
        err = sum(((m[k] - t) / tol) ** 2 for k, (t, tol) in targets.items())
        ok = all(abs(m[k] - t) <= tol for k, (t, tol) in targets.items())
        scored.append((err, params, m))
        if ok:
            accepted.append((err, params, m))
    scored.sort(key=lambda x: x[0])
    predict = cal.get("predict", [])
    preds = []
    for err, params, m in sorted(accepted, key=lambda x: x[0]):
        p = evaluate(raw, params, predict, n, seeds)
        preds.append({"params": params, "fit_error": round(err, 3), fc_cal: m, **p})
    summary = {}
    for fid in predict:
        xs = [p[fid]["share_within_target"] for p in preds]
        if xs:
            summary[fid] = {"share_min": min(xs), "share_median": round(median(xs), 4), "share_max": max(xs),
                            "median_days_median": round(median(p[fid]["median_days_to_treatment"] for p in preds), 2)}
    best = preds[0] if preds else None
    return {
        "scenario": raw["id"], "calibrated_on": fc_cal, "targets": targets, "n": n, "seeds": seeds,
        "grid": grid, "grid_points": len(scored), "accepted": len(accepted),
        "published": raw.get("published"), "prediction_summary": summary, "best": best,
        "closest_if_none_accepted": None if preds else {"params": scored[0][1], fc_cal: scored[0][2]},
        "accepted_sets": preds,
    }


def write_best(path: str, result: dict, out_path: str) -> None:
    """Write a copy of the scenario with the best-fit parameters baked in."""
    raw = yaml.safe_load(Path(path).read_text())
    params = (result["best"] or result["closest_if_none_accepted"])["params"]
    for k, v in params.items():
        apply_param(raw, k, v)
    raw["calibrated_from"] = {"file": str(path), "params": params}
    Path(out_path).write_text(yaml.safe_dump(raw, sort_keys=False))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    seeds = [int(s) for s in a.seeds.split(",")]
    res = calibrate(a.scenario, a.n, seeds)
    print(f"{res['scenario']}: {res['accepted']}/{res['grid_points']} grid points match {res['calibrated_on']} targets")
    if res["best"]:
        print("best fit:", res["best"]["params"])
        for k, v in res["best"].items():
            if isinstance(v, dict) and "share_within_target" in v:
                print(f"  {k:<14} {100*v['share_within_target']:5.1f}%  median {v['median_days_to_treatment']:5.1f} d"
                      f"  sampling/pt {v['sampling_per_patient']:.2f}")
    else:
        print("no grid point accepted; closest:", res["closest_if_none_accepted"])
    for fid, s in res["prediction_summary"].items():
        print(f"prediction {fid:<12} share {100*s['share_min']:.0f}-{100*s['share_max']:.0f}% (median {100*s['share_median']:.0f}%)")
    print("published:", res["published"])
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
        print("wrote", a.out)


if __name__ == "__main__":
    main()

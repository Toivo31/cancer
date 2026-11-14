#!/usr/bin/env python3
"""Collect the few numbers the start page (demo/start.html) cannot read from the other bundles.

Writes demo/data/start_bundle.js (`window.START_DATA = {...};`) from files that browsers cannot open
from disk as JSON:

  docs/validation_results.json                      Norway calibration (accepted grid points, published numbers)
  docs/review_checks/norway_leave_one_out.json      Norway robustness (optional, written by another lane)
  docs/review_checks/encounter_results*.json        tuned encounter-loop report: tuning seeds, fresh seeds, pooled (optional)
  docs/ranges_norway.json                           Norway: spread across the calibration sets that fit (optimiser vs authors' pathway)
  docs/review_checks/norway_opt_summary.json        the optimiser over the 184 settings that fit (ranges and counts)
  docs/review_checks/norway_opt_structure.json      the authors' pathway read literally (structure check)
  docs/ledger.json                                  how many inputs are sourced and how many are assumptions
  catalogue/lung-primary-care/*.yaml                every `source:` in the care catalogue, counted here

Nothing is typed by hand: a file that is missing becomes `null` and the page shows "pending".
Run it again after any of those files change:  python demo/export_start.py
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(rel: str):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def count_sources(node, acc: dict) -> None:
    """Every mapping with a string `source` is one sourced-or-assumed claim."""
    if isinstance(node, dict):
        src = node.get("source")
        if isinstance(src, str):
            acc["total"] += 1
            if src.strip().lower() == "assumption":
                acc["assumption"] += 1
            else:
                acc["sourced"] += 1
        for v in node.values():
            count_sources(v, acc)
    elif isinstance(node, list):
        for v in node:
            count_sources(v, acc)


def catalogue_counts(rel: str):
    import yaml  # pyyaml is a project requirement

    d = ROOT / rel
    if not d.is_dir():
        return None
    acc = {"total": 0, "sourced": 0, "assumption": 0}
    for f in sorted(d.glob("*.yaml")):
        count_sources(yaml.safe_load(f.read_text(encoding="utf-8")), acc)
    status = None
    cat = d / "catalogue.yaml"
    if cat.exists():
        status = (yaml.safe_load(cat.read_text(encoding="utf-8")) or {}).get("status")
    acc["status"] = status
    acc["path"] = rel
    return acc


def pick(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def spread(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return {"min": min(vals), "max": max(vals), "n": len(vals)} if vals else None


def norway_ranges() -> dict | None:
    """Optimiser and authors' pathway across the calibration sets that reproduce the observed pathway."""
    r = read_json("docs/ranges_norway.json")
    sets = pick(r, "accepted_calibration_sets", "per_set") if r else None
    if not sets:
        return None
    out = {"source_file": "docs/ranges_norway.json", "n_sets": len(sets)}
    # D68: the optimiser run from the faster-scanner pathway is not reported, so its range is not exported
    for k in ("observed", "faster_pet", "authors", "optimiser_no_new_equipment"):
        out[k] = spread([s.get(k) for s in sets])
    return out


def norway_optimiser() -> dict | None:
    """The optimiser over the 184 settings that fit the observed data, and the structure check (docs/validation.md,
    "Optimiser robustness, ablation and structure check"). Shares as fractions; read from the cached check files."""
    summ = read_json("docs/review_checks/norway_opt_summary.json")
    struct = read_json("docs/review_checks/norway_opt_structure.json")
    if not summ:
        return None

    def band(key):
        b = (summ.get("bands_percent") or {}).get(key)
        return {k: b[k] / 100 for k in ("min", "median", "max")} if b else None

    c = summ.get("counts") or {}
    out = {
        "source_file": "docs/review_checks/norway_opt_summary.json",
        "n_settings": summ.get("n_settings"),
        "bands": {"observed": band("observed"), "faster_pet": band("faster_pet"), "authors": band("optimal"),
                  "optimiser_no_equipment": band("full_nofast")},
        # D68: only the optimiser run from today's pathway (no new equipment) is exported
        "counts": {"noeq_beats_observed": c.get("opt_nofast_beats_observed"),
                   "noeq_beats_scanner_alone": c.get("opt_nofast_beats_fasterpet")},
        "structure": None,
    }
    gb = pick(struct, "grid_bands")
    if gb:
        lit, shipped = gb.get("optimal_petvisit_nogate"), gb.get("optimal")
        out["structure"] = {
            "source_file": "docs/review_checks/norway_opt_structure.json",
            "literal_median": lit["share"]["median"] / 100, "literal_in_published_ci": lit["in_published_CI_72_87"],
            "shipped_in_published_ci": shipped["in_published_CI_72_87"], "settings": summ.get("n_settings"),
            "published_ci": [0.72, 0.87],
        }
    return out


def _pct_band(b, keys=("min", "p10", "median", "p90", "max")):
    """A band in percent (review files) -> fractions, keeping only the keys present."""
    return {k: round(b[k] / 100, 6) for k in keys if isinstance(b, dict) and isinstance(b.get(k), (int, float))} or None


def _frac_band(b, keys=("min", "p10", "median", "p90", "max")):
    return {k: b[k] for k in keys if isinstance(b, dict) and isinstance(b.get(k), (int, float))} or None


def evidence_page() -> dict | None:
    """Everything the Evidence page (demo/evidence.html, UI lane L4) shows beyond the fields above: the best-fit point
    of every Norway row, the robustness tests of docs/validation.md ("Robustness" 1-5) and the optimiser's ranking,
    ablation and structure check ("Optimiser robustness, ablation and structure check" 1-3). Shares are fractions,
    differences in points. D68: nothing from the optimiser run from the faster-scanner pathway is exported."""
    summ = read_json("docs/review_checks/norway_opt_summary.json")
    best = read_json("docs/review_checks/norway_opt_bestfit.json")
    struct = read_json("docs/review_checks/norway_opt_structure.json")
    rank = read_json("docs/review_checks/norway_ranking.json")
    ext = read_json("docs/review_checks/norway_grid_extension.json")
    ident = read_json("docs/review_checks/norway_identifiability.json")
    loo = read_json("docs/review_checks/norway_leave_one_out.json")
    noise = read_json("docs/review_checks/norway_noise.json")
    mech = read_json("docs/review_checks/norway_mechanisms.json")
    val = read_json("docs/validation_results.json")
    if not (summ and best and val):
        return None
    import yaml

    scen = yaml.safe_load((ROOT / "scenarios" / "stokstad.yaml").read_text(encoding="utf-8")) or {}
    pub = val.get("published") or {}
    bands = summ.get("bands_percent") or {}
    sb = best.get("shipped_best_fit") or {}

    def row(key, review_key, pub_key):
        p = pub.get(pub_key) if pub_key else None
        bf = sb.get(review_key) or {}
        return {
            "key": key,
            "published": p.get("share_within_target") if p else None,
            "published_ci": p.get("ci95") if p else None,
            "best_fit": bf.get("share_within_target"),
            "best_fit_median_days": bf.get("median_days_to_treatment"),
            "band": _pct_band(bands.get(review_key)),
        }

    c = summ.get("counts") or {}
    diffs = summ.get("differences_pts") or {}
    out = {
        "source_files": ["docs/review_checks/norway_opt_summary.json", "docs/review_checks/norway_opt_bestfit.json",
                         "docs/review_checks/norway_opt_structure.json", "docs/review_checks/norway_ranking.json",
                         "docs/review_checks/norway_grid_extension.json", "docs/review_checks/norway_identifiability.json",
                         "docs/review_checks/norway_leave_one_out.json", "docs/review_checks/norway_noise.json",
                         "docs/review_checks/norway_mechanisms.json", "docs/validation_results.json", "scenarios/stokstad.yaml"],
        "target_days": scen.get("target_days"),
        # the scenario's default cohort is the paper's cohort size (100 patients, scenarios/stokstad.yaml header)
        "published_patients": scen.get("default_n"),
        "n_settings": summ.get("n_settings"),
        "best_fit_cohorts": len(best.get("seeds") or []) or None,
        "best_fit_patients_per_cohort": best.get("n"),
        "rows": [row("observed", "observed", "observed"), row("faster_pet", "faster_pet", "faster_pet"),
                 row("authors", "optimal", "optimal"), row("optimiser_no_equipment", "full_nofast", None)],
        "ranking": None, "grid": None, "targets_as_one": None, "noise": None, "scanner_miss": None,
        "optimiser": {
            "beats_observed": c.get("opt_nofast_beats_observed"),
            "beats_scanner_alone": c.get("opt_nofast_beats_fasterpet"),
            "gain_over_observed_pts": _frac_band(diffs.get("full_nofast - observed"), ("min", "median", "max")),
            "minus_scanner_alone_pts": _frac_band(diffs.get("full_nofast - faster_pet"), ("min", "median", "max")),
            # points lost when one change is removed, at the best fit and as the median over the settings
            "ablation": [
                {"change": ch,
                 "loss_best_fit_pts": round((summ.get("best_fit_shipped_percent") or {}).get("full_nofast", 0)
                                            - (summ.get("best_fit_shipped_percent") or {}).get(f"no_{ch}_nofast", 0), 6),
                 "loss_median_pts": pick(diffs, f"full_nofast - no_{ch}_nofast", "median")
                 if ch != "d" else pick(diffs, "full_nofast - no_d_nofast (value of d)", "median"),
                 "loss_min_pts": pick(diffs, f"full_nofast - no_{ch}_nofast", "min")
                 if ch != "d" else pick(diffs, "full_nofast - no_d_nofast (value of d)", "min"),
                 "loss_max_pts": pick(diffs, f"full_nofast - no_{ch}_nofast", "max")
                 if ch != "d" else pick(diffs, "full_nofast - no_d_nofast (value of d)", "max")}
                for ch in ("a", "b", "c", "d")],
        },
        "structure": None,
    }
    if rank:
        out["ranking"] = {
            "settings": rank.get("accepted"), "holds_in": rank.get("optimal>faster_pet>observed_in"),
            "grid_points": rank.get("all_predicted_grid_points"), "holds_at_grid_points": rank.get("ranking_holds_at_grid_points"),
            "authors_gain_pts": rank.get("optimal_gain_pts"), "scanner_gain_pts": rank.get("faster_pet_gain_pts"),
            "authors_minus_scanner_pts": rank.get("optimal_minus_faster_pts"),
        }
    if ext:
        out["grid"] = {
            "first_points": ext.get("n_grid_original_subset"), "first_accepted": ext.get("accepted_original_subset"),
            "extended_points": ext.get("n_grid_extended"), "extended_accepted": ext.get("accepted_extended"),
            "first_authors": _frac_band(pick(ext, "pred_original_subset", "optimal")),
            "extended_authors": _frac_band(pick(ext, "pred_extended", "optimal")),
            "first_scanner": _frac_band(pick(ext, "pred_original_subset", "faster_pet")),
            "extended_scanner": _frac_band(pick(ext, "pred_extended", "faster_pet")),
            "authors_in_published_ci": pick(loo, "both_targets", "optimal_in_published_ci_72_87"),
            "scanner_in_published_ci": pick(loo, "both_targets", "faster_pet_in_published_ci_39_58"),
        }
    if loo:
        out["targets_as_one"] = {
            "singular_values": pick(ident, "constraint_singular_values_in_tolerance_units"),
            "calibrated_on": [
                {"on": k, "accepted": pick(loo, k, "accepted"),
                 "authors": _frac_band(pick(loo, k, "pred", "optimal")),
                 "scanner": _frac_band(pick(loo, k, "pred", "faster_pet"))}
                for k in ("both_targets", "share_only", "median_only") if isinstance(loo.get(k), dict)],
        }
    if noise:
        t = noise.get("tolerance_as_shipped_0.04_2.5") or {}
        out["noise"] = {
            "cohort_sd_share": pick(noise, "cohort_noise_sd", "share"),
            "cohort_sd_days": pick(noise, "cohort_noise_sd", "median_days"),
            "draws": noise.get("n_resamples"),
            "authors": _frac_band(pick(t, "pred_of_accepted_mean_across_resamples", "optimal"), ("mean", "sd", "p5", "p95")),
            "scanner": _frac_band(pick(t, "pred_of_accepted_mean_across_resamples", "faster_pet"), ("mean", "sd", "p5", "p95")),
        }
    if mech:
        out["scanner_miss"] = {
            "published": pick(pub, "faster_pet", "share_within_target"),
            "runs": [{"rho": r.get("rho"), "accepted": r.get("accepted"), "grid_points": r.get("grid_points"),
                      "scanner": _frac_band(r.get("faster_pet"), ("min", "median", "max"))}
                     for r in mech.get("runs") or [] if r.get("scenario") == "base"],
        }
    gb = pick(struct, "grid_bands")
    if gb:
        bfp = struct.get("best_fit_shipped_percent") or {}

        def variant(k):
            g = gb.get(k) or {}
            return {"best_fit": round(bfp[k] / 100, 6) if isinstance(bfp.get(k), (int, float)) else None,
                    "band": _pct_band(g.get("share"), ("min", "median", "max")),
                    "in_published_ci": g.get("in_published_CI_72_87")}

        # as shipped; without the wait for the sample; PET-CT at the first visit; both (the stricter reading)
        out["structure"] = {"shipped": variant("optimal"), "no_sample_wait": variant("optimal_nogate"),
                            "pet_at_first_visit": variant("optimal_petvisit"), "stricter": variant("optimal_petvisit_nogate"),
                            "settings": struct.get("settings") if isinstance(struct.get("settings"), int) else summ.get("n_settings")}
    return out


def consistency_counts() -> dict | None:
    """How many of the loop-against-chain checks pass, on the tuning seeds, on fresh seeds and pooled
    (docs/encounter_results.md, written by scripts/encounter_report.py)."""
    out = {}
    for key, rel in (("tuning", "encounter_results"), ("fresh", "encounter_results_oos"), ("pooled", "encounter_results_8seeds")):
        d = read_json(f"docs/review_checks/{rel}.json")
        c = d and d.get("consistency")
        if c:
            out[key] = {"seeds": d.get("seeds"), "passed": sum(1 for v in c.values() if v.get("passes")), "total": len(c)}
    return out or None


def build() -> dict:
    val = read_json("docs/validation_results.json")
    loo = read_json("docs/review_checks/norway_leave_one_out.json")
    led = read_json("docs/ledger.json")
    out = {
        "format": "start-bundle/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validation": None,
        "norway_robustness": None,
        "encounter_results": read_json("docs/review_checks/encounter_results.json"),
        "encounter_consistency": consistency_counts(),
        "norway": None,
        "ledger": None,
        "catalogue": catalogue_counts("catalogue/lung-primary-care"),
    }
    if val:
        out["validation"] = {
            "source_file": "docs/validation_results.json",
            "grid_points": val.get("grid_points"),
            "accepted": val.get("accepted"),
            "published": val.get("published"),
            "prediction_summary": val.get("prediction_summary"),
        }
    if loo:
        out["norway_robustness"] = {
            "source_file": "docs/review_checks/norway_leave_one_out.json",
            "accepted": pick(loo, "both_targets", "accepted"),
            "pred": pick(loo, "both_targets", "pred"),
        }
    out["norway"] = {
        "ranges": norway_ranges(),
        "optimiser": norway_optimiser(),
        # the robustness band over every setting that fits the observed data (docs/validation.md, Robustness)
        "all_settings": out["norway_robustness"],
    } if val else None
    # UI lane L4 (additive): the Evidence page's fields
    out["evidence"] = evidence_page() if val else None
    if led:
        out["ledger"] = {
            "source_file": "docs/ledger.json",
            "scenarios": [
                {"id": s.get("id"), "blocks": pick(s, "inputs", "blocks"), "sourced": pick(s, "inputs", "sourced"),
                 "assumption": pick(s, "inputs", "assumption")}
                for s in led.get("scenarios", [])
            ],
            "params_table": {k: pick(led, "params_table", k) for k in ("rows", "sourced", "assumption")},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "demo" / "data" / "start_bundle.js"))
    args = ap.parse_args()
    data = build()
    Path(args.out).write_text("window.START_DATA = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"wrote {args.out}")
    for k, v in data.items():
        print(f"  {k}: {'present' if v else 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

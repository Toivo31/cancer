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
    for k in ("observed", "faster_pet", "authors", "optimiser_faster_scanner", "optimiser_no_new_equipment"):
        out[k] = spread([s.get(k) for s in sets])
    out["optimiser_above_authors_in"] = sum(1 for s in sets if s["optimiser_faster_scanner"] > s["authors"])
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
                  "optimiser_no_equipment": band("full_nofast"), "optimiser_scanner": band("full_fast")},
        "counts": {"noeq_beats_observed": c.get("opt_nofast_beats_observed"),
                   "noeq_beats_scanner_alone": c.get("opt_nofast_beats_fasterpet"),
                   "scanner_beats_scanner_alone": c.get("opt_fast_beats_fasterpet")},
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

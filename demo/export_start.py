#!/usr/bin/env python3
"""Collect the few numbers the start page (demo/start.html) cannot read from the other bundles.

Writes demo/data/start_bundle.js (`window.START_DATA = {...};`) from files that browsers cannot open
from disk as JSON:

  docs/validation_results.json                      Norway calibration (accepted grid points, published numbers)
  docs/review_checks/norway_leave_one_out.json      Norway robustness (optional, written by another lane)
  docs/review_checks/encounter_results.json         tuned encounter-loop report (optional, another lane)
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

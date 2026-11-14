"""Synthetic-patients card (demo/export_cards.py): the bundle counts the libraries on disk and the example keeps the
hidden side apart from what the decision model sees."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


def load(path: Path) -> dict:
    return json.loads(re.match(r"window\.CARDS_DATA = (.*);\s*$", path.read_text(encoding="utf-8"), re.S).group(1))


def test_export_counts_libraries_and_splits_hidden_side(tmp_path):
    from demo import export_cards  # noqa: F401  (demo/ is importable as a namespace package from the repo root)

    out = tmp_path / "cards.js"
    assert export_cards.main.__module__ == "demo.export_cards"
    import sys

    argv, sys.argv = sys.argv, ["export_cards", "--out", str(out)]
    try:
        assert export_cards.main() == 0
    finally:
        sys.argv = argv
    d = load(out)
    on_disk = sorted(p.parent.name for p in (ROOT / "libraries").glob("*/manifest.json"))
    assert sorted(r["name"] for r in d["libraries"]) == on_disk
    for r in d["libraries"]:
        m = json.loads((ROOT / "libraries" / r["name"] / "manifest.json").read_text())
        assert r["cards"] == sum(m["card_count_by_condition"].values())
    assert d["totals"]["cards"] == sum(r["cards"] for r in d["libraries"])
    ex = d["example"]
    assert ex and ex["hidden"]["conditions"]
    seen = json.dumps(ex["decider_sees"]) + json.dumps(ex["template"])
    for c in ex["hidden"]["conditions"]:
        assert c["id"] not in seen, "the decider's side must not carry the condition id"
    assert ex["template"]["complaint"].startswith("Synthetic complaint:")


def test_committed_bundle_parses():
    d = load(DEMO / "data" / "cards_bundle.js")
    assert d["format"] == "cards-bundle/1" and d["libraries"]

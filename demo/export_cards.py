#!/usr/bin/env python3
"""Collect the data for the "Synthetic patients" card on the start page (demo/start.html).

Writes demo/data/cards_bundle.js (`window.CARDS_DATA = {...};`):

  libraries   every folder in libraries/ that has a manifest.json: name, number of cards, who wrote the wording
              (a language model, or the offline template generator, model "fake"), cards per condition. Counted
              from the manifests when the script runs, so libraries that arrive later are counted by a rerun.
  example     one model-written patient (the first lung-cancer card of the model-written library with the most
              cards, preferring libraries whose results prompt is in reveal.SAFE_RESULTS_PROMPTS, i.e. g2@3, when any exist), read with the patient_engine API:
                what the decider sees (RevealHandle.visible: background, complaint in the patient's words, the history taken; no test report, see SHOW_TESTS) next to the template wording of the same facts (the style of libraries/ref500),
                and the hidden side (true conditions), which the decision model never sees.

Nothing is typed by hand. Run again after a library changes or arrives:  python demo/export_cards.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from patient_engine.catalogue import load_catalogue  # noqa: E402
from patient_engine.library import load_library  # noqa: E402
from patient_engine.reference import report_text  # noqa: E402
from patient_engine.reveal import RevealHandle  # noqa: E402

CATALOGUES = {"lung_primary_care": "catalogue/lung-primary-care"}
SHOW_TESTS = ("history",)   # only the history is shown: the review found test-report wording in results prompt g2@1 gives away false alarms
from patient_engine.reveal import SAFE_RESULTS_PROMPTS   # noqa: E402
PREFERRED_RESULTS_PROMPTS = frozenset(SAFE_RESULTS_PROMPTS)   # one source of truth: whose report text is served (D65: g2@3)


def lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[:2].isupper() else s


def library_rows(root: Path) -> list[dict]:
    rows = []
    for m in sorted(root.glob("*/manifest.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        by = d.get("card_count_by_condition") or {}
        model = d.get("model")
        rows.append({
            "name": m.parent.name, "cards": sum(by.values()), "generator": d.get("generator"), "model": model,
            "wording": "template" if model == "fake" or d.get("generator") != "llm" else "model",
            "created": d.get("created"), "by_condition": by, "results_prompt": (d.get("prompts") or {}).get("results"),
        })
    return rows


def example(lib_name: str, rows: list[dict]) -> dict | None:
    row = next((r for r in rows if r["name"] == lib_name), None)
    path = ROOT / "libraries" / lib_name
    lib = load_library(path)   # verifies the content hash
    cat = load_catalogue(ROOT / CATALOGUES[lib.manifest.catalogue_id])
    idx = next((i for i, c in enumerate(lib.cards) if c.primary_condition == "lung_cancer"), None)
    if idx is None:
        return None
    card = lib.cards[idx]
    state = card.states[0]
    h = RevealHandle(card, public_id=card.id)
    view = h.visible(state, [(t, 0) for t in SHOW_TESTS])
    obs = {o.test: o for o in view.observations}
    labels = "; ".join(lower_first(cat.variables[v].label) for v in view.presenting.reported)
    conds = []
    for c in card.hidden.conditions:
        cond = cat.conditions[c.id]
        conds.append({"id": c.id, "label": cond.label, "role": c.role, "attributes": dict(c.attributes)})
    return {
        "library": lib_name, "card": card.id, "index": idx, "model": row and row["model"],
        "background": dict(view.background),
        "decider_sees": {
            "complaint": view.presenting.text,
            "reported": [cat.variables[v].label for v in view.presenting.reported],
            "history": obs["history"].report,
        },
        "template": {
            "complaint": f"Synthetic complaint: {labels}.",
            "history": report_text(cat.tests["history"], obs["history"].status, obs["history"].values),
        },
        "hidden": {"conditions": conds, "note": "Only the scoring code reads this."},
    }


def build() -> dict:
    rows = library_rows(ROOT / "libraries")
    model_rows = [r for r in rows if r["wording"] == "model"]
    pref = [r for r in model_rows if r.get("results_prompt") in PREFERRED_RESULTS_PROMPTS]
    pick = max(pref or model_rows, key=lambda r: r["cards"]) if model_rows else None
    out = {
        "format": "cards-bundle/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "libraries": rows,
        "totals": {
            "libraries": len(rows),
            "cards": sum(r["cards"] for r in rows),
            "model_written_cards": sum(r["cards"] for r in model_rows),
            "template_cards": sum(r["cards"] for r in rows if r["wording"] == "template"),
        },
        "example": None,
    }
    if pick:
        try:
            out["example"] = example(pick["name"], rows)
        except Exception as e:  # the page then shows the counts only
            print("  example failed:", e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "demo" / "data" / "cards_bundle.js"))
    args = ap.parse_args()
    data = build()
    Path(args.out).write_text("window.CARDS_DATA = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n", encoding="utf-8")
    t = data["totals"]
    print(f"wrote {args.out}: {t['libraries']} libraries, {t['cards']} cards ({t['model_written_cards']} model-written, {t['template_cards']} template)")
    ex = data["example"]
    print("  example:", ex and f"{ex['library']} {ex['card']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

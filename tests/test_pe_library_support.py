"""Helpers for the library, cohort and reveal tests (WP-C1-6). No tests here.

Cards are copies of ``tests/fixtures/patient_engine/card_example.json`` with new ids, primary conditions and
results. They are made for ``catalogue/_examples/tiny`` (3 conditions: lung_cancer, pneumonia, healthy).
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

from patient_engine.catalogue import load_catalogue
from patient_engine.library import Library, load_library, write_library

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "patient_engine" / "card_example.json"
TINY = ROOT / "catalogue" / "_examples" / "tiny"

CONDITIONS = ("lung_cancer", "pneumonia", "healthy")


def tiny_catalogue():
    return load_catalogue(TINY)


def fixture_card() -> dict:
    return json.loads(FIXTURE.read_text())


def make_card(i: int, primary: str, catalogue_hash: str, lib_name: str = "T") -> dict:
    """A card dict for patient ``i`` with primary condition ``primary``; results vary with ``i``."""
    d = copy.deepcopy(fixture_card())
    d["id"] = f"{lib_name}:{primary}:{i:04d}"
    d["provenance"]["catalogue_hash"] = catalogue_hash
    d["background"]["age"] = 40 + i % 45
    h, obs = d["hidden"], d["observations"]["all_active"]
    f = h["findings"]["all_active"]
    plan = h["error_plan"]["all_active"]
    if primary == "lung_cancer":
        h["conditions"][0]["attributes"] = {"stage": ["I", "II", "III", "IV"][i % 4], "location": ["central", "peripheral"][i % 2]}
        f["lesion_size_mm"]["value"] = float(8 + i % 30)
        obs["chest_ct"][0]["values"]["size_mm"] = float(8 + i % 30)
    else:
        h["conditions"] = [{"id": primary, "role": "primary", "attributes": {}}]
        if primary == "pneumonia":
            f["cough_3wk"]["caused_by"] = ["pneumonia"]
        else:                                           # healthy: nothing causes anything
            for v in f.values():
                v["caused_by"] = []
            f["fever"]["value"] = False
            f["consolidation"]["value"] = False
            d["presenting"]["all_active"] = {"reported": ["cough_3wk"], "text": "A cough that will not go away."}
            obs["history"][0]["values"]["fever"] = False
            obs["chest_xray"][0]["values"]["consolidation"] = False
            obs["chest_xray"][1]["values"]["consolidation"] = False
        f["lung_lesion"] = {"value": False, "caused_by": []}
        f["lesion_size_mm"] = {"value": None, "caused_by": []}
        f["lesion_location"] = {"value": None, "caused_by": []}
        for a in obs["chest_xray"][:2]:
            a["values"]["abnormal"] = False
        obs["chest_ct"][0]["values"] = {"nodule_seen": False, "size_mm": None, "location": None}
        obs["chest_ct"][0]["report"] = "No nodule."
    if i % 5 == 0:                                      # a non-diagnostic first X-ray on some cards
        obs["chest_xray"][0] = {"status": "non_diagnostic", "values": {}, "report": "Image not interpretable."}
        plan["chest_xray"][0] = {"status": "non_diagnostic", "outputs": {}}
    obs["blood_count"][0]["values"]["crp"] = float(5 + (i * 7) % 120)
    return d


def make_cards(per_condition: int, catalogue_hash: str, lib_name: str = "T", conditions=CONDITIONS) -> list[dict]:
    return [make_card(i, c, catalogue_hash, lib_name) for c in conditions for i in range(per_condition)]


def build_library(path: Path, per_condition: int = 30, *, lib_name: str = "T", conditions=CONDITIONS,
                  meta: dict | None = None) -> tuple[Library, object]:
    """Write a library of ``per_condition`` cards for each condition under ``path`` and load it with the catalogue."""
    cat = tiny_catalogue()
    cards = make_cards(per_condition, cat.version_hash, lib_name, conditions)
    write_library(cards, cat, path, {"created": "2026-11-14T12:00:00Z", **(meta or {})})
    return load_library(path, cat), cat


def wide_catalogue(dest: Path, n_tests: int = 20):
    """A catalogue made from the tiny one with ``n_tests`` tests (copies of its four, renamed), and the card
    transform that gives a card results for every test. For the size measurement."""
    shutil.copytree(TINY, dest)
    import yaml
    tests = yaml.safe_load((TINY / "tests.yaml").read_text())
    extra = []
    k = 0
    while len(tests) + len(extra) < n_tests:
        base = tests[k % 4]
        t = copy.deepcopy(base)
        t["id"] = f"{base['id']}_x{k // 4 + 1}"
        t.pop("requires", None)
        extra.append(t)
        k += 1
    (dest / "tests.yaml").write_text(yaml.safe_dump(tests + extra, sort_keys=False))
    cat = load_catalogue(dest)

    def widen(card: dict) -> dict:
        card = copy.deepcopy(card)
        obs = card["observations"]["all_active"]
        plan = card["hidden"]["error_plan"]["all_active"]
        for t in extra:
            base = t["id"].rsplit("_x", 1)[0]
            obs[t["id"]] = copy.deepcopy(obs[base])
            plan[t["id"]] = copy.deepcopy(plan[base])
        card["provenance"]["catalogue_hash"] = cat.version_hash
        return card

    return cat, widen

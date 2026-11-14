"""The encounter-loop demo page (demo/encounter.html): bundle integrity and the hidden-truth split.

The fast tests read the committed bundle (demo/data/encounter_bundle.js, from demo/export_encounter.py);
the slow one re-exports a small run from the scenario files. No browser is needed: the page's data
contract is checked here, the page itself was checked in headless Chrome (see demo/README.md)."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
BUNDLE = DEMO / "data" / "encounter_bundle.js"
sys.path.insert(0, str(DEMO))

TRUTH_KEYS = {"condition", "primary_condition", "conditions", "cancer", "matched", "primary", "marks"}


def load(path: Path = BUNDLE) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"window\.ENC_DATA = (.*);\s*$", text, re.S)
    assert m, "bundle must be a plain script: window.ENC_DATA = {...};"
    return json.loads(m.group(1))


def default_part(b: dict) -> dict:
    return {k: v for k, v in b.items() if k != "truth"}


def check_integrity(b: dict) -> None:
    assert b["format"] == "encounter-bundle/1"
    ids = {n["id"] for n in b["nodes"]}
    assert len(ids) == len(b["nodes"])
    for e in b["edges"]:
        assert e["source"] in ids and e["target"] in ids, e
        assert e["n"] >= 1
    for need in ("first", "discharge", "referral", "treat_pc", "nurse", "gp"):
        assert need in ids
    assert any(e["target"] == "first" and e["source"] == "discharge" for e in b["edges"]), "no return edge"
    ex_ids = {e["id"] for e in b["examples"]}
    by_id = {p["id"]: p for p in b["patients"]}
    assert ex_ids <= set(by_id)
    for p in b["patients"]:
        assert p["lines"], p["id"]
        ts = [r[0] for r in p["path"]]
        assert ts == sorted(ts)
        assert all(0 <= r[1] < len(b["nodes"]) and r[2] in (0, 1, 2, 3) for r in p["path"])
        for t, layer, text, ep in p["lines"]:
            assert layer in (0, 1) and isinstance(text, str) and text.startswith("Day ")
        assert any(l[1] == 1 for l in p["lines"]) and any(l[1] == 0 for l in p["lines"]), "both record layers"
    assert set(b["truth"]) >= {str(i) for i in by_id}
    assert {"overall", "by_group"} <= set(b["results"])


def check_truth_split(b: dict) -> None:
    d = default_part(b)
    for p in d["patients"] + d["examples"]:
        assert not (TRUTH_KEYS & set(p)), set(p)
    blob = json.dumps(d)
    # the patient's own record never carries the true condition id (underscore form, as in the catalogue)
    for p in d["patients"]:
        prim = b["truth"][str(p["id"])].get("primary") or ""
        if "_" in prim:
            assert prim not in json.dumps(p["lines"]), (p["id"], prim)
    assert "treatments_matching_share" not in blob
    # captions that name the truth live only in the truth part
    for e in b["examples"]:
        assert set(e) == {"key", "id", "label"}
        assert b["truth"][str(e["id"])].get("caption")
        assert "cancer" not in e["label"].lower()


@pytest.mark.skipif(not BUNDLE.exists(), reason="demo/data/encounter_bundle.js not generated")
def test_committed_bundle_integrity():
    b = load()
    check_integrity(b)
    assert len(BUNDLE.read_bytes()) < 5_000_000
    assert b["n_cancer"] >= 40
    assert len(b["examples"]) >= 4


@pytest.mark.skipif(not BUNDLE.exists(), reason="demo/data/encounter_bundle.js not generated")
def test_committed_bundle_hides_truth_by_default():
    check_truth_split(load())


def test_page_files_reference_each_other():
    html = (DEMO / "encounter.html").read_text()
    for f in ("encounter.css", "data/encounter_bundle.js", "encounter.js"):
        assert f in html
    js = (DEMO / "encounter.js").read_text()
    # the truth is read only behind the toggle
    assert js.count("D.truth") >= 1
    assert "S.truth" in js


@pytest.mark.slow
def test_fresh_small_export(tmp_path):
    import export_encounter as ex
    b = ex.build(n=700, seed=3, sample=60, target_cancers=10)
    out = tmp_path / "b.js"
    out.write_text("window.ENC_DATA = " + json.dumps(b) + ";\n")
    b2 = load(out)
    check_integrity(b2)
    check_truth_split(b2)

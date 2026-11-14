"""Research claims register (docs/research_claims.yaml) and its generated outputs
(docs/research_claims.md, demo/data/research_bundle.js from demo/export_research.py)."""
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))
import export_research as ER  # noqa: E402

REG = yaml.safe_load((ROOT / "docs" / "research_claims.yaml").read_text())
SOURCES = yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())
SOURCE_IDS = {s["id"] for s in SOURCES}
BUNDLE = ER.read_bundle()


def test_every_claim_has_exactly_one_known_basis_and_a_stable_slug():
    ids = [c["id"] for c in REG["claims"]]
    assert len(ids) == len(set(ids)), "duplicate claim ids"
    themes = {t["id"] for t in REG["themes"]}
    for c in REG["claims"]:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", c["id"]), c["id"]
        assert c["basis"] in {"published", "simulation", "assumption"}, c["id"]
        assert c["theme"] in themes, c["id"]
        assert c.get("strength"), f"{c['id']}: strength line missing"
        if c["basis"] == "simulation":
            assert c.get("run") and c.get("inputs"), c["id"]
        if c["basis"] == "assumption":
            assert c.get("where") and c.get("reason"), c["id"]


def test_published_claims_cite_a_registered_source():
    for c in REG["claims"]:
        if c["basis"] == "published":
            assert c.get("source") in SOURCE_IDS, f"{c['id']}: {c.get('source')!r} not in params/sources.yaml"
            assert c.get("figure") and c.get("kind"), c["id"]


def test_access_level_comes_from_the_registry_not_typed():
    acc = {s["id"]: s.get("access") for s in SOURCES}
    for c in BUNDLE["claims"]:
        if c["basis"] == "published":
            assert c["access"] == acc[c["source"]], c["id"]
    for c in REG["claims"]:
        assert "access" not in c, f"{c['id']}: access is read from params/sources.yaml"


def test_simulation_numbers_are_not_typed():
    """Simulation claims (and computed counts) carry numbers only through {ns.key} placeholders."""
    for c in REG["claims"]:
        if c["basis"] == "simulation":
            bare = re.sub(r"\b[A-Z][A-Z_]*\d{4}\w*", "", ER.PH.sub("", c["claim"]))  # source ids may appear
            assert not re.search(r"\d", bare), f"{c['id']}: typed number in a simulation claim: {bare}"


def test_every_source_id_used_in_params_is_in_the_bundle():
    in_bundle = {s["id"] for s in BUNDLE["sources"]}
    assert in_bundle == SOURCE_IDS
    used = set()
    for p in (ROOT / "params").glob("*.yaml"):
        if p.name == "sources.yaml":
            continue
        used |= set(re.findall(r"source:\s*\"?([A-Z][A-Z0-9_]+)", p.read_text()))
    missing = used - in_bundle
    assert not missing, f"source ids used in params/*.yaml but not in the bundle: {sorted(missing)}"


def test_bundle_claims_resolved_and_counts_add_up():
    assert BUNDLE["format"] == "research-bundle/1"
    assert sum(BUNDLE["counts"].values()) == len(BUNDLE["claims"])
    for c in BUNDLE["claims"]:
        assert "{" not in c["claim"], c["id"]
    assert set(BUNDLE["counts"]) == {"published", "simulation", "assumption"}


def test_framing_sentence_present():
    f = BUNDLE["framing"]
    for phrase in ("research establishes where time is lost", "can be simulated", "Norwegian hospital",
                   "searched for and tested", "estimate that rests on the inputs"):
        assert phrase in f
    md = (ROOT / "docs" / "research_claims.md").read_text()
    assert f in md
    assert "## What we could not support" in md


def test_waiting_split_adds_up():
    for key in ("finland", "norway"):
        d = BUNDLE["waiting_split"][key]
        assert d["critical_path_check_days"] < 1e-6
        assert abs(sum(d["by_basis_share"].values()) - 1) < 0.01
        assert abs(sum(d["by_basis_days"].values()) - d["waiting_days"]) < 0.3


def test_bundle_current_apart_from_the_simulation():
    """Fast tier: rebuild everything except the two simulation runs (reused from the bundle)."""
    stored = json.loads(json.dumps(BUNDLE))
    stored.pop("generated_at", None)
    ws = stored["waiting_split"]
    vals = dict(ws["values"])
    vals["fi_bundle_wait_pct"] = ER.pct(ER.bundle_wait_share("finland_lung"))
    vals["no_bundle_wait_pct"] = ER.pct(ER.bundle_wait_share("stokstad"))
    split = {"finland": ws["finland"], "norway": ws["norway"], "values": vals}
    B = json.loads(json.dumps(ER.build(REG, SOURCES, split, ER.pitch_values())))
    assert B == stored, "research bundle stale: run python demo/export_research.py"
    assert (ROOT / "docs" / "research_claims.md").read_text() == ER.render_md(B)


@pytest.mark.slow
def test_full_reexport_identical_apart_from_timestamp():
    B, md = ER.export()
    stored = dict(BUNDLE)
    stored.pop("generated_at", None)
    assert json.loads(json.dumps(B)) == stored
    assert (ROOT / "docs" / "research_claims.md").read_text() == md

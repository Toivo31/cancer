import json
import re
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "demo"
FIXTURE = DEMO / "data" / "demo_bundle.fixture.json"
INDEX = DEMO / "index.html"

METRIC_KEYS = {
    "n", "n_cancer", "median_days_to_treatment", "share_within_target", "missed_cancers",
    "tests_per_patient", "stage_breakdown", "node_breakdown",
}
STAGES = {"detection", "referral", "diagnosis", "treatment_start"}


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_contract_keys():
    b = load()
    assert b["fixture"] is True
    assert "generated_at" in b and b["scenarios"] and b["assumptions"]
    ids = {s["id"] for s in b["scenarios"]}
    assert {"stokstad", "finland_lung"} <= ids
    for s in b["scenarios"]:
        assert {"id", "title", "target_days", "baseline", "variants",
                "flowchart_before", "flowchart_after"} <= set(s)
        assert s["baseline"]["label"]
        assert any(v.get("changes") for v in s["variants"])
        for m in [s["baseline"]["metrics"]] + [v["metrics"] for v in s["variants"]]:
            assert METRIC_KEYS <= set(m)
            assert set(m["stage_breakdown"]) == STAGES
            for st in m["stage_breakdown"].values():
                assert {"wait", "service"} <= set(st)
        node_ids = {n["id"] for n in s["flowchart_before"]["nodes"]}
        for key in ("flowchart_before", "flowchart_after"):
            nodes = s[key]["nodes"]
            known = {n["id"] for n in nodes}
            for n in nodes:
                assert set(n.get("after", [])) <= known
        assert set(s["baseline"]["metrics"]["node_breakdown"]) <= node_ids
    for a in b["assumptions"]:
        assert {"parameter", "value", "source", "status"} <= set(a)
        assert a["status"] in ("sourced", "assumption")


def test_stokstad_numbers():
    s = next(s for s in load()["scenarios"] if s["id"] == "stokstad")
    m = s["baseline"]["metrics"]
    assert m["share_within_target"] == 0.40 and m["median_days_to_treatment"] == 46.5
    assert s["published"] == {"baseline_share": 0.40, "faster_pet_share": 0.48,
                              "optimal_share": 0.80, "source": s["published"]["source"]}


def test_stage_breakdown_sums_to_node_breakdown():
    for s in load()["scenarios"]:
        m = s["baseline"]["metrics"]
        total_stage = sum(v["wait"] + v["service"] for v in m["stage_breakdown"].values())
        total_node = sum(v["wait"] + v["service"] for v in m["node_breakdown"].values())
        assert abs(total_stage - total_node) < 0.05


def test_embedded_copy_matches_fixture():
    """The embedded offline copy equals the real bundle if one exists, else the fixture."""
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r'<script id="bundle" type="application/json">\n(.*?)\n</script>', html, re.S)
    assert m, "embedded bundle not found"
    real = INDEX.parent / "data" / "demo_bundle.json"
    expected = json.loads(real.read_text()) if real.exists() else load()
    assert json.loads(m.group(1)) == expected


def test_real_bundle_wave2_fields():
    real = INDEX.parent / "data" / "demo_bundle.json"
    if not real.exists():
        return
    for s in json.loads(real.read_text())["scenarios"]:
        o = s["optimiser"]
        assert len(o["details"]) == len(o["steps"])
        assert len(o["cumulative"]) >= len(o["steps"]) + 1
        assert all(0 <= r["share"] <= 1 for r in o["cumulative"])
        assert all(d["label"] and d["raw"] for d in o["details"])
        for r in (s.get("capacity_vs_order") or {}).get("rows", []):
            assert {"kind", "label", "share"} <= set(r)
    st = next(s for s in json.loads(real.read_text())["scenarios"] if s["id"] == "stokstad")
    assert "headline_no_new_equipment" in st


def test_polish_change_has_no_internal_words():
    import sys
    sys.path.insert(0, str(DEMO.parent))
    from demo.export import POLISHED
    for text in POLISHED.values():
        assert not re.search(r"\b(node|optimi[sz]er|flowchart|guard)\b", text, re.I)

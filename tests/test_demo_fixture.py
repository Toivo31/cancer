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
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r'<script id="bundle" type="application/json">\n(.*?)\n</script>', html, re.S)
    assert m, "embedded bundle not found"
    assert json.loads(m.group(1)) == load()

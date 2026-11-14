"""D68 (Tuomas, 14 Nov): no page-facing file states or shows the optimiser's result combined with the faster PET-CT
scanner. The authors (Stokstad et al. 2019) reported the faster scanner alone and their reordered pathway separately,
so we keep those two (and our simulation of each) and report the optimiser only as run from today's pathway with no
new equipment. Same review: the 'Where time is lost' claim carries its provenance (wait_basis) and screen 4
'Capacity or order' has no combined bar and a 'Where these numbers come from' strip. See docs/review_scanner_claims.md."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE_FILES = (sorted((ROOT / "demo").glob("*.html")) + sorted((ROOT / "demo").glob("*.js"))
              + sorted((ROOT / "demo" / "data").glob("*.js")) + [ROOT / "demo" / "data" / "demo_bundle.json"]
              + sorted(p for p in (ROOT / "live_demo").rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".json"))
              + sorted((ROOT / "docs" / "pitch" / "filled").glob("*.md"))
              + [ROOT / "video" / "dots" / "dots_data.js"])

FORBIDDEN = [
    "optimiser_scanner", "optimiser_faster_scanner", "scanner_beats_scanner_alone", "suggested_faster_pet",
    "opt_stokstad_fastpet", "Reordered steps and the faster scanner", "with the faster PET-CT scanner (best fit",
    "with reordering and the faster PET-CT scanner", "With reordering and the faster PET-CT scanner",
    "Optimiser, same scanner", "found blind, with the faster PET-CT", "Optimiser, found blind (with the faster PET-CT)",
    "and the two together help most", "With the faster scanner:", "88% with the faster scanner",
]


def _bundle():
    return json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())


def _scenario(sid):
    return next(s for s in _bundle()["scenarios"] if s["id"] == sid)


def test_page_files_carry_no_with_scanner_optimiser_result():
    hits = []
    for p in PAGE_FILES:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits += [f"{p.relative_to(ROOT)}: {s!r}" for s in FORBIDDEN if s in text]
    assert not hits, "with-scanner optimiser result is back on a page (D68):\n" + "\n".join(hits)


def test_scanner_alone_and_authors_rows_stay():
    """The authors' published figures and our simulation of the scanner alone and of their pathway remain."""
    s = _scenario("stokstad")
    assert s["published"]["baseline_share"] == 0.40
    assert s["published"]["faster_pet_share"] == 0.48
    assert s["published"]["optimal_share"] == 0.80
    roles = [v["role"] for v in s["variants"]]
    assert "faster_pet" in roles and "authors_pathway" in roles
    assert roles.count("optimiser_no_new_equipment") == 1
    assert "optimiser" not in roles, "the Norway 'optimiser' role was the with-scanner run"


def test_norway_optimiser_steps_start_from_observed_not_scanner():
    s = _scenario("stokstad")
    o = s["optimiser"]
    obs = s["baseline"]["metrics"]["share_within_target"]
    fast = next(v for v in s["variants"] if v["role"] == "faster_pet")["metrics"]["share_within_target"]
    cum = [r for r in o["cumulative"] if r["kind"] != "lead"]
    assert not [r for r in o["cumulative"] if r["kind"] == "lead"], "a lead row means the search started elsewhere"
    assert abs(cum[0]["share"] - obs) < 1e-9 and abs(cum[0]["share"] - fast) > 0.05
    noeq = next(v for v in s["variants"] if v["role"] == "optimiser_no_new_equipment")
    assert abs(cum[-1]["share"] - noeq["metrics"]["share_within_target"]) < 1e-9
    assert abs(s["headline_no_new_equipment"]["share"] - noeq["metrics"]["share_within_target"]) < 1e-9
    # every step card's rerun line starts from a share at or below the observed start's first step
    first = o["details"][0]["rerun_said"]
    assert f"{round(100 * fast)}%" not in first.split(" to ")[0]


def test_norway_capacity_rows_have_no_combined_bar():
    cv = _scenario("stokstad")["capacity_vs_order"]
    kinds = [r["kind"] for r in cv["rows"]]
    assert "both" not in kinds
    assert kinds == ["today", "capacity", "order"]
    cap = next(r for r in cv["rows"] if r["kind"] == "capacity")
    assert cap["published_share"] == 0.48
    for sid in ("stokstad", "finland_lung"):
        c = _scenario(sid)["capacity_vs_order"]
        assert c["n_patients"] > 0 and c["n_cohorts"] >= 1
    fin = _scenario("finland_lung")["capacity_vs_order"]["rows"]
    assert all(r.get("what_if") for r in fin if r["kind"] == "capacity")


def test_capacity_strip_is_on_the_dashboard():
    html = (ROOT / "demo" / "index.html").read_text()
    assert "function capSources(" in html and "h+=capSources(sc,cv);" in html
    assert "Where these numbers come from" in html
    assert "What-if: capacity values chosen by us, not measured" in html
    assert "Published estimate by the authors: " in html


def test_wait_basis_in_bundle_and_page():
    for sid in ("stokstad", "finland_lung"):
        wb = _scenario(sid)["wait_basis"]
        g = wb["groups"]
        assert set(g) == {"published", "assumption"}
        assert abs(g["published"]["share_of_waiting"] + g["assumption"]["share_of_waiting"] - 1) < 0.002
        assert abs(g["published"]["days"] + g["assumption"]["days"] - wb["waiting_days"]) < 0.25
        assert not wb["untagged_tests"]
        assert "not a measurement from patient data" in wb["statement"]
        # the page's headline share (stage_breakdown) and wait_basis describe the same waiting
        sb = _scenario(sid)["baseline"]["metrics"]["stage_breakdown"]
        tw = sum(v["wait"] for v in sb.values())
        tt = tw + sum(v["service"] for v in sb.values())
        assert abs(round(100 * tw / tt) - round(100 * wb["waiting_share"])) <= 1
    fin = _scenario("finland_lung")["wait_basis"]["groups"]["published"]["steps"]
    assert any("ALL cancers" in r["source"] for r in fin), "the 37-day figure must be flagged as all cancers"
    html = (ROOT / "demo" / "index.html").read_text()
    assert "In our model, '+Math.round(tw/tt*100)+'% of the time to treatment is waiting" in html
    assert "h+=waitBasisStrip(sc);" in html
    for label in ("From our simulation:", "Set from published figures:", "Our assumption or placeholder:"):
        assert label in html
    flow = (ROOT / "demo" / "flow.js").read_text()
    assert "h += waitBasisNote();" in flow
    fb = (ROOT / "demo" / "data" / "flow_bundle.js").read_text()
    assert fb.count('"wait_basis"') >= 2


def test_pitch_headline_is_no_equipment():
    sheet = (ROOT / "docs" / "pitch" / "filled" / "numbers_sheet.md").read_text()
    assert "with no new equipment at the best fit" in sheet
    assert not re.search(r"\[\[[a-z0-9_]+\]\]", sheet)

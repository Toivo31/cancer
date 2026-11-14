"""Review w7, findings M1 and M2: stale numbers on the demo path and in the plan.

Expected to FAIL on the current tree; each passes after the named exporter is rerun or the text updated.
Fast: reads committed files only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

#: Each test shows an open finding, so it fails today. strict: once the finding is fixed the test passes,
#: the run reports XPASS as a failure, and the marker must be removed (the test then guards the fix).
# Review w7 B2/M1/M2: fixed on 14 Nov evening (bundles regenerated, pitch corrected); these tests now guard the fix.

ROOT = Path(__file__).resolve().parents[1]


def _bundle(name: str) -> dict:
    s = (ROOT / "demo" / "data" / name).read_text()
    return json.loads(s[s.index("{"): s.rindex("}") + 1])


def test_start_bundle_reads_the_robustness_and_tuned_reports_that_exist():
    """docs/review_checks/norway_leave_one_out.json and encounter_results.json exist, yet the start bundle has
    null for both, so the start page shows "pending" for numbers that are ready. Fix: python demo/export_start.py."""
    st = _bundle("start_bundle.js")
    if (ROOT / "docs/review_checks/norway_leave_one_out.json").exists():
        assert st["norway_robustness"] is not None, "start page shows the robustness range as pending"
    if (ROOT / "docs/review_checks/encounter_results.json").exists():
        assert st["encounter_results"] is not None, "start page shows the tuned encounter report as pending"


def test_encounter_bundle_is_newer_than_the_tuned_decision_tables():
    """The encounter bundle (16:42 UTC) predates the tuned tables merged at 17:00 UTC, so the start page and
    encounter.html show pre-tuning numbers (29% within 90 d, 28 d to referral; the current code gives about
    25% and 47 d on the same run). Fix: python demo/export_encounter.py, then demo/export_start.py."""
    enc = _bundle("encounter_bundle.js")
    rep = json.loads((ROOT / "docs/review_checks/encounter_results.json").read_text())
    # the tuned report is written after tuning; the bundle must not be older than the tables it shows
    tables = (ROOT / "scenarios" / "finland_encounter_policy.yaml").read_text()
    assert "suspicion" in tables.lower() or "weight_loss" in tables, "tuned tables not found"
    gen = enc["generated_at"]
    assert gen >= "2026-11-14T17:00:00", f"encounter bundle generated {gen}, before the tuned tables were merged"


def test_plan_does_not_quote_the_superseded_norway_band():
    """The robustness analysis (docs/validation.md, Robustness) widened the authors'-pathway prediction from
    78-86% to 62-86% (central about 75%). The old band may only appear next to the current one."""
    stale = re.compile(r"78\s*(?:to|-|–)\s*86")
    hits = []
    for rel in ("docs/master_plan.md", "docs/pitch/filled/data_transparency.md", "README.md"):
        p = ROOT / rel
        if p.exists():
            for i, line in enumerate(p.read_text().splitlines(), 1):
                # Quoting the old band is fine where the same line gives the current one (62 to 86).
                if stale.search(line) and not re.search(r"62\s*(?:to|-|–)\s*86", line):
                    hits.append(f"{rel}:{i}")
    assert not hits, "superseded 78-86% band quoted at " + ", ".join(hits)

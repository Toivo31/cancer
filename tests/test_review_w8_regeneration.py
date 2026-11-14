"""Review w8: the regeneration script and the training-set builder see the g2@2 libraries correctly."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_training_set as b  # noqa: E402


def _fake(name, n):
    return name, SimpleNamespace(manifest=SimpleNamespace(n_cards=n), path=Path("/x") / name)


def test_holdout_picks_the_newest_g2v2_library():
    found = [_fake("ref500", 500), _fake("gemini_s2_30", 30), _fake("gemini_s7_500", 500),
             _fake("gemini_v2_trial30", 30), _fake("gemini_v2_s13_500", 500), _fake("gemini_v2_s17_500", 500)]
    assert b.pick_holdout(found, None) == "gemini_v2_s17_500"


def _status(tmp_path: Path, report: dict) -> str:
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "generate_gemini.sh", tmp_path / "scripts")
    work = tmp_path / "libraries" / "gemini_v2_s99_500.work"
    work.mkdir(parents=True)
    (work / "generation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    env = {**os.environ, "SEEDS": "99"}
    r = subprocess.run(["bash", str(tmp_path / "scripts" / "generate_gemini.sh"), "status"], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_status_does_not_call_a_partial_library_done(tmp_path):
    out = _status(tmp_path, {"partial": True, "accepted": 300, "requested": 500, "discarded": 2, "failed": 0,
                             "not_completed": 198, "stop_reason": "budget"})
    assert "PARTIAL" in out and "300/500" in out


def test_status_shows_failed_cards(tmp_path):
    out = _status(tmp_path, {"partial": False, "accepted": 470, "requested": 500, "discarded": 5, "failed": 25,
                             "not_completed": 0, "stop_reason": None})
    assert "WITH FAILED CARDS" in out and "failed 25" in out

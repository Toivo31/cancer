"""scripts/build_training_set.py: which libraries are used and which one is held out (no export is run)."""

import subprocess

import pytest
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_training_set as b  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def fake(name, n, tmp=Path("/x")):
    return name, SimpleNamespace(manifest=SimpleNamespace(n_cards=n), path=tmp / name)


def test_holdout_is_the_highest_seed_gemini_library():
    found = [fake("ref500", 500), fake("gemini_trial", 5), fake("gemini_s2_30", 30)]
    assert b.pick_holdout(found, None) == "gemini_s2_30"
    found += [fake("gemini_s3_500", 500), fake("gemini_s7_500", 500), fake("gemini_s5_500", 500)]
    assert b.pick_holdout(found, None) == "gemini_s7_500"
    assert b.pick_holdout(found, "libraries/gemini_s3_500") == "gemini_s3_500"


def test_small_libraries_get_fewer_patients():
    assert b.patients_for(2000, fake("a", 5)[1]) == 200
    assert b.patients_for(2000, fake("a", 30)[1]) == 600
    assert b.patients_for(2000, fake("a", 500)[1]) == 2000
    assert b.patients_for(300, fake("a", 500)[1]) == 300


def test_dry_run_lists_libraries_and_roles():
    p = subprocess.run([sys.executable, "scripts/build_training_set.py", "--dry-run"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if p.returncode != 0 and "no gemini_s<seed>_<n> library found" in p.stderr:
        pytest.skip("no gemini_s* library made for the current catalogue yet (D59 changed the hash)")
    assert p.returncode == 0, p.stderr
    assert "ref500" in p.stdout and "TEST" in p.stdout and "pack-years" in p.stdout

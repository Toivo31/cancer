"""Golden checks on what a judge sees, beyond the template test in test_golden_templates.py.

* Norway through the CLI and through the service API: observed share treated within 42 days is 0.34 to 0.46.
  The published figure is 0.40 (Stokstad 2019); the bundle has 0.401. The band is the published 40% +- 6 points:
  two seeds of 1000 patients have a sampling error of about 1.1 points (1 sd), so 6 points is over 5 sd and only a
  real change in the world file moves a run out of it (the uncalibrated file gives about 0.11).
* The pitch numbers: every [[placeholder]] in docs/pitch/*.md can be filled from the bundle, and the committed
  docs/pitch/filled/*.md equal a fresh fill. docs/pitch/fill_numbers.py has no --check flag, so this test does the
  same with its own build_values() (read-only: nothing is written).
* The Finnish headline in the bundle is sane: the optimiser's flowchart treats more within the target than today's.
"""

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings

ROOT = Path(__file__).resolve().parent.parent
NORWAY = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"
LOW, HIGH = 0.34, 0.46
SEEDS = (301, 302)
N = 1000


def test_norway_observed_through_the_cli():
    shares = []
    for seed in SEEDS:
        out = subprocess.run([sys.executable, "-m", "pathway_sim", "run", str(NORWAY), "--flowchart", "observed",
                              "--n", str(N), "--seed", str(seed)], cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr
        m = re.search(r"^observed\s+on-time\s+([\d.]+)%", out.stdout, re.M)
        assert m, out.stdout
        shares.append(float(m.group(1)) / 100)
    share = sum(shares) / len(shares)
    assert LOW <= share <= HIGH, shares


def test_norway_template_observed_through_the_service_api(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "noweb", max_patients=5000, max_seeds=3))
    with TestClient(app) as c:
        p = c.post("/api/projects", json={"name": "golden", "template": "norway_check"}).json()["id"]
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": N, "seeds": list(SEEDS)})
        assert r.status_code == 202, r.text
        run = r.json()
        end = time.time() + 120
        while time.time() < end:
            j = c.get(f"/api/jobs/{run['job_id']}").json()
            if j["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.1)
        assert j["status"] == "succeeded", j
        share = c.get(f"/api/projects/{p}/runs/{run['id']}").json()["headline"]["on_time"]
    assert LOW <= share <= HIGH, share


# ---------------------------------------------------------------- pitch numbers
def _fill_numbers():
    spec = importlib.util.spec_from_file_location("fill_numbers", ROOT / "docs" / "pitch" / "fill_numbers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pitch_templates_fill_completely_and_the_committed_copies_are_current():
    fn = _fill_numbers()
    V = fn.build_values()
    missing, stale = {}, []
    for p in sorted(fn.PITCH.glob("*.md")):
        text = p.read_text()
        if p.name == "video_script.md":
            spoken = fn.PLACEHOLDER.sub(lambda mo: V.get(mo.group(1), "x"), text.split("## Spoken text only")[1].split("## Claims")[0])
            V["spoken_words"] = str(round(len(spoken.split()), -1))

        def sub(mo, name=p.name):
            if mo.group(1) in V:
                return V[mo.group(1)]
            missing.setdefault(mo.group(1), []).append(name)
            return mo.group(0)

        filled = fn.PLACEHOLDER.sub(sub, text)
        committed = fn.OUT / p.name
        if not committed.exists() or committed.read_text() != filled:
            stale.append(p.name)
    assert not missing, f"unfillable placeholders: {missing}"
    assert not stale, f"docs/pitch/filled is out of date for {stale}: run python docs/pitch/fill_numbers.py"


def test_bundle_headline_numbers_are_sane():
    b = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
    sc = {s["id"]: s for s in b["scenarios"]}
    no, fi = sc["stokstad"], sc["finland_lung"]
    assert 0.34 <= no["baseline"]["metrics"]["share_within_target"] <= 0.46 and no["target_days"] == 42
    opt = next(v for v in fi["variants"] if v.get("role") == "optimiser")["metrics"]
    base = fi["baseline"]["metrics"]
    assert fi["target_days"] == 90
    assert opt["share_within_target"] > base["share_within_target"]
    assert 0.10 <= base["share_within_target"] <= 0.30  # the published-evidence band for today's Finnish pathway is far from 0.40

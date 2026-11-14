"""Re-derive the two Norwegian optimiser flowcharts (same Config as demo/export.py::build_stokstad) and save them.
Exits non-zero if the held-out shares differ from the bundle.   ~5-10 min.
    python3 docs/evidence_checks/norway_suggested.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from optimiser import Config, search  # noqa: E402
from pathway_sim import load_scenario  # noqa: E402

sc = load_scenario(ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml")
cfg = Config(n_train=1000, heldout_seeds=(201, 202, 203), n_heldout=1000)
fast = search(sc, "faster_pet", cfg, log=lambda *a: None)
noeq = search(sc, "observed", cfg, log=lambda *a: None)
b = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
st = next(s for s in b["scenarios"] if s["id"] == "stokstad")
want = {v["role"]: v["metrics"]["share_within_target"] for v in st["variants"]}
got = {"optimiser": fast["heldout"]["after"]["share_within_target"], "optimiser_no_new_equipment": noeq["heldout"]["after"]["share_within_target"]}
ok = all(abs(got[k] - want[k]) < 1e-9 for k in got)
print("held-out", got, "bundle", {k: want[k] for k in got}, "match", ok)
(Path(__file__).with_name("norway_suggested_flowcharts.json")).write_text(json.dumps(
    {"faster_pet_optimised": fast["flowchart_after"], "observed_optimised": noeq["flowchart_after"], "check_matches_bundle": ok}, indent=1, default=str))
sys.exit(0 if ok else 1)

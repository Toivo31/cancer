"""Re-derive the accepted Finnish flowchart (optimiser, same Config as demo/export.py) and save it.

The sensitivity and range scripts need the suggested flowchart as a scenario document. The held-out
numbers printed here must equal the bundle's (demo/data/demo_bundle.json), otherwise the saved flowchart
is not the one behind the headline and the script exits non-zero.

    python3 docs/evidence_checks/finland_suggested.py        # about 3-6 min, writes finland_suggested_flowchart.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from optimiser import Config, search  # noqa: E402
from optimiser.search import cohorts, evaluate  # noqa: E402
from pathway_sim import load_scenario  # noqa: E402

OUT = Path(__file__).with_name("finland_suggested_flowchart.json")


def main() -> int:
    sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
    n = int(sc.raw.get("default_n", 2000))
    cfg = Config(n_train=n, heldout_seeds=(301, 302), n_heldout=n, allow=("detach", "relax", "standardise"), max_steps=6)
    res = search(sc, "baseline", cfg, log=lambda *a: None)
    after = res["flowchart_after"]
    held = cohorts(sc, cfg.heldout_seeds, n)
    m0, _ = evaluate(sc, sc.flowcharts["baseline"], held)
    from pathway_sim.scenario import parse_flowchart
    m1, _ = evaluate(sc, parse_flowchart("suggested", after), held)
    bundle = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
    fin = next(s for s in bundle["scenarios"] if s["id"] == "finland_lung")
    b0 = fin["baseline"]["metrics"]["share_within_target"]
    b1 = next(v for v in fin["variants"] if v.get("role") == "optimiser")["metrics"]["share_within_target"]
    print(f"held-out baseline {m0['share_within_target']:.4f} (bundle {b0:.4f}); suggested {m1['share_within_target']:.4f} (bundle {b1:.4f})")
    print("accepted steps:", [s.get("label") or s.get("text") or s["kind"] for s in res["steps"]])
    ok = abs(m0["share_within_target"] - b0) < 1e-9 and abs(m1["share_within_target"] - b1) < 1e-9
    OUT.write_text(json.dumps({"flowchart": after, "steps": res["steps"], "check_matches_bundle": ok}, indent=1, default=str))
    print("matches bundle:", ok, "->", OUT.name)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

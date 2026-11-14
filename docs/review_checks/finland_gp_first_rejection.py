"""Review check M5: why 'GP first instead of nurse first' was rejected (train cohorts 101, 102) and what the
held-out cohorts (301, 302) say. ~60 s.
    python3 docs/review_checks/finland_gp_first_rejection.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from optimiser.edits import Edit, apply  # noqa: E402
from optimiser.search import Config, cohorts, evaluate, guardrails  # noqa: E402
from pathway_sim import load_scenario  # noqa: E402

sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
for name, seeds in (("train", (101, 102)), ("held-out", (301, 302))):
    co = cohorts(sc, seeds, 18800)
    start = apply(sc, sc.flowcharts["baseline"].copy("x"), Edit("fast_track", "triage"))
    b, _ = evaluate(sc, start, co)
    g, _ = evaluate(sc, apply(sc, start, Edit("standardise", "first_contact", "gp_visit")), co)
    print(f"{name}: after fast track, GP first: share {b['share_within_target']} -> {g['share_within_target']}, "
          f"missed {b['missed_cancers']} -> {g['missed_cancers']} (of ~{b['n_cancer']}), guardrails {guardrails(g, b, Config())}")

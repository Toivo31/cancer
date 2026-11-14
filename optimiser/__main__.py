"""python -m optimiser SCENARIO --start FLOWCHART [--n 1000] [--out runs/opt.json]"""

import argparse
import json
from pathlib import Path

from pathway_sim import load_scenario

from .search import Config, search


def main(argv=None):
    ap = argparse.ArgumentParser(prog="optimiser")
    ap.add_argument("scenario")
    ap.add_argument("--start", default="baseline")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--top-k", type=int, default=12)
    ap.add_argument("--allow", default="detach,relax,standardise")
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    sc = load_scenario(a.scenario)
    cfg = Config(n_train=a.n, max_steps=a.steps, top_k=a.top_k, allow=tuple(a.allow.split(",")), exhaustive=a.exhaustive)
    res = search(sc, a.start, cfg)
    hb, ha = res["heldout"]["before"], res["heldout"]["after"]
    print(f"held-out: on-time {hb['share_within_target']:.3f} -> {ha['share_within_target']:.3f}, "
          f"median {hb['median_days_to_treatment']} -> {ha['median_days_to_treatment']} d, "
          f"missed {hb['missed_cancers']} -> {ha['missed_cancers']}, tests/pt {hb['tests_per_patient']} -> {ha['tests_per_patient']}")
    print(f"selection optimism (train gain - held-out gain): {res['selection_optimism_pp']} pp; "
          f"held-out guardrail breaches: {res['guardrails_heldout'] or 'none'}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print("wrote", a.out)


if __name__ == "__main__":
    main()

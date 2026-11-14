"""D3: `python -m decision_model.benchmark [--quick]`

Trains the dot-product baseline(s) and the correction model on
 (1) the set-relative comparison task and (2) a control task with no set-relative rule,
using fixed seeds and a train/test split, and measures compute for a first vs a second
question on the same context. Prints markdown tables. Numbers are measured, not tuned
for the story; read the notes printed at the end.
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from . import autograd as ag
from .models import CorrectionModel, DotProductModel
from .tasks import make_comparison_task
from .train import evaluate, fit

SEED = 0


def _wall(fn, reps):
    fn()
    t = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t) / reps * 1e6  # microseconds


def compute_table(n_options=4, reps=1000):
    rng = np.random.default_rng(1)
    ctx = rng.random((1, 15))
    opts = rng.random((1, n_options, 5))
    mask = np.ones((1, n_options), bool)
    rows = []
    configs = [("Dot-product", DotProductModel(), "default"),
               ("Correction (2 layers)", CorrectionModel(n_layers=2), "default"),
               ("Dot-product", DotProductModel(ctx_hidden=512), "heavy context encoder (hidden 512)"),
               ("Correction (2 layers)", CorrectionModel(n_layers=2, ctx_hidden=512), "heavy context encoder (hidden 512)")]
    for name, m, cfg in configs:
        f1, f2 = m.flops_first(n_options), m.flops_second(n_options)
        with ag.no_grad():
            c0 = m.encode_context(ctx)
            w1 = _wall(lambda: m.predict(ctx, opts, mask), reps)
            w2 = _wall(lambda: m.predict_proba(c0, opts, mask), reps)
        rows.append((name, cfg, f1, f2, f2 / f1, w1, w2, w2 / w1))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="small run (a few seconds)")
    a = ap.parse_args()
    n, epochs = (6000, 8) if a.quick else (30000, 25)
    t_start = time.time()
    results = []
    for task, relative in [("comparison (set-relative rule)", True), ("control (no set-relative rule)", False)]:
        tr, te = make_comparison_task(n, seed=SEED + 1, relative=relative).split(0.8, seed=SEED)
        models = [("Dot-product (d=32)", DotProductModel(seed=SEED)),
                  ("Dot-product, wider (param-matched)", DotProductModel(d=64, ctx_hidden=128, opt_hidden=128, seed=SEED)),
                  ("Correction (2 layers)", CorrectionModel(n_layers=2, seed=SEED))]
        if a.quick or not relative:
            models = [models[0], models[2]]  # skip the wide baseline where it adds little
        for name, m in models:
            t = time.time()
            fit(m, tr, epochs=epochs, seed=SEED)
            ev = evaluate(m, te)
            results.append((task, name, m.n_params(), ev["acc"], ev["logloss"], time.time() - t, len(te)))
        chance = float((1 / te.mask.sum(1)).mean())
    print(f"\n### Test accuracy and log-loss (n_train={len(tr)}, n_test={len(te)}, seed={SEED}, "
          f"random-pick accuracy ~ {chance:.2f}; binomial s.e. of accuracy ~ +-0.5pp)\n")
    print("| Task | Model | Params | Test accuracy | Test log-loss | Train s |")
    print("|---|---|---|---|---|---|")
    for task, name, npar, acc, ll, sec, _ in results:
        print(f"| {task} | {name} | {npar} | {acc:.3f} | {ll:.3f} | {sec:.0f} |")
    print("\n### Compute for a first vs a second question on the same context (4 options, per example)\n")
    print("| Model | Context encoder | FLOPs 1st | FLOPs 2nd (cached context) | 2nd/1st FLOPs | Wall us 1st | Wall us 2nd | 2nd/1st wall |")
    print("|---|---|---|---|---|---|---|---|")
    for name, cfg, f1, f2, rf, w1, w2, rw in compute_table():
        print(f"| {name} | {cfg} | {f1} | {f2} | {rf:.2f} | {w1:.0f} | {w2:.0f} | {rw:.2f} |")
    print(f"\ntotal runtime {time.time() - t_start:.0f}s")
    print("""
Notes
- The cached part is only the context embedding. Option encoding and the correction layers depend on the
  option set, so they are recomputed for every question. The saving is therefore (context encoder cost) /
  (total first-question cost). At this tiny scale the context encoder is a small share, so the saving is
  far from half; it approaches half only when the context encoder is about as expensive as the rest
  (rows marked 'heavy'), which is true by construction there, not a finding.
- Wall time at this size is dominated by numpy/Python call overhead and does not track FLOPs closely.
- Accuracy differences come from one training seed per model; the held-out set is fixed.""")


if __name__ == "__main__":
    main()

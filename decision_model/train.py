"""Training / evaluation helpers (cross-entropy on the chosen option, Adam, fixed seeds)."""
from __future__ import annotations

import time

import numpy as np

from . import autograd as ag
from .tasks import Dataset


def evaluate(model, ds: Dataset) -> dict:
    p = model.predict(ds.ctx, ds.opts, ds.mask)
    pick = p.argmax(1)
    return {"acc": float((pick == ds.y).mean()),
            "logloss": float(-np.log(p[np.arange(len(ds)), ds.y] + 1e-12).mean())}


def fit(model, ds: Dataset, epochs=20, batch=256, lr=3e-3, seed=0, max_seconds=None, verbose=False):
    rng = np.random.default_rng(seed)
    opt = ag.Adam(model.params, lr=lr)
    n, t0 = len(ds), time.time()
    steps = epochs * max(1, n // batch)
    for ep in range(epochs):
        order = rng.permutation(n)
        for s in range(0, n - batch + 1, batch):
            i = order[s:s + batch]
            for q in model.params.values():
                q.grad = None
            lg = model.logits(ds.ctx[i], ds.opts[i], ds.mask[i])
            loss = ag.cross_entropy(lg, ds.mask[i], ds.y[i])
            loss.backward()
            opt.step()
            opt.lr = lr * (0.5 * (1 + np.cos(np.pi * opt.t / steps)))
        if verbose:
            print(f"ep {ep} loss {float(loss.data):.3f}")
        if max_seconds and time.time() - t0 > max_seconds:
            break
    return model


def fit_reward(model, ds: Dataset, r: np.ndarray, epochs=30, batch=128, lr=3e-3, seed=0, max_seconds=None,
               weight_decay=0.0):
    """Regress the logit of the logged option on its observed outcome r (direct-method bandit).
    The model's logits become predicted outcomes per option; the policy picks the argmax.
    Unbiased for each option's value when the log came from a policy that does not look at
    the outcome (e.g. uniform random exploration). ``weight_decay``: L2 on weight matrices
    (decoupled, applied after each Adam step), shrinks spurious interactions in rare contexts."""
    rng = np.random.default_rng(seed)
    opt = ag.Adam(model.params, lr=lr)
    n, t0 = len(ds), time.time()
    batch = min(batch, n)
    steps = epochs * max(1, n // batch)
    for _ in range(epochs):
        order = rng.permutation(n)
        for s in range(0, n - batch + 1, batch):
            i = order[s:s + batch]
            for q in model.params.values():
                q.grad = None
            lg = model.logits(ds.ctx[i], ds.opts[i], ds.mask[i])
            ag.chosen_mse(lg, ds.y[i], r[i]).backward()
            opt.step()
            if weight_decay:
                for q in model.params.values():
                    if q.data.ndim == 2:
                        q.data -= opt.lr * weight_decay * q.data
            opt.lr = lr * (0.5 * (1 + np.cos(np.pi * min(opt.t, steps) / steps)))
        if max_seconds and time.time() - t0 > max_seconds:
            break
    return model


def predicted_values(model, ds: Dataset) -> np.ndarray:
    """Predicted outcome per option [n, N] (masked options = nan)."""
    with ag.no_grad():
        lg = model.logits(ds.ctx, ds.opts, ds.mask).data
    return np.where(ds.mask, lg, np.nan)

"""Dot-product baseline and the Jev-type correction model, in numpy (manual autograd).

Shapes: ctx [B, Dc], opts [B, N, Do], mask [B, N] (True = option allowed).

DotProductModel   logit_i = <f(context), g(option_i)>; every option scored on its own.
CorrectionModel   same, but L correction blocks first let the context embedding look at
                  the whole option set: c <- c + Wo * attention(q=c, keys/values=options).
                  The logit of option i therefore depends on the other options offered.

Two-step inference so a second question on the same context reuses the embedding:
    c0 = model.encode_context(ctx)                       # cached, depends on context only
    p1 = model.predict_proba(c0, opts_q1, mask_q1)
    p2 = model.predict_proba(c0, opts_q2, mask_q2)       # no context re-encoding
"""
from __future__ import annotations

import numpy as np

from . import autograd as ag
from .autograd import Tensor
from .features import N_CONTEXT, N_OPTION


def _init(rng, fan_in, fan_out):
    return Tensor(rng.normal(0, np.sqrt(2.0 / fan_in), (fan_in, fan_out)), requires_grad=True)


def _zeros(n):
    return Tensor(np.zeros(n), requires_grad=True)


class DotProductModel:
    n_layers = 0

    def __init__(self, d=32, ctx_hidden=64, opt_hidden=64, n_ctx=N_CONTEXT, n_opt=N_OPTION, seed=0):
        rng = np.random.default_rng(seed)
        self.d, self.ctx_hidden, self.opt_hidden, self.n_ctx, self.n_opt = d, ctx_hidden, opt_hidden, n_ctx, n_opt
        self.params: dict[str, Tensor] = {
            "c1": _init(rng, n_ctx, ctx_hidden), "cb1": _zeros(ctx_hidden),
            "c2": _init(rng, ctx_hidden, d), "cb2": _zeros(d),
            "e1": _init(rng, n_opt, opt_hidden), "eb1": _zeros(opt_hidden),
            "e2": _init(rng, opt_hidden, d), "eb2": _zeros(d),
        }
        self._build(rng)

    def _build(self, rng):  # subclasses add blocks
        pass

    # ---- encoders -------------------------------------------------------------
    def encode_context(self, ctx) -> Tensor:
        """Context embedding [B, 1, d]. Depends on the context only, so it can be cached."""
        p = self.params
        x = Tensor(np.asarray(ctx)[:, None, :])
        h = ag.relu(ag.add(ag.matmul(x, p["c1"]), p["cb1"]))
        return ag.add(ag.matmul(h, p["c2"]), p["cb2"])

    def encode_options(self, opts) -> Tensor:
        p = self.params
        x = Tensor(np.asarray(opts))
        h = ag.relu(ag.add(ag.matmul(x, p["e1"]), p["eb1"]))
        return ag.add(ag.matmul(h, p["e2"]), p["eb2"])

    # ---- scoring --------------------------------------------------------------
    def correct(self, c: Tensor, E: Tensor, mask) -> Tensor:
        return c

    def score(self, c0: Tensor, E: Tensor, mask) -> Tensor:
        """Logits [B, N] from the cached context embedding and the option embeddings."""
        c = self.correct(c0, E, mask)
        return _dot(E, c)

    def logits(self, ctx, opts, mask) -> Tensor:
        return self.score(self.encode_context(ctx), self.encode_options(opts), mask)

    def predict_proba(self, c0: Tensor, opts, mask) -> np.ndarray:
        with ag.no_grad():
            lg = self.score(c0, self.encode_options(opts), mask)
            return ag.softmax(lg, mask).data

    def predict(self, ctx, opts, mask) -> np.ndarray:
        with ag.no_grad():
            return self.predict_proba(self.encode_context(ctx), opts, mask)

    def n_params(self) -> int:
        return int(sum(p.data.size for p in self.params.values()))

    # ---- compute accounting (multiply-adds x2, per example) -------------------
    def flops_context(self) -> int:
        return 2 * (self.n_ctx * self.ctx_hidden + self.ctx_hidden * self.d)

    def flops_question(self, n_options: int) -> int:
        enc = 2 * (self.n_opt * self.opt_hidden + self.opt_hidden * self.d) * n_options
        return enc + 2 * self.d * n_options + self._flops_correction(n_options)

    def _flops_correction(self, n_options: int) -> int:
        return 0

    def flops_first(self, n_options: int) -> int:
        return self.flops_context() + self.flops_question(n_options)

    def flops_second(self, n_options: int) -> int:
        return self.flops_question(n_options)  # context embedding reused


def _dot(E: Tensor, c: Tensor) -> Tensor:
    """<c, e_i> for all i: E [B,N,d] x c [B,1,d] -> [B,N]."""
    out = ag.matmul(E, ag.transpose(c))  # [B,N,1]
    return _squeeze_last(out)


def _squeeze_last(t: Tensor) -> Tensor:
    return ag._make(t.data[..., 0], (t,), lambda g: t._acc(g[..., None]))


class CorrectionModel(DotProductModel):
    """Dot-product model plus attention-based correction blocks (see module docstring)."""

    def __init__(self, n_layers=2, **kw):
        self.n_layers = n_layers
        super().__init__(**kw)

    def _build(self, rng):
        d = self.d
        for l in range(self.n_layers):
            for name in ("Wq", "Wk", "Wv", "Wo"):
                self.params[f"{name}{l}"] = _init(rng, d, d)
            self.params[f"Wo{l}"].data *= 0.5  # start close to the baseline

    def correct(self, c: Tensor, E: Tensor, mask) -> Tensor:
        p, d = self.params, self.d
        m = np.asarray(mask)[:, None, :]
        for l in range(self.n_layers):
            q = ag.matmul(c, p[f"Wq{l}"])                      # [B,1,d]
            K = ag.matmul(E, p[f"Wk{l}"])                      # [B,N,d]
            V = ag.matmul(E, p[f"Wv{l}"])
            att = ag.softmax(ag.scale(ag.matmul(q, ag.transpose(K)), d ** -0.5), m)  # [B,1,N]
            delta = ag.matmul(ag.matmul(att, V), p[f"Wo{l}"])  # [B,1,d]
            c = ag.add(c, delta)                              # residual correction
        return c

    def _flops_correction(self, n_options: int) -> int:
        d, n = self.d, n_options
        per_layer = 2 * (d * d + 2 * n * d * d + n * d + n * d + d * d)  # q, K, V, scores, att@V, Wo
        return self.n_layers * per_layer

"""Minimal reverse-mode autograd on numpy arrays (torch is not available here).

Only the handful of ops the decision models need. Gradients are checked against
finite differences in tests/test_decision_model.py.
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np

_GRAD = True


@contextmanager
def no_grad():
    global _GRAD
    old, _GRAD = _GRAD, False
    try:
        yield
    finally:
        _GRAD = old


def _unbroadcast(g: np.ndarray, shape: tuple) -> np.ndarray:
    while g.ndim > len(shape):
        g = g.sum(axis=0)
    for i, s in enumerate(shape):
        if s == 1 and g.shape[i] != 1:
            g = g.sum(axis=i, keepdims=True)
    return g


class Tensor:
    def __init__(self, data, requires_grad: bool = False, parents=(), backward=None):
        self.data = np.asarray(data, dtype=np.float64)
        self.requires_grad = requires_grad
        self.grad = None
        self._parents = parents
        self._backward = backward

    @property
    def shape(self):
        return self.data.shape

    def _acc(self, g):
        self.grad = g if self.grad is None else self.grad + g

    def backward(self):
        order, seen = [], set()

        def visit(t):
            if id(t) in seen:
                return
            seen.add(id(t))
            for p in t._parents:
                visit(p)
            order.append(t)

        visit(self)
        self.grad = np.ones_like(self.data)
        for t in reversed(order):
            if t._backward is not None and t.grad is not None:
                t._backward(t.grad)


def _make(data, parents, backward) -> Tensor:
    if _GRAD and any(p.requires_grad for p in parents):
        return Tensor(data, True, parents, backward)
    return Tensor(data)


def add(a: Tensor, b: Tensor) -> Tensor:
    def bw(g):
        if a.requires_grad:
            a._acc(_unbroadcast(g, a.shape))
        if b.requires_grad:
            b._acc(_unbroadcast(g, b.shape))

    return _make(a.data + b.data, (a, b), bw)


def matmul(a: Tensor, b: Tensor) -> Tensor:
    def bw(g):
        if a.requires_grad:
            a._acc(_unbroadcast(g @ np.swapaxes(b.data, -1, -2), a.shape))
        if b.requires_grad:
            b._acc(_unbroadcast(np.swapaxes(a.data, -1, -2) @ g, b.shape))

    return _make(a.data @ b.data, (a, b), bw)


def relu(a: Tensor) -> Tensor:
    m = a.data > 0
    return _make(a.data * m, (a,), lambda g: a._acc(g * m))


def transpose(a: Tensor) -> Tensor:
    return _make(np.swapaxes(a.data, -1, -2), (a,), lambda g: a._acc(np.swapaxes(g, -1, -2)))


def scale(a: Tensor, s: float) -> Tensor:
    return _make(a.data * s, (a,), lambda g: a._acc(g * s))


def softmax(a: Tensor, mask: np.ndarray | None = None) -> Tensor:
    """Softmax over the last axis; masked-out (False) entries get probability 0."""
    x = a.data if mask is None else np.where(mask, a.data, -1e9)
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    if mask is not None:
        e = e * mask
    p = e / e.sum(axis=-1, keepdims=True)

    def bw(g):
        a._acc(p * (g - (g * p).sum(axis=-1, keepdims=True)))

    return _make(p, (a,), bw)


def cross_entropy(logits: Tensor, mask: np.ndarray, target: np.ndarray) -> Tensor:
    """Mean negative log-likelihood of `target` under masked softmax(logits). logits [B,N]."""
    x = np.where(mask, logits.data, -1e9)
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x) * mask
    p = e / e.sum(axis=-1, keepdims=True)
    B = len(target)
    idx = np.arange(B)
    loss = -np.log(p[idx, target] + 1e-12).mean()

    def bw(g):
        d = p.copy()
        d[idx, target] -= 1.0
        logits._acc(g * d * mask / B)

    return _make(loss, (logits,), bw)


def chosen_mse(logits: Tensor, idx: np.ndarray, target: np.ndarray) -> Tensor:
    """Mean squared error between the logit of the option actually taken (idx) and its
    observed outcome (target). Used to regress per-option value from logged choices
    (contextual bandit, direct method); options not taken get no gradient."""
    B = len(idx)
    rows = np.arange(B)
    err = logits.data[rows, idx] - target
    loss = float((err ** 2).mean())

    def bw(g):
        d = np.zeros_like(logits.data)
        d[rows, idx] = 2.0 * err / B
        logits._acc(g * d)

    return _make(loss, (logits,), bw)


class Adam:
    def __init__(self, params: dict[str, Tensor], lr=3e-3, b1=0.9, b2=0.999, eps=1e-8):
        self.p, self.lr, self.b1, self.b2, self.eps, self.t = params, lr, b1, b2, eps, 0
        self.m = {k: np.zeros_like(v.data) for k, v in params.items()}
        self.v = {k: np.zeros_like(v.data) for k, v in params.items()}

    def step(self):
        self.t += 1
        for k, p in self.p.items():
            if p.grad is None:
                continue
            self.m[k] = self.b1 * self.m[k] + (1 - self.b1) * p.grad
            self.v[k] = self.b2 * self.v[k] + (1 - self.b2) * p.grad**2
            mh = self.m[k] / (1 - self.b1**self.t)
            vh = self.v[k] / (1 - self.b2**self.t)
            p.data = p.data - self.lr * mh / (np.sqrt(vh) + self.eps)
            p.grad = None

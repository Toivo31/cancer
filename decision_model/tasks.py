"""D2: (a) synthetic comparison task, (b) RunLog -> imitation examples adapter."""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .features import (CONTEXT_TESTS, DEFAULT_NODE_TO_TEST, DEFAULT_TEST_TABLE, N_CONTEXT, N_OPTION,
                       context_vector, option_vector)

MAX_OPTIONS = 6


@dataclass
class Dataset:
    ctx: np.ndarray    # [n, N_CONTEXT]
    opts: np.ndarray   # [n, MAX_OPTIONS, N_OPTION]
    mask: np.ndarray   # [n, MAX_OPTIONS] bool
    y: np.ndarray      # [n] index of the chosen option

    def __len__(self):
        return len(self.y)

    def split(self, frac_train: float, seed: int = 0):
        idx = np.random.default_rng(seed).permutation(len(self))
        k = int(frac_train * len(self))
        take = lambda i: Dataset(self.ctx[i], self.opts[i], self.mask[i], self.y[i])
        return take(idx[:k]), take(idx[k:])


def comparison_label(ctx, opts, mask, relative: bool = True) -> np.ndarray:
    """The 'right' next test.

    Context-dependent value: with no positive finding yet we want sensitivity (rule
    disease in); after a positive finding we want specificity (confirm). Waiting is
    penalised more the longer the patient has already waited; invasive tests are
    penalised for older and non-specific-symptom patients.
    Set-relative rule (relative=True): only options at least as informative
    (sens + spec) as the AVERAGE of the options offered are eligible. A per-option
    scorer cannot compute that average; a model that sees the whole set can.
    """
    age, nonspec, elapsed = ctx[:, 0:1], ctx[:, 1:2], ctx[:, 2:3]
    pos = ctx[:, 3::2].max(axis=1, keepdims=True)
    sens, spec, wait, inv, cost = (opts[..., i] for i in range(5))
    value = (1 - pos) * sens + pos * spec
    lam = 0.4 + 2.0 * elapsed
    u = value / (1 + lam * wait) - inv * (0.25 * (age > 0.7) + 0.15 * nonspec) - 0.05 * cost
    if relative:
        info = sens + spec
        mean_info = (info * mask).sum(1, keepdims=True) / mask.sum(1, keepdims=True)
        u = np.where(info >= mean_info - 1e-12, u, -1e9)
    u = np.where(mask, u, -1e9)
    return u.argmax(axis=1)


def make_comparison_task(n: int, seed: int = 0, relative: bool = True) -> Dataset:
    rng = np.random.default_rng(seed)
    ctx = np.zeros((n, N_CONTEXT))
    for i in range(n):
        status = {}
        for t in CONTEXT_TESTS:
            r = rng.random()
            status[t] = None if r < 0.55 else (1 if r < 0.70 else 0)
        ctx[i] = context_vector(int(rng.integers(30, 90)), rng.random() < 0.4, rng.uniform(0, 70), status)
    opts = np.zeros((n, MAX_OPTIONS, N_OPTION))
    opts[..., 0] = rng.uniform(0.5, 0.98, (n, MAX_OPTIONS))
    opts[..., 1] = rng.uniform(0.5, 0.99, (n, MAX_OPTIONS))
    opts[..., 2] = rng.uniform(1, 40, (n, MAX_OPTIONS)) / 30.0
    opts[..., 3] = rng.random((n, MAX_OPTIONS)) < 0.3
    opts[..., 4] = rng.uniform(0.05, 2.0, (n, MAX_OPTIONS))
    sizes = rng.integers(3, MAX_OPTIONS + 1, n)
    mask = np.arange(MAX_OPTIONS)[None, :] < sizes[:, None]
    opts = opts * mask[..., None]
    return Dataset(ctx, opts, mask, comparison_label(ctx, opts, mask, relative))


# ---------------------------------------------------------------- RunLog adapter (retired)
# Deprecated (ticket M6-2): decisions of a run are dataset rows now (``jev.dataset.rows_from_log`` or
# ``GET /runs/{r}/decisions``), read back by ``jev.Dataset``, and the numpy model is trained from them by
# ``jev.train("local", ...)``. This adapter reads the old contract RunLog format and guesses the context from
# events; it stays only so ``ModelPolicy.train_on_runlog`` and its fixture keep working.
def runlog_to_examples(runlog: dict | str, choice_nodes: dict[str, list[str]],
                       test_table: dict | None = None, node_to_test: dict[str, str] | None = None,
                       ages: dict[int, int] | None = None) -> Dataset:
    """Turn a RunLog (contract format) into imitation examples.

    choice_nodes: choice node id -> its option node ids (the RunLog does not store the
    flowchart, so the caller supplies it). For each patient and choice node, the chosen
    option is the option node with the earliest event; the context is built from the
    events of OTHER nodes that had a result by the moment the chosen step became ready.
    A retry fallback (e.g. bronch nondiagnostic -> ttnb) is not a second choice.
    test_table: option/test id -> {sens, spec, wait_days, invasive, cost_eur}.
    node_to_test: node id -> test id for the history (defaults to the event's `test`).
    Hidden fields (condition, cancer) are never read.
    """
    import warnings
    warnings.warn("runlog_to_examples is retired: use jev.dataset rows and jev.train('local', ...) (spec 06)", DeprecationWarning, stacklevel=2)
    if isinstance(runlog, str):
        with open(runlog) as f:
            runlog = json.load(f)
    table = test_table or DEFAULT_TEST_TABLE
    node_to_test = DEFAULT_NODE_TO_TEST if node_to_test is None else node_to_test
    ctxs, optss, masks, ys = [], [], [], []
    for p in runlog["patients"]:
        events = sorted(p.get("events", []), key=lambda e: e["t_ready"])
        for node, options in choice_nodes.items():
            chosen = [e for e in events if e["node"] in options]
            if not chosen:
                continue
            ev = chosen[0]
            t_dec = ev["t_ready"]
            status = {}
            for e in events:
                if e["node"] in options or e["t_result"] > t_dec or e.get("result") is None:
                    continue
                status[e["test"]] = bool(e["result"])
            age = (ages or {}).get(p["id"], p.get("age"))
            ctxs.append(context_vector(age, p["group"] == "non_specific", t_dec - p["arrival"], status))
            o = np.zeros((MAX_OPTIONS, N_OPTION))
            for j, nid in enumerate(options[:MAX_OPTIONS]):
                tid = node_to_test.get(nid, nid)
                o[j] = option_vector(table[tid])
            optss.append(o)
            masks.append(np.arange(MAX_OPTIONS) < len(options))
            ys.append(options.index(ev["node"]))
    if not ys:
        return Dataset(np.zeros((0, N_CONTEXT)), np.zeros((0, MAX_OPTIONS, N_OPTION)),
                       np.zeros((0, MAX_OPTIONS), bool), np.zeros(0, int))
    return Dataset(np.array(ctxs), np.array(optss), np.array(masks), np.array(ys))

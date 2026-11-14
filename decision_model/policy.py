"""D4: ModelPolicy implementing the `Policy` contract (docs/architecture.md).

    policy.choose(view, options) -> {option_id: probability}

Reads only revealed information from the view: group, age, history [(node_id, test_id,
result, t)], t_now (and `arrival` if the view exposes it). It never touches `condition`
or `cancer`. `options` are node ids; `test_table` maps option node id (or the id given by
`node_to_test`) to test attributes {sens, spec, wait_days, invasive, cost_eur}.
Days elapsed = t_now - view.arrival when the view has `arrival`, else t_now minus the
earliest history time; this must match how the model was trained (see tasks.py).
With ``elapsed="t_now"`` the view's ``t_now`` is used directly (pathway_sim's PatientView
already measures it from the patient's clock start).

In-loop use (decision_model/in_loop.py): ``attr_vocab`` appends a one-hot block over the
view's *revealed* attributes (``view.attributes``; pathway_sim only puts revealed ones there),
and ``option_vectors`` (option node id -> feature vector) replaces the test-table lookup.
"""
from __future__ import annotations

import numpy as np

from .features import DEFAULT_NODE_TO_TEST, DEFAULT_TEST_TABLE, AttrVocab, context_vector, option_vector
from .models import CorrectionModel
from .tasks import MAX_OPTIONS, runlog_to_examples
from .train import fit


def _get(view, name, default=None):
    if isinstance(view, dict):
        return view.get(name, default)
    return getattr(view, name, default)


class ModelPolicy:
    def __init__(self, model=None, test_table=None, node_to_test=None, attr_vocab: AttrVocab | None = None,
                 option_vectors: dict | None = None, elapsed: str = "auto", extra_context=None):
        self.model = model if model is not None else CorrectionModel(n_layers=2, seed=0)
        self.test_table = test_table or DEFAULT_TEST_TABLE
        self.node_to_test = DEFAULT_NODE_TO_TEST if node_to_test is None else node_to_test
        self.attr_vocab = attr_vocab
        self.option_vectors = option_vectors
        self.elapsed = elapsed
        self.extra_context = extra_context  # optional callable(view) -> array appended to the context
        self.n_fallbacks = 0
        self._cache: dict = {}  # context key -> cached context embedding

    def context_array(self, view) -> np.ndarray:
        history = list(_get(view, "history", []) or [])
        status = {}
        for _node, test, result, _t in sorted(history, key=lambda h: h[3]):
            if result is None:
                status.pop(test, None)
            else:
                status[test] = bool(result)
        t_now = float(_get(view, "t_now", 0.0) or 0.0)
        if self.elapsed == "t_now":
            arrival = 0.0
        else:
            arrival = _get(view, "arrival")
            if arrival is None:
                arrival = min((h[3] for h in history), default=t_now)
        attrs = _get(view, "attributes") if self.attr_vocab is not None else None
        v = context_vector(_get(view, "age"), _get(view, "group") == "non_specific",
                           t_now - arrival, status, attrs, self.attr_vocab)
        if self.extra_context is not None:
            v = np.concatenate([v, np.asarray(self.extra_context(view), float)])
        return v

    def option_rows(self, options: list[str]) -> list[np.ndarray]:
        """Raises KeyError for an option without features. ``option_vectors`` may be a dict
        (static per option) or a callable(view, options) -> rows (per-decision features)."""
        if callable(self.option_vectors):
            return [np.asarray(x, float) for x in self.option_vectors(self._view, options)]
        if self.option_vectors is not None:
            return [np.asarray(self.option_vectors[o], float) for o in options]
        return [option_vector(self.test_table[self.node_to_test.get(o, o)]) for o in options]

    def choose(self, view, options: list[str]) -> dict[str, float]:
        uniform = {o: 1.0 / len(options) for o in options}
        if len(options) > MAX_OPTIONS:
            self.n_fallbacks += 1
            return uniform
        self._view = view
        try:
            rows = self.option_rows(options)
        except KeyError:
            self.n_fallbacks += 1  # unknown test attributes: no information, stay uniform
            return uniform
        ctx = self.context_array(view)
        key = ctx.tobytes()
        if key not in self._cache:  # second question on the same context reuses the embedding
            self._cache[key] = self.model.encode_context(ctx[None])
            if len(self._cache) > 4096:
                self._cache.pop(next(iter(self._cache)))
        o = np.zeros((1, MAX_OPTIONS, self.model.n_opt))
        o[0, :len(options)] = rows
        mask = (np.arange(MAX_OPTIONS) < len(options))[None]
        p = self.model.predict_proba(self._cache[key], o, mask)[0, :len(options)]
        return {opt: float(x) for opt, x in zip(options, p)}

    def train_on_runlog(self, runlog, choice_nodes, epochs=30, seed=0):
        """Imitate the choices logged in a RunLog (e.g. produced by the rule policy)."""
        ds = runlog_to_examples(runlog, choice_nodes, self.test_table, self.node_to_test)
        if len(ds):
            fit(self.model, ds, epochs=epochs, batch=min(64, len(ds)), seed=seed)
            self._cache.clear()
        return len(ds)

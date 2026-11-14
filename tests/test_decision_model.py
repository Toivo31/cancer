import json
import pathlib

import numpy as np

from decision_model import autograd as ag
from decision_model.models import CorrectionModel, DotProductModel
from decision_model.policy import ModelPolicy
from decision_model.tasks import MAX_OPTIONS, make_comparison_task, runlog_to_examples
from decision_model.train import evaluate, fit

FIX = pathlib.Path(__file__).parent / "fixtures" / "runlog_small.json"
CHOICE = {"sample": ["bronch", "ttnb"]}


def test_gradients_match_finite_differences():
    ds = make_comparison_task(6, seed=3)
    m = CorrectionModel(n_layers=2, d=8, ctx_hidden=8, opt_hidden=8, seed=1)

    def loss():
        return ag.cross_entropy(m.logits(ds.ctx, ds.opts, ds.mask), ds.mask, ds.y)

    for p in m.params.values():
        p.grad = None
    loss().backward()
    rng = np.random.default_rng(0)
    for name in ("c1", "e2", "Wq0", "Wk1", "Wv0", "Wo1"):
        p = m.params[name]
        for _ in range(3):
            idx = tuple(rng.integers(0, s) for s in p.data.shape)
            old = p.data[idx]
            g = p.grad[idx]
            p.data[idx] = old + 1e-5
            lp = float(loss().data)
            p.data[idx] = old - 1e-5
            lm = float(loss().data)
            p.data[idx] = old
            assert abs((lp - lm) / 2e-5 - g) < 1e-5 + 1e-3 * abs(g), name


def test_masked_options_get_zero_probability_and_probs_sum_to_one():
    ds = make_comparison_task(50, seed=1)
    for M in (DotProductModel, CorrectionModel):
        p = M(seed=0).predict(ds.ctx, ds.opts, ds.mask)
        assert np.allclose(p.sum(1), 1)
        assert (p[~ds.mask] == 0).all()


def test_cached_context_equals_uncached():
    ds = make_comparison_task(20, seed=2)
    m = CorrectionModel(seed=0)
    c0 = m.encode_context(ds.ctx)
    assert np.allclose(m.predict_proba(c0, ds.opts, ds.mask), m.predict(ds.ctx, ds.opts, ds.mask))
    assert m.flops_second(4) < m.flops_first(4)


def test_dot_product_cannot_see_other_options_but_correction_can():
    ds = make_comparison_task(5, seed=4)
    ctx, opts, mask = ds.ctx[:1], ds.opts[:1].copy(), ds.mask[:1].copy()
    other = opts.copy()
    other[0, 1] = [0.99, 0.99, 0.02, 0, 0.05]  # change a *different* option
    for M, same in ((DotProductModel, True), (CorrectionModel, False)):
        m = M(seed=5)
        if M is CorrectionModel:
            m.params["Wo0"].data *= 4  # make the effect clearly non-zero
        with ag.no_grad():
            E1 = m.encode_options(opts); E2 = m.encode_options(other)
            c0 = m.encode_context(ctx)
            l1 = m.score(c0, E1, mask).data[0, 0]
            l2 = m.score(c0, E2, mask).data[0, 0]
        assert (abs(l1 - l2) < 1e-12) == same


def test_training_beats_chance_and_correction_learns_comparison_task():
    tr, te = make_comparison_task(4000, seed=7).split(0.75)
    chance = float((1 / te.mask.sum(1)).mean())
    m = CorrectionModel(seed=0)
    fit(m, tr, epochs=6)
    assert evaluate(m, te)["acc"] > chance + 0.3


def test_adapter_on_fixture():
    ds = runlog_to_examples(str(FIX), CHOICE)
    rl = json.load(open(FIX))
    n_expected = sum(any(e["node"] in CHOICE["sample"] for e in p["events"]) for p in rl["patients"])
    assert len(ds) == n_expected == 6
    assert ds.opts.shape[1:] == (MAX_OPTIONS, 5)
    assert set(ds.y) <= {0, 1} and ds.mask.sum(1).tolist() == [2] * 6
    # patient 3: bronch nondiagnostic then ttnb fallback -> the choice is bronch, not ttnb
    assert ds.y[2] == 0
    # context holds the positive chest x-ray (pos column of chest_xray = index 3)
    assert (ds.ctx[:, 3] == 1).all()


def test_policy_contract_and_no_hidden_info():
    class View:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    base = dict(group="non_specific", age=70, history=[("cxr", "chest_xray", True, 4.0)], t_now=9.0, arrival=1.0)
    pol = ModelPolicy(CorrectionModel(seed=0))
    a = pol.choose(View(**base), ["bronch", "ttnb"])
    b = pol.choose(View(**base, condition="lung_cancer", cancer=True), ["bronch", "ttnb"])
    assert a == b and set(a) == {"bronch", "ttnb"} and abs(sum(a.values()) - 1) < 1e-9
    assert pol.choose(View(**base), ["bronch", "mystery_test"]) == {"bronch": 0.5, "mystery_test": 0.5}
    assert pol.n_fallbacks == 1


def test_policy_imitates_fixture_runlog():
    pol = ModelPolicy(CorrectionModel(seed=0))
    n = pol.train_on_runlog(str(FIX), CHOICE, epochs=40)
    assert n == 6

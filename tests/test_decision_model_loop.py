"""Decision model in the simulator loop (decision_model/in_loop.py). Small and fast (< 20 s)."""
import json
import pathlib

import numpy as np
import pytest

from decision_model import autograd as ag
from decision_model.features import N_CONTEXT, AttrVocab, context_vector
from decision_model.in_loop import (markdown, option_vectors, options_with_queue, outcome, run_experiment,
                                    sampling_tests, save)
from decision_model.models import CorrectionModel, DotProductModel
from decision_model.policy import ModelPolicy
from pathway_sim import PatientView, load_scenario

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOK = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"


def test_attribute_one_hot_unknown_is_zero_and_default_layout_unchanged():
    assert context_vector(70, True, 10, {}).shape == (N_CONTEXT,)
    voc = AttrVocab.from_attributes([{"location": "central"}, {"location": "peripheral", "ct_inadequate": "no"}])
    assert len(voc) == 3
    v = context_vector(70, True, 10, {}, {"location": "central"}, voc)
    assert v.shape == (N_CONTEXT + 3,) and v[N_CONTEXT:].sum() == 1
    assert v[N_CONTEXT + voc.index[("location", "central")]] == 1
    unseen = context_vector(70, True, 10, {}, {"location": "hilar", "other": "x"}, voc)
    assert (unseen[N_CONTEXT:] == 0).all()                       # unseen value / attribute -> unknown
    assert (context_vector(70, True, 10, {}, None, voc)[N_CONTEXT:] == 0).all()


def test_chosen_mse_gradient_matches_finite_differences():
    rng = np.random.default_rng(0)
    ctx, opts = rng.random((5, 7)), rng.random((5, 6, 4))
    mask = np.ones((5, 6), bool)
    idx, r = rng.integers(0, 6, 5), rng.normal(size=5)
    m = CorrectionModel(n_layers=1, d=8, ctx_hidden=8, opt_hidden=8, n_ctx=7, n_opt=4, seed=2)

    def loss():
        return ag.chosen_mse(m.logits(ctx, opts, mask), idx, r)

    loss().backward()
    for name in ("c1", "e2", "Wq0", "Wo0"):
        p = m.params[name]
        for _ in range(3):
            i = tuple(rng.integers(0, s) for s in p.data.shape)
            old, g = p.data[i], p.grad[i]
            p.data[i] = old + 1e-5
            lp = float(loss().data)
            p.data[i] = old - 1e-5
            lm = float(loss().data)
            p.data[i] = old
            assert abs((lp - lm) / 2e-5 - g) < 1e-6 + 1e-3 * abs(g), name


def test_model_policy_uses_revealed_attributes_only():
    voc = AttrVocab([("location", "central"), ("location", "peripheral")])
    ov = {"bronch1": np.array([1.0, 0, 1]), "ttnb1": np.array([0, 1.0, 1])}
    m = DotProductModel(n_ctx=N_CONTEXT + 2, n_opt=3, seed=3)
    pol = ModelPolicy(m, attr_vocab=voc, option_vectors=ov, elapsed="t_now")
    v_c = PatientView(1, "non_specific", 70, 12.0, "method", [("ct", "baseline_ct", True, 0.0)], {"location": "central"})
    v_p = PatientView(1, "non_specific", 70, 12.0, "method", [("ct", "baseline_ct", True, 0.0)], {"location": "peripheral"})
    a = pol.choose(v_c, ["bronch1", "ttnb1"])
    assert abs(sum(a.values()) - 1) < 1e-9
    assert a != pol.choose(v_p, ["bronch1", "ttnb1"])            # the revealed attribute is used
    v_c.condition, v_c.cancer, v_c.results = "lung_cancer", True, {"bronchoscopy": [None]}
    assert pol.choose(v_c, ["bronch1", "ttnb1"]) == a            # hidden fields are ignored
    assert pol.context_array(v_c)[2] == pytest.approx(12.0 / 60)  # elapsed = t_now


def test_outcome_and_option_features_use_public_information():
    sc = load_scenario(str(STOK))
    fc = sc.flowcharts["optimal"]
    assert "further_workup" in sampling_tests(sc)                 # invasive, but before the choice
    assert sampling_tests(sc, fc, "method") == {"bronchoscopy", "bronchoscopy_repeat", "ttnb"}
    fin = load_scenario(str(ROOT / "scenarios" / "finland_lung.yaml"))
    ffc = fin.flowcharts["baseline"]
    assert sampling_tests(fin, ffc, "sample_choice") == {"bronchoscopy", "ttnb"}
    assert options_with_queue(fin, ffc, "sample_choice") == ["bronch", "ttnb"]
    ov = option_vectors(sc, fc, "method")
    assert set(ov) == {"bronch1", "ttnb1"} and ov["bronch1"][0] == 1 and ov["ttnb1"][1] == 1
    assert options_with_queue(sc, fc, "method") == []              # Stokstad waits are delays, no booking book

    class E:
        def __init__(self, test, t_ready, t_result, result):
            self.test, self.t_ready, self.t_result, self.result = test, t_ready, t_result, result

    class P:
        arrival = 100.0

    class PR:
        patient = P()
        events = [E("pet_ct", 101, 103, True), E("bronchoscopy", 110, 118, None), E("ttnb", 118, 130, True)]

    diag, days = outcome(PR(), 10.0, {"bronchoscopy", "ttnb"})
    assert diag and days == pytest.approx(20.0)
    PR.events = PR.events[:2]
    assert outcome(PR(), 10.0, {"bronchoscopy", "ttnb"}) == (False, pytest.approx(8.0))


def test_in_loop_stokstad_small(tmp_path):
    res = run_experiment(STOK, "optimal", "method", n_train=3000, n_eval=400, train_seeds=(1001,), eval_seeds=(1,),
                         epochs=60, wd_grid=(0.3,), log=lambda *a: None)
    t = res["table"]
    assert set(t) == {"rule (hand-written)", "random", "dot-product", "correction (2 layers)"}
    sig = res["exploration_signal"]
    # the signal (random exploration, revealed outcomes) says bronchoscopy for central, needle biopsy for peripheral
    assert sig["central->bronch1"]["reward"] > sig["central->ttnb1"]["reward"]
    assert sig["peripheral->ttnb1"]["reward"] > sig["peripheral->bronch1"]["reward"]
    for name in ("dot-product", "correction (2 layers)"):
        assert t[name]["agreement_with_rule"] > 0.9
        assert t[name]["diagnostic_share_at_node"] > t["random"]["diagnostic_share_at_node"]
        lv = res["learned_values"][name]
        assert lv["central"]["bronch1"] > lv["central"]["ttnb1"] and lv["peripheral"]["ttnb1"] > lv["peripheral"]["bronch1"]
    assert t["rule (hand-written)"]["agreement_with_rule"] == 1.0
    out = tmp_path / "m.json"
    key = save(res, out)
    data = json.loads(out.read_text())
    assert key == "stokstad_calibrated/optimal/method" and "| dot-product |" in data[key]["markdown"]
    assert "Choices by revealed `location`" in markdown(res)

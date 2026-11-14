"""Open question 12 experiment (decision_model/comparison_experiment.py). Fast (< 20 s)."""
import pathlib

import numpy as np
import yaml

from decision_model import autograd as ag
from decision_model.comparison_experiment import EV, SCEN, ExpectedValueRule, run
from decision_model.in_loop import FeatureSet, option_vectors, options_with_queue
from decision_model.make_experiment_scenario import build
from decision_model.features import AttrVocab
from decision_model.models import CorrectionModel, DotProductModel
from pathway_sim import PatientView, load_scenario


def _view(loc, offered, leads):
    v = PatientView(1, "lung_referral", 70, 30.0, "method", [("ct", "baseline_ct", True, 0.0)], {"location": loc})
    v.offered, v.option_leads = list(offered), dict(leads)
    return v


def test_generated_scenario_is_up_to_date():
    on_disk = yaml.safe_load(pathlib.Path(SCEN).read_text())
    assert on_disk == yaml.safe_load(yaml.safe_dump(build(), sort_keys=False))


def test_expected_value_rule_best_pick_depends_on_another_options_queue():
    sc = load_scenario(str(SCEN))
    fc = sc.flowcharts["rescue_queue"]
    assert options_with_queue(sc, fc, "method") == ["ttnb1"]
    ev = ExpectedValueRule(sc, fc)
    opts = ["bronch1", "ebus1", "ttnb1"]
    short, long_ = _view("central", opts, {"ttnb1": 2.0}), _view("central", opts, {"ttnb1": 30.0})
    assert ev.value(short, "bronch1") > ev.value(long_, "bronch1")             # bronchoscopy's rescue waits in that queue
    assert ev.value(short, "ebus1") == ev.value(long_, "ebus1")                 # EBUS does not depend on it
    pick = lambda v, o: max(ev.choose(v, o).items(), key=lambda kv: kv[1])[0]
    assert pick(short, opts) == "bronch1" and pick(long_, opts) == "ebus1"      # the comparison flips
    # in the delay-only flowchart option values do not depend on the others
    ev2 = ExpectedValueRule(sc, sc.flowcharts["availability"])
    assert ev2.value(_view("central", opts, {}), "bronch1") == ev2.value(_view("central", ["bronch1"], {}), "bronch1")


def test_dot_product_cannot_see_another_options_lead_but_correction_and_set_summary_can():
    sc = load_scenario(str(SCEN))
    fc = sc.flowcharts["rescue_queue"]
    opts = list(fc.nodes["method"].options)
    vocab = AttrVocab([("location", "central"), ("location", "peripheral")])
    ov = option_vectors(sc, fc, "method")
    short, long_ = _view("central", opts, {"ttnb1": 2.0}), _view("central", opts, {"ttnb1": 30.0})
    for fs_name, M, sees in (("lead", DotProductModel, False), ("lead", CorrectionModel, True), ("lead+set", DotProductModel, True)):
        fs = FeatureSet(fs_name, vocab, ov, opts)
        n_ctx = len(fs.ctx.context_array(short))
        m = M(n_ctx=n_ctx, n_opt=len(fs.rows(short, opts)[0]), seed=3)
        if M is CorrectionModel:
            m.params["Wo0"].data *= 4
        pol = fs.policy(m)
        with ag.no_grad():
            s1 = pol.choose(short, opts)
            s2 = pol.choose(long_, opts)
        # the bronch1 vs ebus1 comparison (neither has a queue) changes only if the model can see ttnb1's lead
        r1, r2 = np.log(s1["bronch1"] / s1["ebus1"]), np.log(s2["bronch1"] / s2["ebus1"])
        assert (abs(r1 - r2) > 1e-9) == sees, (fs_name, M.__name__)


def test_comparison_experiment_quick(tmp_path):
    res, md = run("rescue_queue", quick=True, log=lambda *a: None, out=tmp_path / "m.json",
                  variants=[("dot-product + queue lead", "dot", "lead"),
                            ("dot-product + queue lead + set summary", "dot", "lead+set")])
    t = res["table"]
    assert set(t) == {"rule (hand-written)", "random", EV, "dot-product + queue lead", "dot-product + queue lead + set summary"}
    assert t[EV]["mean_reward_at_node"] > t["random"]["mean_reward_at_node"]
    assert t[EV]["agreement_with " + EV] == 1.0
    assert "Set-dependent cell" in md and "Paired model comparisons" in md
    assert (tmp_path / "m.json").exists()

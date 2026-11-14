"""M1-7: LocalBackend / RuleBackend; the in-loop decision-model setup through the contract gives unchanged results."""

import pathlib

import numpy as np

import jev
from decision_model.features import N_CONTEXT, AttrVocab
from decision_model.in_loop import NodePolicy, option_vectors
from decision_model.models import DotProductModel
from decision_model.policy import ModelPolicy
from pathway_sim import RandomPolicy, RulePolicy, compute_metrics, generate_patients, load_scenario, simulate

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOK = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"


def _setup():
    sc = load_scenario(str(STOK))
    fc = sc.flowcharts["optimal"]
    ov = option_vectors(sc, fc, "method")
    vocab = AttrVocab([("location", "central"), ("location", "peripheral")])
    model = DotProductModel(n_ctx=N_CONTEXT + 2, n_opt=len(next(iter(ov.values()))), seed=3)
    mk = lambda: ModelPolicy(model, attr_vocab=vocab, option_vectors=ov, elapsed="t_now")
    return sc, fc, mk


def _seq(run):
    return [[(c["node"], c["chosen"], c["offered"]) for c in p.choices] for p in run.patients]


def test_in_loop_node_policy_through_the_contract_is_unchanged():
    sc, fc, mk = _setup()
    pts = generate_patients(sc, 300, 11)
    old = simulate(sc, fc, pts, NodePolicy(RulePolicy(fc.policy, 11), "method", mk()), seed=11)
    be = jev.RoutingBackend(jev.RuleBackend(fc.policy, 11), {"method": jev.LocalBackend(mk(), "dot@1")})
    pol = jev.BackendPolicy(be, mode="argmax", scenario=sc, flowchart=fc)
    new = simulate(sc, fc, pts, pol, seed=11)
    assert _seq(new) == _seq(old)
    assert compute_metrics(new, sc) == compute_metrics(old, sc)
    ms = {(c["node"], c["backend"], c["model"]) for p in new.patients for c in p.choices if c["node"] == "method"}
    assert ms == {("method", "local", "dot@1")}
    assert {c["backend"] for p in new.patients for c in p.choices if c["node"] != "method"} == {"rule"}


def test_random_policy_and_rule_backend_through_the_contract():
    sc, fc, _ = _setup()
    pts = generate_patients(sc, 300, 12)
    old = simulate(sc, fc, pts, NodePolicy(RulePolicy(fc.policy, 12), "method", RandomPolicy(seed=12)), seed=12)
    be = jev.RoutingBackend(jev.RuleBackend(fc.policy, 12), {"method": jev.LocalBackend(RandomPolicy(seed=12))})
    new = simulate(sc, fc, pts, jev.BackendPolicy(be, mode="argmax"), seed=12)
    assert _seq(new) == _seq(old)
    # RuleBackend alone equals the legacy default
    legacy = simulate(sc, fc, pts, seed=12)
    rb = simulate(sc, fc, pts, jev.BackendPolicy(jev.RuleBackend(fc.policy, 12), mode="argmax"), seed=12)
    assert _seq(rb) == _seq(legacy)


def test_view_round_trip_keeps_what_the_model_reads():
    sc, fc, mk = _setup()
    seen = []

    class Spy(ModelPolicy):
        def choose(self, view, options):
            seen.append(view)
            return super().choose(view, options)

    pts = generate_patients(sc, 50, 13)
    spy = mk()
    spy.__class__ = Spy
    direct = []

    class Cap(NodePolicy):
        def choose(self, view, options):
            if view.node == self.node:
                direct.append(view)
            return super().choose(view, options)

    simulate(sc, fc, pts, Cap(RulePolicy(fc.policy, 13), "method", mk()), seed=13)
    be = jev.RoutingBackend(jev.RuleBackend(fc.policy, 13), {"method": jev.LocalBackend(spy)})
    simulate(sc, fc, pts, jev.BackendPolicy(be, mode="argmax", scenario=sc, flowchart=fc), seed=13)
    assert len(seen) == len(direct) > 0
    for a, b in zip(seen, direct):
        assert (a.patient_id, a.group, a.age, a.node, a.history, a.attributes, a.priority, a.offered, a.option_leads) == \
               (b.patient_id, b.group, b.age, b.node, b.history, b.attributes, b.priority, b.offered, b.option_leads)
        assert a.t_now == b.t_now

"""The optimiser must find the same changes through the stub backend as through the rule policy.

Cause of the gap this guards against: ``standardise`` wrote only the legacy ``policy`` block, but the stub reads its
table (``decision_policy.points``), which takes precedence in ``jev.migrate_flowchart``, so the edit changed nothing
under the stub and was never accepted. Shipped scenarios give identical metrics through the stub, so the accepted
change list and the held-out numbers must be identical too."""

import collections

import pytest

import jev
from optimiser import Config, search
from optimiser.edits import Edit, apply, candidates
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate
from pathway_sim.documents import documents_to_scenario, scenario_to_documents


@pytest.fixture(scope="module")
def norway():
    sc = load_scenario("scenarios/stokstad.yaml")        # the file behind the norway_check template
    world, fcs = scenario_to_documents(sc)               # stub tables by default, as the service stores them
    doc = next(f for f in fcs if f["id"] == "observed")
    assert doc["decision_policy"]["backend"] == "stub"
    sc_stub = documents_to_scenario(world, [doc])
    return sc, sc_stub


def test_same_changes_and_heldout_numbers_under_rule_and_stub(norway):
    sc, sc_stub = norway
    cfg = Config(n_train=150, n_heldout=150, heldout_seeds=(301,), max_steps=3, allow=("detach", "relax", "standardise"))
    rule = search(sc, "observed", cfg, log=lambda *a: None)
    stub = search(sc_stub, "observed", cfg, log=lambda *a: None, policy_factory=lambda fc, seed: jev.prepare(sc_stub, fc, seed=seed))
    key = lambda r: [(s["kind"], s["target"], s["other"]) for s in r["steps"]]       # noqa: E731
    assert key(rule) == key(stub) and len(key(rule)) >= 2
    assert any(k[0] == "standardise" for k in key(stub))
    for part in ("before", "after"):
        assert stub["heldout"][part]["share_within_target"] == rule["heldout"][part]["share_within_target"]
        assert stub["heldout"][part]["median_days_to_treatment"] == rule["heldout"][part]["median_days_to_treatment"]
    assert [(r["kind"], r["target"], r["other"]) for r in stub["rejected_by_guardrails"]] == \
           [(r["kind"], r["target"], r["other"]) for r in rule["rejected_by_guardrails"]]


def test_standardise_changes_what_the_stub_chooses(norway):
    _, sc_stub = norway
    fc = sc_stub.flowcharts["observed"]
    new = apply(sc_stub, fc, Edit("standardise", "pet_timing", "pet_on_time"))
    assert new.decision_policy["points"]["pet_timing"]["default"] == {"pet_on_time": 1.0, "pet_late": 0.0}
    assert fc.decision_policy["points"]["pet_timing"]["default"]["pet_late"] > 0     # the parent is untouched
    pts = generate_patients(sc_stub, 300, 5)

    def chosen(f):
        f2, pol = jev.prepare(sc_stub, f, seed=5)
        log = simulate(sc_stub, f2, pts, policy=pol, seed=5)
        return collections.Counter(c["chosen"] for pr in log.patients for c in pr.choices if c["node"] == "pet_timing")
    assert set(chosen(new)) == {"pet_on_time"} and set(chosen(fc)) == {"pet_on_time", "pet_late"}


def test_an_already_standard_decision_is_not_proposed_again(norway):
    _, sc_stub = norway
    fc = apply(sc_stub, sc_stub.flowcharts["observed"], Edit("standardise", "pet_timing", "pet_on_time"))
    again = [(e.target, e.other) for e in candidates(sc_stub, fc, {"standardise"})]
    assert ("pet_timing", "pet_on_time") not in again and ("pet_timing", "pet_late") in again

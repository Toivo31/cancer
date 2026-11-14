"""apply_changes (subset, linked changes) and the optimisation report (spec 05)."""

import pytest

from optimiser import ChangeError, Config, apply_changes, search
from optimiser.apply import linked_groups
from optimiser.report import build_report
from pathway_sim import load_scenario


@pytest.fixture(scope="module")
def found():
    sc = load_scenario("scenarios/generated/stokstad_calibrated.yaml")
    cfg = Config(n_train=150, n_heldout=150, heldout_seeds=(301,), max_steps=3, allow=("detach", "relax", "standardise"))
    seen = []
    res = search(sc, "observed", cfg, log=lambda *a: None, progress=lambda d, t, m: seen.append((d, t)))
    assert len(res["steps"]) >= 2
    assert seen and seen[-1][0] < seen[-1][1]
    return sc, res


def test_apply_all_equals_optimiser_output(found):
    sc, res = found
    fc = apply_changes(sc, sc.flowcharts["observed"], res["steps"], new_id=res["flowchart_after"]["id"])
    assert fc.to_dict() == res["flowchart_after"]


def test_apply_subset_and_none(found):
    sc, res = found
    base = sc.flowcharts["observed"]
    none = apply_changes(sc, base, res["steps"], accept=[])
    assert [n.to_dict() for n in none.nodes.values()] == [n.to_dict() for n in base.nodes.values()]
    one = apply_changes(sc, base, res["steps"], accept=[0])
    assert one.to_dict() != none.to_dict()
    assert one.to_dict() != apply_changes(sc, base, res["steps"], new_id="x").to_dict() or len(res["steps"]) == 1


def test_unknown_change_refused(found):
    sc, res = found
    with pytest.raises(ChangeError) as e:
        apply_changes(sc, sc.flowcharts["observed"], res["steps"], accept=[99])
    assert e.value.code == "unknown_change"


def test_linked_changes_must_travel_together(found):
    sc, res = found
    steps = [dict(s, evidence=dict(s["evidence"])) for s in res["steps"]]
    steps[0]["evidence"]["accepted_together_with"] = [steps[1]["plain"]]
    steps[1]["evidence"]["accepted_together_with"] = [steps[0]["plain"]]
    assert [0, 1] in linked_groups(steps)
    with pytest.raises(ChangeError) as e:
        apply_changes(sc, sc.flowcharts["observed"], steps, accept=[0])
    assert e.value.code == "linked_change" and e.value.needs == [1]
    both = apply_changes(sc, sc.flowcharts["observed"], steps, accept=[0, 1])
    assert both.to_dict()["nodes"] == apply_changes(sc, sc.flowcharts["observed"], steps, accept=[0, 1]).to_dict()["nodes"]


def test_report_has_labels_evidence_and_unseen_numbers(found):
    sc, res = found
    rep = build_report(sc, sc.flowcharts["observed"], res)
    assert len(rep["changes"]) == len(res["steps"])
    c = rep["changes"][0]
    assert c["label"] and c["records_reading"] and c["train"]["on_time_after"] is not None
    assert c["heldout_after_this_change"]["on_time"] is not None
    assert rep["changes"][-1]["heldout_after_this_change"]["on_time"] == res["heldout"]["after"]["share_within_target"]
    assert "never saw" in rep["honesty"]
    for b in rep["blocked"]:
        assert b["label"] and b["blocked_by"]

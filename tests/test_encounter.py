"""Encounter loop (WP-C8-1): information boundary, loop, treatment, hand-over, determinism, CLI."""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import pytest

from patient_engine.card import HIDDEN_FIELD_NAMES, Card
from patient_engine.cohort import Cohort
from patient_engine.record import Record
from patient_engine.reveal import RevealHandle
from pathway_sim.encounter import (
    EncounterTablePolicy, compile_when, hospital_subflowchart, load_world, outcomes, record_names, run_encounter,
    undot, world_library,
)
from pathway_sim.policy import PatientView

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "scenarios" / "finland_encounter.yaml"


@pytest.fixture(scope="module")
def base_world():
    return load_world(WORLD)


def variant(world, **raw):
    """A copy of ``world`` with top-level raw settings replaced (small library by default)."""
    w = copy.copy(world)
    w.raw = copy.deepcopy(world.raw)
    w.raw["library"] = {"per_condition": 6, "seed": 3}
    w.raw.update(raw)
    return w


class Script:
    """A policy that picks one action from a function of the record names."""
    backend_name = "script"

    def __init__(self, fn):
        self.fn, self.views = fn, []

    def choose(self, view, options):
        self.views.append(view)
        role = view.node[: -len("_encounter")]
        pick = self.fn(role, record_names(view.record))
        assert pick in options, (pick, options)
        return {o: float(o == pick) for o in options}


# ---------------------------------------------------------------------------- format

def test_policy_table_matches_care(base_world):
    assert base_world.policy.problems(base_world.care) == []
    assert set(base_world.policy.points) == {f"{r}_encounter" for r in base_world.care.roles}


def test_undot_keeps_quoted_text_and_numbers():
    assert undot("found.cough and reason == 'a.b' and x > 0.5") == "found__cough and reason == 'a.b' and x > 0.5"
    assert undot("last.chest_xray.abnormal is False") == "last__chest_xray__abnormal is False"
    assert compile_when("attempts.chest_xray == 0").names == frozenset({"attempts__chest_xray"})


def test_bad_table_is_refused():
    with pytest.raises(ValueError):
        EncounterTablePolicy({"gp_encounter": {"default": {"a": 1}, "rules": [{"when": "open('x')", "probs": {"a": 1}}]}})
    with pytest.raises(ValueError):
        EncounterTablePolicy({"gp_encounter": {"default": {"a": -1}}})


def test_record_names_from_record_only():
    from patient_engine.record import Entry, Observation
    r = Record("P000001", {"age": 70, "sex": "f"})
    r.append(Entry(0, 1, "encounter", encounter=1, role="gp", found={"cough": True}, action="order_chest_xray"))
    r.append(Entry(3, 1, "result", encounter=1, role="gp",
                   observations=(Observation("chest_xray", 1, "ok", {"abnormal": False}, "", False),)))
    r.append(Entry(4, 1, "encounter", encounter=2, role="gp", found={"cough": True}))
    n = record_names(r)
    assert n["reason"] == "result" and n["last_action"] == "order_chest_xray"
    assert n["found__cough"] is True and n["last__chest_xray__abnormal"] is False
    assert n["last__chest_xray__days"] == 1 and n.get("attempts__chest_xray") == 1
    assert n.get("attempts__ct") == 0 and n.get("found__nothing") is None
    assert n["encounters"] == 2 and n["role_encounters"] == 2 and n["age"] == 70
    assert compile_when("reason == 'result' and last.chest_xray.abnormal is False").holds(n)


def test_hospital_subflowchart_starts_at_referral(base_world):
    fc = base_world.flowchart
    entry = fc.nodes["referral_in"]
    assert not entry.after and not entry.after_optional and entry.when is None
    assert "first_contact" not in fc.nodes and "treat" in fc.nodes and "sample_choice" in fc.policy
    with pytest.raises(ValueError):
        hospital_subflowchart(base_world.scenario.flowcharts["baseline"], "no_such_node")


# ---------------------------------------------------------------------------- I1

def _walk(x, seen, out):
    if id(x) in seen:
        return
    seen.add(id(x))
    assert not isinstance(x, (Card, RevealHandle, Cohort)), f"hidden object reached the policy: {type(x)}"
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        for f in dataclasses.fields(x):
            assert f.name not in HIDDEN_FIELD_NAMES, f.name
            _walk(getattr(x, f.name), seen, out)
    elif isinstance(x, dict):
        for k, v in x.items():
            assert k not in HIDDEN_FIELD_NAMES, k
            out.add(k) if isinstance(k, str) else None
            _walk(v, seen, out)
    elif isinstance(x, (list, tuple, set, frozenset)):
        for v in x:
            _walk(v, seen, out)
    elif isinstance(x, str):
        out.add(x)


def test_i1_policy_sees_only_the_record(base_world):
    w = variant(base_world)
    spy = Script(lambda role, n: "book_gp_routine" if role == "nurse" else
                 ("order_chest_xray" if n.get("attempts__chest_xray") == 0 else
                  "refer_urgent" if n.get("last__chest_xray__abnormal") else "advice_return"))
    log = run_encounter(w, 120, 2, policy=spy)
    assert spy.views
    lib = world_library(w)
    hidden = set(w.catalogue.conditions) | {c.id for c in lib.cards}
    for v in spy.views:
        assert type(v) is PatientView and isinstance(v.record, Record)
        assert v.attributes == {} and v.history == [] and v.group == ""
        strings: set = set()
        _walk(v, set(), strings)
        assert not (strings & hidden), strings & hidden
        assert v.record.patient_id.startswith("P")
    assert any(p.record.assessments() == [] for p in log.patients)   # Script returns no words


def test_table_policy_writes_template_assessments(base_world):
    log = run_encounter(variant(base_world), 60, 1)
    a = [e for p in log.patients for e in p.record.assessments()]
    assert a and all(e.author.endswith("_encounter/table") for e in a)
    assert all("{action}" not in e.assessment.get("plan", "") for e in a)
    for p in log.patients:                        # each assessment follows the encounter that chose it
        es = p.record.entries
        for i, e in enumerate(es):
            if e.kind == "assessment":
                assert es[i - 1].kind == "encounter" and es[i - 1].action is not None


# ---------------------------------------------------------------------------- loop, results, horizon

def always_xray(role, n):
    return "book_gp_urgent" if role == "nurse" else "order_chest_xray"


def test_repeated_orders_loop_until_horizon(base_world):
    w = variant(base_world)
    log = run_encounter(w, 25, 4, policy=Script(always_xray))
    assert {p.outcome for p in log.patients} == {"undiagnosed_at_horizon"}
    for p in log.patients:
        att = [o.attempt for _, o in p.record.observations("chest_xray")]
        assert att == list(range(1, len(att) + 1)) and len(att) > 10
        assert all(o.positive in (True, False, None) for _, o in p.record.observations("chest_xray"))
        assert p.t_exit - p.patient.arrival == pytest.approx(365)
        results = [e for e in p.record.entries if e.kind == "result"]
        assert all(r.t_days >= 0 for r in results)
    # every result is followed by a review encounter with the ordering role
    p = log.patients[0]
    kinds = [e.kind for e in p.record.mechanical()]
    for i, k in enumerate(kinds[:-1]):
        if k == "result":
            assert kinds[i + 1] == "encounter"


@pytest.mark.xfail(reason="fresh attempts beyond max_attempts and resolved states come with WP-C8-2 "
                          "(until then the engine falls back to the last stored attempt)", strict=False)
def test_attempts_beyond_max_are_served_by_the_handle(base_world):
    log = run_encounter(variant(base_world), 10, 4, policy=Script(always_xray))
    assert sum(p.fallback_reveals for p in log.patients) == 0


def _order_to_result(log) -> list[float]:
    out = []
    for p in log.patients:
        es = p.record.mechanical()
        for i, e in enumerate(es):
            if e.kind == "result":
                out.append(e.t_days - max(x.t_days for x in es[:i] if x.kind == "encounter"))
    return out


def test_orders_take_time_and_capacity(base_world):
    w = variant(base_world)
    gaps = _order_to_result(run_encounter(w, 25, 4, policy=Script(always_xray)))
    assert min(gaps) >= 1.0                               # X-ray booking lead 2 days plus report time
    scarce = variant(base_world)
    scarce.scenario = copy.deepcopy(base_world.scenario)
    scarce.scenario.resources["xray"] = {**scarce.scenario.resources["xray"], "capacity_per_day": 1}
    gaps_scarce = _order_to_result(run_encounter(scarce, 25, 4, policy=Script(always_xray)))
    assert sum(gaps_scarce) / len(gaps_scarce) > 3 * sum(gaps) / len(gaps)   # one slot a day: a queue forms


# ---------------------------------------------------------------------------- treatment follows truth

def treat_then_send_home(role, n):
    if role == "nurse":
        return "book_gp_routine"
    return "advice_return" if n["reason"] == "treatment" else "treat_antibiotics"


def test_treatment_follows_hidden_truth(base_world):
    w = variant(base_world, prevalence={"pneumonia": 0.5, "lung_cancer": 0.5},
                natural_course={"unexplained": {"p": 1.0, "days": {"dist": "fixed", "value": 0}}})
    log = run_encounter(w, 80, 5, policy=Script(treat_then_send_home))
    pneu = [p for p in log.patients if p.conditions == ("pneumonia",)]
    cancer = [p for p in log.patients if "lung_cancer" in p.conditions]
    assert len(pneu) > 20 and len(cancer) > 20
    assert sum(p.outcome == "left_resolved" for p in pneu) / len(pneu) > 0.8
    assert all(t["matched"] for p in pneu for t in p.treatments)
    assert not any(p.outcome == "left_resolved" for p in cancer)
    assert sum(p.episode >= 2 for p in cancer) / len(cancer) > 0.4
    assert not any(t["matched"] for p in cancer if p.conditions == ("lung_cancer",) for t in p.treatments)


def test_resolved_state_is_served_by_the_handle(base_world):
    pytest.importorskip("patient_engine.states", reason="multi-state cards come with WP-C8-2")
    w = variant(base_world, prevalence={"pneumonia": 1.0})
    log = run_encounter(w, 20, 5, policy=Script(treat_then_send_home))
    # gathers after the treatment are in a resolved state; none should need the fallback below max_attempts
    assert sum(p.fallback_reveals for p in log.patients) == 0


# ---------------------------------------------------------------------------- hand-over

def refer_now(role, n):
    return "book_gp_urgent" if role == "nurse" else "refer_urgent"


def test_referral_enters_hospital_flowchart(base_world):
    w = variant(base_world, prevalence={"lung_cancer": 0.5, "viral_self_limiting": 0.5})
    log = run_encounter(w, 60, 6, policy=Script(refer_now))
    for p in log.patients:
        kinds = [e.kind for e in p.record.mechanical()]
        assert "referral" in kinds and "hospital" in kinds
        assert kinds.index("hospital") > kinds.index("referral")
        d = p.to_dict()
        assert d["t_referral"] is not None and d["t_referral"] >= 0
        if p.outcome == "treatment":
            assert d["t_treatment"] > d["t_referral"]
            assert d["t_treatment"] == pytest.approx(p.t_treatment - p.patient.arrival, abs=1e-3)
    cancer = [p for p in log.patients if p.patient.cancer]
    assert sum(p.outcome == "treatment" for p in cancer) / len(cancer) > 0.6
    ct = [o for p in log.patients for _, o in p.record.observations("chest_ct")]
    assert ct and all("lesion_seen" in o.values for o in ct if o.status == "ok")   # CT reads the card


# ---------------------------------------------------------------------------- I2, I3

def test_determinism_i2(base_world):
    w = variant(base_world)
    a = json.dumps(run_encounter(w, 80, 7).to_dict())
    b = json.dumps(run_encounter(w, 80, 7).to_dict())
    assert a == b


def test_same_results_across_policies_i3(base_world):
    w = variant(base_world)
    runs = [run_encounter(w, 30, 8), run_encounter(w, 30, 8, policy=Script(always_xray)),
            run_encounter(w, 30, 8, policy=Script(refer_now))]
    served: dict = {}
    shared = 0
    for log in runs:
        for p in log.patients:
            for test, k, state, values in p.seen:
                key = (p.patient.id, test, k, state)
                if key in served:
                    shared += 1
                    assert served[key] == values, key
                served[key] = values
    assert shared > 100


def test_outcomes_report_groups(base_world):
    log = run_encounter(variant(base_world), 80, 9)
    o = outcomes(log)
    assert o["overall"]["n"] == 80
    assert set(o["by_group"]) == {"age", "sex", "smoking", "region"}
    assert sum(s["n"] for s in o["by_group"]["sex"].values()) == 80
    d = log.to_dict()
    assert d["library_id"].startswith("L_") and d["patients"][0]["record"]["format"] == "record/1"


@pytest.mark.slow                 # generates the world's 600-card library (about 5 s)
def test_cli_runs_encounter_world(capsys, tmp_path):
    from pathway_sim.__main__ import main
    out = tmp_path / "run.json"
    main(["run", str(WORLD), "--flowchart", "encounter", "--n", "40", "--seed", "1", "--out", str(out)])
    text = capsys.readouterr().out
    assert "patients 40" in text and "group" in text
    d = json.loads(out.read_text())
    assert d["run"]["patients"][0]["record"]["entries"]

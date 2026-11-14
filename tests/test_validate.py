"""Structured validation (pathway_sim/validate.py): one test per problem code, the JSON shape, the
shipped scenarios coming out clean, and the raising validators (CLI, optimiser) behaving as before."""

import copy
import glob
from pathlib import Path

import pytest
import yaml

from pathway_sim import scenario_from_dict
from pathway_sim.problems import CODES, ERROR, WARNING, Problem, report
from pathway_sim.validate import validate, validate_scenario_dict

ROOT = Path(__file__).resolve().parent.parent


def base() -> dict:
    """A small valid scenario with no problems and no warnings."""
    return {
        "id": "v", "target_days": 30, "arrivals": {"spread_days": 100},
        "conditions": [{"id": "ca", "cancer": True, "prevalence": 0.2}, {"id": "no", "cancer": False, "prevalence": 0.8}],
        "groups": [{"id": "g1", "share_by_condition": {"ca": 0.5, "no": 0.5}}, {"id": "g2"}],
        "attributes": {"location": {"values": {"central": 0.5, "peripheral": 0.5}}},
        "resources": {"r": {"type": "delay", "wait": {"dist": "fixed", "value": 2}}},
        "tests": {
            "visit": {"resource": "r"},
            "scan": {"resource": "r", "p_positive": {"ca": 0.9, "default": 0.1}, "reveals": ["location"]},
            "bx": {"resource": "r"}, "nx": {"resource": "r"},
        },
        "flowcharts": {"f": {
            "nodes": [
                {"id": "visit", "test": "visit"},
                {"id": "scan", "test": "scan", "after": ["visit"]},
                {"id": "pick", "kind": "choice", "after": ["scan"], "when": "scan", "options": ["bx", "nx"]},
                {"id": "bx", "test": "bx"},
                {"id": "nx", "test": "nx"},
                {"id": "treat", "kind": "exit", "outcome": "treatment", "after_any": ["bx", "nx"]},
                {"id": "home", "kind": "exit", "outcome": "discharged", "after": ["scan"], "when": "not scan"},
            ],
            "policy": {"pick": {"rules": [{"when": "location == 'central'", "choose": "bx"}], "default": "nx"}},
        }},
    }


def run(mutate=None, deep=True, world_mutate=None) -> list:
    raw = base()
    if world_mutate:
        world_mutate(raw)
    if mutate:
        mutate(raw["flowcharts"]["f"])
    return validate_scenario_dict(raw, deep=deep)["problems"]


def node(fc: dict, nid: str) -> dict:
    return next(n for n in fc["nodes"] if n["id"] == nid)


def codes(problems) -> set:
    return {p["code"] for p in problems}


def only(problems, code: str) -> dict:
    hits = [p for p in problems if p["code"] == code]
    assert hits, f"no {code} in {[(p['code'], p['message']) for p in problems]}"
    return hits[0]


# ----------------------------------------------------------------------------- baseline and shape

def test_base_scenario_is_clean_and_loads():
    r = validate_scenario_dict(base())
    assert r == {"ok": True, "problems": []}
    scenario_from_dict(base())


def test_every_shipped_scenario_validates_clean():
    files = glob.glob(str(ROOT / "scenarios" / "**" / "*.yaml"), recursive=True)
    assert len(files) >= 8
    for f in files:
        r = validate_scenario_dict(yaml.safe_load(open(f)))
        assert r == {"ok": True, "problems": []}, (f, r["problems"])


def test_problem_shape_and_ordering():
    def mut(fc):
        node(fc, "pick")["when"] = "scann"                       # error: unknown name
        fc["nodes"].append({"id": "orphan", "test": "bx", "after": ["treat"]})     # warning only
    r = validate_scenario_dict(_with(mut))
    assert r["ok"] is False
    sev = [p["severity"] for p in r["problems"]]
    assert sev == sorted(sev, key=lambda s: s != "error")         # errors first
    p = only(r["problems"], "guard_unknown_name")
    assert set(p) == {"severity", "code", "message", "flowchart", "node", "edge", "field", "hint"}
    assert (p["severity"], p["flowchart"], p["node"], p["field"]) == ("error", "f", "pick", "when")
    assert p["hint"] == "Did you mean 'scan'?"
    json_ready = Problem("unreachable", "x").to_dict()
    assert json_ready["severity"] == "warning" and "detail" not in json_ready


def _with(mut) -> dict:
    raw = base()
    mut(raw["flowcharts"]["f"])
    return raw


def test_warnings_do_not_make_the_report_not_ok():
    r = report([Problem("unreachable", "x", node="a")])
    assert r["ok"] is True and r["problems"][0]["severity"] == "warning"


def test_code_table_is_consistent():
    assert set(CODES) >= {"unknown_reference", "duplicate_id", "cycle", "no_exit", "decision_needs_two_options",
                          "option_of_two_decisions", "unknown_test", "unknown_resource", "guard_syntax",
                          "guard_unknown_name", "information_not_available", "needs_violated",
                          "policy_unknown_option", "unreachable", "possible_dead_end", "missing_probabilities"}
    assert {c for c, (s, _) in CODES.items() if s == WARNING} == {"unreachable", "possible_dead_end", "missing_probabilities"}
    with pytest.raises(ValueError):
        Problem("made_up_code", "x")


# ----------------------------------------------------------------------------- one test per code

def test_duplicate_id():
    p = only(run(lambda fc: fc["nodes"].append({"id": "bx", "test": "bx"})), "duplicate_id")
    assert p["node"] == "bx" and p["severity"] == "error"


def test_unknown_kind():
    p = only(run(lambda fc: node(fc, "bx").update(kind="stepp")), "unknown_kind")
    assert p["node"] == "bx" and p["field"] == "kind"


def test_unknown_reference_in_after_edge():
    p = only(run(lambda fc: node(fc, "scan").update(after=["visitt"])), "unknown_reference")
    assert p["node"] == "scan" and p["field"] == "after" and p["edge"] == {"from": "visitt", "to": "scan", "type": "required"}
    assert p["hint"] == "Did you mean 'visit'?"


def test_unknown_reference_in_after_any_and_optional_and_options_and_fallback():
    p = only(run(lambda fc: node(fc, "treat").update(after_any=["bx", "nxx"])), "unknown_reference")
    assert p["edge"] == {"from": "nxx", "to": "treat", "type": "any"} and p["field"] == "after_any"
    p = only(run(lambda fc: node(fc, "treat").update(after_optional=["zzz"])), "unknown_reference")
    assert p["edge"]["type"] == "optional"
    p = only(run(lambda fc: node(fc, "pick").update(options=["bx", "nxx"])), "unknown_reference")
    assert p["edge"] == {"from": "pick", "to": "nxx", "type": "option"} and p["field"] == "options"
    p = only(run(lambda fc: node(fc, "bx").update(retry={"max": 1, "fallback": "gone"})), "unknown_reference")
    assert p["field"] == "retry.fallback" and p["node"] == "bx"


def test_cycle():
    p = only(run(lambda fc: node(fc, "visit").update(after=["scan"])), "cycle")
    assert p["severity"] == "error" and p["node"] in {"visit", "scan"} and "->" in p["message"] and p["edge"]


def test_no_exit():
    def mut(fc):
        fc["nodes"] = [n for n in fc["nodes"] if n.get("kind") != "exit"]
        fc["nodes"][2]["options"] = ["bx", "nx"]
    p = only(run(mut), "no_exit")
    assert p["node"] is None


def test_invalid_outcome():
    p = only(run(lambda fc: node(fc, "treat").update(outcome="cured")), "invalid_outcome")
    assert p["node"] == "treat" and p["field"] == "outcome"


def test_unknown_stage():
    p = only(run(lambda fc: node(fc, "scan").update(stage="middle")), "unknown_stage")
    assert p["node"] == "scan" and p["field"] == "stage"


def test_decision_needs_two_options():
    def mut(fc):
        node(fc, "pick")["options"] = ["bx"]
        node(fc, "nx")["after"] = ["visit"]
    p = only(run(mut), "decision_needs_two_options")
    assert p["node"] == "pick" and p["field"] == "options"


def test_option_of_two_decisions():
    def mut(fc):
        fc["nodes"].append({"id": "pick2", "kind": "choice", "after": ["scan"], "options": ["bx", "nx"]})
    p = only(run(mut), "option_of_two_decisions")
    assert p["node"] in {"bx", "nx"} and p["edge"]["type"] == "option" and "pick2" in p["message"]


def test_availability_unknown_option():
    p = only(run(lambda fc: node(fc, "pick").update(availability={"zz": {"p_available": 0.5}})), "availability_unknown_option")
    assert p["node"] == "pick" and p["field"] == "availability"


def test_policy_not_decision():
    p = only(run(lambda fc: fc["policy"].update(scan={"mix": {"a": 1}})), "policy_not_decision")
    assert p["node"] == "scan"
    p = only(run(lambda fc: fc["policy"].update(nowhere={"mix": {"a": 1}})), "policy_not_decision")
    assert p["node"] is None and p["field"] == "policy.nowhere"


def test_policy_unknown_option():
    p = only(run(lambda fc: fc["policy"]["pick"].update(default="zz")), "policy_unknown_option")
    assert p["node"] == "pick" and p["field"] == "policy.default"
    p = only(run(lambda fc: fc["policy"].update(pick={"mix": {"bx": 0.5, "zz": 0.5}})), "policy_unknown_option")
    assert p["field"] == "policy.mix.zz"
    p = only(run(lambda fc: fc["policy"]["pick"]["rules"][0].update(choose="zz")), "policy_unknown_option")
    assert p["field"] == "policy.rules[0].choose"
    p = only(run(lambda fc: fc["policy"].update(pick={"prefer": ["zz"]})), "policy_unknown_option")
    assert p["field"] == "policy.prefer"


def test_unknown_test():
    p = only(run(lambda fc: node(fc, "bx").update(test="bxx")), "unknown_test")
    assert p["node"] == "bx" and p["field"] == "test" and p["hint"] == "Did you mean 'bx'?"
    p = only(run(lambda fc: fc.update(test_overrides={"nope": {"cost_eur": 1}})), "unknown_test")
    assert p["node"] is None and p["field"] == "test_overrides.nope"


def test_unknown_resource():
    p = only(run(lambda fc: fc.update(resource_overrides={"nope": {"capacity_per_day": 3}})), "unknown_resource")
    assert p["field"] == "resource_overrides.nope"
    p = only(run(world_mutate=lambda raw: raw["tests"]["bx"].update(resource="rr")), "unknown_resource")
    assert p["field"] == "tests.bx.resource" and p["flowchart"] is None and p["hint"] == "Did you mean 'r'?"


def test_guard_syntax():
    p = only(run(lambda fc: node(fc, "home").update(when="not (scan")), "guard_syntax")
    assert p["node"] == "home" and p["field"] == "when"
    p = only(run(lambda fc: node(fc, "home").update(when="__import__('os').system('x')")), "guard_syntax")
    assert "call" in p["message"]
    p = only(run(lambda fc: fc["policy"]["pick"]["rules"][0].update(when="location ==")), "guard_syntax")
    assert p["node"] == "pick" and p["field"] == "policy.rules[0].when"


def test_guard_unknown_name():
    p = only(run(lambda fc: node(fc, "home").update(when="not scann")), "guard_unknown_name")
    assert p["node"] == "home" and p["hint"] == "Did you mean 'scan'?"
    p = only(run(lambda fc: fc["policy"]["pick"]["rules"][0].update(when="locaton == 'central'")), "guard_unknown_name")
    assert p["field"] == "policy.rules[0].when" and p["hint"] == "Did you mean 'location'?"


def test_information_not_available():
    # a step condition reading a step that is not upstream
    p = only(run(lambda fc: node(fc, "home").update(when="not bx")), "information_not_available")
    assert p["node"] == "home" and p["edge"] == {"from": "bx", "to": "home", "type": "required"}
    # an attribute no upstream test reveals
    p = only(run(lambda fc: node(fc, "visit").update(when="location == 'central'")), "information_not_available")
    assert p["node"] == "visit" and "location" in p["message"]
    # the policy rule reads an attribute that is revealed only after the decision
    def mut(fc):
        node(fc, "scan")["after"] = ["visit"]
        fc["policy"]["pick"]["rules"][0]["when"] = "location == 'central'"
    assert "information_not_available" not in codes(run(mut))        # the scan reveals it before the decision
    def late(raw):
        raw["tests"]["scan"]["reveals"] = []
        raw["tests"]["bx"]["reveals"] = ["location"]
    assert "information_not_available" in codes(run(world_mutate=late))


def test_information_available_through_instant_join():
    def mut(fc):
        fc["nodes"].insert(2, {"id": "flag", "after": ["scan"], "when": "scan"})
        node(fc, "pick")["when"] = "flag"
        node(fc, "pick")["after"] = ["scan"]
    assert "information_not_available" not in codes(run(mut))


def test_needs_violated():
    def world(raw):
        raw["optimiser"] = {"needs": {"nx": ["bx"]}}
    p = only(run(world_mutate=world), "needs_violated")
    assert p["node"] == "nx" and p["edge"]["from"] == "bx"


def test_world_invalid():
    p = only(run(world_mutate=lambda raw: raw["conditions"][0].update(prevalence=0.5)), "world_invalid")
    assert p["field"] == "conditions" and p["flowchart"] is None
    p = only(run(world_mutate=lambda raw: raw["resources"].update(s={"type": "server", "capacity_per_day": 0})), "world_invalid")
    assert p["field"] == "resources.s.capacity_per_day"
    p = only(run(world_mutate=lambda raw: raw["resources"].update(b={"type": "batch"})), "world_invalid")
    assert p["field"] == "resources.b.weekdays"
    p = only(run(world_mutate=lambda raw: raw["resources"].update(d={"type": "odd"})), "world_invalid")
    assert p["field"] == "resources.d.type"
    p = only(run(world_mutate=lambda raw: raw["tests"]["bx"].update(report_days={"dist": "nope"})), "world_invalid")
    assert p["field"] == "tests.bx.report_days"
    p = only(run(world_mutate=lambda raw: raw["tests"]["bx"].update(stage="x")), "world_invalid")
    assert p["field"] == "tests.bx.stage"


def test_unreachable_by_condition_by_prerequisite_and_by_decision():
    p = only(run(lambda fc: node(fc, "home").update(when="scan and not scan")), "unreachable")
    assert p["node"] == "home" and p["severity"] == "warning" and "condition" in p["message"]
    def mut(fc):
        node(fc, "home")["when"] = "False"
        fc["nodes"].append({"id": "after_home", "test": "bx", "after": ["home"]})
    ps = [p for p in run(mut) if p["code"] == "unreachable"]
    assert {p["node"] for p in ps} == {"home", "after_home"}
    def mut2(fc):
        node(fc, "pick")["when"] = "False"
    assert {p["node"] for p in run(mut2) if p["code"] == "unreachable"} >= {"pick", "bx", "nx", "treat"}


def test_unreachable_is_not_reported_for_a_retry_fallback_or_a_satisfiable_guard():
    def mut(fc):
        node(fc, "bx")["retry"] = {"max": 0, "fallback": "rescue"}
        fc["nodes"].append({"id": "rescue", "test": "nx", "after": ["bx"], "when": "False"})
    assert "unreachable" not in codes(run(mut))
    assert "unreachable" not in codes(run(lambda fc: node(fc, "home").update(when="scan is None or not scan")))
    assert "unreachable" not in codes(run(lambda fc: node(fc, "home").update(when="age > 200")))   # age is unbounded here


def test_possible_dead_end():
    # the exit only fires when the scan is positive; a negative scan has nowhere to go
    def mut(fc):
        fc["nodes"] = [n for n in fc["nodes"] if n["id"] != "home"]
    p = only(run(mut), "possible_dead_end")
    assert p["severity"] == "warning" and p["node"] in {"scan", "visit", "pick"} and "negative" in p["message"]


def test_missing_probabilities():
    p = only(run(lambda fc: fc.pop("policy")), "missing_probabilities")
    assert p["node"] == "pick" and p["severity"] == "warning" and p["field"] == "policy"


def test_every_code_has_a_test_here():
    src = Path(__file__).read_text()
    for code in CODES:
        assert f'"{code}"' in src, f"no test mentions {code}"


# ----------------------------------------------------------------------------- levels and CLI behaviour

def test_cheap_level_skips_editor_checks():
    ps = run(lambda fc: node(fc, "home").update(when="scan and not scan"), deep=False)
    assert "unreachable" not in codes(ps)
    ps = run(lambda fc: fc.pop("policy"), deep=False)
    assert "missing_probabilities" not in codes(ps)
    ps = run(lambda fc: node(fc, "home").update(when="not bx"), deep=False)
    assert "information_not_available" not in codes(ps)            # the loader never checked this


def test_loader_still_raises_valueerror_on_errors_and_accepts_warnings():
    for mutate in (lambda fc: node(fc, "bx").update(test="nope"),
                   lambda fc: node(fc, "scan").update(after=["nope"]),
                   lambda fc: node(fc, "home").update(when="not zzz"),
                   lambda fc: node(fc, "home").update(when="a.b"),
                   lambda fc: node(fc, "visit").update(after=["scan"]),
                   lambda fc: fc["policy"]["pick"].update(default="zz")):
        with pytest.raises(ValueError):
            scenario_from_dict(_with(mutate))
    with pytest.raises(ValueError, match="unknown names"):
        scenario_from_dict(_with(lambda fc: node(fc, "home").update(when="not zzz")))
    # warnings never block loading
    scenario_from_dict(_with(lambda fc: fc.pop("policy")))
    scenario_from_dict(_with(lambda fc: node(fc, "home").update(when="scan and not scan")))
    with pytest.raises(ValueError):
        scenario_from_dict({**base(), "conditions": [{"id": "x", "prevalence": 0.5}]})


def test_validation_does_not_mutate_its_input():
    raw = base()
    before = copy.deepcopy(raw)
    validate_scenario_dict(raw)
    assert raw == before


def test_deep_validation_is_fast_enough_for_live_editing():
    import time
    raw = yaml.safe_load(open(ROOT / "scenarios" / "finland_lung.yaml"))
    t = time.perf_counter()
    validate_scenario_dict(raw)
    assert time.perf_counter() - t < 3.0


def test_wrong_shapes_raise_malformed_document_not_random_errors():
    from pathway_sim.validate import MalformedDocument
    for mutate in (lambda fc: fc.update(nodes="x"), lambda fc: fc["nodes"].append("x"),
                   lambda fc: node(fc, "scan").update(after="visit"), lambda fc: node(fc, "scan").update(test=["a"]),
                   lambda fc: fc.update(policy=["x"]), lambda fc: node(fc, "pick").update(id=5)):
        with pytest.raises(MalformedDocument):
            validate_scenario_dict(_with(mutate))
    with pytest.raises(MalformedDocument):
        validate_scenario_dict({**base(), "tests": {"x": None}})
    with pytest.raises(ValueError):          # it is a ValueError, so loaders that expect ValueError keep working
        scenario_from_dict(_with(lambda fc: node(fc, "scan").update(after="visit")))

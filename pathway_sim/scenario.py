"""Scenario and flowchart loading and validation. Format: docs/architecture.md."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import dists
from .expr import Expr, ExprError, parse as parse_expr

STAGES = ("detection", "referral", "diagnosis", "treatment_start")
NODE_KINDS = ("step", "choice", "milestone", "exit")
OUTCOMES = ("treatment", "discharged", "diagnosis_only")
RESOURCE_TYPES = ("server", "delay", "batch", "none")


@dataclass
class Node:
    id: str
    kind: str = "step"
    test: str | None = None
    after: list[str] = field(default_factory=list)
    after_any: list[str] = field(default_factory=list)
    after_optional: list[str] = field(default_factory=list)   # wait for these only if they run
    when: str | None = None
    options: list[str] = field(default_factory=list)
    availability: dict = field(default_factory=dict)          # choice: option -> {p_available, weekdays}
    outcome: str | None = None
    milestone: str | None = None
    retry: dict | None = None
    fast_track: bool = False
    stage: str | None = None
    label: str | None = None
    code: Expr | None = None  # parsed guard (pathway_sim.expr), callable on a names dict

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind}
        for k in ("test", "when", "outcome", "milestone", "retry", "stage", "label"):
            v = getattr(self, k)
            if v:
                d[k] = v
        if self.availability:
            d["availability"] = copy.deepcopy(self.availability)
        for k in ("after", "after_any", "after_optional", "options"):
            v = getattr(self, k)
            if v:
                d[k] = list(v)
        if self.fast_track:
            d["fast_track"] = True
        return d


@dataclass
class Flowchart:
    id: str
    nodes: dict[str, Node]
    policy: dict = field(default_factory=dict)
    description: str = ""
    resource_overrides: dict = field(default_factory=dict)   # per-flowchart capacity / wait changes
    test_overrides: dict = field(default_factory=dict)       # per-flowchart test changes (e.g. faster PET)

    def to_dict(self) -> dict:
        d = {"id": self.id, "nodes": [n.to_dict() for n in self.nodes.values()]}
        if self.policy:
            d["policy"] = copy.deepcopy(self.policy)
        if self.resource_overrides:
            d["resource_overrides"] = copy.deepcopy(self.resource_overrides)
        if self.test_overrides:
            d["test_overrides"] = copy.deepcopy(self.test_overrides)
        if self.description:
            d["description"] = self.description
        return d

    def copy(self, new_id: str | None = None) -> "Flowchart":
        return parse_flowchart(new_id or self.id, self.to_dict())


@dataclass
class Scenario:
    id: str
    description: str
    clock_start: str
    target_days: float
    arrivals: dict
    conditions: list[dict]
    groups: list[dict]
    attributes: dict
    age: dict
    resources: dict[str, dict]
    tests: dict[str, dict]
    flowcharts: dict[str, Flowchart]
    warmup_days: float = 0.0
    raw: dict = field(default_factory=dict)
    path: str | None = None

    def condition(self, cid: str) -> dict:
        return next(c for c in self.conditions if c["id"] == cid)

    def stage_of(self, node: Node) -> str:
        if node.stage:
            return node.stage
        if node.test:
            return self.tests[node.test].get("stage", "diagnosis")
        return "diagnosis"


def parse_flowchart(fid: str, d: dict) -> Flowchart:
    nodes: dict[str, Node] = {}
    for nd in d["nodes"]:
        nd = dict(nd)
        n = Node(**{k: v for k, v in nd.items() if k in Node.__dataclass_fields__ and k != "code"})
        if n.id in nodes:
            raise ValueError(f"flowchart {fid}: duplicate node id {n.id!r}")
        n.code = compile_guard(n.when, f"{fid}/{n.id}") if n.when else None
        nodes[n.id] = n
    return Flowchart(id=fid, nodes=nodes, policy=copy.deepcopy(d.get("policy") or {}),
                     description=d.get("description", ""),
                     resource_overrides=copy.deepcopy(d.get("resource_overrides") or {}),
                     test_overrides=copy.deepcopy(d.get("test_overrides") or {}))


def compile_guard(expr: str, where: str) -> Expr:
    """Parse a guard with the safe evaluator (pathway_sim/expr.py); ValueError if it is not allowed."""
    try:
        return parse_expr(expr)
    except ExprError as e:
        raise ValueError(f"bad guard in {where}: {expr!r}: {e}") from e


def _raise_first(problems, where: str) -> None:
    for p in problems:
        if p.severity == "error":
            at = f"{where}/{p.node}" if p.node else where
            raise ValueError(f"{at}: {p.detail or p.message}")


def validate_flowchart(sc: Scenario, fc: Flowchart) -> None:
    """Raise ``ValueError`` on the first error. The checks live in ``pathway_sim/validate.py`` (cheap
    subset here: the optimiser calls this for every candidate edit); the editor and service use the
    full structured list from there."""
    from .validate import World, validate
    for n in fc.nodes.values():
        n.code = compile_guard(n.when, f"{sc.id}/{fc.id}/{n.id}") if n.when else None
    problems = validate(World.from_scenario(sc), fc.to_dict(), flowchart_id=fc.id, deep=False)
    _raise_first(problems, f"{sc.id}/{fc.id}")


def validate_scenario(sc: Scenario) -> None:
    from .validate import check_world
    _raise_first(check_world(sc), sc.id)
    for fc in sc.flowcharts.values():
        validate_flowchart(sc, fc)


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    return scenario_from_dict(raw, str(path))


def scenario_from_dict(raw: dict, path: str | None = None) -> Scenario:
    raw = copy.deepcopy(raw)
    fcs = {fid: parse_flowchart(fid, fd) for fid, fd in (raw.get("flowcharts") or {}).items()}
    sc = Scenario(
        id=raw["id"],
        description=raw.get("description", ""),
        clock_start=raw.get("clock_start", "referral_received"),
        target_days=float(raw.get("target_days", 42)),
        arrivals=raw.get("arrivals", {"spread_days": 365}),
        conditions=raw["conditions"],
        groups=raw.get("groups") or [{"id": "all"}],
        attributes=raw.get("attributes") or {},
        age=raw.get("age") or {"dist": "uniform", "low": 50, "high": 85},
        resources={k: dict(v) for k, v in (raw.get("resources") or {}).items()},
        tests={k: dict(v) for k, v in (raw.get("tests") or {}).items()},
        flowcharts=fcs,
        warmup_days=float(raw.get("warmup_days", 0)),
        raw=raw,
        path=path,
    )
    validate_scenario(sc)
    return sc

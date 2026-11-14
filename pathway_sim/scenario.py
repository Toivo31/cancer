"""Scenario and flowchart loading and validation. Format: docs/architecture.md."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import dists

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
    outcome: str | None = None
    milestone: str | None = None
    retry: dict | None = None
    fast_track: bool = False
    stage: str | None = None
    label: str | None = None
    code: object = None  # compiled guard

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind}
        for k in ("test", "when", "outcome", "milestone", "retry", "stage", "label"):
            v = getattr(self, k)
            if v:
                d[k] = v
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
        nodes[n.id] = n
    return Flowchart(id=fid, nodes=nodes, policy=copy.deepcopy(d.get("policy") or {}),
                     description=d.get("description", ""),
                     resource_overrides=copy.deepcopy(d.get("resource_overrides") or {}),
                     test_overrides=copy.deepcopy(d.get("test_overrides") or {}))


def compile_guard(expr: str, where: str):
    try:
        return compile(expr, f"<guard {where}>", "eval")
    except SyntaxError as e:
        raise ValueError(f"bad guard in {where}: {expr!r}: {e}") from e


def validate_flowchart(sc: Scenario, fc: Flowchart) -> None:
    ids = set(fc.nodes)
    option_of: dict[str, str] = {}
    for n in fc.nodes.values():
        where = f"{sc.id}/{fc.id}/{n.id}"
        if n.kind not in NODE_KINDS:
            raise ValueError(f"{where}: unknown kind {n.kind!r}")
        if n.test and n.test not in sc.tests:
            raise ValueError(f"{where}: unknown test {n.test!r}")
        for ref in n.after + n.after_any + n.after_optional + n.options:
            if ref not in ids:
                raise ValueError(f"{where}: unknown node reference {ref!r}")
        if n.kind == "choice":
            if len(n.options) < 2:
                raise ValueError(f"{where}: choice needs >= 2 options")
            for o in n.options:
                if o in option_of:
                    raise ValueError(f"{where}: {o!r} is an option of two choices")
                option_of[o] = n.id
        if n.kind == "exit" and n.outcome not in OUTCOMES:
            raise ValueError(f"{where}: exit needs outcome in {OUTCOMES}")
        if n.stage and n.stage not in STAGES:
            raise ValueError(f"{where}: unknown stage {n.stage!r}")
        if n.retry:
            fb = n.retry.get("fallback")
            if fb and fb not in ids:
                raise ValueError(f"{where}: unknown retry fallback {fb!r}")
        n.code = compile_guard(n.when, where) if n.when else None
    for cid, cfg in (fc.policy or {}).items():
        if cid not in fc.nodes or fc.nodes[cid].kind != "choice":
            raise ValueError(f"{sc.id}/{fc.id}: policy for {cid!r}, which is not a choice node")
        opts = set(fc.nodes[cid].options)
        named = set((cfg.get("mix") or {}).keys()) | set(cfg.get("prefer") or [])
        named |= {r["choose"] for r in cfg.get("rules") or []}
        if cfg.get("default"):
            named.add(cfg["default"])
        bad = named - opts
        if bad:
            raise ValueError(f"{sc.id}/{fc.id}: policy for {cid!r} names unknown options {sorted(bad)}")
    for tid in fc.test_overrides:
        if tid not in sc.tests:
            raise ValueError(f"{sc.id}/{fc.id}: test override for unknown test {tid!r}")
    for rid in fc.resource_overrides:
        if rid not in sc.resources:
            raise ValueError(f"{sc.id}/{fc.id}: resource override for unknown resource {rid!r}")
    if not any(n.kind == "exit" for n in fc.nodes.values()):
        raise ValueError(f"{sc.id}/{fc.id}: no exit node")
    # acyclic over after / after_any / options
    deps = {n.id: set(n.after) | set(n.after_any) | set(n.after_optional) for n in fc.nodes.values()}
    for o, c in option_of.items():
        deps[o].add(c)
    state: dict[str, int] = {}

    def visit(x: str, stack: tuple) -> None:
        if state.get(x) == 1:
            raise ValueError(f"{sc.id}/{fc.id}: cycle through {' -> '.join(stack + (x,))}")
        if state.get(x) == 2:
            return
        state[x] = 1
        for y in deps[x]:
            visit(y, stack + (x,))
        state[x] = 2

    for x in deps:
        visit(x, ())


def validate_scenario(sc: Scenario) -> None:
    prev = sum(float(c["prevalence"]) for c in sc.conditions)
    if abs(prev - 1.0) > 1e-6:
        raise ValueError(f"{sc.id}: condition prevalences sum to {prev}, not 1")
    for rid, r in sc.resources.items():
        t = r.get("type", "server")
        if t not in RESOURCE_TYPES:
            raise ValueError(f"{sc.id}: resource {rid} has unknown type {t!r}")
        if t == "server" and float(r.get("capacity_per_day", 0)) <= 0:
            raise ValueError(f"{sc.id}: server resource {rid} needs capacity_per_day > 0")
        if t == "delay":
            dists.validate(r.get("wait"))
        if t == "batch" and not r.get("weekdays"):
            raise ValueError(f"{sc.id}: batch resource {rid} needs weekdays")
    for tid, t in sc.tests.items():
        if t.get("resource", "none") not in sc.resources and t.get("resource", "none") != "none":
            raise ValueError(f"{sc.id}: test {tid} uses unknown resource {t.get('resource')!r}")
        if t.get("stage", "diagnosis") not in STAGES:
            raise ValueError(f"{sc.id}: test {tid} has unknown stage {t.get('stage')!r}")
        for k in ("service_days", "report_days", "extra_wait", "wait"):
            dists.validate(t.get(k))
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

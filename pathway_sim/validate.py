"""Structured validation: every problem at once, each tied to a node or an edge.

Codes, severities and the problem object are defined in :mod:`pathway_sim.problems`.

Entry points
------------
``validate(world, flowchart_dict, ...) -> list[Problem]``
    One flowchart (engine node form: ``after`` / ``after_any`` / ``after_optional`` / ``options``)
    against a world (a scenario dict or a :class:`~pathway_sim.scenario.Scenario`).
``validate_scenario_dict(raw, ...) -> {"ok", "problems"}``
    World problems plus every flowchart in a scenario dict (what ``scenario_from_dict`` would load).
``check_world(world) -> list[Problem]``
    The world tables only.
``validate_report(problems) -> {"ok", "problems"}``
    JSON shape returned by the service.

A document with the wrong *shape* (a list where a table belongs, a number as a node id) raises
:class:`MalformedDocument` (a ``ValueError``): that is a schema error for the service to answer
with 400, not an item for the editor's problem list.

Levels. ``deep=False`` runs only the cheap error checks that ``scenario.validate_flowchart`` always
did (it now wraps this module and still raises ``ValueError`` on the first error, which the CLI and
the optimiser rely on). ``deep=True`` (the default here) adds the editor checks: information
available to each condition, the world's clinical dependencies, reachability, possible dead ends
and missing probabilities.

Reachability is sound: ``unreachable`` is only reported when the structure or a condition that is
unsatisfiable on its own proves no patient can get there, never because a random run missed it.
Dead ends are found by running the flowchart's own rules without time on random patients
(random group, age, attributes, test results and choices); a patient who ends with no exit is a
*possible* dead end, because the random patients ignore correlations between tests.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import dists
from .expr import ALWAYS_KNOWN, ExprError, parse, suggest
from .problems import (EDGE_ANY, EDGE_OPTION, EDGE_OPTIONAL, EDGE_REQUIRED, Problem, edge_ref, report)
from .scenario import NODE_KINDS, OUTCOMES, RESOURCE_TYPES, STAGES

DECISION_KINDS = ("choice", "decision")      # "decision" is the document name for the engine's "choice"
DEP_FIELDS = (("after", EDGE_REQUIRED), ("after_any", EDGE_ANY), ("after_optional", EDGE_OPTIONAL))
MAX_REPORTED_DEAD_ENDS = 5


# --------------------------------------------------------------------------- world

@dataclass
class World:
    tests: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)
    groups: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
    needs: dict = field(default_factory=dict)       # test id -> test ids whose results it needs
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict) -> "World":
        cfg = raw.get("optimiser") or raw.get("constraints") or {}
        return cls(tests=raw.get("tests") or {}, resources=raw.get("resources") or {},
                   attributes=raw.get("attributes") or {}, groups=raw.get("groups") or [{"id": "all"}],
                   conditions=raw.get("conditions") or [], needs=cfg.get("needs") or {}, raw=raw)

    @classmethod
    def from_scenario(cls, sc) -> "World":
        return cls.from_raw({**sc.raw, "tests": sc.tests, "resources": sc.resources,
                             "attributes": sc.attributes, "groups": sc.groups, "conditions": sc.conditions})


class MalformedDocument(ValueError):
    """The document has the wrong shape (a table where a list belongs, a number as an id ...).
    That is a schema error for the service to answer with 400, not a problem for the editor's list."""


def _is(x, typ) -> bool:
    return isinstance(x, typ) and not (typ is not bool and isinstance(x, bool))


def _shape(cond: bool, path: str, want: str) -> None:
    if not cond:
        raise MalformedDocument(f"{path} must be {want}")


def _world(w) -> World:
    if not isinstance(w, World):
        w = World.from_raw(w) if isinstance(w, dict) else World.from_scenario(w)
    _shape(isinstance(w.tests, dict) and all(isinstance(t, dict) for t in w.tests.values()), "tests", "a table of tables")
    _shape(isinstance(w.resources, dict) and all(isinstance(t, dict) for t in w.resources.values()), "resources", "a table of tables")
    _shape(isinstance(w.attributes, dict) and all(isinstance(t, dict) for t in w.attributes.values()), "attributes", "a table of tables")
    _shape(isinstance(w.groups, list) and all(isinstance(g, dict) and "id" in g for g in w.groups), "groups", "a list of tables with ids")
    _shape(isinstance(w.conditions, list) and all(isinstance(c, dict) for c in w.conditions), "conditions", "a list of tables")
    _shape(isinstance(w.needs, dict), "optimiser.needs", "a table")
    return w


def _check_flowchart_shape(fc) -> None:
    _shape(isinstance(fc, dict), "flowchart", "a table")
    nodes = fc.get("nodes") or []
    _shape(isinstance(nodes, list), "nodes", "a list")
    for i, n in enumerate(nodes):
        at = f"nodes[{i}]"
        _shape(isinstance(n, dict), at, "a table")
        _shape(isinstance(n.get("id"), str), f"{at}.id", "text")
        for k in ("kind", "test", "outcome", "stage", "when", "label", "milestone"):
            _shape(n.get(k) is None or isinstance(n[k], str), f"{at}.{k}", "text")
        for k in ("after", "after_any", "after_optional", "options"):
            v = n.get(k)
            _shape(v is None or (isinstance(v, list) and all(isinstance(x, str) for x in v)), f"{at}.{k}", "a list of node ids")
        _shape(n.get("availability") is None or isinstance(n["availability"], dict), f"{at}.availability", "a table")
        _shape(n.get("retry") is None or isinstance(n["retry"], dict), f"{at}.retry", "a table")
        r = n.get("retry")
        _shape(r is None or r.get("fallback") is None or isinstance(r["fallback"], str), f"{at}.retry.fallback", "a node id")
    pol = fc.get("policy") or {}
    _shape(isinstance(pol, dict) and all(isinstance(c, dict) for c in pol.values()), "policy", "a table of tables")
    for cid, c in pol.items():
        _shape(c.get("mix") is None or isinstance(c["mix"], dict), f"policy.{cid}.mix", "a table")
        _shape(c.get("prefer") is None or isinstance(c["prefer"], list), f"policy.{cid}.prefer", "a list")
        _shape(c.get("rules") is None or (isinstance(c["rules"], list) and all(isinstance(r, dict) for r in c["rules"])),
               f"policy.{cid}.rules", "a list of tables")
        for i, r in enumerate(c.get("rules") or []):
            _shape(isinstance(r.get("when"), str), f"policy.{cid}.rules[{i}].when", "text")
            _shape(r.get("choose") is None or isinstance(r["choose"], str), f"policy.{cid}.rules[{i}].choose", "text")
    for k in ("test_overrides", "resource_overrides"):
        _shape(fc.get(k) is None or isinstance(fc[k], dict), k, "a table")


def check_world(world) -> list[Problem]:
    """Problems in the world tables (prevalences, resources, tests): ``world_invalid`` and ``unknown_resource``."""
    try:
        return _check_world(_world(world))
    except (TypeError, AttributeError, KeyError, ValueError, IndexError) as e:
        if isinstance(e, MalformedDocument):
            raise
        raise MalformedDocument(f"the world has an unexpected shape ({type(e).__name__}: {e})") from e


def _check_world(w: World) -> list[Problem]:
    out: list[Problem] = []

    def bad(field_path: str, message: str, hint: str | None = None) -> None:
        out.append(Problem("world_invalid", message, field=field_path, hint=hint))

    try:
        prev = sum(float(c["prevalence"]) for c in w.conditions)
        if abs(prev - 1.0) > 1e-6:
            bad("conditions", f"Condition prevalences add up to {prev:g}, not 1", "They must sum to exactly 1")
    except (KeyError, TypeError, ValueError):
        bad("conditions", "Every condition needs a numeric prevalence")
    for rid, r in w.resources.items():
        t = r.get("type", "server")
        if t not in RESOURCE_TYPES:
            bad(f"resources.{rid}.type", f"Resource '{rid}' has unknown type {t!r}", f"Use one of {', '.join(RESOURCE_TYPES)}")
            continue
        if t == "server":
            try:
                ok = float(r.get("capacity_per_day", 0)) > 0
            except (TypeError, ValueError):
                ok = False
            if not ok:
                bad(f"resources.{rid}.capacity_per_day", f"Resource '{rid}' needs a capacity per day above 0")
        if t == "delay":
            _dist(out, f"resources.{rid}.wait", r.get("wait"), f"Resource '{rid}' wait")
        if t == "batch" and not r.get("weekdays"):
            bad(f"resources.{rid}.weekdays", f"Resource '{rid}' (batch) needs at least one weekday")
    for tid, t in w.tests.items():
        rid = t.get("resource", "none")
        if rid != "none" and rid not in w.resources:
            out.append(Problem("unknown_resource", f"Test '{tid}' uses resource '{rid}', which does not exist",
                               field=f"tests.{tid}.resource", hint=_did_you_mean(rid, w.resources)))
        if t.get("stage", "diagnosis") not in STAGES:
            bad(f"tests.{tid}.stage", f"Test '{tid}' has unknown stage {t.get('stage')!r}", f"Use one of {', '.join(STAGES)}")
        for k in ("service_days", "report_days", "extra_wait", "wait"):
            _dist(out, f"tests.{tid}.{k}", t.get(k), f"Test '{tid}' {k}")
    return out


def _dist(out: list, path: str, spec, what: str) -> None:
    try:
        dists.validate(spec)
    except Exception as e:      # malformed spec: KeyError, ValueError, TypeError ...
        out.append(Problem("world_invalid", f"{what} is not a valid distribution ({e})", field=path))


def _leaves(spec) -> list[float]:
    """All probabilities in a ``p_positive`` spec (plain, per condition, or per attribute value)."""
    if isinstance(spec, dict):
        out: list[float] = []
        for k, v in spec.items():
            if k in ("by", "value") and not isinstance(v, (int, float)):
                continue
            out += _leaves(v)
        return out
    try:
        return [float(spec)]
    except (TypeError, ValueError):
        return []


def _did_you_mean(name: str, known: Iterable[str]) -> str | None:
    import difflib
    m = difflib.get_close_matches(str(name), [str(k) for k in known], n=1, cutoff=0.6)
    return f"Did you mean '{m[0]}'?" if m else None


# --------------------------------------------------------------------------- flowchart

def validate(world, flowchart: dict, *, flowchart_id: str | None = None, deep: bool = True,
             samples: int = 300, seed: int = 0) -> list[Problem]:
    """All problems of one flowchart dict. ``deep=False`` is the cheap error-only subset."""
    try:
        w = _world(world)
        _check_flowchart_shape(flowchart)
        return _Check(w, flowchart, flowchart_id, deep, samples, seed).run()
    except (TypeError, AttributeError, KeyError, ValueError, IndexError) as e:
        if isinstance(e, MalformedDocument):
            raise
        raise MalformedDocument(f"the document has an unexpected shape ({type(e).__name__}: {e})") from e


def validate_report(problems: Iterable[Problem]) -> dict:
    return report(problems)


def validate_scenario_dict(raw: dict, *, deep: bool = True, samples: int = 300) -> dict:
    """``{"ok", "problems"}`` for a whole scenario dict: world tables, then every flowchart."""
    w = _world(raw)
    _shape(isinstance(raw.get("flowcharts") or {}, dict), "flowcharts", "a table")
    out = check_world(w)
    for fid, fd in (raw.get("flowcharts") or {}).items():
        out += validate(w, fd, flowchart_id=fid, deep=deep, samples=samples)
    return report(out)


class _Check:
    def __init__(self, w: World, fc: dict, fid: str | None, deep: bool, samples: int, seed: int):
        self.w, self.fc, self.fid, self.deep, self.samples, self.seed = w, fc, fid, deep, samples, seed
        self.out: list[Problem] = []
        self.nodes: list[dict] = [n for n in (fc.get("nodes") or []) if isinstance(n, dict) and n.get("id") is not None]
        self.ids: list[str] = [str(n["id"]) for n in self.nodes]
        self.idset = set(self.ids)
        self.by_id: dict[str, dict] = {}
        for n in self.nodes:
            self.by_id.setdefault(str(n["id"]), n)
        self.policy: dict = fc.get("policy") or {}
        self.guards: dict[str, Any] = {}          # node id -> Expr (only valid ones)
        self.rules: dict[str, list] = {}          # decision id -> [(index, Expr, choose)]
        self.structure_ok = True                  # False when references are broken: skip graph analyses

    # -- problem helper
    def add(self, code: str, message: str, node: str | None = None, edge: dict | None = None,
            field: str | None = None, hint: str | None = None, detail: str | None = None) -> None:
        self.out.append(Problem(code, message, flowchart=self.fid, node=node, edge=edge, field=field,
                                hint=hint, detail=detail))

    def is_decision(self, n: dict) -> bool:
        return n.get("kind", "step") in DECISION_KINDS

    @staticmethod
    def listf(n: dict, key: str) -> list:
        v = n.get(key)
        return list(v) if isinstance(v, (list, tuple)) else []

    # -- run
    def run(self) -> list[Problem]:
        self.structure()
        self.policy_checks()
        self.overrides()
        self.guard_checks()
        if self.deep:
            self.information()
            self.needs()
            self.probabilities()
            if self.structure_ok:
                self.reachability()
                self.dead_ends()
        return self.out

    # -- structure
    def structure(self) -> None:
        seen: set[str] = set()
        for n in self.nodes:
            nid = str(n["id"])
            if nid in seen:
                self.add("duplicate_id", f"Two nodes are called '{nid}'", nid, field="id",
                         hint="Rename one of them", detail=f"duplicate node id {nid!r}")
                self.structure_ok = False
            seen.add(nid)
        owner: dict[str, str] = {}
        for n in self.nodes:
            nid = str(n["id"])
            kind = n.get("kind", "step")
            if kind not in NODE_KINDS:
                self.add("unknown_kind", f"Node '{nid}' has unknown kind {kind!r}", nid, field="kind",
                         hint=f"Use one of {', '.join(NODE_KINDS)}",
                         detail=f"unknown kind {kind!r}")
            test = n.get("test")
            if test and test not in self.w.tests:
                self.add("unknown_test", f"Step '{nid}' uses test '{test}', which is not in the world", nid, field="test",
                         hint=_did_you_mean(test, self.w.tests), detail=f"unknown test {test!r}")
            for key, etype in DEP_FIELDS:
                for ref in self.listf(n, key):
                    if ref not in self.idset:
                        self.add("unknown_reference", f"'{nid}' waits for '{ref}', which does not exist", nid,
                                 edge_ref(ref, nid, etype), key, _did_you_mean(ref, self.idset),
                                 f"unknown node reference {ref!r}")
                        self.structure_ok = False
            options = self.listf(n, "options")
            for o in options:
                if o not in self.idset:
                    self.add("unknown_reference", f"Decision '{nid}' has option '{o}', which does not exist", nid,
                             edge_ref(nid, o, EDGE_OPTION), "options", _did_you_mean(o, self.idset),
                             f"unknown node reference {o!r}")
                    self.structure_ok = False
            av = n.get("availability") or {}
            if isinstance(av, dict):
                for o in av:
                    if o not in options:
                        self.add("availability_unknown_option", f"Availability is set for '{o}', which is not an option of '{nid}'",
                                 nid, field="availability", detail=f"availability for {o!r}, not an option")
            if self.is_decision(n):
                if len(set(options)) < 2:
                    self.add("decision_needs_two_options", f"Decision '{nid}' needs at least two options", nid,
                             field="options", detail="choice needs >= 2 options")
                for o in options:
                    if o in owner and owner[o] != nid:
                        self.add("option_of_two_decisions", f"'{o}' is an option of both '{owner[o]}' and '{nid}'",
                                 o, edge_ref(nid, o, EDGE_OPTION), "options", "A node can be chosen by one decision only",
                                 f"{o!r} is an option of two choices")
                        self.structure_ok = False
                    owner.setdefault(o, nid)
            if kind == "exit" and n.get("outcome") not in OUTCOMES:
                self.add("invalid_outcome", f"Exit '{nid}' needs an outcome", nid, field="outcome",
                         hint=f"Use one of {', '.join(OUTCOMES)}", detail=f"exit needs outcome in {OUTCOMES}")
            if n.get("stage") and n["stage"] not in STAGES:
                self.add("unknown_stage", f"Node '{nid}' has unknown stage {n['stage']!r}", nid, field="stage",
                         hint=f"Use one of {', '.join(STAGES)}", detail=f"unknown stage {n['stage']!r}")
            retry = n.get("retry")
            if isinstance(retry, dict) and retry.get("fallback") and retry["fallback"] not in self.idset:
                fb = retry["fallback"]
                self.add("unknown_reference", f"The fallback of '{nid}' is '{fb}', which does not exist", nid,
                         edge_ref(nid, fb, EDGE_REQUIRED), "retry.fallback", _did_you_mean(fb, self.idset),
                         f"unknown retry fallback {fb!r}")
        self.owner = owner
        if not any(n.get("kind") == "exit" for n in self.nodes):
            self.add("no_exit", "The flowchart has no exit, so no patient can finish", None,
                     hint="Add an exit node (treatment, discharged or diagnosis_only)", detail="no exit node")
        self.cycles()

    def deps(self, nid: str) -> list[tuple[str, str]]:
        """(dependency id, edge type) for a node, restricted to existing nodes."""
        n = self.by_id[nid]
        out = [(r, t) for key, t in DEP_FIELDS for r in self.listf(n, key) if r in self.idset]
        d = self.owner.get(nid)
        if d is not None and d in self.idset:
            out.append((d, EDGE_OPTION))
        return out

    def cycles(self) -> None:
        color: dict[str, int] = {}
        reported = 0
        for root in self.ids:
            if color.get(root):
                continue
            stack = [(root, iter(self.deps(root)))]
            path = [root]
            color[root] = 1
            while stack:
                x, it = stack[-1]
                for y, etype in it:
                    if color.get(y) == 1:
                        i = path.index(y)
                        loop = path[i:] + [y]
                        if reported < 5:
                            self.add("cycle", "Steps wait for each other in a loop: " + " -> ".join(loop), x,
                                     edge_ref(y, x, etype) if etype != EDGE_OPTION else edge_ref(y, x, EDGE_OPTION),
                                     hint="Remove one of these waits", detail=f"cycle through {' -> '.join(loop)}")
                        reported += 1
                        self.structure_ok = False
                    elif not color.get(y):
                        color[y] = 1
                        path.append(y)
                        stack.append((y, iter(self.deps(y))))
                        break
                else:
                    color[x] = 2
                    path.pop()
                    stack.pop()

    # -- policy
    def policy_checks(self) -> None:
        for cid, cfg in self.policy.items():
            cfg = cfg if isinstance(cfg, dict) else {}
            n = self.by_id.get(cid)
            if n is None or not self.is_decision(n):
                self.add("policy_not_decision", f"Probabilities or rules are set for '{cid}', which is not a decision",
                         cid if n is not None else None, field=f"policy.{cid}",
                         detail=f"policy for {cid!r}, which is not a choice node")
                continue
            options = set(self.listf(n, "options"))

            def unknown(opt, path):
                if opt not in options:
                    self.add("policy_unknown_option", f"The probabilities of '{cid}' name '{opt}', which is not one of its options",
                             cid, field=path, hint=_did_you_mean(opt, options),
                             detail=f"policy for {cid!r} names unknown options ['{opt}']")
            for opt in (cfg.get("mix") or {}):
                unknown(opt, f"policy.mix.{opt}")
            for opt in cfg.get("prefer") or []:
                unknown(opt, "policy.prefer")
            if cfg.get("default"):
                unknown(cfg["default"], "policy.default")
            for i, r in enumerate(cfg.get("rules") or []):
                if isinstance(r, dict):
                    if r.get("choose") is not None:
                        unknown(r["choose"], f"policy.rules[{i}].choose")
                    self.parse_rule(cid, i, r.get("when"))

    def parse_rule(self, cid: str, i: int, text) -> None:
        path = f"policy.rules[{i}].when"
        try:
            self.rules.setdefault(cid, []).append((i, parse(text), path))
        except ExprError as e:
            self.add("guard_syntax", f"The rule of '{cid}' cannot be read: {self.where(e)}", cid, field=path,
                     hint=e.hint, detail=f"bad guard in {self.fid}/policy/{cid}: {text!r}: {e}")

    @staticmethod
    def where(e: ExprError) -> str:
        return e.message + (f" (at character {e.col + 1})" if e.col is not None else "")

    # -- overrides
    def overrides(self) -> None:
        for tid in self.fc.get("test_overrides") or {}:
            if tid not in self.w.tests:
                self.add("unknown_test", f"This flowchart changes test '{tid}', which is not in the world", None,
                         field=f"test_overrides.{tid}", hint=_did_you_mean(tid, self.w.tests),
                         detail=f"test override for unknown test {tid!r}")
        for rid in self.fc.get("resource_overrides") or {}:
            if rid not in self.w.resources:
                self.add("unknown_resource", f"This flowchart changes resource '{rid}', which is not in the world", None,
                         field=f"resource_overrides.{rid}", hint=_did_you_mean(rid, self.w.resources),
                         detail=f"resource override for unknown resource {rid!r}")

    # -- conditions
    def known_names(self) -> set[str]:
        return self.idset | set(self.w.attributes) | ALWAYS_KNOWN | {"True", "False", "None"}

    def guard_checks(self) -> None:
        known = self.known_names()
        items = []
        for n in self.nodes:
            nid = str(n["id"])
            when = n.get("when")
            if when:
                try:
                    e = parse(when)
                    self.guards.setdefault(nid, e)
                    items.append((nid, "when", e, "condition"))
                except ExprError as ex:
                    self.add("guard_syntax", f"The condition of '{nid}' cannot be read: {self.where(ex)}", nid,
                             field="when", hint=ex.hint, detail=f"bad guard in {self.fid}/{nid}: {when!r}: {ex}")
        for cid, rules in self.rules.items():
            for i, e, path in rules:
                items.append((cid, path, e, "rule"))
        for nid, path, e, what in items:
            for name in sorted(e.names - known):
                s = suggest(name, known - {"True", "False", "None"})
                self.add("guard_unknown_name",
                         f"The {what} of '{nid}' reads '{name}', which is not a step or attribute",
                         nid, field=path, hint=f"Did you mean '{s}'?" if s else None,
                         detail=f"guard {e.source!r} reads unknown names {sorted(e.names - known)}")

    # -- information (deep)
    def ancestors(self, nid: str) -> set[str]:
        out, stack = set(), [nid]
        while stack:
            for d, _ in self.deps(stack.pop()):
                if d not in out:
                    out.add(d)
                    stack.append(d)
        return out

    def instant_known(self, name: str, anc: set[str]) -> bool:
        """A step without a test (join, milestone, guard-only node) is evaluated the moment everything
        it waits for has finished, so a node that waits for all of that has seen its result."""
        n = self.by_id[name]
        if n.get("test") or self.is_decision(n):
            return False
        return all(d in anc for d, _ in self.deps(name))

    def information(self) -> None:
        if not self.structure_ok:
            return
        revealed_by: dict[str, set] = {}
        for nid in self.ids:
            t = self.w.tests.get(self.by_id[nid].get("test"))
            revealed_by[nid] = set((t or {}).get("reveals") or [])
        for nid in self.ids:
            reads: list[tuple[str, Any]] = []
            if nid in self.guards:
                reads.append(("when", self.guards[nid]))
            reads += [(path, e) for _, e, path in self.rules.get(nid, [])]
            if not reads:
                continue
            anc = self.ancestors(nid)
            revealed = set().union(*(revealed_by[a] for a in anc)) if anc else set()
            for path, e in reads:
                for name in sorted(e.names):
                    if name in ALWAYS_KNOWN or name in ("True", "False", "None"):
                        continue
                    if name in self.idset:
                        ok = name in anc or self.instant_known(name, anc)
                    elif name in self.w.attributes:
                        ok = name in revealed
                    else:
                        continue            # unknown name: already reported
                    if not ok:
                        what = "the result of step" if name in self.idset else "the attribute"
                        edge = edge_ref(name, nid, EDGE_REQUIRED) if name in self.idset else None
                        self.add("information_not_available",
                                 f"'{nid}' reads {what} '{name}', which is not known by the time it is evaluated", nid, edge, path,
                                 f"Make '{name}' run before '{nid}', or read something else"
                                 if name in self.idset else f"Add a step before '{nid}' that reveals '{name}'",
                                 f"guard on {nid!r} reads {name!r}, not upstream")

    # -- world constraints (deep)
    def needs(self) -> None:
        if not self.structure_ok:
            return
        by_test: dict[str, list[str]] = {}
        for nid in self.ids:
            t = self.by_id[nid].get("test")
            if t:
                by_test.setdefault(t, []).append(nid)
        for t, needed in (self.w.needs or {}).items():
            for x in by_test.get(t, []):
                anc = self.ancestors(x)
                for nt in needed:
                    for y in by_test.get(nt, []):
                        if y not in anc:
                            self.add("needs_violated", f"'{x}' ({t}) needs the result of '{y}' ({nt}) first, but does not wait for it",
                                     x, edge_ref(y, x, EDGE_REQUIRED), "after",
                                     f"Make '{x}' wait for '{y}'")

    def probabilities(self) -> None:
        for n in self.nodes:
            if not self.is_decision(n):
                continue
            nid = str(n["id"])
            cfg = self.policy.get(nid)
            if not isinstance(cfg, dict) or not any(cfg.get(k) for k in ("mix", "rules", "prefer", "default")):
                self.add("missing_probabilities", f"Decision '{nid}' has no probabilities or rules, so the first option is always taken",
                         nid, field="policy", hint="Set how often each option is chosen")

    # -- reachability (deep, sound)
    def domain(self, name: str) -> list | None:
        """Values a name can take in a condition (a superset), or None when unbounded.
        Every name can be None: a step that was skipped or has not run, an attribute not yet revealed."""
        if name in self.idset:
            n = self.by_id[name]
            if self.is_decision(n):
                return [None]                     # a decision stores no result
            if n.get("test") and n.get("kind") != "exit":
                return [True, False, None]
            return [True, None]                   # joins, milestones: True once done
        if name in self.w.attributes:
            vals = set(((self.w.attributes[name] or {}).get("values")) or {})
            for c in self.w.conditions:
                vals |= set(((c.get("attributes") or {}).get(name)) or {})
            return sorted(vals, key=str) + [None]
        if name == "group":
            return [g["id"] for g in self.w.groups] or None
        return None

    def result_domain(self, nid: str) -> list:
        """What a finished test can come back as for a patient, from the test's ``p_positive`` (a test
        without one is always positive, as in the patient generator) and ``p_nondiagnostic``."""
        t = self.w.tests.get(self.by_id[nid].get("test")) or {}
        spec = t.get("p_positive")
        leaves = _leaves(spec) if spec is not None else [1.0]
        vals = []
        if max(leaves, default=0.0) > 0:
            vals.append(True)
        if min(leaves, default=1.0) < 1:
            vals.append(False)
        if t.get("p_nondiagnostic"):
            vals.append(None)
        return vals or [True]

    def satisfiable(self, e) -> bool:
        """False only when the condition can never be true on its own."""
        if e.is_constant:
            return e.holds({})
        doms = [self.domain(n) for n in sorted(e.names)]
        if any(d is None for d in doms):
            return True
        size = 1
        for d in doms:
            size *= len(d)
            if size > 20000:
                return True
        names = sorted(e.names)
        return any(e.holds(dict(zip(names, combo))) for combo in itertools.product(*doms))

    def reachability(self) -> None:
        order = self.topo()
        if order is None:
            return
        fallback_from: dict[str, list[str]] = {}
        for n in self.nodes:
            r = n.get("retry")
            if isinstance(r, dict) and r.get("fallback") in self.idset:
                fallback_from.setdefault(r["fallback"], []).append(str(n["id"]))
        reach: dict[str, bool] = {}
        why: dict[str, str] = {}
        for nid in order:
            n = self.by_id[nid]
            ok, reason = True, ""
            if nid in self.guards and not self.satisfiable(self.guards[nid]):
                ok, reason = False, "its condition can never be true"
            for key, etype in DEP_FIELDS[:1]:
                for r in self.listf(n, key):
                    if ok and r in reach and not reach[r]:
                        ok, reason = False, f"it waits for '{r}', which no patient can reach"
            any_deps = [r for r in self.listf(n, "after_any") if r in reach]
            if ok and any_deps and not any(reach[r] for r in any_deps):
                ok, reason = False, "none of the steps it can start after are reachable"
            d = self.owner.get(nid)
            if ok and d is not None and d in reach and not reach[d]:
                ok, reason = False, f"its decision '{d}' is unreachable"
            if not ok and any(reach.get(src) for src in fallback_from.get(nid, [])):
                ok, reason = True, ""            # a retry fallback runs it regardless of its own prerequisites
            reach[nid] = ok
            if not ok:
                why[nid] = reason
                self.add("unreachable", f"No patient can reach '{nid}': {reason}", nid, field="when" if "condition" in reason else None)
        self.reach = reach

    def topo(self) -> list[str] | None:
        order, state = [], {}
        for root in self.ids:
            if root in state:
                continue
            stack = [(root, iter(self.deps(root)))]
            state[root] = 1
            while stack:
                x, it = stack[-1]
                for y, _ in it:
                    if y not in state:
                        state[y] = 1
                        stack.append((y, iter(self.deps(y))))
                        break
                    if state[y] == 1:
                        return None
                else:
                    state[x] = 2
                    order.append(x)
                    stack.pop()
        return order

    # -- dead ends (deep, sampled)
    def dead_ends(self) -> None:
        order = self.topo()
        if order is None or not any(n.get("kind") == "exit" for n in self.nodes):
            return
        sim = _AbstractRun(self, order)
        rng = random.Random(self.seed)
        found: dict[str, str] = {}
        for i in range(self.samples + 1):
            res = sim.run(rng, uniform=(i == 0))        # run 0: every test positive, first option always
            if res is None:
                continue
            last, example = res
            if last not in found:
                found[last] = example
            if len(found) >= MAX_REPORTED_DEAD_ENDS:
                break
        for last, example in found.items():
            suffix = f" (for example when {example})" if example else ""
            self.add("possible_dead_end",
                     f"A patient can finish '{last}' and have nowhere to go: no exit is reached{suffix}", last,
                     hint="Make sure every outcome of this step leads to an exit")


class _AbstractRun:
    """The engine's readiness rules without time, for random patients (see module docstring)."""

    def __init__(self, chk: _Check, order: list[str]):
        self.c, self.order = chk, order
        self.nodes = {nid: chk.by_id[nid] for nid in order}
        self.children: dict[str, set[str]] = {x: set() for x in order}
        for nid in order:
            n = self.nodes[nid]
            for key, _ in DEP_FIELDS:
                for d in chk.listf(n, key):
                    if d in self.children:
                        self.children[d].add(nid)
            if chk.is_decision(n):
                for o in chk.listf(n, "options"):
                    if o in self.children:
                        self.children[nid].add(o)
        self.option_of = chk.owner
        self.pos = {nid: i for i, nid in enumerate(order)}

    def run(self, rng: random.Random, uniform: bool = False):
        c = self.c
        w = c.w
        group = rng.choice([g["id"] for g in w.groups] or ["all"])
        env_base = {"group": group, "age": rng.randint(40, 90), "t": rng.uniform(0, 100)}
        patient_attr = {}
        for name, spec in w.attributes.items():
            vals = [v for v in (c.domain(name) or []) if v is not None]
            patient_attr[name] = rng.choice(vals) if vals else None
        status = {nid: "pending" for nid in self.order}
        result: dict[str, Any] = {}
        revealed: dict[str, Any] = {}
        outcome = [None]

        def draw(nid):
            if uniform:
                return True
            return rng.choice(c.result_domain(nid))

        def env():
            d = dict(env_base)
            d.update(revealed)
            d.update(result)
            return d

        def ready_cause(nid):
            st = status[nid]
            n = self.nodes[nid]
            if st == "forced":
                return True, False
            if nid in self.option_of and st != "enabled":
                return False, False
            after, opt, anyl = c.listf(n, "after"), c.listf(n, "after_optional"), c.listf(n, "after_any")
            after = [a for a in after if a in status]
            for a in after:
                if status[a] in ("skipped", "failed"):
                    return False, True
            if any(status[a] != "done" for a in after):
                return False, False
            if any(status[a] not in ("done", "skipped", "failed") for a in opt if a in status):
                return False, False
            anyl = [a for a in anyl if a in status]
            if c.listf(n, "after_any"):
                if not any(status[a] == "done" for a in anyl):
                    if all(status[a] in ("skipped", "failed") for a in anyl):
                        return False, True
                    return False, False
            return True, False

        def skip(nid):
            status[nid] = "skipped"
            n = self.nodes[nid]
            if c.is_decision(n):
                for o in c.listf(n, "options"):
                    if o in status and status[o] in ("pending", "enabled"):
                        skip(o)

        def revive(fb):
            stack, seen = list(self.children[fb]), set()
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                if status[x] != "skipped":
                    continue
                d = self.option_of.get(x)
                if d is not None and status.get(d) == "done":
                    continue
                status[x] = "pending"
                result.pop(x, None)
                stack.extend(self.children[x])

        def do_test(nid, n):
            retry = n.get("retry") if isinstance(n.get("retry"), dict) else None
            attempt, r = 0, draw(nid)
            while r is None and retry and retry.get("on", "nondiagnostic") == "nondiagnostic" and attempt < int(retry.get("max", 1)):
                attempt += 1
                r = draw(nid)
            if r is None and retry and retry.get("on", "nondiagnostic") == "nondiagnostic":
                fb = retry.get("fallback")
                if fb in status and status[fb] in ("pending", "skipped"):
                    status[nid], result[nid] = "failed", None
                    status[fb] = "forced"
                    revive(fb)
                    return
            status[nid], result[nid] = "done", r
            t = w.tests.get(n.get("test")) or {}
            for a in t.get("reveals") or []:
                revealed[a] = patient_attr.get(a)

        guard, rules = c.guards, c.rules
        changed = True
        steps = 0
        while changed and outcome[0] is None and steps < 10 * len(self.order) + 50:
            changed = False
            for nid in self.order:
                st = status[nid]
                if st not in ("pending", "enabled", "forced"):
                    continue
                ready, dead = ready_cause(nid)
                if dead:
                    skip(nid)
                    changed = True
                    steps += 1
                    continue
                if not ready:
                    continue
                changed = True
                steps += 1
                n = self.nodes[nid]
                if st != "forced" and nid in guard and not guard[nid].holds(env()):
                    skip(nid)
                    continue
                if n.get("kind") == "exit":
                    status[nid] = "done"
                    outcome[0] = nid
                    return None
                if c.is_decision(n):
                    opts = [o for o in c.listf(n, "options") if o in status]
                    pick = opts[0] if (uniform or not opts) else rng.choice(opts)
                    for o in opts:
                        if o == pick:
                            status[o] = "enabled"
                        else:
                            skip(o)
                    status[nid] = "done"
                elif n.get("test"):
                    do_test(nid, n)
                else:
                    status[nid] = "done"
                    result.setdefault(nid, True)
                break
        if outcome[0] is not None:
            return None
        done = [nid for nid in self.order if status[nid] == "done"]
        if not done:
            return None
        last = done[-1]
        anc = c.ancestors(last) | {last}
        notes = []
        for nid in self.order:
            if nid in anc and status[nid] in ("done", "failed") and nid in result and result[nid] is not True:
                notes.append(f"'{nid}' is {'negative' if result[nid] is False else 'not diagnostic'}")
        return last, ", ".join(notes[:3])

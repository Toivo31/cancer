"""Document format v1 (docs/platform/specs/01-flowchart-model.md): world and flowchart as JSON.

A *world* is a scenario without its flowcharts. A *flowchart document* lists nodes and first-class
edges instead of the engine's implicit ``after`` / ``after_any`` / ``after_optional`` / ``options``
fields. The engine's classes do not change; these functions convert in both directions and are
lossless for everything the engine reads (round trips give identical metrics, tests/test_documents.py).

    world, flowcharts = load_yaml_as_documents("scenarios/finland_lung.yaml")
    sc = documents_to_scenario(world, [flowcharts[0]])
    # sc.flowcharts["baseline"] is an ordinary engine Flowchart

Everything here is pure (dicts in, dicts or engine objects out) and has no web dependency.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import yaml

from .scenario import Scenario, scenario_from_dict

SCHEMA_VERSION = 1

# document node kinds -> engine node kinds (the engine still says "choice" for a decision point)
DOC_KINDS = ("step", "decision", "join", "milestone", "exit")
KIND_ALIASES = {"choice": "decision"}
EDGE_TYPES = ("required", "any", "optional", "option")
# engine node field that each edge type is stored in
_EDGE_FIELD = {"required": "after", "any": "after_any", "optional": "after_optional"}
_FIELD_EDGE = {v: k for k, v in _EDGE_FIELD.items()}

# node fields copied as they are (the rest, id/kind and the four edge lists, are handled below)
NODE_FIELDS = ("label", "test", "when", "availability", "outcome", "milestone", "retry", "stage")

# scenario keys that are not part of the world as such; ``flowcharts`` leaves, ``optimiser`` is renamed
_WORLD_RENAMES = {"optimiser": "constraints"}

DEFAULT_DECISION_POLICY = {"backend": "rule", "mode": "argmax", "points": {}}


class DocumentError(ValueError):
    """A document cannot be converted. ``problems`` use the shape of spec 01's validation list."""

    def __init__(self, problems: list[dict]):
        self.problems = problems
        super().__init__("; ".join(p.get("message", "") for p in problems) or "invalid document")


def problem(code: str, message: str, node: str | None = None, severity: str = "error", **extra) -> dict:
    d = {"severity": severity, "code": code, "message": message}
    if node is not None:
        d["node"] = node
    d.update(extra)
    return d


# ------------------------------------------------------------------------------------ small helpers

def canonical_json(doc) -> str:
    """Stable text form: same document, same text (used for hashes and the byte-identity checks)."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def doc_hash(doc) -> str:
    return hashlib.sha256(canonical_json(doc).encode()).hexdigest()[:16]


def humanise(identifier: str) -> str:
    s = identifier.replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def _flowchart_name(fid: str, description: str) -> str:
    return description if description and len(description) <= 60 else humanise(fid)


def normalise_kind(kind: str | None) -> str:
    k = kind or "step"
    return KIND_ALIASES.get(k, k)


def normalise_flowchart_doc(doc: dict) -> dict:
    """Copy of ``doc`` with kind aliases (``choice``) replaced and defaults filled in."""
    d = copy.deepcopy(doc)
    d.setdefault("schema_version", SCHEMA_VERSION)
    d["nodes"] = [{**n, "kind": normalise_kind(n.get("kind"))} for n in d.get("nodes") or []]
    d["edges"] = list(d.get("edges") or [])
    return d


# ------------------------------------------------------------------------- engine -> documents

def json_safe(obj):
    """Deep copy with text keys. YAML 1.1 reads an unquoted ``on:`` as ``True``; JSON cannot hold that,
    so booleans become ``"on"`` / ``"off"`` and other non-text keys become text (the engine's
    ``retry.on`` reads the same value either way)."""
    if isinstance(obj, dict):
        return {(("on" if k else "off") if isinstance(k, bool) else (k if isinstance(k, str) else str(k))): json_safe(v)
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return copy.deepcopy(obj)


def legacy_policy_to_decision_policy(policy: dict | None) -> dict:
    """Today's per-choice ``policy`` block as a ``rule`` decision policy (lossless: it is copied).

    Spec 02 also describes migrating ``mix`` / ``rules`` to stub probability tables; that belongs to
    the ``jev`` package. The rule form keeps every shipped scenario's numbers exactly.
    """
    return {"backend": "rule", "mode": "argmax", "points": copy.deepcopy(policy or {})}


def decision_policy_to_legacy(decision_policy: dict | None) -> dict:
    """Inverse of :func:`legacy_policy_to_decision_policy`; other backends give an empty policy."""
    dp = decision_policy or {}
    if dp.get("backend", "rule") != "rule":
        return {}
    return copy.deepcopy(dp.get("points") or {})


def scenario_to_world(sc: Scenario) -> dict:
    raw = {k: json_safe(v) for k, v in sc.raw.items() if k != "flowcharts"}
    world: dict = {"schema_version": SCHEMA_VERSION, "id": sc.id, "name": raw.pop("name", None) or humanise(sc.id)}
    for k, v in raw.items():
        if k == "id":
            continue
        world[_WORLD_RENAMES.get(k, k)] = v
    # the engine fills these defaults in; keep the document explicit about them
    world.setdefault("description", sc.description)
    world.setdefault("clock_start", sc.clock_start)
    world.setdefault("target_days", sc.target_days)
    world.setdefault("groups", copy.deepcopy(sc.groups))
    return world


def flowchart_to_document(fc, world_id: str | None = None, version: int = 1, parent_version: int | None = None) -> dict:
    """Engine :class:`~pathway_sim.scenario.Flowchart` -> flowchart document."""
    nodes, edges = [], []
    for n in fc.nodes.values():
        kind = "decision" if n.kind == "choice" else ("join" if n.kind == "step" and not n.test else n.kind)
        d: dict = {"id": n.id, "kind": kind}
        for k in NODE_FIELDS:
            v = getattr(n, k)
            if v:
                d[k] = json_safe(v)
        if n.fast_track:
            d["fast_track"] = True
        nodes.append(d)
        for fld, etype in _FIELD_EDGE.items():
            for src in getattr(n, fld):
                edges.append({"from": src, "to": n.id, "type": etype})
        for i, opt in enumerate(n.options):
            edges.append({"from": n.id, "to": opt, "type": "option", "index": i})
    doc = {
        "schema_version": SCHEMA_VERSION, "id": fc.id, "version": version, "parent_version": parent_version,
        "world_id": world_id, "name": _flowchart_name(fc.id, fc.description), "description": fc.description,
        "nodes": nodes, "edges": edges,
        "decision_policy": legacy_policy_to_decision_policy(json_safe(fc.policy)),
        "test_overrides": json_safe(fc.test_overrides), "resource_overrides": json_safe(fc.resource_overrides),
        "edits_from_parent": [],
    }
    return doc


def scenario_to_documents(sc: Scenario) -> tuple[dict, list[dict]]:
    world = scenario_to_world(sc)
    return world, [flowchart_to_document(fc, world["id"]) for fc in sc.flowcharts.values()]


def load_yaml_as_documents(path: str | Path) -> tuple[dict, list[dict]]:
    """Import a scenario YAML file (validated by the engine's loader) as world and flowchart documents."""
    from .scenario import load_scenario
    return scenario_to_documents(load_scenario(path))


def yaml_text_to_documents(text: str) -> tuple[dict, list[dict]]:
    """Import scenario YAML text (for the import endpoint). Never reads files named in the text."""
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise DocumentError([problem("schema", "The YAML must be a mapping with id, conditions and flowcharts")])
    return scenario_to_documents(scenario_from_dict(raw))


# ------------------------------------------------------------------------- documents -> engine

def world_to_raw(world: dict) -> dict:
    """World document -> the scenario dict the engine loads (without ``flowcharts``)."""
    back = {v: k for k, v in _WORLD_RENAMES.items()}
    return {back.get(k, k): copy.deepcopy(v) for k, v in world.items() if k != "schema_version"}


def flowchart_document_to_raw(doc: dict) -> dict:
    """Flowchart document -> the dict ``scenario.parse_flowchart`` takes. Raises :class:`DocumentError`."""
    doc = normalise_flowchart_doc(doc)
    problems: list[dict] = []
    nodes: dict[str, dict] = {}
    for nd in doc["nodes"]:
        nid = nd.get("id")
        if not nid or not isinstance(nid, str):
            problems.append(problem("schema", "Every node needs a text id"))
            continue
        if nid in nodes:
            problems.append(problem("duplicate_id", f"Two steps are called '{nid}'", node=nid))
            continue
        if nd["kind"] not in DOC_KINDS:
            problems.append(problem("schema", f"Unknown node kind '{nd['kind']}' (use one of {', '.join(DOC_KINDS)})", node=nid))
        n: dict = {"id": nid, "kind": "choice" if nd["kind"] == "decision" else ("step" if nd["kind"] == "join" else nd["kind"])}
        for k in NODE_FIELDS:
            if nd.get(k):
                n[k] = copy.deepcopy(nd[k])
        if nd.get("fast_track"):
            n["fast_track"] = True
        nodes[nid] = n
    lists: dict[str, dict[str, list]] = {nid: {"after": [], "after_any": [], "after_optional": []} for nid in nodes}
    options: dict[str, list[tuple[int, int, str]]] = {nid: [] for nid in nodes}
    for pos, e in enumerate(doc["edges"]):
        src, dst, etype = e.get("from"), e.get("to"), e.get("type", "required")
        if etype not in EDGE_TYPES:
            problems.append(problem("schema", f"Unknown connection type '{etype}' (use one of {', '.join(EDGE_TYPES)})", edge=e))
            continue
        missing = [x for x in (src, dst) if x not in nodes]
        if missing:
            for x in missing:
                problems.append(problem("unknown_reference", f"A connection points at '{x}', which is not a step", node=x if isinstance(x, str) else None, edge=e))
            continue
        if etype == "option":
            if nodes[src]["kind"] != "choice":
                problems.append(problem("option_of_non_decision", f"'{src}' offers '{dst}' as an option but is not a decision", node=src, edge=e))
                continue
            options[src].append((e.get("index") if isinstance(e.get("index"), int) else 10**6, pos, dst))
        else:
            lists[dst][_EDGE_FIELD[etype]].append(src)
    if problems:
        raise DocumentError(problems)
    out_nodes = []
    for nid, n in nodes.items():
        for fld, v in lists[nid].items():
            if v:
                n[fld] = v
        if options[nid]:
            n["options"] = [o for _i, _p, o in sorted(options[nid])]
        out_nodes.append(n)
    raw: dict = {"nodes": out_nodes}
    if doc.get("description"):
        raw["description"] = doc["description"]
    policy = decision_policy_to_legacy(doc.get("decision_policy"))
    if policy:
        raw["policy"] = policy
    if doc.get("test_overrides"):
        raw["test_overrides"] = copy.deepcopy(doc["test_overrides"])
    if doc.get("resource_overrides"):
        raw["resource_overrides"] = copy.deepcopy(doc["resource_overrides"])
    return raw


def documents_to_raw(world: dict, flowcharts: list[dict]) -> dict:
    raw = world_to_raw(world)
    fcs: dict = {}
    for doc in flowcharts:
        fid = doc.get("id")
        if not fid or fid in fcs:
            raise DocumentError([problem("duplicate_id" if fid else "schema", f"Flowchart id '{fid}' is missing or repeated")])
        fcs[fid] = flowchart_document_to_raw(doc)
    raw["flowcharts"] = fcs
    return raw


def documents_to_scenario(world: dict, flowcharts: list[dict]) -> Scenario:
    """World and flowchart documents -> engine objects. Raises :class:`DocumentError` for structural
    problems and ``ValueError`` (the engine's own checks) for semantic ones."""
    return scenario_from_dict(documents_to_raw(world, flowcharts))


def documents_to_yaml(world: dict, flowcharts: list[dict]) -> str:
    return yaml.safe_dump(documents_to_raw(world, flowcharts), sort_keys=False, allow_unicode=True)

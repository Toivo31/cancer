"""Document validation for the service: one function that returns every problem it can find.

Structural problems come from the converters (:class:`pathway_sim.documents.DocumentError`), the rest from
the engine's own checks. When ``pathway_sim.validate`` exists (spec 01, ticket M2-2) it is used instead of
the message matching below, so problem codes and hints come from one place.
"""

from __future__ import annotations

import re

from pathway_sim.documents import DocumentError, documents_to_scenario, problem

_PATTERNS = [
    (r"prevalences|server resource|resource \S+ has unknown type|batch resource|has unknown stage", "world_invalid"),
    (r"unknown test", "unknown_test"), (r"unknown resource|uses unknown resource", "unknown_resource"),
    (r"cycle through", "cycle"), (r"no exit node", "no_exit"), (r"bad guard", "guard_syntax"),
    (r"reads unknown names", "guard_unknown_name"), (r"choice needs", "decision_needs_two_options"),
    (r"option of two choices", "option_of_two_decisions"), (r"unknown node reference", "unknown_reference"),
    (r"names unknown options", "policy_unknown_option"), (r"exit needs outcome", "invalid_outcome"), (r"unknown kind", "unknown_kind"), (r"unknown stage", "unknown_stage"),
]
_NODE = re.compile(r"^[^/:]+/[^/:]+/([^/:]+): ")


def problems_from_value_error(e: ValueError, node_ids: set[str]) -> list[dict]:
    msg = str(e)
    code = next((c for pat, c in _PATTERNS if re.search(pat, msg)), "invalid")
    m = _NODE.match(msg)
    node = m.group(1) if m and m.group(1) in node_ids else None
    text = msg.split(": ", 2)[-1] if node else msg
    return [problem(code, text[:1].upper() + text[1:], node=node)]


def _policy_problems(sc, doc: dict) -> list[dict]:
    """Stub probability tables against the flowchart (jev's own checks), plus decisions without a table."""
    from jev.stub import StubBackend, StubTableError
    dp = doc.get("decision_policy") or {}
    if dp.get("backend", "stub") != "stub":
        return []
    points = dp.get("points") or {}
    out: list[dict] = []
    try:
        stub = StubBackend(points)
    except (StubTableError, KeyError, TypeError, AttributeError) as e:
        code = "guard_syntax" if "bad condition" in str(e) else "policy_probabilities"
        pt = str(e).split("/")[0].split(":")[0]
        return [problem(code, f"The probability tables cannot be read: {e}", node=pt if pt in sc.flowcharts[doc["id"]].nodes else None,
                        field="decision_policy.points")]
    fc = sc.flowcharts[doc["id"]]
    for msg in stub.validate_against(fc, sc):
        pt = msg.split(":")[0].split("/")[0]
        code = ("policy_not_decision" if "not a decision point" in msg else "policy_unknown_option" if "unknown options" in msg
                else "guard_unknown_name" if "unknown names" in msg else "policy_probabilities")
        out.append(problem(code, msg.split(": ", 1)[-1] if ": " in msg else msg, node=pt if pt in fc.nodes else None, field=f"decision_policy.points.{pt}"))
    for nid, n in fc.nodes.items():
        if n.kind == "choice" and nid not in points:
            out.append(problem("missing_probabilities", f"'{nid}' has no probabilities, so the options are equally likely", node=nid, severity="warning"))
    return out


def validate_documents(world: dict, flowcharts: list[dict]) -> list[dict]:
    """All problems for ``flowcharts`` in ``world`` (never raises for bad documents)."""
    try:
        from pathway_sim import validate as lib          # noqa: F401  (plat/expr, M2-2)
        fn = getattr(lib, "validate_documents", None)
        if fn is not None:
            return list(fn(world, flowcharts))
    except ImportError:
        pass
    node_ids = {n.get("id") for f in flowcharts for n in f.get("nodes", [])}
    try:
        sc = documents_to_scenario(world, flowcharts)
        return [p for d in flowcharts for p in _policy_problems(sc, d)]
    except DocumentError as e:
        return e.problems
    except ValueError as e:
        return problems_from_value_error(e, node_ids)
    except (KeyError, TypeError, AttributeError) as e:      # a malformed world: say so instead of a 500
        return [problem("schema", f"The document is missing or mis-typed a field: {e!r}")]


def has_errors(problems: list[dict]) -> bool:
    return any(p.get("severity", "error") == "error" for p in problems)

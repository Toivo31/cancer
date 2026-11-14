"""Document validation for the service: one function that returns every problem it can find.

Structural problems come from the converters (:class:`pathway_sim.documents.DocumentError`), the rest from
the engine's own checks. When ``pathway_sim.validate`` exists (spec 01, ticket M2-2) it is used instead of
the message matching below, so problem codes and hints come from one place.
"""

from __future__ import annotations

import re

from pathway_sim.documents import DocumentError, documents_to_scenario, problem

_PATTERNS = [
    (r"unknown test", "unknown_test"), (r"unknown resource|uses unknown resource", "unknown_resource"),
    (r"cycle through", "cycle"), (r"no exit node", "no_exit"), (r"bad guard", "guard_syntax"),
    (r"reads unknown names", "guard_unknown_name"), (r"choice needs", "decision_needs_two_options"),
    (r"option of two choices", "option_of_two_decisions"), (r"unknown node reference", "unknown_reference"),
    (r"names unknown options", "policy_unknown_option"), (r"exit needs outcome", "schema"),
]
_NODE = re.compile(r"^[^/:]+/[^/:]+/([^/:]+): ")


def problems_from_value_error(e: ValueError, node_ids: set[str]) -> list[dict]:
    msg = str(e)
    code = next((c for pat, c in _PATTERNS if re.search(pat, msg)), "invalid")
    m = _NODE.match(msg)
    node = m.group(1) if m and m.group(1) in node_ids else None
    text = msg.split(": ", 2)[-1] if node else msg
    return [problem(code, text[:1].upper() + text[1:], node=node)]


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
        documents_to_scenario(world, flowcharts)
    except DocumentError as e:
        return e.problems
    except ValueError as e:
        return problems_from_value_error(e, node_ids)
    except (KeyError, TypeError, AttributeError) as e:      # a malformed world: say so instead of a 500
        return [problem("schema", f"The document is missing or mis-typed a field: {e!r}")]
    return []


def has_errors(problems: list[dict]) -> bool:
    return any(p.get("severity", "error") == "error" for p in problems)

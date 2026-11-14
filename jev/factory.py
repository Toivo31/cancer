"""Build the engine policy for a flowchart from its ``decision_policy`` (spec 02).

``prepare(scenario, flowchart, ...)`` returns ``(flowchart, policy)``. The flowchart may be a
migrated copy (options reordered to follow each legacy ``mix``), so run the returned one::

    fc, pol = jev.prepare(sc, sc.flowcharts["baseline"], backend="stub")
    run = simulate(sc, fc, patients, policy=pol, seed=1)
"""

from __future__ import annotations

from pathway_sim.policy import RulePolicy

from .adapter import BackendPolicy
from .migrate import migrate_flowchart
from .stub import StubBackend


def set_probability(points: dict, point: str, option: str, prob: float) -> None:
    """Set one probability in a decision point's default row and rescale the others so the row
    sums to 1 (proportionally; equally if the others were all zero). Rules are left as they are."""
    if point not in points:
        raise ValueError(f"unknown decision point {point!r}; known: {sorted(points)}")
    row = points[point].setdefault("default", {})
    if option not in row:
        raise ValueError(f"{point}: unknown option {option!r}; known: {sorted(row)}")
    if not 0.0 <= prob <= 1.0:
        raise ValueError(f"probability must be between 0 and 1, not {prob}")
    rest = [o for o in row if o != option]
    old = sum(row[o] for o in rest)
    for o in rest:
        row[o] = (row[o] / old * (1 - prob)) if old > 0 else ((1 - prob) / len(rest) if rest else 0.0)
    row[option] = prob
    if not rest and abs(prob - 1.0) > 1e-9:
        raise ValueError(f"{point}: a one-option row must have probability 1")


def prepare(scenario, flowchart, backend: str | None = None, mode: str | None = None, seed: int = 0,
            sets: dict | None = None):
    """Policy for ``flowchart``.

    ``backend``: ``"stub"`` (default when the flowchart has a ``decision_policy`` or none), ``"rule"``
    (today's :class:`RulePolicy`, unchanged). ``mode``: ``"sample"`` or ``"argmax"``; default is
    the flowchart's ``decision_policy.mode``, else ``"sample"``. ``sets``: ``{(point, option): prob}``
    overrides applied to the stub table.
    """
    dp = flowchart.decision_policy or {}
    backend = backend or dp.get("backend", "stub")
    if backend == "rule":
        if sets:
            raise ValueError("--set needs the stub backend")
        return flowchart, RulePolicy(flowchart.policy, seed)
    if backend != "stub":
        raise ValueError(f"unknown backend {backend!r}")
    fc = migrate_flowchart(flowchart)
    points = fc.decision_policy["points"]
    for (pt, opt), p in (sets or {}).items():
        set_probability(points, pt, opt, p)
    stub = StubBackend(points)
    problems = stub.validate_against(fc, scenario)
    if problems:
        raise ValueError("decision_policy does not fit the flowchart: " + "; ".join(problems))
    mode = mode or fc.decision_policy.get("mode", "sample")
    return fc, BackendPolicy(stub, mode=mode, scenario=scenario, flowchart=fc)

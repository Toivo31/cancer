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
from .http import HttpBackend
from .local import RuleBackend
from .routing import RoutingBackend
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


def _make_backend(kind: str, cfg: dict, stub: StubBackend, where: str, flowchart=None, seed: int = 0):
    """One backend from its config (``decision_policy`` or a per-point override)."""
    if kind == "stub":
        return stub
    if kind == "rule":
        return RuleBackend(flowchart.policy if flowchart is not None else {}, seed)
    if kind == "local":
        from .local_model import backend_from_config       # a trained model carried in decision_policy.models (M6-7)
        return backend_from_config(cfg, where)
    if kind == "http":
        if not cfg.get("url"):
            raise ValueError(f"{where}: the http backend needs a url")
        on_error = cfg.get("on_error", "fail")
        return HttpBackend(cfg["url"], cfg.get("model"), timeout=float(cfg.get("timeout", 2.0)),
                           on_error=on_error, fallback=stub if on_error == "fallback_stub" else None)
    raise ValueError(f"{where}: unknown backend {kind!r}")


def prepare(scenario, flowchart, backend: str | None = None, mode: str | None = None, seed: int = 0,
            sets: dict | None = None, **options):
    """Policy for ``flowchart``.

    ``backend``: ``"stub"`` (default), ``"rule"`` (today's :class:`RulePolicy`, unchanged), ``"http"``
    or a URL ``"http://host:port"``. ``mode``: ``"sample"`` or ``"argmax"``; default is the
    flowchart's ``decision_policy.mode``, else ``"sample"``. ``sets``: ``{(point, option): prob}``
    overrides applied to the stub table. ``options`` (``url``, ``model``, ``on_error``, ``timeout``)
    override the flowchart's ``decision_policy`` for the default backend. Per-point overrides live in
    ``decision_policy.points.<point>.backend``.
    """
    dp = dict(flowchart.decision_policy or {})
    backend = backend or dp.get("backend", "stub")
    cfg = {**{k: v for k, v in dp.items() if k not in ("points", "backend", "mode")}, **options}
    if backend.startswith(("http://", "https://")):
        cfg["url"], backend = backend, "http"
    if backend == "rule":
        if sets:
            raise ValueError("--set needs the stub backend")
        return flowchart, RulePolicy(flowchart.policy, seed)
    fc = migrate_flowchart(flowchart)
    points = fc.decision_policy["points"]
    for (pt, opt), p in (sets or {}).items():
        set_probability(points, pt, opt, p)
    stub = StubBackend(points)
    problems = stub.validate_against(fc, scenario)
    if problems:
        raise ValueError("decision_policy does not fit the flowchart: " + "; ".join(problems))
    default = _make_backend(backend, cfg, stub, "decision_policy", flowchart, seed)
    routes = {}
    for pt, spec in points.items():
        kind = spec.get("backend")
        if kind and kind != backend:
            routes[pt] = _make_backend(kind, {**cfg, **{k: v for k, v in spec.items() if k not in ("default", "rules", "backend")}},
                                       stub, f"points.{pt}", flowchart, seed)
    be = RoutingBackend(default, routes) if routes else default
    mode = mode or fc.decision_policy.get("mode", "sample")
    return fc, BackendPolicy(be, mode=mode, scenario=scenario, flowchart=fc)

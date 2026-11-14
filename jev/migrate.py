"""Migration of today's scenario ``policy`` blocks (``mix``, ``rules``, ``prefer``, ``default``) to a
stub probability table (spec 02, "Migration of today's scenarios").

* ``mix`` becomes the table's ``default`` (zeros for options it does not name).
* ``rules`` with ``choose`` become stub rules with probability 1 on that option.
* ``prefer`` and ``default`` become probability 1 on that option (the first preferred one).
* A choice node with no policy entry gets probability 1 on its first option, which is what the
  rule policy does today ("without a rule the first option wins").

The legacy ``mix`` draw walks the mix in its listed order, the engine's sampling walks the node's
options in their order. :func:`migrate_flowchart` therefore reorders a node's options to follow its
``mix`` where the two differ, which keeps every choice identical to the rule policy's.

``prefer`` lists longer than one entry cannot express "the next one if the first is not on offer"
as probabilities; the stub then falls back to uniform with a ``missing_probabilities`` warning.
"""

from __future__ import annotations

from pathway_sim.scenario import Flowchart


def _onehot(options: list[str], pick: str) -> dict[str, float]:
    return {o: (1.0 if o == pick else 0.0) for o in options}


def table_from_policy(fc: Flowchart) -> dict:
    """Stub ``points`` for every decision node of ``fc``, derived from ``fc.policy``."""
    points: dict = {}
    for nid, n in fc.nodes.items():
        if n.kind != "choice":
            continue
        opts = list(n.options)
        cfg = (fc.policy or {}).get(nid) or {}
        point: dict = {}
        mix = cfg.get("mix")
        if mix:
            tot = sum(mix.values())
            point["default"] = {o: (mix[o] / tot if o in mix else 0.0) for o in opts}
        elif cfg.get("prefer"):
            point["default"] = _onehot(opts, next((o for o in cfg["prefer"] if o in opts), opts[0]))
        elif cfg.get("default") in opts:
            point["default"] = _onehot(opts, cfg["default"])
        else:
            point["default"] = _onehot(opts, opts[0])
        rules = [{"when": r["when"], "probs": _onehot(opts, r["choose"])} for r in cfg.get("rules") or []]
        if rules:
            point["rules"] = rules
        points[nid] = point
    return points


def migrate_flowchart(fc: Flowchart) -> Flowchart:
    """Copy of ``fc`` with ``decision_policy`` filled from its legacy ``policy`` block and node
    options reordered to follow each ``mix``. A flowchart that already has a ``decision_policy``
    keeps it (missing decision points are filled from ``policy``)."""
    new = fc.copy()
    for nid, cfg in (fc.policy or {}).items():
        mix = (cfg or {}).get("mix")
        node = new.nodes.get(nid)
        if mix and node is not None and set(mix) <= set(node.options):
            named = [o for o in mix if o in node.options]
            node.options = named + [o for o in node.options if o not in named]
    dp = dict(fc.decision_policy or {})
    points = table_from_policy(new)
    points.update(dp.get("points") or {})
    dp.setdefault("backend", "stub")
    dp.setdefault("mode", "sample")
    dp["points"] = points
    new.decision_policy = dp
    return new

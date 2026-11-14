"""Policies choose among the options a flowchart allows at a choice node.

A policy sees only revealed information (:class:`PatientView`), never the
patient's condition. The simulator takes the option with the highest
probability (ties broken by option order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PatientView:
    patient_id: int
    group: str
    age: int
    t_now: float                      # days since the patient's clock start
    node: str                         # the choice node being asked
    history: list[tuple] = field(default_factory=list)   # (node_id, test_id, result, t_since_start)
    attributes: dict = field(default_factory=dict)       # revealed attributes only

    def names(self) -> dict:
        d = {"group": self.group, "age": self.age, "t": self.t_now}
        d.update(self.attributes)
        for node_id, _test, result, _t in self.history:
            d[node_id] = result
        return d


class Policy(Protocol):
    def choose(self, view: PatientView, options: list[str]) -> dict[str, float]: ...


class _Names(dict):
    def __missing__(self, key):
        return None


class RulePolicy:
    """Rule-based policy from the flowchart's ``policy`` block.

    ``policy: {choice_node: {rules: [{when: "location == 'central'", choose: bronch}], default: ttnb}}``
    or ``{choice_node: {prefer: [a, b]}}``, or an observed practice mix
    ``{choice_node: {mix: {a: 0.7, b: 0.3}}}`` (deterministic per patient, used only to
    reproduce observed variation in a calibration baseline). Without a rule the first option wins.
    """

    def __init__(self, config: dict | None = None, seed: int = 0):
        self.config = config or {}
        self.seed = seed
        self._compiled: dict[str, list] = {}
        for node, c in self.config.items():
            self._compiled[node] = [(compile(r["when"], f"<rule {node}>", "eval"), r["choose"]) for r in c.get("rules", [])]

    def choose(self, view: PatientView, options: list[str]) -> dict[str, float]:
        c = self.config.get(view.node, {})
        pick = None
        names = _Names(view.names())
        for code, opt in self._compiled.get(view.node, []):
            if opt in options and eval(code, {"__builtins__": {}}, names):
                pick = opt
                break
        if pick is None and c.get("mix"):
            from .dists import uniform
            u, acc = uniform(self.seed, view.patient_id, "mix", view.node), 0.0
            tot = sum(c["mix"].values())
            for opt, w in c["mix"].items():
                acc += w / tot
                if u < acc and opt in options:
                    pick = opt
                    break
        if pick is None:
            for opt in c.get("prefer", []):
                if opt in options:
                    pick = opt
                    break
        if pick is None and c.get("default") in options:
            pick = c["default"]
        if pick is None:
            pick = options[0]
        return {o: (1.0 if o == pick else 0.0) for o in options}


class RandomPolicy:
    """Uniform over options; deterministic per (seed, patient, node). Used for exploration logs."""

    def __init__(self, seed: int = 0):
        self.seed = seed

    def choose(self, view: PatientView, options: list[str]) -> dict[str, float]:
        from .dists import uniform
        k = int(uniform(self.seed, view.patient_id, "policy", view.node) * len(options))
        return {o: (1.0 if i == k else 0.0) for i, o in enumerate(options)}

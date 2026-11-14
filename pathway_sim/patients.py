"""Synthetic patients with hidden truth and pre-drawn test results.

Each patient is generated from a true condition. The result of every test the
scenario knows about is drawn in advance, for several attempts, from that
condition using the test's ``p_positive`` (sensitivity for the target
condition, 1 - specificity otherwise) and ``p_nondiagnostic``. A rerun of the
same patients through another flowchart reveals the same results in a
different order.

Results are drawn independently given the condition and attributes (no
correlation between tests beyond what the condition explains). This is a
simplification, recorded in docs/decisions.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dists import sample, uniform
from .scenario import Scenario

MAX_ATTEMPTS = 4


@dataclass
class Patient:
    id: int
    condition: str            # hidden
    cancer: bool              # hidden
    group: str                # visible: presentation group
    age: int                  # visible
    arrival: float            # day
    attributes: dict = field(default_factory=dict)            # hidden until a test reveals them
    results: dict[str, list] = field(default_factory=dict)    # hidden, per test id, per attempt

    def to_dict(self) -> dict:
        return {
            "id": self.id, "condition": self.condition, "cancer": self.cancer, "group": self.group,
            "age": self.age, "arrival": round(self.arrival, 4), "attributes": self.attributes,
            "results": self.results,
        }


def _pick(weights: dict[str, float], u: float) -> str:
    total = sum(weights.values())
    acc = 0.0
    for k, w in weights.items():
        acc += w / total
        if u < acc:
            return k
    return list(weights)[-1]


def p_positive(test: dict, condition: str, attributes: dict) -> float:
    spec = test.get("p_positive")
    if spec is None:
        return 1.0
    p = spec.get(condition, spec.get("default", 0.0))
    if isinstance(p, dict):
        by = p["by"]
        p = p.get(attributes.get(by), p.get("default", 0.0))
    return float(p)


def _arrival(sc: Scenario, i: int, n: int, seed: int) -> float:
    a = sc.arrivals
    if "rate_per_day" in a:
        return None  # filled cumulatively by caller
    spread = float(a.get("spread_days", 365))
    return spread * uniform(seed, i, "arrival")


def generate_patients(sc: Scenario, n: int, seed: int) -> list[Patient]:
    """Deterministic in ``seed``. Patient ``i`` is the same in every call with the same seed."""
    patients = []
    t = 0.0
    prev = {c["id"]: float(c["prevalence"]) for c in sc.conditions}
    for i in range(n):
        cond_id = _pick(prev, uniform(seed, i, "condition"))
        cond = sc.condition(cond_id)
        # presentation group: share_by_condition for all but the last group, remainder to the last
        group = sc.groups[-1]["id"]
        u = uniform(seed, i, "group")
        acc = 0.0
        for g in sc.groups[:-1]:
            acc += float(g.get("share_by_condition", {}).get(cond_id, g.get("share", 0.0)))
            if u < acc:
                group = g["id"]
                break
        age = int(round(sample(cond.get("age", sc.age), uniform(seed, i, "age"))))
        attrs = {}
        for name, spec in sc.attributes.items():
            w = (cond.get("attributes") or {}).get(name) or spec["values"]
            attrs[name] = _pick(w, uniform(seed, i, "attr", name))
        if "rate_per_day" in sc.arrivals:
            t += sample({"dist": "exponential", "mean": 1.0 / float(sc.arrivals["rate_per_day"])},
                        uniform(seed, i, "interarrival"))
            arrival = t
        else:
            arrival = _arrival(sc, i, n, seed)
        results = {}
        for tid, test in sc.tests.items():
            p = p_positive(test, cond_id, attrs)
            nd = test.get("p_nondiagnostic", 0.0) or 0.0
            if isinstance(nd, dict):
                nd = nd.get(attrs.get(nd["by"]), nd.get("default", 0.0))
            pnd = float(nd)
            rs = []
            for k in range(MAX_ATTEMPTS):
                if uniform(seed, i, "nd", tid, k) < pnd:
                    rs.append(None)
                else:
                    rs.append(uniform(seed, i, "res", tid, k) < p)
            results[tid] = rs
        patients.append(Patient(i, cond_id, bool(cond.get("cancer", False)), group, age, arrival, attrs, results))
    return patients

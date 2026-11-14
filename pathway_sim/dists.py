"""Distributions sampled through common random numbers.

Every random quantity in a run is a deterministic function of
``(seed, patient_id, key)``. Two runs of the same patients through different
flowcharts therefore draw the same uniform for the same step and attempt, so a
before/after difference comes from the change, not from chance.
"""

from __future__ import annotations

import hashlib
import math
from statistics import NormalDist

_Z = NormalDist()
Z90 = _Z.inv_cdf(0.90)


def uniform(seed: int, patient_id: int, *key: object) -> float:
    """A uniform in (0, 1) that depends only on its arguments."""
    h = hashlib.blake2b(f"{seed}|{patient_id}|{'|'.join(map(str, key))}".encode(), digest_size=8)
    x = int.from_bytes(h.digest(), "big")
    return (x + 0.5) / 2**64


def sample(spec: dict | float | int | None, u: float) -> float:
    """Inverse-CDF sample from a distribution spec.

    Specs: ``{dist: fixed, value}``, ``{dist: lognormal, median, p90}``,
    ``{dist: uniform, low, high}``, ``{dist: exponential, mean}``,
    ``{dist: empirical, values: [...]}``. A bare number means fixed.
    """
    if spec is None:
        return 0.0
    if isinstance(spec, (int, float)):
        return float(spec)
    d = spec.get("dist", "fixed")
    if d == "fixed":
        return float(spec["value"])
    if d == "lognormal":
        m, p90 = float(spec["median"]), float(spec["p90"])
        if m <= 0:
            return 0.0
        sigma = math.log(p90 / m) / Z90 if p90 > m else 0.0
        return m * math.exp(sigma * _Z.inv_cdf(u))
    if d == "uniform":
        lo, hi = float(spec["low"]), float(spec["high"])
        return lo + (hi - lo) * u
    if d == "exponential":
        return -float(spec["mean"]) * math.log(1.0 - u)
    if d == "empirical":
        vals = sorted(float(v) for v in spec["values"])
        return vals[min(int(u * len(vals)), len(vals) - 1)]
    raise ValueError(f"unknown distribution {d!r}")


def validate(spec) -> None:
    """Raise if a distribution spec is malformed."""
    if spec is None or isinstance(spec, (int, float)):
        return
    sample(spec, 0.5)
    if spec.get("dist") == "lognormal" and float(spec["p90"]) < float(spec["median"]):
        raise ValueError(f"lognormal p90 < median in {spec}")

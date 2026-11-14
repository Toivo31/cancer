"""Cohort assembly (``cohort/1``): n patients drawn from a library to a scenario's prevalence.

A cohort is ``(library id, prevalence, n, seed)`` plus an arrival model. It needs no language model and no
network: patient ``i`` is a function of the spec and ``i`` only (invariant I2), so ``n = 2000`` starts with
the same 1000 patients as ``n = 1000``.

How a patient is drawn (keys are ``pathway_sim.dists.uniform(seed, i, key...)``, the simulator's own
common-random-number scheme):

1. **Condition, stratified.** Patients are grouped in blocks of ``BLOCK`` = 1000 consecutive indices. In each
   block the number of patients per primary condition is the prevalence times ``BLOCK``, rounded so that the
   expected quota is exact (rounding offset keyed ``(seed, block, "cohort_round")``), and the conditions are
   laid out in a random order (keyed ``(seed, block, "cohort_slot", s)``). So the shares of any cohort are
   within a fraction of a percentage point of the prevalence, instead of the binomial noise of independent draws
   (0.3 pp standard deviation at 25 % and n = 20 000, which a 0.5 pp test would fail one run in ten). A partial
   last block is the first positions of the block's order: unbiased, slightly noisy. Changing ``n`` changes no
   earlier patient. ``BLOCK`` is part of the cohort definition; changing it changes every cohort.
2. **Card, within the condition.** ``floor(u * m)`` with ``u`` keyed ``(seed, i, "card")`` among the ``m`` library
   cards of that primary condition (sorted by card id). A large cohort repeats cards; ``distinct_cards`` says how
   many different ones it used.
3. **Arrival day.** As in ``pathway_sim.patients``: ``{"spread_days": s}`` gives ``s * uniform(seed, i, "arrival")``
   (default s = 365), ``{"rate_per_day": r}`` a Poisson stream (cumulative exponential gaps keyed
   ``(seed, i, "interarrival")``). The arrival model is an argument, not part of ``CohortSpec`` (the shape is
   fixed by ``card.py``); it is stored on the cohort and goes into ``fingerprint()``.

A ``Cohort`` is hidden-side: it knows which card and which condition each patient has, for the simulator's
world and for scoring. The decision layer receives ``cohort.handle(i)`` (a ``RevealHandle``) and nothing else.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import math
from array import array
from dataclasses import dataclass, field
from typing import Any, Mapping

from pathway_sim.dists import sample, uniform

from .card import INITIAL_STATE, Card, CohortSpec
from .library import Library
from .reveal import RevealHandle

__all__ = ["Cohort", "CohortArrays", "CohortError", "draw_cohort", "BLOCK", "DEFAULT_ARRIVALS",
           "NEGATIVE", "POSITIVE", "NON_DIAGNOSTIC", "NO_ATTEMPT", "NO_RULE"]

BLOCK = 1000
DEFAULT_ARRIVALS: dict[str, float] = {"spread_days": 365.0}

#: Codes in ``CohortArrays.results`` (one byte per patient, test, attempt)
NEGATIVE, POSITIVE, NON_DIAGNOSTIC, NO_ATTEMPT, NO_RULE = 0, 1, 2, 3, 4


class CohortError(ValueError):
    """The spec cannot be drawn from this library."""


# ============================================================================ the compact form

@dataclass(frozen=True)
class CohortArrays:
    """What the simulator needs from a cohort, without report text. ``results`` is ``n * len(tests) * attempts``
    bytes, patient-major then test then attempt; codes: ``NEGATIVE`` 0, ``POSITIVE`` 1 (the test's
    ``positive_when`` read on the attempt's outputs), ``NON_DIAGNOSTIC`` 2, ``NO_ATTEMPT`` 3 (the card stores
    fewer attempts for this test), ``NO_RULE`` 4 (an ``ok`` attempt of a test without ``positive_when``)."""
    library_id: str
    catalogue_hash: str
    state: str
    n: int
    conditions: tuple[str, ...]          # vocabulary of primary condition ids
    condition: array                     # per patient (array of unsigned short): index into ``conditions``
    arrival: array                       # per patient: arrival day (float)
    card_index: array                    # per patient: position of the card in ``Library.cards``
    tests: tuple[str, ...]
    attempts: int
    results: bytes

    def code(self, patient: int, test: str | int, attempt: int) -> int:
        t = self.tests.index(test) if isinstance(test, str) else test
        if not 0 <= attempt < self.attempts:
            return NO_ATTEMPT
        return self.results[(patient * len(self.tests) + t) * self.attempts + attempt]

    def positive(self, patient: int, test: str | int, attempt: int) -> bool | None:
        """True / False for an ``ok`` attempt with a rule, None for non-diagnostic or missing."""
        c = self.code(patient, test, attempt)
        return None if c >= NON_DIAGNOSTIC else bool(c)

    @property
    def nbytes(self) -> int:
        """Bytes held by the arrays (the vocabulary is negligible)."""
        return len(self.results) + sum(len(a) * a.itemsize for a in (self.condition, self.arrival, self.card_index))


# ============================================================================ the cohort

@dataclass(frozen=True)
class Cohort:
    spec: CohortSpec
    arrivals: Mapping[str, float]
    library_id: str
    card_index: tuple[int, ...]          # per patient: position in library.cards
    condition: tuple[str, ...]           # per patient: primary condition id (hidden side)
    arrival: tuple[float, ...]           # per patient: arrival day
    library: Library = field(compare=False, repr=False, default=None)   # type: ignore[assignment]

    def __len__(self) -> int:
        return len(self.card_index)

    @property
    def n(self) -> int:
        return len(self.card_index)

    @property
    def distinct_cards(self) -> int:
        """How many different cards the cohort uses (every result should say it, with the library id)."""
        return len(set(self.card_index))

    def condition_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.condition:
            out[c] = out.get(c, 0) + 1
        return dict(sorted(out.items()))

    def card(self, i: int) -> Card:
        """Patient ``i``'s card. Hidden side: simulator world and scoring only."""
        return self.library.cards[self.card_index[i]]

    def handle(self, i: int) -> RevealHandle:
        """The only object the decision layer gets for patient ``i``. Its public label is ``P000042``, not the
        card id (the same card can be several patients, and a generated id could carry the condition)."""
        if not 0 <= i < self.n:
            raise IndexError(i)
        return RevealHandle(self.card(i), public_id=f"P{i:06d}")

    def fingerprint(self) -> str:
        """Hash of everything that defines the cohort's content: equal for two draws of the same spec."""
        h = hashlib.sha256()
        h.update(json.dumps({"spec": self.spec.to_json(), "arrivals": dict(self.arrivals),
                             "library": self.library_id}, sort_keys=True).encode())
        h.update(array("I", self.card_index).tobytes())
        h.update(array("d", self.arrival).tobytes())
        return h.hexdigest()[:16]

    def to_arrays(self, catalogue=None, state: str = INITIAL_STATE) -> CohortArrays:
        """The compact form for the simulator (no report text). ``catalogue`` defaults to the one the library
        was loaded with; it must match the library's catalogue hash. Per distinct card the codes are computed
        once, so the cost follows ``distinct_cards``, not ``n``."""
        catalogue = catalogue if catalogue is not None else self.library.catalogue
        if catalogue is None:
            raise CohortError("to_arrays needs the catalogue (pass it, or load the library with it)")
        if catalogue.version_hash != self.library.manifest.catalogue_hash:
            raise CohortError("catalogue differs from the one the library was made for")
        if state != INITIAL_STATE:
            raise CohortError(f"state {state!r} is not served yet")
        tests = tuple(catalogue.tests)
        attempts = max(t.max_attempts for t in catalogue.tests.values())
        table: dict[int, bytes] = {}
        for ci in set(self.card_index):
            obs = self.library.cards[ci].observations[state]
            row = bytearray(len(tests) * attempts)
            for ti, tid in enumerate(tests):
                stored = obs[tid]
                if len(stored) > attempts:
                    raise CohortError(f"card {self.library.cards[ci].id} stores {len(stored)} attempts of {tid}")
                for ai in range(attempts):
                    if ai >= len(stored):
                        code = NO_ATTEMPT
                    elif stored[ai].status != "ok":
                        code = NON_DIAGNOSTIC
                    else:
                        r = catalogue.tests[tid].is_positive(stored[ai].values)
                        code = NO_RULE if r is None else (POSITIVE if r else NEGATIVE)
                    row[ti * attempts + ai] = code
            table[ci] = bytes(row)
        vocab = tuple(sorted(set(self.condition)))
        pos = {c: k for k, c in enumerate(vocab)}
        return CohortArrays(
            library_id=self.library_id, catalogue_hash=catalogue.version_hash, state=state, n=self.n,
            conditions=vocab, condition=array("H", (pos[c] for c in self.condition)),
            arrival=array("d", self.arrival), card_index=array("I", self.card_index),
            tests=tests, attempts=attempts, results=b"".join(table[ci] for ci in self.card_index))


# ============================================================================ drawing

def _quotas(shares: list[tuple[str, float]], seed: int, block: int) -> list[tuple[str, int]]:
    """Patients per condition in one full block: ``floor(BLOCK * cum_share + r)`` differences with one keyed
    offset ``r`` per block, so each quota is unbiased and they sum to ``BLOCK``."""
    r = uniform(seed, block, "cohort_round")
    out, prev, cum = [], 0, 0.0
    for k, (cond, share) in enumerate(shares):
        cum += share
        edge = BLOCK if k == len(shares) - 1 else min(BLOCK, math.floor(BLOCK * cum + r))
        out.append((cond, max(edge - prev, 0)))
        prev = max(edge, prev)
    return out


def _block_conditions(shares, seed: int, block: int) -> list[str]:
    slots: list[str] = []
    for cond, q in _quotas(shares, seed, block):
        slots.extend([cond] * q)
    order = sorted(range(BLOCK), key=lambda s: uniform(seed, block, "cohort_slot", s))
    return [slots[s] for s in order]


def draw_cohort(library: Library, spec: CohortSpec, arrivals: Mapping[str, float] | None = None) -> Cohort:
    """Draw ``spec.n`` patients from ``library`` (see the module docstring). ``spec.prevalence`` is normalised;
    a condition with a positive share needs at least one card in the library. Raises ``CohortError``."""
    if spec.library_id != library.id:
        raise CohortError(f"spec is for library {spec.library_id}, got {library.id}")
    if spec.n < 0:
        raise CohortError("n must be >= 0")
    arrivals = dict(DEFAULT_ARRIVALS if arrivals is None else arrivals)
    if "rate_per_day" in arrivals:
        if not float(arrivals["rate_per_day"]) > 0:
            raise CohortError("rate_per_day must be positive")
    elif not float(arrivals.get("spread_days", 0)) > 0:
        raise CohortError("arrivals needs rate_per_day or a positive spread_days")
    if any(not math.isfinite(v) or v < 0 for v in spec.prevalence.values()):
        raise CohortError("prevalence shares must be finite and >= 0")
    total = sum(spec.prevalence.values())
    if not total > 0:
        raise CohortError("prevalence sums to zero")
    strata = library.by_condition
    shares = [(c, v / total) for c, v in sorted(spec.prevalence.items()) if v > 0]
    missing = [c for c, _ in shares if c not in strata]
    if missing:
        raise CohortError(f"library {library.id} has no cards for {missing} (has {sorted(strata)})")

    seed, n = spec.seed, spec.n
    conditions: list[str] = []
    for b in range((n + BLOCK - 1) // BLOCK):
        conditions.extend(_block_conditions(shares, seed, b)[: min(BLOCK, n - b * BLOCK)])
    card_index: list[int] = []
    for i, cond in enumerate(conditions):
        pool = strata[cond]
        card_index.append(pool[min(int(uniform(seed, i, "card") * len(pool)), len(pool) - 1)])
    arrival: list[float] = []
    t = 0.0
    for i in range(n):
        if "rate_per_day" in arrivals:
            t += sample({"dist": "exponential", "mean": 1.0 / float(arrivals["rate_per_day"])},
                        uniform(seed, i, "interarrival"))
            arrival.append(t)
        else:
            arrival.append(float(arrivals["spread_days"]) * uniform(seed, i, "arrival"))
    return Cohort(spec=spec, arrivals=arrivals, library_id=library.id, card_index=tuple(card_index),
                  condition=tuple(conditions), arrival=tuple(arrival), library=library)

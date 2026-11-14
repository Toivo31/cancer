"""Decision policy objects for non-rule backends, built by the ``jev`` package (spec 02).

``rule`` is the engine's own RulePolicy and needs nothing here. Anything else that ``jev`` cannot
build is refused with a clear message rather than silently falling back to rules (a silent fallback
would make a "JEV" run a lie).
"""

from __future__ import annotations


class BackendUnavailable(ValueError):
    code = "backend_unavailable"


def build_policy(sc, fc, doc: dict, seed: int):
    dp = doc.get("decision_policy") or {}
    backend = dp.get("backend", "rule")
    try:
        import jev
    except ImportError:
        raise BackendUnavailable(f"decision backend '{backend}' needs the jev package, which is not installed in this build") from None
    try:
        return jev.prepare(sc, fc, backend=backend, mode=dp.get("mode"), seed=seed)
    except (ValueError, jev.BackendError) as e:           # bad table, or a JEV address that cannot be reached
        raise BackendUnavailable(str(e)) from None

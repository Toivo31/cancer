"""Decision policy objects for non-rule backends.

The ``rule`` backend is the engine's own RulePolicy and needs nothing here. ``stub`` and ``http``
backends come from the ``jev`` package (plat/jev); until that is merged they are refused with a clear
message instead of silently falling back to rules (a silent fallback would make a "JEV" run a lie).
"""

from __future__ import annotations


class BackendUnavailable(ValueError):
    code = "backend_unavailable"


def build_policy(sc, fc, doc: dict, seed: int):
    dp = doc.get("decision_policy") or {}
    backend = dp.get("backend", "rule")
    try:
        import jev  # noqa: F401
    except ImportError:
        raise BackendUnavailable(f"decision backend '{backend}' needs the jev package, which is not installed in this build") from None
    raise BackendUnavailable(f"decision backend '{backend}' is not wired into the service yet")

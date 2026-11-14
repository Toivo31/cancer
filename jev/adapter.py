"""Adapter from a :class:`DecisionBackend` to the engine's ``Policy.choose(view, options)``.

The engine never imports this module. It only reads three optional attributes from the policy
object: ``decision_mode`` (``"sample"`` or ``"argmax"``), ``backend_name`` and ``model_id``; they
end up in the run log's ``choices`` entries.
"""

from __future__ import annotations

from .contract import (QUESTION_NEXT_STEP, BackendInfo, ContractError, DecisionBackend, DecisionRequest,
                       check_responses)

MODES = ("sample", "argmax")


def build_context(view) -> dict:
    """Context JSON from a ``PatientView``: revealed information only."""
    return {
        "group": view.group, "age": view.age, "t_days": round(float(view.t_now), 4),
        "fast_track": bool(view.priority),
        "attributes": dict(view.attributes),
        "history": [{"step": n, "test": t, "result": r, "t_days": tt} for n, t, r, tt in view.history],
    }


class OptionCatalogue:
    """Static option metadata (label, test, features) from the world's test catalogue.

    Built from a scenario and a flowchart; without them options carry only their id.
    """

    def __init__(self, scenario=None, flowchart=None):
        self.meta: dict[str, dict] = {}
        if scenario is None or flowchart is None:
            return
        for nid, n in flowchart.nodes.items():
            spec = {}
            if n.test:
                spec = {**scenario.tests.get(n.test, {}), **flowchart.test_overrides.get(n.test, {})}
            feats = {}
            if "invasive" in spec:
                feats["invasive"] = bool(spec["invasive"])
            if spec.get("cost_eur") is not None:
                feats["cost_eur"] = spec["cost_eur"]
            self.meta[nid] = {"label": n.label or nid, "test": n.test, "features": feats}

    def option(self, oid: str, lead_days: float | None) -> dict:
        m = self.meta.get(oid)
        o = {"id": oid}
        if m:
            o["label"], o["test"], feats = m["label"], m["test"], dict(m["features"])
        else:
            feats = {}
        if lead_days is not None:
            feats["lead_days"] = lead_days
        if feats:
            o["features"] = feats
        return o


class BackendPolicy:
    """Engine ``Policy`` backed by a :class:`DecisionBackend`.

    ``mode`` tells the engine how to turn the probabilities into a choice: ``"sample"`` (inverse CDF
    with the common-random-number draw) or ``"argmax"``. Responses are validated against the
    contract (exactly the offered ids, non-negative, sum 1 within 1e-6) before the engine sees them.
    """

    def __init__(self, backend: DecisionBackend, mode: str = "sample", scenario=None, flowchart=None,
                 question_type: str = QUESTION_NEXT_STEP):
        if mode not in MODES:
            raise ValueError(f"decision mode must be one of {MODES}, not {mode!r}")
        self.backend = backend
        self.decision_mode = mode
        self.question_type = question_type
        self.catalogue = OptionCatalogue(scenario, flowchart)
        self._info: BackendInfo = backend.info()
        self.last_explanation: str | None = None

    # attributes the engine reads for the run log
    @property
    def backend_name(self) -> str:
        return self._info.name

    @property
    def model_id(self) -> str:
        return self._info.model

    def request_for(self, view, options: list[str]) -> DecisionRequest:
        leads = getattr(view, "option_leads", None) or {}
        return DecisionRequest(
            request_id=f"p{view.patient_id}:{view.node}", decision_point=view.node,
            context=build_context(view), options=[self.catalogue.option(o, leads.get(o)) for o in options],
            question_type=self.question_type)

    def choose(self, view, options: list[str]) -> dict[str, float]:
        req = self.request_for(view, options)
        resp = check_responses([req], self.backend.decide([req]))[0]
        self.last_explanation = resp.explanation
        return resp.probs

    def run_summary(self) -> dict:
        """Backend counters for the run summary (cache hits, fallbacks, ...); empty if it has none."""
        fn = getattr(self.backend, "summary", None)
        return fn() if callable(fn) else {}


__all__ = ["BackendPolicy", "OptionCatalogue", "build_context", "MODES", "ContractError"]

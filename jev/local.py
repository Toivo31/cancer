"""In-process backends around existing engine policies.

* :class:`LocalBackend` wraps any ``Policy`` (typically ``decision_model.policy.ModelPolicy``, the
  numpy model) behind the contract: request in, probabilities out.
* :class:`RuleBackend` is today's :class:`RulePolicy` (``mix``, ``rules``, ``prefer``) as a backend.

Both rebuild a ``PatientView`` from the request, so they see exactly the revealed information that
travelled through the contract and nothing else.
"""

from __future__ import annotations

import re

from pathway_sim.policy import PatientView, RulePolicy

from .contract import BackendInfo, DecisionRequest, DecisionResponse

_PID = re.compile(r"^p(\d+):")


def view_from_request(req: DecisionRequest) -> PatientView:
    c = req.context
    m = _PID.match(req.request_id)
    leads = {o["id"]: o["features"]["lead_days"] for o in req.options if "lead_days" in (o.get("features") or {})}
    return PatientView(
        patient_id=int(m.group(1)) if m else 0, group=c.get("group"), age=c.get("age"),
        t_now=float(c.get("t_days") or 0.0), node=req.decision_point,
        history=[(h["step"], h.get("test"), h.get("result"), h.get("t_days")) for h in c.get("history") or []],
        attributes=dict(c.get("attributes") or {}), priority=bool(c.get("fast_track")),
        offered=req.option_ids, option_leads=leads)


class LocalBackend:
    """Wrap an engine ``Policy`` as a backend. ``policy.choose(view, options)`` must return
    probabilities over ``options``."""

    def __init__(self, policy, model: str = "local@1", deterministic: bool = True,
                 context_fields: list[str] | None = None):
        self.policy, self.model, self.deterministic, self.context_fields = policy, model, deterministic, context_fields

    def info(self) -> BackendInfo:
        return BackendInfo("local", self.model, self.deterministic, self.context_fields)

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        return [DecisionResponse(q.request_id, dict(self.policy.choose(view_from_request(q), q.option_ids)))
                for q in requests]

    def summary(self) -> dict:
        n = getattr(self.policy, "n_fallbacks", 0)
        return {"model_fallbacks": n} if n else {}


class RuleBackend(LocalBackend):
    """Today's rule policy (``mix``/``rules``/``prefer``/``default``) behind the contract.
    ``mix`` draws from ``(seed, patient)``, so ``request_id`` must start with ``p<patient id>:``."""

    def __init__(self, config: dict | None = None, seed: int = 0, model: str = "rule@1"):
        super().__init__(RulePolicy(config or {}, seed), model, True, None)

    def info(self) -> BackendInfo:
        return BackendInfo("rule", self.model, True, None)

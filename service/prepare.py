"""Documents to something the engine can run, and "try a decision" (no web code here; used by the routers).

``prepare_run`` is what a run or an optimisation calls: it applies the decision policy (the flowchart's own, or an
override for this run), converts the documents and returns ``(scenario, flowchart, policy)`` ready for
``simulate(scenario, flowchart, patients, policy=policy, seed=seed)``. The flowchart returned may be a migrated
copy, so always simulate that one.
"""

from __future__ import annotations

import copy

import jev
from jev.adapter import BackendPolicy, OptionCatalogue
from jev.contract import DecisionRequest, check_responses
from pathway_sim.documents import documents_to_scenario, normalise_flowchart_doc
from pathway_sim.policy import PatientView, RulePolicy

from .errors import ApiError


def prepare_run(world: dict, flowchart_doc: dict, decision_policy: dict | None = None, seed: int = 0):
    """``(scenario, flowchart, policy)``. ``decision_policy`` replaces the document's for this run only."""
    doc = normalise_flowchart_doc(flowchart_doc)
    if decision_policy is not None:
        doc["decision_policy"] = copy.deepcopy(decision_policy)
    sc = documents_to_scenario(world, [doc])
    fc, policy = jev.prepare(sc, sc.flowcharts[doc["id"]], seed=seed)
    return sc, fc, policy


DEFAULT_CONTEXT = {"group": None, "age": 65, "t_days": 0.0, "fast_track": False, "attributes": {}, "history": []}


def decide(world: dict, flowchart_doc: dict, decision_point: str, context: dict | None = None,
           offered: list[str] | None = None, option_leads: dict | None = None, decision_policy: dict | None = None) -> dict:
    """Probabilities for one hand-entered context at one decision point (ticket M2-8)."""
    sc, fc, policy = prepare_run(world, flowchart_doc, decision_policy)
    node = fc.nodes.get(decision_point)
    if node is None or node.kind != "choice":
        raise ApiError(422, "unknown_decision_point", f"'{decision_point}' is not a decision point of this flowchart",
                       [{"severity": "error", "code": "unknown_reference", "message": f"Decision points: {', '.join(n.id for n in fc.nodes.values() if n.kind == 'choice')}"}])
    options = list(node.options)
    on_offer = list(offered) if offered is not None else options
    bad = [o for o in on_offer if o not in options]
    if bad or not on_offer:
        raise ApiError(422, "invalid_offered", f"'offered' must be a non-empty subset of {options}")
    on_offer = [o for o in options if o in on_offer]          # keep the decision's own order
    ctx = {**DEFAULT_CONTEXT, **{k: v for k, v in (context or {}).items() if v is not None}}
    if ctx["group"] is None:
        ctx["group"] = (sc.groups[0] or {}).get("id")
    leads = option_leads or {}
    if isinstance(policy, BackendPolicy):
        req = DecisionRequest(request_id="try", decision_point=decision_point, context=ctx,
                              options=[OptionCatalogue(sc, fc).option(o, leads.get(o)) for o in on_offer])
        resp = check_responses([req], policy.backend.decide([req]))[0]
        probs, why = resp.probs, resp.explanation
        backend, model, mode = policy.backend_name, policy.model_id, policy.decision_mode
    elif isinstance(policy, RulePolicy):
        view = PatientView(patient_id=0, group=ctx["group"], age=ctx["age"], t_now=ctx["t_days"], node=decision_point,
                           history=[(h["step"], h.get("test"), h.get("result"), h.get("t_days", 0.0)) for h in ctx["history"]],
                           attributes=dict(ctx["attributes"]), priority=ctx["fast_track"], offered=on_offer, option_leads=leads)
        probs, why, backend, model, mode = policy.choose(view, on_offer), "legacy rule policy (a draw for mix entries is made per patient)", "rule", "rule@1", "argmax"
    else:
        raise ApiError(422, "unsupported_backend", "This decision backend cannot be tried from here yet")
    cat = OptionCatalogue(sc, fc)
    return {
        "decision_point": decision_point, "backend": backend, "model": model, "mode": mode, "explanation": why,
        "options": [{"id": o, "label": (cat.meta.get(o) or {}).get("label") or o, "offered": o in on_offer,
                     "probability": float(probs.get(o, 0.0))} for o in options],
        "context_used": ctx,
    }

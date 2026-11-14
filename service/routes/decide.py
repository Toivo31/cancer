"""Try a decision (ticket M2-8): what the flowchart's decision policy says for one hand-entered context."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pathway_sim.documents import DocumentError, normalise_flowchart_doc

from ..deps import get_project, get_store
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..models import DecideRequest, DecideResponse, FlowchartRef
from ..prepare import decide
from ..store import NotFound, Store
from ..validation import has_errors, problems_from_value_error, validate_documents

router = APIRouter(tags=["decisions"], responses=ERROR_RESPONSES)


@router.post("/projects/{p}/decide", response_model=DecideResponse)
def try_a_decision(req: DecideRequest, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Probabilities per option at one decision point for the context you enter. ``flowchart`` is
    ``{"id", "version"?}`` of a stored flowchart or a whole document (an unsaved edit)."""
    world, _ = store.get_world(project["id"])
    if isinstance(req.flowchart, FlowchartRef):
        try:
            doc, _info = store.get_version(project["id"], req.flowchart.id, req.flowchart.version)
        except NotFound:
            raise not_found("flowchart version", f"{req.flowchart.id}/{req.flowchart.version or 'latest'}") from None
    else:
        doc = normalise_flowchart_doc({**req.flowchart.to_dict(), "world_id": world["id"]})
    problems = validate_documents(world, [doc])
    if has_errors(problems):
        raise ApiError(422, "invalid_document", "The flowchart has problems", problems)
    try:
        return decide(world, doc, req.decision_point, req.context, req.offered, req.option_leads, req.decision_policy)
    except DocumentError as e:
        raise ApiError(422, "invalid_document", str(e), e.problems) from None
    except ValueError as e:                    # the stub table does not fit the flowchart, and the like
        raise ApiError(422, "invalid_document", str(e), problems_from_value_error(e, {n["id"] for n in doc["nodes"]})) from None

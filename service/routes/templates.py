from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_templates
from ..errors import ERROR_RESPONSES, not_found
from ..models import TemplateDetail, TemplateSummary

router = APIRouter(tags=["templates"], responses=ERROR_RESPONSES)


def _summary(t: dict) -> dict:
    return {"id": t["id"], "name": t["name"], "description": t["description"], "world_id": t["world"]["id"],
            "flowcharts": [{"id": f["id"], "name": f.get("name") or f["id"], "description": f.get("description"),
                            "nodes": len(f["nodes"])} for f in t["flowcharts"]]}


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(templates: dict = Depends(get_templates)):
    """Built-in worlds and flowcharts (the Finnish scenario and the Norway check), converted from the YAML."""
    return [_summary(t) for t in templates.values()]


@router.get("/templates/{template_id}", response_model=TemplateDetail, response_model_exclude_unset=True)
def get_template(template_id: str, templates: dict = Depends(get_templates)):
    t = templates.get(template_id)
    if t is None:
        raise not_found("template", template_id)
    return {**_summary(t), "world": t["world"], "flowchart_documents": t["flowcharts"]}

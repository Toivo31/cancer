"""Projects, the world document, flowcharts and their versions, and validation (spec 03; tickets M2-3, M2-4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from pathway_sim.documents import DocumentError, normalise_flowchart_doc

from ..config import Settings
from ..deps import get_project, get_settings, get_store, get_templates
from ..errors import ERROR_RESPONSES, ApiError, not_found
from ..models import (FlowchartDocument, FlowchartSummary, FlowchartWithLatest, ProjectCreate, ProjectDetail,
                      ProjectRename, ProjectSummary, ValidateRequest, ValidationResult, VersionInfo, WorldDocument,
                      WorldResponse)
from ..store import Conflict, NotFound, Store
from ..templates import template_copy
from ..validation import has_errors, validate_documents

router = APIRouter(tags=["projects"], responses=ERROR_RESPONSES)
DOC = {"response_model_exclude_unset": True}


# ----------------------------------------------------------------------------------------- helpers

def _unprocessable(problems: list[dict], message: str = "The document has problems") -> ApiError:
    return ApiError(422, "invalid_document", message, problems)


def _checked_flowchart(store: Store, pid: str, doc: FlowchartDocument, fid: str | None = None) -> dict:
    """Dict of ``doc`` tied to the project's world, or 422 with the full problem list."""
    d = doc.to_dict()
    if fid is not None and d["id"] != fid:
        raise _unprocessable([{"severity": "error", "code": "id_mismatch",
                               "message": f"The document is called '{d['id']}' but is being saved as '{fid}'"}])
    world, _rev = store.get_world(pid)
    d["world_id"] = world["id"]
    d = normalise_flowchart_doc(d)
    problems = validate_documents(world, [d])
    if has_errors(problems):
        raise _unprocessable(problems)
    return d


def _detail(store: Store, project: dict) -> dict:
    return {**project, "flowcharts": store.list_flowcharts(project["id"])}


def _version_number(v: str) -> int | None:
    if v == "latest":
        return None
    try:
        n = int(v)
    except ValueError:
        raise ApiError(422, "invalid_version", f"'{v}' is not a version number or 'latest'") from None
    if n < 1:
        raise ApiError(422, "invalid_version", "Versions start at 1")
    return n


def _get_version(store: Store, p: str, f: str, v: str) -> tuple[dict, dict]:
    try:
        return store.get_version(p, f, _version_number(v))
    except NotFound:
        raise not_found("flowchart version", f"{f}/{v}") from None


# ----------------------------------------------------------------------------------------- projects

@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(store: Store = Depends(get_store)):
    return store.list_projects()


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_project(req: ProjectCreate, store: Store = Depends(get_store), settings: Settings = Depends(get_settings),
                   templates: dict = Depends(get_templates)):
    """New project, copied from a template (``template``: an id from ``GET /templates``). A name that is
    already taken gets ' (2)' appended; the response carries the name that was kept."""
    if req.template is None:
        raise ApiError(422, "template_required", "Pick a template; blank projects are not supported yet",
                       [{"severity": "error", "code": "template_required", "message": "template is required"}])
    t = templates.get(req.template)
    if t is None:
        raise not_found("template", req.template)
    world, fcs = template_copy(t)
    for f in fcs:
        f["world_id"] = world["id"]
    try:
        project = store.create_project(req.name, world, fcs, template=req.template, max_projects=settings.max_projects)
    except Conflict as e:
        raise ApiError(429, e.code, str(e)) from None
    return _detail(store, project)


@router.get("/projects/{p}", response_model=ProjectDetail)
def get_project_detail(project: dict = Depends(get_project), store: Store = Depends(get_store)):
    return _detail(store, project)


@router.patch("/projects/{p}", response_model=ProjectSummary)
def rename_project(req: ProjectRename, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    return store.rename_project(project["id"], req.name.strip() or project["name"])


@router.delete("/projects/{p}", status_code=204)
def delete_project(project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Deletes the project with its world, flowcharts, runs and stored results."""
    store.delete_project(project["id"])
    return Response(status_code=204)


# ----------------------------------------------------------------------------------------- world

@router.get("/projects/{p}/world", response_model=WorldResponse, **DOC)
def get_world(project: dict = Depends(get_project), store: Store = Depends(get_store)):
    world, rev = store.get_world(project["id"])
    return {"world": world, "rev": rev, "problems": []}


@router.put("/projects/{p}/world", response_model=WorldResponse, **DOC)
def put_world(doc: WorldDocument, if_rev: int | None = Query(None, description="Refuse (409) if the world has moved on since this revision"),
              project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Replace the world. A world that fails validation is refused (422). Flowcharts that no longer fit
    the new world (a test they use was removed, say) do not block the save; they come back in ``problems``."""
    new = doc.to_dict()
    old, _ = store.get_world(project["id"])
    if new["id"] != old["id"]:
        raise _unprocessable([{"severity": "error", "code": "world_id_changed", "message": f"The world is '{old['id']}' and cannot be renamed to '{new['id']}'"}])
    problems = validate_documents(new, [])
    if has_errors(problems):
        raise _unprocessable(problems, "The world has problems")
    try:
        rev = store.put_world(project["id"], new, if_rev)
    except Conflict as e:
        raise ApiError(409, e.code, str(e)) from None
    affected = []
    for fc in store.list_flowcharts(project["id"]):
        latest, _ = store.get_version(project["id"], fc["id"])
        affected += [{**p, "flowchart": fc["id"]} for p in validate_documents(new, [latest])]
    return {"world": new, "rev": rev, "problems": affected}


# ----------------------------------------------------------------------------------------- flowcharts

@router.get("/projects/{p}/flowcharts", response_model=list[FlowchartWithLatest], **DOC)
def list_flowcharts(project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Every flowchart with its versions and its latest version's document."""
    return [{**fc, "latest": store.get_version(project["id"], fc["id"])[0]} for fc in store.list_flowcharts(project["id"])]


@router.post("/projects/{p}/flowcharts", response_model=FlowchartDocument, status_code=201, **DOC)
def create_flowchart(doc: FlowchartDocument, project: dict = Depends(get_project), store: Store = Depends(get_store),
                     settings: Settings = Depends(get_settings)):
    """New flowchart; the document is stored as version 1. 409 if the id exists in this project."""
    d = _checked_flowchart(store, project["id"], doc)
    try:
        return store.create_flowchart(project["id"], d)
    except Conflict as e:
        raise ApiError(409, e.code, str(e)) from None


@router.get("/projects/{p}/flowcharts/{f}", response_model=FlowchartWithLatest, **DOC)
def get_flowchart(f: str, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    fc = next((x for x in store.list_flowcharts(project["id"]) if x["id"] == f), None)
    if fc is None:
        raise not_found("flowchart", f)
    return {**fc, "latest": store.get_version(project["id"], f)[0]}


@router.delete("/projects/{p}/flowcharts/{f}", status_code=204)
def delete_flowchart(f: str, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Only while no version of it has been used in a run (409 otherwise)."""
    try:
        store.delete_flowchart(project["id"], f)
    except NotFound:
        raise not_found("flowchart", f) from None
    except Conflict as e:
        raise ApiError(409, e.code, str(e)) from None
    return Response(status_code=204)


@router.get("/projects/{p}/flowcharts/{f}/versions", response_model=list[VersionInfo])
def list_versions(f: str, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    fc = next((x for x in store.list_flowcharts(project["id"]) if x["id"] == f), None)
    if fc is None:
        raise not_found("flowchart", f)
    return fc["versions"]


@router.get("/projects/{p}/flowcharts/{f}/versions/{v}", response_model=FlowchartDocument, **DOC)
def get_version(f: str, v: str, response: Response, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """One version (``v`` is a number or ``latest``). Header ``X-Version-Locked`` says whether it can still be edited."""
    doc, info = _get_version(store, project["id"], f, v)
    response.headers["X-Version-Locked"] = "true" if info["locked"] else "false"
    return doc


@router.post("/projects/{p}/flowcharts/{f}/versions", response_model=FlowchartDocument, status_code=201, **DOC)
def add_version(f: str, doc: FlowchartDocument, project: dict = Depends(get_project), store: Store = Depends(get_store),
                settings: Settings = Depends(get_settings)):
    """Save the document as version n+1; the server sets ``version`` and ``parent_version``."""
    d = _checked_flowchart(store, project["id"], doc, fid=f)
    try:
        return store.add_version(project["id"], f, d, settings.max_versions_per_flowchart)
    except NotFound:
        raise not_found("flowchart", f) from None
    except Conflict as e:
        raise ApiError(429, e.code, str(e)) from None


@router.put("/projects/{p}/flowcharts/{f}/versions/{v}", response_model=FlowchartDocument, **DOC)
def replace_version(f: str, v: int, doc: FlowchartDocument, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Overwrite a version that no run has used yet. 409 ``version_locked`` once a run has used it."""
    d = _checked_flowchart(store, project["id"], doc, fid=f)
    try:
        return store.replace_version(project["id"], f, v, d)
    except NotFound:
        raise not_found("flowchart version", f"{f}/{v}") from None
    except Conflict as e:
        raise ApiError(409, e.code, str(e)) from None


# ----------------------------------------------------------------------------------------- validate

@router.post("/projects/{p}/validate", response_model=ValidationResult, response_model_exclude_unset=True)
def validate(req: ValidateRequest, project: dict = Depends(get_project), store: Store = Depends(get_store)):
    """Every problem in the flowchart (and world, if one is sent) at once. Never stores anything."""
    world = req.world.to_dict() if req.world else store.get_world(project["id"])[0]
    fc = normalise_flowchart_doc({**req.flowchart.to_dict(), "world_id": world["id"]})
    problems = validate_documents(world, [fc])
    return {"ok": not has_errors(problems), "problems": problems}

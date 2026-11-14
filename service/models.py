"""Request and response models shared by the routers. Documents are loose on purpose: unknown keys survive
(``extra="allow"``) and only fields the client set are written back (``exclude_unset``), so a document a
client sends is the document it gets back."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NodeKind = Literal["step", "decision", "join", "milestone", "exit", "choice"]
EdgeType = Literal["required", "any", "optional", "option"]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class FlowNode(_Loose):
    id: str
    kind: NodeKind = "step"
    label: str | None = None
    test: str | None = None
    when: str | None = None
    availability: dict[str, Any] | None = None
    outcome: str | None = None
    milestone: str | None = None
    retry: dict[str, Any] | None = None
    stage: str | None = None
    fast_track: bool | None = None
    ui: dict[str, Any] | None = None


class FlowEdge(_Loose):
    from_: str = Field(alias="from")
    to: str
    type: EdgeType = "required"
    index: int | None = None


class FlowchartDocument(_Loose):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    version: int | None = None
    parent_version: int | None = None
    world_id: str | None = None
    name: str | None = None
    description: str | None = None
    nodes: list[FlowNode]
    edges: list[FlowEdge] = []
    decision_policy: dict[str, Any] | None = None
    test_overrides: dict[str, Any] | None = None
    resource_overrides: dict[str, Any] | None = None
    edits_from_parent: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, exclude_unset=True)


class WorldDocument(_Loose):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str | None = None
    description: str | None = None
    clock_start: str | None = None
    target_days: int | float | None = None
    arrivals: dict[str, Any] | None = None
    warmup_days: int | float | None = None
    default_n: int | None = None
    conditions: list[dict[str, Any]]
    groups: list[dict[str, Any]] | None = None
    attributes: dict[str, Any] | None = None
    age: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    tests: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, exclude_unset=True)


class Problem(_Loose):
    severity: Literal["error", "warning"] = "error"
    code: str
    message: str
    node: str | None = None
    hint: str | None = None
    flowchart: str | None = None
    edge: dict[str, Any] | None = None
    field: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    problems: list[Problem]


# ------------------------------------------------------------------------------- projects

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    template: str | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class ProjectRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class VersionInfo(BaseModel):
    version: int
    parent_version: int | None = None
    created_at: str
    locked: bool = False


class FlowchartSummary(BaseModel):
    id: str
    name: str
    latest_version: int
    versions: list[VersionInfo]


class FlowchartWithLatest(FlowchartSummary):
    latest: FlowchartDocument


class ProjectSummary(BaseModel):
    id: str
    name: str
    template: str | None = None
    world_id: str | None = None
    world_rev: int
    created_at: str
    updated_at: str


class ProjectDetail(ProjectSummary):
    flowcharts: list[FlowchartSummary]


class WorldResponse(BaseModel):
    world: WorldDocument
    rev: int
    problems: list[Problem] = []      # flowcharts that no longer fit this world (saved anyway; fix them)


class ValidateRequest(BaseModel):
    world: WorldDocument | None = None
    flowchart: FlowchartDocument


# ------------------------------------------------------------------------------- templates

class TemplateFlowchart(BaseModel):
    id: str
    name: str
    description: str | None = None
    nodes: int


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    world_id: str
    flowcharts: list[TemplateFlowchart]


class TemplateDetail(TemplateSummary):
    world: WorldDocument
    flowchart_documents: list[FlowchartDocument]


# ------------------------------------------------------------------------------- try a decision

class FlowchartRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: int | None = None          # default: the latest version


class DecideRequest(BaseModel):
    flowchart: FlowchartRef | FlowchartDocument
    decision_point: str
    context: dict[str, Any] = Field(default_factory=dict, description="group, age, t_days, fast_track, attributes {name: value}, "
                                    "history [{step, test, result, t_days}]; anything left out gets a default (see context_used)")
    offered: list[str] | None = Field(None, description="Options on offer; default all of the decision's options")
    option_leads: dict[str, float] | None = Field(None, description="Days until the earliest appointment per option (queue state)")
    decision_policy: dict[str, Any] | None = Field(None, description="Use this policy instead of the flowchart's")


class DecideOption(BaseModel):
    id: str
    label: str
    offered: bool
    probability: float


class DecideResponse(BaseModel):
    decision_point: str
    backend: str
    model: str
    mode: str
    explanation: str | None = None
    options: list[DecideOption]
    context_used: dict[str, Any]

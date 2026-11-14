"""Public demo contracts: observations and allowed choices, never hidden labels."""
from typing import Annotated, Literal, Any
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Choice(Contract):
    id: Identifier
    text: Text


class Question(Contract):
    id: Identifier
    text: Text
    choices: list[Choice] = Field(min_length=2, max_length=16)
    candidate_format: Literal['newline', 'inline'] = 'newline'

    @model_validator(mode='after')
    def distinct_choices(self):
        if len({c.id for c in self.choices}) != len(self.choices):
            raise ValueError('Choice IDs must be distinct within a question')
        return self


class ScoreRequest(Contract):
    context: Text
    questions: list[Question] = Field(min_length=1, max_length=32)
    image_ids: list[Identifier] = Field(default_factory=list, max_length=4)
    case_id: Identifier | None = None

    @model_validator(mode='after')
    def distinct_questions(self):
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError('Question IDs must be distinct')
        return self


class Evidence(Contract):
    source_id: Identifier
    text: Text
    available_at_step: int = Field(ge=0)


class CaseState(Contract):
    case_id: Identifier
    context: Text
    step: int = Field(ge=0)
    evidence: list[Evidence] = Field(default_factory=list, max_length=128)
    image_ids: list[Identifier] = Field(default_factory=list, max_length=4)


class Action(Contract):
    id: Identifier
    description: Text
    next: Identifier


class Node(Contract):
    terminal: bool = False
    question: Text | None = None
    protocol: Text | None = None
    actions: list[Action] = Field(default_factory=list, max_length=16)


class Workflow(Contract):
    id: Identifier
    version: Identifier
    root: Identifier
    nodes: dict[str, Node] = Field(min_length=1, max_length=128)


class CompletedStep(Contract):
    node_id: Identifier
    action_id: Identifier


class PathwayRequest(Contract):
    case: CaseState
    workflow: Workflow
    node_id: Identifier
    history: list[CompletedStep] = Field(default_factory=list, max_length=64)


class Review(Contract):
    question_id: Identifier
    action_id: Identifier
    reviewer: Identifier
    note: str = Field(default='', max_length=4000)


class ScoredChoice(Choice):
    score: float = Field(ge=0, le=1)


class ScoredQuestion(Contract):
    id: Identifier
    text: Text
    candidate_format: Literal['newline', 'inline']
    choices: list[ScoredChoice]
    proposed_action_id: Identifier
    score_margin: float = Field(ge=0, le=1)


class BackendInfo(Contract):
    mode: Literal['fixture', 'model']
    model: str
    checkpoint_sha256: str
    step: int | None
    revision: str | None = None
    training_identity: str | None = None
    quantization: str | None = None


class DecisionResponse(Contract):
    id: str
    created_at: str
    case_id: str | None
    backend: BackendInfo
    score_kind: Literal['candidate_softmax']
    requires_review: Literal[True]
    questions: list[ScoredQuestion]
    cache: dict[str, Any]
    latency_ms: float
    pathway: dict[str, Any] | None = None
    proposed_next_node_id: str | None = None

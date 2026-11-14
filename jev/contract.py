"""The JEV contract: request, response, backend info, JSON encoding and checks.

Spec: docs/platform/specs/02-jev-interface.md. One request shape for in-process backends and for
``POST /v1/decide``. ``probs`` always covers exactly the offered option ids.

Context field names (used by ``BackendInfo.context_fields`` and the response cache):

* ``group``, ``age``, ``t_days``, ``fast_track``
* ``attributes.<name>``: a revealed attribute
* ``history.<step>``: the latest result of a step (``true``, ``false`` or ``null``)
* ``options.<feature>``: a per-option feature such as ``lead_days`` (the queue state)
"""

from __future__ import annotations

import numbers
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

TOLERANCE = 1e-6          # the client renormalises within this, rejects anything further off
QUESTION_NEXT_STEP = "next_step"
CONTRACT_VERSION = 1


class ContractError(ValueError):
    """A request or response breaks the contract (bad shape, bad probabilities)."""


class BackendError(RuntimeError):
    """A backend could not answer (network failure, timeout, server error)."""


@dataclass
class DecisionRequest:
    request_id: str
    decision_point: str
    context: dict
    options: list[dict]
    question_type: str = QUESTION_NEXT_STEP

    @property
    def option_ids(self) -> list[str]:
        return [o["id"] for o in self.options]

    def to_dict(self) -> dict:
        return {"request_id": self.request_id, "decision_point": self.decision_point,
                "question_type": self.question_type, "context": self.context, "options": self.options}

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionRequest":
        if not isinstance(d, dict):
            raise ContractError("a request must be an object")
        for k in ("request_id", "decision_point", "options"):
            if k not in d:
                raise ContractError(f"request is missing {k!r}")
        req = cls(request_id=str(d["request_id"]), decision_point=str(d["decision_point"]),
                  context=d.get("context") or {}, options=list(d["options"]),
                  question_type=d.get("question_type", QUESTION_NEXT_STEP))
        req.validate()
        return req

    def validate(self) -> None:
        if not isinstance(self.options, list) or not self.options:
            raise ContractError(f"{self.request_id}: a request needs at least one option")
        ids = []
        for o in self.options:
            if not isinstance(o, dict) or not isinstance(o.get("id"), str) or not o["id"]:
                raise ContractError(f"{self.request_id}: every option needs a string 'id'")
            ids.append(o["id"])
        if len(set(ids)) != len(ids):
            raise ContractError(f"{self.request_id}: duplicate option ids {ids}")
        if not isinstance(self.context, dict):
            raise ContractError(f"{self.request_id}: context must be an object")


@dataclass
class DecisionResponse:
    request_id: str
    probs: dict[str, float]
    explanation: str | None = None

    def to_dict(self) -> dict:
        d = {"request_id": self.request_id, "probs": self.probs}
        if self.explanation is not None:
            d["explanation"] = self.explanation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionResponse":
        if not isinstance(d, dict) or "request_id" not in d or not isinstance(d.get("probs"), dict):
            raise ContractError("a response needs 'request_id' and a 'probs' object")
        return cls(request_id=str(d["request_id"]), probs={str(k): v for k, v in d["probs"].items()},
                   explanation=d.get("explanation"))


@dataclass
class BackendInfo:
    name: str                                   # "stub", "http", "local", ...
    model: str                                  # model id, e.g. "stub@1"
    deterministic: bool = True                  # same request -> same probabilities
    context_fields: list[str] | None = None     # fields it reads; None = reads everything
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "model": self.model, "deterministic": self.deterministic,
                "context_fields": self.context_fields, **self.extra}


@runtime_checkable
class DecisionBackend(Protocol):
    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]: ...

    def info(self) -> BackendInfo: ...


# --------------------------------------------------------------------------- probabilities
def check_probs(probs: dict, option_ids: list[str], where: str = "") -> dict[str, float]:
    """Validate ``probs`` against the offered ids and return them renormalised.

    Raises :class:`ContractError` when an id is missing or extra, a value is negative or not a
    number, or the sum is further than ``TOLERANCE`` from 1. Within tolerance the values are
    divided by their sum. The result keeps the order of ``option_ids``.
    """
    tag = f"{where}: " if where else ""
    if not isinstance(probs, dict):
        raise ContractError(f"{tag}probs must be an object")
    offered = set(option_ids)
    extra = [k for k in probs if k not in offered]
    missing = [o for o in option_ids if o not in probs]
    if extra or missing:
        raise ContractError(f"{tag}probs must cover exactly the offered options "
                            f"(missing {missing}, unexpected {extra})")
    out: dict[str, float] = {}
    for o in option_ids:
        v = probs[o]
        if isinstance(v, bool) or not isinstance(v, numbers.Real) or v != v or v < 0 or v == float("inf"):
            raise ContractError(f"{tag}probability for {o!r} is not a non-negative number: {v!r}")
        out[o] = float(v)
    total = sum(out.values())
    if abs(total - 1.0) > TOLERANCE:
        raise ContractError(f"{tag}probabilities sum to {total:.6g}, not 1")
    if total != 1.0:
        out = {o: v / total for o, v in out.items()}
    return out


def uniform_probs(option_ids: list[str]) -> dict[str, float]:
    return {o: 1.0 / len(option_ids) for o in option_ids}


def check_responses(requests: list[DecisionRequest], responses: list[DecisionResponse]) -> list[DecisionResponse]:
    """Responses must come back one per request, in request order, with valid probabilities."""
    if len(responses) != len(requests):
        raise ContractError(f"{len(requests)} requests but {len(responses)} responses")
    out = []
    for q, r in zip(requests, responses):
        if r.request_id != q.request_id:
            raise ContractError(f"response order broken: expected {q.request_id!r}, got {r.request_id!r}")
        out.append(DecisionResponse(r.request_id, check_probs(r.probs, q.option_ids, q.request_id), r.explanation))
    return out


# --------------------------------------------------------------------------- JSON bodies
def encode_request(model: str, requests: list[DecisionRequest]) -> dict:
    """Body of ``POST /v1/decide``."""
    return {"model": model, "requests": [q.to_dict() for q in requests]}


def decode_request(body: dict) -> tuple[str | None, list[DecisionRequest]]:
    if not isinstance(body, dict) or not isinstance(body.get("requests"), list):
        raise ContractError("body must be an object with a 'requests' list")
    return body.get("model"), [DecisionRequest.from_dict(q) for q in body["requests"]]


def encode_response(model: str, responses: list[DecisionResponse]) -> dict:
    return {"model": model, "responses": [r.to_dict() for r in responses]}


def decode_response(body: dict) -> tuple[str | None, list[DecisionResponse]]:
    if not isinstance(body, dict) or not isinstance(body.get("responses"), list):
        raise ContractError("body must be an object with a 'responses' list")
    return body.get("model"), [DecisionResponse.from_dict(r) for r in body["responses"]]

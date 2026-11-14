"""Context field paths (see :mod:`jev.contract`) and the response cache keyed on them."""

from __future__ import annotations

from collections import OrderedDict

from .contract import DecisionRequest, DecisionResponse

_MISSING = None


def field_value(req: DecisionRequest, path: str):
    """Value of a context field path for a request; hashable."""
    c = req.context
    if path in ("group", "age", "t_days", "fast_track"):
        return c.get(path)
    head, _, rest = path.partition(".")
    if head == "attributes":
        return _hashable((c.get("attributes") or {}).get(rest))
    if head == "history":
        res = _MISSING
        for h in c.get("history") or []:
            if h.get("step") == rest:
                res = h.get("result")
        return res
    if head == "options":
        return tuple((o["id"], _hashable((o.get("features") or {}).get(rest))) for o in req.options)
    raise ValueError(f"unknown context field {path!r}")


def _hashable(v):
    if isinstance(v, (list, tuple)):
        return tuple(_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _hashable(x)) for k, x in v.items()))
    return v


class ResponseCache:
    """LRU memo of responses on (decision point, declared context fields, offered options)."""

    def __init__(self, fields: list[str], max_entries: int = 200_000):
        self.fields, self.max = list(fields), max_entries
        self._d: OrderedDict = OrderedDict()
        self.hits = self.misses = 0

    def key(self, req: DecisionRequest):
        return (req.decision_point, req.question_type, tuple(req.option_ids),
                tuple(field_value(req, f) for f in self.fields))

    def get(self, key, request_id: str) -> DecisionResponse | None:
        r = self._d.get(key)
        if r is None:
            return None
        self._d.move_to_end(key)
        self.hits += 1
        return DecisionResponse(request_id, dict(r.probs), r.explanation)

    def put(self, key, resp: DecisionResponse) -> None:
        self._d[key] = resp
        if len(self._d) > self.max:
            self._d.popitem(last=False)

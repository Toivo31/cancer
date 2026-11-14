"""Per-decision-point backends: one point can use JEV while the rest stay on the stub."""

from __future__ import annotations

from .contract import BackendInfo, DecisionBackend, DecisionRequest, DecisionResponse


class RoutingBackend:
    def __init__(self, default: DecisionBackend, routes: dict[str, DecisionBackend]):
        self.default, self.routes = default, dict(routes)

    def backend_for(self, point: str) -> DecisionBackend:
        return self.routes.get(point, self.default)

    def info_for(self, point: str) -> BackendInfo:
        return self.backend_for(point).info()

    def info(self) -> BackendInfo:
        infos = [self.default.info()] + [b.info() for b in self.routes.values()]
        return BackendInfo("mixed", "+".join(sorted({i.model for i in infos})),
                           all(i.deterministic for i in infos), None)

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        out: list[DecisionResponse | None] = [None] * len(requests)
        groups: dict[int, tuple[DecisionBackend, list[int]]] = {}
        for i, q in enumerate(requests):
            b = self.backend_for(q.decision_point)
            groups.setdefault(id(b), (b, []))[1].append(i)
        for b, idx in groups.values():
            for i, r in zip(idx, b.decide([requests[i] for i in idx])):
                out[i] = r
        return out  # type: ignore[return-value]

    def summary(self) -> dict:
        s = {}
        for name, b in [("default", self.default), *self.routes.items()]:
            fn = getattr(b, "summary", None)
            if callable(fn) and fn():
                s[name] = fn()
        return s

"""The stub backend: hardcoded and conditional probability tables per decision point.

Table (``decision_policy.points`` in the flowchart document, spec 02)::

    {"sample_method": {"default": {"bronch": 0.5, "ttnb": 0.5},
                       "rules": [{"when": "location == 'central'", "probs": {"bronch": 0.9, "ttnb": 0.1}}]}}

Rules are checked in order and the first whose condition holds wins, otherwise ``default``. The
chosen row is restricted to the offered options and renormalised. A rule whose row has no
probability left on the offered options is skipped (the option it picks is not on offer today). A
decision point with no entry, or a row with no mass on what is offered, gets uniform probabilities
and a ``missing_probabilities`` warning (counted in :meth:`StubBackend.summary`).

Names a condition can read are the ones guards see: ``group``, ``age``, ``t`` (days since the
clock start; also ``t_days``), ``fast_track``, revealed attributes and the latest result of each
step.
"""

from __future__ import annotations

from .conditions import compile_condition
from .contract import BackendInfo, ContractError, DecisionRequest, DecisionResponse, uniform_probs

STUB_MODEL = "stub@1"
_BUILTIN = {"group": "group", "age": "age", "t": "t_days", "t_days": "t_days", "fast_track": "fast_track"}


class StubTableError(ValueError):
    """The probability table is malformed (a problem the editor should show)."""


def condition_env(context: dict) -> dict:
    """Names a stub condition sees, built from the request context."""
    env = {"group": context.get("group"), "age": context.get("age"), "t": context.get("t_days"),
           "t_days": context.get("t_days"), "fast_track": context.get("fast_track")}
    env.update(context.get("attributes") or {})
    for h in context.get("history") or []:
        env[h["step"]] = h.get("result")           # later attempts overwrite earlier ones
    return env


def _check_row(where: str, row, allow_zero_total: bool = False) -> dict[str, float]:
    if not isinstance(row, dict) or not row:
        raise StubTableError(f"{where}: probabilities must be an object like {{\"a\": 0.5, \"b\": 0.5}}")
    out = {}
    for k, v in row.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0 or v == float("inf"):
            raise StubTableError(f"{where}: probability for {k!r} must be a number >= 0, not {v!r}")
        out[str(k)] = float(v)
    if sum(out.values()) <= 0:
        raise StubTableError(f"{where}: probabilities are all zero")
    return out


class StubBackend:
    def __init__(self, points: dict | None = None, model: str = STUB_MODEL):
        self.model = model
        self.points: dict[str, dict] = {}
        self._fields: set[str] = set()
        self.warnings: dict[str, int] = {}
        for pt, spec in (points or {}).items():
            self.points[pt] = self._compile_point(pt, spec)

    # ------------------------------------------------------------------ compile
    def _compile_point(self, pt: str, spec) -> dict:
        if not isinstance(spec, dict):
            raise StubTableError(f"{pt}: expected an object with 'default' and optional 'rules'")
        default = _check_row(f"{pt}/default", spec["default"]) if spec.get("default") else None
        rules = []
        for i, r in enumerate(spec.get("rules") or []):
            where = f"{pt}/rules[{i}]"
            if not isinstance(r, dict) or "when" not in r or "probs" not in r:
                raise StubTableError(f"{where}: a rule needs 'when' and 'probs'")
            try:
                cond = compile_condition(r["when"])
            except ValueError as e:
                raise StubTableError(f"{where}: bad condition {r['when']!r}: {e}") from None
            for name in cond.names:
                self._fields |= self._fields_for(name)
            rules.append((cond, _check_row(where, r["probs"]), r["when"]))
        return {"default": default, "rules": rules}

    @staticmethod
    def _fields_for(name: str) -> set[str]:
        if name in _BUILTIN:
            return {_BUILTIN[name]}
        return {f"attributes.{name}", f"history.{name}"}

    def validate_against(self, flowchart, scenario=None) -> list[str]:
        """Check the table against a flowchart: decision points exist, options exist, condition
        names are known. Returns a list of problems (empty when fine)."""
        problems = []
        known = set(flowchart.nodes) | set(_BUILTIN)
        if scenario is not None:
            known |= set(scenario.attributes)
        for pt, row in self.points.items():
            node = flowchart.nodes.get(pt)
            if node is None or node.kind != "choice":
                problems.append(f"{pt}: not a decision point in this flowchart")
                continue
            opts = set(node.options)
            rows = ([("default", row["default"])] if row["default"] else []) + [(f"rule {w!r}", p) for _, p, w in row["rules"]]
            for label, probs in rows:
                bad = sorted(set(probs) - opts)
                if bad:
                    problems.append(f"{pt}/{label}: unknown options {bad}")
            for cond, _, w in row["rules"]:
                unk = sorted(set(cond.names) - known)
                if unk:
                    problems.append(f"{pt}: condition {w!r} reads unknown names {unk}")
        return problems

    # ------------------------------------------------------------------ backend protocol
    def info(self) -> BackendInfo:
        return BackendInfo("stub", self.model, deterministic=True, context_fields=sorted(self._fields))

    def _warn(self, code: str, pt: str) -> None:
        key = f"{code}:{pt}"
        self.warnings[key] = self.warnings.get(key, 0) + 1

    @staticmethod
    def _restrict(row: dict, offered: list[str]) -> dict[str, float] | None:
        total = sum(row.get(o, 0.0) for o in offered)
        if total <= 0:
            return None
        return {o: row.get(o, 0.0) / total for o in offered}

    def _one(self, q: DecisionRequest) -> DecisionResponse:
        offered = q.option_ids
        pt = self.points.get(q.decision_point)
        if pt is None:
            self._warn("missing_probabilities", q.decision_point)
            return DecisionResponse(q.request_id, uniform_probs(offered), "no probabilities for this decision point; uniform")
        env = None
        row, why = None, None
        for cond, probs, when in pt["rules"]:
            if env is None:
                env = condition_env(q.context)
            if cond.holds(env):
                r = self._restrict(probs, offered)
                if r is not None:
                    row, why, used = r, f"rule {when!r}", probs
                    break
        if row is None and pt["default"] is not None:
            r = self._restrict(pt["default"], offered)
            if r is not None:
                row, why, used = r, "default", pt["default"]
        if row is None:
            self._warn("missing_probabilities", q.decision_point)
            return DecisionResponse(q.request_id, uniform_probs(offered), "no probabilities on the offered options; uniform")
        if any(o not in used for o in offered):
            self._warn("missing_probabilities", q.decision_point)
        return DecisionResponse(q.request_id, row, why)

    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]:
        return [self._one(q) for q in requests]

    def summary(self) -> dict:
        return {"warnings": dict(self.warnings)} if self.warnings else {}

    # ------------------------------------------------------------------ table access
    def to_points(self) -> dict:
        """The table as JSON (what was compiled), for the editor."""
        out = {}
        for pt, c in self.points.items():
            d = {}
            if c["default"]:
                d["default"] = dict(c["default"])
            if c["rules"]:
                d["rules"] = [{"when": w, "probs": dict(p)} for _, p, w in c["rules"]]
            out[pt] = d
        return out


__all__ = ["StubBackend", "StubTableError", "condition_env", "STUB_MODEL", "ContractError"]

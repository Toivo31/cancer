"""Conditions for stub rules, evaluated without ``eval``.

Uses the safe expression language ``pathway_sim.expr`` (ticket M1-4, branch plat/expr) when it is
present. Until that branch is merged, a small ``ast``-based evaluator with the same whitelist core
(``and``/``or``/``not``, comparisons, names, constants, tuples of constants) stands in, so the stub
never needs ``eval``. Delete the fallback once ``pathway_sim.expr`` is on this branch.
"""

from __future__ import annotations

import ast
import operator
from functools import lru_cache

try:                                                    # pragma: no cover - depends on the merge
    from pathway_sim import expr as _expr
except ImportError:
    _expr = None

_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Gt: operator.gt, ast.GtE: operator.ge}


class ConditionError(ValueError):
    pass


class _Mini:
    """Stand-in condition: ``names`` (the names it reads) and ``holds(env)``."""

    def __init__(self, source: str):
        self.source = source
        try:
            tree = ast.parse(source.strip(), mode="eval")
        except SyntaxError as e:
            raise ConditionError(f"syntax error in condition {source!r}: {e.msg}") from None
        self.names: set[str] = set()
        self._fn = self._build(tree.body)

    def _build(self, node):
        if isinstance(node, ast.BoolOp):
            parts = [self._build(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return lambda env: all(p(env) for p in parts)
            return lambda env: any(p(env) for p in parts)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            f = self._build(node.operand)
            return lambda env: not f(env)
        if isinstance(node, ast.Name):
            self.names.add(node.id)
            nid = node.id
            return lambda env: env.get(nid)
        if isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, (bool, int, float, str))):
            v = node.value
            return lambda env: v
        if isinstance(node, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Constant) for e in node.elts):
            v = tuple(e.value for e in node.elts)
            return lambda env: v
        if isinstance(node, ast.Compare):
            left = self._build(node.left)
            steps = []
            for op, comp in zip(node.ops, node.comparators):
                right = self._build(comp)
                if type(op) in _CMP:
                    fn = _CMP[type(op)]
                elif isinstance(op, ast.In):
                    fn = lambda a, b: a in b
                elif isinstance(op, ast.NotIn):
                    fn = lambda a, b: a not in b
                else:
                    raise ConditionError("comparison not supported")
                steps.append((fn, right))

            def run(env, left=left, steps=steps):
                a = left(env)
                for fn, r in steps:
                    b = r(env)
                    try:
                        if not fn(a, b):
                            return False
                    except TypeError:       # None < 3 and the like: a missing value never satisfies
                        return False
                    a = b
                return True
            return run
        raise ConditionError(f"not allowed in a condition: {type(node).__name__}")

    def holds(self, env) -> bool:
        return bool(self._fn(env))


@lru_cache(maxsize=4096)
def compile_condition(source: str):
    """Parse a condition once; returns an object with ``names`` and ``holds(env)``.
    Raises ``ValueError`` (``ConditionError`` or the expression module's error) if it is not allowed."""
    if not isinstance(source, str):
        raise ConditionError("a condition must be text")
    if _expr is not None:
        return _expr.parse(source)
    return _Mini(source)

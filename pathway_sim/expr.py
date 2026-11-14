"""Safe condition expressions for flowchart guards (``when:``) and policy rules.

Conditions used to be handed to Python's ``eval``. That is a code-execution hole as soon as users
type them online, so they are now parsed with ``ast``, checked against a small whitelist and turned
into a tree of closures. Nothing in this module calls ``eval``, ``exec`` or ``compile``; a condition
can only read names from the environment dict it is given.

Supported grammar (exactly what the shipped scenarios use, plus ordering and ``in`` for age and t)::

    expr     := or_expr
    or_expr  := and_expr ("or" and_expr)*
    and_expr := not_expr ("and" not_expr)*
    not_expr := "not" not_expr | compare
    compare  := atom (cmp_op atom)*            # chains like  50 <= age < 70  are allowed
    cmp_op   := == | != | < | <= | > | >= | is | is not | in | not in
    atom     := NAME | constant | "(" expr ")"
    constant := 'text' | "text" | integer | decimal | True | False | None | -number
    # the right side of in / not in must be a tuple or list of constants:  group in ('a', 'b')
    # the right side of is / is not must be True, False or None

Semantics follow Python so existing scenarios behave the same: ``and`` / ``or`` short-circuit and
return an operand (callers test truthiness), a name that is not in the environment is ``None``
(``environment.get``), ``x is not False`` distinguishes None from False. One deliberate difference:
an ordering comparison between values that cannot be ordered (``None < 3``) is False instead of
raising ``TypeError``, so a patient with an unrevealed age or result never crashes a run.

Everything else is rejected at parse time with an :class:`ExprError` (a ``ValueError``) that carries a
column and, where possible, a hint: calls, attribute access, subscripts, arithmetic, lambdas,
comprehensions, f-strings, walrus, ``await``/``yield``, starred, dict/set displays, names starting
with an underscore, over-long text, deep nesting. Limits keep the parser itself cheap:
:data:`MAX_LENGTH` characters, :data:`MAX_DEPTH` nesting, :data:`MAX_NODES` tree nodes.

Parsing is cached by source text (``functools.lru_cache``): the optimiser copies flowcharts
thousands of times and every copy re-reads its guards. An :class:`Expr` is immutable and pickles as
its source text.
"""

from __future__ import annotations

import ast
import difflib
import io
import math
import re
import tokenize
import warnings
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping

MAX_LENGTH = 1000
MAX_DEPTH = 32
MAX_NODES = 300
MAX_STRING = 200
MAX_NAME = 80
MAX_SEQUENCE = 64
MAX_INT = 10 ** 12

_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
ALWAYS_KNOWN = frozenset({"group", "age", "t"})


class ExprError(ValueError):
    """A condition that cannot be read or is not allowed. ``col`` is a 0-based offset into the text."""

    def __init__(self, message: str, col: int | None = None, hint: str | None = None, source: str | None = None):
        super().__init__(message)
        self.message, self.col, self.hint, self.source = message, col, hint, source

    def __str__(self) -> str:
        return self.message


class Expr:
    """A parsed, checked condition. Call it with an environment mapping: ``expr(env)`` is the value,
    ``expr.holds(env)`` its truth."""

    __slots__ = ("source", "names", "_fn", "is_constant")

    def __init__(self, source: str, names: frozenset, fn: Callable[[Mapping], Any], is_constant: bool):
        for k, v in (("source", source), ("names", names), ("_fn", fn), ("is_constant", is_constant)):
            object.__setattr__(self, k, v)

    def __setattr__(self, key, value):
        raise AttributeError("Expr is immutable")

    def __call__(self, env: Mapping) -> Any:
        return self._fn(env)

    def holds(self, env: Mapping) -> bool:
        return bool(self._fn(env))

    def __reduce__(self):
        return (parse, (self.source,))

    def __repr__(self) -> str:
        return f"Expr({self.source!r})"


# --------------------------------------------------------------------------- parsing

_DISALLOWED = {
    ast.Call: "function calls are not allowed",
    ast.Attribute: "attribute access (a.b) is not allowed",
    ast.Subscript: "indexing (a[b]) is not allowed",
    ast.BinOp: "arithmetic is not supported; compare with ==, !=, <, <=, >, >=, in",
    ast.Lambda: "lambda is not allowed",
    ast.ListComp: "comprehensions are not allowed",
    ast.SetComp: "comprehensions are not allowed",
    ast.DictComp: "comprehensions are not allowed",
    ast.GeneratorExp: "comprehensions are not allowed",
    ast.Dict: "dictionaries are not allowed",
    ast.JoinedStr: "f-strings are not allowed",
    ast.FormattedValue: "f-strings are not allowed",
    ast.IfExp: "'x if c else y' is not allowed; use and / or / not",
    ast.NamedExpr: "assignment inside a condition is not allowed",
    ast.Await: "await is not allowed",
    ast.Yield: "yield is not allowed",
    ast.YieldFrom: "yield is not allowed",
    ast.Starred: "starred expressions are not allowed",
    ast.Slice: "slices are not allowed",
}


def _fail(node: ast.AST, message: str, hint: str | None = None) -> ExprError:
    return ExprError(message, getattr(node, "col_offset", None), hint)


def parse(source: str) -> Expr:
    """Parse and check ``source``; raise :class:`ExprError` if it is not a supported condition.
    Results are cached per source text."""
    if not isinstance(source, str):
        raise ExprError(f"a condition must be text, not {type(source).__name__}")
    return _parse_cached(source)


@lru_cache(maxsize=8192)
def _parse_cached(source: str) -> Expr:
    try:
        return _parse(source)
    except ExprError as e:
        e.source = source
        raise


def _parse(source: str) -> Expr:
    text = source.strip()
    if not text:
        raise ExprError("the condition is empty")
    if len(text) > MAX_LENGTH:
        raise ExprError(f"the condition is too long ({len(text)} characters, the limit is {MAX_LENGTH})")
    if "\x00" in text:
        raise ExprError("the condition contains a null character")
    if "#" in text and _has_comment(text):
        raise ExprError("comments are not allowed in a condition", text.index("#"))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise ExprError(f"syntax error: {e.msg}", (e.offset - 1) if e.offset else None) from None
    except (RecursionError, MemoryError):
        raise ExprError("the condition is nested too deeply") from None
    except ValueError as e:      # e.g. source code string cannot contain null bytes
        raise ExprError(f"cannot read the condition: {e}") from None
    c = _Compiler(text)
    fn = c.build(tree.body, 0)
    return Expr(text, frozenset(c.names), fn, not c.names)


def _has_comment(text: str) -> bool:
    """True if a '#' starts a comment (a '#' inside a quoted string is fine)."""
    try:
        return any(tok.type == tokenize.COMMENT for tok in tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return False      # unreadable text: ast.parse reports the real error


class _Compiler:
    def __init__(self, text: str):
        self.text = text
        self.names: set[str] = set()
        self.count = 0

    # -- helpers
    def tick(self, node: ast.AST, depth: int) -> None:
        self.count += 1
        if self.count > MAX_NODES:
            raise _fail(node, f"the condition is too complex (more than {MAX_NODES} parts)")
        if depth > MAX_DEPTH:
            raise _fail(node, f"the condition is nested too deeply (more than {MAX_DEPTH} levels)")

    def constant(self, node: ast.AST) -> Any:
        """The Python value of a constant node (including -number), or raise."""
        if isinstance(node, ast.Constant):
            v = node.value
            if v is None or isinstance(v, bool):
                return v
            if isinstance(v, str):
                if len(v) > MAX_STRING:
                    raise _fail(node, f"text is too long (limit {MAX_STRING} characters)")
                return v
            if isinstance(v, int):
                if abs(v) > MAX_INT:
                    raise _fail(node, "number is too large")
                return v
            if isinstance(v, float):
                if not math.isfinite(v) or abs(v) > MAX_INT:
                    raise _fail(node, "number is out of range")
                return v
            raise _fail(node, f"{type(v).__name__} values are not allowed")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) \
                and isinstance(node.operand, ast.Constant) \
                and isinstance(node.operand.value, (int, float)) and not isinstance(node.operand.value, bool):
            v = self.constant(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        raise _fail(node, "expected a constant (text, number, True, False or None)")

    def sequence(self, node: ast.AST, depth: int) -> tuple:
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            raise _fail(node, "the right side of 'in' must be a list of constants, like ('a', 'b')")
        self.tick(node, depth)
        if len(node.elts) > MAX_SEQUENCE:
            raise _fail(node, f"the list has more than {MAX_SEQUENCE} items")
        vals = []
        for e in node.elts:
            self.tick(e, depth + 1)
            vals.append(self.constant(e))
        return tuple(vals)

    # -- tree
    def build(self, node: ast.AST, depth: int) -> Callable[[Mapping], Any]:
        self.tick(node, depth)
        for cls, msg in _DISALLOWED.items():
            if isinstance(node, cls):
                raise _fail(node, msg)
        if isinstance(node, ast.Name):
            return self.name(node)
        if isinstance(node, ast.Constant) or (isinstance(node, ast.UnaryOp) and not isinstance(node.op, ast.Not)):
            v = self.constant(node)
            return lambda env, v=v: v
        if isinstance(node, ast.UnaryOp):      # Not
            inner = self.build(node.operand, depth + 1)
            return lambda env: not inner(env)
        if isinstance(node, ast.BoolOp):
            parts = [self.build(v, depth + 1) for v in node.values]
            if isinstance(node.op, ast.And):
                if len(parts) == 2:
                    a, b = parts
                    return lambda env: a(env) and b(env)

                def and_(env, parts=tuple(parts)):
                    v = True
                    for p in parts:
                        v = p(env)
                        if not v:
                            return v
                    return v
                return and_
            if len(parts) == 2:
                a, b = parts
                return lambda env: a(env) or b(env)

            def or_(env, parts=tuple(parts)):
                v = False
                for p in parts:
                    v = p(env)
                    if v:
                        return v
                return v
            return or_
        if isinstance(node, ast.Compare):
            return self.compare(node, depth)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            raise _fail(node, "lists are only allowed on the right side of 'in'")
        raise _fail(node, f"{type(node).__name__} is not allowed in a condition")

    def name(self, node: ast.Name) -> Callable[[Mapping], Any]:
        n = node.id
        if len(n) > MAX_NAME:
            raise _fail(node, "name is too long")
        if n.startswith("_") or not _NAME_RE.match(n):
            raise _fail(node, f"name {n!r} is not allowed (names must start with a letter)")
        self.names.add(n)
        return lambda env: env.get(n)

    def compare(self, node: ast.Compare, depth: int) -> Callable[[Mapping], Any]:
        left = self.build(node.left, depth + 1)
        steps = []
        for op, right_node in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                seq = self.sequence(right_node, depth + 1)
                steps.append((type(op), seq))
            elif isinstance(op, (ast.Is, ast.IsNot)):
                self.tick(right_node, depth + 1)
                v = self.constant(right_node)
                if not (v is None or isinstance(v, bool)):
                    raise _fail(right_node, "'is' can only be used with True, False or None", "use == for text and numbers")
                steps.append((type(op), v))
            elif isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                steps.append((type(op), self.build(right_node, depth + 1)))
            else:
                raise _fail(node, f"operator {type(op).__name__} is not allowed")
        if len(steps) == 1:
            return _single_compare(left, steps[0][0], steps[0][1], self, node.comparators[0])
        # chained comparison: a < b < c  ==  a < b and b < c, each operand evaluated once
        def chain(env, left=left, steps=tuple(steps)):
            lv = left(env)
            result = True
            for op, r in steps:
                rv = r(env) if callable(r) else r
                result = _apply(op, lv, rv)
                if not result:
                    return result
                lv = rv
            return result
        return chain


def _apply(op: type, a: Any, b: Any) -> bool:
    if op is ast.Eq:
        return a == b
    if op is ast.NotEq:
        return a != b
    if op is ast.Is:
        return a is b
    if op is ast.IsNot:
        return a is not b
    if op is ast.In:
        return a in b
    if op is ast.NotIn:
        return a not in b
    try:
        if op is ast.Lt:
            return a < b
        if op is ast.LtE:
            return a <= b
        if op is ast.Gt:
            return a > b
        return a >= b
    except TypeError:
        return False


def _single_compare(left, op, right, compiler: _Compiler, right_node: ast.AST):
    """One comparison, with the common shapes unrolled (this runs per patient per node)."""
    if op is ast.Eq:
        return (lambda env: left(env) == right(env))
    if op is ast.NotEq:
        return (lambda env: left(env) != right(env))
    if op is ast.Is:
        return (lambda env: left(env) is right)
    if op is ast.IsNot:
        return (lambda env: left(env) is not right)
    if op is ast.In:
        return (lambda env: left(env) in right)
    if op is ast.NotIn:
        return (lambda env: left(env) not in right)

    def ordered(env):
        return _apply(op, left(env), right(env))
    return ordered


# --------------------------------------------------------------------------- helpers for callers

def names_in(source: str) -> frozenset:
    """Names a condition reads (raises :class:`ExprError` if it is not valid)."""
    return parse(source).names


def unknown_names(source: str, known: Iterable[str]) -> list[str]:
    """Names in ``source`` that are neither in ``known`` nor the built-in ``group``, ``age``, ``t``."""
    ok = set(known) | ALWAYS_KNOWN
    return sorted(parse(source).names - ok)


def suggest(name: str, known: Iterable[str]) -> str | None:
    m = difflib.get_close_matches(name, sorted(set(known) | ALWAYS_KNOWN), n=1, cutoff=0.7)
    return m[0] if m else None

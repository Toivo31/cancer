"""Load and check a clinical catalogue (``catalogue/1``). The format is ``catalogue/README.md``.

    from patient_engine.catalogue import load_catalogue
    cat = load_catalogue("catalogue/_examples/tiny")       # raises CatalogueError(problems) on errors
    cat.version_hash, cat.conditions["lung_cancer"].prevalence.resolve({"smoking_status": "current"})

Public API:
  load_catalogue(path, sources=None) -> Catalogue     read the YAML files, validate, build typed objects
  read_catalogue(path) -> (raw, problems)             the files as one dict (no validation beyond YAML)
  validate_catalogue(raw, sources=None) -> [Problem]  every problem of a raw catalogue dict
  version_hash(raw) -> str                            SHA-256 of the normalised content
  Catalogue, Condition, Variable, Test, TestOutput, Cooccurrence, BackgroundField, Leaf, CatalogueError

``raw`` is ``{"catalogue": {...}, "conditions": [...], "variables": [...], "tests": [...],
"cooccurrence": [...]}``, the parsed files. ``sources`` is the set of known source ids, or a path to a
sources YAML, or None for the repo's ``params/sources.yaml``.

YAML is read with ``yaml.safe_load`` and expressions with ``pathway_sim.expr`` (no eval; I7).
Distribution specs use ``pathway_sim.dists`` so the catalogue and the simulator speak one language.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import yaml

from pathway_sim import dists as _dists
from pathway_sim import expr as _expr

from .problems import ERROR, Problem

FORMAT = "catalogue/1"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = REPO / "params" / "sources.yaml"

FILES = {"catalogue": "catalogue.yaml", "conditions": "conditions.yaml", "variables": "variables.yaml",
         "tests": "tests.yaml", "cooccurrence": "cooccurrence.yaml"}
REQUIRED_FILES = ("catalogue", "conditions", "variables", "tests")

ASSUMPTION = "assumption"
GRADES = ("A", "B", "C", "assumption", "llm_draft")
STATUSES = ("example", "draft", "reviewed")
CONDITION_CLASSES = ("cancer", "other_illness", "healthy")
VARIABLE_KINDS = ("symptom", "sign", "lab_true", "imaging_true", "function_true", "tissue_true")
VARIABLE_TYPES = ("binary", "continuous", "categorical", "size_mm")
BACKGROUND_TYPES = ("binary", "continuous", "categorical")
TEST_CATEGORIES = ("history", "examination", "bloodwork", "imaging", "endoscopy", "tissue", "function", "molecular")
DEFAULT_MAX_ATTEMPTS = 3
RESERVED = frozenset({"condition", "default"})

INITIAL_STATE = "all_active"
ALL_RESOLVED = "all_resolved"

_ID = re.compile(r"[a-z][a-z0-9_]*\Z")
_BAND = re.compile(r"\s*(-?\d+(?:\.\d+)?)?\s*\.\.\s*(-?\d+(?:\.\d+)?)?\s*\Z")
_META = frozenset({"source", "grade", "note", "by"})
_RANGE_KEYS = frozenset({"low", "high"})
_DIST_PARAMS = {"fixed": {"value"}, "lognormal": {"median", "p90"}, "uniform": {"low", "high"},
                "exponential": {"mean"}, "empirical": {"values"}}


class CatalogueError(ValueError):
    """A catalogue that cannot be loaded. ``problems`` lists every problem found (errors and warnings)."""

    def __init__(self, problems: list[Problem], path: str | None = None):
        self.problems = list(problems)
        self.path = path
        errs = [p for p in self.problems if p.severity == ERROR]
        head = f"catalogue {path!r} has {len(errs)} error(s)" if path else f"catalogue has {len(errs)} error(s)"
        super().__init__(head + ":\n" + "\n".join(f"  {p}" for p in errs[:20]))


# ============================================================================ typed objects

@dataclass(frozen=True)
class Leaf:
    """One reference number (or distribution) with its source. ``kind`` is ``value``, ``p``,
    ``dist`` or ``values``; ``params`` holds the number(s) without the metadata."""
    kind: str
    params: dict
    source: str
    grade: str | None = None
    note: str | None = None
    low: float | None = None
    high: float | None = None
    by: dict | None = None

    def resolve(self, facts: Mapping[str, Any] | None = None):
        """The effective number for a patient with ``facts`` (name -> value: ``condition``, attribute
        names, variable ids, background fields). Returns a float for ``value``/``p``, a distribution
        spec for ``dist`` (feed it to ``pathway_sim.dists.sample``), a ``{level: share}`` dict for
        ``values``. Facts that are missing or None leave the base number."""
        params = _apply_by(dict(self.params), self.by, facts or {}, self.kind)
        if self.kind in ("value", "p"):
            return float(params[self.kind])
        if self.kind == "values":
            return dict(params["values"])
        return params


@dataclass(frozen=True)
class BackgroundField:
    id: str
    type: str
    label: str | None = None
    unit: str | None = None
    values: tuple[str, ...] = ()
    range: tuple[float | None, float | None] = (None, None)


@dataclass(frozen=True)
class Condition:
    id: str
    label: str
    cls: str                                                   # "class" in YAML: cancer | other_illness | healthy
    prevalence: Leaf
    attributes: dict[str, Leaf] = field(default_factory=dict)  # name -> categorical leaf
    note: str | None = None

    def attribute_levels(self, name: str) -> tuple[str, ...]:
        return tuple(self.attributes[name].params["values"])


@dataclass(frozen=True)
class Variable:
    id: str
    label: str
    kind: str
    type: str
    given: dict[str, Leaf]                                     # condition id or "default" -> leaf
    unit: str | None = None
    values: tuple[str, ...] = ()
    range: tuple[float | None, float | None] = (None, None)
    only_if: str | None = None
    note: str | None = None

    def given_for(self, condition: str) -> Leaf:
        return self.given.get(condition) or self.given["default"]


@dataclass(frozen=True)
class TestOutput:
    id: str
    type: str
    measures: str                                              # variable id
    unit: str | None = None
    values: tuple[str, ...] = ()                               # categorical levels (the variable's)
    only_if: str | None = None
    sensitivity: Leaf | None = None                            # binary
    specificity: Leaf | None = None                            # binary
    accuracy: Leaf | None = None                               # categorical
    error_sd: Leaf | None = None                               # continuous, size_mm


@dataclass(frozen=True)
class Test:
    __test__ = False                                           # not a pytest class
    id: str
    label: str
    category: str
    outputs: tuple[TestOutput, ...]
    max_attempts: int
    positive_when: str | None = None
    nondiagnostic: Leaf | None = None
    timing: dict[str, Leaf] = field(default_factory=dict)      # service_days, report_days
    resource_kind: str | None = None
    cost_eur: Leaf | None = None
    invasive: bool = False
    harm: dict[str, Leaf] = field(default_factory=dict)
    requires: tuple[str, ...] = ()
    note: str | None = None

    def output(self, output_id: str) -> TestOutput:
        return next(o for o in self.outputs if o.id == output_id)

    @property
    def output_ids(self) -> tuple[str, ...]:
        return tuple(o.id for o in self.outputs)

    def is_positive(self, values: Mapping[str, Any]) -> bool | None:
        """The yes/no reading of an ``ok`` result through ``positive_when`` (None without a rule)."""
        if self.positive_when is None:
            return None
        return _expr.parse(self.positive_when).holds(values)


@dataclass(frozen=True)
class Cooccurrence:
    primary: str
    coexisting: str
    share: Leaf


@dataclass(frozen=True)
class Catalogue:
    id: str
    version: Any
    title: str
    status: str
    scope: str
    max_attempts: int
    background: dict[str, BackgroundField]
    conditions: dict[str, Condition]
    variables: dict[str, Variable]
    tests: dict[str, Test]
    cooccurrence: tuple[Cooccurrence, ...]
    version_hash: str
    path: str | None = None
    problems: tuple[Problem, ...] = ()                         # warnings kept from loading
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def states(self) -> tuple[str, ...]:
        """State names a card may use: ``all_active``, ``<illness>_resolved`` for every
        ``other_illness`` condition, and ``all_resolved``."""
        return (INITIAL_STATE, *(f"{c}_resolved" for c, x in self.conditions.items() if x.cls == "other_illness"),
                ALL_RESOLVED)

    def leaves(self) -> Iterator[tuple[str, Leaf]]:
        """Every reference number as (dotted path, leaf)."""
        for c in self.conditions.values():
            yield f"conditions.{c.id}.prevalence", c.prevalence
            for a, lf in c.attributes.items():
                yield f"conditions.{c.id}.attributes.{a}", lf
        for v in self.variables.values():
            for k, lf in v.given.items():
                yield f"variables.{v.id}.given.{k}", lf
        for t in self.tests.values():
            for o in t.outputs:
                for name in ("sensitivity", "specificity", "accuracy", "error_sd"):
                    lf = getattr(o, name)
                    if lf is not None:
                        yield f"tests.{t.id}.outputs.{o.id}.{name}", lf
            if t.nondiagnostic is not None:
                yield f"tests.{t.id}.nondiagnostic", t.nondiagnostic
            for k, lf in t.timing.items():
                yield f"tests.{t.id}.timing.{k}", lf
            if t.cost_eur is not None:
                yield f"tests.{t.id}.cost_eur", t.cost_eur
            for k, lf in t.harm.items():
                yield f"tests.{t.id}.harm.{k}", lf
        for co in self.cooccurrence:
            yield f"cooccurrence.{co.primary}.{co.coexisting}.share", co.share

    def sources_used(self) -> dict[str, int]:
        """Source id (or ``assumption``) -> number of reference numbers citing it, including sources
        given inside ``by:`` levels."""
        out: dict[str, int] = {}
        for _, lf in self.leaves():
            for s in _leaf_sources(lf.source, lf.by):
                out[s] = out.get(s, 0) + 1
        return dict(sorted(out.items()))

    def cooccurring(self, primary: str) -> tuple[Cooccurrence, ...]:
        return tuple(c for c in self.cooccurrence if c.primary == primary)


def _leaf_sources(source: str, by: dict | None) -> list[str]:
    out = [source]
    for levels in (by or {}).values():
        if isinstance(levels, dict):
            for ov in levels.values():
                if isinstance(ov, dict):
                    if isinstance(ov.get("source"), str) and ov["source"] != source:
                        out.append(ov["source"])
                    out.extend(s for s in _leaf_sources(source, ov.get("by")) if s != source)
    return out


# ============================================================================ `by:` matching

def _band(key: Any) -> tuple[float, float] | None:
    if not isinstance(key, str):
        return None
    m = _BAND.match(key)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    lo = float(m.group(1)) if m.group(1) is not None else -math.inf
    hi = float(m.group(2)) if m.group(2) is not None else math.inf
    return (lo, hi) if lo < hi else None


def _level_key(k: Any) -> str:
    if isinstance(k, bool):
        return "true" if k else "false"
    return str(k)


def _match(levels: Mapping, x: Any):
    if isinstance(x, bool):
        want = "true" if x else "false"
        for k, v in levels.items():
            if _level_key(k) == want:
                return v
        return None
    if isinstance(x, (int, float)):
        for k, v in levels.items():
            b = _band(k)
            if b and b[0] <= x < b[1]:
                return v
        for k, v in levels.items():           # a categorical fact that happens to be numeric
            if _level_key(k) == _level_key(x):
                return v
        return None
    for k, v in levels.items():
        if _level_key(k) == str(x):
            return v
    return None


def _apply_by(params: dict, by: Mapping | None, facts: Mapping, kind: str) -> dict:
    for ref, levels in (by or {}).items():
        x = facts.get(ref)
        if x is None or not isinstance(levels, Mapping):
            continue
        ov = _match(levels, x)
        if ov is None:
            continue
        if isinstance(ov, Mapping):
            keep = (lambda k: k not in _META) if kind == "dist" else (lambda k: k not in _META and k not in _RANGE_KEYS)
            params.update({k: v for k, v in ov.items() if keep(k)})
            if ov.get("by"):
                params = _apply_by(params, ov["by"], facts, kind)
        else:
            params[kind if kind in ("value", "p") else "value"] = ov
    return params


# ============================================================================ reading

@lru_cache(maxsize=8)
def _source_ids_from(path: str) -> frozenset:
    data = yaml.safe_load(Path(path).read_text()) or []
    return frozenset(str(e["id"]) for e in data if isinstance(e, dict) and "id" in e)


def _known_sources(sources) -> frozenset:
    if sources is None:
        return _source_ids_from(str(DEFAULT_SOURCES))
    if isinstance(sources, (str, Path)):
        return _source_ids_from(str(sources))
    return frozenset(sources)


def read_catalogue(path: str | Path) -> tuple[dict, list[Problem]]:
    """Parse the catalogue's YAML files into one raw dict. Missing optional files become empty lists."""
    root = Path(path)
    raw: dict[str, Any] = {}
    problems: list[Problem] = []
    for key, name in FILES.items():
        f = root / name
        if not f.is_file():
            if key in REQUIRED_FILES:
                problems.append(Problem("file_missing", f"{name} is missing in {root}", file=name))
            raw[key] = {} if key == "catalogue" else []
            continue
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError as e:
            problems.append(Problem("yaml_error", f"{name} is not valid YAML: {e}", file=name))
            data = None
        if data is None:
            data = {} if key == "catalogue" else []
        raw[key] = data
    return raw, problems


# ============================================================================ version hash

def _norm(x: Any, top: str | None = None) -> Any:
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, Mapping):
        return {_level_key(k): _norm(v, k if top is None else None) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        items = [_norm(v) for v in x]
        if items and all(isinstance(v, dict) and isinstance(v.get("id"), str) for v in items):
            items.sort(key=lambda v: v["id"])
        elif top == "cooccurrence":
            items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return items
    return str(x)


def version_hash(raw: Mapping[str, Any]) -> str:
    """SHA-256 (hex) of the normalised catalogue: entries sorted by id, keys sorted, numbers as floats.
    Equal for reordered but equal files; different after any change to a number, source or note."""
    content = {k: _norm(raw.get(k), k) for k in FILES}
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


# ============================================================================ validation

def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


class _Validator:
    def __init__(self, raw: Mapping[str, Any], sources: frozenset):
        self.raw = raw
        self.sources = sources
        self.problems: list[Problem] = []
        self.file: str | None = None
        self.deferred_by: list[tuple] = []        # (file, path, leaf obj, kind, condition scope, graph owner, prob, nonneg, levels)
        self.edges: dict[str, set[str]] = {}
        # name tables, filled by the structural pass
        self.background: dict[str, dict] = {}
        self.conditions: dict[str, dict] = {}
        self.attributes: dict[str, dict[str, tuple]] = {}     # condition -> attribute -> levels
        self.variables: dict[str, dict] = {}
        self.tests: dict[str, dict] = {}

    # ----------------------------------------------------------------- helpers
    def add(self, code: str, message: str, path: str | None = None, hint: str | None = None, file: str | None = None):
        self.problems.append(Problem(code, message, path=path, file=file if file is not None else self.file, hint=hint))

    def need(self, obj: Mapping, key: str, path: str, typ=None) -> Any:
        if key not in obj or obj[key] is None:
            self.add("missing_field", f"`{key}` is required", f"{path}.{key}" if path else key)
            return None
        v = obj[key]
        if typ is not None and not isinstance(v, typ):
            self.add("bad_type", f"`{key}` must be {_tname(typ)}, not {type(v).__name__}", f"{path}.{key}" if path else key)
            return None
        return v

    def check_id(self, x: Any, path: str) -> bool:
        if not isinstance(x, str) or not _ID.match(x):
            self.add("bad_id", f"id {x!r} is not snake_case", path)
            return False
        if x in RESERVED:
            self.add("bad_id", f"id {x!r} is reserved", path)
            return False
        return True

    def entries(self, section: str) -> list[dict]:
        data = self.raw.get(section)
        if data is None:
            return []
        if not isinstance(data, list):
            self.add("bad_type", f"{FILES[section]} must be a list of entries", section, file=FILES[section])
            return []
        out = []
        for i, e in enumerate(data):
            if not isinstance(e, dict):
                self.add("bad_type", f"entry {i} must be a mapping", f"{section}[{i}]", file=FILES[section])
            else:
                out.append(e)
        return out

    def unknown_fields(self, obj: Mapping, allowed: Iterable[str], path: str):
        allowed = set(allowed)
        for k in obj:
            if k not in allowed:
                self.add("unknown_field", f"field `{k}` is not part of the format; it is ignored", f"{path}.{k}",
                         hint=_did_you_mean(str(k), allowed))

    # ----------------------------------------------------------------- leaves
    def leaf(self, obj: Any, path: str, kinds: tuple[str, ...], prob: bool = False, nonneg: bool = False,
             levels: tuple | None = None, scope: str | None = None, owner: str | None = None) -> Leaf | None:
        if obj is None:
            self.add("missing_field", "a number is required here", path)
            return None
        if _is_num(obj):
            self.add("missing_source", f"bare number {obj!r}: write it as {{{kinds[0]}: {obj}, source: ...}}", path)
            return None
        if not isinstance(obj, dict):
            self.add("bad_type", f"expected a number object ({' or '.join(kinds)} with source), not {type(obj).__name__}", path)
            return None
        kind = "dist" if "dist" in obj else "values" if "values" in obj else "p" if "p" in obj else \
            "value" if "value" in obj else None
        if kind is None:
            self.add("missing_field", f"no number: expected `{kinds[0]}`", path)
            return None
        if kind not in kinds:
            self.add("bad_type", f"`{kind}` is not allowed here; use {' or '.join('`'+k+'`' for k in kinds)}", path)
            return None
        ok = True
        src = obj.get("source")
        if src is None:
            self.add("missing_source", "number without `source` (an id in params/sources.yaml, or `assumption`)", path)
            ok = False
        elif not isinstance(src, str) or (src != ASSUMPTION and src not in self.sources):
            self.add("unknown_source", f"source {src!r} is not in params/sources.yaml", f"{path}.source",
                     hint=_did_you_mean(str(src), self.sources | {ASSUMPTION}))
            ok = False
        grade = obj.get("grade")
        if grade is not None and grade not in GRADES:
            self.add("bad_grade", f"grade {grade!r} is not one of {', '.join(GRADES)}", f"{path}.grade")
            ok = False
        note = obj.get("note")
        if note is not None and not isinstance(note, str):
            self.add("bad_type", "`note` must be text", f"{path}.note")
        params = {k: v for k, v in obj.items() if k not in _META and not (kind in ("value", "p") and k in _RANGE_KEYS)}
        ok &= self.check_params(params, kind, path, prob, nonneg, levels)
        low = high = None
        if kind in ("value", "p"):
            low, high = obj.get("low"), obj.get("high")
            for nm, b in (("low", low), ("high", high)):
                if b is not None and not _is_num(b):
                    self.add("bad_type", f"`{nm}` must be a number", f"{path}.{nm}")
                    ok = False
            if ok and _is_num(low) and _is_num(high) and low > high:
                self.add("bad_range", f"low {low} is above high {high}", path)
                ok = False
            v = params.get(kind)
            if ok and _is_num(v) and ((_is_num(low) and v < low) or (_is_num(high) and v > high)):
                self.add("bad_range", f"{kind} {v} lies outside low..high", path)
                ok = False
            if prob:
                for nm, b in (("low", low), ("high", high)):
                    if _is_num(b) and not 0.0 <= b <= 1.0:
                        self.add("probability_out_of_range", f"`{nm}` {b} is a probability and must be in 0..1", f"{path}.{nm}")
                        ok = False
        by = obj.get("by")
        if by is not None:
            if not isinstance(by, dict):
                self.add("bad_type", "`by` must map a name to levels", f"{path}.by")
                ok = False
            else:
                self.deferred_by.append((self.file, path, obj, kind, scope, owner, prob, nonneg, levels))
        if not ok:
            return None
        return Leaf(kind=kind, params=params, source=src, grade=grade, note=note,
                    low=float(low) if _is_num(low) else None, high=float(high) if _is_num(high) else None,
                    by=by if isinstance(by, dict) else None)

    def check_params(self, params: dict, kind: str, path: str, prob: bool, nonneg: bool, levels) -> bool:
        if kind in ("value", "p"):
            v = params.get(kind)
            extra = set(params) - {kind}
            for k in sorted(extra, key=str):
                self.add("unknown_field", f"field `{k}` is not part of a number object; it is ignored", f"{path}.{k}")
            if not _is_num(v):
                self.add("bad_type", f"`{kind}` must be a number, not {v!r}", f"{path}.{kind}")
                return False
            if (prob or kind == "p") and not 0.0 <= float(v) <= 1.0:
                self.add("probability_out_of_range", f"{kind} {v} is a probability and must be in 0..1", f"{path}.{kind}")
                return False
            if nonneg and float(v) < 0:
                self.add("negative_value", f"{kind} {v} must not be negative", f"{path}.{kind}")
                return False
            return True
        if kind == "values":
            vals = params.get("values")
            for k in sorted(set(params) - {"values"}, key=str):
                self.add("unknown_field", f"field `{k}` is not part of a categorical distribution; it is ignored", f"{path}.{k}")
            if not isinstance(vals, dict) or not vals:
                self.add("bad_type", "`values` must map each level to its share", f"{path}.values")
                return False
            ok = True
            for lv, s in vals.items():
                if not _is_num(s):
                    self.add("bad_type", f"share of {lv!r} must be a number", f"{path}.values.{lv}")
                    ok = False
                elif not 0.0 <= float(s) <= 1.0:
                    self.add("probability_out_of_range", f"share {s} of {lv!r} must be in 0..1", f"{path}.values.{lv}")
                    ok = False
                if levels is not None and _level_key(lv) not in levels:
                    self.add("unknown_level", f"level {lv!r} is not one of {list(levels)}", f"{path}.values.{lv}",
                             hint=_did_you_mean(str(lv), levels))
                    ok = False
            if ok and abs(sum(float(s) for s in vals.values()) - 1.0) > 1e-6:
                self.add("values_do_not_sum_to_one", f"shares add up to {sum(float(s) for s in vals.values()):.6g}, not 1",
                         f"{path}.values")
                ok = False
            return ok
        # dist
        d = params.get("dist")
        if d not in _DIST_PARAMS:
            self.add("bad_distribution", f"unknown distribution {d!r}; use one of {', '.join(_DIST_PARAMS)}", f"{path}.dist",
                     hint=_did_you_mean(str(d), _DIST_PARAMS))
            return False
        need = _DIST_PARAMS[d]
        for k in sorted(set(params) - need - {"dist"}, key=str):
            self.add("unknown_field", f"`{k}` is not a parameter of {d}; it is ignored", f"{path}.{k}")
        for k in sorted(need - set(params)):
            self.add("bad_distribution", f"{d} needs `{k}`", f"{path}.{k}")
            return False
        try:
            _dists.validate({k: params[k] for k in need | {"dist"}})
        except Exception as e:  # noqa: BLE001 - any malformed spec is a problem, not a crash
            self.add("bad_distribution", f"{d} distribution is malformed: {e}", path)
            return False
        if d == "uniform" and float(params["low"]) > float(params["high"]):
            self.add("bad_distribution", "uniform low is above high", path)
            return False
        if nonneg:
            lo = {"fixed": "value", "uniform": "low", "lognormal": "median", "exponential": "mean"}.get(d)
            if lo and float(params[lo]) < 0:
                self.add("negative_value", f"{d} `{lo}` must not be negative here", f"{path}.{lo}")
                return False
            if d == "empirical" and any(float(v) < 0 for v in params["values"]):
                self.add("negative_value", "empirical values must not be negative here", f"{path}.values")
                return False
        return True

    # ----------------------------------------------------------------- sections
    def run(self) -> list[Problem]:
        self.catalogue_section()
        self.condition_section()
        self.variable_section()
        self.test_section()
        self.cooccurrence_section()
        self.file = None
        self.name_clashes()
        self.check_by()
        self.file = None
        self.check_cycles()
        return self.problems

    def catalogue_section(self):
        self.file = FILES["catalogue"]
        c = self.raw.get("catalogue")
        if not isinstance(c, dict):
            self.add("bad_type", "catalogue.yaml must be a mapping", "catalogue")
            return
        if c.get("format") != FORMAT:
            self.add("bad_format", f"`format` must be {FORMAT!r}, not {c.get('format')!r}", "format")
        cid = self.need(c, "id", "", str)
        if cid is not None:
            self.check_id(cid, "id")
        self.need(c, "title", "", str)
        st = c.get("status", "draft")
        if st not in STATUSES:
            self.add("bad_value", f"status {st!r} is not one of {', '.join(STATUSES)}", "status")
        ma = c.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        if not isinstance(ma, int) or isinstance(ma, bool) or ma < 1:
            self.add("bad_type", "`max_attempts` must be a whole number of at least 1", "max_attempts")
        self.unknown_fields(c, ("format", "id", "version", "title", "status", "scope", "max_attempts", "background", "note"), "")
        bg = c.get("background") or []
        if not isinstance(bg, list):
            self.add("bad_type", "`background` must be a list of fields", "background")
            bg = []
        for i, f in enumerate(bg):
            p = f"background[{i}]"
            if not isinstance(f, dict):
                self.add("bad_type", "a background field must be a mapping", p)
                continue
            fid = self.need(f, "id", p, str)
            if fid is None or not self.check_id(fid, f"{p}.id"):
                continue
            p = f"background.{fid}"
            if fid in self.background:
                self.add("duplicate_id", f"background field {fid!r} is defined twice", p)
                continue
            t = f.get("type")
            if t not in BACKGROUND_TYPES:
                self.add("bad_value", f"type {t!r} is not one of {', '.join(BACKGROUND_TYPES)}", f"{p}.type")
            if t == "categorical":
                self.levels_list(f, p)
            self.range_check(f, p)
            self.unknown_fields(f, ("id", "label", "type", "unit", "values", "range", "note"), p)
            self.background[fid] = f

    def levels_list(self, obj: dict, path: str) -> tuple:
        vals = obj.get("values")
        if not isinstance(vals, list) or not vals or not all(isinstance(v, (str, bool, int)) for v in vals):
            self.add("missing_field", "a categorical needs `values`: a list of its levels", f"{path}.values")
            return ()
        lv = tuple(_level_key(v) for v in vals)
        if len(set(lv)) != len(lv):
            self.add("duplicate_id", "a level is listed twice", f"{path}.values")
        return lv

    def range_check(self, obj: dict, path: str):
        r = obj.get("range")
        if r is None:
            return
        if not isinstance(r, dict) or not all(k in ("min", "max") for k in r) or \
                not all(_is_num(v) for v in r.values()):
            self.add("bad_type", "`range` must be {min: number, max: number}", f"{path}.range")
            return
        if "min" in r and "max" in r and r["min"] > r["max"]:
            self.add("bad_range", f"range min {r['min']} is above max {r['max']}", f"{path}.range")

    def condition_section(self):
        self.file = FILES["conditions"]
        for i, c in enumerate(self.entries("conditions")):
            cid = self.need(c, "id", f"conditions[{i}]", str)
            if cid is None or not self.check_id(cid, f"conditions[{i}].id"):
                continue
            p = f"conditions.{cid}"
            if cid in self.conditions:
                self.add("duplicate_id", f"condition {cid!r} is defined twice", p)
                continue
            self.conditions[cid] = c
            self.need(c, "label", p, str)
            cls = c.get("class")
            if cls not in CONDITION_CLASSES:
                self.add("bad_value", f"class {cls!r} is not one of {', '.join(CONDITION_CLASSES)}", f"{p}.class")
            c["_prevalence"] = self.leaf(c.get("prevalence"), f"{p}.prevalence", ("value",), prob=True,
                                         owner="condition")
            attrs = c.get("attributes") or {}
            if not isinstance(attrs, dict):
                self.add("bad_type", "`attributes` must map a name to a categorical distribution", f"{p}.attributes")
                attrs = {}
            self.attributes[cid] = {}
            c["_attributes"] = {}
            for a, spec in attrs.items():
                ap = f"{p}.attributes.{a}"
                if not self.check_id(a, ap):
                    continue
                lf = self.leaf(spec, ap, ("values",), scope=cid, owner=f"attr:{cid}.{a}")
                if lf is not None:
                    self.attributes[cid][a] = tuple(_level_key(k) for k in lf.params["values"])
                    c["_attributes"][a] = lf
            self.unknown_fields(c, ("id", "label", "class", "prevalence", "attributes", "note", "_prevalence", "_attributes"), p)
        prevs = [c["_prevalence"].params["value"] for c in self.conditions.values() if c.get("_prevalence")]
        if prevs and len(prevs) == len(self.conditions) and abs(sum(prevs) - 1.0) > 1e-3:
            self.add("prevalence_sum", f"prevalences add up to {sum(prevs):.4g}, not 1", "conditions")

    def variable_section(self):
        self.file = FILES["variables"]
        entries = self.entries("variables")
        # first collect ids and types so `given` levels and only_if names can be checked in any order
        for i, v in enumerate(entries):
            vid = self.need(v, "id", f"variables[{i}]", str)
            if vid is None or not self.check_id(vid, f"variables[{i}].id"):
                continue
            if vid in self.variables:
                self.add("duplicate_id", f"variable {vid!r} is defined twice", f"variables.{vid}")
                continue
            self.variables[vid] = v
        for vid, v in self.variables.items():
            p = f"variables.{vid}"
            self.need(v, "label", p, str)
            if v.get("kind") not in VARIABLE_KINDS:
                self.add("bad_value", f"kind {v.get('kind')!r} is not one of {', '.join(VARIABLE_KINDS)}", f"{p}.kind")
            t = v.get("type")
            if t not in VARIABLE_TYPES:
                self.add("bad_value", f"type {t!r} is not one of {', '.join(VARIABLE_TYPES)}", f"{p}.type")
            levels = self.levels_list(v, p) if t == "categorical" else None
            v["_levels"] = levels or ()
            if t in ("continuous", "size_mm"):
                self.range_check(v, p)
            oi = v.get("only_if")
            if oi is not None:
                names = self.expression(oi, f"{p}.only_if", set(self.variables) | set(self.background), "variable or background field")
                for n in names:
                    if n in self.variables:
                        self.edge(f"var:{n}", f"var:{vid}")
                    if n == vid:
                        self.add("by_cycle", f"{vid} depends on itself through only_if", f"{p}.only_if")
            given = v.get("given")
            if not isinstance(given, dict) or not given:
                self.add("missing_field", "`given` (a distribution per condition) is required", f"{p}.given")
                v["_given"] = {}
                continue
            kinds = {"binary": ("p",), "continuous": ("dist",), "size_mm": ("dist",), "categorical": ("values",)}.get(t, ("p", "dist", "values"))
            v["_given"] = {}
            for cond, spec in given.items():
                gp = f"{p}.given.{cond}"
                if cond != "default" and cond not in self.conditions:
                    self.add("unknown_condition", f"`given` names condition {cond!r}, which is not in conditions.yaml", gp,
                             hint=_did_you_mean(str(cond), set(self.conditions) | {"default"}))
                    continue
                lf = self.leaf(spec, gp, kinds, nonneg=t == "size_mm", levels=levels,
                               scope=None if cond == "default" else cond, owner=f"var:{vid}")
                if lf is not None:
                    v["_given"][cond] = lf
            if "default" not in given:
                missing = [c for c in self.conditions if c not in given]
                if missing:
                    self.add("missing_given", f"no entry for {', '.join(missing)} and no `default`", f"{p}.given")
            self.unknown_fields(v, ("id", "label", "kind", "type", "unit", "values", "range", "only_if", "given", "note",
                                    "_levels", "_given"), p)

    def test_section(self):
        self.file = FILES["tests"]
        cat = self.raw.get("catalogue") if isinstance(self.raw.get("catalogue"), dict) else {}
        cmax = cat.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        entries = self.entries("tests")
        for i, t in enumerate(entries):
            tid = self.need(t, "id", f"tests[{i}]", str)
            if tid is None or not self.check_id(tid, f"tests[{i}].id"):
                continue
            if tid in self.tests:
                self.add("duplicate_id", f"test {tid!r} is defined twice", f"tests.{tid}")
                continue
            self.tests[tid] = t
        for tid, t in self.tests.items():
            p = f"tests.{tid}"
            self.need(t, "label", p, str)
            if t.get("category") not in TEST_CATEGORIES:
                self.add("bad_value", f"category {t.get('category')!r} is not one of {', '.join(TEST_CATEGORIES)}", f"{p}.category")
            ma = t.get("max_attempts", cmax)
            if not isinstance(ma, int) or isinstance(ma, bool) or ma < 1 or (isinstance(cmax, int) and ma > cmax):
                self.add("bad_value", f"`max_attempts` must be a whole number from 1 to the catalogue's {cmax}", f"{p}.max_attempts")
            outs = t.get("outputs")
            t["_outputs"] = []
            if not isinstance(outs, list) or not outs:
                self.add("missing_field", "`outputs` (what the test reports) is required", f"{p}.outputs")
                outs = []
            out_ids: list[str] = []
            for j, o in enumerate(outs):
                if not isinstance(o, dict):
                    self.add("bad_type", "an output must be a mapping", f"{p}.outputs[{j}]")
                    continue
                oid = self.need(o, "id", f"{p}.outputs[{j}]", str)
                if oid is None or not self.check_id(oid, f"{p}.outputs[{j}].id"):
                    continue
                if oid in out_ids:
                    self.add("duplicate_id", f"output {oid!r} is defined twice", f"{p}.outputs.{oid}")
                    continue
                out_ids.append(oid)
            for o in outs:
                if isinstance(o, dict) and o.get("id") in out_ids:
                    built = self.output(o, f"{p}.outputs.{o['id']}", out_ids)
                    if built is not None:
                        t["_outputs"].append(built)
            pw = t.get("positive_when")
            if pw is None:
                self.add("no_positive_when", "no `positive_when`: the adapter cannot read this test as yes/no", p)
            else:
                self.expression(pw, f"{p}.positive_when", set(out_ids), "output of this test")
            nd = t.get("nondiagnostic")
            t["_nondiagnostic"] = None if nd is None else self.leaf(nd, f"{p}.nondiagnostic", ("value",), prob=True)
            timing = t.get("timing") or {}
            t["_timing"] = {}
            if not isinstance(timing, dict):
                self.add("bad_type", "`timing` must be a mapping", f"{p}.timing")
                timing = {}
            for k, spec in timing.items():
                if k not in ("service_days", "report_days"):
                    self.add("unknown_field", f"timing `{k}` is not part of the format; it is ignored", f"{p}.timing.{k}")
                    continue
                lf = self.leaf(spec, f"{p}.timing.{k}", ("value", "dist"), nonneg=True)
                if lf is not None:
                    t["_timing"][k] = lf
            ce = t.get("cost_eur")
            t["_cost"] = None if ce is None else self.leaf(ce, f"{p}.cost_eur", ("value",), nonneg=True)
            if "invasive" in t and not isinstance(t["invasive"], bool):
                self.add("bad_type", "`invasive` must be true or false", f"{p}.invasive")
            if "resource_kind" in t and not isinstance(t["resource_kind"], str):
                self.add("bad_type", "`resource_kind` must be text", f"{p}.resource_kind")
            harm = t.get("harm") or {}
            t["_harm"] = {}
            if not isinstance(harm, dict):
                self.add("bad_type", "`harm` must be a mapping", f"{p}.harm")
                harm = {}
            for k, spec in harm.items():
                lf = self.leaf(spec, f"{p}.harm.{k}", ("value",), prob=True)
                if lf is not None:
                    t["_harm"][k] = lf
            req = t.get("requires") or []
            if not isinstance(req, list):
                self.add("bad_type", "`requires` must be a list", f"{p}.requires")
                req = []
            t["_requires"] = req
            self.unknown_fields(t, ("id", "label", "category", "max_attempts", "outputs", "nondiagnostic", "positive_when",
                                    "timing", "resource_kind", "cost_eur", "invasive", "harm", "requires", "note",
                                    "_outputs", "_nondiagnostic", "_timing", "_cost", "_harm", "_requires"), p)
        for tid, t in self.tests.items():
            for r in t.get("_requires", []):
                rt, _, ro = str(r).partition(".")
                if rt not in self.tests:
                    self.add("unknown_test", f"`requires` names test {rt!r}, which is not in tests.yaml", f"tests.{tid}.requires",
                             hint=_did_you_mean(rt, self.tests))
                elif ro and ro not in [o.get("id") for o in self.tests[rt].get("outputs") or [] if isinstance(o, dict)]:
                    self.add("unknown_test", f"test {rt!r} has no output {ro!r}", f"tests.{tid}.requires")

    def output(self, o: dict, p: str, out_ids: list[str]) -> TestOutput | None:
        t = o.get("type")
        if t not in VARIABLE_TYPES:
            self.add("bad_value", f"type {t!r} is not one of {', '.join(VARIABLE_TYPES)}", f"{p}.type")
            return None
        m = o.get("measures")
        if m is None:
            self.add("missing_field", "`measures` (the variable this output reports) is required", f"{p}.measures")
            return None
        if m not in self.variables:
            self.add("unknown_variable", f"output measures {m!r}, which is not in variables.yaml", f"{p}.measures",
                     hint=_did_you_mean(str(m), self.variables))
            return None
        var = self.variables[m]
        if var.get("type") != t:
            self.add("type_mismatch", f"output is {t} but variable {m!r} is {var.get('type')}", f"{p}.type")
            return None
        unit = o.get("unit", var.get("unit"))
        if t == "continuous" and o.get("unit") is not None and var.get("unit") is not None and o["unit"] != var["unit"]:
            self.add("type_mismatch", f"unit {o['unit']!r} differs from the variable's {var['unit']!r}", f"{p}.unit")
        oi = o.get("only_if")
        if oi is not None:
            self.expression(oi, f"{p}.only_if", set(out_ids) - {o["id"]}, "other output of this test")
        allowed = {"binary": ("sensitivity", "specificity"), "categorical": ("accuracy",),
                   "continuous": ("error_sd",), "size_mm": ("error_sd",)}[t]
        required = {"binary": ("sensitivity", "specificity"), "categorical": ("accuracy",)}.get(t, ())
        leaves: dict[str, Leaf | None] = {}
        for name in ("sensitivity", "specificity", "accuracy", "error_sd"):
            spec = o.get(name)
            if spec is None:
                if name in required:
                    self.add("missing_field", f"a {t} output needs `{name}`", f"{p}.{name}")
                continue
            if name not in allowed:
                self.add("unknown_field", f"`{name}` does not apply to a {t} output; it is ignored", f"{p}.{name}")
                continue
            leaves[name] = self.leaf(spec, f"{p}.{name}", ("value",), prob=name != "error_sd", nonneg=name == "error_sd")
        self.unknown_fields(o, ("id", "type", "measures", "unit", "only_if", "sensitivity", "specificity", "accuracy",
                                "error_sd", "note"), p)
        if any(leaves.get(n) is None for n in required):
            return None
        return TestOutput(id=o["id"], type=t, measures=m, unit=unit if t == "continuous" else ("mm" if t == "size_mm" else None),
                          values=tuple(var.get("_levels") or ()), only_if=oi, **leaves)

    def cooccurrence_section(self):
        self.file = FILES["cooccurrence"]
        sums: dict[str, float] = {}
        seen = set()
        for i, e in enumerate(self.entries("cooccurrence")):
            p = f"cooccurrence[{i}]"
            pr, co = e.get("primary"), e.get("coexisting")
            ok = True
            for nm, x in (("primary", pr), ("coexisting", co)):
                if x is None:
                    self.add("missing_field", f"`{nm}` is required", f"{p}.{nm}")
                    ok = False
                elif x not in self.conditions:
                    self.add("unknown_condition", f"{nm} {x!r} is not in conditions.yaml", f"{p}.{nm}",
                             hint=_did_you_mean(str(x), self.conditions))
                    ok = False
            if ok and pr == co:
                self.add("bad_cooccurrence", "a condition cannot co-exist with itself", p)
                ok = False
            if ok and self.conditions[co].get("class") != "other_illness":
                self.add("bad_cooccurrence", f"co-existing {co!r} must be of class other_illness", f"{p}.coexisting")
                ok = False
            if ok and (pr, co) in seen:
                self.add("duplicate_id", f"pair {pr} + {co} is listed twice", p)
                ok = False
            seen.add((pr, co))
            lf = self.leaf(e.get("share"), f"{p}.share", ("value",), prob=True)
            e["_share"] = lf
            self.unknown_fields(e, ("primary", "coexisting", "share", "note", "_share"), p)
            if ok and lf is not None:
                sums[pr] = sums.get(pr, 0.0) + float(lf.params["value"])
        for pr, s in sums.items():
            if s > 1.0 + 1e-9:
                self.add("bad_cooccurrence", f"co-existing shares of {pr!r} add up to {s:.4g} (> 1; at most one co-existing illness)",
                         "cooccurrence")

    def name_clashes(self):
        owners: dict[str, list[str]] = {}
        for n in self.variables:
            owners.setdefault(n, []).append("variable")
        for n in self.tests:
            owners.setdefault(n, []).append("test")
        for n in self.background:
            owners.setdefault(n, []).append("background field")
        for n in {a for attrs in self.attributes.values() for a in attrs}:
            owners.setdefault(n, []).append("condition attribute")
        for n, kinds in owners.items():
            if len(kinds) > 1:
                self.add("ambiguous_name", f"{n!r} is both a {' and a '.join(kinds)}", n)

    # ----------------------------------------------------------------- expressions, `by`, cycles
    def expression(self, source: Any, path: str, known: set, what: str) -> frozenset:
        try:
            e = _expr.parse(source)
        except _expr.ExprError as ex:
            self.add("bad_expression", f"cannot read {source!r}: {ex}", path, hint=ex.hint)
            return frozenset()
        for n in sorted(e.names):
            if n not in known:
                code = "unknown_variable" if what.startswith("variable") else "bad_expression"
                self.add(code, f"{source!r} reads {n!r}, which is not a {what}", path, hint=_did_you_mean(n, known))
        return e.names

    def edge(self, a: str, b: str):
        self.edges.setdefault(a, set()).add(b)

    def ref_levels(self, ref: str, scope: str | None) -> tuple[str, Any, list[str]] | None:
        """(what, levels or 'bands', graph nodes) for a `by:` key, or None if unknown."""
        if ref == "condition":
            return "condition", tuple(self.conditions), ["condition"]
        if scope is not None and ref in self.attributes.get(scope, {}):
            return "attribute", self.attributes[scope][ref], [f"attr:{scope}.{ref}"]
        owners = [c for c, attrs in self.attributes.items() if ref in attrs]
        if owners:
            lv = tuple(dict.fromkeys(x for c in owners for x in self.attributes[c][ref]))
            return "attribute", lv, [f"attr:{c}.{ref}" for c in owners]
        if ref in self.variables:
            v = self.variables[ref]
            t = v.get("type")
            lv = ("true", "false") if t == "binary" else v.get("_levels") if t == "categorical" else "bands"
            return "variable", lv, [f"var:{ref}"]
        if ref in self.background:
            f = self.background[ref]
            t = f.get("type")
            lv = ("true", "false") if t == "binary" else tuple(_level_key(x) for x in f.get("values") or ()) \
                if t == "categorical" else "bands"
            return "background", lv, []
        return None

    def check_by(self):
        for file, path, obj, kind, scope, owner, prob, nonneg, levels in self.deferred_by:
            self.file = file
            self.check_by_tree(obj, path, kind, scope, owner, prob, nonneg, levels, dict(obj))

    def check_by_tree(self, obj, path, kind, scope, owner, prob, nonneg, levels, base: dict):
        for ref, lv in obj["by"].items():
            bp = f"{path}.by.{ref}"
            info = self.ref_levels(str(ref), scope)
            if info is None:
                known = {"condition"} | set(self.variables) | set(self.background) | \
                    {a for attrs in self.attributes.values() for a in attrs}
                self.add("unknown_reference", f"`by` reads {ref!r}, which is not a condition attribute, variable, "
                         "background field or `condition`", bp, hint=_did_you_mean(str(ref), known))
                continue
            what, allowed, nodes = info
            if owner is not None:
                for n in nodes:
                    self.edge(n, owner)
            if not isinstance(lv, dict) or not lv:
                self.add("bad_type", f"`by.{ref}` must map levels to numbers", bp)
                continue
            if allowed == "bands":
                bands = []
                for k in lv:
                    b = _band(k)
                    if b is None:
                        self.add("bad_band", f"level {k!r} of the numeric {ref!r} is not a band like '..20', '20..40' or '40..'",
                                 f"{bp}.{k}")
                    else:
                        bands.append(b)
                bands.sort()
                for a, b in zip(bands, bands[1:]):
                    if b[0] < a[1]:
                        self.add("bad_band", f"bands of {ref!r} overlap", bp)
                        break
            else:
                for k in lv:
                    if _level_key(k) not in allowed:
                        code = "unknown_condition" if what == "condition" else "unknown_level"
                        self.add(code, f"level {k!r} of {ref!r} is not one of {list(allowed)}", f"{bp}.{k}",
                                 hint=_did_you_mean(_level_key(k), allowed))
            for k, ov in lv.items():
                lp = f"{bp}.{_level_key(k)}"
                if _is_num(ov):
                    if kind not in ("value", "p"):
                        self.add("bad_type", f"a {kind} needs a mapping of its own keys at each level, not a number", lp)
                    else:
                        self.check_params({kind: ov}, kind, lp, prob, nonneg, levels)
                elif isinstance(ov, dict):
                    if "source" in ov and (not isinstance(ov["source"], str) or
                                           (ov["source"] != ASSUMPTION and ov["source"] not in self.sources)):
                        self.add("unknown_source", f"source {ov['source']!r} is not in params/sources.yaml", f"{lp}.source",
                                 hint=_did_you_mean(str(ov["source"]), self.sources | {ASSUMPTION}))
                    if "grade" in ov and ov["grade"] not in GRADES:
                        self.add("bad_grade", f"grade {ov['grade']!r} is not one of {', '.join(GRADES)}", f"{lp}.grade")
                    merged = {k2: v2 for k2, v2 in base.items() if k2 not in _META}
                    merged.update({k2: v2 for k2, v2 in ov.items() if k2 not in _META})
                    if kind in ("value", "p"):
                        merged = {kind: merged.get(kind)}
                    self.check_params(merged, kind, lp, prob, nonneg, levels)
                    if isinstance(ov.get("by"), dict):
                        self.check_by_tree(ov, lp, kind, scope, owner, prob, nonneg, levels, merged)
                else:
                    self.add("bad_type", f"level {k!r} must be a number or a mapping", lp)

    def check_cycles(self):
        # implicit edges: the primary condition decides attributes and variables
        for c, attrs in self.attributes.items():
            for a in attrs:
                self.edge("condition", f"attr:{c}.{a}")
        for v in self.variables:
            self.edge("condition", f"var:{v}")
        color: dict[str, int] = {}
        stack: list[str] = []
        reported: set[frozenset] = set()

        def visit(n: str):
            color[n] = 1
            stack.append(n)
            for m in sorted(self.edges.get(n, ())):
                if color.get(m) == 1:
                    cyc = stack[stack.index(m):] + [m]
                    key = frozenset(cyc)
                    if key not in reported:
                        reported.add(key)
                        self.add("by_cycle", "dependencies form a loop: " + " -> ".join(_node_label(x) for x in cyc),
                                 _node_label(m))
                elif color.get(m) is None:
                    visit(m)
            stack.pop()
            color[n] = 2

        for n in sorted(self.edges):
            if color.get(n) is None:
                visit(n)


def _node_label(n: str) -> str:
    kind, _, name = n.partition(":")
    return {"var": f"variables.{name}", "attr": f"conditions.{name.replace('.', '.attributes.', 1)}"}.get(kind, "condition prevalence")


def _tname(typ) -> str:
    names = {str: "text", list: "a list", dict: "a mapping", int: "a whole number", bool: "true or false"}
    if isinstance(typ, tuple):
        return " or ".join(names.get(t, t.__name__) for t in typ)
    return names.get(typ, typ.__name__)


def _did_you_mean(name: str, known: Iterable[str]) -> str | None:
    m = difflib.get_close_matches(name, [str(k) for k in known], n=1, cutoff=0.7)
    return f"Did you mean {m[0]!r}?" if m else None


def validate_catalogue(raw: Mapping[str, Any], sources=None) -> list[Problem]:
    """Every problem of a raw catalogue dict (see module doc). Does not modify ``raw``."""
    return _validate(raw, sources)[0]


def _validate(raw: Mapping[str, Any], sources=None) -> tuple[list[Problem], _Validator]:
    import copy
    v = _Validator(copy.deepcopy(dict(raw)), _known_sources(sources))
    return v.run(), v


# ============================================================================ build

def _range(obj: Mapping) -> tuple[float | None, float | None]:
    r = obj.get("range") or {}
    return (float(r["min"]) if "min" in r else None, float(r["max"]) if "max" in r else None)


def build_catalogue(raw: Mapping[str, Any], sources=None, path: str | None = None) -> Catalogue:
    """Validate ``raw`` and build a ``Catalogue``; raise ``CatalogueError`` on any error."""
    problems, v = _validate(raw, sources)
    if any(p.severity == ERROR for p in problems):
        raise CatalogueError(problems, path)
    c = v.raw["catalogue"]
    background = {
        fid: BackgroundField(id=fid, type=f["type"], label=f.get("label"), unit=f.get("unit"),
                             values=tuple(_level_key(x) for x in f.get("values") or ()), range=_range(f))
        for fid, f in v.background.items()}
    conditions = {
        cid: Condition(id=cid, label=x["label"], cls=x["class"], prevalence=x["_prevalence"],
                       attributes=dict(x["_attributes"]), note=x.get("note"))
        for cid, x in v.conditions.items()}
    variables = {
        vid: Variable(id=vid, label=x["label"], kind=x["kind"], type=x["type"], given=dict(x["_given"]),
                      unit="mm" if x["type"] == "size_mm" else x.get("unit"), values=tuple(x["_levels"]),
                      range=_range(x), only_if=x.get("only_if"), note=x.get("note"))
        for vid, x in v.variables.items()}
    cmax = int(c.get("max_attempts", DEFAULT_MAX_ATTEMPTS))
    tests = {
        tid: Test(id=tid, label=x["label"], category=x["category"], outputs=tuple(x["_outputs"]),
                  max_attempts=int(x.get("max_attempts", cmax)), positive_when=x.get("positive_when"),
                  nondiagnostic=x["_nondiagnostic"], timing=dict(x["_timing"]), resource_kind=x.get("resource_kind"),
                  cost_eur=x["_cost"], invasive=bool(x.get("invasive", False)), harm=dict(x["_harm"]),
                  requires=tuple(str(r) for r in x["_requires"]), note=x.get("note"))
        for tid, x in v.tests.items()}
    cooc = tuple(Cooccurrence(e["primary"], e["coexisting"], e["_share"]) for e in v.entries("cooccurrence"))
    return Catalogue(
        id=c["id"], version=c.get("version"), title=c["title"], status=c.get("status", "draft"),
        scope=str(c.get("scope") or "").strip(), max_attempts=cmax, background=background, conditions=conditions,
        variables=variables, tests=tests, cooccurrence=cooc, version_hash=version_hash(raw), path=path,
        problems=tuple(problems), raw=dict(raw))


def load_catalogue(path: str | Path, sources=None) -> Catalogue:
    """Read, validate and build the catalogue in folder ``path``. Raises ``CatalogueError`` (with
    ``.problems``) if any file is missing or unreadable or any check fails; warnings are kept on
    ``Catalogue.problems``."""
    raw, problems = read_catalogue(path)
    if problems:
        raise CatalogueError(problems, str(path))
    return build_catalogue(raw, sources, str(path))

"""JSON Schema of a ``card/1`` card, generated from a catalogue, and a small validator for it.

``card_schema(catalogue)`` returns a plain dict, JSON Schema draft 2020-12. It is what the language
model is asked to fill (structured output) and what every stored card must match:

- ``background``: every background field of the catalogue, typed (enum for categorical, bounds from
  ``range``).
- ``states``: allowed state names (``Catalogue.states()``), the first is ``all_active``.
- ``hidden.conditions``: one entry per condition the patient has; ``id`` and ``attributes`` must be the
  catalogue's (levels as enums); only ``other_illness`` conditions may have ``role: coexisting``.
- ``hidden.findings[state]``: every catalogue variable, typed, with ``caused_by`` (condition ids).
  Variables with ``only_if`` may be ``null``.
- ``hidden.error_plan``: ``null`` or, per state and test, a planned status and outcome per output.
- ``observations[state]``: every catalogue test (and no other), 1..``max_attempts`` attempts, each
  either ``{"status": "ok", "values": {every output, typed}, "report": text}`` or, for tests with a
  ``nondiagnostic`` rate, ``{"status": "non_diagnostic", "values": {}, "report": text}``.
- ``notes``: ``mentions`` from the variable ids, test ids and ``test.output`` keys.

What a schema cannot say (keys of ``presenting``/``findings``/``observations`` equal ``states``, exactly
one primary condition, findings consistent with conditions) is the card validator's job (WP-C1-4).

``schema_problems(instance, schema)`` checks an instance against the subset of JSON Schema this
module generates (type, enum, const, properties, required, additionalProperties, propertyNames,
min/maxProperties, items, prefixItems, min/maxItems, uniqueItems, minimum, maximum, minLength,
anyOf, oneOf, local ``$ref``). It exists so the engine needs no third-party package; the tests also
check the generated schema with the ``jsonschema`` package when it is installed.
"""

from __future__ import annotations

from typing import Any

from .card import CARD_FORMAT, ERROR_SOURCES, GENERATORS, INITIAL_STATE, NOTE_KINDS, OUTCOMES, ROLES, STATUSES
from .problems import Problem

DRAFT = "https://json-schema.org/draft/2020-12/schema"


# ============================================================================ generation

def _obj(props: dict, required: list | None = None, extra: bool = False, **kw) -> dict:
    d = {"type": "object", "properties": props, "required": list(props) if required is None else required,
         "additionalProperties": extra}
    d.update(kw)
    return d


def _nullable(s: dict) -> dict:
    s = dict(s)
    if "enum" in s:
        s["enum"] = [*s["enum"], None]
    else:
        t = s["type"]
        s["type"] = [t, "null"] if isinstance(t, str) else [*t, "null"]
    return s


def _ranged(s: dict, rng) -> dict:
    lo, hi = rng
    if lo is not None:
        s["minimum"] = lo
    if hi is not None:
        s["maximum"] = hi
    return s


def _value_schema(type_: str, values=(), rng=(None, None), nullable: bool = False) -> dict:
    if type_ == "binary":
        s: dict = {"type": "boolean"}
    elif type_ == "categorical":
        s = {"enum": list(values)}
    elif type_ == "size_mm":
        lo, hi = rng
        s = _ranged({"type": "number"}, (0 if lo is None else lo, hi))
    else:
        s = _ranged({"type": "number"}, rng)
    return _nullable(s) if nullable else s


def card_schema(catalogue) -> dict:
    """JSON Schema (draft 2020-12) of a complete card for ``catalogue`` (a ``Catalogue``)."""
    cat = catalogue
    states = list(cat.states())
    cond_ids = list(cat.conditions)
    var_ids = list(cat.variables)
    mentions = [*var_ids, *cat.tests, *(f"{t.id}.{o.id}" for t in cat.tests.values() for o in t.outputs)]
    defs: dict[str, Any] = {}

    defs["state"] = {"enum": states}

    # background
    bg = {f.id: _value_schema(f.type, f.values, f.range) for f in cat.background.values()}
    for f in cat.background.values():
        if f.type == "continuous" and f.unit:
            bg[f.id]["description"] = f.unit

    # conditions: one shape per condition
    cond_shapes = []
    for c in cat.conditions.values():
        attrs = {a: {"enum": list(lf.params["values"])} for a, lf in c.attributes.items()}
        roles = list(ROLES) if c.cls == "other_illness" else ["primary"]
        cond_shapes.append(_obj({"id": {"const": c.id}, "role": {"enum": roles}, "attributes": _obj(attrs)}))
    defs["condition"] = {"anyOf": cond_shapes}

    # findings in one state
    caused_by = {"type": "array", "items": {"enum": cond_ids}, "uniqueItems": True}
    findings = {}
    for v in cat.variables.values():
        findings[v.id] = _obj({"value": _value_schema(v.type, v.values, v.range, nullable=v.only_if is not None),
                               "caused_by": caused_by})
    defs["findings"] = _obj(findings)

    # observations: one attempt shape per test
    obs_props = {}
    plan_props = {}
    for t in cat.tests.values():
        outs = {o.id: _value_schema(o.type, o.values, cat.variables[o.measures].range if o.type != "categorical" else (None, None),
                                    nullable=o.only_if is not None)
                for o in t.outputs}
        ok = _obj({"status": {"const": "ok"}, "values": _obj(outs), "report": {"type": "string"}})
        if t.nondiagnostic is not None:
            nd = _obj({"status": {"const": "non_diagnostic"}, "values": {"type": "object", "maxProperties": 0},
                       "report": {"type": "string"}})
            defs[f"attempt__{t.id}"] = {"oneOf": [ok, nd]}
        else:
            defs[f"attempt__{t.id}"] = ok
        obs_props[t.id] = {"type": "array", "minItems": 1, "maxItems": t.max_attempts,
                           "items": {"$ref": f"#/$defs/attempt__{t.id}"}}
        planned = _obj({"status": {"enum": list(STATUSES)},
                        "outputs": _obj({o.id: {"enum": list(OUTCOMES)} for o in t.outputs}, required=[])})
        plan_props[t.id] = {"type": "array", "minItems": 1, "maxItems": t.max_attempts, "items": planned}
    defs["observations"] = _obj(obs_props)
    defs["error_plan_state"] = _obj(plan_props, required=[])

    presenting = _obj({"reported": {"type": "array", "items": {"enum": var_ids}, "uniqueItems": True},
                       "text": {"type": ["string", "null"]}})
    note = _obj({"id": {"type": "string", "minLength": 1}, "kind": {"enum": list(NOTE_KINDS)},
                 "state": {"$ref": "#/$defs/state"}, "text": {"type": "string"},
                 "mentions": {"type": "array", "items": {"enum": mentions}, "uniqueItems": True}})

    def by_state(ref: str) -> dict:
        return {"type": "object", "propertyNames": {"$ref": "#/$defs/state"}, "minProperties": 1,
                "additionalProperties": {"$ref": ref}}

    hidden = _obj({
        "conditions": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/condition"}},
        "findings": by_state("#/$defs/findings"),
        "error_plan": {"anyOf": [{"type": "null"}, by_state("#/$defs/error_plan_state")]},
    })
    provenance = _obj({
        "library": {"type": ["string", "null"]},
        "catalogue_id": {"const": cat.id},
        "catalogue_hash": {"type": "string", "minLength": 1},
        "generator": {"enum": list(GENERATORS)},
        "model": {"type": ["string", "null"]},
        "prompts": {"type": "object", "additionalProperties": {"type": "string"}},
        "error_source": {"enum": [*ERROR_SOURCES, None]},
        "validation": {"type": "object"},
    })
    return {
        "$schema": DRAFT,
        "$id": f"urn:patient-engine:{CARD_FORMAT}:{cat.id}",
        "title": f"{CARD_FORMAT} card for catalogue {cat.id}",
        "description": f"Generated from catalogue {cat.id} (version hash {cat.version_hash}).",
        **_obj({
            "format": {"const": CARD_FORMAT},
            "id": {"type": "string", "minLength": 1},
            "background": _obj(bg),
            "states": {"type": "array", "minItems": 1, "uniqueItems": True,
                       "prefixItems": [{"const": INITIAL_STATE}], "items": {"$ref": "#/$defs/state"}},
            "presenting": {"type": "object", "propertyNames": {"$ref": "#/$defs/state"}, "minProperties": 1,
                           "additionalProperties": presenting},
            "hidden": hidden,
            "observations": by_state("#/$defs/observations"),
            "notes": {"type": "array", "items": note},
            "provenance": provenance,
        }),
        "$defs": defs,
    }


# ============================================================================ validation (the subset above)

_TYPES = {
    "object": lambda x: isinstance(x, dict),
    "array": lambda x: isinstance(x, list),
    "string": lambda x: isinstance(x, str),
    "boolean": lambda x: isinstance(x, bool),
    "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
    "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
    "null": lambda x: x is None,
}


def _eq(a, b) -> bool:
    """JSON equality: booleans are not numbers."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _join(path: str, key) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else str(key)


def _check(x: Any, s: dict, root: dict, path: str, out: list[tuple[str, str]]) -> None:
    if "$ref" in s:
        ref = s["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"only local $ref is supported, not {ref!r}")
        target: Any = root
        for part in ref[2:].split("/"):
            target = target[part]
        _check(x, target, root, path, out)
    t = s.get("type")
    if t is not None:
        ts = [t] if isinstance(t, str) else t
        if not any(_TYPES[k](x) for k in ts):
            out.append((path, f"expected {' or '.join(ts)}, got {_jtype(x)}"))
            return
    if "const" in s and not _eq(x, s["const"]):
        out.append((path, f"must be {s['const']!r}, got {x!r}"))
        return
    if "enum" in s and not any(_eq(x, e) for e in s["enum"]):
        shown = s["enum"] if len(s["enum"]) <= 12 else [*s["enum"][:12], "..."]
        out.append((path, f"{x!r} is not one of {shown}"))
        return
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if "minimum" in s and x < s["minimum"]:
            out.append((path, f"{x} is below the minimum {s['minimum']}"))
        if "maximum" in s and x > s["maximum"]:
            out.append((path, f"{x} is above the maximum {s['maximum']}"))
    if isinstance(x, str) and "minLength" in s and len(x) < s["minLength"]:
        out.append((path, f"text shorter than {s['minLength']}"))
    if isinstance(x, dict):
        props = s.get("properties", {})
        for k in s.get("required", ()):
            if k not in x:
                out.append((_join(path, k), "required field is missing"))
        if "minProperties" in s and len(x) < s["minProperties"]:
            out.append((path, f"needs at least {s['minProperties']} entries"))
        if "maxProperties" in s and len(x) > s["maxProperties"]:
            out.append((path, f"must have at most {s['maxProperties']} entries"))
        pn = s.get("propertyNames")
        for k, v in x.items():
            kp = _join(path, k)
            if pn is not None:
                sub: list = []
                _check(k, pn, root, kp, sub)
                if sub:
                    out.append((kp, f"key {k!r} is not allowed here: {sub[0][1]}"))
                    continue
            if k in props:
                _check(v, props[k], root, kp, out)
            else:
                ap = s.get("additionalProperties", True)
                if ap is False:
                    out.append((kp, f"unknown key {k!r}"))
                elif isinstance(ap, dict):
                    _check(v, ap, root, kp, out)
    if isinstance(x, list):
        if "minItems" in s and len(x) < s["minItems"]:
            out.append((path, f"needs at least {s['minItems']} items"))
        if "maxItems" in s and len(x) > s["maxItems"]:
            out.append((path, f"must have at most {s['maxItems']} items"))
        if s.get("uniqueItems"):
            seen: list = []
            for v in x:
                if any(_eq(v, w) and type(v) is type(w) for w in seen):
                    out.append((path, f"item {v!r} appears twice"))
                    break
                seen.append(v)
        prefix = s.get("prefixItems", [])
        for i, v in enumerate(x):
            if i < len(prefix):
                _check(v, prefix[i], root, _join(path, i), out)
            elif "items" in s:
                _check(v, s["items"], root, _join(path, i), out)
    for key in ("anyOf", "oneOf"):
        if key in s:
            results = []
            for branch in s[key]:
                sub = []
                _check(x, branch, root, path, sub)
                results.append(sub)
            n_ok = sum(1 for r in results if not r)
            if key == "anyOf" and n_ok == 0 or key == "oneOf" and n_ok != 1:
                if n_ok > 1:
                    out.append((path, "matches more than one allowed shape"))
                else:
                    best = min(results, key=len)
                    out.extend(best if best else [(path, "matches none of the allowed shapes")])


def _jtype(x: Any) -> str:
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _TYPES[name](x):
            return name
    return type(x).__name__


def schema_problems(instance: Any, schema: dict) -> list[Problem]:
    """Problems of ``instance`` against ``schema`` (code ``card_schema``), each with the dotted path
    of the offending part. Empty list = valid."""
    out: list[tuple[str, str]] = []
    _check(instance, schema, schema, "", out)
    return [Problem("card_schema", msg, path=p or None) for p, msg in out]

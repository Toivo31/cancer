"""Decision datasets: one row per decision (docs/platform/specs/06-datasets-training.md, ticket M6-1/M6-2).

A row is a request plus the answer that was given::

    {"decision_point": "sample_choice", "patient_id": "p1042", "t_days": 31.5,
     "context": {"group": "non_specific", "age": 67, "fast_track": false,
                 "attributes": {"location": "peripheral"},
                 "history": [{"step": "ct", "test": "chest_ct", "result": true, "t_days": 30.9}]},
     "offered": ["bronch", "ttnb"], "chosen": "ttnb",
     "outcome": {"usable_result": true, "days_to_next_milestone": 9.5},   # optional
     "option_leads": {"bronch": 6.0, "ttnb": 2.0}}                        # optional, queue state at the decision

``context`` is exactly the contract's context (spec 02): only what was revealed at the decision, never
the hidden condition. ``outcome`` is never read when training to imitate practice; it exists for
outcome-labelled data from exploration runs. The format has no free-text fields: ids and values are
short identifier-like strings, so identifiable text has nowhere to go.

This module reads (JSON lines, CSV), normalises, validates against a flowchart and its world, and builds
rows from an engine run log. It never imports the service.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter, defaultdict
from typing import Iterable

SCHEMA_VERSION = 1
MIN_CELL = 30                  # spec 06: warn when a cell the trainer estimates has fewer rows
MAX_ATTR_VALUES = 8            # a default context field must stay a small categorical
MAX_PROBLEM_ROWS = 10          # rows quoted per problem
BUILTIN_CONTEXT = ("group", "age", "t_days", "fast_track")
KNOWN_EXTRAS = ("probs", "measured", "seed", "mode", "backend", "model")     # run-export fields that are not part of the row
HIDDEN_NAMES = {"condition", "cancer", "has_cancer", "truth", "ground_truth", "true_condition", "diagnosis_true"}
_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
_VALUE = re.compile(r"^[A-Za-z0-9_.+\- ]{0,40}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CTX_KEYS = {"group", "age", "t_days", "fast_track", "attributes", "history"}
_ROW_KEYS = {"decision_point", "patient_id", "t_days", "context", "offered", "chosen", "outcome", "option_leads", "measured",
             "date"}
_OUTCOME_KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


class DatasetError(ValueError):
    """The input cannot be read at all (not a malformed row, which becomes a problem in the report)."""


# --------------------------------------------------------------------------------- problems
class Problems:
    """Collects problems grouped by (severity, code, point, message) with a count and the first rows."""

    def __init__(self):
        self._g: dict[tuple, dict] = {}

    def add(self, severity: str, code: str, message: str, point: str | None = None, row: int | None = None) -> None:
        key = (severity, code, point, message)
        g = self._g.get(key)
        if g is None:
            g = self._g[key] = {"severity": severity, "code": code, "message": message, "count": 0, "rows": []}
            if point is not None:
                g["point"] = point
        g["count"] += 1
        if row is not None and len(g["rows"]) < MAX_PROBLEM_ROWS:
            g["rows"].append(row)

    def error(self, code, message, point=None, row=None):
        self.add("error", code, message, point, row)

    def warn(self, code, message, point=None, row=None):
        self.add("warning", code, message, point, row)

    def extend(self, other: list[dict]) -> None:
        for g in other:
            key = (g["severity"], g["code"], g.get("point"), g["message"])
            mine = self._g.get(key)
            if mine is None:
                self._g[key] = dict(g, rows=list(g.get("rows", [])))
            else:
                mine["count"] += g["count"]
                mine["rows"] = (mine["rows"] + g.get("rows", []))[:MAX_PROBLEM_ROWS]

    def to_list(self) -> list[dict]:
        order = {"error": 0, "warning": 1}
        return sorted(self._g.values(), key=lambda g: (order.get(g["severity"], 2), g["code"], g.get("point") or "", g["message"]))


# --------------------------------------------------------------------------------- row normalisation
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _scalar(v) -> bool:
    if v is None or isinstance(v, bool):
        return True
    if _num(v):
        return True
    return isinstance(v, str) and bool(_VALUE.match(v))


def _result(v):
    if v is None or v is True or v is False:
        return v, True
    if v in ("+", "true", "True"):
        return True, True
    if v in ("-", "false", "False"):
        return False, True
    if v in ("?", "null", "None", ""):
        return None, True
    return None, False


def normalise_row(d, line: int, problems: Problems, ignored: Counter) -> dict | None:
    """One raw row to the canonical row, or None (with a problem recorded) when it cannot be used."""
    if not isinstance(d, dict):
        problems.error("malformed_row", "A row must be an object", row=line)
        return None
    bad = False

    def err(code, msg, point=None):
        nonlocal bad
        bad = True
        problems.error(code, msg, point or (d.get("decision_point") if isinstance(d.get("decision_point"), str) else None), line)

    pt, pid, chosen = d.get("decision_point"), d.get("patient_id"), d.get("chosen")
    if not isinstance(pt, str) or not pt:
        err("missing_field", "A row needs a 'decision_point'")
    if pid is None or isinstance(pid, bool) or not isinstance(pid, (str, int)) or not _ID.match(str(pid)):
        err("bad_patient_id", "'patient_id' must be 1-64 characters from letters, digits and _ . : -")
    if not isinstance(chosen, str) or not chosen:
        err("missing_field", "A row needs 'chosen' (an option id)")
    offered = d.get("offered")
    if not isinstance(offered, list) or not offered or not all(isinstance(o, str) and o for o in offered):
        err("bad_offered", "'offered' must be a non-empty list of option ids")
        offered = []
    t = d.get("t_days")
    if t is not None and not (_num(t) and t >= 0):
        err("bad_value", "'t_days' must be a number of days >= 0")
        t = None
    date = d.get("date")
    if date is not None and not (isinstance(date, str) and _DATE.match(date)):
        err("bad_value", "'date' must look like 2026-11-14")
        date = None

    raw_ctx = d.get("context", {})
    if raw_ctx is None:
        raw_ctx = {}
    if not isinstance(raw_ctx, dict):
        err("bad_context", "'context' must be an object")
        raw_ctx = {}
    hidden = sorted(k for k in list(d) + list(raw_ctx) if str(k).lower() in HIDDEN_NAMES or str(k).lower().startswith(("hidden", "true_")))
    if hidden:
        err("hidden_truth", f"Fields {hidden} look like hidden truth. A decision row may hold only what was known at the decision")
    for k in d:
        if k not in _ROW_KEYS and k not in hidden:
            ignored[k] += 1
    for k in raw_ctx:
        if k not in _CTX_KEYS and k not in hidden:
            ignored[f"context.{k}"] += 1

    group, age, fast = raw_ctx.get("group"), raw_ctx.get("age"), raw_ctx.get("fast_track", False)
    if group is not None and not (isinstance(group, str) and _VALUE.match(group)):
        err("bad_value", "context.group must be a short identifier")
        group = None
    if age is not None and not (_num(age) and 0 <= age <= 120):
        err("bad_value", "context.age must be a number between 0 and 120")
        age = None
    if not isinstance(fast, bool):
        err("bad_value", "context.fast_track must be true or false")
        fast = False
    attrs_in = raw_ctx.get("attributes") or {}
    attrs: dict = {}
    if not isinstance(attrs_in, dict):
        err("bad_context", "context.attributes must be an object")
    else:
        for k, v in attrs_in.items():
            if not isinstance(k, str) or not re.match(r"^[A-Za-z][A-Za-z0-9_]{0,40}$", k):
                err("bad_value", f"Attribute name {k!r} must be a short identifier")
            elif not _scalar(v):
                err("bad_value", f"Attribute {k!r} must be a short identifier-like value, not free text")
            elif str(k).lower() not in HIDDEN_NAMES:
                attrs[k] = v
    hist_in = raw_ctx.get("history") or []
    hist: list[dict] = []
    if not isinstance(hist_in, list):
        err("bad_context", "context.history must be a list")
    else:
        for h in hist_in:
            if not isinstance(h, dict) or not isinstance(h.get("step"), str) or not h["step"]:
                err("bad_context", "Every history entry needs a 'step' id")
                continue
            res, ok = _result(h.get("result"))
            ht = h.get("t_days")
            if not ok or (ht is not None and not _num(ht)):
                err("bad_value", f"History entry '{h['step']}' needs a result of true, false or null and a numeric t_days")
                continue
            e = {"step": h["step"], "result": res}
            if isinstance(h.get("test"), str) and h["test"]:
                e["test"] = h["test"]
            if ht is not None:
                e["t_days"] = float(ht)
            hist.append(e)

    outcome = d.get("outcome")
    if outcome is not None:
        if not isinstance(outcome, dict) or not all(isinstance(k, str) and _OUTCOME_KEY.match(k) and (v is None or isinstance(v, bool) or _num(v))
                                                    for k, v in outcome.items()):
            err("bad_outcome", "'outcome' must be an object of numbers, true/false or null")
            outcome = None
    leads = d.get("option_leads")
    if leads is not None:
        if not isinstance(leads, dict) or not all(isinstance(k, str) and _num(v) and v >= 0 for k, v in leads.items()):
            err("bad_value", "'option_leads' must map option ids to days >= 0")
            leads = None
    if bad:
        return None
    row = {"decision_point": pt, "patient_id": str(pid), "t_days": None if t is None else float(t),
           "context": {"group": group, "age": age, "t_days": None if t is None else float(t), "fast_track": fast,
                       "attributes": attrs, "history": hist},
           "offered": list(offered), "chosen": chosen}
    if outcome is not None:
        row["outcome"] = outcome
    if leads is not None:
        row["option_leads"] = {k: float(v) for k, v in leads.items()}
    if isinstance(d.get("measured"), bool):
        row["measured"] = d["measured"]
    if date is not None:
        row["date"] = date
    return row


# --------------------------------------------------------------------------------- Dataset
class Dataset:
    """Normalised rows plus the problems found while reading them."""

    def __init__(self, rows: list[dict] | None = None, problems: list[dict] | None = None, ignored: dict | None = None,
                 n_input: int | None = None):
        self.rows = rows or []
        self.read_problems = problems or []
        self.ignored = dict(ignored or {})
        self.n_input = len(self.rows) if n_input is None else n_input

    def __len__(self):
        return len(self.rows)

    @classmethod
    def from_rows(cls, raw_rows: Iterable, first_line: int = 1) -> "Dataset":
        problems, ignored, rows, n = Problems(), Counter(), [], 0
        for i, d in enumerate(raw_rows, first_line):
            n += 1
            r = normalise_row(d, i, problems, ignored)
            if r is not None:
                rows.append(r)
        return cls(rows, problems.to_list(), dict(ignored), n)

    @classmethod
    def from_jsonl(cls, text_or_lines: str | Iterable[str | bytes]) -> "Dataset":
        lines = text_or_lines.splitlines() if isinstance(text_or_lines, str) else text_or_lines
        problems, ignored, rows, n = Problems(), Counter(), [], 0
        for i, line in enumerate(lines, 1):
            if isinstance(line, bytes):
                line = line.decode("utf-8", "replace")
            if not line.strip():
                continue
            n += 1
            try:
                d = json.loads(line)
            except ValueError:
                problems.error("malformed_row", "Not valid JSON", row=i)
                continue
            r = normalise_row(d, i, problems, ignored)
            if r is not None:
                rows.append(r)
        return cls(rows, problems.to_list(), dict(ignored), n)

    @classmethod
    def from_csv(cls, text: str) -> "Dataset":
        """CSV: ``decision_point, patient_id, t_days, offered, chosen``; context as ``ctx.<name>`` (``group``, ``age``,
        ``fast_track`` or an attribute); results of earlier steps as ``step.<id>`` with ``+``, ``-``, ``?`` (done,
        inconclusive) or empty (not done); ``out.<name>`` for outcomes; ``offered`` is separated by ``|``."""
        rd = csv.DictReader(io.StringIO(text))
        cols = [c.strip() for c in (rd.fieldnames or [])]
        missing = [c for c in ("decision_point", "patient_id", "offered", "chosen") if c not in cols]
        if missing:
            raise DatasetError(f"The CSV needs the columns {missing} (found {cols})")
        raw = []
        for rec in rd:
            rec = {(k or "").strip(): (v or "").strip() for k, v in rec.items() if k is not None}
            d: dict = {"decision_point": rec.get("decision_point"), "patient_id": rec.get("patient_id"),
                       "offered": [o for o in re.split(r"[|;]", rec.get("offered", "")) if o], "chosen": rec.get("chosen")}
            if rec.get("t_days"):
                d["t_days"] = _try_float(rec["t_days"])
            if rec.get("date"):
                d["date"] = rec["date"]
            ctx: dict = {"attributes": {}, "history": []}
            outcome: dict = {}
            for k, v in rec.items():
                if k.startswith("ctx."):
                    name = k[4:]
                    if v == "":
                        continue
                    if name in ("age", "t_days"):
                        ctx[name] = _try_float(v)
                    elif name == "fast_track":
                        ctx[name] = v.lower() in ("1", "true", "yes", "y")
                    elif name == "group":
                        ctx[name] = v
                    else:
                        ctx["attributes"][name] = v
                elif k.startswith("step.") and v != "":
                    ctx["history"].append({"step": k[5:], "result": v})
                elif k.startswith("out.") and v != "":
                    low = v.lower()
                    outcome[k[4:]] = True if low == "true" else False if low == "false" else _try_float(v)
            d["context"] = ctx
            if outcome:
                d["outcome"] = outcome
            raw.append(d)
        return cls.from_rows(raw, first_line=2)

    @classmethod
    def read(cls, text: str, fmt: str | None = None) -> "Dataset":
        """``fmt``: ``jsonl``, ``csv`` or None to guess (a first character ``{`` means JSON lines)."""
        s = text.lstrip()
        fmt = fmt or ("jsonl" if s.startswith("{") else "csv")
        if fmt == "jsonl":
            return cls.from_jsonl(text)
        if fmt == "csv":
            return cls.from_csv(text)
        raise DatasetError(f"Unknown format {fmt!r}; use jsonl or csv")

    # ---- output
    def to_jsonl(self) -> str:
        return "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in self.rows)

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for r in self.rows:
            h.update(json.dumps(r, sort_keys=True, separators=(",", ":")).encode())
            h.update(b"\n")
        return h.hexdigest()[:20]

    def dedup(self) -> tuple["Dataset", int]:
        """Without exact duplicates (same patient, decision point, time and choice); the count removed."""
        seen, out = set(), []
        for r in self.rows:
            k = (r["patient_id"], r["decision_point"], r["t_days"], r["chosen"])
            if k not in seen:
                seen.add(k)
                out.append(r)
        return Dataset(out, self.read_problems, self.ignored, self.n_input), len(self.rows) - len(out)


def _try_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v         # normalise_row reports it


# --------------------------------------------------------------------------------- context cells
def field_value(row: dict, f: str):
    """Value of a context field of a row: ``group``, ``fast_track``, ``attributes.<name>`` or ``history.<step>``
    (the latest result of the step: True, False, or None when not done or inconclusive)."""
    c = row["context"]
    if f in ("group", "fast_track"):
        return c.get(f)
    head, _, rest = f.partition(".")
    if head == "attributes":
        return (c.get("attributes") or {}).get(rest)
    if head == "history":
        res = None
        for h in c.get("history") or []:
            if h.get("step") == rest:
                res = h.get("result")
        return res
    raise ValueError(f"unknown context field {f!r}; use group, fast_track, attributes.<name> or history.<step>")


def revealed_attributes(sc) -> dict[str, set[str]]:
    """attribute -> tests that reveal it (from the world's ``reveals`` lists)."""
    out: dict[str, set[str]] = defaultdict(set)
    for tid, spec in (sc.tests or {}).items():
        for a in spec.get("reveals") or []:
            out[a].add(tid)
    return out


def default_context_fields(rows: list[dict], sc=None) -> list[str]:
    """What the frequency trainer cells on by default: the group, and revealed categorical attributes.

    With a world: attributes some test reveals. Without: attributes seen in the data. Either way only
    small categoricals (at most 8 values) that actually vary in the data are kept."""
    fields = []
    groups = {r["context"].get("group") for r in rows} - {None}
    if len(groups) > 1:
        fields.append("group")
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        for k, v in (r["context"].get("attributes") or {}).items():
            seen[k].add(v)
    allowed = set(revealed_attributes(sc)) if sc is not None else set(seen)
    for a in sorted(seen):
        vals = seen[a] - {None}
        if a in allowed and 1 < len(vals) <= MAX_ATTR_VALUES:
            fields.append(f"attributes.{a}")
    return fields


def point_fields(rows: list[dict], fields: list[str]) -> list[str]:
    """The fields that vary among a decision point's rows: a field that is constant there (or not revealed yet)
    cannot split anything and is left out of its cells."""
    return [f for f in fields if len({_hk(field_value(r, f)) for r in rows}) > 1]


def _hk(v):
    return v


def cell_key(row: dict, fields: list[str]) -> tuple:
    return tuple(field_value(row, f) for f in fields)


# --------------------------------------------------------------------------------- split
def in_holdout(patient_id: str, fraction: float = 0.2, seed: int = 0) -> bool:
    """Deterministic patient-level split: all rows of one patient go the same way."""
    h = hashlib.sha256(f"{seed}:{patient_id}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 2 ** 32 < fraction


def split_by_patient(rows: list[dict], fraction: float = 0.2, seed: int = 0) -> tuple[list[dict], list[dict]]:
    train, hold = [], []
    for r in rows:
        (hold if in_holdout(r["patient_id"], fraction, seed) else train).append(r)
    return train, hold


# --------------------------------------------------------------------------------- validation
def _decision_points(fc) -> dict[str, list[str]]:
    return {nid: list(n.options) for nid, n in fc.nodes.items() if n.kind == "choice"}


def validate(ds: Dataset, sc=None, fc=None, context_fields: list[str] | None = None, min_cell: int = MIN_CELL) -> dict:
    """The validation report (spec 06). ``sc``/``fc`` are the world and flowchart to check against; without
    them only the structure is checked. ``trainable`` is False when any problem is an error."""
    P = Problems()
    P.extend(ds.read_problems)
    rows = ds.rows
    points = _decision_points(fc) if fc is not None else None
    steps = {nid: n for nid, n in fc.nodes.items() if n.kind != "choice"} if fc is not None else {}
    known_attrs = set(sc.attributes) if sc is not None else None
    known_groups = {g["id"] for g in sc.groups} if sc is not None else None
    revealers = revealed_attributes(sc) if sc is not None else {}
    attr_values = {a: set((spec.get("values") or {}).keys()) for a, spec in (sc.attributes or {}).items()} if sc is not None else {}
    unknown = {"attributes": Counter(), "steps": Counter(), "groups": Counter(), "attribute_values": Counter()}

    if ds.ignored:
        extras = {k: n for k, n in ds.ignored.items() if k not in KNOWN_EXTRAS}
        if extras:
            P.warn("ignored_fields", f"Fields the format does not know are ignored: {sorted(extras)}")

    by_point: dict[str, list[dict]] = defaultdict(list)
    rownum = {id(r): i for i, r in enumerate(rows, 1)}
    for r in rows:
        by_point[r["decision_point"]].append(r)
        i, pt = rownum[id(r)], r["decision_point"]
        if len(set(r["offered"])) != len(r["offered"]):
            P.error("duplicate_offered", "An option is offered twice in one row", pt, i)
        if r["chosen"] not in r["offered"]:
            P.error("chosen_not_offered", f"The chosen option is not among the offered ones", pt, i)
        t = r["t_days"]
        later = [h for h in r["context"]["history"] if t is not None and h.get("t_days") is not None and h["t_days"] > t + 0.01]
        if later:
            P.error("history_after_decision", "The history holds results that arrived after the decision: that would leak the future "
                    f"({sorted({h['step'] for h in later})})", pt, i)
        if points is not None:
            if pt not in points:
                P.error("unknown_decision_point", f"'{pt}' is not a node of this flowchart" if pt not in fc.nodes
                        else f"'{pt}' is not a decision point (it is a step)", pt, i)
            else:
                bad = sorted({o for o in r["offered"] + [r["chosen"]] if o not in points[pt]})
                if bad:
                    P.error("unknown_option", f"Options {bad} are not options of '{pt}' in this flowchart (it has {points[pt]})", pt, i)
        c = r["context"]
        if known_groups is not None and c.get("group") is not None and c["group"] not in known_groups:
            unknown["groups"][c["group"]] += 1
        done_tests = {h.get("test") or (steps[h["step"]].test if h["step"] in steps else None) for h in c["history"]}
        for h in c["history"]:
            if steps and h["step"] not in steps:
                unknown["steps"][h["step"]] += 1
        for a, v in c["attributes"].items():
            if known_attrs is not None and a not in known_attrs:
                unknown["attributes"][a] += 1
                continue
            if a in revealers and not (revealers[a] & done_tests):
                P.error("unrevealed_attribute", f"Attribute '{a}' is in the context but no earlier step that reveals it "
                        f"({sorted(revealers[a])}) is in the history. A model trained on it would see something the clinic did not yet know", pt, i)
            elif a not in revealers and known_attrs is not None:
                P.warn("attribute_not_revealed_by_flowchart", f"Attribute '{a}' is not revealed by any test of this world; it comes from outside the "
                       "flowchart, make sure it was known at the decision", pt, i)
            if a in attr_values and attr_values[a] and v is not None and str(v) not in attr_values[a]:
                unknown["attribute_values"][f"{a}={v}"] += 1

    for kind, label in (("attributes", "Context attributes"), ("steps", "History steps"), ("groups", "Groups")):
        if unknown[kind]:
            P.warn(f"unknown_{kind[:-1] if kind != 'attributes' else 'attribute'}",
                   f"{label} not in this flowchart's world: {sorted(unknown[kind])}. They are listed, not fatal; the trainers ignore context they cannot match")
    if unknown["attribute_values"]:
        P.warn("unknown_attribute_value", f"Attribute values the world does not list: {sorted(unknown['attribute_values'])}")

    fields = context_fields if context_fields is not None else default_context_fields(rows, sc)
    out_points: dict[str, dict] = {}
    for pt in sorted(by_point):
        rs = by_point[pt]
        opts = points[pt] if points is not None and pt in points else sorted({o for r in rs for o in r["offered"]})
        chosen = Counter(r["chosen"] for r in rs)
        offered = Counter(o for r in rs for o in r["offered"])
        eff = point_fields(rs, fields)
        shares = {}
        for f in ["group", "fast_track"] + [x for x in fields if x.startswith("attributes.")]:
            cnt = Counter(str(field_value(r, f)) for r in rs)
            if f == "group" or f in fields or len(cnt) > 1:
                shares[f] = {k: round(v / len(rs), 4) for k, v in sorted(cnt.items())}
        cells = Counter(cell_key(r, eff) for r in rs)
        small = [(k, n) for k, n in cells.items() if n < min_cell]
        out_points[pt] = {
            "rows": len(rs),
            "options": {o: {"chosen": chosen.get(o, 0), "share": round(chosen.get(o, 0) / len(rs), 4), "offered": offered.get(o, 0)} for o in opts},
            "context_shares": shares, "cell_fields": eff, "cells": len(cells), "cells_below_min": len(small),
            "rows_in_small_cells": sum(n for _, n in small),
        }
        for o in opts:
            if chosen.get(o, 0) == 0 and (points is None or pt in points):
                P.warn("option_never_chosen", f"Option '{o}' was never chosen at '{pt}'; a trained model will give it almost no probability", pt)
        if small and eff:
            P.warn("small_cell", f"{len(small)} of {len(cells)} cells at '{pt}' ({', '.join(eff)}) have fewer than {min_cell} rows; "
                   "the frequency trainer does not give them their own probabilities", pt)
        if len(opts) > 6:
            P.warn("many_options", f"'{pt}' has {len(opts)} options; the local trainer handles at most 6 and skips it", pt)
    if points is not None:
        for pt in points:
            if pt not in by_point:
                P.warn("no_rows_for_point", f"No rows for decision point '{pt}'; it keeps whatever probabilities the flowchart has", pt)
    if not rows:
        P.error("no_rows", "The dataset has no usable rows")

    dups = len(rows) - len({(r["patient_id"], r["decision_point"], r["t_days"], r["chosen"]) for r in rows})
    if dups:
        P.warn("duplicate_rows", f"{dups} rows repeat another row (same patient, decision point, time and choice); training drops them")
    ts = [r["t_days"] for r in rows if r["t_days"] is not None]
    dates = sorted(r["date"] for r in rows if "date" in r)
    patients = {r["patient_id"] for r in rows}
    problems = P.to_list()
    n_err = sum(g["count"] for g in problems if g["severity"] == "error")
    n_warn = sum(g["count"] for g in problems if g["severity"] == "warning")
    return {
        "schema": SCHEMA_VERSION, "rows": len(rows), "rows_read": ds.n_input, "patients": len(patients), "duplicates": dups,
        "t_days": {"min": min(ts), "max": max(ts)} if ts else None,
        "dates": {"min": dates[0], "max": dates[-1]} if dates else None,
        "decision_points": out_points, "context_fields": fields, "min_cell": min_cell,
        "unknown": {k: dict(v) for k, v in unknown.items() if v},
        "ignored_fields": {k: n for k, n in ds.ignored.items() if k not in KNOWN_EXTRAS},
        "checked_against": None if fc is None else {"flowchart": fc.id, "decision_points": sorted(points)},
        "problems": problems, "n_errors": n_err, "n_warnings": n_warn,
        "trainable": n_err == 0 and bool(rows),
    }


# --------------------------------------------------------------------------------- rows from a run log (M6-2)
def rows_from_patient(sc, fc, pr, seed: int | None = None, warmup: float = 0.0) -> Iterable[dict]:
    """The decisions one simulated patient met, as dataset rows: the request that was made plus the answer.

    The context holds only what had been revealed by the decision time: results that had arrived by then,
    and the attributes those tests reveal. The patient's hidden condition is never read.
    ``patient_id`` is ``s<seed>:<id>`` when ``seed`` is given, so cohorts of different seeds do not collide
    in a patient-level split."""
    a = pr.patient.arrival
    events = sorted(pr.events, key=lambda e: e.t_result)
    for ch in pr.choices:
        t = ch["t"]
        hist, attrs, fast = [], {}, False
        for e in events:
            rel = e.t_result - a
            if rel > t + 1e-9:
                break
            hist.append({"step": e.node, "test": e.test, "result": e.result, "t_days": round(rel, 3)})
            for k in sc.tests.get(e.test, {}).get("reveals") or []:
                attrs[k] = pr.patient.attributes.get(k)
            if e.node in fc.nodes and fc.nodes[e.node].fast_track:
                fast = True
        pid = f"s{seed}:{pr.patient.id}" if seed is not None else str(pr.patient.id)
        yield {"decision_point": ch["node"], "patient_id": pid, "t_days": t,
               "context": {"group": pr.patient.group, "age": pr.patient.age, "t_days": t, "fast_track": fast,
                           "attributes": attrs, "history": hist},
               "offered": list(ch["offered"]), "chosen": ch["chosen"], "measured": a >= warmup}


def rows_from_log(sc, fc, log, seed: int | None = None) -> list[dict]:
    """All decision rows of an engine run log (``simulate`` result), canonical and ready for :meth:`Dataset.from_rows`."""
    seed = log.seed if seed is None and hasattr(log, "seed") else seed
    out = []
    for pr in log.patients:
        out.extend(rows_from_patient(sc, fc, pr, seed, getattr(log, "warmup_days", 0.0)))
    return out


def dataset_from_log(sc, fc, log, seed: int | None = None) -> Dataset:
    return Dataset.from_rows(rows_from_log(sc, fc, log, seed))


def rows_from_run_export(lines: Iterable[str | bytes | dict], measured_only: bool = False) -> Dataset:
    """A run's stored decisions export (``GET /runs/{r}/decisions``) as a dataset. Fields of the export that
    are not part of the row (the generating policy's ``probs``) are dropped: a trainer must learn from what was
    chosen, not from the probabilities the chooser used."""
    raw = []
    for line in lines:
        d = json.loads(line) if isinstance(line, (str, bytes)) else line
        if measured_only and not d.get("measured", True):
            continue
        raw.append(d)
    return Dataset.from_rows(raw)

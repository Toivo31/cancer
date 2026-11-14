"""Flowchart edit operators.

Three kinds of change, each expressed in plain language for the demo:

* ``detach(X, A)``: step X no longer waits for A. A still runs, and treatment still waits for
  A (it is added to every treatment exit's optional prerequisites), so no information is lost
  before treatment; it is just gathered in parallel.
* ``relax(X, A)``: step X is ordered when A is *ordered* rather than when A is finished, i.e. X
  inherits A's own prerequisites (moves one step earlier).
* ``standardise(C, o)``: at choice C always pick option o (replaces practice variation by a
  standard; the plan's "a shared flowchart standardises care").
* ``fast_track(X)``: patients who complete X get priority in every capacity queue afterwards.

Validity rules (an edit that breaks one is not proposed):
* the flowchart must still validate (no cycles, references exist);
* every name a guard or policy rule reads must still be revealed *before* that step
  (a result of an ancestor step, or an attribute revealed by an ancestor's test): the optimiser
  cannot schedule a decision before the information it needs;
* protected edges (scenario ``optimiser.protected``) are never removed;
* a step keeps at least one required prerequisite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pathway_sim.expr import parse as parse_expr
from pathway_sim.scenario import Flowchart, Scenario, validate_flowchart

SAFE_NAMES = {"group", "age", "t", "True", "False", "None"}


@dataclass
class Edit:
    kind: str
    target: str
    other: str | None = None
    plain: str = ""
    score: float = 0.0
    evidence: dict = field(default_factory=dict)

    def key(self) -> tuple:
        return (self.kind, self.target, self.other)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "target": self.target, "other": self.other, "plain": self.plain,
                "score": round(self.score, 3), "evidence": self.evidence}


def label(fc: Flowchart, nid: str) -> str:
    n = fc.nodes[nid]
    return n.label or nid.replace("_", " ")


def ancestors(fc: Flowchart, nid: str) -> set[str]:
    option_of = {o: n.id for n in fc.nodes.values() if n.kind == "choice" for o in n.options}
    out, stack = set(), [nid]
    while stack:
        x = stack.pop()
        n = fc.nodes[x]
        deps = list(n.after) + list(n.after_any) + list(n.after_optional)
        if x in option_of:
            deps.append(option_of[x])
        for d in deps:
            if d not in out:
                out.add(d)
                stack.append(d)
    return out


def names_needed(fc: Flowchart, nid: str) -> set[str]:
    n = fc.nodes[nid]
    exprs = [n.when] if n.when else []
    for r in (fc.policy.get(nid) or {}).get("rules", []) or []:
        exprs.append(r["when"])
    names = set()
    for e in exprs:
        names |= set(parse_expr(e).names)
    return names - SAFE_NAMES


def information_ok(sc: Scenario, fc: Flowchart, nid: str) -> bool:
    anc = ancestors(fc, nid)
    revealed = set()
    for a in anc:
        t = fc.nodes[a].test
        if t:
            revealed |= set(sc.tests[t].get("reveals") or [])
    for name in names_needed(fc, nid):
        if name in fc.nodes:
            if name not in anc:
                return False
        elif name not in revealed:
            return False
    return True


def needs_ok(sc: Scenario, fc: Flowchart) -> bool:
    """Scenario ``optimiser.needs: {test_id: [test ids whose results it needs]}``: every node using
    a needed test must stay an ancestor of every node using the needing test (e.g. the tumour
    board needs PET-CT staging)."""
    needs = (sc.raw.get("optimiser") or {}).get("needs") or {}
    by_test: dict[str, list[str]] = {}
    for n in fc.nodes.values():
        if n.test:
            by_test.setdefault(n.test, []).append(n.id)
    for t, needed in needs.items():
        for x in by_test.get(t, []):
            anc = ancestors(fc, x)
            for nt in needed:
                for y in by_test.get(nt, []):
                    if y not in anc:
                        return False
    return True


def is_join(fc: Flowchart, nid: str) -> bool:
    n = fc.nodes[nid]
    return n.kind in ("step", "milestone") and not n.test and not n.after_any


def _protected(sc: Scenario) -> set[tuple[str, str]]:
    cfg = sc.raw.get("optimiser") or {}
    return {tuple(p) for p in cfg.get("protected", [])}


def _frozen(sc: Scenario) -> set[str]:
    return set((sc.raw.get("optimiser") or {}).get("frozen", []))


def _treatment_exits(fc: Flowchart) -> list[str]:
    return [n.id for n in fc.nodes.values() if n.kind == "exit" and n.outcome == "treatment"]


def apply(sc: Scenario, fc: Flowchart, e: Edit) -> Flowchart | None:
    """Return the edited copy, or None if the edit is invalid."""
    new = fc.copy(fc.id)
    nodes = new.nodes
    if e.kind == "detach" and e.other and "/" in e.other:
        # detach X from B, one branch of join prerequisite A: X waits for A's other inputs directly
        x = nodes[e.target]
        j, b = e.other.split("/")
        jn = nodes[j]
        req = j in x.after
        if req:
            x.after = [p for p in x.after if p != j]
        elif j in x.after_optional:
            x.after_optional = [p for p in x.after_optional if p != j]
        else:
            return None
        for p in jn.after:
            if p != b and p not in x.after and p != x.id:
                (x.after if req else x.after_optional).append(p)
        for p in jn.after_optional:
            if p != b and p not in x.after_optional and p not in x.after and p != x.id:
                x.after_optional.append(p)
        if not x.after and not x.after_any:
            return None
        for ex in _treatment_exits(new):
            if j not in ancestors(new, ex) and ex not in ancestors(new, j):
                nodes[ex].after_optional.append(j)
    elif e.kind in ("detach", "relax"):
        x, a = nodes[e.target], e.other
        if a in x.after:
            x.after = [p for p in x.after if p != a]
            required = True
        elif a in x.after_optional:
            x.after_optional = [p for p in x.after_optional if p != a]
            required = False
        else:
            return None
        if e.kind == "relax":
            an = nodes[a]
            if an.after_any or a in {o for n in nodes.values() if n.kind == "choice" for o in n.options}:
                return None
            for p in an.after:
                if p not in x.after and p != x.id:
                    (x.after if required else x.after_optional).append(p)
            for p in an.after_optional:
                if p not in x.after_optional and p not in x.after and p != x.id:
                    x.after_optional.append(p)
        if not x.after and not x.after_any:
            return None
        # treatment still waits for A if A no longer precedes it
        for ex in _treatment_exits(new):
            if ex != a and a not in ancestors(new, ex) and ex not in ancestors(new, a):
                nodes[ex].after_optional.append(a)
    elif e.kind == "standardise":
        new.policy[e.target] = {"prefer": [e.other], "note": "standardised by optimiser"}
    elif e.kind == "fast_track":
        if nodes[e.target].fast_track:
            return None
        nodes[e.target].fast_track = True
    else:
        raise ValueError(e.kind)
    try:
        validate_flowchart(sc, new)
    except ValueError:
        return None
    for nid in nodes:
        if not information_ok(sc, new, nid):
            return None
    if not needs_ok(sc, new):
        return None
    return new


def candidates(sc: Scenario, fc: Flowchart, allow: set[str] | None = None) -> list[Edit]:
    """All syntactically possible edits (validity is checked when applied)."""
    allow = allow or {"detach", "relax", "standardise", "fast_track"}
    prot, frozen = _protected(sc), _frozen(sc)
    out: list[Edit] = []
    for x in fc.nodes.values():
        if x.id in frozen:
            continue
        for a in list(x.after) + list(x.after_optional):
            if (x.id, a) in prot:
                continue
            if "detach" in allow:
                out.append(Edit("detach", x.id, a,
                                f"{label(fc, x.id)}: don't wait for {label(fc, a).lower()} (it runs in parallel; treatment still waits for it)"))
            if "detach" in allow and is_join(fc, a):
                for b in list(fc.nodes[a].after) + list(fc.nodes[a].after_optional):
                    if (x.id, b) not in prot:
                        out.append(Edit("detach", x.id, f"{a}/{b}",
                                        f"{label(fc, x.id)}: don't wait for {label(fc, b).lower()} (it runs in parallel; treatment still waits for it)"))
            if "relax" in allow:
                out.append(Edit("relax", x.id, a,
                                f"{label(fc, x.id)}: order it at the same time as {label(fc, a).lower()}, not after"))
        if x.kind == "choice" and "standardise" in allow:
            pol = fc.policy.get(x.id) or {}
            current = pol.get("prefer", [None])[0] if "mix" not in pol and not pol.get("rules") else None
            for o in x.options:
                if o != current:
                    out.append(Edit("standardise", x.id, o, f"{label(fc, x.id)}: always {label(fc, o).lower()}"))
        if "fast_track" in allow and x.test and x.kind == "step" and not x.fast_track:
            out.append(Edit("fast_track", x.id, None, f"Fast track patients after {label(fc, x.id).lower()}"))
    return out

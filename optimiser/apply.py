"""Apply a chosen subset of an optimisation result to a flowchart (spec 05).

``search`` returns accepted changes in order. Two things make a subset non-trivial:

* **Linked changes**: when no single change helped, the search accepted a pair together (the
  lookahead). Each of the two records the other in ``evidence.accepted_together_with``. Accepting one
  without the other is refused with the dependency named, so a UI can keep the two switches linked.
* **Order**: a later change was found on top of the earlier ones. Applying a subset replays the
  chosen changes in their original order and re-validates each; one that no longer applies is refused.

Accepting every change gives exactly the flowchart ``search`` returned.
"""

from __future__ import annotations

from pathway_sim.scenario import Flowchart, Scenario

from .edits import Edit, apply


class ChangeError(Exception):
    """A subset cannot be applied. ``code``: ``unknown_change``, ``linked_change`` or ``not_applicable``."""

    def __init__(self, code: str, message: str, index: int | None = None, needs: list[int] | None = None):
        super().__init__(message)
        self.code, self.message, self.index, self.needs = code, message, index, needs or []

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.index is not None:
            d["change"] = self.index
        if self.needs:
            d["needs"] = self.needs
        return d


def linked_groups(steps: list[dict]) -> list[list[int]]:
    """Indices of changes that were accepted together, e.g. ``[[0], [1, 2], [3]]``."""
    by_plain: dict[str, list[int]] = {}
    for i, s in enumerate(steps):
        by_plain.setdefault(s.get("plain", ""), []).append(i)
    parent = list(range(len(steps)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, s in enumerate(steps):
        for p in (s.get("evidence") or {}).get("accepted_together_with") or []:
            for j in by_plain.get(p, []):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(steps)):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values())


def apply_changes(sc: Scenario, fc: Flowchart, steps: list[dict], accept: list[int] | None = None,
                  new_id: str | None = None) -> Flowchart:
    """New flowchart from ``fc`` with the accepted changes applied (all of them when ``accept`` is None)."""
    chosen = list(range(len(steps))) if accept is None else sorted(set(accept))
    for i in chosen:
        if not isinstance(i, int) or i < 0 or i >= len(steps):
            raise ChangeError("unknown_change", f"there is no change number {i}", index=i)
    for group in linked_groups(steps):
        hit = [i for i in group if i in chosen]
        if hit and len(hit) < len(group):
            missing = [i for i in group if i not in chosen]
            raise ChangeError("linked_change",
                              f"change {hit[0]} was only found to work together with change {missing[0]}; accept both or neither",
                              index=hit[0], needs=missing)
    cur = fc.copy(new_id or f"{fc.id}_optimised")
    for i in chosen:
        s = steps[i]
        new = apply(sc, cur, Edit(s["kind"], s["target"], s.get("other"), s.get("plain", "")))
        if new is None:
            raise ChangeError("not_applicable",
                              f"change {i} no longer applies to this flowchart (it was found on top of an earlier change that is not accepted)",
                              index=i, needs=[j for j in range(i) if j not in chosen])
        cur = new
    return cur

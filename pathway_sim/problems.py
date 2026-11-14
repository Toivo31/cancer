"""Validation problems: the codes, the severities and the problem object shape.

This module is the contract between the validator (``pathway_sim/validate.py``), the service
(``/validate`` endpoint, save checks) and the web editor (live problems list, click-to-select).
It has no dependencies, so any of them can import it.

A problem, as JSON (``Problem.to_dict()``)::

    {"severity": "error", "code": "guard_unknown_name",
     "message": "The condition reads 'cxrr', which is not a step or attribute",
     "flowchart": "baseline",                 # flowchart the problem is in (null for world problems)
     "node": "referral",                      # node to select in the editor (null if none)
     "edge": {"from": "cxr", "to": "referral", "type": "required"},   # edge to select (null if none)
     "field": "when",                         # which field of the node, see FIELD_* below (null if none)
     "hint": "Did you mean 'cxr'?"}           # optional suggestion

``validate()`` returns ``{"ok": bool, "problems": [...]}``; ``ok`` is false when any problem has
severity ``error`` (warnings never block a save or a run).

Click-to-fix rule for the editor: select ``edge`` if present, else select ``node``, else open the
world screen for ``field`` (a dotted path such as ``resources.ct_scanner.capacity_per_day``).
``field`` on a node problem names the property to focus in the node's side panel: ``when``,
``test``, ``kind``, ``outcome``, ``stage``, ``after``, ``after_any``, ``after_optional``,
``options``, ``availability``, ``retry.fallback``, ``policy``, ``policy.rules[i].when``,
``policy.rules[i].choose``, ``policy.mix.<option>``, ``policy.prefer``, ``policy.default``,
``test_overrides.<test>``, ``resource_overrides.<resource>``.

Edge types match docs/platform/specs/01-flowchart-model.md: ``required`` (engine ``after``), ``any``
(``after_any``), ``optional`` (``after_optional``), ``option`` (a decision's ``options``; ``from`` is
the decision, ``to`` the option). For an ``unknown_reference`` the missing node is still named in
``from``/``to`` so the editor can show which wire is dangling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

ERROR = "error"
WARNING = "warning"

EDGE_REQUIRED, EDGE_ANY, EDGE_OPTIONAL, EDGE_OPTION = "required", "any", "optional", "option"

# code -> (severity, one-line meaning). The order is the order shown in documentation.
CODES: dict[str, tuple[str, str]] = {
    # structure
    "duplicate_id": (ERROR, "Two nodes share an id."),
    "unknown_kind": (ERROR, "The node kind is not step, choice (decision), milestone or exit."),
    "unknown_reference": (ERROR, "An edge, retry fallback or option points to a node that does not exist."),
    "cycle": (ERROR, "Steps wait for each other in a loop; the flowchart must be acyclic."),
    "no_exit": (ERROR, "The flowchart has no exit node, so no patient can finish."),
    "invalid_outcome": (ERROR, "An exit node needs an outcome: treatment, discharged or diagnosis_only."),
    "unknown_stage": (ERROR, "The node's stage is not detection, referral, diagnosis or treatment_start."),
    # decisions
    "decision_needs_two_options": (ERROR, "A decision node needs at least two options."),
    "option_of_two_decisions": (ERROR, "A node is an option of two different decisions."),
    "availability_unknown_option": (ERROR, "Availability is set for something that is not an option of the decision."),
    "policy_not_decision": (ERROR, "Probabilities or rules are set for a node that is not a decision."),
    "policy_unknown_option": (ERROR, "A policy names an option the decision does not have."),
    # references into the world
    "unknown_test": (ERROR, "A step or a test override uses a test that is not in the world."),
    "unknown_resource": (ERROR, "A test or a resource override uses a resource that is not in the world."),
    # conditions
    "guard_syntax": (ERROR, "The condition cannot be read: bad syntax, or it uses something conditions do not allow."),
    "guard_unknown_name": (ERROR, "The condition reads a name that is not a step, a revealed attribute, group, age or t."),
    "information_not_available": (ERROR, "A condition reads a result that is not known at this point of the pathway."),
    # world and constraints
    "needs_violated": (ERROR, "The flowchart breaks a clinical dependency declared in the world (for example the tumour board needs PET-CT)."),
    "world_invalid": (ERROR, "A world table is inconsistent (prevalences, resource or test settings)."),
    # warnings
    "unreachable": (WARNING, "No patient can reach this node (its condition can never be true, or what it waits for is unreachable)."),
    "possible_dead_end": (WARNING, "A patient can finish every started step without reaching an exit; this shows up in a run as 'stuck'."),
    "missing_probabilities": (WARNING, "A decision has no probabilities or rules, so the first option is always taken."),
}

ERROR_CODES = tuple(c for c, (s, _) in CODES.items() if s == ERROR)
WARNING_CODES = tuple(c for c, (s, _) in CODES.items() if s == WARNING)


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    severity: str = ""            # defaults to CODES[code][0]
    flowchart: str | None = None
    node: str | None = None
    edge: dict | None = None      # {"from": id, "to": id, "type": EDGE_*}
    field: str | None = None
    hint: str | None = None

    def __post_init__(self) -> None:
        if self.code not in CODES:
            raise ValueError(f"unknown problem code {self.code!r}")
        if not self.severity:
            object.__setattr__(self, "severity", CODES[self.code][0])
        if self.severity not in (ERROR, WARNING):
            raise ValueError(f"unknown severity {self.severity!r}")

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message,
                "flowchart": self.flowchart, "node": self.node, "edge": self.edge,
                "field": self.field, "hint": self.hint}


def edge_ref(source: str, target: str, kind: str) -> dict:
    return {"from": source, "to": target, "type": kind}


def report(problems: Iterable[Problem]) -> dict:
    """The JSON the service returns: ``{"ok": bool, "problems": [..]}`` (errors first, then warnings)."""
    ps = list(problems)
    ps.sort(key=lambda p: 0 if p.severity == ERROR else 1)   # stable: keeps discovery order within a severity
    return {"ok": not any(p.severity == ERROR for p in ps), "problems": [p.to_dict() for p in ps]}

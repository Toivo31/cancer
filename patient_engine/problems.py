"""Problems found in a catalogue or a card: the codes, the severities and the object shape.

Same shape as ``pathway_sim/problems.py`` (severity, code, message, hint) so the service and the
web editor can show both lists the same way, plus ``path``: a dotted location in the catalogue
(``variables.crp_true.given.pneumonia.dist``) or in a card (``observations.all_active.chest_ct.0``),
and ``file``: the catalogue file the entry came from (``tests.yaml``), or null.

A problem as JSON (``Problem.to_dict()``)::

    {"severity": "error", "code": "unknown_source", "file": "tests.yaml",
     "path": "tests.chest_xray.outputs.abnormal.sensitivity",
     "message": "source 'BRADLY2021' is not in params/sources.yaml",
     "hint": "Did you mean 'BRADLEY2021'?"}

Errors block loading (``load_catalogue`` raises ``CatalogueError``); warnings never do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

ERROR = "error"
WARNING = "warning"

# code -> (severity, one-line meaning). Later packages (card validation, audit) add their codes here.
CODES: dict[str, tuple[str, str]] = {
    # files and structure
    "file_missing": (ERROR, "A required catalogue file is missing (catalogue.yaml, conditions.yaml, variables.yaml, tests.yaml)."),
    "yaml_error": (ERROR, "A catalogue file cannot be read as YAML."),
    "bad_format": (ERROR, "catalogue.yaml does not declare `format: catalogue/1`."),
    "missing_field": (ERROR, "A required field is missing."),
    "bad_type": (ERROR, "A field has the wrong type (for example text where a number or a list is expected)."),
    "bad_value": (ERROR, "A field has a value that is not one of the allowed ones."),
    "bad_id": (ERROR, "An id is not snake_case (lower-case letters, digits and _; starting with a letter)."),
    "duplicate_id": (ERROR, "Two entries share an id."),
    "ambiguous_name": (ERROR, "The same name is used for two things (a variable, an attribute, a background field or a test), so a reference to it is ambiguous."),
    "unknown_field": (WARNING, "A field the format does not define; it is ignored (typo?)."),
    # numbers
    "missing_source": (ERROR, "A number has no source: every reference number is an object with `source` (an id in params/sources.yaml or `assumption`)."),
    "unknown_source": (ERROR, "A source id is not in params/sources.yaml."),
    "bad_grade": (ERROR, "A grade is not A, B, C, assumption or llm_draft."),
    "probability_out_of_range": (ERROR, "A probability is outside 0..1."),
    "negative_value": (ERROR, "A quantity that cannot be negative (a time, a cost, a standard deviation) is negative."),
    "bad_distribution": (ERROR, "A distribution is malformed (unknown `dist`, missing or inconsistent parameters)."),
    "bad_range": (ERROR, "`low` is above `high`, or the value lies outside them."),
    "values_do_not_sum_to_one": (ERROR, "The shares of a categorical distribution do not add up to 1."),
    "prevalence_sum": (WARNING, "Condition prevalences do not add up to 1 (they are shares of presenters)."),
    # references
    "unknown_condition": (ERROR, "A condition id that is not in conditions.yaml (in `given`, `by`, or co-occurrence)."),
    "unknown_variable": (ERROR, "A variable id that is not in variables.yaml (a test output measures it, or a `by` or `only_if` reads it)."),
    "unknown_reference": (ERROR, "A `by:` key is not a condition attribute, a variable, a background field or `condition`."),
    "unknown_level": (ERROR, "A `by:` level is not one of the values of what it reads."),
    "bad_band": (ERROR, "A numeric `by:` level is not a band like `..20`, `20..40` or `40..`, or two bands overlap."),
    "missing_given": (ERROR, "A variable says nothing for a condition and has no `default`."),
    "type_mismatch": (ERROR, "A test output's type does not match the type of the variable it measures."),
    "unknown_test": (ERROR, "A test id that is not in tests.yaml (in `requires`)."),
    "bad_expression": (ERROR, "An expression (`positive_when`, `only_if`) cannot be read, or reads an unknown name."),
    "by_cycle": (ERROR, "Dependencies (`by:` and `only_if`) form a loop; they must be acyclic."),
    "bad_cooccurrence": (ERROR, "A co-occurrence pair is not a primary condition with an `other_illness`, or a primary's shares exceed 1."),
    "no_positive_when": (WARNING, "A test has no `positive_when`, so the adapter to today's simulator cannot give it a yes/no result."),
    # cards (schema check; semantic checks belong to the card validator)
    "card_schema": (ERROR, "A card does not match the JSON Schema generated from its catalogue."),
}


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    path: str | None = None
    file: str | None = None
    hint: str | None = None
    severity: str = ""            # defaults to CODES[code][0]

    def __post_init__(self) -> None:
        if self.code not in CODES:
            raise ValueError(f"unknown problem code {self.code!r}")
        if not self.severity:
            object.__setattr__(self, "severity", CODES[self.code][0])
        if self.severity not in (ERROR, WARNING):
            raise ValueError(f"unknown severity {self.severity!r}")

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "file": self.file, "path": self.path,
                "message": self.message, "hint": self.hint}

    def __str__(self) -> str:
        where = ":".join(x for x in (self.file, self.path) if x)
        return f"{self.severity} {self.code}" + (f" at {where}" if where else "") + f": {self.message}" + \
            (f" ({self.hint})" if self.hint else "")


def errors(problems: Iterable[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == ERROR]


def report(problems: Iterable[Problem]) -> dict:
    """``{"ok": bool, "problems": [...]}``, errors first, discovery order kept within a severity."""
    ps = sorted(problems, key=lambda p: 0 if p.severity == ERROR else 1)
    return {"ok": not any(p.severity == ERROR for p in ps), "problems": [p.to_dict() for p in ps]}

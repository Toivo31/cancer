"""Technique classifier: names the manipulation technique or reasoning shortcut in a text
and explains it in plain language. See docs/technique_classifier.md."""

from .schema import (
    Coordination,
    Evidence,
    Flag,
    Span,
    Verdict,
    VERDICT_JSON_SCHEMA,
    load_taxonomy,
    technique_ids,
    validate_verdict,
)

__all__ = [
    "Coordination",
    "Evidence",
    "Flag",
    "Span",
    "Verdict",
    "VERDICT_JSON_SCHEMA",
    "load_taxonomy",
    "technique_ids",
    "validate_verdict",
]

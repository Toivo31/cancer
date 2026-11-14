"""Pathway optimiser: proposes flowchart changes from revealed information, accepts them only if a
full rerun of the same patients is faster within guardrails, and reports on held-out patients.

    python -m optimiser scenarios/generated/stokstad_calibrated.yaml --start observed

See search.py for the loop and the honesty note, edits.py for the change operators,
analysis.py for the revealed-information scores.
"""

from .edits import Edit, apply, candidates
from .search import Config, objective, search

__all__ = ["Config", "Edit", "apply", "candidates", "objective", "search"]

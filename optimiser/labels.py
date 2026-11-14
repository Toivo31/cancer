"""Plain-language wording for optimiser changes (used by the dashboard export and the service API).

``polish_change(fc, kind, target, other)`` gives the sentence a clinician reads; the optimiser's raw
text stays available as ``Edit.plain``.
"""

from __future__ import annotations

from pathway_sim.scenario import Flowchart


def _clean(label: str) -> str:
    return label.split(" (")[0].strip()


# Hand-written wording for the changes the search is known to find; anything else falls back to a
# generator built from the edit kind and the step labels. The raw optimiser text is kept as "raw".
POLISHED = {
    ("relax", "book_treat", "mdt"): "Reserve the treatment slot when the case is sent to the tumour board, not after the board has met",
    ("relax", "spec_visit", "triage"): "Book the specialist visit as soon as the referral arrives, not after it has been handled",
    ("standardise", "first_contact", "gp_visit"): "Book a GP appointment, not a nurse, at first contact",
    ("standardise", "first_contact", "nurse_visit"): "Book a nurse appointment, not a GP, at first contact",
    ("fast_track", "triage", None): "Fast lane: once the hospital has handled a referral, give that patient priority in every later queue",
    ("detach", "diagnosis", "sampling_done"): "Hold the tumour board without waiting for tissue sampling to finish; sampling runs alongside while treatment is booked",
    ("standardise", "pet_timing", "pet_on_time"): "Always order the PET-CT scan at triage or the first visit, never late",
    ("standardise", "ex_timing", "ex_early"): "Always order the exercise test early, together with the other tests",
    # relax(sample_plan, visit): sample_plan inherits the visit's prerequisite (the baseline CT at referral
    # receipt), so sampling is planned when the referral is triaged, BEFORE the first visit (D18).
    ("relax", "sample_plan", "visit"): "Plan tissue sampling when the referral is triaged, before the first hospital visit",
}


def _lab(fc: Flowchart, nid: str) -> str:
    n = fc.nodes[nid]
    return _clean(n.label or nid.replace("_", " "))


def polish_change(fc: Flowchart, kind: str, target: str, other: str | None) -> str:
    if (kind, target, other) in POLISHED:
        return POLISHED[(kind, target, other)]
    if kind == "fast_track":
        return f"Fast lane: patients who have completed {_lab(fc, target).lower()} get priority in every later queue"
    if kind == "standardise":
        return f"At \u201c{_lab(fc, target)}\u201d always choose \u201c{_lab(fc, other).lower()}\u201d"
    a = _lab(fc, other.split("/")[-1] if other else target).lower() if other else ""
    x = _lab(fc, target)
    if kind == "detach":
        return f"{x}: no longer waits for {a}; it runs alongside and treatment still waits for it"
    if kind == "relax":
        return f"Order {x.lower()} at the same time as {a}, not after it"
    return kind

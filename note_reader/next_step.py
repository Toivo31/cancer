"""Next-step estimates shown next to the flagged note.

Transparent decision support, not a trained model: the flags decide which questions are
shown, and every percentage carries its source. Numbers (keep in sync with video/dots/zoom.js):

- Chest X-ray finds 77-80% of lung cancers in symptomatic patients (best-quality studies; 76.8% in
  primary care): Bradley et al., Br J Gen Pract 2019;69:e827, doi:10.3399/bjgp19X706853.
- Diagnostic CT finds 97%: simulator assumption (sensitivity about 0.95 noted in params).
- Central tumour: bronchoscopy 94% diagnostic in about 14 days vs needle biopsy 68% in about
  22 days; peripheral: 97% / 22 days vs 92% / 21 days. Measured in our simulator on synthetic
  exploration runs (runs/model_in_loop.json on overnight/sim, finland_lung / sample_choice).
"""

from __future__ import annotations

import re

URGENT = {"red_flag_without_action", "diagnostic_overshadowing", "anchoring_premature_closure",
          "dismissive_no_safety_net"}

CHEST = re.compile(r"cough|chest|breath|dyspn|haemopt|hemopt|smok|lung|x-ray|xray", re.I)

NEXT_TEST = {
    "question": "Which test finds a lung cancer, if there is one?",
    "options": [
        {"label": "Chest X-ray (again)", "p": 0.77, "detail": "finds 77-80% of lung cancers",
         "source": "Bradley et al. 2019, systematic review"},
        {"label": "Direct CT", "p": 0.97, "detail": "finds 97%", "source": "simulator assumption"},
    ],
    "pick": "Direct CT",
}

BIOPSY = {
    "question": "If CT shows a central tumour: which biopsy?",
    "options": [
        {"label": "Bronchoscopy", "p": 0.94, "detail": "94% diagnosed, about 14 days",
         "source": "our simulator, 161 synthetic cases"},
        {"label": "Needle biopsy", "p": 0.68, "detail": "68% diagnosed, about 22 days",
         "source": "our simulator, 150 synthetic cases"},
    ],
    "pick": "Bronchoscopy",
}


def next_step(text: str, flags: list[dict]) -> dict:
    ids = {f["technique_id"] for f in flags}
    urgent = bool(ids & URGENT)
    chest = bool(CHEST.search(text))
    route = "Fast lane: urgent CT and referral" if urgent and chest else (
        "Second look: review the note with the patient" if ids else "No change suggested")
    panels = [NEXT_TEST, BIOPSY] if (urgent and chest) else []
    why = []
    if "red_flag_without_action" in ids:
        why.append("a warning sign is recorded without the expected test")
    if "diagnostic_overshadowing" in ids:
        why.append("the symptom is explained by something already known about the patient")
    if "anchoring_premature_closure" in ids:
        why.append("the same explanation is repeated across visits")
    if "dismissive_no_safety_net" in ids:
        why.append("reassurance without a follow-up plan")
    if "stigmatising_language" in ids:
        why.append("wording that can make the next reader take the complaint less seriously")
    return {"route": route, "urgent": urgent and chest, "why": why, "panels": panels,
            "note": "Decision support. A clinician confirms every step."}

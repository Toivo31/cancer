"""The team's decision model (Birch) at the choice nodes of a pathway flowchart (``pathway_sim.engine``).

:class:`jev.birch.BirchPolicy` renders an encounter record (``view.record``) as words. Flowchart runs (the
simulator page: Norway, Finland) have no record: the view carries age, revealed attributes and the steps done
so far. Without a record ``jev.birch.map_request`` falls back to a primary-care case text and drops the steps,
so the model would see "Patient in Finnish primary care" and an age, nothing else. This module puts the
flowchart's own visible information into ``context['record_text']`` (which ``map_request`` reads):

* the case: the setting, the referral reason, age, and the question asked at this node (its label);
* one evidence line per finished step, in time order (step label, day, result in words);
* one evidence line per revealed attribute (what the record shows by now).

Visible information only (invariant I1): the patient's condition, hidden attributes and future results are
never read; ``jev.birch.check_visible`` still checks every payload before it is sent. Nothing here sends
anything: the backend (``jev.birch.BirchBackend`` or the owner's ``decision_api.jev_bridge.backend()``) does.
"""

from __future__ import annotations

from .birch import BirchPolicy

#: setting and referral reason per scenario id (plain words, visible to a clinician at referral)
SETTINGS = {
    "stokstad": ("Synthetic patient on the lung cancer diagnostic pathway of one Norwegian university hospital "
                 "(pathway rebuilt from a published study).",
                 "Referred to the hospital after a chest CT raised the suspicion of lung cancer."),
    "finland_lung": ("Synthetic patient in a Finnish county's lung cancer pathway, from first contact in primary care "
                     "to hospital treatment.",
                     "Presented with chest symptoms."),
}
DEFAULT_SETTING = ("Synthetic patient on a hospital diagnostic pathway.", "")
RESULT_WORDS = {True: "done", False: "done, no finding", None: "inconclusive (no usable result)"}
#: revealed attributes in plain words (fallback: the id with spaces)
ATTRIBUTE_WORDS = {
    "location": "Tumour location on CT",
    "ct_inadequate": "First CT technically inadequate",
    "needs_exercise_test": "Exercise test needed before surgery can be decided",
    "further_workup_after_pet": "Further tests needed after PET-CT",
    "treatment": "Treatment planned by the tumour board",
}


def _words(s) -> str:
    return str(s).replace("_", " ")


class FlowBirchPolicy(BirchPolicy):
    """``BirchPolicy`` for flowchart choice nodes: the request carries the flowchart's visible state as words.

    ``scenario`` and ``flowchart`` are required (labels of steps, options and the question). The condition ids
    of the scenario are the forbidden values of the visibility check.
    """

    def __init__(self, backend, scenario, flowchart, mode: str = "argmax"):
        super().__init__(backend, mode=mode, scenario=scenario, flowchart=flowchart)
        self.scenario, self.flowchart = scenario, flowchart
        conds = {c["id"] for c in (scenario.raw.get("conditions") or []) if isinstance(c, dict) and c.get("id")}
        if not backend.forbidden_values:
            backend.forbidden_values = frozenset(conds)
        labels = {n.label for n in flowchart.nodes.values() if n.label}
        backend.public_phrases = frozenset(set(backend.public_phrases) | labels)

    def _label(self, nid: str) -> str:
        n = self.flowchart.nodes.get(nid)
        return (n.label if n is not None and n.label else _words(nid))

    def flow_text(self, view) -> dict:
        """``{"case": str, "lines": [{"step", "kind", "text"}]}`` from the view's visible state only."""
        setting, referral = SETTINGS.get(self.scenario.id, DEFAULT_SETTING)
        bits = [setting]
        if referral:
            bits.append(referral)
        if view.age is not None:
            bits.append(f"Age {view.age}.")
        if view.priority:
            bits.append("Fast-tracked.")
        bits.append(f"Day {view.t_now:.1f} of the pathway. Decision now: {self._label(view.node).rstrip('?.')}.")
        lines = []
        for nid, test, result, t in sorted(view.history, key=lambda h: h[3]):
            what = self._label(nid)
            lines.append({"kind": "step", "text": f"Day {float(t):.1f}: {what}: {RESULT_WORDS.get(result, _words(result))}."})
        for k, v in sorted(view.attributes.items()):
            lines.append({"kind": "finding", "text": f"{ATTRIBUTE_WORDS.get(k, _words(k).capitalize())}: {_words(v)}."})
        for i, x in enumerate(lines):
            x["step"] = i + 1
        return {"case": " ".join(bits), "lines": lines}

    def request_for(self, view, options):
        req = super().request_for(view, options)       # option labels and lead times from the flowchart
        req.context = {**req.context, "record_text": self.flow_text(view)}
        return req


__all__ = ["FlowBirchPolicy", "SETTINGS"]

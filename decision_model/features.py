"""Feature layout shared by the synthetic task, the RunLog adapter and ModelPolicy.

Context vector (revealed information only):
  [age/100, non_specific_group, days_elapsed/60, (pos, neg) for each test in CONTEXT_TESTS]
  A test that has not been done / is nondiagnostic has pos = neg = 0 ("unknown").
  optionally followed by a one-hot block over revealed attributes (AttrVocab): one column per
  (attribute, value) pair seen in training; an attribute that is not revealed, or a value never
  seen in training, is all zero ("unknown"). Without a vocab the vector is unchanged (N_CONTEXT).
Option vector (a candidate next test):
  [sensitivity, specificity, wait_days/30, invasive, cost_eur/1000]
  (in-loop runs pass their own per-option vectors, see decision_model/in_loop.py)
"""
from __future__ import annotations

import numpy as np

CONTEXT_TESTS = ["chest_xray", "ct_chest", "pet_ct", "bronchoscopy", "ebus", "ttnb"]
N_CONTEXT = 3 + 2 * len(CONTEXT_TESTS)
N_OPTION = 5
OPTION_FIELDS = ["sens", "spec", "wait_days", "invasive", "cost_eur"]
DEFAULT_AGE = 65  # used when a RunLog patient has no age (the contract RunLog omits it)

# ILLUSTRATIVE attributes for the lung tests, status: assumption (not sourced; the real
# numbers belong to params/ once that track lands). Pass your own table to override.
DEFAULT_TEST_TABLE = {
    "chest_xray": dict(sens=0.75, spec=0.90, wait_days=3, invasive=0, cost_eur=60),
    "ct_chest": dict(sens=0.95, spec=0.85, wait_days=10, invasive=0, cost_eur=250),
    "pet_ct": dict(sens=0.90, spec=0.85, wait_days=20, invasive=0, cost_eur=1500),
    "bronchoscopy": dict(sens=0.70, spec=0.99, wait_days=14, invasive=1, cost_eur=900),
    "ebus": dict(sens=0.90, spec=0.99, wait_days=18, invasive=1, cost_eur=1500),
    "ttnb": dict(sens=0.90, spec=0.98, wait_days=12, invasive=1, cost_eur=1100),
}


class AttrVocab:
    """One-hot layout for revealed attributes, built from training contexts only."""

    def __init__(self, pairs=()):
        self.pairs = sorted({(str(a), str(v)) for a, v in pairs})
        self.index = {p: i for i, p in enumerate(self.pairs)}

    @classmethod
    def from_attributes(cls, attr_dicts) -> "AttrVocab":
        return cls((a, v) for d in attr_dicts for a, v in (d or {}).items() if v is not None)

    def __len__(self):
        return len(self.pairs)

    def vector(self, attrs: dict | None) -> np.ndarray:
        v = np.zeros(len(self.pairs))
        for a, val in (attrs or {}).items():
            i = self.index.get((str(a), str(val)))
            if i is not None:
                v[i] = 1.0
        return v

    def to_list(self) -> list:
        return [list(p) for p in self.pairs]


def context_vector(age, non_specific, days_elapsed, status: dict[str, int | None],
                   attributes: dict | None = None, attr_vocab: AttrVocab | None = None) -> np.ndarray:
    """status: test id -> 1 (positive), 0 (negative), None/absent (unknown).
    attributes / attr_vocab: revealed attributes, appended as a one-hot block when a vocab is given."""
    v = np.zeros(N_CONTEXT)
    v[0] = (DEFAULT_AGE if age is None else age) / 100.0
    v[1] = float(non_specific)
    v[2] = min(max(days_elapsed, 0.0), 90.0) / 60.0
    for k, t in enumerate(CONTEXT_TESTS):
        s = status.get(t)
        if s is True or s == 1:
            v[3 + 2 * k] = 1.0
        elif s is False or s == 0:
            v[4 + 2 * k] = 1.0
    if attr_vocab is not None:
        v = np.concatenate([v, attr_vocab.vector(attributes)])
    return v


def option_vector(attrs: dict) -> np.ndarray:
    return np.array([attrs["sens"], attrs["spec"], attrs["wait_days"] / 30.0,
                     float(attrs["invasive"]), attrs["cost_eur"] / 1000.0])

# Common flowchart node ids -> test ids (architecture.md examples); override per scenario.
DEFAULT_NODE_TO_TEST = {"bronch": "bronchoscopy", "pet": "pet_ct", "cxr": "chest_xray", "ct": "ct_chest"}

"""Feature layout shared by the synthetic task, the RunLog adapter and ModelPolicy.

Context vector (revealed information only):
  [age/100, non_specific_group, days_elapsed/60, (pos, neg) for each test in CONTEXT_TESTS]
  A test that has not been done / is nondiagnostic has pos = neg = 0 ("unknown").
Option vector (a candidate next test):
  [sensitivity, specificity, wait_days/30, invasive, cost_eur/1000]
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


def context_vector(age, non_specific, days_elapsed, status: dict[str, int | None]) -> np.ndarray:
    """status: test id -> 1 (positive), 0 (negative), None/absent (unknown)."""
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
    return v


def option_vector(attrs: dict) -> np.ndarray:
    return np.array([attrs["sens"], attrs["spec"], attrs["wait_days"] / 30.0,
                     float(attrs["invasive"]), attrs["cost_eur"] / 1000.0])

# Common flowchart node ids -> test ids (architecture.md examples); override per scenario.
DEFAULT_NODE_TO_TEST = {"bronch": "bronchoscopy", "pet": "pet_ct", "cxr": "chest_xray", "ct": "ct_chest"}

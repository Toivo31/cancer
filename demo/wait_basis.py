"""Where the simulated waiting comes from: which part of it was set from a published figure and which part is our
own assumption or placeholder (dashboard screen 2 and the flow page's 'Where time is lost' card; review 14 Nov).

The share of time spent waiting is arithmetic on the simulation's output, but each step's wait is largely an input:
booking leads, capacities and assumed extra waits that we wrote into the scenario file. This module tags every
waiting day on the critical path of treated cancers with how its input was set, so the pages can say so.

The tags are this module's own mapping (BASIS below), written from the `source:` and `note:` fields of
scenarios/finland_lung.yaml and scenarios/generated/stokstad_calibrated.yaml, because those fields do not give a
clean per-step tag (for example `clinic` is `source: assumption` but its lead is calibrated to a published wait,
and `gp_represent` mixes a sourced booking lead with an assumed re-presentation interval). An assumed `extra_wait`
(a delay before the booking starts) is always counted as an assumption, separately from the step's booking wait.
Same cohorts and the same critical-path accounting as pathway_sim.metrics (stage_breakdown), so the totals match.
"""
from __future__ import annotations

from pathway_sim.dists import sample, uniform

PUB, ASM = "published", "assumption"

# test id -> (basis, short step label, where the input comes from)
BASIS = {
    "finland_lung": {
        "gp_assessment": (PUB, "GP appointment", "booking lead set so the first GP appointment takes about 14 d (KHALIFE2025, THL survey)"),
        "gp_assessment_after_nurse": (PUB, "GP appointment", "booking lead set so the first GP appointment takes about 14 d (KHALIFE2025, THL survey)"),
        "gp_represent": (PUB, "GP appointment", "booking lead set so the first GP appointment takes about 14 d (KHALIFE2025, THL survey)"),
        "referral_triage": (PUB, "referral handling", "handling 1-2 working days, invitation letter 3-4 (Pirkanmaa pathway, PIRHA_PATH)"),
        "specialist_visit": (PUB, "specialist visit", "lead and queue calibrated to 14-28 d from GP referral to specialist visit (KHALIFE2025)"),
        "treatment_booking": (PUB, "treatment booking", "lead calibrated to about 37 d from diagnosis to treatment (IHE2026); that figure covers ALL cancers, "
                                                     "not lung cancer: Finnish lung-specific figures are 65-69 d (docs/evidence_research.md)"),
        "nurse_assessment": (ASM, "nurse appointment", "assumed capacity and booking lead"),
        "chest_xray": (ASM, "chest X-ray", "assumed: direct-access X-ray within days"),
        "chest_ct": (ASM, "chest CT", "assumed capacity slice and lead"),
        "bronchoscopy": (ASM, "bronchoscopy", "placeholder capacity and assumed lead"),
        "ttnb": (ASM, "needle biopsy", "assumed slots and lead"),
        "pet_ct": (ASM, "PET-CT", "placeholder capacity; no Finnish PET-CT wait found"),
        "tumour_board": (ASM, "tumour board", "assumed weekly board (weekly is Norwegian practice)"),
        "gp_second_look": (ASM, "paperwork", "assumed"),
        "symptoms_persist": (ASM, "paperwork", "assumed"),
        "gp_referral_letter": (ASM, "paperwork", "assumed"),
    },
    "stokstad": {
        "first_visit": (PUB, "first hospital visit", "wait derived from the paper's counts (STOKSTAD2019)"),
        "bronchoscopy_repeat": (PUB, "repeat sampling", "median 8 d (STOKSTAD2019)"),
        "ttnb": (PUB, "needle biopsy", "repeat-sampling wait 8 d (STOKSTAD2019)"),
        "ct_redo": (PUB, "CT redo", "median extra delay 15.5 d (STOKSTAD2019)"),
        "pet_ct": (PUB, "PET-CT", "referral to report 20.5 d (STOKSTAD2019)"),
        "pet_ct_late": (PUB, "PET-CT, ordered late", "late referral costs 8 d (STOKSTAD2019)"),
        "exercise_test": (PUB, "exercise test", "median 11 d (STOKSTAD2019)"),
        "exercise_test_late": (PUB, "exercise test, ordered late", "late referral costs 10 d (STOKSTAD2019)"),
        "surgery_booking": (PUB, "surgery booking", "treatment referral to surgery 13 d (STOKSTAD2019, our reading of the start point)"),
        "radiotherapy_booking": (PUB, "radiotherapy booking", "treatment referral to radiotherapy 22.5 d (STOKSTAD2019)"),
        "bronchoscopy": (ASM, "bronchoscopy", "wait not reported in the paper; fitted"),
        "further_workup": (ASM, "further work-up", "duration not reported; assumed like a sampling procedure"),
        "tumour_board": (ASM, "tumour board", "weekly in the paper; weekday and cutoff fitted"),
    },
}
EXTRA = {  # assumed extra_wait, always an assumption
    "gp_represent": "re-presentation interval after reassurance (assumed, median 14 d)",
    "treatment_booking": "pre-treatment work-up before the slot (assumed)",
    "first_visit": "CT report not ready at the first visit (fitted)",
}
SENTENCE = ("This is a consequence of the waits we put in, not a measurement from patient data; it shows where the modelled "
            "time sits, and it is only as good as those inputs.")


def wait_basis(sc, runs) -> dict:
    """runs: the RunLogs of the baseline flowchart on the held-out cohorts (optimiser.search.evaluate)."""
    tags = BASIS.get(sc.id, {})
    per_run = []
    untagged = set()
    for run in runs:
        acc: dict[tuple, float] = {}
        tot_wait = tot_all = 0.0
        prs = [pr for pr in run.patients if pr.patient.arrival >= run.warmup_days and pr.patient.cancer and pr.t_treatment is not None]
        for pr in prs:
            for e in pr.events:
                if not e.critical:
                    continue
                w, s = e.t_start - e.t_ready, e.t_result - e.t_start
                tot_wait += w
                tot_all += w + s
                if w <= 0:
                    continue
                test = sc.tests.get(e.test, {})
                ex = 0.0
                if test.get("extra_wait") is not None:
                    ex = min(w, max(0.0, sample(test["extra_wait"], uniform(run.seed, pr.patient.id, "extra", e.test, e.attempt))))
                base_test = e.test[:-5] if e.test.endswith("_fast") and e.test not in tags else e.test
                basis, label, src = tags.get(base_test) or (ASM, e.test.replace("_", " "), "not tagged; counted as an assumption")
                if base_test not in tags:
                    untagged.add(e.test)
                if ex > 0:
                    k = (ASM, label + ": extra wait", EXTRA.get(base_test, "assumed extra wait"))
                    acc[k] = acc.get(k, 0.0) + ex
                k = (basis, label, src)
                acc[k] = acc.get(k, 0.0) + (w - ex)
        n = max(len(prs), 1)
        per_run.append(({k: v / n for k, v in acc.items()}, tot_wait / n, tot_all / n))
    keys = {k for a, _, _ in per_run for k in a}
    R = len(per_run)
    days = {k: sum(a.get(k, 0.0) for a, _, _ in per_run) / R for k in keys}
    wait = sum(x for _, x, _ in per_run) / R
    total = sum(x for _, _, x in per_run) / R
    groups = {}
    for b in (PUB, ASM):
        steps: dict[tuple, float] = {}
        for (bb, label, src), d in days.items():
            if bb == b:
                steps[(label, src)] = steps.get((label, src), 0.0) + d
        rows = sorted(({"step": l, "source": s, "days": round(d, 1)} for (l, s), d in steps.items() if d >= 0.05), key=lambda r: -r["days"])
        gd = sum(steps.values())
        groups[b] = {"days": round(gd, 1), "share_of_waiting": round(gd / wait, 4) if wait else None, "steps": rows}
    return {
        "waiting_days": round(wait, 1), "total_days": round(total, 1),
        "waiting_share": round(wait / total, 4) if total else None,
        "groups": groups,
        "untagged_tests": sorted(untagged),
        "statement": SENTENCE,
        "method": "Mean days per treated cancer on the critical path, held-out cohorts of the baseline flowchart. Tags: "
                  "demo/wait_basis.py (BASIS), written from the scenario file's source and note fields. A step tagged "
                  "'published' has its booking lead (and, where noted, its queue) set to match a published wait; the "
                  "capacity behind any queue is still our input.",
    }

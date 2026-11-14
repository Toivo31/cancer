"""Pathway simulator: synthetic patients through a configurable diagnostic flowchart.

Quick start::

    from pathway_sim import load_scenario, generate_patients, simulate, compute_metrics
    sc = load_scenario("scenarios/stokstad.yaml")
    pts = generate_patients(sc, 100, seed=1)
    run = simulate(sc, "observed", pts, seed=1)
    print(compute_metrics(run, sc)["share_within_target"])

CLI: ``python -m pathway_sim --help``. Contract: docs/architecture.md.
"""

from .dists import sample, uniform
from .engine import Event, PatientRun, RunLog, simulate
from .metrics import compute_metrics, queue_series, summary_line
from .patients import Patient, generate_patients
from .policy import PatientView, Policy, RandomPolicy, RulePolicy
from .scenario import Flowchart, Node, Scenario, load_scenario, parse_flowchart, scenario_from_dict

__all__ = [
    "Event", "Flowchart", "Node", "Patient", "PatientRun", "PatientView", "Policy", "RandomPolicy",
    "RulePolicy", "RunLog", "Scenario", "compute_metrics", "generate_patients", "load_scenario",
    "parse_flowchart", "queue_series", "sample", "scenario_from_dict", "simulate", "summary_line", "uniform",
]

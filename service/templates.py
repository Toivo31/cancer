"""Built-in worlds and flowcharts, converted from the shipped scenario YAML at first use (spec 03)."""

from __future__ import annotations

import copy
from pathlib import Path

from pathway_sim.documents import load_yaml_as_documents

# id, file, name, description. Order is display order.
SOURCES = [
    ("finland_lung", "finland_lung.yaml", "Finnish lung cancer pathway (synthetic)",
     "One Finnish wellbeing services county, from first contact in primary care to the start of treatment. "
     "All numbers are synthetic and each carries its source or is marked as an assumption."),
    ("norway_check", "stokstad.yaml", "Norway check (Stokstad 2019)",
     "The published Norwegian stage I-II lung cancer pathway, re-timed with published waits. Used to check the "
     "simulator against a known result."),
]


def load_templates(scenario_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for tid, filename, name, description in SOURCES:
        path = Path(scenario_dir) / filename
        if not path.exists():
            continue
        world, fcs = load_yaml_as_documents(path)
        world["name"] = name
        out[tid] = {"id": tid, "name": name, "description": description, "world": world, "flowcharts": fcs}
    return out


def template_copy(t: dict) -> tuple[dict, list[dict]]:
    return copy.deepcopy(t["world"]), copy.deepcopy(t["flowcharts"])

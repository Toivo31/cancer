"""Service configuration from the environment (spec 03 limits, spec 07 variables)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v else default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("PATHWAY_DATA_DIR") or REPO_ROOT / "data"))
    scenario_dir: Path = field(default_factory=lambda: Path(os.environ.get("PATHWAY_SCENARIO_DIR") or REPO_ROOT / "scenarios"))
    web_dir: Path = field(default_factory=lambda: Path(os.environ.get("PATHWAY_WEB_DIR") or REPO_ROOT / "web" / "dist"))
    max_patients: int = field(default_factory=lambda: _int("PATHWAY_MAX_PATIENTS", 50_000))
    max_seeds: int = field(default_factory=lambda: _int("PATHWAY_MAX_SEEDS", 5))
    max_jobs: int = field(default_factory=lambda: _int("PATHWAY_MAX_JOBS", os.cpu_count() or 2))
    job_seconds: int = field(default_factory=lambda: _int("PATHWAY_JOB_SECONDS", 900))
    max_document_bytes: int = field(default_factory=lambda: _int("PATHWAY_MAX_DOCUMENT_BYTES", 1_000_000))
    max_projects: int = field(default_factory=lambda: _int("PATHWAY_MAX_PROJECTS", 200))
    max_versions_per_flowchart: int = field(default_factory=lambda: _int("PATHWAY_MAX_VERSIONS", 500))

    def __post_init__(self):
        self.data_dir = Path(self.data_dir)
        self.scenario_dir = Path(self.scenario_dir)
        self.web_dir = Path(self.web_dir)

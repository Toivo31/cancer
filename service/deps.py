"""Shared wiring that every router imports: settings, store, templates, project lookup.

    from service.deps import get_store, get_settings
    @router.get("/projects/{p}/runs")
    def list_runs(p: str, store: Store = Depends(get_store)): ...
"""

from __future__ import annotations

import threading

from fastapi import Depends, Request

from .config import Settings
from .errors import not_found
from .store import NotFound, Store


class Services:
    """Per-app singletons, created lazily so importing ``service.app`` touches no files."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._store: Store | None = None
        self._templates = None
        self._lock = threading.Lock()

    @property
    def store(self) -> Store:
        with self._lock:
            if self._store is None:
                self._store = Store(self.settings.data_dir)
            return self._store

    @property
    def templates(self):
        with self._lock:
            if self._templates is None:
                from .templates import load_templates
                self._templates = load_templates(self.settings.scenario_dir)
            return self._templates


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_settings(services: Services = Depends(get_services)) -> Settings:
    return services.settings


def get_store(services: Services = Depends(get_services)) -> Store:
    return services.store


def get_templates(services: Services = Depends(get_services)):
    return services.templates


def get_project(p: str, store: Store = Depends(get_store)) -> dict:
    """Path dependency: the project row or a 404. Use as ``project: dict = Depends(get_project)``."""
    try:
        return store.get_project(p)
    except NotFound:
        raise not_found("project", p) from None

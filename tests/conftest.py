"""Options for the JEV contract tests (tests/test_jev_contract.py), and the fast/slow test tiers.

Slow tests are listed in tests/slow_tests.txt and get the ``slow`` marker here, so no lane's test file has
to change. ``python -m pytest -m "not slow"`` is the fast tier, ``-m slow`` the rest; scripts/gate.sh runs them."""

from pathlib import Path

import pytest

SLOW_LIST = Path(__file__).resolve().parent / "slow_tests.txt"


def _slow_entries(path: Path = SLOW_LIST) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.split(" #", 1)[0].strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def is_listed_slow(nodeid: str, entries: list[str]) -> bool:
    """An entry matches a whole file, a class or test (with or without parametrisation), or one exact node id."""
    for e in entries:
        if nodeid == e or nodeid.startswith((e + "::", e + "[")):
            return True
    return False


def pytest_collection_modifyitems(config, items):
    entries = _slow_entries()
    for item in items:
        if is_listed_slow(item.nodeid, entries):
            item.add_marker(pytest.mark.slow)


def pytest_addoption(parser):
    g = parser.getgroup("jev", "JEV contract tests")
    g.addoption("--jev-url", default=None, help="base URL of a JEV service to test (default: start the stub server)")
    g.addoption("--jev-model", default=None, help="model id to ask for (default: the first one /v1/models lists)")
    g.addoption("--jev-point", default="sample_method", help="a decision point name the service knows")
    g.addoption("--jev-options", default="bronch,ttnb,ebus", help="comma separated option ids to offer at that point")


def pytest_terminal_summary(terminalreporter):
    lat = getattr(terminalreporter.config, "_jev_latency", None)
    if lat:
        terminalreporter.write_sep("-", "JEV latency")
        terminalreporter.write_line(lat)

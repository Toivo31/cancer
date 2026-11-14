"""Options for the JEV contract tests (tests/test_jev_contract.py)."""


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

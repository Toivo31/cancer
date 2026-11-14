"""M1-8: CLI flags --jev, --decision-mode, --set."""

import json

import pytest

import jev
from jev.stub_server import serve_in_thread
from pathway_sim import load_scenario
from pathway_sim.__main__ import main

FIN = "scenarios/finland_lung.yaml"


def run(capsys, *args):
    main(["run", FIN, "--n", "3500", "--seed", "2", *args])
    return capsys.readouterr().out


def headline(out):
    return next(l for l in out.splitlines() if l.startswith("baseline"))


def test_default_unchanged_and_stub_equals_rule(capsys):
    legacy = run(capsys)
    assert "decisions:" not in legacy
    stub = run(capsys, "--jev", "stub")
    assert "decisions:" in stub and "via stub (stub@1), mode sample" in stub
    assert headline(stub) == headline(legacy)               # shipped scenario reproduces exactly
    assert headline(run(capsys, "--jev", "rule")) == headline(legacy)


def test_set_changes_the_run_and_decision_mode(capsys):
    base = headline(run(capsys, "--jev", "stub"))
    assert headline(run(capsys, "--jev", "stub", "--set", "first_contact.nurse_visit=0.95")) != base
    out = run(capsys, "--decision-mode", "argmax")
    assert "mode argmax" in out and headline(out) != base           # most-likely option at every point


def test_http_url_and_failure(capsys, tmp_path):
    sc = load_scenario(FIN)
    fc = jev.migrate_flowchart(sc.flowcharts["baseline"])
    srv, url = serve_in_thread(jev.StubBackend(fc.decision_policy["points"]))
    try:
        legacy = run(capsys)
        out = tmp_path / "r.json"
        remote = run(capsys, "--jev", url, "--out", str(out))
        assert headline(remote) == headline(legacy) and "via http" in remote
        d = json.loads(out.read_text())["decisions"]
        assert d["backend"] == "http" and d["requests_sent"] < d["decisions"]
        c = json.loads(out.read_text())["run"]["patients"][0]["choices"]
        assert c == [] or {"mode", "backend", "model"} <= set(c[0])
    finally:
        srv.shutdown()
        srv.server_close()
    with pytest.raises(SystemExit, match="did not answer"):
        run(capsys, "--jev", url)
    out = run(capsys, "--jev", url, "--on-error", "fallback_stub")
    assert headline(out) == headline(legacy) and "fallbacks" in out


@pytest.mark.parametrize("bad", [["--set", "nonsense"], ["--set", "foo.bar=0.1"], ["--set", "first_contact.nope=0.1"],
                                 ["--set", "first_contact.nurse_visit=2"], ["--jev", "wat"]])
def test_bad_flags_exit_with_a_message(capsys, bad):
    with pytest.raises(SystemExit) as e:
        run(capsys, *bad)
    assert e.value.code not in (0, None)

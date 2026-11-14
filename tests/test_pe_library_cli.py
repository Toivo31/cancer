"""Command line of the patient engine (WP-C1-6): ``python -m patient_engine`` and its command discovery."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from patient_engine.card import CohortSpec
from test_pe_library_support import ROOT, TINY, build_library


@pytest.fixture(scope="module")
def lib_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("cli") / "lib"
    build_library(path, per_condition=12)
    return path


def run(*args, cwd=ROOT, check=True, env=None):
    p = subprocess.run([sys.executable, "-m", "patient_engine", *map(str, args)], cwd=cwd, capture_output=True,
                       text=True, timeout=60, env=env)
    if check:
        assert p.returncode == 0, p.stderr
    return p


def test_library_info(lib_path):
    out = run("library-info", lib_path).stdout
    assert "library L_" in out and "verified" in out and "tiny" in out
    assert "lung_cancer" in out and "36" in out
    j = json.loads(run("library-info", lib_path, "--json").stdout)
    assert j["format"] == "library/1" and j["card_count_by_condition"] == {"healthy": 12, "lung_cancer": 12, "pneumonia": 12}


def test_library_info_fails_on_a_changed_file(lib_path, tmp_path):
    import shutil
    copy = tmp_path / "copy"
    shutil.copytree(lib_path, copy)
    f = copy / "cards.jsonl.gz"
    b = bytearray(f.read_bytes())
    b[len(b) // 2] ^= 0xFF
    f.write_bytes(bytes(b))
    p = run("library-info", copy, check=False)
    assert p.returncode == 1 and "LibraryError" in p.stderr and p.stdout == ""


def test_cohort_prints_marginals(lib_path):
    out = run("cohort", lib_path, "--n", 2000, "--seed", 3, "--prevalence", "lung_cancer=0.1,pneumonia=0.3,healthy=0.6").stdout
    assert "n=2000 seed=3" in out and "distinct cards" in out
    rows = {line.split()[0]: line.split() for line in out.splitlines() if line.split() and line.split()[0] in ("lung_cancer", "pneumonia", "healthy")}
    assert float(rows["lung_cancer"][2]) == pytest.approx(0.1, abs=0.005) and rows["healthy"][3] == "1200"


def test_cohort_json_with_catalogue_and_spec_file(lib_path, tmp_path):
    lib_id = json.loads(run("library-info", lib_path, "--json").stdout)["id"]
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(CohortSpec(lib_id, {"lung_cancer": 0.2, "healthy": 0.8}, 500, 7).to_json()))
    a = json.loads(run("cohort", lib_path, "--spec", spec, "--catalogue", TINY, "--rate-per-day", 44, "--json").stdout)
    b = json.loads(run("cohort", lib_path, "--spec", spec, "--catalogue", TINY, "--rate-per-day", 44, "--json").stdout)
    assert a == b and a["n"] == 500 and a["arrivals"] == {"rate_per_day": 44.0}
    assert {r["condition"] for r in a["conditions"]} == {"lung_cancer", "healthy"}
    assert set(a["tests"]) == {"history", "blood_count", "chest_xray", "chest_ct"} and a["array_bytes"] > 500 * 4 * 3
    assert a["tests"]["chest_xray"]["positive_first_attempt"] is not None


def test_cohort_refuses_a_condition_the_library_lacks(lib_path):
    p = run("cohort", lib_path, "--prevalence", "mesothelioma=1", check=False)
    assert p.returncode == 1 and "no cards" in p.stderr


def test_show_prints_the_public_view_only(lib_path):
    out = run("show", lib_path, "#0").stdout
    assert "patient" in out and "background" in out and "reported" in out
    for secret in ("hidden", "caused_by", "findings", "error_plan", "mentions", "lung_lesion"):
        assert secret not in out
    revealed = run("show", lib_path, "#0", "--reveal", "chest_xray:1", "--reveal", "blood_count").stdout
    assert "chest_xray[1]" in revealed and "blood_count[0]" in revealed and "crp=" in revealed
    j = json.loads(run("show", lib_path, "#0", "--json", "--reveal", "chest_ct").stdout)
    assert set(j) == {"card_id", "state", "background", "presenting", "observations", "notes"}
    assert j["observations"][0]["test"] == "chest_ct"


def test_show_hidden_prints_the_whole_card(lib_path):
    from patient_engine.library import load_library
    lib = load_library(lib_path)
    card = lib.cards[5]
    d = json.loads(run("show", lib_path, card.id, "--hidden").stdout)
    assert d["id"] == card.id and "hidden" in d and d["hidden"]["conditions"][0]["id"] == card.primary_condition
    assert run("show", lib_path, "no-such-card", check=False).returncode == 1


def test_no_command_prints_help_and_exits_2():
    p = run(check=False)
    assert p.returncode == 2 and "library-info" in p.stdout and "cohort" in p.stdout and "show" in p.stdout


def test_other_packages_add_commands_without_editing_main(tmp_path):
    """Discovery: a module dropped into patient_engine/commands/ that defines register() becomes a command; a
    broken module is reported and the rest keep working."""
    root = tmp_path / "repo"
    (root / "patient_engine").mkdir(parents=True)
    for f in ("__init__.py", "__main__.py"):
        (root / "patient_engine" / f).write_text((ROOT / "patient_engine" / f).read_text())
    (root / "patient_engine" / "commands").mkdir()
    (root / "patient_engine" / "commands" / "__init__.py").write_text((ROOT / "patient_engine" / "commands" / "__init__.py").read_text())
    (root / "patient_engine" / "commands" / "design.py").write_text(textwrap.dedent('''
        def register(subparsers):
            p = subparsers.add_parser("design", help="a command from another package")
            p.add_argument("--x", type=int, default=2)
            p.set_defaults(func=lambda a: print("designed", a.x) or 0)
    '''))
    (root / "patient_engine" / "commands" / "broken.py").write_text("import module_that_does_not_exist\n")
    (root / "patient_engine" / "commands" / "_private.py").write_text("raise SystemExit('never imported')\n")
    (root / "patient_engine" / "commands" / "plain.py").write_text("X = 1   # no register(): ignored\n")
    p = subprocess.run([sys.executable, "-m", "patient_engine", "design", "--x", "5"], cwd=root, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.strip() == "designed 5"
    assert "commands/broken.py failed to import" in p.stderr and "_private" not in p.stderr and "plain" not in p.stderr

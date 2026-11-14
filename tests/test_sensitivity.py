"""Fast checks of pathway_sim.sensitivity and pathway_sim.checks (tiny n)."""
from pathlib import Path

import yaml

from pathway_sim.checks import incomplete_board_scenario
from pathway_sim.scenario import scenario_from_dict
from pathway_sim.sensitivity import Evaluator, discover, noise, run_sensitivity, select, tornado

ROOT = Path(__file__).resolve().parent.parent
STOK = ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml"
FIN = ROOT / "scenarios" / "finland_lung.yaml"


def test_discovery_finds_assumptions_and_applies_them():
    raw = yaml.safe_load(STOK.read_text())
    ps = {p.id: p for p in discover(raw)}
    assert "tests.further_workup.wait.median" in ps and "treatment_wait_after_board" in ps
    r = yaml.safe_load(STOK.read_text())
    p = ps["tests.further_workup.wait.median"]
    ratio = r["tests"]["further_workup"]["wait"]["p90"] / r["tests"]["further_workup"]["wait"]["median"]
    p.apply(r, 1.0)
    w = r["tests"]["further_workup"]["wait"]
    assert abs(w["median"] - 7 * 1.25) < 1e-9 and abs(w["p90"] / w["median"] - ratio) < 1e-9
    scenario_from_dict(r)                       # still valid


def test_finland_params_integer_capacity_and_shortlist():
    raw = yaml.safe_load(FIN.read_text())
    allp = discover(raw)
    ids = {p.id for p in allp}
    assert "resources.ct_scanner.capacity_per_day" in ids and "arrivals.rate_per_day" in ids
    sel = {p.id for p in select(allp, None, "finland_lung")}
    assert 10 < len(sel) < 40
    cap = {p.id: p for p in allp}["resources.pet_scanner.capacity_per_day"]
    r = yaml.safe_load(FIN.read_text())
    cap.apply(r, -1.0)
    assert r["resources"]["pet_scanner"]["capacity_per_day"] == 1          # never below one slot
    cap.apply(r, 1.0)
    assert r["resources"]["pet_scanner"]["capacity_per_day"] == 2
    assert r["flowcharts"]["bundled_workup"]["resource_overrides"]["pet_scanner"]["capacity_per_day"] == 4


def test_tornado_and_noise_tiny():
    res = run_sensitivity(str(STOK), [("observed", "optimal")], n=120, seeds=[1], draws=3,
                          only=[r"further_workup\.wait", r"^treatment_wait_after_board$"], noise_seeds=[1, 2], log=lambda *_: None)
    rows = res["tornado"]["rows"]
    assert len(rows) == 2 and res["n_params"] == 2
    x = rows[0]["observed>optimal"]
    assert {"gain_pp_low", "gain_pp_high", "swing_pp", "gain_vanishes"} <= set(x)
    # reordering beats the status quo at the base setting
    assert res["tornado"]["pairs"]["observed>optimal"]["base_gain_pp"] > 0
    assert res["joint"]["summary"]["observed>optimal"]["all"]["draws"] == 3
    assert res["noise"]["observed>optimal"]["sd_pp_single_seed"] is not None


def test_incomplete_board_scenario_loads_and_runs():
    from pathway_sim import compute_metrics, generate_patients, simulate
    for both in (False, True):
        sc = scenario_from_dict(yaml.safe_load(incomplete_board_scenario(0.16, both)))
        pts = generate_patients(sc, 150, 1)
        for f in ("observed", "faster_pet", "optimal"):
            m = compute_metrics(simulate(sc, f, pts, seed=1), sc)
            assert m["stuck"] == 0

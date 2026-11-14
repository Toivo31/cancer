"""Golden check on what a judge sees: the service's Norway template reproduces the published figure.

Stokstad 2019 observed 40% treated within 42 days; our calibrated world gives 40.1% in the dashboard
bundle. A template built from the uncalibrated file gives about 11% (found 14 Nov), so this test pins it."""

from pathlib import Path

from pathway_sim import compute_metrics, generate_patients, simulate
from service.prepare import prepare_run
from service.templates import load_templates

ROOT = Path(__file__).resolve().parent.parent


def test_norway_template_observed_is_near_the_published_40_percent():
    t = load_templates(ROOT / "scenarios")["norway_check"]
    doc = next(f for f in t["flowcharts"] if f["id"] == "observed")
    shares = []
    for seed in (301, 302):
        sc, fc, policy = prepare_run(t["world"], doc, seed=seed)
        run = simulate(sc, fc, generate_patients(sc, 1000, seed), policy=policy, seed=seed)
        shares.append(compute_metrics(run, sc)["share_within_target"])
    share = sum(shares) / len(shares)
    assert 0.34 <= share <= 0.46, share

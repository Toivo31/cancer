"""Review check M3: the 'predicted' 80% for the authors' pathway depends on the calibrated share of PET-CT
ordered at referral triage (1.0, grid edge), which reaches the `optimal` flowchart through the YAML anchor
&pet_triage_mix. Held-out seeds 201-203, n=1000. ~20 s.
    python3 docs/review_checks/stokstad_authors_pathway_vs_pet_triage.py"""
import copy
import json
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import compute_metrics, generate_patients, simulate  # noqa: E402
from pathway_sim.scenario import scenario_from_dict  # noqa: E402

raw = yaml.safe_load((ROOT / "scenarios" / "generated" / "stokstad_calibrated.yaml").read_text())
print("observed and optimal share one mix object:", raw["flowcharts"]["observed"]["policy"]["pet_on_time"] is raw["flowcharts"]["optimal"]["policy"]["pet_on_time"])
results = {}
for share in (1.0, 0.5, 0.0):
    r = copy.deepcopy(raw)
    r["flowcharts"]["optimal"]["policy"]["pet_on_time"] = {"mix": {"pet_triage": share, "pet_early_route": 1 - share}}
    sc = scenario_from_dict(r)
    v = [compute_metrics(simulate(sc, "optimal", generate_patients(sc, 1000, s), seed=s), sc)["share_within_target"] for s in (201, 202, 203)]
    results[f"{share:.1f}"] = sum(v) / 3
    print(f"authors' pathway, PET-CT ordered at triage for {share:.0%} (rest at first visit): {sum(v) / 3:.3f}")

(ROOT / "docs" / "review_checks" / "stokstad_pet_triage_result.json").write_text(json.dumps(
    {"note": "authors' pathway share within 42 d by share of PET-CT ordered at referral triage; held-out seeds 201-203, n=1000", "share_within_target_by_pet_triage_share": results}, indent=1))

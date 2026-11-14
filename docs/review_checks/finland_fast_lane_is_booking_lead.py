"""Review check B1: the Finnish headline change (fast_track at referral triage) equals 'shorten every
routine booking lead to the assumed urgent lead'. Held-out cohorts 301, 302 as in the bundle. ~30 s.
    python3 docs/review_checks/finland_fast_lane_is_booking_lead.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate  # noqa: E402

sc = load_scenario(ROOT / "scenarios" / "finland_lung.yaml")
cohorts = [(s, generate_patients(sc, 18800, s)) for s in (301, 302)]
urgent = {rid: r for rid, r in sc.resources.items() if "urgent_lead_days" in r}


def ev(fc):
    ms = [compute_metrics(simulate(sc, fc, p, seed=s), sc) for s, p in cohorts]
    return tuple(round(sum(m[k] for m in ms) / 2, 4) for k in ("share_within_target", "median_days_to_treatment", "missed_cancers"))


base = sc.flowcharts["baseline"]
print("baseline                                   share, median, missed:", ev(base))
lead = base.copy("lead")
lead.resource_overrides = {rid: {"min_lead_days": r["urgent_lead_days"]} for rid, r in urgent.items()}
print("baseline, routine lead := urgent lead, NO fast track:      ", ev(lead))
for frac in (1.0, 0.5, 0.0):
    ft = base.copy("ft")
    ft.nodes["triage"].fast_track = True
    ft.resource_overrides = {rid: {"urgent_lead_days": r["min_lead_days"] - frac * (r["min_lead_days"] - r["urgent_lead_days"])}
                             for rid, r in urgent.items()}
    print(f"fast_track(triage), urgent lead = {frac:.0%} of assumed gap:   ", ev(ft))

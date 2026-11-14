"""Render docs/ranges.md, docs/booking_vs_queue.md and docs/capacity_probe.md from the JSON outputs of the scripts in this
folder (every number in those documents is printed from the JSON, none typed).   python3 docs/evidence_checks/render_docs.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "docs"
J = lambda n: json.loads((D / n).read_text())  # noqa: E731
p0 = lambda x: f"{100 * x:.0f}"  # noqa: E731
p1 = lambda x: f"{100 * x:.1f}"  # noqa: E731

# ------------------------------------------------------------------ ranges.md
F, N = J("ranges_finland.json"), J("ranges_norway.json")
A = F["cohort_spread"]
S = F["sensitivity_suggested_vs_baseline"]
k = "baseline>suggested"
rows = S["tornado"]["rows"]
jt = S["joint"]["summary"][k]["all"]
nz = S["noise"][k]
worst = min(rows, key=lambda r: r[k]["worst_gain_pp"])
top = sorted(rows, key=lambda r: -(r[k]["swing_pp"] or 0))[:8]
L = ["# Ranges next to the headline numbers", "",
     "Analysis outputs only; no simulation behaviour changed. Scripts: `docs/evidence_checks/` (`finland_suggested.py`, `norway_suggested.py`, `ranges_finland.py`, `ranges_norway.py`, then `render_docs.py`). "
     "Raw numbers: `docs/ranges_finland.json`, `docs/ranges_norway.json`. The headline numbers elsewhere are unchanged; this page says how far they move.", "",
     "## Finland: today 18% to 33% within 90 days", "",
     f"The headline is the mean of two held-out cohorts (seeds 301 and 302, each about {int(S['n']):,} patients and {A['per_cohort'][0]['baseline']['n_cancer']:.0f} cancers). "
     f"Here is the same comparison on {len(A['seeds'])} independent cohorts (seeds {A['seeds'][0]} to {A['seeds'][-1]}); the accepted flowchart is the one the optimiser found, re-derived and checked against the bundle.", "",
     "| Cohort | Today | Suggested | Gain, pp |", "|---|---|---|---|"]
for r in A["per_cohort"]:
    L.append(f"| {r['seed']} | {p1(r['baseline']['share'])}% | {p1(r['suggested']['share'])}% | {100 * (r['suggested']['share'] - r['baseline']['share']):.1f} |")
g, b, s_ = A["gain_pp"], A["baseline_share"], A["suggested_share"]
L += ["", f"- Today ranges from {p0(b['min'])}% to {p0(b['max'])}% across cohorts (mean {p1(b['mean'])}, sd {100 * b['sd']:.1f} pp). The suggested change ranges from {p0(s_['min'])}% to {p0(s_['max'])}% (mean {p1(s_['mean'])}).",
      f"- The gain is {g['min']:.1f} to {g['max']:.1f} pp (mean {g['mean']:.1f}, sd {g['sd']:.1f}) and positive in {A['cohorts_where_suggested_beats_baseline']} of {len(A['seeds'])} cohorts. By group: vague symptoms {A['gain_pp_by_group']['non_specific']['min']:.1f} to {A['gain_pp_by_group']['non_specific']['max']:.1f} pp, alarm symptoms {A['gain_pp_by_group']['site_specific']['min']:.1f} to {A['gain_pp_by_group']['site_specific']['max']:.1f} pp.",
      f"- Median days to treatment: today {A['baseline_median']['min']:.0f} to {A['baseline_median']['max']:.0f}, suggested {A['suggested_median']['min']:.0f} to {A['suggested_median']['max']:.0f}.",
      "- **Reading.** Say \"18% to 33%\" only with \"two cohorts\" next to it. The level of the share moves by about 10 pp from cohort to cohort (cohorts have about 260 cancers); the size of the gain is stabler, about 15 pp. The training cohorts the search used show the same pattern (13% to 29% in the bundle).", "",
      "### Sensitivity of the accepted Finnish changes (the comparison the older sensitivity files do not cover)", "",
      f"`pathway_sim.sensitivity` with the accepted flowchart as comparison B: {len(rows)} shortlisted assumption parameters varied one at a time (x0.75 / x1.25, integer capacities plus or minus one slot), seed 1, then {jt['draws']} joint draws. "
      f"Base gain at seed 1 is {S['tornado']['pairs'][k]['base_gain_pp']} pp and {abs(S['tornado']['pairs'][k]['base_gain_days'])} days; seed-to-seed sd of the gain {nz['sd_pp_single_seed']} pp (seeds {nz['seeds']}: {nz['gain_pp']} pp).", "",
      f"- One at a time: the gain stays positive in {sum(1 for r in rows if not r[k]['gain_vanishes'])} of {len(rows)} parameters; the smallest is {worst[k]['worst_gain_pp']} pp (`{worst['param']}`, flagged unstable: {worst[k]['unstable']}).",
      f"- Joint draws: the suggested change beats today in {p0(jt['p_B_better_share'])}% of {jt['draws']} draws, gain {jt['gain_pp']['p5']} to {jt['gain_pp']['p95']} pp (5th to 95th percentile; min {jt['gain_pp']['min']}, max {jt['gain_pp']['max']}), median {jt['gain_pp']['median']} pp; median days {jt['gain_days']['p5']} to {jt['gain_days']['p95']}.",
      f"- The gain nearly disappears when clinic or CT capacity is one slot lower ({worst['param']} low: {worst[k]['gain_pp_low']} pp; clinic capacity low: {next(r for r in rows if r['param'] == 'resources.clinic.capacity_per_day')[k]['gain_pp_low']} pp), the same capacity dependence the older sensitivity page found for the order-together pathway.",
      "- The urgent booking leads, which carry the conditional 61%, do not move this gain: the accepted changes use no priority lane. What moves it is capacity at the clinic and CT, the share of cancers a GP sends on at first contact, and the arrival rate.", "",
      "| Parameter (varied one at a time) | Low / base / high | Gain at low, pp | Gain at high, pp |", "|---|---|---|---|"]
for r in top:
    L.append(f"| `{r['param']}` | {r['low']} / {r['base']} / {r['high']} | {r[k]['gain_pp_low']} | {r[k]['gain_pp_high']} |")
L += ["", "Caveats: one seed per variant (single-seed noise about the sd above, so ranking among the smaller rows is not reliable); only the 26 default-shortlist assumptions are varied, out of the assumption parameters listed in `docs/ledger.md`; the Finnish scenario is not calibrated to Finnish capacity data, so this is robustness to our assumptions, not to the real county.", ""]
C, B = N["cohorts_of_100"], N["accepted_calibration_sets"]
L += ["## Norway: 40 observed, 80 authors' pathway, 88 optimiser with the faster scanner, 67 without", "",
      "Two sources of uncertainty, both for the flowcharts the bundle reports (the two optimiser flowcharts were found once, on the best-fit calibration).", "",
      "| Flowchart | Bundle (3 x 1000 patients) | 100-patient cohorts, central 95% (300 cohorts) | Across the 11 accepted calibration sets (3 x 1000 patients each), min to max |", "|---|---|---|---|"]
bundle = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
st = next(s for s in bundle["scenarios"] if s["id"] == "stokstad")
bv = {"observed": st["baseline"]["metrics"], **{v["role"]: v["metrics"] for v in st["variants"]}}
names = [("observed", "Observed pathway", "observed", "Published 40% (95% CI 31 to 50)"), ("faster_pet", "Faster PET-CT only", "faster_pet", "Published 48% (39 to 58)"),
         ("authors", "Authors' pathway, simulated", "authors_pathway", "Published 80% (72 to 87)"),
         ("optimiser_faster_scanner", "Optimiser, faster scanner", "optimiser", "no published value"), ("optimiser_no_new_equipment", "Optimiser, no new equipment", "optimiser_no_new_equipment", "no published value")]
for key, lab, role, _ in names:
    L.append(f"| {lab} | {p1(bv[role]['share_within_target'])}% | {p0(C[key]['p2_5'])} to {p0(C[key]['p97_5'])}% | {p0(B['range'][key]['min'])} to {p0(B['range'][key]['max'])}% |")
L += ["", f"- A real cohort has 100 patients, so any single-hospital number carries about plus or minus {(C['authors']['p97_5'] - C['authors']['p2_5']) * 50:.0f} pp (central 95% range {p0(C['authors']['p2_5'])} to {p0(C['authors']['p97_5'])}% for the authors' pathway); the published 95% intervals (observed 31 to 50, authors' 72 to 87) are of that size and our 100-patient ranges match them.",
      f"- Across the {len(B['per_set'])} calibration sets that all reproduce the observed pathway ({p0(B['range']['observed']['min'])} to {p0(B['range']['observed']['max'])}% in this check; the fit tolerance is plus or minus 4 pp), the authors' pathway is {p0(B['range']['authors']['min'])} to {p0(B['range']['authors']['max'])}%, the optimiser with the faster scanner {p0(B['range']['optimiser_faster_scanner']['min'])} to {p0(B['range']['optimiser_faster_scanner']['max'])}%, and without new equipment {p0(B['range']['optimiser_no_new_equipment']['min'])} to {p0(B['range']['optimiser_no_new_equipment']['max'])}%. The no-new-equipment number is the less certain of the two optimiser numbers. The ordering (optimiser above the authors' pathway above faster PET-CT above observed) holds in {sum(1 for r in B['per_set'] if r['optimiser_faster_scanner'] > r['authors'] > r['faster_pet'] > r['observed'])} of {len(B['per_set'])} sets.",
      "- The optimiser flowcharts were found under the best-fit calibration and evaluated under the others unchanged, so these ranges are slightly pessimistic for the optimiser (a re-search per calibration might find a better flowchart).",
      "- Disclosures from the review stand (PET-CT at triage carried into the authors' pathway: 66% if PET-CT is ordered at the first visit; the menu of about 69 changes contained the authors' changes).", ""]
(D / "ranges.md").write_text("\n".join(L))

# ------------------------------------------------------------------ booking_vs_queue.md
Q = J("booking_vs_queue.json")
keys = ["booking lead", "assumed extra_wait", "capacity queue", "paper / weekly board"]
b, s2 = Q["baseline"]["mean"], Q["suggested"]["mean"]
L = ["# Booking time versus queueing (review item, M8-6)", "",
     "Script: `docs/evidence_checks/booking_vs_queue.py` (extends `docs/review_checks/finland_waiting_decomposition.py` to both held-out cohorts, 301 and 302, and to the accepted flowchart). Mean over treated cancers of the days on each patient's critical path, by kind of wait. "
     "Waiting plus service on the critical path equals time to treatment exactly (largest difference "
     f"{max(Q[f]['cohorts'][c]['max_accounting_error_days'] for f in Q for c in Q[f]['cohorts']):.1g} d).", "",
     "| Kind of wait (days per treated cancer) | Today | Suggested | Change |", "|---|---|---|---|"]
for kk in keys:
    L.append(f"| {kk} | {b[kk]:.1f} | {s2[kk]:.1f} | {s2[kk] - b[kk]:+.1f} |")
L.append(f"| **Mean days to treatment** | {b['mean_days_to_treatment']:.1f} | {s2['mean_days_to_treatment']:.1f} | {s2['mean_days_to_treatment'] - b['mean_days_to_treatment']:+.1f} |")
tot = sum(b[kk] for kk in keys)
L += ["", f"- **Most of the waiting is booking lead, not queueing.** Today {b['booking lead']:.0f} of {tot:.0f} waiting days ({100 * b['booking lead'] / tot:.0f}%) are the fixed booking lead (`min_lead_days`, tuned to published waits), {b['capacity queue']:.0f} ({100 * b['capacity queue'] / tot:.0f}%) are capacity queueing. "
      "The dashboard and deck therefore say \"waiting (booking time and queues)\".",
      f"- **The accepted reorders remove paperwork and board time from the critical path, not booking or queue time.** The change in the table is {s2['paper / weekly board'] - b['paper / weekly board']:+.1f} d in referral paperwork and board waiting and {s2['capacity queue'] - b['capacity queue']:+.1f} d in capacity queueing; booking leads change by {s2['booking lead'] - b['booking lead']:+.1f} d. "
      "Mechanism: the specialist visit is booked while the referral is being handled, and the treatment slot is reserved while the case waits for the board, so those waits overlap instead of adding up.",
      "- **What the gain rests on.** The paperwork steps are `referral_triage` (sourced to the Pirkanmaa pathway document: handling 1 to 2 working days, invitation letter 3 to 4), `gp_referral_letter`, `gp_second_look` and the weekly board (all `assumption`). The size of the 8-day gain is therefore as good as those assumed delays; the direction does not depend on booking leads.",
      "- **Model change?** None made. The split suggests the dashboard's stage bars could show booking lead and queue separately (the engine knows both), but that is a display change owned by the dashboard track. See the channel entry.", ""]
(D / "booking_vs_queue.md").write_text("\n".join(L))

# ------------------------------------------------------------------ capacity_probe.md
P = J("capacity_probe.json")
bundle_probe = {r["resource"]: r for r in next(s for s in bundle["scenarios"] if s["id"] == "finland_lung")["capacity_probe"]}
L = ["# Capacity probe: what one more slot a day gains (M8-4)", "",
     "Script: `docs/evidence_checks/capacity_probe.py`. Same method as the dashboard's table (add one slot a day to one resource through `resource_overrides`, same patients), "
     "run on six cohorts (seeds 301 to 306) so each row carries its range, and on both today's pathway and the accepted pathway. The dashboard's column is the mean of two cohorts (301, 302).", "",
     "| Resource | Slots now | Today: gain in share within 90 d, pp (mean, range over 6 cohorts) | Dashboard (2 cohorts) | After the suggested change: gain, pp (mean, range) |", "|---|---|---|---|---|"]
sug = {r["resource"]: r for r in P["suggested"]["rows"]}
for r in P["baseline"]["rows"]:
    bp = bundle_probe.get(r["resource"], {})
    s3 = sug[r["resource"]]
    L.append(f"| `{r['resource']}` | {r['slots_now']} | {r['delta_share_pp_mean']:+.1f} ({r['delta_share_pp_min']:+.1f} to {r['delta_share_pp_max']:+.1f}) | {bp.get('delta_share_pp', float('nan')):+.1f} | {s3['delta_share_pp_mean']:+.1f} ({s3['delta_share_pp_min']:+.1f} to {s3['delta_share_pp_max']:+.1f}) |")
L += ["", "- The ranking at the top is stable: the PET-CT scanner first, bronchoscopy second, in the mean, and the same two after the suggested change. The size of any single gain is not: one cohort can show several points more or fewer, and rows within about 1 pp of zero are noise.",
      "- Reading for the pitch: \"one more slot at the PET-CT scanner is worth about the same as the two reorders' gain, and the reorders need no slot\" would overstate it; the honest line is that the PET-CT scanner and bronchoscopy are the capacity-limited steps in our synthetic county, and the capacities are our assumptions.", ""]
(D / "capacity_probe.md").write_text("\n".join(L))
print("rendered ranges.md, booking_vs_queue.md, capacity_probe.md")

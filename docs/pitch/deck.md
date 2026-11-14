# Deck: final content, 10 slides

Numbers in double square brackets come from `demo/data/demo_bundle.json` via `fill_numbers.py`; read the filled copy in `filled/deck.md`. Weights: Actionability 30, Insight 25, Data quality and transparency 20, Execution 15, Clarity 10. Plain words on slides (no "node", "embedding"). "Synthetic data" label on every results slide. Screens refer to `demo/index.html` (keys 1-4).

**Two team decisions change slide 1 and 6.** D20: the Finnish headline uses a provisional [[f_target]]-day target; the alternative is to show the median days (from [[f_median_base]] to [[f_median_opt]]) as the headline and the share only as a second number. D17: the Norwegian headline is the search with the faster scanner (the authors' premise); the alternative is to lead with the no-new-equipment result. Both versions are written below.

| # | Slide title (one message) | Numbers and content | Visual (dashboard screen) | Criterion |
|---|---|---|---|---|
| 1 | **In our synthetic Finnish county, one change gets [[f_share_opt]]% treated within [[f_target]] days, from [[f_share_base]]%** | Median [[f_median_base]] to [[f_median_opt]] days. Missed cancers [[f_missed_base]] to [[f_missed_opt]] per cohort. Held-out patients. Alt (D20): lead with "[[f_median_gain]] days faster" and show the share small. | Screen 1, headline number in large type | Clarity, Actionability |
| 2 | **Finland waits longest in the Nordics at the first steps, and survives least** | Sourced, not ours: lung cancer five-year survival in men 17% against 27-30% (IHE dashboard); first appointment about 14 days against 2-7; 40-60% see a nurse first; under 10% of primary-care units can perform CT. Strategy Goal 3 indicator "treatment within target times" is what we measure. | Static slide with cited numbers | Insight |
| 3 | **Time is lost mostly in waiting, and mostly before the specialist** | In the synthetic baseline waiting is [[f_wait_share]]% of the [[f_wait_total]] + [[f_svc_total]] days. By stage: detection [[f_wait_detection]] d, referral [[f_wait_referral]], diagnosis [[f_wait_diagnosis]], treatment start [[f_wait_treatment]]. Largest single waits: [[f_node_list]]. | Screen 2, four stage bars, waiting vs service | Insight |
| 4 | **Order matters more than capacity, in a real Norwegian study and in ours** | Stokstad: [[s_pub_base]]% observed, [[s_pub_fast]]% with a faster PET-CT (not significant), [[s_pub_opt]]% reordered. Ours: extra CT and PET capacity alone [[f_capctl_share]]%, the same capacity plus reordering [[f_bundle_share]]% (baseline [[f_share_base]]%). One more slot at the busiest scanner: +[[f_cap_top_pp]] points; next best +[[f_cap_second_pp]]. | Screen 2 or 3, bar pair; capacity probe table | Insight, Data quality |
| 5 | **How it works: propose, rerun, compare** | Synthetic patients, a flowchart of steps, a run. The optimiser proposes from what steps revealed, never the hidden truth. Same patients rerun to accept. Held-out patients to report. A clinician approves. In real life the rerun is a pilot. | One diagram | Execution, Clarity |
| 6 | **It reproduces a real pathway first, with one miss** | Fitted on the observed pathway only: [[s_obs_share]]% (published [[s_pub_base]]%). Predicted, not fitted: authors' pathway [[s_auth_share]]% (published [[s_pub_opt]]%). Faster PET only: [[s_fast_share]]% against published [[s_pub_fast]]%: we over-predict. Blind search: [[s_opt_share]]% with the faster scanner (authors' three changes plus one), [[s_noeq_share]]% with no new equipment. Alt (D17): lead with [[s_noeq_share]]%. | Screen 3, validation bars with published markers | Data quality, Execution |
| 7 | **The change for Finland** | Before/after flowchart. [[f_n_changes]]: [[f_changes]]. Held-out: within [[f_target]] d [[f_share_base]]% to [[f_share_opt]]%, tests per patient [[f_tests_base]] to [[f_tests_opt]], non-cancer patients leave the pathway in [[f_noncancer_base]] to [[f_noncancer_opt]] days (median). Hand-written "order together" reaches [[f_bundle_share]]% but needs 3 PET-CT slots. | Screen 3, flowchart before/after | Actionability |
| 8 | **Who waits longest, and does the change reach them?** | Vague-symptom patients [[f_ns_share_base]]% to [[f_ns_share_opt]]%; alarm-symptom [[f_ss_share_base]]% to [[f_ss_share_opt]]% within target. Both gain. Gap in points [[f_gap_pp_widens]] ([[equity_gap_before_pp]] to [[equity_gap_after_pp]]); gap in median days [[f_gap_days_narrows]] ([[f_gap_days_before]] to [[f_gap_days_after]]). The group gap is built from our assumption. | Screen 4, two bars per group | Insight, Data quality |
| 9 | **A recommendation in five actions** | Order together at the first specialist visit; direct CT paired with it (alone: [[f_direct_share]]%); fast lane for vague symptoms with a published guardrail ([[f_fast_share]]%); monitor time per step by county; pilot in one county first. Say which are tested in simulation (1-3) and which rest on cited evidence (4-5). | Recommendation card | Actionability |
| 10 | **What is real, what is synthetic, what comes next** | All patients synthetic; [[parameter_count]] parameters, [[assumption_count]] marked assumption, rest sourced. Held-out reporting; [[s_opt_optimism_pp]] point selection optimism in the Norwegian run. Next: real county data and a pilot. Decision model: beats a dot-product baseline on a set-relative task ([[dm_acc_corr]]% against [[dm_acc_dot]]%), but not yet in the demo loop, and the half-compute claim did not hold. Team, ask. | Screen 4 sources list | Data quality, Clarity |

## Speaker notes, one line each

1. Number, then the change, then stop. Say "in our synthetic county".
2. These are reported figures from the dashboard, not ours.
3. Say that most of the time is waiting, and that primary care is the biggest single stage in our model.
4. The 80% is a model estimate in the paper; the lesson is direction. Our capacity-only control is the same extra capacity with the old order.
5. Do not name the architecture. A judge can ask; see qa.md.
6. Say the miss: we over-predict the faster-scanner-only result.
7. Held-out numbers, not training numbers.
8. Report both gap measures; do not say the gap closes.
9. Actions 4 and 5 are not tested by us.
10. Synthetic, stated plainly, with a path to real data.

## Backup slides

- Decision model against the dot-product baseline at one choice point: [[dm_acc_corr]]% against [[dm_acc_dot]]% (parameter-matched wider baseline [[dm_acc_dot_wide]]%); on the control task without the set-relative rule the gap is [[dm_ctrl_gain_pp]] points, so part of the gain is capacity. Second question costs [[dm_second_lo]]-[[dm_second_hi]]% of the first at our sizes, not half.
- Parameter table with sources (screen 4).
- Capacity probe table: [[f_cap_table]]
- Limits: crowd-out (Swedish interviews), real shortages (Cooke 2022), single region.

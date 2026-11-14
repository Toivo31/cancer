# Deck outline, 10 slides (E4)

Each slide: one message, the judging criterion it serves (weights: Actionability 30, Insight 25, Data quality and transparency 20, Execution 15, Clarity 10). Plain words on slides: no "node", "optimiser", "embedding". Placeholders `[[ ]]` come from the final run.

| # | Message (slide title) | Content | Criterion |
|---|---|---|---|
| 1 | **`[[finland_share_base]]%` treated on time today, `[[finland_share_opt]]%` with one change** | Number first, large type. One sentence: what changes and for whom. | Clarity, Actionability |
| 2 | **Finland waits longest in the Nordics, and survives least** | Lung cancer 5-year survival, men 17% vs 27-30%; waits at the first two steps (IHE dashboard). Strategy Goal 3 indicator "treatment within target times" named as what we measure. | Insight |
| 3 | **Time is lost in specific places** | Four stages (detection, referral, diagnosis, treatment start), waiting vs service time; nurse-first 40-60%, <10% of primary-care units perform CT, Satakunta two weeks plus two months. | Insight |
| 4 | **Order matters more than capacity** | Stokstad: 40% observed, 48% with faster PET-CT (not significant), 80% reordered. Beside it: English rapid CT, 15 to 3 days to CT, decision time 66 vs 65. | Insight, Data quality |
| 5 | **The system: propose, rerun, compare** | One simple diagram: synthetic patients, flowchart, run, change proposed from revealed information only, same patients rerun, held-out patients checked. Clinician approves. | Execution, Clarity |
| 6 | **It reproduces a real pathway first** | Calibration against Stokstad: `[[stokstad_sim_share]]` vs 40%; search finds a similar reordering `[[stokstad_opt_share]]` vs 80%; what matched, what was assumed. | Data quality, Execution |
| 7 | **The change for Finland** | Before/after flowchart and numbers on held-out patients: share within target, median days, missed cancers, tests per patient, waits for other patients (guardrail). | Actionability |
| 8 | **Who waits longest, and does the change reach them?** | Split by presentation group; gap `[[equity_gap_before_pp]]` to `[[equity_gap_after_pp]]` pp. Plus what we cannot show: one region, synthetic groups. | Insight, Data quality |
| 9 | **A national recommendation in five actions** | Order together at first visit; direct CT in primary care; fast track for vague symptoms with guardrail; per-step monitoring by county; pilot first. Owners: counties, THL, collaborative areas. Which are tested, which rest on evidence. | Actionability |
| 10 | **What is real, what is synthetic, what comes next** | Data is synthetic; every parameter traced to `params/sources.yaml`; proposal vs acceptance honesty note; pilot with real county data as the step after. Team, call to action. | Data quality, Clarity |

## Speaker notes, one line each

1. Say the number, then the change, then stop.
2. Everything on this slide is from the cited dashboard; say "reported" not "proven".
3. Point to the stage where most waiting is, from our run.
4. Emphasise that the 80% is a model estimate in the paper; the lesson is the direction.
5. Do not name the architecture. A reviewer can ask.
6. If calibration is not close, say the gap and why.
7. Show held-out numbers, not training numbers.
8. Do not claim Finnish inequality is proven by our model; the registry studies show it.
9. Be explicit that actions 4 and 5 are not tested by us.
10. Synthetic, stated plainly, and a path to real data.

## Backup slides

- Decision model vs dot-product baseline at one choice point (if the result is ready).
- Parameter table with sources.
- Limits: crowd-out (Swedish interviews), real shortages (Cooke 2022).

# Deck: final content, 10 slides

Numbers in double square brackets come from `demo/data/demo_bundle.json` via `fill_numbers.py`; read the filled copy in `filled/deck.md`. Weights: Actionability 30, Insight 25, Data quality and transparency 20, Execution 15, Clarity 10. Plain words on slides (no "node", "embedding"). "Synthetic data" label on every results slide. Screens refer to `demo/index.html` (keys 1-4).

**Two team decisions change slide 1 and 6.** D20: the Finnish headline uses a provisional 90-day target; the alternative is to show the median days (from 102 to 80) as the headline and the share only as a second number. D17: the Norwegian headline is the search with the faster scanner (the authors' premise); the alternative is to lead with the no-new-equipment result. Both versions are written below.

| # | Slide title (one message) | Numbers and content | Visual (dashboard screen) | Criterion |
|---|---|---|---|---|
| 1 | **In our synthetic Finnish county, one change gets 64% treated within 90 days, from 18%** | Median 102 to 80 days. Missed cancers 27.5 to 25.0 per cohort. Held-out patients. Alt (D20): lead with "23 days faster" and show the share small. | Screen 1, headline number in large type | Clarity, Actionability |
| 2 | **Finland waits longest in the Nordics at the first steps, and survives least** | Sourced, not ours: lung cancer five-year survival in men 17% against 27-30% (IHE dashboard); first appointment about 14 days against 2-7; 40-60% see a nurse first; under 10% of primary-care units can perform CT. Strategy Goal 3 indicator "treatment within target times" is what we measure. | Static slide with cited numbers | Insight |
| 3 | **Time is lost mostly in waiting, and mostly before the specialist** | In the synthetic baseline waiting is 87% of the 91 + 14 days. By stage: detection 30 d, referral 17, diagnosis 23, treatment start 21. Largest single waits: waiting for treatment slot (16 d), re-presents to gp (15 d), specialist visit (13 d). | Screen 2, four stage bars, waiting vs service | Insight |
| 4 | **Order matters more than capacity, in a real Norwegian study and in ours** | Stokstad: 40% observed, 48% with a faster PET-CT (not significant), 80% reordered. Ours: extra CT and PET capacity alone 31%, the same capacity plus reordering 54% (baseline 18%). One more slot at the busiest scanner: +9.7 points; next best +3.6. | Screen 2 or 3, bar pair; capacity probe table | Insight, Data quality |
| 5 | **How it works: propose, rerun, compare** | Synthetic patients, a flowchart of steps, a run. The optimiser proposes from what steps revealed, never the hidden truth. Same patients rerun to accept. Held-out patients to report. A clinician approves. In real life the rerun is a pilot. | One diagram | Execution, Clarity |
| 6 | **It reproduces a real pathway first, with one miss** | Fitted on the observed pathway only: 40% (published 40%). Predicted, not fitted: authors' pathway 80% (published 80%). Faster PET only: 60% against published 48%: we over-predict. Blind search: 88% with the faster scanner (authors' three changes plus one), 67% with no new equipment. Alt (D17): lead with 67%. | Screen 3, validation bars with published markers | Data quality, Execution |
| 7 | **The change for Finland** | Before/after flowchart. Two steps: Fast track patients after referral handling at hospital; Nurse or GP first: always gp appointment. Held-out: within 90 d 18% to 64%, tests per patient 0.41 to 0.39, non-cancer patients leave the pathway in 16.8 to 13.8 days (median). Hand-written "order together" reaches 54% but needs 3 PET-CT slots. | Screen 3, flowchart before/after | Actionability |
| 8 | **Who waits longest, and does the change reach them?** | Vague-symptom patients 16% to 60%; alarm-symptom 31% to 78% within target. Both gain. Gap in points widens (14.9 to 18.6); gap in median days narrows (13.6 to 7.3). The group gap is built from our assumption. | Screen 4, two bars per group | Insight, Data quality |
| 9 | **A recommendation in five actions** | Order together at the first specialist visit; direct CT paired with it (alone: 20%); fast lane for vague symptoms with a published guardrail (37%); monitor time per step by county; pilot in one county first. Say which are tested in simulation (1-3) and which rest on cited evidence (4-5). | Recommendation card | Actionability |
| 10 | **What is real, what is synthetic, what comes next** | All patients synthetic; 131 parameters, 18 marked assumption, rest sourced. Held-out reporting; 2.3 point selection optimism in the Norwegian run. Next: real county data and a pilot. Decision model: beats a dot-product baseline on a set-relative task (84.5% against 78.3%), but not yet in the demo loop, and the half-compute claim did not hold. Team, ask. | Screen 4 sources list | Data quality, Clarity |

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

- Decision model against the dot-product baseline at one choice point: 84.5% against 78.3% (parameter-matched wider baseline 79.0%); on the control task without the set-relative rule the gap is 2.5 points, so part of the gain is capacity. Second question costs 76-91% of the first at our sizes, not half.
- Parameter table with sources (screen 4).
- Capacity probe table: | Resource | Slots a day now | Utilisation | Change in share within 90 d with one more slot |
|---|---|---|---|
| pet scanner | 1 | 79% | +9.7 pp |
| bronchoscopy | 1 | 82% | +3.6 pp |
| ttnb slot | 1 | 69% | +1.5 pp |
| ct scanner | 3 | 84% | +1.1 pp |
| nurse appt | 35 | 89% | +0.6 pp |
| treatment slot | 2 | 36% | +0.4 pp |
| xray | 24 | 84% | +0.2 pp |
| clinic | 7 | 77% | +0.0 pp |
| gp appt | 74 | 89% | -0.4 pp |
- Limits: crowd-out (Swedish interviews), real shortages (Cooke 2022), single region.

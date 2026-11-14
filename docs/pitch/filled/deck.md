# Deck: final content, 10 slides

> **Safe to claim / do not claim** (numbers from `numbers_sheet.md`; update there first)
>
> **Safe to claim**
> - All patients are synthetic. The Finnish county is a scenario, not calibrated to Finnish capacity data.
> - Norway, fitted: the observed pathway, 40% within 42 days (published 40%). This is the only thing fitted.
> - Norway, predicted and not fitted: the authors' reordered pathway is 80% at our best fit (published 80%). Across all 184 settings that fit the observed data it ranges from 62% to 86%, typically about 75%; 64% of the settings fall inside the published interval (72-87%).
> - The ranking holds in all 184 settings: reordering beats a faster scanner beats today.
> - We over-predict the faster scanner alone: 60% at the best fit against the published 48% (range 50 to 74%).
> - The search found the authors' three changes plus a fourth (needs a clinical check): 88% with the faster scanner, 67% with no new equipment. It chose from a menu of about 69 single changes that contained the authors' changes.
> - Finland, synthetic: two reorders, no new equipment, 18% to 33% treated within 90 days (provisional target) on two held-out cohorts; the gain is 9 to 19 points across 12 cohorts.
> - The primary-care loop is a mechanism with placeholder decision tables. The patient engine makes synthetic cards; the catalogue is a draft no clinician has read.
>
> **Do not claim**
> - "We predicted 80% exactly", "it matches the paper", or "78 to 86%" (the older, narrower grid).
> - The optimiser "discovered the authors' answer from nothing" (its menu contained their changes), or that the fourth change is safe.
> - 61% as a Finnish result. It is conditional on assumed urgent booking times.
> - Any Finnish number as an estimate for real Finnish patients or counties, or any lives saved.
> - Any number from the primary-care loop as a finding (it fails 7 of 8 consistency checks against the calibrated chain).
> - That a model trained on synthetic cards is validated on real patients, or that the team's decision model (JEV) produced the headline numbers (placeholder tables and rules did).
> - That the equity gap closes.
> - How the optimiser's Norwegian changes hold on all 184 settings or without the fourth change. That check is pending (`numbers_sheet.md`, section P).

Numbers in double square brackets come from `demo/data/demo_bundle.json` via `fill_numbers.py`; read the filled copy in `filled/deck.md`. Weights: Actionability 30, Insight 25, Data quality and transparency 20, Execution 15, Clarity 10. Plain words on slides (no "node", "embedding"). "Synthetic data" label on every results slide. Screens refer to `demo/index.html` (keys 1-6).

**Two team decisions change slide 1 and 6.** D20: the Finnish headline uses a provisional 90-day target; the alternative is to show the median days (from 102 to 94) as the headline and the share only as a second number. D17: the Norwegian headline is the search with the faster scanner (the authors' premise); the alternative is to lead with the no-new-equipment result. Both versions are written below.

| # | Slide title (one message) | Numbers and content | Visual (dashboard screen) | Criterion |
|---|---|---|---|---|
| 1 | **In our synthetic Finnish county, two reorders get 33% treated within 90 days, from 18%** | Median 102 to 94 days. No new equipment. Missed cancers 27.5 to 27.5 per cohort. Held-out patients (two cohorts; across 12 cohorts the gain is 9 to 19 points, positive in every one). A larger effect (61%) exists only if urgent booking leads that we assumed hold; shown as a conditional finding, not the headline. Alt (D20): lead with "8 days faster" and show the share small. | Screen 1, headline number in large type | Clarity, Actionability |
| 2 | **Finland waits longest in the Nordics at the first steps, and survives least** | Sourced, not ours: lung cancer five-year survival in men 17% against 27-30% (IHE dashboard); first appointment about 14 days against 2-7; 40-60% see a nurse first; under 10% of primary-care units can perform CT. Strategy Goal 3 indicator "treatment within target times" is what we measure. | Static slide with cited numbers | Insight |
| 3 | **Time is lost mostly in waiting, and mostly before the specialist** | In the synthetic baseline waiting (booking time and queues) is 87% of the 91 + 14 days; per-step waits are calibrated to published Finnish waits, not an emergent queue result. By stage: detection 30 d, referral 17, diagnosis 23, treatment start 21. Largest single waits: waiting for treatment slot (16 d), re-presents to gp (15 d), specialist visit (13 d). | Screen 2, four stage bars, waiting vs service | Insight |
| 4 | **Order matters more than capacity: in a real Norwegian study (a model estimate) and in our simulation** | Stokstad: 40% observed, 48% with a faster PET-CT (not significant), 80% reordered (the last is the authors' model estimate, not an observed result). In our reproduction reordering beats the faster scanner in all 184 settings that fit the observed data. Ours: extra CT and PET capacity alone 31%, the same capacity plus hand-written reordering 54%, the optimiser's reorders with no new capacity 33% (baseline 18%). One more slot at the busiest scanner: +9.7 points; next best +3.6. | Screen 4, bar rows; capacity probe table | Insight, Data quality |
| 5 | **How it works: propose, rerun, compare** | Synthetic patients, a flowchart of steps, a run. The optimiser proposes from what steps revealed, never the hidden truth. Same patients rerun to accept. Held-out patients to report. A clinician approves. In real life the rerun is a pilot. | One diagram | Execution, Clarity |
| 6 | **We rebuilt a real Norwegian pathway. The ranking holds; the exact size is uncertain; one prediction misses** | Fitted on the observed pathway only: 40% (published 40%). Predicted, not fitted: authors' pathway 80% at the best fit (published 80%), but the best fit is one point in a band: across all 184 settings that fit the observed data it is 62 to 86%, typically about 75%, and 64% of settings fall inside the published interval (72-87%). Why a band: the two fitted numbers act as one constraint, so the data cannot pin down the five unreported inputs. Reordering beats faster scanner beats today in all 184 settings. Faster PET only: 60% at the best fit against published 48% (band 50 to 74%): we over-predict. The best fit also carries the calibrated practice of ordering PET-CT at triage; with PET-CT ordered only at the first visit it would be 66%. Search over a menu of about 69 single changes that contained each of the authors' changes (it was not told which): 88% with the faster scanner (authors' three changes plus one), 67% with no new equipment, both at the best-fit setting; checks on the other settings are pending. The fourth change plans sampling at referral triage, before a specialist visit; needs a clinical check. Alt (D17): lead with 67%. | Screen 5, validation bars with published markers | Data quality, Execution |
| 7 | **The change for Finland** | Before/after flowchart. Two steps: Reserve the treatment slot when the case is sent to the tumour board, not after the board has met; Book the specialist visit as soon as the referral arrives, not after it has been handled. Held-out: within 90 d 18% to 33%, tests per patient 0.41 to 0.41, non-cancer patients leave the pathway in 16.8 to 16.8 days (median). Hand-written "order together" reaches 54% but needs 3 PET-CT slots. Conditional (assumed urgent booking leads): 18% / 44% / 61% at 0 / 50 / 100% of the lead reduction. | Screen 5, flowchart before/after (screen 1 for the conditional rows) | Actionability |
| 8 | **Who waits longest, and does the change reach them?** | Vague-symptom patients 13% to 26%; alarm-symptom 27% to 50% within target. Under our assumptions both gain. Gap in points widens (13.6 to 24.6); gap in median days narrows (11.2 to 9.9). The group gap is built from our assumption. | Screen 6, two bars per group | Insight, Data quality |
| 9 | **A recommendation in five actions** | Reserve the treatment slot at tumour-board referral and book the specialist visit on referral arrival (33%, the headline change); direct CT paired with it (alone: 20%); a priority track for vague symptoms with a published guardrail (hand-written, 37%); monitor time per step and booking leads by county; pilot in one county first. Say which are tested in simulation (1-3) and which rest on cited evidence (4-5). | Recommendation card | Actionability |
| 10 | **What is real, what is synthetic, what comes next** | All patients synthetic. Finnish scenario: 49 input blocks (`docs/ledger.md`), 9 sourced and 40 assumptions (every capacity and booking lead); Norwegian scenario: 25 input blocks, 3 assumptions. The parameter table (131 rows) is evidence and calibration targets, most are not simulator inputs. Held-out reporting; 1.7 point selection optimism in the Norwegian run. Next: real county data and a pilot. Patient engine: 500 template-written cards and 35 model-written cards so far (all synthetic; catalogue is a draft, not read by a clinician; no claim of validity on real patients). Primary-care loop: a mechanism with placeholder decision tables, not a result. Team's decision model (JEV): connected through an adapter; the headline runs use placeholder tables and rules. Our own small decision-model benchmark: beats a parameter-matched dot-product baseline on a set-relative task (84.5% against 79.0%; 78.3% for the smaller d=32 model); in the simulator loop it matched the hand-written rule and showed that per-patient optimisation overloads a shared queue without queue state; the half-compute claim did not hold. Team, ask. | Screen 6 sources list | Data quality, Clarity |

## Speaker notes, one line each

1. Number, then the change, then stop. Say "in our synthetic county".
2. These are reported figures from the dashboard, not ours.
3. Say that most of the time is waiting, and that primary care is the biggest single stage in our model.
4. The 80% is a model estimate in the paper; the lesson is direction (ranking), not the exact size. Our capacity-only control is the same extra capacity with the old order. Add the PET-at-triage caveat when asked about 80%.
5. Do not name the architecture. A judge can ask; see qa.md.
6. Say the band, not just the best fit: "80 at our best fit, 62 to 86 across every setting that fits the data, about 75 typically." Say the miss: we over-predict the faster-scanner-only result (60 against 48). Say that the ranking holds in every setting. Never say "exactly".
7. Held-out numbers, not training numbers. Say "two reorders, no new equipment"; if asked about 61%, explain it is conditional on assumed urgent booking times.
8. Report both gap measures, as what the simulation shows under its assumptions; do not say the gap closes.
9. Actions 4 and 5 are not tested by us.
10. Synthetic, stated plainly, with a path to real data. If asked about the patient cards: "500 template-written and a few dozen model-written, all synthetic; we do not claim they behave like real patients."

## Backup slides

- Decision model against the dot-product baseline at one choice point: 84.5% against 79.0% (parameter-matched wider baseline; the smaller d=32 baseline scores 78.3%); on the control task without the set-relative rule the gap is 2.5 points, so part of the gain is capacity. Second question costs 76-91% of the first at our sizes, not half.
- Parameter table with sources (screen 6).
- Conditional urgent-booking finding (depends on assumed leads, not a recommendation):

| Share of the assumed urgent-booking lead reduction that holds | Treated within 90 d | Median days | Missed cancers per cohort |
|---|---|---|---|
| 0% | 18% | 102 | 27.5 |
| 50% | 44% | 90 | 27.5 |
| 100% | 61% | 80 | 27.5 |

- Capacity-controlled comparison:

| Option (same patients) | Treated within 90 d | Median days |
|---|---|---|
| Baseline | 18% | 102 |
| Large capacity increase, same order (CT 8, PET-CT 3) | 31% | 97 |
| Same extra capacity plus ordering tests together (hand-written) | 54% | 83 |
| Suggested change, no new capacity | 33% | 94 |

- Capacity probe table: | Resource | Slots a day now | Utilisation | Change in share within 90 d with one more slot |
|---|---|---|---|
| PET-CT scanner | 1 | 79% | +9.7 pp |
| Bronchoscopy | 1 | 82% | +3.6 pp |
| Needle biopsy slots | 1 | 69% | +1.5 pp |
| CT scanner | 3 | 84% | +1.1 pp |
| Nurse appointments | 35 | 89% | +0.6 pp |
| Treatment slots | 2 | 36% | +0.4 pp |
| Chest X-ray | 24 | 84% | +0.2 pp |
| Specialist clinic | 7 | 77% | +0.0 pp |
| GP appointments | 74 | 89% | -0.4 pp |
- Limits: crowd-out (Swedish interviews), real shortages (Cooke 2022), single region.

# Deck: final content, 10 slides

> **Safe to claim / do not claim** (numbers from `numbers_sheet.md`; update there first)
>
> **Safe to claim**
> - All patients are synthetic. The Finnish county is a scenario, not calibrated to Finnish capacity data.
> - Norway, fitted: the observed pathway, 40% within 42 days (published 40%). This is the only thing fitted.
> - Norway, predicted and not fitted: the authors' reordered pathway is 80% at our best fit (published 80%). Across all 184 settings that fit the observed data it ranges from 62% to 86%, typically about 75%; 64% of the settings fall inside the published interval (72-87%).
> - The ranking holds in all 184 settings: reordering beats a faster scanner beats today.
> - We over-predict the faster scanner alone: 60% at the best fit against the published 48% (range 50 to 74%).
> - Optimiser, a plausibility check (D62, D68): Starting from today's pathway, with no new equipment and without being told the answer, the optimiser arrived at the authors' three timing changes plus a fourth that needs clinical review. It did not improve on the authors' redesign. With no new equipment: 67% at the best fit; 48 to 77% across all 184 settings (median 65%), against 36 to 44% for today's pathway. The authors' 80% (72-87%) for their reordered pathway includes the shorter PET-CT wait; our optimiser's pathway assumes no new equipment, so the two are not a like-for-like pair. It chose from a menu of about 69 single changes that contained the authors' changes.
> - Finland, synthetic: two reorders, no new equipment, 18% to 33% treated within 90 days (provisional target) on two held-out cohorts; the gain is 9 to 19 points across 12 cohorts.
> - The primary-care loop is a mechanism with placeholder decision tables. The patient engine makes synthetic cards; the catalogue is a draft no clinician has read.
>
> **Do not claim**
> - "We predicted 80% exactly", "it matches the paper", or "78 to 86%" (the older, narrower grid).
> - That the optimiser "beat" or "improved on" the authors, or "discovered their answer from nothing" (its menu contained their changes); that the fourth change is safe. Do not state or show any optimiser result combined with the faster PET-CT scanner (D68): the authors reported the scanner and the reordering separately, and so do we.
> - "Reordering with no new equipment beats buying the scanner" without the count: Without new equipment it beats today's pathway in 184 of 184 settings but beats the faster scanner alone in only 128 of 184. Never quote 67% without the range.
> - 61% as a Finnish result. It is conditional on assumed urgent booking times.
> - Any Finnish number as an estimate for real Finnish patients or counties, or any lives saved.
> - Any number from the primary-care loop as a Finnish estimate. The loop uses placeholder decision tables and every behaviour number is an assumption; it reproduces the calibrated chain at the edge of the tolerances: 8 of 8 checks on the seeds it was tuned on, 6 of 8 on fresh seeds, 7 of 8 pooled over eight seeds. Do not use the old figures (37 days, one cancer in six, 84 days, 840 EUR).
> - That a model trained on synthetic cards is validated on real patients, or that the team's decision model (JEV) produced the headline numbers (placeholder tables and rules did).
> - That the equity gap closes (in points it widens, 13.6 to 24.6), or that faster care saves lives in lung cancer.
> - That the model-written cards are "leak-free" or clinically realistic. The review found report wording in the old result prompt that gives away false alarms; the new result prompt (g2@2: the engine sets every value, the language model writes report text from the reported values only) has not yet been run on the real model; the 35 model-written cards in the repository use the old prompt g2@1, and their report text is rebuilt from values before any decider sees it. Patient backgrounds come from a population model whose numbers are mostly assumptions.
> - That the paper's text gives 80% exactly: A stricter reading of the paper's text (PET-CT at the first visit, treatment not waiting for sampling) gives a median of 79% over the 184 settings (64 to 90%; 139 of 184 inside the published 72-87%) and 77% at the best fit. Caveats: we read summaries of the paper, not its figures, and the observed pathway was not recalibrated under that reading; the shipped scenario is unchanged and this is an open decision for the human lead.

Numbers in double square brackets come from `demo/data/demo_bundle.json` via `fill_numbers.py`; read the filled copy in `filled/deck.md`. Weights: Actionability 30, Insight 25, Data quality and transparency 20, Execution 15, Clarity 10. Plain words on slides (no "node", "embedding"). "Synthetic data" label on every results slide. Screens refer to `demo/index.html` (keys 1-6).

**Two team decisions change slide 1 and 6.** D20: the Finnish headline uses a provisional 90-day target; the alternative is to show the median days (from 102 to 94) as the headline and the share only as a second number. D17 is closed by D62 and D68: the Norwegian headline is the search from today's pathway with no new equipment, with its range, framed as a plausibility check.

| # | Slide title (one message) | Numbers and content | Visual (dashboard screen) | Criterion |
|---|---|---|---|---|
| 1 | **In our synthetic Finnish county, two reorders get 33% treated within 90 days, from 18%** | Median 102 to 94 days. No new equipment. Missed cancers 27.5 to 27.5 per cohort. Held-out patients (two cohorts; across 12 cohorts the gain is 9 to 19 points, positive in every one). A larger effect (61%) exists only if urgent booking leads that we assumed hold; shown as a conditional finding, not the headline. Alt (D20): lead with "8 days faster" and show the share small. | Screen 1, headline number in large type | Clarity, Actionability |
| 2 | **Finland waits longest in the Nordics at the first steps, and has the weakest lung cancer survival** | Sourced, not ours: lung cancer five-year survival in men 17% against 27-30% (IHE dashboard); first appointment about 14 days against 2-7; 40-60% see a nurse first; under 10% of primary-care units can perform CT. Survival is context for the gap; we do not claim that shorter waits improve survival in lung cancer (lung-surgery delay estimate not significant, `numbers_sheet.md` G1). Strategy Goal 3 indicator "treatment within target times" is what we measure. | Static slide with cited numbers | Insight |
| 3 | **In our model, time is spent mostly waiting, and mostly before the specialist** | In the synthetic baseline waiting (booking time and queues) is 87% of the 91 + 14 days. Where that comes from: the share is computed from the simulated patients' paths; 46% of the waiting days are set from published figures (GP appointment 17 d, specialist visit 13 d, treatment booking 10 d, referral handling 3 d; the 37-day treatment figure covers all cancers, not lung cancer), 54% are our assumption or placeholder (PET-CT 9 d, GP appointment: extra wait 9 d, chest CT 6 d, treatment booking: extra wait 6 d, bronchoscopy 6 d, tumour board 5 d, needle biopsy 4 d, paperwork 3 d, chest X-ray 2 d, nurse appointment 1 d). This is a consequence of the waits we put in, not a measurement from patient data; it shows where the modelled time sits, and it is only as good as those inputs. By stage: detection 30 d, referral 17, diagnosis 23, treatment start 21. Largest single waits: waiting for treatment slot (16 d), re-presents to gp (15 d), specialist visit (13 d). | Screen 2, four stage bars, waiting vs service | Insight |
| 4 | **Order matters more than capacity: in a real Norwegian study (a model estimate) and in our simulation** | Stokstad: 40% observed, 48% with a faster PET-CT (not significant), 80% reordered (the last is the authors' model estimate, not an observed result). In our reproduction reordering beats the faster scanner in all 184 settings that fit the observed data. Ours: extra CT and PET capacity alone 31%, the same capacity plus hand-written reordering 54%, the optimiser's reorders with no new capacity 33% (baseline 18%). One more slot at the busiest scanner: +9.7 points; next best +3.6. | Screen 4, bar rows; capacity probe table | Insight, Data quality |
| 5 | **How it works: propose, rerun, compare** | Synthetic patients, a flowchart of steps, a run. The optimiser proposes from what steps revealed, never the hidden truth. Same patients rerun to accept. Held-out patients to report. A clinician approves. In real life the rerun is a pilot. | One diagram | Execution, Clarity |
| 6 | **We rebuilt a real Norwegian pathway. The ranking holds; the exact size is uncertain; one prediction misses** | Fitted on the observed pathway only: 40% (published 40%). Predicted, not fitted: authors' pathway 80% at the best fit (published 80%), but the best fit is one point in a band: across all 184 settings that fit the observed data it is 62 to 86%, typically about 75%, and 64% of settings fall inside the published interval (72-87%). Why a band: the two fitted numbers act as one constraint, so the data cannot pin down the five unreported inputs. Reordering beats faster scanner beats today in all 184 settings. Faster PET only: 60% at the best fit against published 48% (band 50 to 74%): we over-predict. The best fit also carries the calibrated practice of ordering PET-CT at triage; with PET-CT ordered only at the first visit it would be 66%. Search over a menu of about 69 single changes that contained each of the authors' changes (it was not told which). A plausibility check, not a forecast (D62, D68): Starting from today's pathway, with no new equipment and without being told the answer, the optimiser arrived at the authors' three timing changes plus a fourth that needs clinical review. It did not improve on the authors' redesign. With no new equipment: 67% at the best fit; 48 to 77% across all 184 settings (median 65%), against 36 to 44% for today's pathway. The authors' 80% (72-87%) for their reordered pathway includes the shorter PET-CT wait; our optimiser's pathway assumes no new equipment, so the two are not a like-for-like pair. Without new equipment it beats today's pathway in 184 of 184 settings but beats the faster scanner alone in only 128 of 184. Without the fourth change the optimiser still gives 65% at the best fit; the fourth change is worth 2 to 3 points and overlaps with "tumour board before sampling". It was not in the paper and needs a clinical check. Sensitivity sentence, only with its caveats: A stricter reading of the paper's text (PET-CT at the first visit, treatment not waiting for sampling) gives a median of 79% over the 184 settings (64 to 90%; 139 of 184 inside the published 72-87%) and 77% at the best fit. Caveats: we read summaries of the paper, not its figures, and the observed pathway was not recalibrated under that reading; the shipped scenario is unchanged and this is an open decision for the human lead. | Screen 5, validation bars with published markers | Data quality, Execution |
| 7 | **The change for Finland** | Before/after flowchart. Two steps: Reserve the treatment slot when the case is sent to the tumour board, not after the board has met; Book the specialist visit as soon as the referral arrives, not after it has been handled. Held-out: within 90 d 18% to 33%, tests per patient 0.41 to 0.41, non-cancer patients leave the pathway in 16.8 to 16.8 days (median). Hand-written "order together" reaches 54% but needs 3 PET-CT slots. Conditional (assumed urgent booking leads): 18% / 44% / 61% at 0 / 50 / 100% of the lead reduction. | Screen 5, flowchart before/after (screen 1 for the conditional rows) | Actionability |
| 8 | **Who waits longest, and does the change reach them?** | Vague-symptom patients 13% to 26%; alarm-symptom 27% to 50% within target. Under our assumptions both gain. Gap in points widens (13.6 to 24.6); gap in median days narrows (11.2 to 9.9). The group gap is built from our assumption. | Screen 6, two bars per group | Insight, Data quality |
| 9 | **A recommendation in five actions** | Reserve the treatment slot at tumour-board referral and book the specialist visit on referral arrival (33%, the headline change); direct CT paired with it (alone: 20%); a priority track for vague symptoms with a published guardrail (hand-written, 37%); monitor time per step and booking leads by county; pilot in one county first. Say which are tested in simulation (1-3) and which rest on cited evidence (4-5). | Recommendation card | Actionability |
| 10 | **What is real, what is synthetic, what comes next** | All patients synthetic. Finnish scenario: 49 input blocks (`docs/ledger.md`), 9 sourced and 40 assumptions (every capacity and booking lead); Norwegian scenario: 25 input blocks, 3 assumptions. The parameter table (131 rows) is evidence and calibration targets, most are not simulator inputs. Held-out reporting; -0.6 point selection optimism in the Norwegian run. Next: real county data and a pilot. Patient engine: 500 template-written cards and 35 model-written cards so far (not yet run on the real model for the new result prompt; all synthetic; catalogue is a draft, not read by a clinician; no claim of validity on real patients). Primary-care loop: placeholder decision tables, every behaviour number an assumption; it reproduces the calibrated chain at the edge of the tolerances: 8 of 8 checks on the seeds it was tuned on, 6 of 8 on fresh seeds, 7 of 8 pooled over eight seeds; not a Finnish estimate. Team's decision model (JEV): connected through an adapter; the headline runs use placeholder tables and rules. Our own small decision-model benchmark: beats a parameter-matched dot-product baseline on a set-relative task (84.5% against 79.0%; 78.3% for the smaller d=32 model); in the simulator loop it matched the hand-written rule and showed that per-patient optimisation overloads a shared queue without queue state; the half-compute claim did not hold. Team, ask. | Screen 6 sources list | Data quality, Clarity |

## Speaker notes, one line each

1. Number, then the change, then stop. Say "in our synthetic county".
2. These are reported figures from the dashboard, not ours.
3. Say "in our model": most of the time is waiting, and primary care is the biggest single stage. Say where it comes from: the waits are inputs (part set from published figures, part our assumptions), so this shows where the modelled time sits; it is not a measurement from patient data.
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

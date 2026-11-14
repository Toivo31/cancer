# Demo path: presenter's script

Start page: `demo/start.html` (opens from disk, no server). It shows the story in six steps, each with one result read from the data behind its screen. **Say the number that is on the screen, not one from memory**: the encounter-loop numbers are still being tuned, so they can differ from earlier notes. A number shown as "pending" is not there yet; say so.

## Before you present (2 minutes)

1. Open `demo/start.html`. Check that no row says "pending" (at the last build none did; the Norway range and the tuned encounter report are both found).
2. Open each screen once in its own tab so it is warm: `demo/encounter.html`, `demo/flow.html?s=finland&compare`, `demo/index.html#stokstad/5`.
3. If the model should be live: `BIRCH_API_KEY_FILE=... python -m decision_api.server` in a terminal, then `python -m jev.walk --pick cancer` ready in a second one. Warm calls take a few seconds, a cold start minutes: make one call before you go on stage.
4. If any bundle was regenerated, reload the start page. One command rebuilds all of them: `python demo/export_all.py` (about 1 to 2 minutes; `python demo/export_all.py encounter` for one; run times are in `demo/README.md`). The encounter bundle is the one that changes when the encounter loop is retuned.
5. Every page has a "Demo start" link (top left, or the title on the dashboard) back to the start page.

Wording to hold to everywhere: synthetic data only; primary-care behaviour is assumed; the Norway check supports the ranking of reorderings, not their exact size; decision-model scores are relative candidate scores, not probabilities.

## 3-minute version (judges walk past)

| Time | Click | Say |
|---|---|---|
| 0:00 | Start page, row 1 | "Finland waits longest in the Nordics at the first steps of lung cancer care. In our synthetic county only the share on the screen is treated inside the target. These patients are simulated; the target is provisional." |
| 0:25 | "The encounter loop" (row 2). Press Space to play. Click an example, "Antibiotics ... referred ..." | "Each dot is a patient moving through nurse, GP, tests and home. Here the clinician saw a cough, gave antibiotics, and the cancer was found much later. This is the record the clinician saw, not the truth." |
| 1:05 | Back, "Finland: today vs suggested" (row 3). Compare is already on | "Same patients, same steps, two reorders, no new capacity. The share treated in time goes from the first number to the second on held-out patients, and missed cancers do not rise. This is a simulated county, not measured Finnish data." |
| 1:45 | Back, row 4 (read it on the start page; "Norway check on screen" opens the dashboard chart) | "We rebuilt a published Norwegian pathway and fitted only today's order. It predicted the authors' reordered pathway, the published figure and ours side by side, but that is the best fit: over all settings that fit the observed data the answer is a wider range, with a typical value (read both off the screen). It over-states the scanner-only case, and we show that. Trust the ranking, not the exact size. On the same new scanner our optimiser's pathway is ahead of the authors' in the simulator; with no new equipment it gives a lower number with no published counterpart." (Read each number off the screen; do not quote from memory.) |
| 2:25 | Back, row 5 (and `jev.walk` if live) | "At every clinician decision the team's model scores the options from the visible record; a person decides. The scores are relative, not probabilities." |
| 2:50 | Row 6 | "Everything is synthetic; the ledger counts what is sourced and what is assumption." |

## 10-minute version

1. **The brief and the gap (1 min).** Start page, row 1, then "Where the time goes" (`index.html#finland_lung/2`). Time is lost mostly in waiting, mostly booking time calibrated to published waits, and less in capacity queues. Say "booking time and queues", not "queues". The Finnish figure is simulated, not measured.
2. **Primary care (2.5 min).** `encounter.html`. Play the flow. Switch to "Time at step". Open the first two examples; for one, click a record line to expand it. Show the two layers: the blue mechanical log and the coral assessments. Toggle "Reveal truth (teaching view)" once, on the cancer that was treated as an infection, then turn it off. Point at the results table at the bottom (read its numbers aloud as shown; mention the tuning note if the start page says "pending").
3. **Reordering (2 min).** `flow.html?s=finland&compare`. Show the per-step change, then Queues. State the guardrails: missed cancers, other patients' waits. Say which model this result is from (the row shows the scenario name: the hospital-chain model of the Finnish county). If asked whether the optimiser ran on the encounter loop: not yet; say that plainly.
4. **Trust (2 min).** Start page row 4 first (it carries the whole Norway picture; open the "Our optimiser against the authors' pathway" fold), then `flow.html?s=norway&compare` (opens with the authors' pathway on the left and our suggested change with the same faster scanner on the right: the fair pair; the panel "Check against the published study" is the first card on the right), then `index.html#stokstad/5` for the bar chart and its "How to read the bars" paragraph. Say in this order: (a) the model was fitted only on today's order, and the authors' reordered pathway came out at the published figure; (b) that is the best fit, and the range over every setting that fits the observed data is wider; (c) the model over-predicts the faster scanner alone, so trust the ranking, not the size; (d) the authors' figure assumes a new, faster scanner, so the fair comparison with our optimiser is on the same scanner; with no new equipment our pathway gives a lower number that has no published counterpart; (e) the optimiser found the authors' three changes and a fourth, planning tissue sampling at referral triage, which needs a clinical check, and without it the pathway still gives most of the lead (the fold gives the number). Then open `docs/validation.md` for the disclosure that the reordered result is not fully independent of the fitted triage practice.
5. **Decision model (1.5 min).** Run `python -m jev.walk --pick cancer`: at the decision, show the record so far, the options with the model's scores, accept the proposal or type another; end on the record. Then open `http://127.0.0.1:8771/decision` for the panel. Always say whether the answer is live or a saved example; the panel labels it.
6. **Honesty and next (1 min).** Row 6 numbers, `docs/ledger.md`. Then the "Synthetic patients" card at the bottom of the start page: one model-written patient as the decider sees it (complaint in the patient's words, the history, one test report) next to the template wording of the same facts; open the red "Hidden side" fold only to show what the decision model never sees. Read the counts from the card (they come from the library manifests). Close on what is not done: model-written patient libraries are not the headline source; the optimiser has not run on the encounter loop; the care catalogue is a draft until a clinician reads it.

## If something is down

| Symptom | Do |
|---|---|
| Model GPU cold or key missing (`jev.walk` stops with "Model may still be starting") | Retry once (answers received are cached). Otherwise `python -m jev.walk --pick cancer --jev mock` and say it is a mock, or open the saved examples in the panel at `/decision` and say "saved example". Never present a mock or saved answer as live. |
| `decision_api.server` will not start | Skip row 5's live part, show `decision_api/README.md` and the walk against `--jev table` (placeholder tables, labelled). |
| Eemeli's live demo blank | It needs its server: `python -m note_reader.server --port 8770`, then open `http://127.0.0.1:8770/`. From disk it stays empty. Without it, skip it; nothing else depends on it. |
| A row on the start page says "pending" | Rerun the exporter named under it (`export_flow.py`, `export_encounter.py`, `export_start.py`) and reload; if it cannot be fixed, say the number is pending and move on. |
| A screen shows a number that differs from an earlier note or slide | The screen is right for the run it shows (its footer or the start page gives the time of the run). Say which run. |
| No browser tab opens a file | Serve the folder: `python -m http.server -d demo 8000`, open `http://localhost:8000/start.html`. |

## Questions to expect

- *Is this real patient data?* No. Synthetic patients; inputs sourced or marked assumption (row 6).
- *Your optimiser got 88 and the authors 80. Is yours better?* On the same new scanner, in our simulator, yes, by the margin on the screen, and ahead in every one of the fitting settings of the original grid (the fold on the start page gives the count). Most of that comes from how the optimiser orders the same steps, and a fourth change (tissue sampling planned at referral triage) needs a clinical check. The simulator over-predicts scanner-only gains, so read it as a ranking, not a forecast.
- *Why is your no-new-equipment number lower than the authors' 80?* The authors' 80 needs the new scanner. Ours without it is the lower number on the screen; there is no published figure to compare it with.
- *Did the model-written patients drive these results?* No. The results on these pages come from the simulator runs shown; the Synthetic patients card shows what a model-written patient looks like and how many exist.
- *Does the Norway check prove the Finnish numbers?* No. It supports the engine's reordering logic on a hospital pathway; it does not validate primary care.
- *What do the model's scores mean?* Relative candidate scores for the offered options; not disease probabilities, test accuracy or times.

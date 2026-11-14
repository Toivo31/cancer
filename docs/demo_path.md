# Demo path: presenter's script

Start page: `demo/start.html` (opens from disk, no server). It shows the story in six steps, each with one result read from the data behind its screen. **Say the number that is on the screen, not one from memory**: the encounter-loop numbers are still being tuned, so they can differ from earlier notes. A number shown as "pending" is not there yet; say so.

## Before you present (2 minutes)

1. Open `demo/start.html`. Check that no row says "pending" except the ones you expect (tuned encounter report, wider-grid robustness range).
2. Open each screen once in its own tab so it is warm: `demo/encounter.html`, `demo/flow.html?s=finland&compare`, `demo/index.html#stokstad/5`.
3. If the model should be live: `BIRCH_API_KEY_FILE=... python -m decision_api.server` in a terminal, then `python -m jev.walk --pick cancer` ready in a second one. Warm calls take a few seconds, a cold start minutes: make one call before you go on stage.
4. If any bundle was regenerated (`python demo/export_encounter.py`, `python demo/export_flow.py`, `python demo/export_start.py`), reload the start page.

Wording to hold to everywhere: synthetic data only; primary-care behaviour is assumed; the Norway check supports the ranking of reorderings, not their exact size; decision-model scores are relative candidate scores, not probabilities.

## 3-minute version (judges walk past)

| Time | Click | Say |
|---|---|---|
| 0:00 | Start page, row 1 | "Finland waits longest in the Nordics at the first steps of lung cancer care. In our synthetic county only the share on the screen is treated inside the target. These patients are simulated; the target is provisional." |
| 0:25 | "The encounter loop" (row 2). Press Space to play. Click an example, "Antibiotics ... referred ..." | "Each dot is a patient moving through nurse, GP, tests and home. Here the clinician saw a cough, gave antibiotics, and the cancer was found much later. This is the record the clinician saw, not the truth." |
| 1:05 | Back, "Finland: today vs suggested" (row 3). Compare is already on | "Same patients, same steps, two reorders, no new capacity. The share treated in time goes from the first number to the second on held-out patients, and missed cancers do not rise." |
| 1:45 | Back, "Norway check on screen" (row 4) | "We rebuilt a published Norwegian pathway and fitted only today's order. It predicted the authors' reordered pathway without being told it. It over-states the scanner-only case, and we show that. Trust the ranking, not the exact size." |
| 2:25 | Back, row 5 (and `jev.walk` if live) | "At every clinician decision the team's model scores the options from the visible record; a person decides. The scores are relative, not probabilities." |
| 2:50 | Row 6 | "Everything is synthetic; the ledger counts what is sourced and what is assumption." |

## 10-minute version

1. **The brief and the gap (1 min).** Start page, row 1, then "Where the time goes" (`index.html#finland_lung/2`). Time is lost mostly in waiting, mostly booking time calibrated to published waits, and less in capacity queues. Say "booking time and queues", not "queues". The Finnish figure is simulated, not measured.
2. **Primary care (2.5 min).** `encounter.html`. Play the flow. Switch to "Time at step". Open the first two examples; for one, click a record line to expand it. Show the two layers: the blue mechanical log and the coral assessments. Toggle "Reveal truth (teaching view)" once, on the cancer that was treated as an infection, then turn it off. Point at the results table at the bottom (read its numbers aloud as shown; mention the tuning note if the start page says "pending").
3. **Reordering (2 min).** `flow.html?s=finland&compare`. Show the per-step change, then Queues. State the guardrails: missed cancers, other patients' waits. Say which model this result is from (the row shows the scenario name: the hospital-chain model of the Finnish county). If asked whether the optimiser ran on the encounter loop: not yet; say that plainly.
4. **Trust (2 min).** `index.html#stokstad/5`, then open `docs/validation.md`. Published 40, 48 and 80 against ours. Tell the over-prediction yourself, then the disclosure that the reordered result is not fully independent of the fitted triage practice, then the wider-grid range if the start page shows it.
5. **Decision model (1.5 min).** Run `python -m jev.walk --pick cancer`: at the decision, show the record so far, the options with the model's scores, accept the proposal or type another; end on the record. Then open `http://127.0.0.1:8771/decision` for the panel. Always say whether the answer is live or a saved example; the panel labels it.
6. **Honesty and next (1 min).** Row 6 numbers, `docs/ledger.md`. Close on what is not done: model-written patient libraries are not the headline source; the optimiser has not run on the encounter loop; the care catalogue is a draft until a clinician reads it.

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
- *Does the Norway check prove the Finnish numbers?* No. It supports the engine's reordering logic on a hospital pathway; it does not validate primary care.
- *What do the model's scores mean?* Relative candidate scores for the offered options; not disease probabilities, test accuracy or times.

# Demo path: presenter's script

Start page: `demo/start.html`, the **Overview** (opens from disk, no server). Five pages share one nav at the top:
Overview · Simulator · Patients · Evidence · Decision model. Two more are reached from them: `research.html` (Research
behind the numbers, from any basis tag) and `encounter.html` (the primary-care loop, from the Simulator's pathway
dropdown and from Patients). Every page reads its numbers from the data bundles when it opens. **Say the number that is on
the screen, not one from memory.** A number shown as "pending" is not there yet; say so.

Each number carries a small tag: PUBLISHED RESEARCH (solid black), OUR SIMULATION (mustard), OUR ASSUMPTION (dashed).
Clicking a tag opens that claim on the research page with its source and strength.

## Before you present (2 minutes)

1. Open `demo/start.html`. Check that nothing says "pending".
2. Open in their own tabs so they are warm: `demo/flow.html?s=finland`, `demo/patients.html`, `demo/evidence.html`,
   `demo/jev.html`, `demo/encounter.html`, `demo/index.html#stokstad/5`.
3. If the projector washes out the paper look, add `?theme=night` to any page (the old dark look; nav links keep it). Not on `index.html`.
4. If the model should be live: `BIRCH_API_KEY_FILE=... python -m decision_api.server` in a terminal, then `python -m jev.walk --pick cancer` ready in a second one. Warm calls take a few seconds, a cold start minutes: make one call before you go on stage.
5. If any bundle was regenerated, reload the pages. One command rebuilds all of them: `python demo/export_all.py` (about 1 to 2 minutes; run times are in `demo/README.md`).
6. The nav brand (EQUAL CARE PATHWAYS, top left) always leads back to the Overview; on the dashboard the brand in the tab header does the same.

Wording to hold to everywhere: synthetic data only; primary-care behaviour is assumed; the Norway check supports the
ranking of reorderings, not their exact size; the optimiser result on Norway is a plausibility check with its range beside
it; decision-model scores are relative candidate scores, not probabilities.

## 3-minute version (judges walk past)

| Time | Click | Say |
|---|---|---|
| 0:00 | Overview: read the sentence, then the three cards left to right | "Today a synthetic Finnish county takes a median of N days from first contact to treatment; two reorders with no new equipment move the on-time share from A to B; on a real Norwegian hospital, fitted only to its observed pathway, the optimiser found the authors' reordering: X to Y at the best fit, with the range under it." (Read N, A, B, X, Y and the range off the cards.) |
| 0:35 | OPEN THE SIMULATOR (`flow.html?s=finland`) | "Every dot is a simulated patient. Where dots pile up, patients wait; steps turn mustard, then brick, as a queue forms." |
| 1:00 | Press OPTIMISE | "The two changes type out; the steps they touch get a dashed outline; the view flips to after the change. Same patients: the share within 90 days goes from today to after, median days fall, cancers missed unchanged: that is the guardrail. This is a saved optimiser run on held-out patients; the page does not search live." Flip TODAY / AFTER THE CHANGE once. |
| 1:45 | Nav: Evidence | "Fitted only to today's Norwegian pathway, the optimiser, started from it with no new equipment, arrived at the authors' three timing changes plus a fourth that needs clinical review: about the number on the screen at our best fit, with the range beside it. Here, on the faster scanner, we over-predict, and we say so. Trust the direction and the ranking, not the size." |
| 2:25 | Nav: Decision model | "At each clinical decision the model reads the visible record, scores only the answers the pathway allows, and a person accepts or overrides. The figure is a real recording of the deployed model, labelled as such. Scores are relative, not probabilities." |
| 2:50 | Click any tag, e.g. OUR SIMULATION on the Overview | "Every number we show is one of three kinds: published research, our simulation, or our assumption. Everything is synthetic." |

## 10-minute version

1. **The brief and the gap (1 min).** Overview, card 1 and DETAILS → first finding. Then the dashboard "Where time is lost"
   (`index.html#finland_lung/2`): time is lost mostly in waiting, mostly booking time calibrated to published waits, and
   less in capacity queues. Say "booking time and queues", not "queues". The tags under the headline open the claims; about
   half of the waiting days sit at steps set from published figures, the rest are our assumptions. The Finnish figure is simulated, not measured.
2. **Primary care (2 min).** Simulator → pathway dropdown → "Primary-care loop ›" (or DETAILS → "Primary-care loop"; `encounter.html`). Press Play
   (2 days/s), click the example "Antibiotics on day 45…", then press `t`: the brown ring and the truth box show what the
   record did not. Say: the decisions in this loop are placeholder tables, so it shows how the loop behaves; the numbers to
   quote are the multi-seed report below DETAILS. The ASSUMED BEHAVIOUR stamp opens the claim.
3. **Patients (1.5 min).** Nav: Patients. "Every patient here has a sealed truth: what they really have, drawn before day one.
   The system only sees the record on the right." Click LIFT THE SEAL: "This one was lung cancer; the antibiotics on day
   forty-five treated something she did not have. The optimiser never sees this side. It reads records, proposes a
   reordering, reruns the same patients, keeps it only if faster with no more missed cancers, then we report the result on
   new patients." Point at the caption: "Rerunning the same patients only works in a simulator; in a hospital that is a pilot."
   WATCH THIS PATIENT VISIT BY VISIT opens the loop on that patient.
4. **Reordering (2 min).** Simulator, `flow.html?s=finland`, OPTIMISE, flip. Hover a step for its numbers (click pins, Esc
   closes); click a dot for that patient's path. DETAILS → "Where time is lost" and "All results". State the guardrails:
   missed cancers, other patients' waits. If asked whether the optimiser ran on the encounter loop: not yet; say that plainly.
   Speed 0.5–8 days/s at the bottom; Space plays/pauses, arrows step, `r` restarts.
5. **Trust (2 min).** Nav: Evidence. Say in this order: (a) the model was fitted only on today's order (top row: published
   ring and our dot); (b) the authors' reordered pathway is predicted, not fitted, at the best fit, and the range over every
   setting that fits is wider (read it off the row); (c) the brick line: the model over-predicts the faster scanner alone, so
   trust the ranking, not the size; (d) the optimiser, started from today's pathway with no new equipment and not told the
   answer, arrived at the authors' three timing changes; it did not improve on their redesign; the fourth change it found,
   planning tissue sampling at referral triage, needs a clinical check; (e) the authors' figure includes the shorter PET-CT
   wait, so it is not a like-for-like pair with ours. If a judge asks "is this overfitted?", scroll to DETAILS for the
   robustness panels. Then `flow.html?s=norway&compare` (opens on After with the best-fit range under the headline; DETAILS →
   "Check against the published study" holds the table and all caveats; "See both pathways drawn step by step" opens
   dashboard screen 5) and `index.html#stokstad/5` for the bars and "How to read the bars". Deeper: `docs/norway_case_study.md`, `docs/validation.md`.
6. **Decision model (1.5 min).** Nav: Decision model. Figure first, then TRY THE EXAMPLES and the GP visit card: the context
   is a simulator patient, the bars below it are the placeholder table the simulator uses today (labelled brick: not the
   model). Live scoring needs `?api=hosted`. Optionally run `python -m jev.walk --pick cancer`. Always say whether an answer is
   live or a recording; the page labels it.
7. **Honesty and next (1 min).** Click any tag to open `research.html`: the counts of published / simulation / assumption, the
   worked example of the waiting split, and "What we could not support" first below DETAILS (we do not claim survival gains).
   Open one row, e.g. `research.html#fi-diagnosis-to-treatment-37d`: source, how we read it, and the conflict (lung-specific
   65 to 69 days against the 37 we use). Close on what is not done: model-written patient libraries are not the headline
   source; the optimiser has not run on the encounter loop; the care catalogue is a draft until a clinician reads it.

## If something is down

| Symptom | Do |
|---|---|
| Model GPU cold or key missing (`jev.walk` stops with "Model may still be starting") | Retry once (answers received are cached). Otherwise `python -m jev.walk --pick cancer --jev mock` and say it is a mock, or show the recording on the Decision model page and say "recorded". Never present a mock or saved answer as live. |
| `decision_api.server` will not start | Skip the live part; the Decision model page works from disk with its recordings. Show `decision_api/README.md` and the walk against `--jev table` (placeholder tables, labelled). |
| Eemeli's live demo blank | It needs its server: `python -m note_reader.server --port 8770`, then open `http://127.0.0.1:8770/`. From disk it stays empty. Without it, skip it; nothing else depends on it. |
| A page says "pending" | Rerun the exporter for that bundle (`export_flow.py`, `export_encounter.py`, `export_start.py`, `export_cards.py`) or `python demo/export_all.py`, and reload; if it cannot be fixed, say the number is pending and move on. |
| A screen shows a number that differs from an earlier note or slide | The screen is right for the run it shows (the footer strip names the bundle and, where known, when it was built). Say which run. |
| The paper look is unreadable on the projector | Add `?theme=night` to the URL. |
| No browser tab opens a file | Serve the folder: `python -m http.server -d demo 8000`, open `http://localhost:8000/start.html`. |

## Questions to expect

- *Is this real patient data?* No. Synthetic patients; inputs sourced or marked assumption (the tags, and `research.html`).
- *Your optimiser got less than the authors' 80. Is it worse?* Not comparable: the authors' figure includes the shorter PET-CT wait, ours assumes no new equipment, and we do not report the optimiser with the scanner (D68). What is a result: started from today's pathway and not told the answer, it arrived at the authors' three changes plus one overlapping change that needs a clinical check; it did not improve on their redesign. Read the range, not the best-fit point.
- *Does reordering without equipment beat buying the scanner?* Not shown. Without new equipment it beats today in every fitting setting, but beats the scanner alone in only part of them (the count is on the Evidence page, DETAILS). The authors' figure includes the shorter PET-CT wait, so it is not comparable with the no-equipment number.
- *Is this overfitting?* The reported number comes from patients the search never saw (Patients page, step five and the first finding below DETAILS; Evidence, robustness panels).
- *Did the model-written patients drive these results?* No. The results come from the simulator runs shown; the Patients page shows what a model-written patient looks like and how many exist.
- *Does the Norway check prove the Finnish numbers?* No. It supports the engine's reordering logic on a hospital pathway; it does not validate primary care.
- *What do the model's scores mean?* Relative candidate scores for the offered options; not disease probabilities, test accuracy or times.

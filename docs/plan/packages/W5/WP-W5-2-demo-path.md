# WP-W5-2: One demo path for the judges

| | |
|---|---|
| Size | S–M · Model: Sonnet |
| Why | The submission now has five screens made by different lanes and people: the dashboard (`demo/index.html`), the flowchart page (`demo/flow.html`, ordering result), the encounter-loop page (`demo/encounter.html`, primary care), the decision-model panel (`decision_api`, `/decision` on `note_reader.server`) and Eemeli's live demo (`live_demo/flow.html`, note reader). A judge has minutes. There is no single start page or order. |
| Owned paths | `demo/start.html` (new), `demo/start.css` (new), `docs/demo_path.md` (new), `tests/test_demo_start.py` (new) |
| Do not edit | every other demo page, `live_demo/`, `note_reader/`, `decision_api/`, `web/`, `README.md` (propose README lines in your report; the integrator adds them) |

## Outcome

1. `demo/start.html` (offline, opens from disk, same visual language as `demo/encounter.html`): a one-screen start page that tells the story in order and links each screen with one sentence of what to look at and the one number it proves:
   1. The problem (Finnish lung cancer: share treated within the target today, with source).
   2. **Where time is lost in primary care** → `encounter.html` (the loop, a patient's record, the second finding).
   3. **What reordering wins** → `flow.html?s=finland&compare` (the ordering result, held-out).
   4. **Why we trust the engine** → the Norway check (`docs/validation.md`, with its honest limits).
   5. **The decision model at the nodes** → how to run `python -m jev.walk` and the `/decision` panel (live when the GPU is up, saved examples otherwise, always labelled).
   6. Data and honesty: synthetic only, catalogue sourcing counts, assumptions marked.
2. Numbers are read from the existing bundles (`demo/data/*.js`) and `docs/review_checks/*.json` at page load where they exist, never typed by hand; a missing number shows "pending", not a guess.
3. `docs/demo_path.md`: a 3-minute and a 10-minute walkthrough script for whoever presents, with the exact clicks and what to say at each, plus the fallback if a live service is down.
4. Test: every link target exists in the repo; every number shown is read from a file (grep the page for digits outside the data-binding code).

## Acceptance

- [ ] Opens from disk with no console errors (headless Chrome is available: `google-chrome --headless=new --no-sandbox --screenshot=...`); check at 1440×900 and 1280×720.
- [ ] `scripts/gate.sh` green.
- [ ] Report: a screenshot path, and proposed README lines.

## Report (builder fills in)

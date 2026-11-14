# WP-W4-2: Show the encounter loop and patient records in the demo

| | |
|---|---|
| Component | C6 demo, C8 |
| Size | M · Model: Sonnet |
| Needs | merged encounter loop and `patient_engine/record_text.py`; the offline flow page `demo/flow.html` (read `demo/README.md` "Flowchart simulation page", `docs/platform/flow-format.md`) |
| Owned paths | `demo/export_encounter.py` (new), `demo/data/encounter_bundle.js` (new, generated), `demo/encounter.html`, `demo/encounter.js`, `demo/encounter.css` (new), `demo/README.md` (one new section), `tests/test_demo_encounter.py` (new) |
| Do not edit | `demo/flow.html`, `demo/flow.js`, `demo/flow.css` (another lane may touch them), `pathway_sim/`, `web/` |

## Outcome

A new offline page `demo/encounter.html` (open from disk, no server) in the same visual language as
`demo/flow.html` (read its CSS and copy the look; light and dark as that page does):

1. **The loop as a graph**: first contact → nurse / GP encounters → tests (grouped: in-visit, lab, imaging, definitive) → treatment → discharge / return → referral → hospital steps → treatment. Edge thickness = how many patients took that transition in the run; the return edge visibly loops back. Patients as dots moving over simulated days, like the flow page (play/pause, speed).
2. **Patient panel**: click a dot (or pick from a list of interesting patients: a cancer first treated as infection, a long loop, a worried-well patient) to see that patient's record as `record_text.render` lines, mechanical log and assessments visually distinct, with the hidden truth shown only behind a "reveal truth (teaching view)" toggle.
3. **Results strip**: the outcome table of the run and the by-group table (from the run's own report).
4. Data: `python demo/export_encounter.py` runs the encounter scenario (seed fixed, n large enough to have about 50 cancers; time it) and writes `demo/data/encounter_bundle.js` (keep it under about 5 MB: sample patients for the animation, aggregate edges for the graph).

## Acceptance

- [ ] `python demo/export_encounter.py` under 2 minutes; bundle under 5 MB.
- [ ] Page opens from disk with no console errors (check with a headless browser if available, e.g. `python -m playwright` or node; otherwise a test that parses the bundle and checks every node referenced by an edge exists and every sampled patient's record renders).
- [ ] The hidden truth appears nowhere in the page's default view (test greps the bundle's default-view fields).
- [ ] `scripts/gate.sh` green.

## Report (builder fills in)

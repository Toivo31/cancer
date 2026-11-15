# Equal Care Pathways

Junction2026 prototype for the AstraZeneca challenge. Start with
[the master plan](docs/master_plan.md).

**Video:** https://vimeo.com/1246920559/41ca86218a?share=copy&fl=sv&fe=ci
**Technology challenges** (Modal, Nemotron, Gemini API, Verda): [what we claim and what backs it](docs/submission_tech_challenges.md).

## Decision model integration for the demo team

Read [the teammate setup guide](decision_api/README.md) or give
[the integration prompt](decision_api/INTEGRATION_PROMPT.md) to your coding model.
The follow-up [shared-Nemotron refinement handoff](decision_api/REASONING_HANDOFF.md)
adds the optional token-budget and patient-tool design; it is off by default.

```bash
python3 -m decision_api.server
```

Open http://127.0.0.1:8771/decision. Medical-dataset pictures and recorded model
examples work immediately, without credentials, uploads or GPU usage. A backend
key enables an explicit live call to the separately hosted checkpoint1138 model.
The JavaScript client and optional review component can be reused in your own UI.

## Existing project demo

```bash
python3 -m pip install -r requirements.txt
python3 -m note_reader.server
```

Open http://127.0.0.1:8770 for the flowchart demo, `/note` for the note reader,
`/report/` for the dashboard and `/decision` for the decision-model panel.
Simulator estimates and model candidate scores are separate quantities.
All model proposals require human review. See the integration guide for the
prototype's limitations and the difference between live and saved examples.

## Three-slide live website

[Open Equal Care Pathways](https://cancer123--equal-care-pathways-web.us-east.modal.run/?release=20261115-6) — a moving patient graph, Decision Studio (Text, Photo and Custom question), and a discussion/manifesto placeholder.

[Join our Modal organization](https://modal.com/signup?token=dd6w00V0NL0JDEY0zPvPJ5uZ08k73wqyJLys8mplk8o&shareable-token=true&organization=true) using this invitation link.

Website source and deployment instructions: [website/README.md](website/README.md). The site reuses the existing public decision gateway; visitors do not need a Modal account to try it.

Decision Studio lists all examples on one scrollable page. Predefined medical text, patient retrieval, and photo examples use recorded results only. Medical text preserves archived checkpoint 1138 provenance; photos and retrieval retain checkpoint 2350. Only custom questions compute live. The first slide animates a vertical branching graph without controls.

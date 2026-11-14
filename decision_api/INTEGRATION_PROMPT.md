# Copy this brief to the coding model building the project demo

Integrate the decision-model API into the existing project demo as a real,
user-facing interface. Read `CLAUDE.md`, `docs/master_plan.md` and
`decision_api/README.md` first. Preserve teammates' existing work.

## What to build

Build patient/example cards, available observations, a readable question,
allowed choices with scores, a highlighted proposal, and accept/correct review
controls. Match the project's visual design. The reference `<birch-decision>`
component is optional; you may build your own UI around `client.js`.

**Do not make the user type JSON, API requests, raw decisions or server paths.**
Your UI constructs API requests internally from the selected patient's visible
state and the flowchart's allowed choices. Send the question and choices to be
scored, not a preselected/model-generated decision. Never send prior model
scores, a model proposal, hidden diagnosis, future observations or gold labels
as evidence. Only send a human's chosen action to the separate review endpoint.

The model proposes; the human chooses. The API does not own or advance simulator
sessions. Do not automatically execute referrals, tests or treatment. Do not
change the simulator's headline results or turn these relative scores into
clinical probabilities, test sensitivity or time-to-treatment estimates.

## Required ready-made content

Use the actual medical-dataset pictures in `decision_api/web/samples/`, including
the patient context, source link and CC BY4.0 attribution. These are unchanged
PAD-UFES-20 training examples. **Do not add uploads** or fabricate patient images.

Include the precomputed examples in `decision_api/web/precomputed.json` so the
demo works instantly without cloud credentials or a GPU. They contain recorded
checkpoint1138 outputs, not guessed scores. Use `api.precomputed(id)` and label
these results **Saved example**, with their recorded timestamp. Use the bundled
synthetic pathway case as the default workflow example. It is a configurable
integration example, not a validated cancer protocol.

Offer **Run live model** as a separate, deliberate action. Keep **Live model**,
**Saved example** and **Scripted fixture** visibly distinct. A live failure must
stay visible; never silently replace it with saved or invented results. Comparing
a saved example stays local and must not POST the raw saved decision to the API.

## Integration constraints

- Import `createDecisionClient` from `decision_api/client.js` and call your app's
  same-origin `/api/decision` proxy. TypeScript declarations are provided.
- Keep the cloud API key on your backend. Never put it in browser code or a
  public environment variable. The Python proxy has no ML dependencies and is
  already mounted into `note_reader.server`.
- Render every allowed candidate score. Keep stable action/question IDs and
  checkpoint identity. Scores are relative to the supplied choices.
- Only use visible patient information. For a pathway, pass `case.step` and
  evidence availability; do not serialize the whole hidden simulator patient.
- Ignore/cancel stale responses when the selected patient or workflow changes.
- Call the model on user actions. No health polling, per-frame scoring, bulk
  cohort inference or idle keepalive: the model costs money while allocated.
- Allow a startup/error/retry state. A cold start has taken about six minutes.
- Owner/team handles overnight pausing. Do not install a schedule or change
  training jobs, weights, checkpoints, providers or GPU configuration.

## Completion criteria

A teammate can clone the repo, run `python3 -m decision_api.server`, choose a
picture or pathway, and see a labelled saved model result immediately. With a
backend key configured, Run live model obtains a fresh proposal and a human
can record a review. Custom cases use the same client without exposing raw JSON
to users. Original model outputs stay unchanged; reviews are separate events.

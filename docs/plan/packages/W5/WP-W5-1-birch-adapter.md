# WP-W5-1: Connect the team's decision model (checkpoint 1138, "Birch" API) to the decision nodes

| | |
|---|---|
| Component | C4 decision layer; D49, D51; the JEV owner's kit `decision_api/` (README, INTEGRATION_PROMPT) |
| Size | M · Model: Sonnet |
| Needs | merged on `overnight/sim`: `decision_api/` (proxy `python -m decision_api.server`, routes `/api/decision/score` and `/api/decision/pathway`), `jev/` contract and `BackendPolicy.choose_with_note`, `jev/record_context.py`, `patient_engine/record_text.py`, the encounter loop |
| Owned paths | `jev/birch.py` (new), `jev/factory.py` (register the backend only), `jev/walk.py` (new), `tests/test_jev_birch.py` (new), `docs/platform/jev-birch.md` (new) |
| Do not edit | `decision_api/` (the JEV owner's code), `pathway_sim/`, `jev/record_context.py`, `pathway_sim/__main__.py` (another lane adds `--jev URL` there; your backend must work through `jev.factory`) |
| Review required | yes: I1, network, cost |

## What the model's API is (read `decision_api/README.md`)

`POST /v1/pathway/propose` with `{case: {case_id, context, step, evidence: [{source_id, available_at_step, text}]}, workflow: {id, version, root, nodes: {<node>: {question, protocol, actions: [{id, description, next}]}}}, node_id}` returns
`questions[0].choices[].score` (relative candidate softmax over the offered choices), `proposed_action_id`, `score_margin`, `latency_ms`, backend identity. No free-text rationale. Warm latency about 5–7 s per call, cold start about 6 min, one GPU, costs money while allocated. The owner's rules: visible information only; no bulk cohort inference; no health polling; the model proposes and a human reviews.

## Outcome

1. **`BirchBackend`** (a `jev` DecisionBackend): turns a `DecisionRequest` built from a patient record into a pathway-propose call through the local proxy (`http://127.0.0.1:8771/api/decision/pathway` by default; the proxy holds the key, `BIRCH_API_KEY` never reaches our code) or through the note-reader mount. Mapping: `case.context` = background and presenting complaint in plain words; `evidence` = the mechanical record entries rendered by `record_text.render` (one evidence item per entry, `available_at_step` = its encounter number, `step` = the current encounter), assessments excluded unless a flag is set; `workflow` = one node per decision point with the offered options as actions (`description` from `care.yaml` labels) and terminal next nodes. Scores become `probs` over the offered option ids (renormalised); `explanation` carries checkpoint, latency and margin. `record_note`/`assessment` stay empty (the API returns none) and the engine's template assessment is used, labelled as such.
2. **Cost guards**: a response cache keyed by the request hash (on disk, `runs/jev_cache/`), a hard call budget (`--max-calls`, default 50), concurrency 1, a clear error (no silent fallback) when the proxy or model is down or cold, and a summary of calls, cache hits, latency.
3. **`python -m jev.walk`**: the demo and test tool. Takes one synthetic patient (`--library`, `--patient` or `--pick cancer|pneumonia|worried_well`) and walks them through the encounter loop step by step: at each decision prints the record so far, the offered actions with the model's scores and its proposal, and waits for a human choice (Enter = accept the proposal, or type an action id), with `--auto-accept` for unattended runs and `--placeholder` to compare with the table policy. Ends with the outcome and the full record (`record_text`), saved as JSON.
4. Registered in `jev.factory` so `--jev birch` (and `birch+http://host:port`) works wherever a JEV backend is chosen.

## Acceptance

- [ ] Tests with a local mock of `/api/decision/pathway` (an `http.server` in the test that returns the recorded format from `decision_api/web/precomputed.json`): request mapping, scores to probs, cache hit on repeat, budget stop, error on 503 and on timeout.
- [ ] I1 test: for a record built from a card with a co-existing illness, the JSON sent to the API contains no condition id, hidden field name or library card id; evidence never has `available_at_step` greater than `step`.
- [ ] `python -m jev.walk --pick cancer --auto-accept --jev mock` runs end to end against the mock in under 30 s.
- [ ] `docs/platform/jev-birch.md`: how to start the proxy with the key, how to walk a patient, how to run a small cohort with a budget, and the owner's constraints quoted in plain words.
- [ ] `scripts/gate.sh` green. No test calls the real model.

## Report (builder fills in)

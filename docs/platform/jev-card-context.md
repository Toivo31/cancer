# What a JEV decision request contains once patient cards are in

For whoever builds the JEV. One page. Status: **field names fixed, 14 Nov.** They follow the card
contract (`card/1`, `patient_engine/card.py`) and the reveal handle (`patient_engine/reveal.py`),
both merged on `overnight/sim`. What is not built yet is the step that puts them into a request
(the simulator adapter, WP-C1-8); `episode` and the per-result `t_days` come with it. Any change
will be posted on the agent channel.

## The rule that shapes everything

The JEV never receives a patient card. A card has a hidden side (true conditions, true values,
which test results are planned to be wrong) and a revealed side. A request carries **only what has
been revealed for this patient up to this moment** (invariant I1 in `docs/plan/01-architecture.md`).
The JEV has to work as a clinician does: from the record, never from the truth. Training data
built from runs follows the same rule.

## Request: what stays the same

Endpoint and envelope are unchanged (`POST /v1/decide`, `jev/contract.py`,
`docs/platform/specs/02-jev-interface.md`, example `jev/examples/decide_request.json`):
`request_id`, `decision_point`, `question_type`, `options` (each with `id`, `label`, `test`,
`features` such as `invasive`, `cost_eur`, `lead_days`), and the response is probabilities over
the offered option ids. The existing context keys (`group`, `age`, `t_days`, `fast_track`,
`attributes`, `history`) stay, so a JEV built on today's contract keeps working.

## Request: what is added to `context` (all optional for the JEV to read)

```json
"context": {
  "group": "non_specific", "age": 67, "t_days": 31.5, "fast_track": false,
  "attributes": {"location": "peripheral"},
  "history": [{"step": "cxr", "test": "chest_xray", "result": false, "t_days": 14.0}],

  "card_format": "card/1", "patient_id": "c_5f2a91e0",
  "background": {"age": 67, "sex": "f", "smoking_status": "former", "pack_years": 30, "region": "rural_east"},
  "episode": 1,
  "presenting": {"reported": ["cough_3wk", "fever"],
                 "text": "I have had a cough for about a month and a temperature since the weekend."},
  "observations": [
    {"test": "history", "attempt": 1, "status": "ok",
     "values": {"cough_3wk": true, "fever": true, "weight_loss": false},
     "report": "Cough for four weeks, fever for three days. No weight loss reported.", "t_days": 0.0},
    {"test": "blood_count", "attempt": 1, "status": "ok",
     "values": {"crp": 88.0, "hb": 127.0}, "report": "CRP 88 mg/L, Hb 127 g/L.", "t_days": 1.0},
    {"test": "chest_xray", "attempt": 1, "status": "ok",
     "values": {"abnormal": false, "consolidation": true},
     "report": "Right lower lobe consolidation. No separate lesion identified.", "t_days": 14.0}
  ],
  "notes": [
    {"id": "n2", "kind": "gp_note",
     "text": "Chest X-ray shows consolidation; treated as pneumonia. Review in six weeks."}
  ]
}
```

| Key | Meaning | Comes from |
|---|---|---|
| `patient_id` | An opaque id (a hash). It never contains the condition or the library's card id | `PublicView.card_id` |
| `background` | Facts known from arrival. Field names come from the catalogue's `background` list | `PublicView.background` |
| `episode` | 1 for the first contact; 2, 3 … when the patient comes back after a discharge or treatment that did not help | engine (planned, decision D40) |
| `presenting` | What the patient says at first contact in this episode: catalogue variable ids plus free text | `PublicView.presenting` |
| `observations` | Every test result revealed so far, oldest first. One entry per (test, attempt); a repeated test has attempt 2, 3. `values` are **typed**: booleans, numbers with the catalogue's units, categories. `status` is `ok` or `non_diagnostic` (no values). `report` is the clinician-readable text | `RevealedObservation` (+ `t_days` from the engine) |
| `notes` | Clinical notes, shown only after every fact they mention has been revealed | `RevealedNote` |

Ids (`cough_3wk`, `chest_xray`, `crp`) are defined in the catalogue: `catalogue/README.md` for the
format, `catalogue/_examples/tiny/` for a small example, `catalogue/lung-primary-care/` for the real
one (being built now). A JEV should read the catalogue once to know every possible variable,
test, output, type and unit, so its input layout is fixed even when a patient has few results.

## The JEV can write to the record (decision D49)

The response may carry, next to `probs`, the JEV's own words; the simulator appends them to the
patient record as an `assessment` entry right after the decision, and every later request includes
them. This is where the JEV's enriched context lives.

```json
{"request_id": "p1042:gp_encounter:3", "probs": {"order_chest_xray": 0.7, "follow_up": 0.3},
 "record_note": "Cough 5 weeks after antibiotics, ex-smoker 30 pack-years, CXR 4 weeks ago read as consolidation. Persisting symptoms after treatment: repeat CXR.",
 "assessment": {"working_diagnosis": "unresolved pneumonia", "differential": ["lung cancer", "COPD"],
                "plan": "repeat chest X-ray, refer if abnormal", "confidence": 0.5}}
```

Rules: at most 2 000 characters per note; `assessment` keys as above, all optional; the note is
interpretation and never replaces the **mechanical log** the simulator keeps by itself (every step,
every result with `positive` true or false). Requests carry both layers: mechanical entries in full,
assessments newest first within a size budget. `explanation` stays a free comment that is logged but
not put in the record.

## What is never in a request

Condition names as facts, `hidden.*`, `caused_by`, the error plan, results of tests not yet done,
notes whose facts are not yet revealed. The type separation is tested
(`tests/test_pe_contract.py::test_i1_*`); the request builder will get the same kind of test.

## Coming next (depends on a decision Tuomas is making now)

Primary care is likely to become an **encounter loop**: nurse, GP and specialist encounters each
add findings to the record and choose among role-specific actions (order a test, treat on a
presumption, book a follow-up, refer, discharge), and a patient can return any number of times.
For the JEV this means more decision points, `decision_point` names like `gp_encounter` or
`nurse_encounter`, a `role` key in `context`, and `options` that include treatments and
follow-ups as well as tests. The envelope does not change.

## How to try it today

- Example card: `tests/fixtures/patient_engine/card_example.json` (hidden and revealed parts together; the JEV sees only the revealed part).
- Types: `patient_engine/card.py` (`PublicView`, `RevealedObservation`, `RevealedNote`, `Presenting`).
- The handle that produces them: `patient_engine/reveal.py` (`RevealHandle.visible(state, revealed=[(test, attempt), ...])`, `.reveal(test, attempt, state)`). Try `python -m patient_engine show <library> <n>` for a patient's public view.
- Contract and stub: `python -m jev.stub_server --scenario scenarios/finland_lung.yaml --flowchart baseline --port 8100`, then `python -m pytest -q tests/test_jev_contract.py`.

Questions or requests for fields: post on the agent channel (`python scripts/comms.py post --type QUESTION ...`, to `claude-code@tuomas/architect`) or ask Tuomas.

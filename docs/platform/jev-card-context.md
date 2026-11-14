# What a JEV decision request contains once patient cards are in

For whoever builds the JEV. One page. Status: **field names fixed, 14 Nov.** They follow the card
contract (`card/1`, `patient_engine/card.py`) and the reveal handle (`patient_engine/reveal.py`),
both merged on `overnight/sim`. What is not built yet is the step that puts them into a request
(the simulator adapter, WP-C1-8); `episode` and the per-result `t_days` come with it. The record-based builder (WP-C8-4) is below. Any change
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

## Built from a patient record (encounter loop)

In the encounter loop the simulator builds the context from the patient's **record**
(`patient_engine/record.py`, `record/1`) with `jev.record_context.context_from_record(record, role=,
now_days=, catalogue=)`; `jev.adapter.build_context(view)` uses it whenever the view carries a record.
Same keys as above, plus these (new names marked; nothing above was renamed):

| Key | Meaning |
|---|---|
| `role` (new) | `nurse`, `gp` or `specialist`: who is deciding. Null at steps with no role |
| `encounters_so_far` (new) | Number of visits (encounters) in the record |
| `found` (new) | Latest revealed value of each variable asked or examined (`{"cough_3wk": true, "weight_loss": false}`), from the encounters |
| `actions` (new) | Ids of the actions already taken, oldest first (orders, bookings, treatments), so a repeat can be recognised |
| `notes` | Now the clinicians' encounter notes: `{id: "n1", kind: "gp_note", text, t_days}` (`kind` is `<role>_note`) |
| `observations` | As above; `attempt` counts from 1; `t_days` is when the result arrived |
| `presenting` | `reported` only (the record keeps no free text); `text` is absent |
| `history` | One entry per result: `step` and `test` are the test id; `result` is the yes/no reading through the test's `positive_when` when the catalogue is passed, otherwise `null` |
| `group`, `fast_track`, `attributes` | Kept for old JEVs. `group` is whatever the engine's view has (absent when the record is all there is) |

A request example: `jev/examples/decide_request_record.json` (decision point `gp_encounter`, options are
actions such as `order_chest_xray`, `treat_antibiotics`, `refer_urgent`). The envelope does not change.
`patient_engine/record_text.py` (`render(record, catalogue, care)`) turns a record into one readable line per
entry for the demo. The request builder has the I1 test the section below promises:
`tests/test_jev_record_context.py` builds a record from a card with a co-existing illness and checks that
no condition id or hidden field name reaches the context (a clinician's note may use a diagnosis word
the clinician wrote; the test treats notes as the clinician's own prose).

## What is never in a request

Condition names as facts, `hidden.*`, `caused_by`, the error plan, results of tests not yet done,
notes whose facts are not yet revealed. The type separation is tested
(`tests/test_pe_contract.py::test_i1_*`); the record-based request builder has the same kind of test (`tests/test_jev_record_context.py`).

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

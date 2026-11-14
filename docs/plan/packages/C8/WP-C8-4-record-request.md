# WP-C8-4: From the patient record to the JEV request, and readable records

| | |
|---|---|
| Component | C8, C4; `docs/platform/jev-card-context.md` |
| Size | S–M · Model: Sonnet |
| Needs | merged `patient_engine/record.py`, `jev/` |
| Provides | `jev.record_context.context_from_record(record, *, role, now_days)`; `build_context` uses it when a view carries a record; `patient_engine/record_text.py` renders a record as readable lines for the demo |
| Owned paths | `jev/record_context.py` (new), `jev/adapter.py` (`build_context` only), `patient_engine/record_text.py` (new), `tests/test_jev_record_context.py`, `tests/contracts/test_record_request.py`, `docs/platform/jev-card-context.md`, `jev/examples/decide_request_record.json` (new) |
| Review required | yes: I1 |

## Outcome

- `context_from_record` returns the context described in `docs/platform/jev-card-context.md` from a
  `Record`: `card_format`, `patient_id`, `background`, `episode`, `presenting` (the latest episode's
  `reported` plus text if any), `observations` (every revealed result with `t_days`), `notes` (encounter
  notes), plus `role` and `encounters_so_far`, plus the existing keys (`age`, `t_days`, `history` as
  `(step, test, result)` with result from the catalogue's `positive_when` when the caller passes the
  catalogue, else `null`). Update the doc where the record adds or renames anything.
- `build_context(view)`: when `view` has a non-empty `record` attribute (WP-C8-1 adds it to
  `PatientView`), merge `context_from_record`; otherwise unchanged (existing tests stay green). Use
  `getattr(view, "record", None)` so this works before WP-C8-1 merges.
- A contract test sends a record-based request to the stub server and validates the response.
- `record_text.render(record, catalogue=None) -> list[str]`: one short readable line per entry
  ("Day 9 · GP · cough 4 weeks, no fever · ordered chest X-ray"; "Day 11 · result · chest X-ray: no
  lesion, consolidation"), using catalogue labels when given.
- I1 test: the context built from a record contains no condition ids or hidden field names even when
  the record is built from a card with a co-existing illness.

## Tickets

| | ID | Ticket | Done when |
|---|---|---|---|
| [ ] | C8-4-T1 | `context_from_record` + example JSON + tests | green |
| [ ] | C8-4-T2 | `build_context` merge; existing JEV tests green | green |
| [ ] | C8-4-T3 | Contract test against the stub server | green |
| [ ] | C8-4-T4 | `record_text.render` + tests; doc updated | green |

## Report (builder fills in)

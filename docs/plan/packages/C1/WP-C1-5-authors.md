# WP-C1-5: Model-written cards (authors G1, G2) and the generation pipeline

| | |
|---|---|
| Component | C1 (P5, P13 `generate`), "Generation pipeline", "Error rates" (`guided`) |
| Size | M · Model: Sonnet |
| Needs | merged: `patient_engine/llm.py` (client, fake client), `skeleton.py` (`make_design`, `make_skeleton`, `settle_error_plan`), `validate.py` (`validate_card`, `repair_prompt`, `has_errors`), `library.py` (`write_library`), `card.py` (`card_schema`) |
| Provides | `generate_library(catalogue, design, seed, client, *, budget, out_dir) -> LibraryManifest`; `python -m patient_engine generate ...` |
| Owned paths | `patient_engine/authors.py`, `patient_engine/pipeline.py`, `patient_engine/prompts/` (prompt texts as versioned data files), `patient_engine/commands/generate.py`, `tests/test_pe_authors*.py`, `tests/test_pe_pipeline*.py` |
| Review required | yes: I1 (G2 sees hidden findings; notes must not leak), cost |

## Outcome

Per card: skeleton → **G1 patient author** (background, findings with `caused_by` per state, what the
patient reports, the patient's account) → `settle_error_plan` → **G2 result author** (every test,
state and attempt, following the plan in `guided` mode, with short report texts and a GP note) →
`validate_card`; on errors `repair_prompt` and ask again at most twice, then discard and log. Output
JSON validated against schemas derived from `card_schema(catalogue)`. Prompts are versioned files;
`provenance` records model, prompt versions, `error_source`, repairs. Concurrency via `LLMClient.map`,
budget stop is clean (partial library written, manifest says so), cache makes reruns cheap.

`python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 300 --seed 1 --out runs/libraries/L1`
works with `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` set; `--fake` uses `FakeLLMClient` backed by the
reference generator (so the whole pipeline runs offline and in tests).

## Acceptance

- [ ] Offline end to end with `--fake`: 50 cards, all valid, library written and loadable (test).
- [ ] Repair loop: a fake client returning a broken card then a fixed one yields one repair recorded
      in provenance; three broken answers discard the card and log it (tests).
- [ ] Budget: `Budget(max_calls=5)` stops cleanly with a partial library (test).
- [ ] I1: G1 and G2 prompts are built from the skeleton and catalogue only; a test asserts the
      condition label does not appear in note text fields of fake-generated cards unless a revealing
      fact is mentioned (reuse validator rule 8).
- [ ] No API key in logs, files or exceptions (reuse the client's guarantees; one test).
- [ ] Prompts ask for English text (C1 Q5), synthetic, no real names or places beyond the region field.

## Report (builder fills in)

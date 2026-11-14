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

**Built** (branch `w3/pe-authors`): `patient_engine/authors.py` (G1/G2 prompt builders, schemas, assembly, repair routing),
`patient_engine/pipeline.py` (`generate_card`, `generate_library`, `generate_library_with_report`, `reference_fake_client`,
`estimate_cost`), `patient_engine/commands/generate.py`, `patient_engine/prompts/` (`g1_patient.v1.*`, `g2_results.v1.*`, README),
`tests/test_pe_authors.py`, `tests/test_pe_pipeline.py` (27 tests, about 2 s). Gate: PASS.

**Real run**: `export LLM_BASE_URL=... LLM_MODEL=... LLM_API_KEY=...` (optional `LLM_MODEL_G2`), then
`python -m patient_engine generate --catalogue catalogue/lung-primary-care --n 300 --seed 1 --out runs/libraries/L1 --max-calls 2000`.
`--estimate` prints calls and tokens first; `--resume` replaces a partial library (same cache). Exit 3 = partial.

**Cost per card (lung catalogue, measured prompt sizes)**: 2 calls (plus repairs, plus the client's own schema retries), about 12.4k input
tokens (G2 is most of it: schema, 16 tests x 3 attempts of plan) and about 4k output tokens (reference output 2.7k x 1.5). 300 cards: about
600 calls, 3.7M in, 1.2M out, before repairs and any reasoning tokens.

**Decisions**
- Background, conditions, attributes and the error plan come from the skeleton and engine; the models write findings, presenting text, account, results, reports, GP note.
- G1 sees reference chances per variable for this patient (resolved per condition) so frequencies can match; the audit (G4) still has to measure drift.
- G2 gets the settled plan plus engine-suggested numbers for measured outputs and for `wrong` categorical ones (keeps error sizes inside the validator's bands).
- Repair: failing author gets its own answer back plus `repair_prompt`; a G1 repair re-asks G2. `card_reveals_condition` is promoted to an error in the pipeline.
- Cards run one per thread (not `LLMClient.map`) so a budget stop leaves whole cards. Partial flag lives in `<out>.work/generation_report.json`, because `LibraryManifest` has no field for it.
- `presenting.reported` must be true symptom findings (checked, repaired, not silently fixed). Temperatures default to unset (reasoning models reject them).

**Not done**: states other than `all_active` (raises NotImplementedError); G4 audit; `free` error mode; real endpoint never exercised (json_schema mode and server quirks untested); findings-from-engine fallback if G1 drifts too typical.

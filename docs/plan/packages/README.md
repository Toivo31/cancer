# Work packages: wave 2 (Saturday 14 Nov, toward the Sunday freeze)

Written by the architect directly from the component files (no separate spec wave, to save time
before the freeze at Sunday 06:00 Helsinki = 04:00 UTC). Each package file is self-contained for a
builder agent with no memory of the conversation. Rules for builders: `docs/plan/02-execution-strategy.md`
(Part 2, "Builder rules" and "Definition of done").

## Package map

| WP | Outcome | Size | Needs | Provides | Owned paths | Review | Wave | Model |
|----|---------|------|-------|----------|-------------|--------|------|-------|
| [WP-C1-1](C1/WP-C1-1-contracts.md) | `card/1`, `library/1`, `cohort/1` types; `catalogue/1` format, loader and validator; tiny example catalogue | M | – | `card/1`, `catalogue/1` | `patient_engine/{__init__,card,catalogue,schema}.py`, `catalogue/README.md`, `catalogue/_examples/`, `tests/test_pe_contract*.py`, `tests/test_pe_catalogue*.py` | yes (I1) | 2a | Opus |
| [WP-C1-2](C1/WP-C1-2-llm-client.md) | Model client with structured output, retries, budget, cache, call log; fake client | M | – | `patient_engine.llm` API | `patient_engine/llm.py`, `tests/test_pe_llm*.py` | yes (network) | 2a | Sonnet |
| [WP-C2-R1](C2/WP-C2-R1-research-conditions-symptoms.md) | Sourced numbers: conditions, prevalence among presenters, symptom and sign frequencies by condition | M | – | research notes | `docs/research/catalogue/conditions_symptoms.md` | yes (medical) | 2a | Sonnet |
| [WP-C2-R2](C2/WP-C2-R2-research-tests-labs.md) | Sourced numbers: test accuracy, bloodwork distributions, report times | M | – | research notes | `docs/research/catalogue/tests_labs.md` | yes (medical) | 2a | Sonnet |
| [WP-INFRA-1](infra/WP-INFRA-1-gate.md) | `slow` marker, one gate command, contract-test folder, golden checks | S–M | – | `scripts/gate.sh` | `pytest.ini`, `tests/conftest.py`, `tests/slow_tests.txt`, `tests/contracts/`, `scripts/gate.sh`, `docs/plan/02-execution-strategy.md` (gate section only) | no | 2a | Sonnet |
| [WP-C6-SEC1](C6/WP-C6-SEC1-security-fixes.md) | Close F16, F2 timeout, F3, F5, F6, F7; `tests/security` green and back in the default run | M | – | nothing new | `service/`, `jev/factory.py`, `jev/http.py`, `tests/security/`, `tests/test_service_security.py` | yes (security) | 2a | Sonnet |
| [WP-C2-1](C2/WP-C2-1-lung-catalogue.md) | First catalogue `catalogue/lung-primary-care/`: migrate Finnish content (K2) and fill from R1/R2 | M | C1-1, R1, R2 | content | `catalogue/lung-primary-care/`, `params/sources.yaml` | yes | 2b | Sonnet |
| [WP-C1-3](C1/WP-C1-3-reference-generator.md) | Skeleton and error plan (P4) + reference generator (P8) | M | C1-1 | `generate_reference()` | `patient_engine/{skeleton,reference}.py` | no | 2b | Sonnet |
| [WP-C1-4](C1/WP-C1-4-validate-repair.md) | Validate and repair (P6) | S–M | C1-1 | `validate_card()` | `patient_engine/validate.py` | no | 2b | Sonnet |
| WP-C1-5 | Authors G1, G2 with prompts as data (P5) | M | C1-1, C1-2, C1-3 | `generate_library()` | `patient_engine/{authors,pipeline}.py`, `patient_engine/prompts/` | yes (I1) | 2c | Sonnet |
| [WP-C1-6](C1/WP-C1-6-library-cohort-reveal.md) | Library store, cohort assembly, reveal handle (P9) + CLI (P13) | M | C1-1, C1-3 | `library/1`, `cohort/1`, reveal | `patient_engine/{library,cohort,reveal,__main__}.py` | yes (I1, I3) | 2c | Sonnet |
| WP-C1-7 | Audit report (P7) | M | C1-1, C1-3 | audit JSON + Markdown | `patient_engine/audit.py` | no | 2c | Sonnet |
| WP-C1-8 | Adapter to `pathway_sim.Patient`, comparison report, card shown in the patient trace (P10) | M | C1-6 | – | `patient_engine/adapter.py`, `demo/` (card panel), `docs/patient_engine_comparison.md` | yes (headline) | 2c | Sonnet |

Wave 2b and 2c packages get their own files once WP-C1-1 has published the contract (their tickets
name its types). Until then the rows above are the scope.

## Dependency graph

```
WP-C1-1 ─┬─► WP-C2-1 ◄── WP-C2-R1, WP-C2-R2
         ├─► WP-C1-3 ─┬─► WP-C1-5 ◄── WP-C1-2
         │            ├─► WP-C1-6 ─► WP-C1-8
         │            └─► WP-C1-7
         └─► WP-C1-4 ─► WP-C1-5
WP-INFRA-1, WP-C6-SEC1: independent
```

## Shared files and who edits them first

| File | Rule |
|---|---|
| `patient_engine/__init__.py` | WP-C1-1 creates it. Others do not edit it in wave 2a; later packages add one import line each |
| `params/sources.yaml` | Only WP-C2-1 edits it. Research lanes list new sources in their notes file |
| `pytest.ini` | Only WP-INFRA-1. It keeps `--ignore=tests/security`; the integrator removes it after WP-C6-SEC1 is merged green |
| `docs/plan/04-status.md`, `docs/decisions.md` | Integrator only. Builders write decisions into their package file and report |

## Open questions posted

None new; the open ones are in `04-status.md` "Waiting for a human". Builders proceed on the leans:
`guided` error rates (V10, C1 Q1); English notes (C1 Q5); one co-existing illness, and none in the
Sunday slice (C1 Q6); headline numbers stay on the calibrated generator (C1 Q4).

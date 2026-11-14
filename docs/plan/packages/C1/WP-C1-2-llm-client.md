# WP-C1-2: Language-model client

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md`, P3 ("The language-model client") |
| Status | not started |
| Size | M |
| Needs | – |
| Provides | `patient_engine.llm`: `LLMClient`, `FakeLLMClient`, `Budget`, `CallLog` |
| Owned paths | `patient_engine/llm.py`, `tests/test_pe_llm*.py` |
| May create | the files above. Do **not** create `patient_engine/__init__.py` (WP-C1-1 owns it; the folder works as a namespace package until then) |
| Review required | yes: network calls, secrets |
| Track | submission |

## Outcome

`from patient_engine.llm import LLMClient; c = LLMClient.from_env(budget=Budget(max_calls=50, max_tokens=200_000), cache_dir='runs/llm_cache')`
then `c.complete_json(system, user, schema, key='card-17:g1')` returns a dict that validates
against `schema`, retrying with the validation errors on failure. Without `LLM_BASE_URL` set,
`from_env` raises a clear error and `FakeLLMClient(responses|fn)` serves tests. Every call is
logged (prompt hash, model, tokens, latency, outcome) to a JSON-lines file; a rerun with the same
cache directory makes no network call for prompts already answered.

## Why

Generation (WP-C1-5) needs this, and it is independent of everything else. Generation will run on
Tuomas's or Eemeli's machine where a key exists; this session has no endpoint, so the fake client
and the cache are what make the rest testable.

## Interfaces

**Provides** `LLMClient.complete_json(system: str, user: str, schema: dict, *, key: str,
temperature: float | None = None, max_repairs: int = 2) -> dict`, `LLMClient.map(requests,
concurrency=4)` (bounded concurrency with threads), `Budget` (calls, tokens; raising
`BudgetExceeded` before a call that would pass the cap), `CallLog` (path, append-only), a cache
keyed by sha256 of (model, system, user, schema, temperature). `FakeLLMClient` with the same
methods.

**Consumes**: environment `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (OpenAI-compatible
`/chat/completions`), like `technique_classifier/llm.py`. Read that file for the request shape;
**copy what you need, do not import Eemeli's package**.

## Acceptance (all machine-checkable)

- [ ] Against a local stub HTTP server started in the test (`http.server` on 127.0.0.1, random
      port), `complete_json` sends one OpenAI-style request with `response_format` json, parses
      the answer, validates it; with a first answer that fails the schema, it sends a second
      request containing the errors and returns the valid second answer (test).
- [ ] Retries with backoff on 429 and 5xx, honours `Retry-After`, gives up after N attempts with
      a clear error (test using the stub server; backoff patched to near zero).
- [ ] Budget: with `max_calls=2`, the third call raises `BudgetExceeded` before any request (test).
- [ ] Cache: a second client on the same cache dir answers the same request with zero HTTP calls (test).
- [ ] Call log: one line per call with prompt hash, model, tokens in and out if reported, latency,
      outcome; **never the API key**; the test asserts the key string is absent from the log and
      from every exception message.
- [ ] `map` with concurrency 4 over 10 requests completes and keeps result order (test).
- [ ] Standard library only for HTTP (`urllib.request`); schema validation via `jsonschema` if
      installed, else a minimal validator for type/required/enum/properties/items (say which).
- [ ] Tests run in under 15 seconds, offline.

## Out of scope

Prompts, card generation, choosing models, any real network call in tests.

## Things to look at and weigh

- `technique_classifier/llm.py` (111 lines): request and environment handling to copy.
- Not all OpenAI-compatible servers support `response_format: json_schema`; send
  `{"type": "json_object"}` by default with the schema in the system prompt, and allow
  `json_schema` mode by a flag. Strip markdown fences before parsing.
- Concurrency with `concurrent.futures.ThreadPoolExecutor`; the budget and log must be thread-safe.
- Proxies: the client must respect `HTTPS_PROXY` (urllib does by default) and a CA bundle from
  `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` if set.

## Tickets

| | ID | Ticket | Size | Needs | Done when |
|---|---|---|---|---|---|
| [ ] | C1-2-T1 | Request and parse against a stub server; `from_env`; fences stripped | S | – | stub test passes |
| [ ] | C1-2-T2 | Schema check and repair loop with errors fed back | S | T1 | repair test passes |
| [ ] | C1-2-T3 | Retry with backoff, `Retry-After`, give-up error | S | T1 | retry tests pass |
| [ ] | C1-2-T4 | Budget and cache | S | T1 | budget and cache tests pass |
| [ ] | C1-2-T5 | Call log without secrets; thread-safe `map` | S | T1 | log and map tests pass |
| [ ] | C1-2-T6 | `FakeLLMClient` with canned responses or a function; docstring example | S | T1 | used by one test |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|

## Report (builder fills in at the end)

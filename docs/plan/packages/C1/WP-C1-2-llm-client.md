# WP-C1-2: Language-model client

| | |
|---|---|
| Component | C1 `components/C1-patient-engine.md`, P3 ("The language-model client") |
| Status | done (w2/pe-llm) |
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

- [x] Against a local stub HTTP server started in the test (`http.server` on 127.0.0.1, random
      port), `complete_json` sends one OpenAI-style request with `response_format` json, parses
      the answer, validates it; with a first answer that fails the schema, it sends a second
      request containing the errors and returns the valid second answer (test).
- [x] Retries with backoff on 429 and 5xx, honours `Retry-After`, gives up after N attempts with
      a clear error (test using the stub server; backoff patched to near zero).
- [x] Budget: with `max_calls=2`, the third call raises `BudgetExceeded` before any request (test).
- [x] Cache: a second client on the same cache dir answers the same request with zero HTTP calls (test).
- [x] Call log: one line per call with prompt hash, model, tokens in and out if reported, latency,
      outcome; **never the API key**; the test asserts the key string is absent from the log and
      from every exception message.
- [x] `map` with concurrency 4 over 10 requests completes and keeps result order (test).
- [x] Standard library only for HTTP (`urllib.request`); schema validation via `jsonschema` if
      installed, else a minimal validator for type/required/enum/properties/items (say which).
- [x] Tests run in under 15 seconds, offline.

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
| [x] | C1-2-T1 | Request and parse against a stub server; `from_env`; fences stripped | S | – | stub test passes |
| [x] | C1-2-T2 | Schema check and repair loop with errors fed back | S | T1 | repair test passes |
| [x] | C1-2-T3 | Retry with backoff, `Retry-After`, give-up error | S | T1 | retry tests pass |
| [x] | C1-2-T4 | Budget and cache | S | T1 | budget and cache tests pass |
| [x] | C1-2-T5 | Call log without secrets; thread-safe `map` | S | T1 | log and map tests pass |
| [x] | C1-2-T6 | `FakeLLMClient` with canned responses or a function; docstring example | S | T1 | used by one test |

## Decisions made (builder fills in)

| Decision | Why | How to change |
|---|---|---|
| Budget counts one call per model request, repair rounds included; transport retries (429/5xx) do not count; cache hits are free | Retries are the endpoint's fault, repairs cost tokens | `Budget.reserve` / `_BaseClient.complete_json` |
| Token cap is checked before a call against tokens already used (a call may overshoot once) | Cost of the next call is unknown before it is made | `Budget.reserve` |
| Cache key = sha256(model, system, user, schema, temperature); the `key` argument is only a log label | As specified; same prompt answered once whatever its label | `_hash` use in `complete_json` |
| Only validated answers are cached; one file per hash in `cache_dir`, written atomically | A rerun continues where it stopped, bad answers are never replayed | `complete_json` |
| Call log defaults to `<cache_dir>/calls.jsonl`; one line per model request (outcomes ok, schema_invalid, not_json, http_error, budget_exceeded) plus one per cache hit | A repair is a visible second line | pass `log=` |
| `from_env` requires `LLM_BASE_URL` and `LLM_MODEL`; `LLM_API_KEY` optional | No silent default model; local servers need no key | `LLMClient.from_env` |
| Default `response_format` is `json_object` with the schema pasted into the system prompt; `json_schema_mode=True` switches | Not every server supports json_schema | constructor flag |
| Error bodies are scrubbed of the key; `repr(client)` omits it | A server can echo headers | `LLMClient._scrub` |
| Schema validation: `jsonschema` (Draft 2020-12) if installed (it is here), else a minimal type/required/enum/properties/items checker; `llm.VALIDATOR` says which | As specified | `validation_errors` |
| `map(..., return_exceptions=False)` raises the first failure in order after all finish | Deterministic; pass True to keep going | `_BaseClient.map` |

## Report (builder fills in at the end)

Public API: `LLMClient(base_url, model, api_key, *, budget, cache_dir, log, timeout, max_attempts,
backoff_base, backoff_max, json_schema_mode, max_tokens, default_temperature)`, `LLMClient.from_env(...)`,
`FakeLLMClient(responses|fn, ...)`, `.complete_json(system, user, schema, *, key, temperature=None,
max_repairs=2)`, `.map(requests, concurrency=4, return_exceptions=False)`, `Budget`, `CallLog`,
errors `LLMError` > `LLMConfigError`, `BudgetExceeded`, `LLMHTTPError`, `LLMOutputError`;
helpers `validation_errors`, `parse_json_text`, `VALIDATOR`.

Tests: `tests/test_pe_llm.py` (21 tests, about 2 s, offline stub server on 127.0.0.1). Not run: any
real endpoint (none here), so `json_schema` mode and real server quirks are untested.

How WP-C1-5 calls it: `c = LLMClient.from_env(budget=Budget(max_calls=..., max_tokens=...), cache_dir=...)`
(or `FakeLLMClient`), then `c.map([dict(system=..., user=..., schema=..., key="card-17:g1"), ...], concurrency=4,
return_exceptions=True)`; catch `BudgetExceeded` to stop cleanly and rerun with the same cache dir to continue.

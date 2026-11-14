# Spec 02: JEV interface

Milestone M1 (stub and contract), M6 (training and the real API). Depends on spec 01 for the word
"decision point". Open forks: F1, F2, F3 in `../README.md`.

## Purpose

JEV is the team's decision model. In the platform it is an API attached to the flowchart's decision
points: context and options in, a probability per option out. The simulator must run today without
it, so a stub with hardcoded probabilities implements the same contract. Swapping the stub for the
real JEV must be a configuration change, not a code change.

## Terms

- **Decision point**: a `decision` node in the flowchart (today's `choice` node).
- **Question**: which of the offered options comes next for this patient at this decision point.
- **Context**: everything revealed about the patient so far. Never the hidden condition or
  unrevealed results. This is today's `PatientView`.
- **Backend**: whatever answers the question: `stub`, `http` (the real JEV), `local` (the numpy
  model in `decision_model/`), `rule` (today's `RulePolicy`).

## The contract

One request, usable in-process and over HTTP. Batches are allowed everywhere.

```json
POST /v1/decide
{
  "model": "stub@1",
  "requests": [{
    "request_id": "p1042:sample_method",
    "decision_point": "sample_method",
    "question_type": "next_step",
    "context": {
      "group": "non_specific", "age": 67, "t_days": 31.5, "fast_track": false,
      "attributes": {"location": "peripheral"},
      "history": [
        {"step": "gp_visit", "test": "gp_assessment", "result": true, "t_days": 13.2},
        {"step": "ct", "test": "ct_chest", "result": true, "t_days": 30.9}
      ]
    },
    "options": [
      {"id": "bronch", "label": "Bronchoscopy", "test": "bronchoscopy",
       "features": {"invasive": true, "cost_eur": 1200, "lead_days": 6.0}},
      {"id": "ttnb", "label": "Needle biopsy", "test": "ttnb",
       "features": {"invasive": true, "cost_eur": 900, "lead_days": 2.0}}
    ]
  }]
}

200
{
  "model": "stub@1",
  "responses": [{"request_id": "p1042:sample_method", "probs": {"bronch": 0.2, "ttnb": 0.8}}]
}
```

Rules:

- `probs` covers exactly the offered option ids, non-negative, summing to 1 (the client
  renormalises within 1e-6 and rejects anything further off).
- `result` is `true`, `false` or `null` (inconclusive or not yet reported).
- `features.lead_days` is the queue state the engine already exposes (`option_leads`): days until
  the earliest appointment. The in-loop experiments showed a model that cannot see queues overloads
  the shortest-looking one.
- Option `features` come from the world's test catalogue. A backend may ignore them.
- The response may carry `"explanation"` per request (free text) for the UI; optional.

Other endpoints, same service:

| Endpoint | Purpose |
|---|---|
| `GET /v1/health` | liveness |
| `GET /v1/models` | available models: id, created, trained on, which context fields it reads |
| `POST /v1/train` | start training from a dataset (spec 06); returns a job id |
| `GET /v1/train/{job}` | status; on success the new model id |

**Question for the JEV owner (F3):** does JEV take structured context like this, or does it need
its own encoding (tokens, embeddings)? If the latter, the encoding lives inside the JEV service or
in a thin adapter next to it; the platform keeps sending this JSON.

## In-process interface (`jev/` package, new)

```python
@dataclass
class DecisionRequest:  request_id, decision_point, question_type, context: dict, options: list[dict]
@dataclass
class DecisionResponse: request_id, probs: dict[str, float], explanation: str | None = None
@dataclass
class BackendInfo:      name, model, deterministic: bool, context_fields: list[str] | None  # None = reads everything

class DecisionBackend(Protocol):
    def decide(self, requests: list[DecisionRequest]) -> list[DecisionResponse]: ...
    def info(self) -> BackendInfo: ...
```

`jev.BackendPolicy(backend)` adapts a backend to the engine's existing `Policy.choose(view, options)`,
building the request from `PatientView`. The engine does not import `jev`.

## The stub: hardcoded probabilities per decision point

Stored in the flowchart document as `decision_policy`:

```json
"decision_policy": {
  "backend": "stub",
  "mode": "sample",
  "points": {
    "first_contact": {"default": {"nurse_visit": 0.5, "gp_visit": 0.5}},
    "sample_method": {
      "default": {"bronch": 0.5, "ttnb": 0.5},
      "rules": [
        {"when": "location == 'central'", "probs": {"bronch": 0.9, "ttnb": 0.1}},
        {"when": "location == 'peripheral'", "probs": {"bronch": 0.15, "ttnb": 0.85}}
      ]
    }
  }
}
```

- `rules` are checked in order; the first whose condition holds wins; otherwise `default`.
  Conditions use the safe expression language of spec 01 over the same names guards see.
- If an offered option is missing from the table (for example it is unavailable today), the
  remaining probabilities are renormalised over what is offered.
- A decision point with no entry gets uniform probabilities and a `missing_probabilities` warning.
- Other backends: `{"backend": "http", "url": "...", "model": "jev-2026-11-15", "mode": "argmax"}`,
  `{"backend": "local", "model": "<registry id>"}`, `{"backend": "rule", "points": {...}}`.
- A per-point override is allowed (`"points": {"sample_method": {"backend": "http", ...}}`) so one
  decision point can use JEV while the rest stay on the stub.

Migration of today's scenarios (automatic, in the YAML importer): `mix` becomes a stub `default`;
`rules` with `choose` become stub rules with probability 1; `prefer` and `default` become
probability 1 on that option.

## Who picks: sampling in the engine (F2)

Today the engine takes the option with the highest probability, and `mix` hides its own random
draw inside the policy. That changes:

- `mode: "sample"`: the engine draws the option from `probs` by inverse CDF in the decision node's
  option order, using the common-random-number draw `uniform(seed, patient_id, "mix", node_id)`.
  The same patient facing the same probabilities at the same decision point therefore makes the
  same choice in every flowchart variant, which keeps before/after comparisons exact.
- `mode: "argmax"`: today's behaviour.
- The run log's `choices` entries gain `mode`, `backend`, `model`.

Acceptance: every shipped scenario reproduces its current metrics exactly after migration (the
key `"mix"` is kept for that reason; the importer reorders a node's options where an old `mix` was
listed in a different order).

## HTTP client and performance

A Finnish run asks about 40k questions; the event engine asks them one at a time, in simulated
time order.

- `jev.HttpBackend`: one keep-alive connection, configurable timeout (default 2 s), retries once.
- Cache: when `info().context_fields` is declared, responses are memoised on
  (decision point, those fields, offered options). The stub declares its fields from its rules, so
  it caches almost perfectly. A model that reads `t_days` or `lead_days` caches poorly; that is
  expected.
- On failure: `on_error: "fail"` (default; the run stops with a clear message) or
  `"fallback_stub"` (use the stub table, count the fallbacks in the run summary). Never silent.
- Target: a Finnish run through the stub server on localhost at most 3 times slower than
  in-process. If the real JEV is slower than that allows, options are a batch-per-tick mode in the
  engine or loading the model in-process; decide when we have a number.

`jev.stub_server` (`python -m jev.stub_server --flowchart … --port 8100`) serves the stub over the
HTTP contract so the whole network path can be tested before the real JEV exists.

## Contract tests

`tests/test_jev_contract.py`, runnable against any URL
(`pytest tests/test_jev_contract.py --jev-url http://…`): shape, probabilities sum to 1, only
offered options, batch order preserved, unknown decision point handled, determinism when
`deterministic` is declared, latency report. The JEV owner runs the same file against their service.

## Build order

1. Contract dataclasses, JSON examples, `BackendPolicy` (M1-1).
2. Engine sampling mode with the common-random-number draw (M1-2).
3. `StubBackend` and YAML migration; all shipped scenarios reproduce (M1-3).
4. Stub server, `HttpBackend`, cache, error modes (M1-5); contract tests (M1-6).
5. `LocalBackend` around `decision_model` (M1-7); CLI flags (M1-8).

## Not decided here

- Which nodes become decision points beyond today's (F1).
- How JEV is trained on outcomes rather than imitation (decision D25, spec 06).

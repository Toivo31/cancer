# Hosted decision API: teammate and coding-agent quick start

Base URL: **https://cancer123--birch-decision-1138-demo.us-east.modal.run**

Open `/decision` for the ready-made review panel. No Modal account, token, GPU
setup, inference API key or local private file is required. The gateway holds
the private inference credential. Use synthetic demo data only.

## In the project

Pull this integration, then run:

```bash
python3 -m decision_api.server
```

Open http://127.0.0.1:8771/decision. Existing `/api/decision/*` mounts in the
project use the hosted gateway automatically when no local inference key is set.
Saved examples load locally in fixture mode; the hosted gateway serves the same
recorded examples without starting a GPU. Run live inference explicitly.

For an agent or Python code, with no dependencies:

```bash
python3 -m decision_api.agent --saved
python3 -m decision_api.agent
python3 -m decision_api.agent --reason --tokens 128 --instructions 'Give a quick evidence review.'
```

Or import `decision_api.agent.call('/reason', payload)`. It polls the accepted
job and returns the completed result. A custom request file can be passed with
`--request visible-case.json`; tools are disabled for custom patients because
the bundled synthetic record is unrelated to them.

For the quickest webpage integration, embed the working interface (saved examples
load by default; no upload UI and no automatic GPU call):

```html
<iframe title="Decision review" loading="lazy" style="width:100%;height:1000px;border:0"
  src="https://cancer123--birch-decision-1138-demo.us-east.modal.run/decision"></iframe>
```

For a webpage, use the SDK from this repo:

```js
import {createDecisionClient} from './decision_api/client.js';
const api = createDecisionClient({
  baseUrl: 'https://cancer123--birch-decision-1138-demo.us-east.modal.run/api/decision'
});
const result = await api.reason({
  example_id: 'pathway',
  reasoning: {enabled: true, max_tokens: 128, additional_prompt: 'Give a quick evidence review.'}
});
// Render result.refinement.context/trace and result.decision.questions.
```

CORS permits browser calls without credentials. The SDK polls automatically;
reasoning defaults OFF unless explicitly enabled. Build a human-facing interface
with questions, allowed options, all scores and separate accept/correct review.
Never ask users for raw JSON, upload files, send previous decisions/scores back
as evidence, or advance a simulator from a model proposal without human review.
Use the bundled medical pictures, attribution and recorded examples.

## HTTP contract

All paths below start with `/api/decision`:

| Method | Path | Use |
| --- | --- | --- |
| GET | `/examples` | Request templates and capability flags; no GPU |
| GET | `/examples/pathway/decision` | Recorded result; no GPU |
| GET | `/examples/example-1/decision` | Recorded photo result; no GPU |
| POST | `/reason` | `{example_id:"pathway", reasoning:{enabled:true,max_tokens:128}}`, or `{request, reasoning}` |
| POST | `/score` | `{context, questions:[{id,text,choices:[{id,text}]}]}` |
| POST | `/pathway` | Existing `{case,workflow,node_id,history?}` contract |
| POST | `/samples/example-1/score` | Score an allowlisted bundled picture; no upload |
| GET | `/health` | Explicitly start/check native model |
| GET | `/decisions/{id}` | Exact native decision trace |
| POST | `/decisions/{id}/review` | Separate human correction/acceptance |
| GET | `/jobs/{id}` | Poll an accepted job |

Quick live operations can return HTTP200 directly. Longer operations return HTTP202 with `{delivery:"pending", job_id, status_url}`.
Poll `GET /api/decision` + `status_url` about once per second. Completion returns
HTTP200 and the normal endpoint result; failure returns its HTTP error/detail.
Do not replay a POST while its job is pending. Cold loading can take several
minutes. Allow 660 seconds overall. Jobs expire after 30 minutes and are
in-memory; a gateway restart may lose an outstanding job. Look up an existing
decision when its ID is known; do not blindly repeat review/scoring writes.
Cancelling the browser wait does not cancel an accepted inference job.

There is one GPU, concurrency one, and at most three accepted jobs outstanding.
The public demo gateway limits submissions to six per minute / 120 per hour per
gateway process. These reset on restart and are not a billing cap. Local
metadata, saved results and job polling do not consume submission slots.

`reasoning.max_tokens` is a total generation budget (0–512), not per tool round.
Default128; up to3 rounds/2 tools by default. `max_tool_calls:0` enables text
refinement without synthetic patient tools. Custom cases requiring tools must
supply an explicitly authorized binding; currently only `sim:demo-record` at
step0 or1 is available. Do not bind arbitrary simulator patients to that record.
The model generates an evidence summary using the original pretrained Nemotron
head and unadapted suffix, sharing frozen prefix weights with the classifier.
Tool calls are validated and actually executed; raw generated text is never
executed. Only visible tool results can enter the final scoring context.

## Existing simulator Birch adapter

The teammate's `jev.birch.BirchBackend` on `overnight/sim` expects synchronous
responses from a localhost proxy and deliberately rejects raw Modal URLs.
Keep its URL at `http://127.0.0.1:8771`: the updated secretless local proxy waits
for the hosted job and returns its usual decision object. The older adapter defaults to step1138 in its metadata and does not separate its cache by checkpoint. Use the included bridge without changing
teammate-owned `jev/` files:

```python
from decision_api.jev_bridge import backend, policy
model = backend()  # localhost8771, checkpoint2350, timeout660
# Or: model_policy = policy(world, max_calls=20)
```

The bridge separates the cache by checkpoint/hash, rejects cached1138 results, and verifies live step/hash before accepting scores. If using `BirchBackend` directly, set checkpoint2350 and timeout660 and use a new checkpoint-specific cache directory.
Its older defaults are checkpoint1138 and timeout160seconds. Keep the existing call budget/cache/visible-record checks. This
migration does not alter simulator state or bulk-run model scoring.

## Owner deployment

```bash
/home/toivo31/Junction_hackathon/cancer/.venv/bin/modal deploy decision_api/modal_inference.py
```

Only the owner needs Modal credentials and the existing `birch-inference`
secret. `runtime/decision_model/` is an isolated inference source snapshot,
with the reference branch enabled; it does not overwrite teammate model code or
any training working tree. Checkpoint2350 remains pinned and checksum-verified.
The inference URL remains authenticated. The public gateway has no image upload
route and keeps the API key server-side. Overnight pausing remains with the
team; no schedule has been installed.


## Checkpoint selection

Live scoring now pins `birch07-refine-v3/checkpoint-00002350`, with trainable SHA256
`22570c201a9e3d25dcdf7aa904770a568328e034ccb5ac89623784707a7323e8`.
The legacy app/URL name contains1138 for compatibility; use response
`backend.step` and `checkpoint_sha256` for the actual identity. The default saved examples and native reasoning recording have been refreshed with actual2350 outputs. Original1138 recordings are retained in `web/precomputed-1138.json` and `web/precomputed-reasoning-1138.json`; never relabel them as2350. The2366 experimental reasoning
pilot was considered but its paired raw check fell from29/40 to25/40;2350 was
chosen for this demo. This small screen does not prove general model quality.


Deployment checks and limitations: [validation/README.md](validation/README.md), with the recorded2350 provenance and GPU report in `validation/step2350.json`.


## Efficient inference

Reasoning stays off by default. When enabled, a bounded64-entry in-memory cache
reuses deterministic pretrained-head outputs only for an identical complete
message history and remaining token budget. Actual patient tools execute again;
changed source results invalidate the generated summary. `tokens_used` charges
the output budget even on a cache hit; `tokens_generated` reports actual new
model tokens, and `generation_cache_hits` identifies reuse in the UI/trace.

The classifier continues to reuse bounded context/candidate embeddings while
creating a new decision and audit record. Registered IDs for the three fixed
images are reused, avoiding duplicate file writes and preparation round trips.
The gateway returns completed fast calls directly instead of forcing a job poll.

An experimental batching path changed some relative scores by up to0.0127 in
the synthetic checks. It was removed; production retains the original independent
encoding shapes. Fresh-context generation and scale-to-zero cold starts still
have their original model-compute/startup costs.

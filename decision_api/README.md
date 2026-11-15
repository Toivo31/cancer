> **Hosted access:** teammates need no Modal account or inference key. See [HOSTED_API.md](HOSTED_API.md) for the URL, SDK and one-command agent client.

# Decision model: teammate integration kit

**For the coding model implementing the demo: start with [INTEGRATION_PROMPT.md](INTEGRATION_PROMPT.md).**

This folder is an adapter to the already deployed model. Your frontend does not
load weights, install Torch, train anything, or manage GPUs. It renders an
interface and sends **visible information + a question + allowed choices**.

## Try it immediately — no key, no GPU, no dependencies

From the repository root, Python 3.10+:

```bash
python3 -m decision_api.server
```

Open **http://127.0.0.1:8771/decision**. The page loads **recorded model outputs**
instantly, with the original scores, checkpoint and timestamps. Three original
PAD-UFES-20 medical images and a synthetic pathway example are bundled. No uploads.

The existing project server also serves the panel at `/decision` and the proxy
at `/api/decision/*`:

```bash
python3 -m pip install -r requirements.txt
python3 -m note_reader.server --port 8770
```

The flowchart's **Decision model** link opens the reference panel. The simulator,
note reader and their existing estimates are not driven or overwritten by this
adapter. Your team decides how to connect a reviewed choice to simulator state.

## Add it to your own page

Use the JavaScript client if you already have components:

```js
import {createDecisionClient} from './decision_api/client.js';
const api = createDecisionClient(); // same-origin /api/decision proxy

// Run this on a user action, not every render, animation frame or patient tick.
const decision = await api.score({
  case_id: patient.id,
  context: visiblePatientSummary,
  questions: [{
    id: node.id,
    text: node.question,
    choices: allowedActions.map(a => ({id: a.id, text: a.description})),
  }],
});

// Use your own UI; retain IDs when rendering or recording a review.
renderChoices(decision.questions[0].choices);
highlightProposal(decision.questions[0].proposed_action_id);
// A person chooses. Never execute a model proposal automatically.
await api.review(decision.id, {
  question_id: node.id,
  action_id: humanSelectedActionId,
  reviewer: reviewerLabel,
  note: optionalReviewNote,
});
```

Or embed the optional, framework-independent reference panel:

```html
<script type="module" src="/decision-assets/widget.js"></script>
<birch-decision api-base="/api/decision"></birch-decision>
```

When importing with a bundler, `import './decision_api/widget.js'` registers the
same element. Set `element.request = scoreRequest` or `pathwayRequest` to show
one of your own patient/workflow states. Use a ref in React to set that property.
The panel discards stale results when the current patient/request changes.
For your own asynchronous UI, pass `{signal: abortController.signal}` and ignore
responses for a patient that is no longer selected.

Events bubble from the panel:

- `decision-result`: `{delivery, decision}`. Delivery is `live`, `precomputed`, or `fixture`.
- `decision-review`: `{delivery, persisted, review, decisionId, caseId}`.
  Comparing a saved example stays local (`persisted=false`); it does not POST
  an old decision back to the model or create a training label.

CSS variables `--decision-font`, `--decision-ink`, `--decision-background` and
`--decision-border`, plus `::part(panel)` / `::part(choice)`, support restyling.
The client has TypeScript declarations and no npm dependencies or build step.

## Ready-made pictures and recorded examples

```js
const examples = await api.examples();             // local; no GPU
const saved = await api.precomputed('example-2');  // local; no GPU
renderSaved(saved.decision, saved.recorded_at);    // label “Saved example”
const live = await api.scoreExample('example-2');  // explicit new model call
```

IDs: `pathway`, `example-1`, `example-2`, `example-3`. Pictures, published patient
context and attribution are in `web/samples/`. Recorded real outputs are in
`web/precomputed.json`; they are not fabricated fixture scores. Keep **Saved
example / Live model / Scripted fixture** visible. A live error remains an error;
showing saved data must be an explicit user choice, not a silent fallback.

The local proxy's picture endpoint registers the bundled image on the model
server and supplies its opaque image ID. The browser never uploads photo bytes.
Do not add upload controls to the project demo.

## Enable live inference

The owner shares the inference key **out of band**. Do not put it in Git, a
browser bundle, `VITE_*`, `NEXT_PUBLIC_*`, or screenshots. The proxy reads
`BIRCH_API_KEY` or `BIRCH_API_KEY_FILE`. On the owner's laptop the default file
is `~/.config/birch/demo-api-key`.

```bash
BIRCH_API_KEY_FILE=/private/path/to/key python3 -m decision_api.server
```

`BIRCH_API_URL` defaults to the stable authenticated Modal endpoint (live checkpoint2881). Only
root HTTPS Modal URLs are accepted. For the existing note-reader server, its
root `.env` loader can supply the same variables. See [.env.example](.env.example).
Restart the proxy after changing configuration. No key is needed for saved data.

The proxy binds localhost in standalone mode. When mounting it in a hosted app,
use the app's authentication and set `BIRCH_ALLOWED_HOSTS` to your demo hostname.
For a different backend stack, reuse the route table below and keep the bearer
credential exclusively server-side.

### Proxy routes

| Your frontend calls | Meaning / upstream |
| --- | --- |
| `GET /api/decision/examples` | Bundled input examples and picture catalog; local |
| `GET /api/decision/examples/{id}/decision` | Recorded output; local, includes `delivery=precomputed` |
| `GET /api/decision/health` | Explicit live call to `/healthz` |
| `POST /api/decision/score` | Same JSON as `/v1/score` |
| `POST /api/decision/pathway` | Same JSON as `/v1/pathway/propose` |
| `POST /api/decision/samples/{id}/score` | Prepare a bundled photo and score it; optional context/questions/case_id overrides |
| `GET /api/decision/decisions/{id}` | Exact visible input, scores and provenance |
| `POST /api/decision/decisions/{id}/review` | Human-selected choice; append-only review |

Sample pathway payload: [web/pathway.json](web/pathway.json). Generic scoring
payload: [web/score.json](web/score.json). Preserve `candidate_format=inline` for
the binary photo task; ordinary questions default to `newline`. Stable choice
IDs identify actions; array positions do not. The pathway endpoint validates
actual graph edges and history, excludes future observations and never advances
a simulator. Generic scoring requires callers to supply visible context only.

## Runtime, pausing and limitations

The reasoning-enabled runtime uses one RTX PRO6000 with NF4 experts (~78.3GiB loaded). The stable URL retains1138 in its name; live identity is checkpoint2881.
Observed warm text scoring median ~7.4s; a cold start took ~6minutes. The browser
shows errors and allows manual retry. No automatic POST retry, health polling,
or background keepalive is installed. Modal scales down when idle.

Overnight pausing is managed by the owner/team; **no schedule is installed**.
`BIRCH_DECISION_PAUSED=1` blocks this proxy's live requests; already-running work
can finish and the GPU then idles down. This flag does not disable direct calls
from other clients to the Modal API. Saved examples remain available.

Scores are relative candidate softmax scores, not disease probabilities, test
sensitivities, or expected pathway time reductions. Do not replace the existing
simulator's published/assumed test sensitivities with these values. Proposals
are experimental and always need review. The small sanity run agreed with17/27
source text labels; at least one source label is inconsistent with its passage.
All3bundled images matched their labels even without images, so they do not
establish useful photo understanding. Images are training examples, not a
held-out evaluation. No training or clinical action is started by this package.

## Test without paid inference

```bash
python3 -m unittest discover -s decision_api/tests -v
node --test decision_api/tests/client.test.js
```

For scripted API-contract testing only, `python3 -m decision_api.server --fixture`
provides explicitly labelled fixture responses for the bundled questions. Unknown
questions fail. Fixture reviews exist only in memory. Recorded real examples
remain a separate, labelled playback path in all modes. The tests never call Modal.

## Follow-up: optional shared-Nemotron context refinement

See **[handoff 2](REASONING_HANDOFF.md)** for the coding model implementing the
next step. Refinement is off by default. Enabling it appends the question and
optional extra instructions, uses a total new-token budget, permits bounded
patient-record retrieval and then scores the refined context.

The intended generator is the original frozen Nemotron vocabulary head and
unadapted suffix sharing the decision model's frozen prefix. It is not a second
LLM service. The native runtime helper and owner patch are prepared; the live
GPU server has not yet been updated or validated for generation. Until its
preflight succeeds, the reference panel offers an explicitly scripted tool-flow
preview with real local synthetic retrieval, without making a model call.
Existing saved outputs and normal scoring remain unchanged.

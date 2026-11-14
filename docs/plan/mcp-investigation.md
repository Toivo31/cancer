# Should we add an MCP server? Investigation and tentative plan

Status: investigation, 14 Nov 2026 (Saturday evening). Author: lane `w4/mcp-plan`. No product code was written or changed.
Decision wanted from Tuomas: yes or no, and when.

## 1. Verdict

**Worth building, but not as part of the entry. Do it after Sunday 10:00 Helsinki.**

- It would work. The pieces MCP needs (JSON in, JSON out, jobs with polling, a token, rate limits) already exist in `service/`, and the official Python SDK can wrap them in a few hundred lines.
- It does not move the judging weights (actionability 30, insight 25, data quality 20, execution 15, clarity 10). The platform already has a web app for the demo, and a judge is far more likely to have a browser than an MCP client. Every hour on it before the deadline is an hour not spent on the evidence and review items that carry the other 75 percent (see `docs/platform/README.md` section 5, note on F6).
- The one exception worth considering: a **2 to 3 hour spike (tickets MCP-1 and MCP-2 only)** by an agent that would otherwise be idle, kept out of the demo path and out of the submitted instructions. It is useful to Tuomas and the team for exploring scenarios from a chat client tonight. Do not mention it in the pitch unless it is solid.

Two findings that change the design, found while reading the code (section 4):

1. **The headline scenario is not reachable through the service.** `finland_encounter.yaml` runs only through the CLI and `pathway_sim.encounter.run_encounter`. `grep -i encounter service/` finds nothing. An MCP that only wraps the HTTP service would cover the older flowchart scenarios (`finland_lung`, `stokstad`), not the encounter loop that the team is tuning now.
2. **The existing HTTP API already returns hidden truth.** `PatientRun.to_dict()` (`pathway_sim/engine.py`) includes `condition` and `cancer`, and `GET /api/projects/{p}/runs/{r}/patients` serves it. That is fine for the web app's trace view, but an MCP that forwards this to a language model would break the information boundary (invariant I1 in `docs/plan/01-architecture.md`). The MCP needs its own filter; it cannot just proxy.

## 2. Who would use it, and for what

| User | Use | Value | Honest comment |
|---|---|---|---|
| Tuomas in a chat client | "Run the encounter scenario with 500 patients, then with the nurse step removed, and tell me what moved." | High for exploration; saves writing curl or YAML by hand | Needs a client that speaks MCP; Claude Code and Claude Desktop do |
| JEV owner | Inspect decision records: "show 5 decisions at the GP referral point, what context did the model see, what probabilities came back" | Medium; `/decisions` and `/decide` already exist as HTTP | The MCP adds convenience, not capability |
| Judge demo, "ask the simulator" | A judge types a question and the simulator answers | Low before submission: judges need an MCP client and a reachable server, and any failure is visible on stage | A scripted web demo is safer. Revisit as a recorded clip once it is solid |
| Agents in this repo | Run, compare and read results without shelling out and parsing stdout | Medium; but agents already have the CLI and `python -m pytest` | The CLI is already agent-friendly. The MCP wins on structured results and guarded access, not on reach |

Net: the clearest user is Tuomas himself, plus anyone later who wants to put the simulator inside an LLM workflow without writing client code.

## 3. What MCP gives us (from the primary sources)

Read: the MCP specification (version 2025-11-25; a 2026-07-28 revision also exists, I read its draft authorization page) and the official Python SDK docs.

- **Tools** are model-controlled, have a JSON-Schema `inputSchema` and an optional `outputSchema`; results can carry text, images, resource links and `structuredContent`. Errors split into protocol errors and tool execution errors (`isError: true`) that the model can use to retry. Servers must validate inputs, apply access controls and rate limit. [Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools.md)
- **Resources** are application-driven, identified by URI, listable and readable, with URI templates for parameterised ones. They suit catalogues and reports a user or client attaches as context, rather than something the model calls. [Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources.md)
- **Prompts** are user-controlled templates, typically surfaced as slash commands. [Prompts](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts)
- **Transports:** stdio (client launches the server as a subprocess; stdout must carry only MCP messages) and Streamable HTTP. For HTTP the spec says servers MUST validate the `Origin` header, SHOULD bind to localhost when local, and SHOULD authenticate. [Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md)
- **Auth:** optional. HTTP servers that do it SHOULD follow the OAuth 2.1 based flow; stdio servers SHOULD instead take credentials from the environment. [Authorization](https://modelcontextprotocol.io/specification/draft/basic/authorization) The Python SDK supports the resource-server side with a `TokenVerifier`; it applies to HTTP only. [SDK authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/)
- **Long-running work:** progress notifications are optional and the receiver may send none. [Progress](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress.md) A "tasks" mechanism (create, poll with `tasks/get`, fetch with `tasks/result`) was added in 2025-11-25 and is labelled **experimental**. [Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks.md) I could not confirm which clients support it, so the design below does not depend on it.
- **Structured output:** in the Python SDK the return type annotation becomes the `outputSchema`, and a pydantic model or `TypedDict` is returned as the structured object; the SDK validates the result against the schema. [SDK structured output](https://py.sdk.modelcontextprotocol.io/servers/structured-output/)
- **Mounting:** `mcp.streamable_http_app()` returns a Starlette app that can be mounted inside FastAPI; the host app must run `mcp.session_manager.run()` in its lifespan. [SDK ASGI](https://py.sdk.modelcontextprotocol.io/run/asgi/)
- **Result size:** I found no size limit in the spec. Limits are set by clients and by the model's context, and I did not verify any client's number. Design assumption: keep a tool result to a few kilobytes and hand back a URI for anything bigger.
- **Install:** `pip download mcp` resolved cleanly here on Python 3.13 (it pulls `starlette`, `httpx`, `anyio`, `sse-starlette`, `uvicorn`, `pyjwt`, `cryptography`), so it fits next to FastAPI. The SDK's docs now name the server class `MCPServer`; older material says `FastMCP`. Pin a version at install time and check the name against it.

## 4. What exists in the repo that the MCP would sit on

- **Service** (`service/`): projects, flowchart documents with versions, `POST /validate`, `POST /runs` (jobs as child processes, polled through `GET /jobs/{j}`, same request returns the cached run), `POST /compare`, `POST /optimisations` plus `apply`, `POST /decide`, datasets and models, `GET /api/templates`. One shared bearer token (`PATHWAY_ACCESS_TOKEN`), 600 requests per minute, 6 job starts per minute, caps on patients (`PATHWAY_MAX_PATIENTS`), seeds and job seconds. Hosted modes include `PATHWAY_PUBLIC_READ` and `PATHWAY_READ_ONLY` (`docs/platform/runbook.md`). The security review (`docs/platform/security-review.md`) fixed the SSRF, size and traceback holes; the MCP inherits those if it goes through the service.
- **Encounter loop** (`pathway_sim/encounter.py`, `scenarios/finland_encounter*.yaml`): CLI only. I ran `python -m pathway_sim run scenarios/finland_encounter.yaml --flowchart encounter --n 500 --seed 1`: it printed a result summary in 11.1 s (4 cancers in 500 patients, 0.25 treated, per-group table). Eleven seconds for 500 patients means a synchronous tool call is borderline; runs of 2,000 or more must be jobs.
- **Patient engine** (`python -m patient_engine design|generate|library-info|cohort|show`): `show` already has the boundary built in, printing the public view unless `--hidden` is given (`patient_engine/reveal.py`, `RevealHandle`). `audit` (WP-W4-3) is still in flight in another lane, so `audit_library` cannot be promised yet.
- **JEV** (`jev/`): the contract and `POST /decide` exist; the real JEV is not part of this.

## 5. Design sketch

### 5.1 Shape: two layers, one server

- **Platform tools go through the HTTP service** (a thin client with `httpx`, base URL and token from environment). This reuses auth, limits, caching of identical runs, job isolation and the SSRF guard. The MCP adds no new simulation logic, in line with the platform rule "the service only orchestrates".
- **Encounter and patient-engine tools run in process** (import `pathway_sim.encounter` and `patient_engine`) inside a worker subprocess with its own time limit, because the service does not expose them. This is the part that costs effort; the clean fix is a later service ticket that registers encounter worlds as a run kind, after which the MCP drops its in-process path.
- Rejected: direct in-process for everything. It would duplicate the job runner, the limits and the token check, and would be the second place to harden.

### 5.2 Tools (names are suggestions; every one has an `outputSchema`)

Read-only, safe by default:

| Tool | Does | Result |
|---|---|---|
| `list_scenarios` | Service templates plus `scenarios/*.yaml` worlds, with one-line descriptions | list of `{id, kind, description, default_n}` |
| `describe_world` | Steps, resources, decision points, key parameters of one scenario, each parameter marked sourced or assumption (from `params/sources.yaml`) | compact structured summary, not the YAML |
| `validate_flowchart` | Calls `/validate` on a document or scenario edit | `{ok, problems[]}` |
| `get_run_summary` | Headline metrics, by-group table, utilisation for a finished run | the `headline` object and short tables |
| `compare_runs` / `compare_flowcharts` | `/compare` on runs with the same patients; refuses otherwise (the service already returns `409 different_patients`) | deltas per metric and group |
| `get_decisions` | A page of decision rows at one decision point (context, offered, probabilities, chosen); revealed side only | at most 20 rows per call |
| `get_patient_record` | One patient's revealed record: background, presenting symptoms, the tests and results the pathway revealed, route and times | revealed fields only (5.4) |
| `library_info`, `show_card` | Wrap `patient_engine library-info` and `show` without `--hidden` | manifest, public card view |

Start work, bounded:

| Tool | Does | Limit |
|---|---|---|
| `start_run` | Service `POST /runs`, or an in-process encounter run in a worker; returns `run_id` at once | n up to 1,000 on the default tools; larger needs the explicit `PATHWAY_MCP_ALLOW_LARGE` setting; the service caps still apply |
| `get_run_status` | Status, progress, message; the poll partner of `start_run` | |
| `cancel_run` | Cancel | |
| `propose_optimisation` | Service `POST /optimisations`; returns an id, then poll with `get_optimisation` | the service job limit (15 minutes) applies; use a low n |
| `apply_optimisation` | The service `apply`, which saves a new flowchart version and optionally reruns | Writes data; disabled in read-only mode |
| `generate_library_fake` | `patient_engine generate` with the fake author only, never a paid model | the model-written path costs money and stays off by default |

Run a short run synchronously only when n is small enough to finish in a few seconds; otherwise return the id. Many clients let the model call the tool again, and all of them can poll with a plain tool, so polling does not depend on the experimental tasks feature. `ctx.report_progress` can be added where a client shows it, since it does nothing without a callback.

### 5.3 Resources and prompts

- Resources (attachable context, not model-called): `catalogue://lung-primary-care` (condition list and counts), `scenario://finland_encounter` (the scenario doc as markdown), `run://{run_id}/report` (the same short text the CLI prints, plus a link to the dashboard bundle), `docs://ledger` (evidence ledger). Size note: serve summaries, with a resource link to the full bundle.
- Prompts (user-picked, like slash commands): `explore_scenario` (describe the world, run a baseline, report what drives delay), `what_if` (arguments: scenario, change; run baseline and variant on the same patients, compare, say what is within noise), `audit_a_run` (check the guardrails: missed cancers, equity by group, tests per patient), `explain_decision_point`. Prompts should push the model to quote numbers from tool results and to state seeds and n.

### 5.4 Transport and hosting

- **stdio first.** The client launches `python -m pathway_mcp` with `PATHWAY_API_URL` and `PATHWAY_ACCESS_TOKEN` in the environment, which is what the spec recommends for stdio. Nothing is exposed on the network. This covers Tuomas and the repo's agents.
- **Streamable HTTP second**, mounted at `/mcp` in the existing app or as its own small process, for the hosted box. Needs Origin validation, localhost binding unless behind Caddy, and authentication. The honest wrinkle: the spec's HTTP auth is OAuth 2.1 shaped, and I expect (not verified) that clients which discover servers by themselves, such as hosted connectors, want that flow, while clients that let you set a static `Authorization` header can reuse the shared token. Reusing the platform token is cheap; real OAuth is an extra day and not justified for this event.

### 5.5 Long runs and result sizes

`start_run` returns within a second. The model polls `get_run_status` (the service suggests polling about once a second; an MCP tool should sleep up to a few seconds inside the call to avoid dozens of model turns). A finished run is summarised in at most a few KB; the per-patient log, decisions and bundle are reached by paged tools (`limit` at most 20) or by resource links. Nothing returns a raw log.

## 6. Safety

- **Information boundary (I1).** Default tools return only the revealed side. Concretely: strip `condition`, `cancer` and any field derived from the hidden card from run logs before they leave the MCP (an allowlist of output fields, not a blocklist, so a new field does not leak by default); build patient records through the engine's `RevealHandle` (`truth_for_scoring` is never called); add a test that scrambles hidden truth in a run and checks the MCP output for the revealed tools is byte-identical, in the style of the existing optimiser test `test_proposal_scores_ignore_hidden_truth`. I have not verified that the event `result` fields in run logs are measured rather than true values; ticket MCP-3 starts with that audit.
- **Teaching mode** (`show_truth`): set by the operator through an environment variable at server start, never a tool argument the model could set; absent on the hosted instance; every result in that mode is labelled `HIDDEN TRUTH, teaching only` in both the text and the structured field; documented as not for decision work. Without it, truth tools simply do not appear in `tools/list`.
- **Untrusted text.** Model-written patient cards (WP-C1-5) put LLM-generated free text into tool results that another LLM then reads. The data is synthetic, but the injection path is real; treat card text as data, wrap it in a clearly delimited field, and do not let any tool take actions based on text inside results.
- **Credentials and rate limits.** Reuse `PATHWAY_ACCESS_TOKEN` and the service's limits (the MCP's calls hit the same 600 requests and 6 job starts per minute); the in-process encounter path needs its own cap (one concurrent worker, 60 s, n at most 1,000), because it bypasses the service's limits.
- **No arbitrary code.** No tool takes a Python expression, a path or a URL. Scenario edits arrive as the existing structured document and go through the service's safe expression evaluator; scenario names are an allowlist of known ids, never a path (the security review's F10 and F11 are the precedent).
- **Synthetic data only.** Same notice as the platform (`/api/access` `data_notice`); the MCP refuses dataset upload tools in this version.
- **Human in the loop.** The spec says clients SHOULD show tool calls to the user for confirmation. Mark the read-only tools with the read-only annotation and the write tools (`apply_optimisation`, `generate_library_fake`) without it, but note that annotations are untrusted by spec, so the real control is the server-side mode, not the label.

## 7. Cost, risk and comparison

**Build effort (agent hours, includes tests; one competent agent):**

| Part | Hours |
|---|---|
| Skeleton, service client, stdio entry, 5 read tools | 3 |
| Run, poll, cancel, compare, optimisation | 4 |
| Record and decision views with the boundary filter and the scramble test | 3 |
| Encounter and patient-engine in-process path with worker, caps | 4 |
| Resources and prompts | 2 |
| HTTP mount, Origin check, token, Caddy and runbook entry | 4 |
| Total | about 20 hours, 2 to 3 agent days |

**Maintenance.** Each new tool is a second public surface to keep in step with the service and the contracts (`card/1`, `catalogue/1`, `jev`). Tool schemas change when the service changes; one contract test per tool against `TestClient` keeps this honest. The SDK is moving (class rename `FastMCP` to `MCPServer`, spec revisions every few months), so pin it.

**Testing.** The SDK ships an in-memory client; run every tool against the service `TestClient` with a temp data directory. Add a leakage test and a limits test. About a third of the hours above.

**Demo risk.** High if it is in the live path (client availability, network, a model choosing odd arguments, 11 second runs). Low if it stays an internal tool. Hence the recommendation not to put it in the pitch before it has survived a week of use.

**Alternatives**

| Option | Strength | Weakness vs MCP |
|---|---|---|
| Existing HTTP API with OpenAPI (`/docs`, `/openapi.json`) | Already built, tested, hardened, 39 paths | An LLM client must read a large schema and chain 5 to 8 calls; no filtering of hidden fields; no prompts or resources; any LLM tool-use framework can import OpenAPI, so for agents it is nearly as good |
| CLI (`python -m pathway_sim`, `patient_engine`) | Works today for agents and Tuomas; prints readable summaries | Free text output, no structure, no job handling, each call re-loads the library (the 11 s) |
| Notebook | Best for plots and one-off analysis, easy to share | Not interactive from a chat client; needs a kernel and local setup |
| A single `scripts/ask.py` helper that runs a scenario and prints compact JSON | An hour of work; gets about 60 percent of the agent value | Not discoverable by chat clients, no safety layer |

Honest ranking for the next 16 hours: the CLI and the web app already cover the entry. The MCP wins on one thing only: a non-technical person (or a model) can drive the simulator by describing what they want, with the boundary enforced by the server instead of by a prompt.

## 8. Tickets (if yes, after the deadline; MCP-1 and MCP-2 as an optional spike tonight)

Package under `pathway_mcp/` (new), tests in `tests/test_mcp_*.py`, one runbook paragraph. None touches `service/`, `pathway_sim/` or `patient_engine/`.

| # | Ticket | Size | Acceptance |
|---|---|---|---|
| MCP-1 | Skeleton: stdio server, service client, `list_scenarios`, `describe_world`, `validate_flowchart`, `get_run_summary` | S (3 h) | `mcp dev` or the SDK in-memory client lists the tools; each returns structured output validated against its `outputSchema`; token read from the environment; with no token against a hosted service the error is a tool error, not a crash; works against `TestClient` in a test |
| MCP-2 | Runs: `start_run`, `get_run_status`, `cancel_run`, `compare_runs`, `propose_optimisation`, `get_optimisation`, `apply_optimisation` | M (4 h) | Same request twice returns the cached run (service behaviour passed through); polling reaches `succeeded`; `compare_runs` on different patients returns the service's `different_patients` error as an `isError` result; no result exceeds 8 KB in the tests; write tools absent in read-only mode |
| MCP-3 | Records and boundary: `get_decisions`, `get_patient_record`, allowlist filter, optional teaching mode | M (3 h) | A test that scrambles hidden truth and compares tool output is byte-identical; a test that no key named `cancer`, `condition` or `hidden` appears in any default tool result; teaching mode is off unless the environment variable is set at start, is not in `tools/list` otherwise, and labels every result when on; `limit` capped at 20 |
| MCP-4 | Encounter and patient engine in process: `start_run` for world files, `library_info`, `show_card`, `generate_library_fake` (and `audit_library` once WP-W4-3 is merged) | M (4 h) | `finland_encounter` n=500 seed 1 returns the same headline numbers as the CLI; worker has a 60 s limit and one concurrent run; n above 1,000 refused with an actionable message; scenario names come from an allowlist and a path is rejected |
| MCP-5 | Resources and prompts | S (2 h) | `resources/list` shows catalogue, scenarios, ledger; `run://{id}/report` reads a finished run; the four prompts render with their arguments; a prompt run end to end in a client produces a what-if comparison with n, seeds and numbers quoted |
| MCP-6 | Streamable HTTP and hosting | M (4 h) | Mounted at `/mcp` (or its own process); requests without a valid token get 401; a bad `Origin` gets 403; a runbook section says how to connect Claude Code with the token as a header; smoke script in `deploy/` passes; hosted instance runs in `PATHWAY_READ_ONLY` or `PATHWAY_PUBLIC_READ` mode with teaching mode off |

Order: MCP-1, MCP-2, MCP-3 are the useful core (10 h); MCP-4 is needed for the encounter scenario; MCP-5 and MCP-6 are optional polish.

## 9. Open questions for Tuomas

1. Is anyone on the team actually going to use a chat client against the simulator in the next two weeks? If not, defer past the end of the event.
2. Should the encounter loop become a service run kind first (service owner, about 4 to 6 hours)? That makes MCP-4 mostly redundant and also gives the web app the encounter scenario.
3. Hosted or local only? Local stdio is safe and sufficient for the team; hosted adds the auth question (section 5.4).

Not verified: client-specific tool-result size limits, which clients implement the experimental tasks feature, and whether run-log `result` fields are measured or true values. All three are checked in MCP-1 to MCP-3.

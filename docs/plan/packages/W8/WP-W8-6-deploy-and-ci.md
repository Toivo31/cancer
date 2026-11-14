# WP-W8-6: Continuous integration green, and deployment to a real host

| | |
|---|---|
| Component | C6 platform (deployment, fork F5); security review (`docs/platform/security-review.md`) |
| Status | not started |
| Size | S for T1 to T3 (agent); M for T4 to T6 (human with a host) |
| Needs | T4 to T6: a person with ssh to a Linux host with Docker and compose v2 |
| Owned paths | `tests/test_expr.py` and `tests/fixtures/guard_eval_baseline.json` (T1), `Dockerfile`, `.dockerignore`, `web/tsconfig*.json` or `web/vite.config.*` only as needed (T2), `deploy/platform.env.example` (T3), `deploy/` scripts (T4 to T6), `docs/platform/runbook.md` (deploy section) |
| Do not edit | `service/` behaviour, `web/src/**` logic |
| Review required | yes for T3 to T6 (security settings) |
| Track | T1 and T2 before freeze (CI on PR #2 is red); T3 before freeze; T4 to T6 need a human, after submission unless a host appears |

## What is true now (checked 21:15 UTC, `gh run list`)

The CI workflow **does run** on pushes to `overnight/sim` and on PR #2, and **fails** (04-status says it was never run; that
row is stale):

1. **python job:** `tests/test_expr.py::test_shipped_scenarios_give_identical_results` fails (also locally). It globs every
   `scenarios/**/*.yaml` with flowcharts, and `w8/fi-sens` added 92 combinations from
   `scenarios/experiments/finland_evidence_*.yaml` that are not in `tests/fixtures/guard_eval_baseline.json`. Not a behaviour change.
2. **container job:** `npm run build` (`tsc -b && vite build`) fails inside Docker: `web/src/graph/layers.test.ts` and
   `web/src/mock/mockApi.ts` import `../../../docs/platform/fixtures/flow_*.json`, which is outside what the Dockerfile copies
   (`COPY web/ ./`). The web job outside Docker passes.
3. `deploy/platform.env.example` disagrees with 04-status's hosted settings: it has `PATHWAY_MAX_PATIENTS=50000`,
   `PATHWAY_JOB_SECONDS=900` and no `PATHWAY_MAX_SEEDS`; 04-status says 20000, 120 and 3. The service reads all three.
4. A full-size Finnish optimisation through the service has never been timed against the job limit (04-status known
   problems); with `PATHWAY_JOB_SECONDS=120` it may never finish.

## Options for T1 (lean in bold)

(a) **Exclude generated experiment worlds from the guard** (they are outputs of a script, regenerated on demand; the guard is
for shipped scenarios); (b) add their digests to the baseline (the guard then fails every time the script is rerun);
(c) move the generated worlds out of `scenarios/`. (c) breaks the paths written in `docs/evidence_sensitivity.md`.

## Options for T2 (lean in bold)

(a) **Copy `docs/platform/fixtures/` into the web build stage** at the same relative path; (b) exclude `*.test.ts` and
`src/mock/` from the production `tsc` project (but `mockApi.ts` may be imported by the app in mock mode: check);
(c) move the fixtures into `web/`. (c) touches files other lanes read.

## Acceptance

- [ ] CI run on the integration branch: python, web and container jobs green (link in the report).
- [ ] `docker build .` locally (if Docker is available) gives an image; `deploy/smoke.sh` passes against it.
- [ ] `deploy/platform.env.example` values match the documented hosted settings, each with a one-line reason; 04-status's
      row and the example say the same.
- [ ] Edge: the container refuses to start without a token unless `PATHWAY_PUBLIC_READ=1` (existing CI step stays green).

## Tickets

| | ID | Ticket | Size | Owner | Needs | Done when |
|---|---|---|---|---|---|---|
| [ ] | W8-DP-T1 | Make the scenario guard cover shipped scenarios only (option a) | S | agent | – | `pytest tests/test_expr.py` green; a new file under `scenarios/experiments/` does not break it (test) |
| [ ] | W8-DP-T2 | Fix the Docker web build (option a or b) | S | agent | – | container job green on CI |
| [ ] | W8-DP-T3 | Align `deploy/platform.env.example` with the hosted limits (incl. `PATHWAY_MAX_SEEDS`) and time one Finnish optimisation through the service locally to pick `PATHWAY_JOB_SECONDS` | S | agent | – | example updated; measured time written next to the setting |
| [ ] | W8-DP-T4 | First deploy: `DRY_RUN=1 deploy/deploy.sh user@host --seed`, then for real; smoke | M | **human with a host** | T1 to T3, a host (fork F5) | `/api/health` answers; `deploy/smoke.sh` passes on the host |
| [ ] | W8-DP-T5 | Set the security settings on the host: token (16+ characters), `PATHWAY_PUBLIC_READ`, `PATHWAY_READ_ONLY` for judging, limits from T3, `JEV_ALLOWED_HOSTS` empty unless a JEV server is named | S | **human with a host** | T4 | settings listed in the runbook; a request without token cannot start a job (manual check) |
| [ ] | W8-DP-T6 | Rollback and backup tried once (`deploy/backup.py`, redeploy an older sha) | S | **human with a host** | T4 | runbook records both commands as tested |

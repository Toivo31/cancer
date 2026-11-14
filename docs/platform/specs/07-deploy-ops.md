# Spec 07: Deploy and operations

Milestone M7. Depends on M2 and M3. Open fork: F5 (host, visibility, data).

## Purpose

"Online": one address the team and the judges can open. Smallest thing that is safe to expose.

## Shape

One container: the service (API, jobs) serving the built web app, SQLite and result files on a
mounted volume. No separate database, queue or object store at this size.

```
docker build -t pathway-platform .
docker run -p 8000:8000 -v pathway-data:/data -e PATHWAY_ACCESS_TOKEN=… pathway-platform
```

Dockerfile: Node stage builds `web/`; Python slim stage installs `requirements.txt`, copies the
packages and the built files; `uvicorn service.app:app`.

Configuration by environment: `PATHWAY_DATA_DIR`, `PATHWAY_ACCESS_TOKEN`, `PATHWAY_MAX_PATIENTS`,
`PATHWAY_MAX_JOBS`, `PATHWAY_JOB_SECONDS`, `JEV_ALLOWED_HOSTS`, `JEV_DEFAULT_URL`.

## Access

- Hackathon: one shared token. The web app asks for it once and sends it as a header. Read-only
  "demo" mode without a token is an option if judges should click around without credentials
  (templates and stored runs visible, no new jobs).
- Later: accounts and per-user projects. Not planned in detail.

## Limits and abuse

Per spec 03: patients per run, seeds, concurrent jobs, wall time, document size. Plus request rate
per token. Conditions only through the safe evaluator (spec 01). Outbound JEV calls only to
allowed hosts.

## Hosting (needs Tuomas)

Any host that runs one container with a persistent volume and 2 CPUs works: Fly.io, Render,
Railway, a small VM. A Finnish run uses one core for a few seconds and well under 1 GB.
This session cannot reach hosting providers, so the deliverable is the container, a config file for
the chosen host and a short runbook; the deploy command is run from your machine or from CI with
your credentials.

## CI

GitHub Actions on pull requests: `pytest -q`, web build, type check, container build. No deploy
from CI until a host is chosen.

## Data

- Hosted instance: synthetic data and simulator-exported decisions only (banner on the upload page).
- Backups: the volume holds only reproducible results and user documents; a nightly copy of the
  SQLite file is enough.
- Results carry the engine version; an upgrade does not silently change stored numbers.

## Build order

1. Dockerfile and compose file; one-command local run (M7-1).
2. Token access, demo mode, limits (M7-2).
3. Host config and runbook once F5 is answered (M7-3).
4. CI workflow (M7-4).
5. Seed the instance with the two templates and a guided project (M7-5); data notice (M7-6).

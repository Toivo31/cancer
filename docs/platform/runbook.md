# Runbook: hosting the platform (spec 07, tickets M7-1 to M7-6)

Status: written and tested without Docker or a host (see "Not tested"). Hosting itself is fork F5 and needs a human.

## The one command

You need: a Linux host with Docker (compose v2) and ssh access for a user in the `docker` group; this repo with
`web/` merged (branch `plat/web`), committed.

```
cp deploy/platform.env.example deploy/platform.env     # git-ignored; set PATHWAY_ACCESS_TOKEN (openssl rand -hex 24)
chmod 600 deploy/platform.env
deploy/deploy.sh user@host --seed                      # first time; later: deploy/deploy.sh user@host
```

It ships `git archive HEAD` (uncommitted changes are not deployed), builds the image on the host, starts it on the
host's `127.0.0.1:8000`, waits for `/api/health`, seeds (first time), runs `deploy/smoke.sh` on the host and keeps the
last 3 releases. Variables: `PROXY=1` also starts Caddy (below), `ALLOW_NO_WEB=1` deploys the API alone,
`DRY_RUN=1` prints every step and changes nothing, `REMOTE_DIR`, `SSH_OPTS`, `DEPLOY_ENV_FILE`.

Local, same image, no ssh: `docker compose --env-file deploy/platform.env up -d --build`, then `http://127.0.0.1:8000`.
Without compose: `docker build -t pathway-platform . && docker run -p 8000:8000 -v pathway-data:/data -e PATHWAY_ACCESS_TOKEN=... pathway-platform`.

## Modes (set in `deploy/platform.env`)

| Settings | Who can do what | Use |
|---|---|---|
| token only | everything needs `Authorization: Bearer <token>`; the page asks once | team work |
| token + `PATHWAY_PUBLIC_READ=1` | anyone reads and may use validate, try-a-decision, compare; writes and jobs need the token | **recommended for judges** |
| + `PATHWAY_READ_ONLY=1` | nobody writes, token or not | freeze after seeding, for the judging window |
| no token, no flags | open: everyone writes. Only for a laptop; the image refuses to start like this | development |

`GET /api/access` (public) reports `mode`, whether the caller's token is valid, `can_write` and `data_notice` (the
synthetic-data text the web app shows on the upload page and footer; reword with `PATHWAY_DATA_NOTICE`).
Web app contract: send `Authorization: Bearer <token>` on every `/api` call; on `401 unauthorized` ask for the token;
on `403 read_only` explain; `429` has `Retry-After`; `507 storage_full`.

Limits when not open: 600 requests/min per client address, 6 job starts/min (runs, optimisations, apply, datasets, models),
queued plus running jobs capped at 4 x `PATHWAY_MAX_JOBS`, 10 requests/min with a missing or wrong token (then 429),
bodies over 1 MB are 413, writes refused with 507 below `PATHWAY_MIN_FREE_MB` free (deletes still work, so you can free space).
Patients, seeds and wall time per job are the spec 03 limits (`PATHWAY_MAX_PATIENTS`, `PATHWAY_MAX_SEEDS`, `PATHWAY_JOB_SECONDS`).

## JEV servers (SSRF guard)

A decision policy with `backend: http` makes the server call a URL a user typed. It is refused unless the host is in
`JEV_ALLOWED_HOSTS` (`host` or `host:port`, comma separated; `JEV_DEFAULT_URL` is allowed implicitly). Empty means no
JEV calls at all. Even a listed name is refused if it resolves to a link-local or cloud-metadata address
(169.254.0.0/16, fe80::/10, 100.100.100.200, fd00:ec2::). Loopback and private addresses work only when you list them.
Residual risk: the name is resolved when the policy is built and again when the connection is made; an allowed name whose
DNS an attacker controls could change in between. List only names you control.

## One host for the platform and Eemeli's live demo

`PROXY=1 deploy/deploy.sh ...` starts Caddy (compose profile `proxy`, host networking) in front of two loopback-only upstreams:

| Site (env) | Upstream | What |
|---|---|---|
| `PLATFORM_SITE` | `127.0.0.1:8000` | this platform |
| `LIVE_SITE` | `127.0.0.1:8770` | `python -m note_reader.server --host 127.0.0.1 --port 8770` (Eemeli's, from his checkout) |

A domain as a site address gets automatic HTTPS (DNS must point at the host; ports 80 and 443 open); `:80` and `:8080` give
plain HTTP on those ports when there is no domain yet. Run his server with `deploy/live-demo.service` (systemd; edit
paths). His server has no login and calls a paid LLM per `/api/read`; the proxy caps request bodies at 16 KB, but anyone can
still spend his key: keep a spending limit on the key or put `basicauth` in `deploy/Caddyfile` for his site. His files are untouched.
Firewall: expose 80 and 443 (and 8080 if used) only; 8000 and 8770 stay on loopback. Never change the compose port to `"8000:8000"`.

## Other hosts

Anything that runs one container with a persistent volume at `/data` and 2 CPUs. Exactly one instance (jobs are child
processes, SQLite is one file). `deploy/fly.toml` is a starting point for Fly.io (untested). Set the same variables as secrets/env.
Behind any proxy set `FORWARDED_ALLOW_IPS` to the proxy's address (compose uses `*` because only loopback can reach the port),
otherwise all visitors share one rate-limit budget.

## Operating

- Logs: `docker compose --env-file ../platform.env logs -f platform` from the release directory. The token is never logged;
  denied requests log method, path and client only.
- Backup (nightly cron on the host): `docker compose -p pathway exec -T platform python /app/deploy/backup.py` writes a checked
  copy of the SQLite file to `/data/backups` (keeps 7). Copy it off the host. Result files are reproducible and not backed up.
- Restore: stop, copy a backup over `/data/pathway.sqlite3` (`docker run --rm -v pathway_pathway-data:/data ...`), start.
- Change the token: edit `platform.env`, redeploy (or `docker compose up -d` in the release directory). The old token stops working at once.
- Disk full: writes get `507 storage_full`. Delete old projects through the API (deletes still work) or prune the volume.
- Roll back: `git checkout <old-sha> && deploy/deploy.sh user@host`; the data volume carries over (results carry their engine version).
- Seed again: `deploy/deploy.sh user@host --seed`, or `docker compose ... exec -T platform python /app/deploy/seed.py http://127.0.0.1:8000`.
  Idempotent; it creates two template copies and "Guided tour: Finland lung" (run, optimise, apply, rerun, compare), a few minutes. Needs write access, so seed before `PATHWAY_READ_ONLY=1`.
- After deploying run `deploy/smoke.sh https://your-address` from your laptop: health, mode, notice, strangers refused, token works.

## What I checked from the attacker's and the tired operator's side

- No token set: the image refuses to start (`PATHWAY_REQUIRE_AUTH=1`); a token under 16 characters is refused. Outside Docker it runs open and says so in the log and in `/api/access`.
- Token in logs or URLs: only the header is read; query-string tokens are ignored; uvicorn's access log has no headers; deploy passes the token by file, never on a command line.
- Public demo with expensive jobs: anonymous callers cannot start any; token holders are limited per minute and by active jobs.
- Guessing: 10 failures/min per address, then 429; the token compare is constant time.
- SSRF: see above; both "start a run" and "try a decision" go through the check.
- Full volume: writes refused at 500 MB free (compose), deletes allowed. A job that is already running can still fill the last 500 MB.
- Not done: per-user accounts, per-project quotas on disk, request signing, a WAF. The shared token means anyone with it can delete anything.

## Not tested from this session

No Docker daemon here, so `docker build`, `docker compose up`, the Caddy container, the Fly file, the GitHub workflow and
`deploy.sh` over a real ssh connection have not been run. Checked instead: `docker compose config` accepts the compose file; the Dockerfile's
file list was verified by running the service, `deploy/seed.py` and `deploy/smoke.sh` from a directory holding only those
files (clean import closure, seeding in about 2.5 minutes with `--quick`); `deploy.sh` dry run; shell syntax; the workflow parses as YAML; security
behaviour by `tests/test_service_security.py`. First real deploy: expect a small fix or two, and read `docker compose logs platform`.

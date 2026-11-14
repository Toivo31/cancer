#!/usr/bin/env bash
# Deploy the committed HEAD to one host over ssh. The one command:
#
#     deploy/deploy.sh user@host            # add --seed on the first deploy; PROXY=1 to start the Caddy proxy as well
#
# You supply: ssh access to a Linux host with Docker (compose v2) and your user in the docker group, and
# deploy/platform.env (copy deploy/platform.env.example; it holds the access token; git-ignored).
# What it does: checks the env file, ships `git archive HEAD` to <REMOTE_DIR>/releases/<sha>, copies the env file
# (mode 600), builds, starts, waits for /api/health, runs deploy/smoke.sh on the host, keeps the last 3 releases.
# Rollback: run deploy.sh again from the older commit (git checkout <old-sha>), or on the host:
#   cd pathway/releases/<old-sha> && docker compose --env-file ../../platform.env up -d --build
# Variables: DEPLOY_ENV_FILE, REMOTE_DIR (pathway, in the login directory), SSH_OPTS, DRY_RUN=1 (print, change nothing), ALLOW_NO_WEB=1 (API only).
set -euo pipefail
HOST="${1:?usage: deploy/deploy.sh user@host [--seed]}"; SEED=0; [ "${2:-}" = "--seed" ] && SEED=1
cd "$(git rev-parse --show-toplevel)"
ENV_FILE="${DEPLOY_ENV_FILE:-deploy/platform.env}"
REMOTE="${REMOTE_DIR:-pathway}"          # relative to the ssh login directory; an absolute path needs it to be writable
SSH="ssh ${SSH_OPTS:-}"
SHA=$(git rev-parse --short=10 HEAD)
run() { if [ "${DRY_RUN:-0}" = 1 ]; then printf '+ %s\n' "$*"; else "$@"; fi; }

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (copy deploy/platform.env.example and set PATHWAY_ACCESS_TOKEN)"; exit 1; }
getv() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1; }
TOKEN=$(getv PATHWAY_ACCESS_TOKEN); PUBREAD=$(getv PATHWAY_PUBLIC_READ)
if [ "${#TOKEN}" -lt 16 ] && [ -z "$PUBREAD" ]; then echo "PATHWAY_ACCESS_TOKEN in $ENV_FILE must be 16+ characters (openssl rand -hex 24)"; exit 1; fi
if [ -n "$TOKEN" ] && [ "${#TOKEN}" -lt 16 ]; then echo "PATHWAY_ACCESS_TOKEN in $ENV_FILE is shorter than 16 characters"; exit 1; fi
if ! git cat-file -e HEAD:web/package.json 2>/dev/null && [ "${ALLOW_NO_WEB:-0}" != 1 ]; then
  echo "HEAD has no web/ (merge branch plat/web first), or set ALLOW_NO_WEB=1 to deploy the API alone"; exit 1; fi
[ -z "$(git status --porcelain --untracked-files=no)" ] || echo "warning: uncommitted changes are NOT deployed (only HEAD $SHA)"
[ "${ALLOW_NO_WEB:-0}" = 1 ] && export PATHWAY_BUILD_TARGET=api
PROFILE=""; [ "${PROXY:-0}" = 1 ] && PROFILE="--profile proxy"

echo "deploying $SHA to $HOST:$REMOTE"
run $SSH "$HOST" "mkdir -p '$REMOTE/releases/$SHA' && chmod 700 '$REMOTE'"
if [ "${DRY_RUN:-0}" = 1 ]; then echo "+ git archive HEAD | $SSH $HOST tar -x -C $REMOTE/releases/$SHA"
else git archive HEAD | $SSH "$HOST" "tar -x -C '$REMOTE/releases/$SHA'"; fi
if [ "${DRY_RUN:-0}" = 1 ]; then echo "+ copy $ENV_FILE to $HOST:$REMOTE/platform.env (mode 600)"
else $SSH "$HOST" "umask 077 && cat > '$REMOTE/platform.env'" < "$ENV_FILE"; fi
BUILD_TARGET_ENV=""; [ "${ALLOW_NO_WEB:-0}" = 1 ] && BUILD_TARGET_ENV="PATHWAY_BUILD_TARGET=api"
# On the host: R is the real path of the deploy directory (compose resolves --env-file against the physical cwd).
IN_RELEASE="cd '$REMOTE' && R=\$(pwd -P) && ln -sfn 'releases/$SHA' current && cd 'releases/$SHA'"
COMPOSE="$BUILD_TARGET_ENV docker compose --env-file \"\$R/platform.env\""
run $SSH "$HOST" "$IN_RELEASE && $COMPOSE $PROFILE up -d --build"
PORT=$(getv PATHWAY_PORT); PORT="${PORT:-8000}"
run $SSH "$HOST" "for i in \$(seq 1 40); do curl -fs http://127.0.0.1:$PORT/api/health >/dev/null && exit 0; sleep 3; done; echo 'service did not become healthy; recent logs:'; $IN_RELEASE && $COMPOSE logs --tail 40 platform; exit 1"
[ "$SEED" = 1 ] && run $SSH "$HOST" "$IN_RELEASE && $COMPOSE exec -T platform python /app/deploy/seed.py http://127.0.0.1:8000"
run $SSH "$HOST" "$IN_RELEASE && PATHWAY_ACCESS_TOKEN=\$(sed -n 's/^PATHWAY_ACCESS_TOKEN=//p' \"\$R/platform.env\") bash deploy/smoke.sh http://127.0.0.1:$PORT"
run $SSH "$HOST" "cd '$REMOTE/releases' && ls -1t | tail -n +4 | xargs -r rm -rf"
echo "done. Next: put a proxy in front (docs/platform/runbook.md) and run deploy/smoke.sh https://your-address"

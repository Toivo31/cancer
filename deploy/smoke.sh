#!/usr/bin/env bash
# After a deploy: does the instance answer, and is it closed to strangers?
#   deploy/smoke.sh https://platform.example.org [TOKEN]       (TOKEN may also be in $PATHWAY_ACCESS_TOKEN)
# Exit code 1 if anything fails. Creates nothing.
set -uo pipefail
BASE="${1:?usage: smoke.sh BASE_URL [TOKEN]}"; BASE="${BASE%/}"
TOKEN="${2:-${PATHWAY_ACCESS_TOKEN:-}}"
fail=0
check() { # name, condition-exit-code
  if [ "$2" -eq 0 ]; then printf 'ok    %s\n' "$1"; else printf 'FAIL  %s\n' "$1"; fail=1; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
body() { curl -s --max-time 15 "$@"; }

[ "$(code "$BASE/api/health")" = 200 ]; check "health answers 200" $?
ACCESS=$(body "$BASE/api/access")
echo "$ACCESS" | grep -q '"mode"'; check "/api/access answers (mode: $(echo "$ACCESS" | sed -n 's/.*"mode":"\([a-z_]*\)".*/\1/p'))" $?
echo "$ACCESS" | grep -q '"synthetic_only":true'; check "synthetic-data notice is on" $?
if echo "$ACCESS" | grep -q '"mode":"open"'; then
  case "$BASE" in http://127.0.0.1*|http://localhost*) echo "note  open mode on localhost is fine for development";;
                  *) check "instance is NOT open to the world (mode is open!)" 1;; esac
else
  [ "$(code -X POST "$BASE/api/projects" -H 'content-type: application/json' -d '{"name":"smoke","template":"norway_check"}')" = 401 ] \
    || [ "$(code -X POST "$BASE/api/projects" -H 'content-type: application/json' -d '{"name":"smoke","template":"norway_check"}')" = 403 ]
  check "a stranger cannot create a project" $?
  [ "$(code -X POST -H 'Authorization: Bearer wrong-token-for-smoke-test' -H 'content-type: application/json' -d '{"name":"smoke","template":"norway_check"}' "$BASE/api/projects")" = 401 ]; check "a wrong token is refused" $?
fi
if [ -n "$TOKEN" ]; then
  [ "$(code -H "Authorization: Bearer $TOKEN" "$BASE/api/templates")" = 200 ]; check "the token works (templates)" $?
  echo "$(body -H "Authorization: Bearer $TOKEN" "$BASE/api/access")" | grep -q '"authenticated":true'; check "access reports the token as valid" $?
fi
code "$BASE/api/templates" | grep -qE '^(200|401)$'; check "templates answer 200 (public read) or 401 (token required)" $?
if [ -z "${SMOKE_NO_WEB:-}" ]; then body "$BASE/" | grep -qi '<div id=\|<html'; check "the web app is served at /" $?; fi
exit $fail

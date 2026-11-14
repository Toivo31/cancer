#!/usr/bin/env bash
# The integrator's one command. Steps, in order, one summary line each; exit code is non-zero if any step fails.
#   fast tests      pytest -m "not slow"          (budget 2 min)
#   contract tests  pytest tests/contracts        (JEV against the stub, flow/1, service OpenAPI, tiers)
#   golden checks   pytest tests/test_golden_*.py (Norway ~40% through CLI and service, pitch numbers)
#   web             npm run typecheck && npm test (only if web/node_modules exists)
#   slow tests      pytest -m slow                (only with --slow; before any push to main and at wave close)
# Usage: scripts/gate.sh [--slow]      PYTHON=/path/to/python overrides the interpreter.
set -u
cd "$(dirname "$0")/.."

SLOW=0
for a in "$@"; do
  case "$a" in
    --slow) SLOW=1 ;;
    -h|--help) sed -n 2,9p "$0"; exit 0 ;;
    *) echo "unknown argument: $a (use --slow)" >&2; exit 2 ;;
  esac
done

# Interpreter: $PYTHON, else python if it can import the service's dependencies, else the main checkout's .venv.
pick_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  for c in python python3 "$(git rev-parse --git-common-dir 2>/dev/null)/../.venv/bin/python" .venv/bin/python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import fastapi, numpy, yaml, pytest" >/dev/null 2>&1; then echo "$c"; return; fi
  done
  echo python
}
PY="$(pick_python)"
echo "gate: python = $PY"

FAILED=0
SUMMARY=()

step() {  # step "name" command...
  local name="$1"; shift
  local t0=$SECONDS
  echo; echo "=== $name: $*"
  "$@"
  local rc=$?
  local dt=$((SECONDS - t0))
  if [ $rc -eq 0 ]; then SUMMARY+=("PASS   $name (${dt}s)"); else SUMMARY+=("FAIL   $name (${dt}s, exit $rc)"); FAILED=1; fi
}

step "fast tests"     "$PY" -m pytest -q -m "not slow" -p no:cacheprovider
step "contract tests" "$PY" -m pytest -q tests/contracts -p no:cacheprovider
step "golden checks"  "$PY" -m pytest -q tests/test_golden_templates.py tests/test_golden_cli.py -p no:cacheprovider

if [ -d web/node_modules ]; then
  step "web" bash -c 'cd web && npm run typecheck && npm test'
else
  echo; echo "=== web: skipped: run npm install in web/"
  SUMMARY+=("SKIP   web (skipped: run npm install in web/)")
fi

if [ $SLOW -eq 1 ]; then
  step "slow tests" "$PY" -m pytest -q -m slow -p no:cacheprovider
else
  SUMMARY+=("SKIP   slow tests (add --slow)")
fi

echo; echo "=== gate summary"
printf '%s\n' "${SUMMARY[@]}"
if [ $FAILED -eq 0 ]; then echo "GATE: PASS"; else echo "GATE: FAIL"; fi
exit $FAILED

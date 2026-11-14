#!/usr/bin/env bash
# Generate model-written patient cards with Gemini, on a machine that can reach Google's API.
#
#   export LLM_API_KEY="..."              # once per terminal tab; never put the key in a file
#   bash scripts/generate_gemini.sh trial   # 30 cards, about 5 minutes, runs in the foreground
#   bash scripts/generate_gemini.sh full    # 5 x 500 cards in the background, about 60 to 90 minutes
#   bash scripts/generate_gemini.sh status  # where the background runs are
#   bash scripts/generate_gemini.sh resume  # restart any background run that stopped before finishing
#
# Libraries are written to libraries/gemini_v2_*; logs to runs/gen_logs/. Synthetic data only.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-}"
SEEDS="${SEEDS:-13 14 15 16 17}"   # new seeds, so ids do not collide with the first (g2@1) libraries
N="${N:-500}"
CONC="${CONC:-20}"
CAT=catalogue/lung-primary-care

if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
PY=python; command -v python >/dev/null 2>&1 || PY=python3
export SSL_CERT_FILE="${SSL_CERT_FILE:-$($PY -m certifi 2>/dev/null || true)}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai}"
export LLM_MODEL="${LLM_MODEL:-gemini-3.8-flash}"
KEEP_AWAKE=""; command -v caffeinate >/dev/null 2>&1 && KEEP_AWAKE="caffeinate -i"
mkdir -p runs/gen_logs

need_key() {
  if [ -z "${LLM_API_KEY:-}" ]; then
    echo 'LLM_API_KEY is not set in this terminal. Run:  export LLM_API_KEY="your key"   and try again.' >&2
    exit 1
  fi
}

case "$MODE" in
  trial)
    need_key
    OUT=libraries/gemini_v2_trial30
    if [ -e "$OUT" ]; then echo "$OUT already exists. Remove it (and $OUT.work) to rerun the trial." >&2; exit 1; fi
    $PY -m patient_engine generate --catalogue $CAT --n 30 --seed 12 --out $OUT --concurrency 15
    echo
    echo "Audit (look at the lines report_wording and background_realism):"
    $PY -m patient_engine audit $OUT --catalogue $CAT --out /tmp/audit_gemini_v2_trial30 | grep -v "SKIPPED" | tail -15
    ;;
  full)
    need_key
    for s in $SEEDS; do
      OUT=libraries/gemini_v2_s${s}_${N}
      if [ -e "$OUT" ]; then echo "skip seed $s: $OUT exists"; continue; fi
      nohup $KEEP_AWAKE $PY -m patient_engine generate --catalogue $CAT --n "$N" --seed "$s" \
        --out "$OUT" --concurrency "$CONC" > runs/gen_logs/v2_s$s.log 2>&1 &
      echo "started seed $s -> $OUT (log runs/gen_logs/v2_s$s.log)"
    done
    echo "Running in the background. Keep the computer awake and plugged in."
    echo "Progress:  bash scripts/generate_gemini.sh status"
    ;;
  resume)
    need_key
    for s in $SEEDS; do
      OUT=libraries/gemini_v2_s${s}_${N}
      if [ -f "$OUT/manifest.json" ] && ! grep -q '"partial": true' "$OUT.work/generation_report.json" 2>/dev/null; then
        echo "seed $s: finished"; continue
      fi
      if pgrep -f "patient_engine generate.*--seed $s " >/dev/null 2>&1; then echo "seed $s: still running"; continue; fi
      RES=""; [ -e "$OUT" ] && RES="--resume"
      nohup $KEEP_AWAKE $PY -m patient_engine generate --catalogue $CAT --n "$N" --seed "$s" \
        --out "$OUT" --concurrency "$CONC" $RES > runs/gen_logs/v2_s${s}_resume.log 2>&1 &
      echo "restarted seed $s"
    done
    ;;
  status)
    for s in $SEEDS; do
      OUT=libraries/gemini_v2_s${s}_${N}
      if [ -f "$OUT.work/generation_report.json" ]; then
        echo "seed $s: done  $(grep -E '"accepted"|"discarded"|"failed"' "$OUT.work/generation_report.json" | tr -d ' \n')"
      else
        echo "seed $s: $(tail -n 1 runs/gen_logs/v2_s$s*.log 2>/dev/null | tail -n 1)"
      fi
    done
    ;;
  *)
    sed -n 2,11p "$0"; exit 1 ;;
esac

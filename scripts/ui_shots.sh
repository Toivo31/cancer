#!/usr/bin/env bash
# Screenshots of the offline demo pages at 1440x900 and 1920x1080, with console-error capture, network off.
# Usage: scripts/ui_shots.sh <out-dir> [url-list-file]
#   url-list-file: one URL per line, relative to demo/ (e.g. "flow.html?s=norway&compare"); "#" lines are comments.
#   Without a list: every page and the simulator variants below.
# Writes <out-dir>/<page>_<w>x<h>.png and <out-dir>/console.txt. Exit code 1 if any page logs a console error.
# Console capture needs puppeteer-core: found in web/node_modules (this checkout or the main one), /tmp/node_modules,
# or $PUPPETEER_CORE. Without it, falls back to plain `google-chrome --screenshot` (no console capture; says so).
set -u
cd "$(dirname "$0")/.."
REPO="$PWD"
OUT="${1:?usage: scripts/ui_shots.sh <out-dir> [url-list-file]}"
LIST="${2:-}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

DEFAULT_URLS=(
  "start.html"
  "flow.html"
  "flow.html?s=finland"
  "flow.html?s=finland&compare"
  "flow.html?s=norway&compare"
  "flow.html?s=norway&compare&left=authors&right=suggested"
  "flow.html?paused&day=60"
  "flow.html?layer=time"
  "flow.html?theme=night"
  "patients.html"
  "evidence.html"
  "jev.html"
  "encounter.html"
  "index.html"
  "research.html"
  "_skeleton.html"
)

URLS=()
if [ -n "$LIST" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"; line="$(echo "$line" | xargs)"
    [ -n "$line" ] && URLS+=("$line")
  done < "$LIST"
else
  for u in "${DEFAULT_URLS[@]}"; do
    [ -f "demo/${u%%\?*}" ] && URLS+=("$u")   # skip pages that do not exist on this branch yet
  done
fi
[ ${#URLS[@]} -gt 0 ] || { echo "ui_shots: no URLs" >&2; exit 2; }

CHROME="${CHROME:-}"
for c in "$CHROME" /usr/bin/google-chrome google-chrome chromium chromium-browser; do
  [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 && { CHROME="$(command -v "$c")"; break; }
done
[ -n "$CHROME" ] || { echo "ui_shots: no Chrome found (set CHROME=...)" >&2; exit 2; }

PP="${PUPPETEER_CORE:-}"
if [ -z "$PP" ]; then
  COMMON="$(git rev-parse --git-common-dir 2>/dev/null || true)"
  for d in "$REPO/web/node_modules/puppeteer-core" "${COMMON:+$COMMON/../web/node_modules/puppeteer-core}" /tmp/node_modules/puppeteer-core; do
    [ -n "$d" ] && [ -f "$d/package.json" ] && { PP="$(cd "$d" && pwd)"; break; }
  done
fi

if [ -n "$PP" ] && command -v node >/dev/null 2>&1; then
  echo "ui_shots: ${#URLS[@]} URLs x 2 sizes -> $OUT (puppeteer-core: $PP)"
  node scripts/ui_shots.js "$PP" "$CHROME" "$OUT" "$REPO/demo" "${URLS[@]}"
  rc=$?
  [ $rc -eq 0 ] && echo "ui_shots: no console errors" || echo "ui_shots: console errors, see $OUT/console.txt"
  exit $rc
fi

echo "ui_shots: puppeteer-core not found; plain screenshots, NO console capture" | tee "$OUT/console.txt"
for u in "${URLS[@]}"; do
  s="$(echo "${u/.html/}" | sed 's/[^A-Za-z0-9]\+/_/g; s/^_//; s/_$//')"
  for size in 1440,900 1920,1080; do
    timeout 60 "$CHROME" --headless=new --no-sandbox --hide-scrollbars --host-resolver-rules="MAP * ~NOTFOUND" \
      --window-size="$size" --virtual-time-budget=4000 --screenshot="$OUT/${s}_${size/,/x}.png" \
      "file://$REPO/demo/$u" >/dev/null 2>&1 || echo "failed: $u $size" | tee -a "$OUT/console.txt"
  done
done
exit 0

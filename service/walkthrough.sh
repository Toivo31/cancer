#!/usr/bin/env bash
# The whole loop with curl: template -> run -> results -> optimise -> apply -> rerun on the same patients -> compare.
# Needs curl and jq. Start the service first:  uvicorn service.app:app --port 8000
# Usage: bash service/walkthrough.sh [http://localhost:8000]      (synthetic data only)
set -euo pipefail
B="${1:-http://localhost:8000}/api"
H='content-type: application/json'
say() { printf '\n== %s\n' "$*"; }
wait_job() {   # poll a job until it is finished, print its final line
  local s
  while :; do
    s=$(curl -s "$B/jobs/$1")
    case $(echo "$s" | jq -r .status) in succeeded|failed|cancelled) echo "$s" | jq -c '{status, progress, message, error}'; return;; esac
    sleep 0.5
  done
}

say "1. New project from the Norway check template"
P=$(curl -s -X POST "$B/projects" -H "$H" -d '{"name": "Norway walkthrough", "template": "norway_check"}' | jq -r .id)
echo "project $P"

say "2. Start a run: today's pathway, two cohorts of 300 patients"
R=$(curl -s -X POST "$B/projects/$P/runs" -H "$H" \
    -d '{"flowchart": {"id": "observed"}, "n": 300, "seeds": [301, 302], "label": "today"}')
echo "$R" | jq -c '{id, job_id, status, cached}'
RID=$(echo "$R" | jq -r .id); wait_job "$(echo "$R" | jq -r .job_id)"

say "3. Results: headline, per cohort, dashboard bundle, decisions, flow"
curl -s "$B/projects/$P/runs/$RID" | jq -c '{status, headline, per_seed: [.per_seed[] | {seed, on_time}]}'
curl -s "$B/projects/$P/runs/$RID/bundle" | jq -c '.scenarios[0] | {id, target_days, steps: (.flowchart_before.nodes | length)}'
curl -s "$B/projects/$P/runs/$RID/decisions" | sed -n 1p | jq -c '{decision_point, offered, chosen, probs}'
curl -s "$B/projects/$P/runs/$RID/flow" | jq -c '{format, totals, steps: (.steps | length), playback_patients: (.cohort.patients | length)}'

say "4. The same request again returns the same run (cache)"
curl -s -X POST "$B/projects/$P/runs" -H "$H" \
    -d '{"flowchart": {"id": "observed"}, "n": 300, "seeds": [301, 302], "label": "someone else"}' | jq -c '{id, cached}'

say "5. Optimise: search on training cohorts, report on unseen ones"
O=$(curl -s -X POST "$B/projects/$P/optimisations" -H "$H" \
    -d '{"flowchart": {"id": "observed"}, "n": 300, "train_seeds": [101, 102], "heldout_seeds": [301, 302], "max_changes": 3}')
OID=$(echo "$O" | jq -r .id); wait_job "$(echo "$O" | jq -r .job_id)"
curl -s "$B/projects/$P/optimisations/$OID" | jq -c '{status, changes: [.changes[] | {index, label}], blocked: (.blocked | length),
    unseen_patients: {before: .heldout.before.share_within_target, after: .heldout.after.share_within_target}}'

say "6. Apply the first two changes: new flowchart version, rerun on the held-out patients"
A=$(curl -s -X POST "$B/projects/$P/optimisations/$OID/apply" -H "$H" -d '{"accept": [0, 1]}')
echo "$A" | jq -c '{flowchart, run_id, baseline_run_id}'
wait_job "$(echo "$A" | jq -r .baseline_run.job_id)" >/dev/null; wait_job "$(echo "$A" | jq -r .run.job_id)"

say "7. Compare before and after (refused with 409 if the runs are not on the same patients)"
curl -s -X POST "$B/projects/$P/compare" -H "$H" \
    -d "{\"runs\": [\"$(echo "$A" | jq -r .baseline_run_id)\", \"$(echo "$A" | jq -r .run_id)\"]}" |
  jq -c '{same_patients, on_time: .headline.share_within_target, median_days: .headline.median_days_to_treatment}'

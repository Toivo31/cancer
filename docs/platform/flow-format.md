# Flow document format (`flow/1`)

What the flowchart screen draws for one run. Produced by `pathway_sim.flow.build_flow(log, scenario,
flowchart, sample=300, seed=0, cancer_share=0.5, queue_points=120, meta=None)`; `log` is one `RunLog` or a
list of cohorts of the same flowchart (pooled). Served by the service as `GET /api/projects/{p}/runs/{r}/flow`
(ticket M2-11). Fixtures: `docs/platform/fixtures/flow_norway.json`, `flow_finland.json` (observed / today) and
`*_optimised.json` (small cohorts, 40-patient sample; shape only, the numbers are not the headline results).

All counts use the patients measured after the warm-up (the population of `compute_metrics`). Only
`cohort.patients` is a sample. Times are calendar days; trace times are relative to the patient's own first
contact (day 0). Everything is simulated; `synthetic` is true for the Finnish scenario and false only in
the sense that the Norwegian pathway is calibrated to a published study (the patients are still simulated).

```
{
 "format": "flow/1", "scenario", "flowchart", "policy", "seeds": [..], "synthetic": bool,
 "clock_start", "target_days", "warmup_days",
 "totals":  {n, n_cancer, missed_cancers, untreated_cancers, treated_cancers, stuck, cohorts},   // pooled counts
 "metrics": {n, n_cancer, share_within_target, median_days_to_treatment, median_days_to_diagnosis,
             missed_cancers, tests_per_patient, invasive_per_patient, cost_per_patient,
             median_days_to_exit_noncancer, target_days},   // mean over cohorts, as the dashboard
 "by_group": {group: {n, n_cancer, median_days_to_treatment, share_within_target, median_days_to_diagnosis, missed_cancers}},
 "graph": {
   "nodes": [{id, label, short, kind: "step"|"decision"|"milestone"|"exit", stage, layer,
              test?, resource?, options? (decision: option node ids), outcome? (exit), when?, option_of?, fast_track?}],
   "edges": [{id: "a>b", source, target, kind: "then"|"maybe"|"option", n, shortcut?}],   // n = patients who went a then b
   "stages": [..]},
 "steps": {node_id: {n, n_cancer,                        // patients who went through it
            events, wait_mean, wait_median, wait_p90,      // days between ready and start
            service_mean, service_median,                  // days between start and result
            wait_days,                                     // total patient-days waited here (all patients)
            positive, negative, nondiagnostic,
            critical_n, critical_wait, critical_service,   // mean days per treated cancer on the critical path (= metrics.node_breakdown)
            critical_share, critical_wait_share}},         // share of the time to treatment (sums to 1 over nodes)
 "resources": {id: {label, type, capacity_per_day?, utilisation?}},
 "queues": {node_id: {x: [days since measured window start], y: [patients waiting], peak, mean}},
 "decisions": {node_id: {n, options, offered{opt: n}, chosen{opt: n}, share{opt}, mean_probability{opt},
                         by_group{group: {n, share{opt}}}}},
 "exits": {node_id: {n, n_cancer, outcome}},
 "time_lost": [{node, label, wait, service, share, wait_share, n_critical, wait_median, wait_p90}],   // sorted by critical wait
 "cohort": {seed, size, horizon, time_zero, strata: {cancer, other, cancer_total, other_total},
            "patients": [{id, cohort (seed), g, age, cancer, out, exit, t_exit, t_diag, t_treat, ft,
                          "v": [[node, t_ready, t_start, t_end, t_result, result 1|0|null, critical 0|1], ..],
                          "c": [[node, t, chosen, [offered], {option: probability offered}], ..]}]},
 "meta": {}   // free: titles, labels, published values (set by the caller)
}
```

Notes for drawing:

- `layer` is the longest path from a start; use it for left-to-right layout or ignore it for dagre.
  Edges with `shortcut: true` skip a step that has its own path; draw them thin or hidden when `n` is 0.
- A patient's dot sits at the step of its **critical** events (`v` rows with the last field 1, ordered by
  `t_ready`): waiting while `t_ready <= t < t_start`, being served while `t_start <= t < t_result`, then
  hopping along the graph to the next one. Rows without that flag are parallel steps (listed in the trace only).
- Decisions have no events; their moment is `c[i][1]`. Exits without a test have no `v` row; the patient rests at
  `exit` from `t_exit`.
- Playback uses day 0 = each patient's first contact, so patients of different arrival days replay together;
  queues are over real run days. The sample is `cancer_share` cancer patients so a pathway with 3% cancer still
  shows patients reaching treatment; `cohort.strata` records the sizes. Counts and colours on the graph use everyone.
- Compare two runs of different flowcharts by joining on node id; ids missing on one side are new or removed steps.

// Document and response shapes from docs/platform/specs/01 (documents), 03 (API) and 02 (stub policy).
// Kept by hand next to the generated `schema.d.ts` (npm run gen:api); the client in client.ts is the
// only place that converts from the wire to these types, so a change in the service stays local.

export type NodeKind = 'step' | 'decision' | 'join' | 'milestone' | 'exit'
export type EdgeType = 'required' | 'any' | 'optional' | 'option'
export type Stage = 'detection' | 'referral' | 'diagnosis' | 'treatment_start'

export interface FlowNode {
  id: string
  kind: NodeKind
  label: string
  test?: string
  when?: string
  stage?: Stage | string
  outcome?: 'treatment' | 'discharged' | 'diagnosis_only' | string
  milestone?: string
  options?: string[]
  availability?: Record<string, unknown>
  retry?: Record<string, unknown>
  fast_track?: boolean
  ui?: { x: number; y: number }
}

export interface FlowEdge {
  from: string
  to: string
  type: EdgeType
  index?: number
}

export interface StubRule {
  when: string
  probs?: Record<string, number>
  /** older 'rule' backend: always pick this option when the condition holds */
  choose?: string
}
export interface StubPoint {
  default?: Record<string, number> | string
  /** older 'rule' backend: shares sampled by the policy */
  mix?: Record<string, number>
  prefer?: string[]
  rules?: StubRule[]
  source?: string
  note?: string
  backend?: string
}
export interface DecisionPolicy {
  backend: string
  mode?: 'sample' | 'argmax' | string
  points: Record<string, StubPoint>
  [k: string]: unknown
}

export interface Flowchart {
  schema_version: number
  id: string
  version: number
  parent_version: number | null
  world_id: string
  name: string
  nodes: FlowNode[]
  edges: FlowEdge[]
  decision_policy: DecisionPolicy
  test_overrides?: Record<string, unknown>
  resource_overrides?: Record<string, unknown>
  edits_from_parent?: unknown[]
}

export interface World {
  schema_version: number
  id: string
  name: string
  clock_start?: string
  target_days?: number
  default_n?: number
  arrivals?: Record<string, unknown>
  resources?: Record<string, { type?: string; capacity_per_day?: number; min_lead_days?: number; source?: string }>
  tests?: Record<string, { kind?: string; resource?: string; stage?: string; source?: string }>
  [k: string]: unknown
}

export interface Template {
  id: string
  name: string
  description?: string
  /** flowcharts in the order the template lists them (today's pathway first) */
  flowcharts?: { id: string; name?: string }[]
}

export interface Project {
  id: string
  name: string
  template?: string | null
  created_at?: string
}

export interface FlowchartSummary {
  id: string
  name: string
  latest_version: number
  /** All version numbers, ascending. Filled in by the client when the service only gives the latest. */
  versions: number[]
  /** versions that have been used in a run (immutable) */
  locked: number[]
}

export interface Problem {
  severity: 'error' | 'warning'
  code: string
  node?: string | null
  message: string
  hint?: string | null
}
export interface ValidationResult {
  ok: boolean
  problems: Problem[]
}

export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export interface Job {
  id: string
  state: JobState
  progress: number
  message?: string
  error?: string | null
  started?: string | null
  finished?: string | null
  log_tail?: string[]
}

export interface RunMetrics {
  on_time_share?: number | null
  median_days?: number | null
  missed_cancers?: number | null
  n_patients?: number | null
  [k: string]: unknown
}

export interface RunRequest {
  flowchart: { id: string; version: number }
  n: number
  seeds: number[]
  decision_policy?: DecisionPolicy | null
  label?: string
}

export interface Run {
  id: string
  job_id: string | null
  status: JobState
  progress: number
  label: string
  flowchart: { id: string; version: number }
  n: number
  seeds: number[]
  created_at?: string
  metrics?: RunMetrics | null
  error?: string | null
}

// ---- run layers: the flow document `flow/1` (docs/platform/flow-format.md), GET /projects/{p}/runs/{r}/flow ----
export interface FlowGraphNode {
  id: string; label: string; short?: string; kind: string; stage?: string; layer?: number
  test?: string; resource?: string; options?: string[]; outcome?: string; when?: string
}
export interface FlowGraphEdge { id: string; source: string; target: string; kind: 'then' | 'maybe' | 'option' | string; n: number; shortcut?: boolean }
export interface FlowStep {
  n: number; n_cancer?: number; events?: number
  wait_mean?: number | null; wait_median?: number | null; wait_p90?: number | null
  service_mean?: number | null; service_median?: number | null; wait_days?: number
  positive?: number; negative?: number; nondiagnostic?: number
  critical_n?: number; critical_wait?: number | null; critical_service?: number | null
  critical_share?: number | null; critical_wait_share?: number | null
}
export interface FlowQueue { x: number[]; y: number[]; peak: number; mean: number }
export interface FlowDecision {
  n: number; options: string[]; offered: Record<string, number>; chosen: Record<string, number>
  share: Record<string, number>; mean_probability?: Record<string, number>
  by_group?: Record<string, { n: number; share: Record<string, number> }>
}
export interface TimeLost { node: string; label: string; wait: number; service: number; share: number; wait_share: number; n_critical: number; wait_median?: number | null; wait_p90?: number | null }
/** one visit: [node, t_ready, t_start, t_end, t_result, result (1 | 0 | null), critical (0 | 1)] */
export type Visit = [string, number, number, number, number, 1 | 0 | null, 0 | 1]
/** one decision: [node, t, chosen option, offered options, {option: probability offered}] */
export type Choice = [string, number, string, string[], Record<string, number>]
export interface CohortPatient {
  id: number | string; cohort?: number; g: string; age: number; cancer: boolean | 0 | 1
  out: string; exit: string | null; t_exit: number | null; t_diag: number | null; t_treat: number | null; ft?: boolean | 0 | 1
  v: Visit[]; c: Choice[]
}
export interface FlowData {
  format: string
  scenario: string; flowchart: string; seeds: number[]; synthetic?: boolean
  clock_start?: string; target_days: number; warmup_days?: number
  totals: { n: number; n_cancer: number; missed_cancers: number; untreated_cancers: number; treated_cancers: number; stuck: number; cohorts: number }
  metrics: { n: number; share_within_target: number | null; median_days_to_treatment: number | null; median_days_to_diagnosis?: number | null; missed_cancers: number | null; [k: string]: unknown }
  by_group?: Record<string, Record<string, number | null>>
  graph: { nodes: FlowGraphNode[]; edges: FlowGraphEdge[]; stages?: string[] }
  steps: Record<string, FlowStep>
  resources?: Record<string, { label?: string; type?: string; capacity_per_day?: number; utilisation?: number }>
  queues: Record<string, FlowQueue>
  decisions: Record<string, FlowDecision>
  exits: Record<string, { n: number; n_cancer: number; outcome: string }>
  time_lost: TimeLost[]
  cohort: { seed?: number; size: number; horizon: number; time_zero?: number; strata?: Record<string, number>; patients: CohortPatient[] }
  meta?: Record<string, unknown>
}

// ---- optimisations (spec 05, service/routes/optimisations.py) ----
export interface OptChange {
  index: number
  kind: string
  target: string
  other?: string | null
  label: string
  records_reading?: string
  predicted_days_saved?: number | null
  linked_with?: number[]
  train?: { on_time_before?: number; on_time_after?: number; median_before?: number; median_after?: number }
  heldout_after_this_change?: { on_time?: number; median_days?: number; missed_cancers?: number; tests_per_patient?: number }
}
export interface OptBlocked { label?: string; kind?: string; target?: string; reason?: string; message?: string; [k: string]: unknown }
export interface Optimisation {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
  message: string
  flowchart: { id: string; version: number }
  settings?: Record<string, unknown>
  created_at?: string
  error?: string | null
  summary?: { n_changes?: number; n_blocked?: number; heldout_before?: number | null; heldout_after?: number | null } | null
  applied?: { accepted: number[]; flowchart: { id: string; version: number }; run_id?: string | null }[]
  changes?: OptChange[]
  blocked?: OptBlocked[]
  heldout?: { before?: Record<string, number | null>; after?: Record<string, number | null> }
  selection_optimism_pp?: number | null
  honesty?: string
  candidates_evaluated?: number
}
export interface OptimiseRequest {
  flowchart: { id: string; version: number }
  n?: number
  max_changes?: number
  allow?: string[]
}
export interface ApplyResult {
  flowchart: { id: string; version: number }
  based_on: { id: string; version: number }
  accepted: number[]
  run_id?: string
  baseline_run_id?: string
}
export interface CompareValue { a: number | null; b: number | null; delta: number | null }
export interface Comparison { same_patients: boolean; n: number; seeds: number[]; headline: Record<string, CompareValue>; by_group: Record<string, Record<string, CompareValue>> }

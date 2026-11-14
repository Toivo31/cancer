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

// ---- run layers (flow endpoint; shape agreed with plat/flow, see flow-format.md once merged) ----
export interface StepStats {
  /** patients who ran this step */
  n: number
  wait_median?: number | null
  wait_mean?: number | null
  took_median?: number | null
  /** days on the critical path, summed over patients, and share of all critical-path days */
  critical_days?: number
  critical_share?: number
  /** resource steps */
  queue?: { t: number[]; length: number[] } | null
}
export interface EdgeStats {
  n: number
}
export interface DecisionStats {
  offered: Record<string, number>
  chosen: Record<string, number>
  by_group?: Record<string, Record<string, number>>
}
export interface FlowData {
  run_id: string
  n_patients: number
  steps: Record<string, StepStats>
  edges: Record<string, EdgeStats>
  exits: Record<string, Record<string, number>>
  decisions: Record<string, DecisionStats>
  cohort?: unknown
}

import type { Api } from '../api/client'
import { ApiError } from '../api/client'
import type { FlowData, Flowchart, Job, Problem, Project, Run, RunRequest, Template, World } from '../api/types'
import { defaultShares } from '../lib/policy'
import templates from './fixtures/templates.json'
import mockMetrics from './fixtures/mock_metrics.json'

// An in-memory stand-in for the service (shapes from spec 03), persisted to localStorage so a reload
// keeps projects, saved versions and runs. Run numbers are real headline numbers from the shipped demo
// bundle for the UNEDITED flowcharts; the mock cannot recompute an edited one and says so.

interface TemplateFixture { id: string; name: string; description: string; world: World; flowcharts: Flowchart[] }
const TEMPLATES = templates as unknown as TemplateFixture[]
const METRICS = mockMetrics as Record<string, { n: number; share_within_target: number; median_days_to_treatment: number; missed_cancers: number }>

interface MockRun extends Run { template: string | null; started_ms: number; duration_ms: number; cancelled: boolean; edited: boolean }
interface DB {
  seq: number
  projects: (Project & { template: string | null })[]
  worlds: Record<string, World>
  flowcharts: Record<string, Record<string, Flowchart[]>>
  runs: Record<string, MockRun[]>
}

// Real flow documents from the engine (small cohorts), loaded on demand so they stay out of the main bundle.
const FLOWS: Record<string, () => Promise<{ default: unknown }>> = {
  'finland_lung/baseline': () => import('../../../docs/platform/fixtures/flow_finland.json'),
  'norway_check/observed': () => import('../../../docs/platform/fixtures/flow_norway.json'),
}

const KEY = 'pathway-mock-db-v1'
let db: DB = load()

function load(): DB {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(KEY) : null
    if (raw) return JSON.parse(raw) as DB
  } catch { /* ignore */ }
  return { seq: 1, projects: [], worlds: {}, flowcharts: {}, runs: {} }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(db)) } catch { /* quota or disabled: stay in memory */ }
}
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))
const nextId = (prefix: string) => `${prefix}_${(db.seq++).toString(36)}${Math.random().toString(36).slice(2, 5)}`
const wait = <T,>(v: T, ms = 60) => new Promise<T>((res) => setTimeout(() => res(clone(v)), ms))

export function resetMock() { db = { seq: 1, projects: [], worlds: {}, flowcharts: {}, runs: {} }; save() }

function project(p: string) {
  const x = db.projects.find((q) => q.id === p)
  if (!x) throw new ApiError(404, 'not_found', `No project ${p}`)
  return x
}

function sync(r: MockRun): MockRun {
  if (r.status === 'queued' || r.status === 'running') {
    if (r.cancelled) { r.status = 'cancelled'; return r }
    const f = Math.min(1, (Date.now() - r.started_ms) / r.duration_ms)
    r.progress = f
    r.status = f >= 1 ? 'succeeded' : 'running'
    if (f >= 1) {
      const m = r.template && !r.edited ? METRICS[`${r.template}/${r.flowchart.id}`] : undefined
      r.metrics = m
        ? { on_time_share: m.share_within_target, median_days: m.median_days_to_treatment, missed_cancers: m.missed_cancers, n_patients: m.n }
        : { on_time_share: null, median_days: null, missed_cancers: null, n_patients: r.n }
      if (!m) r.error = r.edited ? 'Mock mode: this version has edited probabilities, which only the real service can simulate.' : 'Mock mode has no stored numbers for this flowchart.'
      save()
    }
  }
  return r
}
const publicRun = (r: MockRun): Run => {
  const { template: _t, started_ms: _s, duration_ms: _d, cancelled: _c, edited: _e, ...rest } = r
  void _t; void _s; void _d; void _c; void _e
  return rest
}

export function checkProblems(fc: Flowchart): Problem[] {
  const out: Problem[] = []
  for (const [pid, pt] of Object.entries(fc.decision_policy.points)) {
    const tables = [{ name: 'default', probs: defaultShares(pt) }, ...(pt.rules ?? []).map((r, i) => ({ name: `rule ${i + 1}`, probs: r.probs }))]
    for (const t of tables) {
      if (!t.probs) continue
      const s = Object.values(t.probs).reduce((a, b) => a + b, 0)
      if (Math.abs(s - 1) > 1e-6) out.push({ severity: 'error', code: 'policy_probs_sum', node: pid, message: `The probabilities in ${t.name} add to ${(s * 100).toFixed(1)}, not 100.` })
    }
  }
  return out
}

export const mock: Api = {
  kind: 'mock',
  templates: () => wait(TEMPLATES.map<Template>(({ id, name, description, flowcharts }) => ({ id, name, description, flowcharts: flowcharts.map((f) => ({ id: f.id, name: f.name })) }))),
  listProjects: () => wait(db.projects),
  createProject: (name, template) => {
    const id = nextId('p')
    const p = { id, name, template: template ?? null, created_at: new Date().toISOString() }
    db.projects.unshift(p)
    const t = template ? TEMPLATES.find((x) => x.id === template) : undefined
    if (template && !t) return Promise.reject(new ApiError(404, 'not_found', `No template ${template}`))
    if (t) {
      db.worlds[id] = clone(t.world)
      db.flowcharts[id] = Object.fromEntries(t.flowcharts.map((f) => [f.id, [clone(f)]]))
    } else {
      db.worlds[id] = { schema_version: 1, id: 'blank', name }
      db.flowcharts[id] = {}
    }
    db.runs[id] = []
    save()
    return wait(p)
  },
  getProject: async (id) => wait(project(id)),
  deleteProject: async (id) => { db.projects = db.projects.filter((p) => p.id !== id); delete db.flowcharts[id]; delete db.runs[id]; save() },
  getWorld: async (p) => { project(p); return wait(db.worlds[p]) },
  listFlowcharts: async (p) => {
    project(p)
    return wait(Object.entries(db.flowcharts[p]).map(([id, vs]) => ({ id, name: vs[vs.length - 1].name, latest_version: vs.length, versions: vs.map((v) => v.version), locked: [...new Set((db.runs[p] ?? []).filter((r) => r.flowchart.id === id).map((r) => r.flowchart.version))] })))
  },
  getFlowchart: async (p, f, v) => {
    project(p)
    const doc = db.flowcharts[p]?.[f]?.find((x) => x.version === v)
    if (!doc) throw new ApiError(404, 'not_found', `No flowchart ${f} version ${v}`)
    return wait(doc)
  },
  saveFlowchart: async (p, f, doc) => {
    project(p)
    const vs = db.flowcharts[p]?.[f]
    if (!vs) throw new ApiError(404, 'not_found', `No flowchart ${f}`)
    const problems = checkProblems(doc).filter((x) => x.severity === 'error')
    if (problems.length) throw new ApiError(422, 'invalid_document', 'The flowchart has errors.', problems)
    const parent = vs[vs.length - 1]
    const saved = { ...clone(doc), version: parent.version + 1, parent_version: parent.version }
    vs.push(saved)
    save()
    return wait(saved)
  },
  validate: async (_p, fc) => { const problems = checkProblems(fc); return wait({ ok: !problems.some((x) => x.severity === 'error'), problems }) },
  startRun: async (p, req: RunRequest) => {
    const pr = project(p)
    const vs = db.flowcharts[p]?.[req.flowchart.id]
    const doc = vs?.find((x) => x.version === req.flowchart.version)
    if (!doc) throw new ApiError(404, 'not_found', 'No such flowchart version')
    const original = TEMPLATES.find((t) => t.id === pr.template)?.flowcharts.find((f) => f.id === doc.id)
    const edited = !original || JSON.stringify(original.decision_policy) !== JSON.stringify(doc.decision_policy)
    const id = nextId('r')
    const r: MockRun = {
      id, job_id: nextId('j'), status: 'running', progress: 0, label: req.label ?? '', flowchart: req.flowchart, n: req.n, seeds: req.seeds,
      created_at: new Date().toISOString(), metrics: null, error: null,
      template: pr.template, started_ms: Date.now(), duration_ms: 3500 + Math.min(6000, req.n / 8), cancelled: false, edited,
    }
    db.runs[p].unshift(r)
    save()
    return wait({ run_id: id, job_id: r.job_id!, status: 'queued' })
  },
  listRuns: async (p) => { project(p); return wait((db.runs[p] ?? []).map((r) => publicRun(sync(r)))) },
  getRun: async (p, r) => {
    project(p)
    const x = db.runs[p]?.find((q) => q.id === r)
    if (!x) throw new ApiError(404, 'not_found', `No run ${r}`)
    return wait(publicRun(sync(x)))
  },
  getJob: async (j) => {
    for (const rs of Object.values(db.runs)) {
      const r = rs.find((q) => q.job_id === j)
      if (r) {
        sync(r)
        const job: Job = { id: j, state: r.status, progress: r.progress, message: r.status === 'running' ? `Simulating ${r.n.toLocaleString('en')} patients` : r.status, error: r.status === 'failed' ? r.error : null }
        return wait(job)
      }
    }
    throw new ApiError(404, 'not_found', `No job ${j}`)
  },
  cancelJob: async (j) => {
    for (const rs of Object.values(db.runs)) {
      const r = rs.find((q) => q.job_id === j)
      if (r && (r.status === 'running' || r.status === 'queued')) { r.cancelled = true; sync(r); save() }
    }
  },
  getFlow: async (p, r) => {
    project(p)
    const run = db.runs[p]?.find((q) => q.id === r)
    if (!run) throw new ApiError(404, 'not_found', `No run ${r}`)
    sync(run)
    const loader = run.status === 'succeeded' && !run.edited && run.template ? FLOWS[`${run.template}/${run.flowchart.id}`] : undefined
    if (!loader) throw new ApiError(404, 'no_flow', 'Mock mode has run layers only for the unedited Norway "observed" and Finnish "baseline" flowcharts.')
    return clone((await loader()).default as unknown as FlowData)
  },
}

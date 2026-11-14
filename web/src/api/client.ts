import type {
  DecisionPolicy, FlowData, Flowchart, FlowchartSummary, Job, Project, Run, RunMetrics, RunRequest,
  Template, ValidationResult, World,
} from './types'

/** Everything the screens need from the service. HttpApi talks to /api; MockApi (../mock) answers from fixtures. */
export interface Api {
  readonly kind: 'http' | 'mock'
  templates(): Promise<Template[]>
  listProjects(): Promise<Project[]>
  createProject(name: string, template?: string | null): Promise<Project>
  getProject(id: string): Promise<Project>
  deleteProject(id: string): Promise<void>
  getWorld(p: string): Promise<World>
  listFlowcharts(p: string): Promise<FlowchartSummary[]>
  getFlowchart(p: string, f: string, v: number): Promise<Flowchart>
  /** Saves `doc` as the next version of flowchart f; returns the stored version. */
  saveFlowchart(p: string, f: string, doc: Flowchart): Promise<Flowchart>
  validate(p: string, flowchart: Flowchart): Promise<ValidationResult>
  startRun(p: string, req: RunRequest): Promise<{ run_id: string; job_id: string; status: string }>
  listRuns(p: string): Promise<Run[]>
  getRun(p: string, r: string): Promise<Run>
  getJob(j: string): Promise<Job>
  cancelJob(j: string): Promise<void>
  getFlow(p: string, r: string): Promise<FlowData>
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public problems?: unknown) {
    super(message)
  }
}

const BASE = '/api'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (e) {
    throw new ApiError(0, 'network', 'The service could not be reached.')
  }
  const text = await res.text()
  let data: unknown = undefined
  if (text) {
    try { data = JSON.parse(text) } catch { /* not JSON: the dev server's index.html when the proxy has no target */ }
  }
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; problems?: unknown } } | undefined)?.error
    throw new ApiError(res.status, err?.code ?? String(res.status), err?.message ?? `Request failed (${res.status})`, err?.problems)
  }
  if (data === undefined && res.status !== 204 && text) throw new ApiError(res.status, 'not_json', 'The service answered with something that is not JSON.')
  return data as T
}

// ---- wire -> app types. The spec fixes the paths, not every field name, so be forgiving here. ----
type Obj = Record<string, unknown>
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

export function normaliseMetrics(m: unknown): RunMetrics | null {
  if (!m || typeof m !== 'object') return null
  const o = m as Obj
  // metrics may be {mean: {...}, per_seed: [...]} or flat; the bundle format uses share_within_target
  const flat = (o.mean && typeof o.mean === 'object' ? o.mean : o) as Obj
  return {
    ...flat,
    on_time_share: num(flat.on_time_share) ?? num(flat.on_time) ?? num(flat.share_within_target),
    median_days: num(flat.median_days) ?? num(flat.median_days_to_treatment),
    missed_cancers: num(flat.missed_cancers),
    n_patients: num(flat.n_patients) ?? num(flat.n),
  }
}

export function normaliseRun(r: Obj): Run {
  const fc = (r.flowchart ?? {}) as Obj
  return {
    id: String(r.id ?? r.run_id),
    job_id: (r.job_id as string | null) ?? null,
    status: (r.status ?? r.state ?? 'queued') as Run['status'],
    progress: num(r.progress) ?? 0,
    label: String(r.label ?? ''),
    flowchart: { id: String(fc.id ?? r.flowchart_id ?? ''), version: Number(fc.version ?? r.flowchart_version ?? 1) },
    n: Number(r.n ?? 0),
    seeds: (r.seeds as number[]) ?? [],
    created_at: (r.created_at ?? r.created) as string | undefined,
    metrics: normaliseMetrics(r.headline ?? r.metrics),
    error: (r.error as string | null) ?? null,
  }
}

export const http: Api = {
  kind: 'http',
  templates: async () => {
    const r = await req<unknown>('GET', '/templates')
    return (Array.isArray(r) ? r : ((r as Obj).templates as unknown[]) ?? []) as Template[]
  },
  listProjects: async () => {
    const r = await req<unknown>('GET', '/projects')
    return (Array.isArray(r) ? r : ((r as Obj).projects as unknown[]) ?? []) as Project[]
  },
  createProject: (name, template) => req('POST', '/projects', { name, ...(template ? { template } : {}) }),
  getProject: (id) => req('GET', `/projects/${id}`),
  deleteProject: (id) => req('DELETE', `/projects/${id}`),
  getWorld: async (p) => { const r = await req<Obj>('GET', `/projects/${p}/world`); return (r.world ?? r) as World },
  listFlowcharts: async (p) => {
    const r = await req<unknown>('GET', `/projects/${p}/flowcharts`)
    const list = (Array.isArray(r) ? r : ((r as Obj).flowcharts as unknown[]) ?? []) as Obj[]
    return list.map((f) => {
      const latest = Number(f.latest_version ?? (f.latest as Obj | undefined)?.version ?? f.version ?? 1)
      const versions = Array.isArray(f.versions)
        ? (f.versions as unknown[]).map((v) => Number(typeof v === 'object' && v ? (v as Obj).version : v))
        : Array.from({ length: latest }, (_, i) => i + 1)
      const locked = Array.isArray(f.versions) ? (f.versions as Obj[]).filter((v) => typeof v === 'object' && v && v.locked).map((v) => Number(v.version)) : []
      return { id: String(f.id), name: String(f.name ?? (f.latest as Obj | undefined)?.name ?? f.id), latest_version: latest, versions, locked }
    })
  },
  getFlowchart: (p, f, v) => req('GET', `/projects/${p}/flowcharts/${f}/versions/${v}`),
  saveFlowchart: (p, f, doc) => req('POST', `/projects/${p}/flowcharts/${f}/versions`, doc),
  validate: (p, flowchart) => req('POST', `/projects/${p}/validate`, { flowchart }),
  startRun: (p, body) => req('POST', `/projects/${p}/runs`, body),
  listRuns: async (p) => {
    const r = await req<unknown>('GET', `/projects/${p}/runs`)
    return ((Array.isArray(r) ? r : ((r as Obj).runs as unknown[]) ?? []) as Obj[]).map(normaliseRun)
  },
  getRun: async (p, r) => normaliseRun(await req<Obj>('GET', `/projects/${p}/runs/${r}`)),
  getJob: async (j) => {
    const o = await req<Obj>('GET', `/jobs/${j}`)
    return { ...o, id: String(o.id ?? j), state: (o.state ?? o.status) as Job['state'], progress: num(o.progress) ?? 0 } as Job
  },
  cancelJob: async (j) => { await req('POST', `/jobs/${j}/cancel`) },
  getFlow: (p, r) => req('GET', `/projects/${p}/runs/${r}/flow`),
}

export type { DecisionPolicy }

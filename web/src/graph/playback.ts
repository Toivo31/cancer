import type { CohortPatient, FlowData } from '../api/types'

// Playback is a view of recorded results (spec 04): every position and counter is derived from the patients'
// events in the flow document, nothing is simulated here.

export type SegKind = 0 | 1 | 2 // waiting, being served, resting at an exit
export interface Seg { t0: number; t1: number; node: string; kind: SegKind }
export interface PPatient {
  idx: number
  p: CohortPatient
  segs: Seg[]
  treated: boolean
  late: boolean
  missed: boolean
  tDiag: number | null
  tTreat: number | null
  tExit: number | null
}

export function preparePatients(flow: FlowData, known: Set<string>): PPatient[] {
  const out: PPatient[] = []
  flow.cohort.patients.forEach((p, idx) => {
    const crit = p.v.filter((r) => r[6] === 1)
    const chain = (crit.length ? crit : p.v).slice().sort((a, b) => a[1] - b[1] || a[2] - b[2])
    const segs: Seg[] = []
    for (const r of chain) {
      if (!known.has(r[0])) continue
      segs.push({ t0: r[1], t1: r[2], node: r[0], kind: 0 })
      segs.push({ t0: r[2], t1: Math.max(r[4], r[2]), node: r[0], kind: 1 })
    }
    if (p.exit && known.has(p.exit) && p.t_exit != null) segs.push({ t0: Math.max(p.t_exit, segs.length ? segs[segs.length - 1].t0 : 0), t1: Infinity, node: p.exit, kind: 2 })
    if (!segs.length) return
    segs.sort((a, b) => a.t0 - b.t0 || a.kind - b.kind)
    const treated = p.out === 'treatment'
    out.push({
      idx, p, segs, treated,
      late: treated && p.t_treat != null && p.t_treat > flow.target_days,
      missed: !!p.cancer && p.out !== 'treatment',
      tDiag: p.t_diag, tTreat: p.t_treat, tExit: p.t_exit,
    })
  })
  return out
}

export interface PState {
  node: string
  kind: SegKind
  /** node the patient is travelling from, with progress 0..1, while moving between steps */
  from: string | null
  u: number
}

/** Where a patient is at time t (days since their first contact), or null before they arrive. */
export function stateAt(pp: PPatient, t: number, transit: number): PState | null {
  const segs = pp.segs
  if (t < segs[0].t0) return null
  let i = 0
  for (let k = segs.length - 1; k >= 0; k--) if (t >= segs[k].t0) { i = k; break }
  const g = segs[i]
  // the previous step's node, if this segment opens a new node
  let from: string | null = null
  for (let k = i - 1; k >= 0; k--) { if (segs[k].node !== g.node) { from = segs[k].node; break } if (k === 0) break }
  const arrival = firstOfRun(segs, i)
  if (from && t < arrival + transit) return { node: g.node, kind: g.kind, from, u: Math.min(1, Math.max(0, (t - arrival) / transit)) }
  return { node: g.node, kind: g.kind, from: null, u: 1 }
}

function firstOfRun(segs: Seg[], i: number): number {
  let k = i
  while (k > 0 && segs[k - 1].node === segs[i].node) k--
  return segs[k].t0
}

export interface Counters { arrived: number; waiting: number; served: number; diagnosed: number; treated: number; /** left the pathway without cancer */ left: number; /** had cancer and left without treatment */ missed: number; total: number }

export function counters(pps: PPatient[], t: number): Counters {
  const c: Counters = { arrived: 0, waiting: 0, served: 0, diagnosed: 0, treated: 0, left: 0, missed: 0, total: pps.length }
  for (const pp of pps) {
    if (t < pp.segs[0].t0) continue
    c.arrived++
    let k = pp.segs.length - 1
    while (k > 0 && t < pp.segs[k].t0) k--
    const g = pp.segs[k]
    if (g.kind === 0) c.waiting++
    else if (g.kind === 1) c.served++
    if (pp.tDiag != null && t >= pp.tDiag) c.diagnosed++
    if (pp.treated && pp.tTreat != null && t >= pp.tTreat) c.treated++
    else if (!pp.treated && pp.tExit != null && t >= pp.tExit) { if (pp.missed) c.missed++; else c.left++ }
  }
  return c
}

/** Stable pseudo-random numbers in [0,1) from a patient index, so a dot keeps its place in a pile. */
export function jitter(idx: number, salt = 0): number {
  let x = (idx + 1) * 374761393 + salt * 668265263
  x = (x ^ (x >>> 13)) * 1274126177
  x = x ^ (x >>> 16)
  return ((x >>> 0) % 10007) / 10007
}

/** Shortest chain of steps from a to b along the flowchart's connections, or null. */
export function bfsPath(adj: Map<string, string[]>, a: string, b: string): string[] | null {
  if (a === b) return [a]
  const prev = new Map<string, string | null>([[a, null]])
  const q = [a]
  while (q.length) {
    const u = q.shift()!
    for (const v of adj.get(u) ?? []) {
      if (prev.has(v)) continue
      prev.set(v, u)
      if (v === b) {
        const path: string[] = []
        for (let x: string | null = b; x != null; x = prev.get(x) ?? null) path.unshift(x)
        return path
      }
      q.push(v)
    }
  }
  return null
}

export function adjacency(edges: { from: string; to: string }[]): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const e of edges) { if (!m.has(e.from)) m.set(e.from, []); m.get(e.from)!.push(e.to) }
  return m
}

/** The steps and connections one patient went through, in order (their critical path, decisions and exit). */
export function patientPath(pp: PPatient, adj: Map<string, string[]>): { nodes: Set<string>; edges: Set<string> } {
  const seq: string[] = []
  for (const s of pp.segs) if (seq[seq.length - 1] !== s.node) seq.push(s.node)
  const nodes = new Set<string>(), edges = new Set<string>()
  seq.forEach((n, i) => {
    nodes.add(n)
    if (i === 0) return
    const path = bfsPath(adj, seq[i - 1], n)
    if (!path) return
    path.forEach((x, k) => { nodes.add(x); if (k) edges.add(`${path[k - 1]}>${x}`) })
  })
  for (const c of pp.p.c) nodes.add(c[0])
  return { nodes, edges }
}

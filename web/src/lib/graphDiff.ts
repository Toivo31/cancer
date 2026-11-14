import type { FlowEdge, FlowNode, Flowchart } from '../api/types'
import { defaultShares } from './policy'

export type Change = 'same' | 'added' | 'removed' | 'changed'
export interface NodeDiff { id: string; change: Change; label: string; what: string[] }
export interface EdgeDiff { from: string; to: string; change: Change; typeA?: string; typeB?: string }
export interface GraphDiff {
  nodes: Record<string, NodeDiff>
  edges: Record<string, EdgeDiff>
  /** short sentences, one per difference, in a stable order */
  lines: string[]
  counts: { added: number; removed: number; changed: number; edgesAdded: number; edgesRemoved: number; edgesChanged: number }
  identical: boolean
}

export const edgeKey = (from: string, to: string) => `${from}\u0001${to}`

const FIELD: [keyof FlowNode, string][] = [
  ['label', 'label'], ['kind', 'kind'], ['test', 'what happens'], ['when', 'guard'], ['stage', 'stage'], ['outcome', 'outcome'], ['fast_track', 'fast track'],
]
const show = (v: unknown) => (v === undefined || v === '' ? 'none' : String(v))
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

function nodeChanges(a: FlowNode, b: FlowNode): string[] {
  const out: string[] = []
  for (const [k, name] of FIELD) if (!same(a[k], b[k])) out.push(`${name}: ${show(a[k])} → ${show(b[k])}`)
  if (!same([...(a.options ?? [])].sort(), [...(b.options ?? [])].sort())) out.push('options changed')
  if (!same(a.availability, b.availability)) out.push('availability changed')
  if (!same(a.retry, b.retry)) out.push('retry changed')
  return out
}

function sharesText(s?: Record<string, number>): string {
  return s ? Object.entries(s).map(([k, v]) => `${k} ${Math.round(v * 1000) / 10}%`).join(', ') : 'none'
}

/** Compare two versions of a flowchart: steps and connections added, removed or changed, and decisions whose probabilities moved. */
export function diffFlowcharts(a: Flowchart, b: Flowchart): GraphDiff {
  const na = new Map(a.nodes.map((n) => [n.id, n])), nb = new Map(b.nodes.map((n) => [n.id, n]))
  const nodes: Record<string, NodeDiff> = {}
  const lines: string[] = []
  const counts = { added: 0, removed: 0, changed: 0, edgesAdded: 0, edgesRemoved: 0, edgesChanged: 0 }
  const label = (id: string) => nb.get(id)?.label ?? na.get(id)?.label ?? id

  for (const n of b.nodes) {
    const o = na.get(n.id)
    if (!o) { nodes[n.id] = { id: n.id, change: 'added', label: n.label, what: [] }; counts.added++ }
    else {
      const what = nodeChanges(o, n)
      // probabilities are a property of the decision, shown on the decision's box
      const pa = defaultShares(a.decision_policy?.points?.[n.id]), pb = defaultShares(b.decision_policy?.points?.[n.id])
      if (n.kind === 'decision' && (!same(pa, pb) || (a.decision_policy?.points?.[n.id]?.rules?.length ?? 0) !== (b.decision_policy?.points?.[n.id]?.rules?.length ?? 0))) what.push(`probabilities: ${sharesText(pa)} → ${sharesText(pb)}`)
      nodes[n.id] = { id: n.id, change: what.length ? 'changed' : 'same', label: n.label, what }
      if (what.length) counts.changed++
    }
  }
  for (const n of a.nodes) if (!nb.has(n.id)) { nodes[n.id] = { id: n.id, change: 'removed', label: n.label, what: [] }; counts.removed++ }

  const ea = new Map<string, FlowEdge>(a.edges.map((e) => [edgeKey(e.from, e.to), e])), eb = new Map<string, FlowEdge>(b.edges.map((e) => [edgeKey(e.from, e.to), e]))
  const edges: Record<string, EdgeDiff> = {}
  for (const [k, e] of eb) {
    const o = ea.get(k)
    if (!o) { edges[k] = { from: e.from, to: e.to, change: 'added', typeB: e.type }; counts.edgesAdded++ }
    else if (o.type !== e.type) { edges[k] = { from: e.from, to: e.to, change: 'changed', typeA: o.type, typeB: e.type }; counts.edgesChanged++ }
    else edges[k] = { from: e.from, to: e.to, change: 'same', typeA: o.type, typeB: e.type }
  }
  for (const [k, e] of ea) if (!eb.has(k)) { edges[k] = { from: e.from, to: e.to, change: 'removed', typeA: e.type }; counts.edgesRemoved++ }

  // in words: steps first, then connections
  for (const d of Object.values(nodes)) {
    if (d.change === 'added') lines.push(`New step: ${d.label}`)
    else if (d.change === 'removed') lines.push(`Step removed: ${d.label}`)
    else if (d.change === 'changed') lines.push(`${d.label}: ${d.what.join('; ')}`)
  }
  const ends = (e: EdgeDiff) => `${label(e.from)} → ${label(e.to)}`
  for (const e of Object.values(edges)) {
    if (e.change === 'added') lines.push(`New connection (${e.typeB}): ${ends(e)}`)
    else if (e.change === 'removed') lines.push(`Connection removed (${e.typeA}): ${ends(e)}`)
    else if (e.change === 'changed') lines.push(`Connection ${ends(e)} changed from ${e.typeA} to ${e.typeB}`)
  }
  return { nodes, edges, lines, counts, identical: lines.length === 0 }
}

/** Steps and connections of both versions merged, so one layout can place both drawings identically. A step keeps the newer version's data. */
export function unionGraph(a: Flowchart, b: Flowchart): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const nodes = new Map<string, FlowNode>()
  for (const n of a.nodes) nodes.set(n.id, n)
  for (const n of b.nodes) nodes.set(n.id, n)
  const edges = new Map<string, FlowEdge>()
  for (const e of a.edges) edges.set(edgeKey(e.from, e.to), e)
  for (const e of b.edges) edges.set(edgeKey(e.from, e.to), e)
  return { nodes: [...nodes.values()], edges: [...edges.values()] }
}

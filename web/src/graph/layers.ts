import type { Flowchart, FlowData } from '../api/types'
import { defaultShares } from '../lib/policy'

export type Layer = 'structure' | 'flow' | 'time' | 'queues' | 'decisions'
export const LAYERS: { id: Layer; label: string; hint: string }[] = [
  { id: 'structure', label: 'Structure', hint: 'The flowchart as drawn, with the probabilities it offers' },
  { id: 'flow', label: 'Flow', hint: 'How many patients took each connection' },
  { id: 'time', label: 'Time', hint: 'Median wait at each step, and its share of the time to treatment' },
  { id: 'queues', label: 'Queues', hint: 'Patients waiting at steps that book a limited resource' },
  { id: 'decisions', label: 'Decisions', hint: 'Shares actually chosen against the shares offered' },
]

export interface NodeOverlay { fill?: string; border?: string; borderWidth?: number; badge?: string; sub?: string; subColor?: string; spark?: number[]; glow?: boolean }
export interface EdgeOverlay { width?: number; label?: string; color?: string; opacity?: number; dashed?: boolean }
export interface Overlay { nodes: Record<string, NodeOverlay>; edges: Record<string, EdgeOverlay>; legend: string }

const AMBER = '255,192,77', BLUE = '98,176,255'
const fmt = (n: number) => Math.round(n).toLocaleString('en')
const f1 = (x: number) => (Math.round(x * 10) / 10).toFixed(1)
const pct = (x: number) => `${Math.round(x * 100)}%`
const clamp = (x: number, a: number, b: number) => Math.max(a, Math.min(b, x))

/** Edge key used by overlays: connections are identified by their ends, as in the flow document. */
export const pairKey = (from: string, to: string) => `${from}>${to}`

export function buildOverlay(fc: Flowchart, flow: FlowData, layer: Layer, labelOf: (id: string) => string): Overlay {
  const nodes: Record<string, NodeOverlay> = {}
  const edges: Record<string, EdgeOverlay> = {}
  if (layer === 'structure') return { nodes, edges, legend: '' }

  const maxE = Math.max(1, ...flow.graph.edges.map((e) => e.n))
  const maxWait = Math.max(0.1, ...Object.values(flow.steps).map((s) => s.wait_median ?? 0))
  const maxCrit = Math.max(0.01, ...Object.values(flow.steps).map((s) => s.critical_share ?? 0))
  const maxQ = Math.max(0.1, ...Object.values(flow.queues).map((q) => q.mean))

  for (const e of flow.graph.edges) {
    const a = Math.sqrt(e.n / maxE)
    edges[pairKey(e.source, e.target)] = {
      width: e.n ? 0.8 + 5.2 * a : 1,
      opacity: e.n ? (layer === 'flow' ? 0.35 + 0.6 * a : 0.2 + 0.35 * a) : 0.1,
      color: layer === 'flow' ? '#8FB6D9' : undefined,
      dashed: e.n === 0,
      label: layer === 'flow' && e.n > 0.18 * maxE ? fmt(e.n) : '',
    }
  }

  for (const n of fc.nodes) {
    const st = flow.steps[n.id], dc = flow.decisions[n.id], ex = flow.exits[n.id]
    const o: NodeOverlay = {}
    if (layer === 'flow') {
      if (n.kind === 'exit' && ex) o.sub = `${fmt(ex.n)} patients${ex.n_cancer && ex.outcome !== 'treatment' ? ` (${fmt(ex.n_cancer)} cancer)` : ''}`
      else if (dc) o.sub = `${fmt(dc.n)} decisions`
      else if (st) o.sub = `${fmt(st.n)} patients`
    } else if (layer === 'time') {
      if (st && st.wait_median != null) {
        const a = clamp(Math.sqrt(st.wait_median / maxWait), 0, 1)
        o.fill = `rgba(${AMBER},${(0.05 + 0.5 * a).toFixed(3)})`
        o.border = a > 0.5 ? '#FFC04D' : undefined
        o.borderWidth = st.critical_share ? 1 + 2.4 * Math.sqrt(st.critical_share / maxCrit) : undefined
        o.sub = `wait ${f1(st.wait_median)} d${st.critical_share ? ` · ${pct(st.critical_share)} of path` : ''}`
        o.subColor = a > 0.4 ? '#FFC04D' : undefined
      } else if (st) o.sub = `${fmt(st.n)} patients`
    } else if (layer === 'queues') {
      const q = flow.queues[n.id]
      if (q) {
        const a = clamp(Math.sqrt(q.mean / maxQ), 0, 1)
        o.fill = `rgba(${BLUE},${(0.04 + 0.32 * a).toFixed(3)})`
        o.spark = q.y.map((v) => clamp(v / Math.max(1, q.peak), 0, 1))
        o.sub = `peak ${fmt(q.peak)} waiting`
        o.subColor = '#62B0FF'
      } else if (st) o.sub = `${fmt(st.n)} patients`
    } else if (layer === 'decisions') {
      if (dc && dc.n) {
        const top = Object.entries(dc.share).sort((a, b) => b[1] - a[1])[0]
        o.sub = `${pct(top[1])} ${labelOf(top[0])}`
        o.subColor = '#B79CFF'
      } else if (st) o.sub = `${fmt(st.n)} patients`
    }
    if (o.sub || o.fill) nodes[n.id] = o
  }

  if (layer === 'decisions') {
    for (const [id, dc] of Object.entries(flow.decisions)) {
      const offered = defaultShares(fc.decision_policy.points[id])
      for (const [opt, share] of Object.entries(dc.share)) {
        const off = offered?.[opt]
        const differs = off !== undefined && Math.abs(off - share) >= 0.02
        edges[pairKey(id, opt)] = {
          width: 0.8 + 5.2 * Math.sqrt((dc.chosen[opt] ?? 0) / Math.max(1, dc.n)),
          color: '#B79CFF', opacity: 0.9,
          label: `${pct(share)}${differs ? ` (offered ${pct(off!)})` : ''}`,
        }
      }
    }
  }

  const legend = {
    flow: 'Line width and number: patients who took the connection. Steps show how many passed through.',
    time: 'Amber: median wait at the step. Border weight: its share of the days from first contact to treatment.',
    queues: 'Blue: average number waiting for the step’s resource; the line is the queue over the run.',
    decisions: 'Violet: share of patients each option was chosen for, against the share offered when they differ.',
  }[layer]
  return { nodes, edges, legend }
}

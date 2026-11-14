import dagre from '@dagrejs/dagre'
import type { FlowEdge, FlowNode, Flowchart, NodeKind } from '../api/types'
import { assignLanes, countCrossings } from './layoutScore'

export interface Box { x: number; y: number; w: number; h: number; row: number }

/** Node footprint by kind, in canvas pixels. Used both by the layout and by the node components. */
export const SIZE: Record<NodeKind, { w: number; h: number }> = {
  step: { w: 180, h: 60 },
  decision: { w: 180, h: 60 },
  join: { w: 128, h: 36 },
  milestone: { w: 160, h: 44 },
  exit: { w: 160, h: 48 },
}
/** Lines a label needs when words wrap within `chars` characters (a greedy estimate; the box grows to fit). */
export function wrapLines(label: string, chars: number): number {
  let lines = 1, cur = 0
  for (const word of label.split(/\s+/).filter(Boolean)) {
    const w = word.length
    if (cur === 0) cur = w
    else if (cur + 1 + w <= chars) cur += 1 + w
    else { lines++; cur = w }
    while (cur > chars) { lines++; cur -= chars }
  }
  return lines
}

/** Footprint of one step: the kind's width, and a height that fits the whole label (no cut-off text). */
export function nodeSize(n: Pick<FlowNode, 'kind' | 'label'>): { w: number; h: number } {
  const { w, h } = SIZE[n.kind]
  const lines = wrapLines(n.label ?? '', Math.max(8, Math.floor((w - 26) / 6.4)))
  if (n.kind === 'join') return { w, h: Math.max(h, 14 + lines * 14) }
  if (n.kind === 'step' || n.kind === 'decision') return { w, h: Math.max(h, 18 + 12 + lines * 15 + 12) }
  return { w, h: Math.max(h, 22 + 12 + lines * 15) }
}
const RANKSEP = 64
const ROWGAP = 96

export interface Layout { boxes: Record<string, Box>; rows: number; width: number; height: number; rowTop: number[]; rowBottom: number[]; /** lane of each connection (same order as the edges given), see assignLanes */ lanes?: number[] }
export const MARGIN_X = -40
export const ROW_GAP = ROWGAP
/** Bump when the automatic layout changes in a way that makes older stored box positions meaningless (see viewLayout.ts). */
export const LAYOUT_VERSION = 2

type Ranker = 'network-simplex' | 'tight-tree' | 'longest-path'
interface Setup { ranker: Ranker; nodesep: number; perRow: boolean }

function dagreGraph(nodes: FlowNode[], edges: FlowEdge[], size: Map<string, { w: number; h: number }>, o: { ranker: Ranker; nodesep: number }, minlen?: (e: FlowEdge) => number) {
  const g = new dagre.graphlib.Graph({ multigraph: true })
  g.setGraph({ rankdir: 'LR', ranksep: RANKSEP, nodesep: o.nodesep, edgesep: 12, marginx: 0, marginy: 0, ranker: o.ranker })
  g.setDefaultEdgeLabel(() => ({}))
  const ids = new Set(nodes.map((n) => n.id))
  for (const n of nodes) g.setNode(n.id, { width: size.get(n.id)!.w, height: size.get(n.id)!.h })
  edges.forEach((e, i) => {
    if (ids.has(e.from) && ids.has(e.to) && e.from !== e.to) g.setEdge(e.from, e.to, { minlen: minlen ? minlen(e) : 1, weight: e.type === 'option' ? 2 : 1 }, String(i))
  })
  dagre.layout(g)
  return g
}

/** Layouts of one drawing: every combination of dagre ranker and spacing, whole-drawing or per-row vertical placement, and number of rows. */
export function candidates(nodes: FlowNode[], edges: FlowEdge[]): Layout[] {
  const size = new Map(nodes.map((n) => [n.id, nodeSize(n)]))
  const out: Layout[] = []
  const setups: Setup[] = []
  for (const [ranker, nodesep, perRow] of [['network-simplex', 22, false], ['network-simplex', 22, true], ['tight-tree', 30, true]] as [Ranker, number, boolean][]) setups.push({ ranker, nodesep, perRow })
  for (const st of setups) {
    const g = dagreGraph(nodes, edges, size, st)
    // ranks = distinct x centres, left to right
    const cx = nodes.map((n) => Math.round(g.node(n.id).x))
    const rankCx = [...new Set(cx)].sort((a, b) => a - b)
    const rankOf = new Map(nodes.map((n, i) => [n.id, rankCx.indexOf(cx[i])]))
    const R = rankCx.length
    const rankW = new Array(R).fill(0)
    nodes.forEach((n) => { rankW[rankOf.get(n.id)!] = Math.max(rankW[rankOf.get(n.id)!], size.get(n.id)!.w) })
    const rankX: number[] = []
    let acc = 0
    for (let r = 0; r < R; r++) { rankX[r] = acc; acc += rankW[r] + RANKSEP }
    const total = acc - RANKSEP
    // edges that would cross a cut placed before rank r
    const cross = new Array(R + 1).fill(0)
    for (const e of edges) {
      const a = rankOf.get(e.from), b = rankOf.get(e.to)
      if (a === undefined || b === undefined) continue
      for (let r = a + 1; r <= b; r++) cross[r]++
    }

    /** Vertical centres of the steps of one row. With `perRow` the row is laid out on its own, so connections that leave the row do not reserve space inside it. */
    const rowCentres = (inRow: FlowNode[]): Map<string, number> => {
      const y = new Map<string, number>()
      if (!st.perRow) { for (const n of inRow) y.set(n.id, g.node(n.id).y); return y }
      const sub = dagreGraph(inRow, edges, size, { ...st, ranker: 'longest-path' }, (e) => Math.max(1, (rankOf.get(e.to) ?? 0) - (rankOf.get(e.from) ?? 0)))
      for (const n of inRow) y.set(n.id, sub.node(n.id).y)
      // steps of one column must not overlap after the row was ranked on its own
      const cols = new Map<number, FlowNode[]>()
      for (const n of inRow) { const r = rankOf.get(n.id)!; cols.set(r, [...(cols.get(r) ?? []), n]) }
      for (const col of cols.values()) {
        col.sort((a, b) => y.get(a.id)! - y.get(b.id)!)
        let bottom = -Infinity
        for (const n of col) {
          const h = size.get(n.id)!.h
          const yy = Math.max(y.get(n.id)!, bottom + st.nodesep + h / 2)
          y.set(n.id, yy); bottom = yy + h / 2
        }
      }
      return y
    }

    for (let k = 1; k <= Math.min(5, R); k++) {
      // cut points: near equal widths, nudged to where fewest connections cross
      const cuts: number[] = [0]
      let ok = true
      for (let j = 1; j < k; j++) {
        const want = (total * j) / k
        let best = -1, bestScore = Infinity
        for (let r = cuts[cuts.length - 1] + 1; r < R; r++) {
          const dist = Math.abs(rankX[r] - want)
          if (dist > total / k / 3) continue
          const score = cross[r] * 120 + dist
          if (score < bestScore) { bestScore = score; best = r }
        }
        if (best < 0) { ok = false; break }
        cuts.push(best)
      }
      if (!ok) continue
      cuts.push(R)
      const rowOfRank = new Array(R).fill(0)
      for (let j = 0; j < k; j++) for (let r = cuts[j]; r < cuts[j + 1]; r++) rowOfRank[r] = j
      const boxes: Record<string, Box> = {}
      let y0 = 0, width = 0
      const rowTop: number[] = [], rowBottom: number[] = []
      for (let j = 0; j < k; j++) {
        const inRow = nodes.filter((n) => rowOfRank[rankOf.get(n.id)!] === j)
        if (!inRow.length) continue
        const yc = rowCentres(inRow)
        const top = Math.min(...inRow.map((n) => yc.get(n.id)! - size.get(n.id)!.h / 2))
        const bottom = Math.max(...inRow.map((n) => yc.get(n.id)! + size.get(n.id)!.h / 2))
        const left = rankX[cuts[j]]
        for (const n of inRow) {
          const r = rankOf.get(n.id)!
          const sz = size.get(n.id)!
          boxes[n.id] = { x: rankX[r] - left + (rankW[r] - sz.w) / 2, y: y0 + (yc.get(n.id)! - sz.h / 2 - top), w: sz.w, h: sz.h, row: j }
          width = Math.max(width, boxes[n.id].x + boxes[n.id].w)
        }
        rowTop[j] = y0; rowBottom[j] = y0 + bottom - top
        y0 += bottom - top + ROWGAP
      }
      out.push({ boxes, rows: k, width, height: y0 - ROWGAP, rowTop, rowBottom })
    }
  }
  return out
}

/**
 * Left-to-right layered layout (dagre), then wrapped into rows like lines of text so a long pathway stays
 * legible on one screen. Several layouts are built (dagre's rankers, tighter or looser spacing, each row laid out
 * on its own or the whole drawing at once, one to five rows) and the best is kept: the largest scale on a laptop
 * canvas, discounted by the number of crossing connections (see layoutScore). Steps that run in parallel stack
 * within a rank; a connection that crosses a row break goes from the bottom of its source to the top of its
 * target (see edgeGeometry).
 */
export function layoutFlowchart(nodes: FlowNode[], edges: FlowEdge[], view = LAPTOP_CANVAS): Layout {
  // the same drawing is asked for again and again (a version is opened twice, a label is retyped): keep the last few results
  const ck = `${view.w}x${view.h}|${nodes.map((n) => { const z = nodeSize(n); return `${n.id}:${n.kind}:${z.w}x${z.h}` }).join('|')}#${edges.map((e) => `${e.from}>${e.to}:${e.type}`).join('|')}`
  const hit = CACHE.get(ck)
  if (hit) return hit
  const out = compute(nodes, edges, view)
  CACHE.set(ck, out)
  if (CACHE.size > 12) CACHE.delete(CACHE.keys().next().value as string)
  return out
}
const CACHE = new Map<string, Layout>()

function compute(nodes: FlowNode[], edges: FlowEdge[], view: { w: number; h: number }): Layout {
  const list = candidates(nodes, edges).filter((l) => l.rows > 0)
  if (!list.length) return { boxes: {}, rows: 0, width: 0, height: 0, rowTop: [], rowBottom: [] }
  const scaleOf = (l: Layout) => Math.min(view.w / (l.width + 60), view.h / (l.height + 60))
  const top = Math.max(...list.map(scaleOf))
  // crossings are only counted for layouts that could win (the count is the slow part)
  let best: Layout | null = null, bestScore = -1
  const contenders = list.filter((l) => scaleOf(l) >= top * 0.6).sort((a, b) => a.rows - b.rows)
  for (const l of contenders) {
    const s = scaleOf(l)
    l.lanes = assignLanes(l, edges)
    const score = s / (1 + countCrossings(l, edges) / 12)
    if (score > bestScore * 1.03) { best = l; bestScore = score } // prefer fewer rows unless clearly better
  }
  const chosen = best ?? list[0]
  chosen.lanes ??= assignLanes(chosen, edges)
  return chosen
}

/** The canvas the layout is judged against: a 1440 x 900 laptop with the side panel open. */
export const LAPTOP_CANVAS = { w: 1100, h: 700 }

/** A key that changes only when the drawing's structure does (not when probabilities or labels change). */
export function structureKey(fc: Pick<Flowchart, 'nodes' | 'edges'>): string {
  return fc.nodes.map((n) => `${n.id}:${n.kind}`).join('|') + '#' + fc.edges.map((e) => `${e.from}>${e.to}:${e.type}`).join('|')
}

/** Boxes that overlap (used by the test that both templates draw without overlaps). */
export function overlaps(boxes: Record<string, Box>): [string, string][] {
  const ids = Object.keys(boxes)
  const out: [string, string][] = []
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
    const a = boxes[ids[i]], b = boxes[ids[j]]
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) out.push([ids[i], ids[j]])
  }
  return out
}

import dagre from '@dagrejs/dagre'
import type { FlowEdge, FlowNode, Flowchart, NodeKind } from '../api/types'

export interface Box { x: number; y: number; w: number; h: number; row: number }

/** Node footprint by kind, in canvas pixels. Used both by the layout and by the node components. */
export const SIZE: Record<NodeKind, { w: number; h: number }> = {
  step: { w: 180, h: 60 },
  decision: { w: 180, h: 60 },
  join: { w: 128, h: 36 },
  milestone: { w: 160, h: 44 },
  exit: { w: 160, h: 48 },
}
const RANKSEP = 56
const ROWGAP = 96

export interface Layout { boxes: Record<string, Box>; rows: number; width: number; height: number; rowTop: number[]; rowBottom: number[] }
export const MARGIN_X = -40
export const ROW_GAP = ROWGAP

/**
 * Left-to-right layered layout (dagre), then wrapped into rows like lines of text so a long pathway stays
 * legible on one screen. The number of rows is chosen so the whole drawing fits a landscape canvas at the
 * largest scale. Steps that run in parallel stack within a rank; a connection that crosses a row break goes
 * from the bottom of its source to the top of its target (see rowOf).
 */
export function layoutFlowchart(nodes: FlowNode[], edges: FlowEdge[], view = { w: 1400, h: 760 }, ranker: 'network-simplex' | 'tight-tree' | 'longest-path' = 'network-simplex'): Layout {
  const g = new dagre.graphlib.Graph({ multigraph: true })
  g.setGraph({ rankdir: 'LR', ranksep: RANKSEP, nodesep: 22, edgesep: 12, marginx: 0, marginy: 0, ranker })
  g.setDefaultEdgeLabel(() => ({}))
  const ids = new Set(nodes.map((n) => n.id))
  for (const n of nodes) g.setNode(n.id, { width: SIZE[n.kind].w, height: SIZE[n.kind].h })
  edges.forEach((e, i) => {
    if (ids.has(e.from) && ids.has(e.to) && e.from !== e.to) g.setEdge(e.from, e.to, { minlen: 1, weight: e.type === 'option' ? 2 : 1 }, String(i))
  })
  dagre.layout(g)

  // ranks = distinct x centres, left to right
  const cx = nodes.map((n) => Math.round(g.node(n.id).x))
  const rankCx = [...new Set(cx)].sort((a, b) => a - b)
  const rankOf = new Map(nodes.map((n, i) => [n.id, rankCx.indexOf(cx[i])]))
  const R = rankCx.length
  const rankW = new Array(R).fill(0)
  nodes.forEach((n) => { rankW[rankOf.get(n.id)!] = Math.max(rankW[rankOf.get(n.id)!], SIZE[n.kind].w) })
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

  const build = (k: number): Layout => {
    // cut points: near equal widths, nudged to where fewest connections cross
    const cuts: number[] = [0]
    for (let j = 1; j < k; j++) {
      const want = (total * j) / k
      let best = -1, bestScore = Infinity
      for (let r = cuts[cuts.length - 1] + 1; r < R; r++) {
        const dist = Math.abs(rankX[r] - want)
        if (dist > total / k / 3) continue
        const score = cross[r] * 120 + dist
        if (score < bestScore) { bestScore = score; best = r }
      }
      if (best < 0) return { boxes: {}, rows: 0, width: Infinity, height: Infinity, rowTop: [], rowBottom: [] }
      cuts.push(best)
    }
    cuts.push(R)
    const rowOfRank = new Array(R).fill(0)
    for (let j = 0; j < k; j++) for (let r = cuts[j]; r < cuts[j + 1]; r++) rowOfRank[r] = j
    const boxes: Record<string, Box> = {}
    let y0 = 0, width = 0
    const rowTop: number[] = [], rowBottom: number[] = []
    for (let j = 0; j < k; j++) {
      const inRow = nodes.filter((n) => rowOfRank[rankOf.get(n.id)!] === j)
      if (!inRow.length) continue
      const top = Math.min(...inRow.map((n) => g.node(n.id).y - SIZE[n.kind].h / 2))
      const bottom = Math.max(...inRow.map((n) => g.node(n.id).y + SIZE[n.kind].h / 2))
      const left = rankX[cuts[j]]
      for (const n of inRow) {
        const r = rankOf.get(n.id)!
        boxes[n.id] = { x: rankX[r] - left + (rankW[r] - SIZE[n.kind].w) / 2, y: y0 + (g.node(n.id).y - SIZE[n.kind].h / 2 - top), w: SIZE[n.kind].w, h: SIZE[n.kind].h, row: j }
        width = Math.max(width, boxes[n.id].x + boxes[n.id].w)
      }
      rowTop[j] = y0; rowBottom[j] = y0 + bottom - top
      y0 += bottom - top + ROWGAP
    }
    return { boxes, rows: k, width, height: y0 - ROWGAP, rowTop, rowBottom }
  }

  let best: Layout | null = null, bestScale = -1
  for (let k = 1; k <= Math.min(7, R); k++) {
    const l = build(k)
    if (!l.rows) continue
    const s = Math.min(view.w / (l.width + 60), view.h / (l.height + 60))
    if (s > bestScale * 1.04) { best = l; bestScale = s } // prefer fewer rows unless clearly larger
  }
  return best ?? build(1)
}

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

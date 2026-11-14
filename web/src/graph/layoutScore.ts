import type { FlowEdge } from '../api/types'
import { edgeGeometry } from './geometry'
import type { Box, Layout } from './layout'

type Pt = [number, number]
const orient = (p: Pt, q: Pt, r: Pt) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
const cut = (a: Pt, b: Pt, c: Pt, d: Pt) => orient(a, b, c) * orient(a, b, d) < 0 && orient(c, d, a) * orient(c, d, b) < 0

export const MAX_LANE = 9

/**
 * Lanes for the connections that run along the channel between rows. Two connections that leave and enter the same
 * channel cross when one's vertical run meets the other's horizontal run, which depends on which one is nearer the
 * row above. For each channel the order with the fewest such crossings is searched (swaps from a sensible start),
 * and the lanes follow that order. Connections inside a row get lane 0 (their curves do not use the channel).
 */
export function assignLanes(layout: Pick<Layout, 'boxes' | 'rowTop' | 'rowBottom'>, edges: FlowEdge[]): number[] {
  const lanes = edges.map(() => 0)
  const groups = new Map<string, number[]>()
  edges.forEach((e, i) => {
    const a = layout.boxes[e.from], b = layout.boxes[e.to]
    if (!a || !b || b.row <= a.row) return
    const k = `${a.row}>${b.row}`
    groups.set(k, [...(groups.get(k) ?? []), i])
  })
  for (const idx of groups.values()) {
    const info = idx.map((i) => { const a = layout.boxes[edges[i].from], b = layout.boxes[edges[i].to]; const sx = a.x + a.w + 14, tx = b.x + b.w / 2; return { i, sx, tx, lo: Math.min(sx, tx), hi: Math.max(sx, tx) } })
    const inSpan = (x: number, o: { lo: number; hi: number }) => x > o.lo && x < o.hi
    const above = (p: (typeof info)[number], q: (typeof info)[number]) => (inSpan(q.sx, p) ? 1 : 0) + (inSpan(p.tx, q) ? 1 : 0) // cost of p being nearer the row above than q
    let order = info.slice().sort((p, q) => q.tx - p.tx || p.sx - q.sx)
    const cost = (o: typeof info) => { let c = 0; for (let a = 0; a < o.length; a++) for (let b = a + 1; b < o.length; b++) c += above(o[a], o[b]); return c }
    let best = cost(order)
    for (let pass = 0; pass < 6 && best > 0; pass++) {
      let improved = false
      for (let a = 0; a < order.length; a++) for (let b = a + 1; b < order.length; b++) {
        const t = order.slice(); [t[a], t[b]] = [t[b], t[a]]
        const c = cost(t)
        if (c < best) { best = c; order = t; improved = true }
      }
      if (!improved) break
    }
    order.forEach((o, rank) => { lanes[o.i] = Math.min(MAX_LANE, rank) })
  }
  return lanes
}

/** Routes of every connection as the canvas draws them (same lanes as FlowCanvas). */
export function routesOf(layout: Layout, edges: FlowEdge[], lanes = layout.lanes ?? assignLanes(layout, edges)): (Pt[] | null)[] {
  return edges.map((e, i) => {
    const a = layout.boxes[e.from], b = layout.boxes[e.to]
    if (!a || !b) return null
    const p = edgeGeometry(a, b, layout, lanes[i]).pts
    // a coarse polyline is enough to count crossings (and 16 times cheaper)
    return p.length > 6 ? p.filter((_, k) => k % 4 === 0 || k === p.length - 1) : p
  })
}

const bbox = (p: Pt[]) => p.reduce((m, [x, y]) => [Math.min(m[0], x), Math.min(m[1], y), Math.max(m[2], x), Math.max(m[3], y)], [Infinity, Infinity, -Infinity, -Infinity])

/** How many pairs of drawn connections cross (pairs that share a step are not counted: they meet there by design). */
export function countCrossings(layout: Layout, edges: FlowEdge[]): number {
  const routes = routesOf(layout, edges)
  const bb = routes.map((r) => (r ? bbox(r) : null))
  let n = 0
  for (let i = 0; i < edges.length; i++) {
    const A = routes[i]; if (!A) continue
    for (let j = i + 1; j < edges.length; j++) {
      const B = routes[j]; if (!B) continue
      const ei = edges[i], ej = edges[j]
      if (ei.from === ej.from || ei.to === ej.to || ei.from === ej.to || ei.to === ej.from) continue
      const p = bb[i]!, q = bb[j]!
      if (p[2] < q[0] || q[2] < p[0] || p[3] < q[1] || q[3] < p[1]) continue
      let hit = false
      for (let a = 0; a < A.length - 1 && !hit; a++) for (let b = 0; b < B.length - 1; b++) if (cut(A[a], A[a + 1], B[b], B[b + 1])) { hit = true; break }
      if (hit) n++
    }
  }
  return n
}

const hitsBox = (x: number, y: number, w: number, h: number, b: Box, pad = 2) => x - w / 2 < b.x + b.w + pad && b.x - pad < x + w / 2 && y - h / 2 < b.y + b.h + pad && b.y - pad < y + h / 2

/**
 * Where to put each connection's label so it sits on its own line, clear of every box and of the other labels.
 * Tries the middle of the route first, then points further along it. `labels[i]` is the text of connection i (or undefined).
 * Returns the centre for each labelled connection (the route's own default where nothing fits).
 */
export function placeLabels(routes: (Pt[] | null)[], labels: (string | undefined)[], boxes: Box[], measure = (t: string) => t.length * 6.6 + 10): (Pt | null)[] {
  const placed: { x: number; y: number; w: number; h: number }[] = []
  const out: (Pt | null)[] = routes.map(() => null)
  const along = (pts: Pt[], f: number): Pt => {
    const seg: number[] = []; let total = 0
    for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); total += l }
    let want = f * total
    for (let i = 0; i < seg.length; i++) { if (want <= seg[i]) { const w = seg[i] ? want / seg[i] : 0; return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * w, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * w] }; want -= seg[i] }
    return pts[pts.length - 1]
  }
  routes.forEach((pts, i) => {
    const text = labels[i]
    if (!pts || !text) return
    const w = measure(text), h = 18
    let fallback: Pt | null = null
    for (const f of [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82]) {
      const [x, y] = along(pts, f)
      fallback ??= [x, y]
      if (boxes.some((b) => hitsBox(x, y, w, h, b)) || placed.some((p) => Math.abs(p.x - x) < (p.w + w) / 2 && Math.abs(p.y - y) < (p.h + h) / 2)) continue
      placed.push({ x, y, w, h }); out[i] = [x, y]; return
    }
    if (fallback) { placed.push({ x: fallback[0], y: fallback[1], w, h }); out[i] = fallback }
  })
  return out
}

/** Labels that still overlap a box after placement (for tests). */
export function labelsOverBoxes(routes: (Pt[] | null)[], labels: (string | undefined)[], spots: (Pt | null)[], boxes: Box[], measure = (t: string) => t.length * 6.6 + 10): number {
  let n = 0
  spots.forEach((s, i) => { if (s && labels[i] && boxes.some((b) => hitsBox(s[0], s[1], measure(labels[i]!), 18, b, 0))) n++ })
  void routes
  return n
}

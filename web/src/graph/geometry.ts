import type { Box, Layout } from './layout'
import { MARGIN_X, ROW_GAP } from './layout'

export interface EdgeGeom {
  /** SVG path of the drawn connection */
  d: string
  /** the same route as a polyline, in canvas coordinates; dots in playback travel along it */
  pts: [number, number][]
  label: [number, number]
}

function rounded(pts: [number, number][], R = 9): string {
  let path = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1], [cx, cy] = pts[i], [nx, ny] = pts[i + 1]
    const l1 = Math.hypot(cx - px, cy - py), l2 = Math.hypot(nx - cx, ny - cy)
    const r = Math.min(R, l1 / 2, l2 / 2)
    const ax = cx - ((cx - px) / (l1 || 1)) * r, ay = cy - ((cy - py) / (l1 || 1)) * r
    const bx = cx + ((nx - cx) / (l2 || 1)) * r, by = cy + ((ny - cy) / (l2 || 1)) * r
    path += ` L ${ax} ${ay} Q ${cx} ${cy} ${bx} ${by}`
  }
  return path + ` L ${pts[pts.length - 1][0]} ${pts[pts.length - 1][1]}`
}

/**
 * Route of one connection. Within a row: a smooth curve from the right of the source to the left of the target.
 * Across a row break: out of the source, down to the channel between rows, back along it (by the left margin when it
 * skips a row) and down into the top of the target. `lane` (0..4) shifts parallel routes apart.
 */
export function edgeGeometry(a: Box, b: Box, layout: Pick<Layout, 'rowTop' | 'rowBottom'>, lane: number): EdgeGeom {
  if (b.row <= a.row) {
    const sx = a.x + a.w, sy = a.y + a.h / 2, tx = b.x, ty = b.y + b.h / 2
    const dx = Math.max(40, (tx - sx) * 0.5)
    const c1: [number, number] = [sx + dx, sy], c2: [number, number] = [tx - dx, ty]
    const pts: [number, number][] = []
    for (let i = 0; i <= 20; i++) {
      const t = i / 20, u = 1 - t
      pts.push([u ** 3 * sx + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * tx, u ** 3 * sy + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * ty])
    }
    return { d: `M ${sx} ${sy} C ${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${tx} ${ty}`, pts, label: pts[15] }
  }
  const l = lane * 5
  const sx = a.x + a.w, sy = a.y + a.h / 2, tx = b.x + b.w / 2, ty = b.y
  const below = layout.rowBottom[a.row] + ROW_GAP / 2 + l, above = layout.rowTop[b.row] - ROW_GAP / 2 + l
  const pts: [number, number][] = [[sx, sy], [sx + 14 + l, sy], [sx + 14 + l, below]]
  if (b.row === a.row + 1) pts.push([tx, below])
  else pts.push([MARGIN_X - l, below], [MARGIN_X - l, above], [tx, above])
  pts.push([tx, ty])
  return { d: rounded(pts), pts, label: [tx, ty - 18] }
}

/** Point at fraction f (0..1) of the polyline's length. */
export function pointAlong(pts: [number, number][], f: number): [number, number] {
  if (f <= 0) return pts[0]
  let total = 0
  const seg: number[] = []
  for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); total += l }
  if (f >= 1 || total === 0) return pts[pts.length - 1]
  let want = f * total
  for (let i = 0; i < seg.length; i++) {
    if (want <= seg[i]) { const w = seg[i] ? want / seg[i] : 0; return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * w, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * w] }
    want -= seg[i]
  }
  return pts[pts.length - 1]
}

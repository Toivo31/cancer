import { useEffect, useMemo, useRef } from 'react'
import { useStore } from '@xyflow/react'
import type { Box } from './layout'
import type { Clock } from './clock'
import { pointAlong } from './geometry'
import { adjacency, bfsPath, jitter, stateAt } from './playback'
import type { PPatient } from './playback'

export interface PlaybackProps {
  clock: Clock
  patients: PPatient[]
  boxes: Record<string, Box>
  /** polyline of each connection, keyed "from>to" */
  routes: Record<string, [number, number][]>
  edges: { from: string; to: string }[]
  transit: number
  selectedPatient: number | null
  onPick: (idx: number | null) => void
}

const COL = { wait: '#FFC04D', served: '#62B0FF', ontime: '#55E3B0', late: '#8A97A5', missed: '#FF5D73', left: '#4b5d6e' }

/** Dots for the sampled patients, drawn on a canvas over the graph using the graph's own viewport. */
export function PlaybackLayer(props: PlaybackProps) {
  const { clock, patients, boxes, routes, edges, transit, selectedPatient, onPick } = props
  const ref = useRef<HTMLCanvasElement>(null)
  const transform = useStore((s) => s.transform)
  const width = useStore((s) => s.width)
  const height = useStore((s) => s.height)
  const hits = useRef<{ x: number; y: number; idx: number }[]>([])
  const live = useRef({ transform, width, height, selectedPatient })
  live.current = { transform, width, height, selectedPatient }

  const adj = useMemo(() => adjacency(edges), [edges])
  const routeCache = useRef(new Map<string, [number, number][]>())
  useEffect(() => { routeCache.current.clear() }, [routes, adj])

  const routeBetween = (a: string, b: string): [number, number][] | null => {
    const key = `${a}>${b}`
    const hit = routeCache.current.get(key)
    if (hit) return hit
    const path = bfsPath(adj, a, b)
    let pts: [number, number][] | null = null
    if (path) {
      pts = []
      for (let i = 0; i + 1 < path.length; i++) pts.push(...(routes[`${path[i]}>${path[i + 1]}`] ?? []))
    }
    if (!pts || pts.length < 2) {
      const A = boxes[a], B = boxes[b]
      pts = A && B ? [[A.x + A.w, A.y + A.h / 2], [B.x, B.y + B.h / 2]] : null
    }
    if (pts) routeCache.current.set(key, pts)
    return pts
  }

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const draw = () => {
      const { transform: [tx, ty, z], width: w, height: h, selectedPatient: sel } = live.current
      const dpr = window.devicePixelRatio || 1
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr) }
      const ctx = canvas.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const r = Math.max(2, Math.min(4.6, 3.1 * Math.sqrt(z)))
      const t = clock.t
      const hs: { x: number; y: number; idx: number }[] = []
      let selXY: [number, number] | null = null
      for (const pp of patients) {
        const st = stateAt(pp, t, transit)
        if (!st) continue
        const B = boxes[st.node]
        if (!B) continue
        let x: number, y: number
        const j1 = jitter(pp.idx, 1), j2 = jitter(pp.idx, 2)
        if (st.from) {
          const route = routeBetween(st.from, st.node)
          if (route) {
            // along the route, with a little sideways spread so a crowd reads as a stream
            const [px, py] = pointAlong(route, st.u)
            x = px
            y = py + (j2 - 0.5) * 6
          } else { x = B.x; y = B.y + B.h / 2 }
        } else if (st.kind === 0) { x = B.x + 8 + j1 * (B.w - 16); y = B.y + B.h + 3 + j2 * 11 }
        else if (st.kind === 1) { x = B.x + 8 + j1 * (B.w - 16); y = B.y - 3 - j2 * 9 }
        else { x = B.x + 10 + j1 * (B.w - 20); y = B.y + B.h + 3 + j2 * 17 }
        const sx = x * z + tx, sy = y * z + ty
        const color = st.from || st.kind === 1 ? COL.served : st.kind === 0 ? COL.wait : pp.treated ? (pp.late ? COL.late : COL.ontime) : pp.missed ? COL.missed : COL.left
        ctx.fillStyle = color
        ctx.globalAlpha = pp.idx === sel ? 1 : 0.88
        ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill()
        hs.push({ x: sx, y: sy, idx: pp.idx })
        if (pp.idx === sel) selXY = [sx, sy]
      }
      if (selXY) {
        ctx.globalAlpha = 1; ctx.strokeStyle = '#EAF1F8'; ctx.lineWidth = 2
        ctx.beginPath(); ctx.arc(selXY[0], selXY[1], r + 4, 0, Math.PI * 2); ctx.stroke()
      }
      ctx.globalAlpha = 1
      hits.current = hs
    }
    draw()
    const off = clock.subscribe(draw)
    return off
  }, [clock, patients, boxes, routes, adj, transit]) // eslint-disable-line react-hooks/exhaustive-deps

  // redraw when the viewport or selection changes while paused
  useEffect(() => { clock.seek(clock.t) }, [transform, width, height, selectedPatient, clock])

  // a click on a dot picks that patient; anything else goes through to the graph
  useEffect(() => {
    const el = ref.current?.parentElement
    if (!el) return
    const handler = (e: MouseEvent) => {
      const rect = ref.current!.getBoundingClientRect()
      const x = e.clientX - rect.left, y = e.clientY - rect.top
      let best: { idx: number; d: number } | null = null
      for (const h of hits.current) { const d = Math.hypot(h.x - x, h.y - y); if (d <= 8 && (!best || d < best.d)) best = { idx: h.idx, d } }
      if (best) { e.stopPropagation(); onPick(best.idx) }
    }
    el.addEventListener('click', handler, true)
    return () => el.removeEventListener('click', handler, true)
  }, [onPick])

  return <canvas ref={ref} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 6 }} data-testid="playback-canvas" />
}

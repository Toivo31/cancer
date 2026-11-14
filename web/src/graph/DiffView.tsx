import { useEffect, useMemo, useRef, useState } from 'react'
import type { Flowchart } from '../api/types'
import { diffFlowcharts, edgeKey, unionGraph } from '../lib/graphDiff'
import type { Change } from '../lib/graphDiff'
import { edgeGeometry } from './geometry'
import { layoutFlowchart } from './layout'

const COLOR: Record<Change, string> = { same: '#2C3F52', added: '#55E3B0', removed: '#FF9A7A', changed: '#FFC04D' }
const WORD: Record<Change, string> = { same: '', added: 'new', removed: 'removed', changed: 'changed' }

/** Break a label into lines of at most `chars` characters (words are kept whole; a longer word is cut). */
export function wrapText(label: string, chars: number, maxLines = 4): string[] {
  const out: string[] = []
  let cur = ''
  for (let word of label.split(/\s+/).filter(Boolean)) {
    while (word.length > chars) { if (cur) { out.push(cur); cur = '' } out.push(word.slice(0, chars)); word = word.slice(chars) }
    if (!cur) cur = word
    else if (cur.length + 1 + word.length <= chars) cur += ` ${word}`
    else { out.push(cur); cur = word }
  }
  if (cur) out.push(cur)
  if (out.length > maxLines) { const k = out.slice(0, maxLines); k[maxLines - 1] = `${k[maxLines - 1].slice(0, Math.max(1, chars - 1))}…`; return k }
  return out.length ? out : ['']
}

interface Props { a: Flowchart; b: Flowchart; labelA: string; labelB: string }

/**
 * Two versions of a flowchart drawn next to each other. One layout is computed over the steps and connections of
 * both, so a step that is in both sits at exactly the same place in each drawing. Added steps and connections are
 * green on the right (and a faint outline on the left), removed ones are coral on the left (and a faint outline on
 * the right), changed ones amber. Everything unchanged is dimmed so the differences stand out.
 */
export function DiffView({ a, b, labelA, labelB }: Props) {
  const diff = useMemo(() => diffFlowcharts(a, b), [a, b])
  const layout = useMemo(() => { const u = unionGraph(a, b); return { u, l: layoutFlowchart(u.nodes, u.edges, { w: 760, h: 640 }) } }, [a, b])
  const { u, l } = layout
  const pad = 30
  const W = l.width + pad * 2 + 60, H = l.height + pad * 2
  const [zoom, setZoom] = useState(1)
  const [paneW, setPaneW] = useState(560)
  useEffect(() => {
    const m = () => { const w = refs[0].current?.clientWidth; if (w) setPaneW(w) }
    m(); window.addEventListener('resize', m)
    return () => window.removeEventListener('resize', m)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // 100% = the whole drawing fits the pane's width
  const scale = (Math.max(200, paneW - 4) / W) * zoom
  const refs = [useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null)]
  const syncing = useRef(false)
  const sync = (from: number) => {
    if (syncing.current) return
    const s = refs[from].current, t = refs[1 - from].current
    if (!s || !t) return
    syncing.current = true
    t.scrollLeft = s.scrollLeft; t.scrollTop = s.scrollTop
    requestAnimationFrame(() => { syncing.current = false })
  }
  const geoms = useMemo(() => u.edges.map((e, i) => {
    const x = l.boxes[e.from], y = l.boxes[e.to]
    return x && y ? edgeGeometry(x, y, l, i % 5) : null
  }), [u, l])

  const pane = (side: 0 | 1) => {
    const fc = side === 0 ? a : b
    const present = new Set(fc.nodes.map((n) => n.id))
    const presentEdge = new Set(fc.edges.map((e) => edgeKey(e.from, e.to)))
    return (
      <div className="diff-pane" key={side}>
        <div className="diff-title"><strong>{side === 0 ? labelA : labelB}</strong><span className="dim"> · {fc.nodes.length} steps · {fc.edges.length} connections</span></div>
        <div className="diff-scroll" ref={refs[side]} onScroll={() => sync(side)} tabIndex={0} aria-label={`${side === 0 ? labelA : labelB} drawing; scrolls together with the other one`} data-testid={`diff-pane-${side}`}>
          <svg width={W * scale} height={H * scale} viewBox={`${-pad - 40} ${-pad} ${W} ${H}`} role="img" aria-label={`Flowchart ${side === 0 ? labelA : labelB}`}>
            <defs>
              {(Object.keys(COLOR) as Change[]).map((c) => <marker key={c} id={`ar-${side}-${c}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={c === 'same' ? '#4a6177' : COLOR[c]} /></marker>)}
            </defs>
            {u.edges.map((e, i) => {
              const g = geoms[i]; if (!g) return null
              const k = edgeKey(e.from, e.to)
              const d = diff.edges[k]
              const here = presentEdge.has(k)
              const ch = d?.change ?? 'same'
              const stroke = !here ? '#2C3F52' : ch === 'same' ? '#4a6177' : COLOR[ch]
              return <path key={k} d={g.d} fill="none" stroke={stroke} strokeWidth={here && ch !== 'same' ? 3 : 1.4} strokeDasharray={here ? (e.type === 'optional' ? '2 4' : e.type === 'any' ? '7 4' : undefined) : '3 5'}
                opacity={here ? (ch === 'same' ? 0.7 : 1) : 0.28} markerEnd={here ? `url(#ar-${side}-${ch})` : undefined} data-testid={here && ch !== 'same' ? `diff-edge-${ch}` : undefined} />
            })}
            {u.nodes.map((n) => {
              const bx = l.boxes[n.id]; if (!bx) return null
              const d = diff.nodes[n.id]
              const here = present.has(n.id)
              const ch = d?.change ?? 'same'
              const col = !here ? '#2C3F52' : COLOR[ch]
              const lines = wrapText(n.label, Math.max(8, Math.floor((bx.w - 16) / 6.6)))
              const lh = 14
              const y0 = bx.y + bx.h / 2 - ((lines.length - 1) * lh) / 2 + 4
              return (
                <g key={n.id} opacity={here ? (ch === 'same' ? 0.85 : 1) : 0.3} data-testid={here && ch !== 'same' ? `diff-node-${ch}` : undefined}>
                  <title>{`${n.label}${here && d?.what.length ? `\n${d.what.join('\n')}` : ''}${!here ? `\n(${side === 0 ? 'not in this version' : 'removed in this version'})` : ''}`}</title>
                  <rect x={bx.x} y={bx.y} width={bx.w} height={bx.h} rx={n.kind === 'decision' ? 22 : 8} fill={here && ch !== 'same' ? `${COLOR[ch]}22` : '#111A24'} stroke={col} strokeWidth={here && ch !== 'same' ? 2.5 : 1.2} strokeDasharray={here && n.kind !== 'join' ? undefined : '4 4'} />
                  {lines.map((t, i) => <text key={i} x={bx.x + bx.w / 2} y={y0 + i * lh} textAnchor="middle" fontSize={12} fill="#EAF1F8">{t}</text>)}
                  {here && ch !== 'same' && <text x={bx.x + bx.w - 6} y={bx.y - 5} textAnchor="end" fontSize={10.5} fill={COLOR[ch]} fontFamily="var(--mono)">{WORD[ch]}</text>}
                </g>
              )
            })}
          </svg>
        </div>
      </div>
    )
  }

  return (
    <div data-testid="diff-view">
      <div className="form-row" style={{ marginBottom: 8, gap: 10 }}>
        <span className="diff-key"><i style={{ background: COLOR.added }} />new</span>
        <span className="diff-key"><i style={{ background: COLOR.removed }} />removed</span>
        <span className="diff-key"><i style={{ background: COLOR.changed }} />changed</span>
        <span className="dim" style={{ fontSize: 12 }}>The same step sits at the same place on both sides. Faint outlines show where a step is in the other version only.</span>
        <span className="spacer" />
        <button className="btn small" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))} aria-label="Zoom out">−</button>
        <span className="num dim" style={{ fontSize: 12, minWidth: 36, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
        <button className="btn small" onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))} aria-label="Zoom in">+</button>
        <button className="btn small" onClick={() => setZoom(1)}>Fit</button>
      </div>
      <div className="diff-panes">{pane(0)}{pane(1)}</div>
      <DiffList diff={diff} />
    </div>
  )
}

export function DiffList({ diff }: { diff: ReturnType<typeof diffFlowcharts> }) {
  const c = diff.counts
  return (
    <div style={{ marginTop: 10 }} data-testid="diff-list">
      <div className="label" style={{ marginBottom: 4 }}>
        {diff.identical ? 'No differences' : `${c.added} step${c.added === 1 ? '' : 's'} added · ${c.removed} removed · ${c.changed} changed · ${c.edgesAdded} connection${c.edgesAdded === 1 ? '' : 's'} added · ${c.edgesRemoved} removed${c.edgesChanged ? ` · ${c.edgesChanged} retyped` : ''}`}
      </div>
      {diff.identical
        ? <div className="muted" style={{ fontSize: 12.5 }}>The two versions have the same steps, connections and settings.</div>
        : <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, maxHeight: 150, overflow: 'auto' }}>{diff.lines.map((t, i) => <li key={i}>{t}</li>)}</ul>}
    </div>
  )
}

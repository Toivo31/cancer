import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BaseEdge, Background, Controls, Handle, MarkerType, MiniMap, NodeResizer, Position, ReactFlow } from '@xyflow/react'
import type { Edge, EdgeProps, Node, NodeChange, NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Flowchart, FlowNode, World } from '../api/types'
import { defaultShares } from '../lib/policy'
import { edgeGeometry } from './geometry'
import type { EdgeGeom } from './geometry'
import { layoutFlowchart, nodeSize, structureKey } from './layout'
import { placeLabels } from './layoutScore'
import { applyView, emptyView, isEmptyView, loadView, saveView } from './viewLayout'
import type { ViewLayout } from './viewLayout'
import type { NodeOverlay, Overlay } from './layers'
type NodeOverlayEdge = NonNullable<Overlay['edges'][string]>
import { pairKey } from './layers'
import { PlaybackLayer } from './PlaybackLayer'
import type { PlaybackProps } from './PlaybackLayer'

export const STAGE_LABEL: Record<string, string> = {
  detection: 'Detection', referral: 'Referral', diagnosis: 'Diagnosis', treatment_start: 'Treatment start',
}

export function stageOf(n: FlowNode, world?: World | null): string | undefined {
  return (n.stage as string | undefined) ?? (n.test ? (world?.tests?.[n.test]?.stage as string | undefined) : undefined)
}

interface PData extends Record<string, unknown> {
  node: FlowNode
  stage?: string
  selected: boolean
  onPath: boolean
  overlay?: NodeOverlay
  probLine?: string
  tip: string
}

const PNode = memo(function PNode({ data }: NodeProps<Node<PData>>) {
  const { node, stage, selected, onPath, overlay, probLine, tip } = data
  const cls = ['pnode', node.kind, node.kind === 'exit' ? (node.outcome === 'treatment' ? 'treatment' : 'discharged') : '', selected ? 'sel' : '', onPath ? 'onpath' : ''].join(' ')
  const eyebrow = node.kind === 'decision' ? 'Decision' : node.kind === 'exit' ? (node.outcome === 'treatment' ? 'Treatment starts' : '') : node.kind === 'milestone' ? 'Diagnosis reached' : node.kind === 'join' ? '' : stage ? (STAGE_LABEL[stage] ?? stage) : ''
  const sub = overlay?.sub ?? probLine
  return (
    <>
    <NodeResizer isVisible={selected} minWidth={100} minHeight={34} lineStyle={{ borderColor: '#62B0FF' }} handleStyle={{ width: 10, height: 10, background: '#62B0FF', border: 'none' }} />
    <div className={cls} style={{ background: overlay?.fill, borderColor: overlay?.border, borderWidth: overlay?.borderWidth }} title={tip}>
      <Handle id="l" type="target" position={Position.Left} />
      <Handle id="t" type="target" position={Position.Top} />
      {eyebrow && <div className="stage">{eyebrow}</div>}
      <div className="title">{node.label}</div>
      {sub && <div className="num sub" style={{ color: overlay?.subColor }}>{sub}</div>}
      {overlay?.spark && (
        <svg className="spark" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden>
          <polyline fill="none" stroke="#62B0FF" strokeWidth="1.2" vectorEffect="non-scaling-stroke" points={overlay.spark.map((v, i) => `${(i / Math.max(1, overlay.spark!.length - 1)) * 100},${10 - v * 10}`).join(' ')} />
        </svg>
      )}
      <Handle id="r" type="source" position={Position.Right} />
      <Handle id="b" type="source" position={Position.Bottom} />
    </div>
    </>
  )
})
const nodeTypes = { p: PNode }

interface EData extends Record<string, unknown> { geom: EdgeGeom }
function PEdge({ markerEnd, style, label, labelStyle, labelBgStyle, labelBgPadding, labelBgBorderRadius, data }: EdgeProps) {
  const g = (data as EData).geom
  return <BaseEdge path={g.d} markerEnd={markerEnd} style={style} label={label} labelX={g.label[0]} labelY={g.label[1]} labelStyle={labelStyle} labelBgStyle={labelBgStyle} labelBgPadding={labelBgPadding} labelBgBorderRadius={labelBgBorderRadius} labelShowBg />
}
const edgeTypes = { pf: PEdge }

const EDGE_STYLE: Record<string, { stroke: string; dash?: string; w: number }> = {
  required: { stroke: '#4a6177', w: 1.5 },
  any: { stroke: '#5d7a93', dash: '7 4', w: 1.5 },
  optional: { stroke: '#3a5063', dash: '2 4', w: 1.5 },
  option: { stroke: '#B79CFF', w: 1.7 },
}

export interface CanvasPlayback extends Omit<PlaybackProps, 'boxes' | 'routes' | 'edges'> {}

interface Props {
  flowchart: Flowchart
  world?: World | null
  selected?: string | null
  onSelect?: (id: string | null) => void
  overlay?: Overlay | null
  /** steps and connections to emphasise (a patient's critical path) */
  path?: { nodes: Set<string>; edges: Set<string> } | null
  playback?: CanvasPlayback | null
  showLegend?: boolean
  /** where the view-only layout (dragged positions, resized boxes) is kept in the browser, one entry per flowchart */
  layoutKey?: string
  /** change to redo the fit to the available space (for example after a panel opens or closes) */
  refit?: string | number
}

export function FlowCanvas({ flowchart, world, selected, onSelect, overlay, path, playback, showLegend = true, refit, layoutKey }: Props) {
  const key = structureKey(flowchart)
  // the layout depends on how tall each box is, not on every letter typed into a label
  const labelKey = flowchart.nodes.map((n) => nodeSize(n).h).join('|')
  const layout = useMemo(() => layoutFlowchart(flowchart.nodes, flowchart.edges), [key, labelKey]) // eslint-disable-line react-hooks/exhaustive-deps
  const lkey = layoutKey ?? flowchart.id
  const [view, setView] = useState<ViewLayout>(() => loadView(lkey))
  const [resetTick, setResetTick] = useState(0)
  const loadedKey = useRef(lkey)
  useEffect(() => { if (loadedKey.current !== lkey) { loadedKey.current = lkey; setView(loadView(lkey)) } }, [lkey])
  useEffect(() => { if (loadedKey.current === lkey) saveView(lkey, view) }, [lkey, view])
  const { boxes, moved } = useMemo(() => applyView(layout.boxes, view), [layout, view])
  const geoms = useMemo(() => flowchart.edges.map((e, i) => {
    const a = boxes[e.from], b = boxes[e.to]
    if (!a || !b) return null
    // a connection to a step the user moved is drawn directly; the others keep the row-wrapped routes
    return moved.has(e.from) || moved.has(e.to) ? edgeGeometry({ ...a, row: 0 }, { ...b, row: 0 }, layout, 0) : edgeGeometry(a, b, layout, layout.lanes?.[i] ?? 0)
  }), [key, layout, boxes, moved]) // eslint-disable-line react-hooks/exhaustive-deps
  const routes = useMemo(() => {
    const r: Record<string, [number, number][]> = {}
    flowchart.edges.forEach((e, i) => { const g = geoms[i]; if (g && !r[pairKey(e.from, e.to)]) r[pairKey(e.from, e.to)] = g.pts })
    return r
  }, [key, geoms]) // eslint-disable-line react-hooks/exhaustive-deps
  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setView((v) => {
      let next = v
      for (const c of changes) {
        if (c.type === 'position' && c.position) next = { ...next, pos: { ...next.pos, [c.id]: { x: c.position.x, y: c.position.y } } }
        else if (c.type === 'dimensions' && c.setAttributes && c.dimensions) next = { ...next, size: { ...next.size, [c.id]: { w: Math.round(c.dimensions.width), h: Math.round(c.dimensions.height) } } }
      }
      return next
    })
  }, [])
  const [hover, setHover] = useState<string | null>(null)
  const focus = hover ?? selected ?? null

  const labelText = (e: Flowchart['edges'][number], ov: NodeOverlayEdge | undefined): string | undefined => {
    if (ov?.label !== undefined) return ov.label
    if (e.type === 'option') { const p = defaultShares(flowchart.decision_policy.points[e.from])?.[e.to]; if (p !== undefined) return `${Math.round(p * 1000) / 10}%` }
    return undefined
  }
  const { nodes, edges } = useMemo(() => {
    const texts = flowchart.edges.map((e) => labelText(e, overlay?.edges[pairKey(e.from, e.to)]))
    const spots = placeLabels(geoms.map((g) => g?.pts ?? null), texts, Object.values(boxes))
    const incident = new Set<string>()
    flowchart.edges.forEach((e, i) => { if (focus && (e.from === focus || e.to === focus)) incident.add(`e${i}`) })
    const ns: Node<PData>[] = flowchart.nodes.map((n) => {
      const pt = flowchart.decision_policy.points[n.id]
      let probLine: string | undefined
      const shares = defaultShares(pt)
      if (n.kind === 'decision' && shares) probLine = `${Object.keys(shares).length} options${pt?.rules?.length ? ` · ${pt.rules.length} rule${pt.rules.length > 1 ? 's' : ''}` : ''}`
      else if (n.kind === 'decision') probLine = 'no probabilities set'
      return {
        id: n.id, type: 'p', position: { x: boxes[n.id].x, y: boxes[n.id].y }, width: boxes[n.id].w, height: boxes[n.id].h,
        data: { node: n, stage: stageOf(n, world), selected: selected === n.id, onPath: !!path?.nodes.has(n.id), overlay: overlay?.nodes[n.id], probLine, tip: [n.label, overlay?.nodes[n.id]?.sub ?? probLine].filter(Boolean).join('\n') },
        draggable: true, selectable: true,
      }
    })
    const es: Edge[] = flowchart.edges.map((e, i) => {
      const id = `e${i}`
      const st = EDGE_STYLE[e.type] ?? EDGE_STYLE.required
      const ov = overlay?.edges[pairKey(e.from, e.to)]
      const onPath = !!path?.edges.has(pairKey(e.from, e.to))
      const on = !focus || incident.has(id)
      const label = texts[i]
      const color = onPath ? '#EAF1F8' : ov?.color ?? (on && focus ? (e.type === 'option' ? '#B79CFF' : '#62B0FF') : st.stroke)
      const geom0 = geoms[i]
      const geom = geom0 && spots[i] ? { ...geom0, label: spots[i]! } : geom0
      const wrap = !!geom && boxes[e.to].row > boxes[e.from].row
      return {
        id, source: e.from, target: e.to, type: 'pf', label,
        sourceHandle: 'r', targetHandle: wrap ? 't' : 'l',
        data: { geom: geom ?? { d: '', pts: [], label: [0, 0] } } as EData,
        labelStyle: { fill: '#EAF1F8', fontFamily: 'var(--mono)', fontSize: 11 },
        labelBgStyle: { fill: '#0A0F14', fillOpacity: 0.9 }, labelBgPadding: [4, 2] as [number, number], labelBgBorderRadius: 4,
        style: {
          stroke: color, strokeWidth: onPath ? 3 : ov?.width ?? (on && focus ? st.w + 0.8 : st.w),
          strokeDasharray: ov ? (ov.dashed ? '3 4' : undefined) : st.dash,
          opacity: path && !onPath ? 0.25 : (ov?.opacity ?? 1) * (on ? 1 : 0.16),
        },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12, markerUnits: 'userSpaceOnUse' },
        zIndex: onPath || (on && focus) ? 10 : 0,
      }
    })
    return { nodes: ns, edges: es }
  }, [flowchart, world, boxes, geoms, selected, focus, overlay, path])

  return (
    <div style={{ position: 'absolute', inset: 0 }} data-testid="canvas" onKeyDown={(e) => {
      // a step reached with Tab is chosen with Enter or Space, like a click
      if (e.key !== 'Enter' && e.key !== ' ') return
      const el = (e.target as HTMLElement).closest?.('.react-flow__node') as HTMLElement | null
      if (el?.dataset.id) { e.preventDefault(); onSelect?.(el.dataset.id) }
    }}>
      <ReactFlow
        key={`${key}/${refit ?? ''}/${resetTick}`} nodes={nodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        fitView fitViewOptions={{ padding: { top: '84px', right: '24px', bottom: '64px', left: '24px' } }} minZoom={0.15} maxZoom={1.8}
        nodesDraggable nodesConnectable={false} elementsSelectable
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => onSelect?.(n.id)} onPaneClick={() => onSelect?.(null)}
        onNodeMouseEnter={(_, n) => setHover(n.id)} onNodeMouseLeave={() => setHover(null)}
      >
        <Background color="#17222d" gap={28} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => ((n.data as PData).node.kind === 'decision' ? '#B79CFF' : '#2C3F52')} maskColor="rgba(10,15,20,.7)" style={{ width: 150, height: 96 }} />
        {playback && <PlaybackLayer {...playback} boxes={boxes} routes={routes} edges={flowchart.edges} />}
      </ReactFlow>
      <button className="btn small resetbtn" disabled={isEmptyView(view)} onClick={() => { setView(emptyView()); setResetTick((t) => t + 1) }} title="Put every box back where the automatic layout placed it. Drag a box to move it and select a box to resize it; this changes only how the chart looks, not the flowchart.">Reset layout</button>
      {showLegend && !overlay && (
        <div className="legend">
          <span><i />required</span><span><i className="dash" />any of</span><span><i className="dot" />only if it ran</span><span><i className="opt" />decision option (% offered)</span>
        </div>
      )}
    </div>
  )
}

import { memo, useMemo, useState } from 'react'
import { BaseEdge, Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow } from '@xyflow/react'
import type { Edge, EdgeProps, Node, NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Flowchart, FlowNode, World } from '../api/types'
import { defaultShares } from '../lib/policy'
import { edgeGeometry } from './geometry'
import type { EdgeGeom } from './geometry'
import { layoutFlowchart, SIZE, structureKey } from './layout'
import type { NodeOverlay, Overlay } from './layers'
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
}

const PNode = memo(function PNode({ data }: NodeProps<Node<PData>>) {
  const { node, stage, selected, onPath, overlay, probLine } = data
  const cls = ['pnode', node.kind, node.kind === 'exit' ? (node.outcome === 'treatment' ? 'treatment' : 'discharged') : '', selected ? 'sel' : '', onPath ? 'onpath' : ''].join(' ')
  const eyebrow = node.kind === 'decision' ? 'Decision' : node.kind === 'exit' ? (node.outcome === 'treatment' ? 'Treatment starts' : '') : node.kind === 'milestone' ? 'Diagnosis reached' : node.kind === 'join' ? '' : stage ? (STAGE_LABEL[stage] ?? stage) : ''
  const sub = overlay?.sub ?? probLine
  return (
    <div className={cls} style={{ background: overlay?.fill, borderColor: overlay?.border, borderWidth: overlay?.borderWidth }} title={node.label}>
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
  /** change to redo the fit to the available space (for example after a panel opens or closes) */
  refit?: string | number
}

export function FlowCanvas({ flowchart, world, selected, onSelect, overlay, path, playback, showLegend = true, refit }: Props) {
  const key = structureKey(flowchart)
  const layout = useMemo(() => layoutFlowchart(flowchart.nodes, flowchart.edges), [key]) // eslint-disable-line react-hooks/exhaustive-deps
  const boxes = layout.boxes
  const geoms = useMemo(() => flowchart.edges.map((e, i) => (boxes[e.from] && boxes[e.to] ? edgeGeometry(boxes[e.from], boxes[e.to], layout, i % 5) : null)), [key, layout]) // eslint-disable-line react-hooks/exhaustive-deps
  const routes = useMemo(() => {
    const r: Record<string, [number, number][]> = {}
    flowchart.edges.forEach((e, i) => { const g = geoms[i]; if (g && !r[pairKey(e.from, e.to)]) r[pairKey(e.from, e.to)] = g.pts })
    return r
  }, [key, geoms]) // eslint-disable-line react-hooks/exhaustive-deps
  const [hover, setHover] = useState<string | null>(null)
  const focus = hover ?? selected ?? null

  const { nodes, edges } = useMemo(() => {
    const incident = new Set<string>()
    flowchart.edges.forEach((e, i) => { if (focus && (e.from === focus || e.to === focus)) incident.add(`e${i}`) })
    const ns: Node<PData>[] = flowchart.nodes.map((n) => {
      const pt = flowchart.decision_policy.points[n.id]
      let probLine: string | undefined
      const shares = defaultShares(pt)
      if (n.kind === 'decision' && shares) probLine = `${Object.keys(shares).length} options${pt?.rules?.length ? ` · ${pt.rules.length} rule${pt.rules.length > 1 ? 's' : ''}` : ''}`
      else if (n.kind === 'decision') probLine = 'no probabilities set'
      return {
        id: n.id, type: 'p', position: { x: boxes[n.id].x, y: boxes[n.id].y }, width: SIZE[n.kind].w, height: SIZE[n.kind].h,
        data: { node: n, stage: stageOf(n, world), selected: selected === n.id, onPath: !!path?.nodes.has(n.id), overlay: overlay?.nodes[n.id], probLine },
        draggable: false, selectable: true,
      }
    })
    const es: Edge[] = flowchart.edges.map((e, i) => {
      const id = `e${i}`
      const st = EDGE_STYLE[e.type] ?? EDGE_STYLE.required
      const ov = overlay?.edges[pairKey(e.from, e.to)]
      const onPath = !!path?.edges.has(pairKey(e.from, e.to))
      const on = !focus || incident.has(id)
      let label: string | undefined = ov?.label
      if (label === undefined && e.type === 'option') {
        const p = defaultShares(flowchart.decision_policy.points[e.from])?.[e.to]
        if (p !== undefined) label = `${Math.round(p * 1000) / 10}%`
      }
      const color = onPath ? '#EAF1F8' : ov?.color ?? (on && focus ? (e.type === 'option' ? '#B79CFF' : '#62B0FF') : st.stroke)
      const geom = geoms[i]
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
    <div style={{ position: 'absolute', inset: 0 }} data-testid="canvas">
      <ReactFlow
        key={`${key}/${refit ?? ''}`} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        fitView fitViewOptions={{ padding: { top: '84px', right: '24px', bottom: '24px', left: '24px' } }} minZoom={0.15} maxZoom={1.8}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => onSelect?.(n.id)} onPaneClick={() => onSelect?.(null)}
        onNodeMouseEnter={(_, n) => setHover(n.id)} onNodeMouseLeave={() => setHover(null)}
      >
        <Background color="#17222d" gap={28} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => ((n.data as PData).node.kind === 'decision' ? '#B79CFF' : '#2C3F52')} maskColor="rgba(10,15,20,.7)" style={{ width: 150, height: 96 }} />
        {playback && <PlaybackLayer {...playback} boxes={boxes} routes={routes} edges={flowchart.edges} />}
      </ReactFlow>
      {showLegend && !overlay && (
        <div className="legend">
          <span><i />required</span><span><i className="dash" />any of</span><span><i className="dot" />only if it ran</span><span><i className="opt" />decision option (% offered)</span>
        </div>
      )}
    </div>
  )
}

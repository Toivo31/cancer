import { memo, useMemo, useState } from 'react'
import { BaseEdge, Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow } from '@xyflow/react'
import type { Edge, EdgeProps, Node, NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Flowchart, FlowNode, World } from '../api/types'
import { layoutFlowchart, MARGIN_X, ROW_GAP, SIZE, structureKey } from './layout'

export const STAGE_LABEL: Record<string, string> = {
  detection: 'Detection', referral: 'Referral', diagnosis: 'Diagnosis', treatment_start: 'Treatment start',
}

export function stageOf(n: FlowNode, world?: World | null): string | undefined {
  return (n.stage as string | undefined) ?? (n.test ? (world?.tests?.[n.test]?.stage as string | undefined) : undefined)
}

/** Per-step and per-edge decoration that run layers add (kept generic so every layer uses the same canvas). */
export interface NodeOverlay { fill?: string; border?: string; badge?: string; sub?: string; subColor?: string }
export interface EdgeOverlay { width?: number; label?: string; color?: string }
export const edgeKey = (e: { from: string; to: string; type: string }) => `${e.from}>${e.to}:${e.type}`

interface PData extends Record<string, unknown> {
  node: FlowNode
  stage?: string
  selected: boolean
  muted: boolean
  overlay?: NodeOverlay
  probLine?: string
}

const PNode = memo(function PNode({ data }: NodeProps<Node<PData>>) {
  const { node, stage, selected, muted, overlay, probLine } = data
  const cls = ['pnode', node.kind, node.kind === 'exit' ? (node.outcome === 'treatment' ? 'treatment' : 'discharged') : '', selected ? 'sel' : '', muted ? 'dim-out' : ''].join(' ')
  const eyebrow = node.kind === 'decision' ? 'Decision' : node.kind === 'exit' ? (node.outcome === 'treatment' ? 'Treatment starts' : '') : node.kind === 'milestone' ? 'Diagnosis reached' : node.kind === 'join' ? '' : stage ? (STAGE_LABEL[stage] ?? stage) : ''
  return (
    <div className={cls} style={{ background: overlay?.fill, borderColor: overlay?.border }} title={node.label}>
      <Handle id="l" type="target" position={Position.Left} />
      <Handle id="t" type="target" position={Position.Top} />
      {eyebrow && <div className="stage">{eyebrow}</div>}
      <div className="title">{node.label}</div>
      {(overlay?.sub || probLine) && <div className="num" style={{ fontSize: 10.5, color: overlay?.subColor ?? 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{overlay?.sub ?? probLine}</div>}
      {overlay?.badge && <div className="num" style={{ position: 'absolute', right: 8, top: 5, fontSize: 11, color: 'var(--text)' }}>{overlay.badge}</div>}
      <Handle id="r" type="source" position={Position.Right} />
      <Handle id="b" type="source" position={Position.Bottom} />
    </div>
  )
})
const nodeTypes = { p: PNode }

interface WrapData extends Record<string, unknown> { below: number; above: number; lane: number; adjacent: boolean }

/** A connection that crosses a row break: out of the source, down to the channel between rows, back along it to the target's column, down into its top. */
function WrapEdge({ sourceX, sourceY, targetX, targetY, markerEnd, style, label, labelStyle, labelBgStyle, labelBgPadding, labelBgBorderRadius, data }: EdgeProps) {
  const d = data as WrapData
  const lane = d.lane * 5
  const pts: [number, number][] = [[sourceX, sourceY], [sourceX + 14 + lane, sourceY], [sourceX + 14 + lane, d.below + lane]]
  if (d.adjacent) pts.push([targetX, d.below + lane])
  else pts.push([MARGIN_X - lane, d.below + lane], [MARGIN_X - lane, d.above + lane], [targetX, d.above + lane])
  pts.push([targetX, targetY])
  const R = 9
  let path = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1], [cx, cy] = pts[i], [nx, ny] = pts[i + 1]
    const l1 = Math.hypot(cx - px, cy - py), l2 = Math.hypot(nx - cx, ny - cy)
    const r = Math.min(R, l1 / 2, l2 / 2)
    const ax = cx - ((cx - px) / (l1 || 1)) * r, ay = cy - ((cy - py) / (l1 || 1)) * r
    const bx = cx + ((nx - cx) / (l2 || 1)) * r, by = cy + ((ny - cy) / (l2 || 1)) * r
    path += ` L ${ax} ${ay} Q ${cx} ${cy} ${bx} ${by}`
  }
  path += ` L ${pts[pts.length - 1][0]} ${pts[pts.length - 1][1]}`
  return <BaseEdge path={path} markerEnd={markerEnd} style={style} label={label} labelX={targetX} labelY={targetY - 18} labelStyle={labelStyle} labelBgStyle={labelBgStyle} labelBgPadding={labelBgPadding} labelBgBorderRadius={labelBgBorderRadius} labelShowBg />
}
const edgeTypes = { wrap: WrapEdge }

const EDGE_STYLE: Record<string, { stroke: string; dash?: string; w: number }> = {
  required: { stroke: '#4a6177', w: 1.5 },
  any: { stroke: '#5d7a93', dash: '7 4', w: 1.5 },
  optional: { stroke: '#3a5063', dash: '2 4', w: 1.5 },
  option: { stroke: '#B79CFF', w: 1.7 },
}

interface Props {
  flowchart: Flowchart
  world?: World | null
  selected?: string | null
  onSelect?: (id: string | null) => void
  nodeOverlay?: Record<string, NodeOverlay>
  edgeOverlay?: Record<string, EdgeOverlay>
  showLegend?: boolean
}

export function FlowCanvas({ flowchart, world, selected, onSelect, nodeOverlay, edgeOverlay, showLegend = true }: Props) {
  const key = structureKey(flowchart)
  const layout = useMemo(() => layoutFlowchart(flowchart.nodes, flowchart.edges), [key])
  const boxes = layout.boxes // eslint-disable-line react-hooks/exhaustive-deps
  const [hover, setHover] = useState<string | null>(null)
  const focus = hover ?? selected ?? null

  const { nodes, edges } = useMemo(() => {
    const incident = new Set<string>()
    flowchart.edges.forEach((e, i) => { if (focus && (e.from === focus || e.to === focus)) incident.add(`e${i}`) })
    const ns: Node<PData>[] = flowchart.nodes.map((n) => {
      const pt = flowchart.decision_policy.points[n.id]
      let probLine: string | undefined
      if (n.kind === 'decision' && pt?.default) probLine = `${Object.keys(pt.default).length} options${pt.rules?.length ? ` · ${pt.rules.length} rule${pt.rules.length > 1 ? 's' : ''}` : ''}`
      else if (n.kind === 'decision') probLine = 'no probabilities set'
      return {
        id: n.id, type: 'p', position: { x: boxes[n.id].x, y: boxes[n.id].y }, width: SIZE[n.kind].w, height: SIZE[n.kind].h,
        data: { node: n, stage: stageOf(n, world), selected: selected === n.id, muted: false, overlay: nodeOverlay?.[n.id], probLine },
        draggable: false, selectable: true,
      }
    })
    const es: Edge[] = flowchart.edges.map((e, i) => {
      const id = `e${i}`
      const st = EDGE_STYLE[e.type] ?? EDGE_STYLE.required
      const ov = edgeOverlay?.[edgeKey(e)]
      const on = !focus || incident.has(id)
      let label: string | undefined = ov?.label
      if (label === undefined && e.type === 'option') {
        const p = flowchart.decision_policy.points[e.from]?.default?.[e.to]
        if (p !== undefined) label = `${Math.round(p * 1000) / 10}%`
      }
      const color = ov?.color ?? (on && focus ? (e.type === 'option' ? '#B79CFF' : '#62B0FF') : st.stroke)
      const wrap = boxes[e.from] && boxes[e.to] && boxes[e.to].row > boxes[e.from].row
      return {
        id, source: e.from, target: e.to, type: wrap ? 'wrap' : 'default', label,
        sourceHandle: 'r', targetHandle: wrap ? 't' : 'l',
        data: wrap ? ({ below: layout.rowBottom[boxes[e.from].row] + ROW_GAP / 2, above: layout.rowTop[boxes[e.to].row] - ROW_GAP / 2, lane: i % 5, adjacent: boxes[e.to].row === boxes[e.from].row + 1 } as WrapData) : undefined,
        labelStyle: { fill: '#EAF1F8', fontFamily: 'var(--mono)', fontSize: 11 },
        labelBgStyle: { fill: '#0A0F14', fillOpacity: 0.9 }, labelBgPadding: [4, 2] as [number, number], labelBgBorderRadius: 4,
        style: { stroke: color, strokeWidth: ov?.width ?? (on && focus ? st.w + 0.8 : st.w), strokeDasharray: st.dash, opacity: on ? 1 : 0.16 },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        zIndex: on && focus ? 10 : 0,
      }
    })
    return { nodes: ns, edges: es }
  }, [flowchart, world, boxes, layout, selected, focus, nodeOverlay, edgeOverlay])

  return (
    <div style={{ position: 'absolute', inset: 0 }} data-testid="canvas">
      <ReactFlow
        key={key} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        fitView fitViewOptions={{ padding: 0.12 }} minZoom={0.15} maxZoom={1.8}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => onSelect?.(n.id)} onPaneClick={() => onSelect?.(null)}
        onNodeMouseEnter={(_, n) => setHover(n.id)} onNodeMouseLeave={() => setHover(null)}
      >
        <Background color="#17222d" gap={28} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => ((n.data as PData).node.kind === 'decision' ? '#B79CFF' : '#2C3F52')} maskColor="rgba(10,15,20,.7)" style={{ width: 150, height: 96 }} />
      </ReactFlow>
      {showLegend && (
        <div className="legend">
          <span><i />required</span><span><i className="dash" />any of</span><span><i className="dot" />only if it ran</span><span><i className="opt" />decision option (% offered)</span>
        </div>
      )}
    </div>
  )
}

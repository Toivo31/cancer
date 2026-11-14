import { describe, expect, it } from 'vitest'
import type { Flowchart, FlowData } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import flowNorway from '../../../docs/platform/fixtures/flow_norway.json'
import { buildOverlay, pairKey } from './layers'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'norway_check')!.flowcharts.find((f) => f.id === 'observed')!
const flow = flowNorway as unknown as FlowData

describe('run layers on the Norway graph', () => {
  it('every step of the flow document is a step of the flowchart', () => {
    const ids = new Set(fc.nodes.map((n) => n.id))
    for (const n of flow.graph.nodes) expect(ids.has(n.id)).toBe(true)
  })
  it('flow layer: edge counts equal the flow document', () => {
    const o = buildOverlay(fc, flow, 'flow', (id) => id)
    for (const e of flow.graph.edges) {
      const ov = o.edges[pairKey(e.source, e.target)]
      expect(ov).toBeDefined()
      expect(ov.dashed).toBe(e.n === 0)
    }
    const treat = flow.exits['treat']
    expect(o.nodes['treat'].sub).toContain(treat.n.toLocaleString('en'))
  })
  it('time layer: the slowest steps are the darkest', () => {
    const o = buildOverlay(fc, flow, 'time', (id) => id)
    const slow = Object.entries(flow.steps).filter(([, s]) => s.wait_median != null).sort((a, b) => b[1].wait_median! - a[1].wait_median!)[0][0]
    expect(o.nodes[slow].fill).toMatch(/rgba\(255,192,77,0\.5/)
  })
  it('decisions layer: shows chosen shares', () => {
    const o = buildOverlay(fc, flow, 'decisions', (id) => id)
    const [id, d] = Object.entries(flow.decisions)[0]
    const opt = Object.keys(d.share)[0]
    expect(o.edges[pairKey(id, opt)].label).toContain(`${Math.round(d.share[opt] * 100)}%`)
  })
})

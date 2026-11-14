import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { layoutFlowchart, overlaps } from './layout'

const all = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).flatMap((t) => t.flowcharts.map((f) => [`${t.id}/${f.id}`, f] as const))

describe('auto layout', () => {
  it.each(all)('%s draws without overlapping steps', (_n, fc) => {
    const { boxes } = layoutFlowchart(fc.nodes, fc.edges)
    expect(Object.keys(boxes).length).toBe(fc.nodes.length)
    expect(overlaps(boxes)).toEqual([])
  })
  it('reads like text: a step is right of what it waits for, or on a later row', () => {
    const fc = all.find(([n]) => n === 'finland_scenario/baseline')![1]
    const { boxes } = layoutFlowchart(fc.nodes, fc.edges)
    for (const e of fc.edges) {
      const a = boxes[e.from], b = boxes[e.to]
      expect(b.row > a.row || (b.row === a.row && b.x > a.x)).toBe(true)
    }
  })
  it.each(all)('%s fits a laptop canvas at a readable scale', (_n, fc) => {
    const l = layoutFlowchart(fc.nodes, fc.edges)
    const scale = Math.min(1240 / (l.width + 60), 700 / (l.height + 60))
    expect(scale).toBeGreaterThan(0.5)
  })
})

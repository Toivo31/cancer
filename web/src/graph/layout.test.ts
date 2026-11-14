import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { LAPTOP_CANVAS, layoutFlowchart, nodeSize, overlaps, wrapLines } from './layout'
import { assignLanes, countCrossings, labelsOverBoxes, placeLabels, routesOf } from './layoutScore'

const all = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).flatMap((t) => t.flowcharts.map((f) => [`${t.id}/${f.id}`, f] as const))

describe('auto layout', () => {
  it.each(all)('%s draws without overlapping steps', (_n, fc) => {
    const { boxes } = layoutFlowchart(fc.nodes, fc.edges)
    expect(Object.keys(boxes).length).toBe(fc.nodes.length)
    expect(overlaps(boxes)).toEqual([])
  })
  it('reads like text: a step is right of what it waits for, or on a later row', () => {
    const fc = all.find(([n]) => n === 'finland_lung/baseline')![1]
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
    // and on the narrower canvas left by an open side panel
    expect(Math.min(LAPTOP_CANVAS.w / (l.width + 60), LAPTOP_CANVAS.h / (l.height + 60))).toBeGreaterThan(0.45)
  })
  it.each(all)('%s has few crossing connections', (_n, fc) => {
    expect(countCrossings(layoutFlowchart(fc.nodes, fc.edges), fc.edges)).toBeLessThanOrEqual(16)
  })
  it.each(all)('%s gives every option percentage a place clear of the boxes', (_n, fc) => {
    const l = layoutFlowchart(fc.nodes, fc.edges)
    const routes = routesOf(l, fc.edges)
    const labels = fc.edges.map((e) => (e.type === 'option' ? '55.5%' : undefined))
    const spots = placeLabels(routes, labels, Object.values(l.boxes))
    expect(spots.filter((s, i) => labels[i] && !s)).toEqual([])
    expect(labelsOverBoxes(routes, labels, spots, Object.values(l.boxes))).toBeLessThanOrEqual(Math.ceil(labels.filter(Boolean).length * 0.1))
  })
  it('lanes keep parallel row-crossing connections apart', () => {
    const fc = all.find(([n]) => n === 'norway_check/observed')![1]
    const l = layoutFlowchart(fc.nodes, fc.edges)
    const lanes = assignLanes(l, fc.edges)
    const wrapped = fc.edges.map((e, i) => [e, i] as const).filter(([e]) => l.boxes[e.to].row > l.boxes[e.from].row)
    expect(wrapped.length).toBeGreaterThan(0)
    expect(Math.max(...lanes)).toBeLessThanOrEqual(9)
  })
})

describe('node sizes', () => {
  it('grow with the label so no text is cut off', () => {
    expect(nodeSize({ kind: 'step', label: 'Chest X-ray' }).h).toBeLessThan(nodeSize({ kind: 'step', label: 'GP appointment after a nurse assessment with a very long wording' }).h)
    expect(wrapLines('GP review of a negative film', 24)).toBe(2)
    expect(wrapLines('', 24)).toBe(1)
  })
})

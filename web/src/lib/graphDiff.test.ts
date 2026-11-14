import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { diffFlowcharts, unionGraph } from './graphDiff'

const base = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]
const clone = (f: Flowchart): Flowchart => JSON.parse(JSON.stringify(f))

describe('diffFlowcharts', () => {
  it('finds nothing between a version and itself', () => {
    const d = diffFlowcharts(base, clone(base))
    expect(d.identical).toBe(true)
    expect(d.lines).toEqual([])
  })
  it('reports added and removed steps and connections and changed labels in words', () => {
    const b = clone(base)
    const gone = b.nodes.pop()!
    b.edges = b.edges.filter((e) => e.from !== gone.id && e.to !== gone.id)
    b.nodes[0].label = 'Renamed first step'
    b.nodes.push({ id: 'new_step', kind: 'step', label: 'New step' })
    b.edges.push({ from: b.nodes[0].id, to: 'new_step', type: 'required' })
    const d = diffFlowcharts(base, b)
    expect(d.nodes[gone.id].change).toBe('removed')
    expect(d.nodes.new_step.change).toBe('added')
    expect(d.nodes[b.nodes[0].id].change).toBe('changed')
    expect(d.counts.edgesAdded).toBe(1)
    expect(d.counts.edgesRemoved).toBeGreaterThan(0)
    expect(d.lines.some((l) => l.startsWith('New step: New step'))).toBe(true)
    expect(d.lines.some((l) => l.includes('Renamed first step') && l.includes('label:'))).toBe(true)
  })
  it('notices a connection that only changed type, and moved decision probabilities', () => {
    const b = clone(base)
    const e = b.edges.find((x) => x.type === 'required')!
    e.type = 'optional'
    const dec = b.nodes.find((n) => n.kind === 'decision' && b.decision_policy.points[n.id]?.default && typeof b.decision_policy.points[n.id].default === 'object')
    if (dec) { const p = b.decision_policy.points[dec.id].default as Record<string, number>; const k = Object.keys(p); p[k[0]] += 0.1; p[k[1]] -= 0.1 }
    const d = diffFlowcharts(base, b)
    expect(d.counts.edgesChanged).toBe(1)
    if (dec) expect(d.nodes[dec.id].what.join(' ')).toContain('probabilities')
  })
  it('the union keeps every step and connection of both once', () => {
    const b = clone(base)
    b.nodes.push({ id: 'x', kind: 'step', label: 'X' })
    const u = unionGraph(base, b)
    expect(u.nodes.length).toBe(base.nodes.length + 1)
    expect(u.edges.length).toBe(base.edges.length)
  })
})

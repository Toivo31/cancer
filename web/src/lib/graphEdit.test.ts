import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { addEdge, removeEdge, setStepFields } from './graphEdit'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]

describe('graph edits', () => {
  it('changes label, test and guard without touching the original', () => {
    const n = fc.nodes.find((x) => x.kind === 'step' && x.test)!
    const d = setStepFields(fc, n.id, { label: 'New label', when: 'age > 50', test: '' })
    const m = d.nodes.find((x) => x.id === n.id)!
    expect(m).toMatchObject({ label: 'New label', when: 'age > 50' })
    expect(m.test).toBeUndefined()
    expect(fc.nodes.find((x) => x.id === n.id)!.label).toBe(n.label)
  })
  it('adds a connection once and removes it again, but leaves decision options alone', () => {
    const [a, b] = fc.nodes.filter((n) => n.kind === 'step')
    const free = fc.nodes.find((n) => n.id !== a.id && !fc.edges.some((e) => e.from === a.id && e.to === n.id))!
    const d = addEdge(fc, a.id, free.id, 'optional')
    expect(d.edges.length).toBe(fc.edges.length + 1)
    expect(addEdge(d, a.id, free.id, 'required')).toBe(d)
    expect(addEdge(d, a.id, a.id, 'required')).toBe(d)
    expect(removeEdge(d, a.id, free.id).edges.length).toBe(fc.edges.length)
    const opt = fc.edges.find((e) => e.type === 'option')!
    expect(removeEdge(fc, opt.from, opt.to).edges.length).toBe(fc.edges.length)
    void b
  })
})

import { addOption, addStep, connectionsOf, removeOption, removeStep, uniqueId } from './graphEdit'

describe('steps and options', () => {
  const dec = fc.nodes.find((n) => n.kind === 'decision')!
  const opts = (d: Flowchart, id: string) => d.edges.filter((e) => e.from === id && e.type === 'option')
  it('adds a step with a unique id, optionally connected after another step', () => {
    const a = fc.nodes.find((n) => n.kind === 'step')!
    const { doc, id } = addStep(fc, { label: 'Chest X-ray', kind: 'step' }, a.id)
    expect(doc.nodes.length).toBe(fc.nodes.length + 1)
    expect(doc.edges).toContainEqual({ from: a.id, to: id, type: 'required' })
    expect(new Set(doc.nodes.map((n) => n.id)).size).toBe(doc.nodes.length)
    expect(addStep(doc, { label: 'Chest X-ray', kind: 'step' }).id).not.toBe(id)
    expect(uniqueId(doc, 'Chest X-ray')).not.toBe(id)
    expect(addStep(fc, { label: '', kind: 'exit', outcome: 'treatment' }).doc.nodes.at(-1)).toMatchObject({ kind: 'exit', outcome: 'treatment' })
    expect(fc.nodes.length).toBe(doc.nodes.length - 1)
  })
  it('deletes a step with every connection and its decision table, and drops the option it was', () => {
    const target = opts(fc, dec.id)[0].to
    const d = removeStep(fc, target)
    expect(d.nodes.some((n) => n.id === target)).toBe(false)
    expect(connectionsOf(d, target)).toEqual([])
    expect(opts(d, dec.id).length).toBe(opts(fc, dec.id).length - 1)
    const probs = d.decision_policy.points[dec.id].default as Record<string, number>
    expect(target in probs).toBe(false)
    expect(Object.values(probs).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 9)
    const dd = removeStep(fc, dec.id)
    expect(dd.decision_policy.points[dec.id]).toBeUndefined()
  })
  it('adds an option with a share of 0 and removes it again', () => {
    const free = fc.nodes.find((n) => n.id !== dec.id && !fc.edges.some((e) => e.from === dec.id && e.to === n.id))!
    const d = addOption(fc, dec.id, free.id)
    expect(opts(d, dec.id).map((e) => e.index)).toEqual(opts(fc, dec.id).map((_, i) => i).concat(opts(fc, dec.id).length))
    expect((d.decision_policy.points[dec.id].default as Record<string, number>)[free.id]).toBe(0)
    expect(addOption(d, dec.id, free.id)).toBe(d)
    const back = removeOption(d, dec.id, free.id)
    expect(back.edges.length).toBe(fc.edges.length)
    expect(back.decision_policy.points[dec.id].default).toEqual(fc.decision_policy.points[dec.id].default)
  })
})

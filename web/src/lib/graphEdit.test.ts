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

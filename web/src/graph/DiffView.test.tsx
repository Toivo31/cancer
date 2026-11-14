import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { DiffView, wrapText } from './DiffView'
import { diffFlowcharts, unionGraph } from '../lib/graphDiff'
import { layoutFlowchart } from './layout'

const base = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]
const clone = (f: Flowchart): Flowchart => JSON.parse(JSON.stringify(f))

describe('graph diff view', () => {
  it('draws both versions, marks the new step and lists it in words', () => {
    const b = clone(base)
    b.nodes.push({ id: 'new_step', kind: 'step', label: 'Brand new step' })
    b.edges.push({ from: b.nodes[0].id, to: 'new_step', type: 'required' })
    render(<DiffView a={base} b={b} labelA="Before" labelB="After" />)
    expect(screen.getAllByTestId('diff-node-added').length).toBe(1)
    expect(screen.getAllByTestId('diff-edge-added').length).toBe(1)
    expect(screen.getByTestId('diff-list').textContent).toContain('New step: Brand new step')
  })
  it('says so when nothing changed', () => {
    render(<DiffView a={base} b={clone(base)} labelA="A" labelB="B" />)
    expect(screen.getByTestId('diff-list').textContent).toContain('No differences')
  })
  it('places a step in both versions at the same position (one layout for the union)', () => {
    const b = clone(base)
    b.nodes.push({ id: 'zz', kind: 'step', label: 'Extra' })
    b.edges.push({ from: b.nodes[1].id, to: 'zz', type: 'required' })
    const u = unionGraph(base, b)
    const l = layoutFlowchart(u.nodes, u.edges, { w: 760, h: 640 })
    expect(Object.keys(l.boxes).length).toBe(u.nodes.length)
    expect(diffFlowcharts(base, b).nodes.zz.change).toBe('added')
  })
  it('wraps long labels without losing words and caps the lines', () => {
    expect(wrapText('GP referral to the regional hospital', 14)).toEqual(['GP referral to', 'the regional', 'hospital'])
    expect(wrapText('a '.repeat(80).trim(), 10, 3)).toHaveLength(3)
  })
})

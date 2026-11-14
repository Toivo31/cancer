import { describe, expect, it } from 'vitest'
import type { CohortPatient, FlowData } from '../api/types'
import { adjacency, bfsPath, counters, patientPath, preparePatients, stateAt } from './playback'

const flow = {
  target_days: 90,
  cohort: { size: 3, horizon: 120, patients: [] as CohortPatient[] },
} as unknown as FlowData

const mk = (id: number, over: Partial<CohortPatient>): CohortPatient => ({
  id, g: 'g', age: 60, cancer: false, out: 'treatment', exit: 'treat', t_exit: 50, t_diag: 20, t_treat: 50,
  v: [['a', 0, 5, 5.5, 8, 1, 1], ['b', 8, 10, 11, 20, 1, 1]], c: [], ...over,
})

describe('playback', () => {
  const pats = [
    mk(1, { cancer: true }),
    mk(2, { cancer: true, out: 'discharged', exit: 'gone', t_exit: 30, t_treat: null, t_diag: null }),
    mk(3, { out: 'discharged', exit: 'gone', t_exit: 12, t_treat: null, t_diag: null }),
  ]
  const f = { ...flow, cohort: { ...flow.cohort, patients: pats } } as FlowData
  const known = new Set(['a', 'b', 'treat', 'gone'])
  const pps = preparePatients(f, known)

  it('puts a patient in the waiting, then served, then resting state', () => {
    const p = pps[0]
    expect(stateAt(p, 2, 1)).toMatchObject({ node: 'a', kind: 0 })
    expect(stateAt(p, 5.2, 1)).toMatchObject({ node: 'a', kind: 1 })
    expect(stateAt(p, 8.2, 1)).toMatchObject({ node: 'b', kind: 0, from: 'a' })
    expect(stateAt(p, 60, 1)).toMatchObject({ node: 'treat', kind: 2, from: null })
  })
  it('counters at the end equal the sample totals', () => {
    const c = counters(pps, Infinity)
    expect(c.treated).toBe(pats.filter((p) => p.out === 'treatment').length)
    expect(c.missed).toBe(1)
    expect(c.left).toBe(1)
    expect(c.waiting + c.served).toBe(0)
    expect(c.arrived).toBe(3)
  })
  it('counters before anyone arrives are zero', () => { expect(counters(pps, -1).arrived).toBe(0) })
  it('finds a path along connections and a patient trail', () => {
    const adj = adjacency([{ from: 'a', to: 'x' }, { from: 'x', to: 'b' }, { from: 'b', to: 'treat' }])
    expect(bfsPath(adj, 'a', 'b')).toEqual(['a', 'x', 'b'])
    const trail = patientPath(pps[0], adj)
    expect([...trail.nodes].sort()).toEqual(['a', 'b', 'treat', 'x'])
    expect(trail.edges.has('a>x')).toBe(true)
  })
})

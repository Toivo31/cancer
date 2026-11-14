import { describe, expect, it } from 'vitest'
import type { Run } from '../api/types'
import { effectiveRun } from './runSelect'

const run = (id: string, version: number, status: Run['status'] = 'succeeded'): Run => ({ id, job_id: null, status, progress: 1, label: id, flowchart: { id: 'f', version }, n: 10, seeds: [1] })

describe('effectiveRun', () => {
  const runs = [run('r2', 2), run('r1', 1)]
  it('keeps a requested run that belongs to the shown version', () => {
    expect(effectiveRun(runs, 'r2', 'f', 2)?.id).toBe('r2')
  })
  it('ignores a requested run of an older version after saving a new one', () => {
    expect(effectiveRun(runs, 'r1', 'f', 3)).toBeNull()
    expect(effectiveRun(runs, 'r1', 'f', 2)?.id).toBe('r2')
  })
  it('falls back to a finished run of this version, not a running one', () => {
    expect(effectiveRun([run('r3', 2, 'running')], null, 'f', 2)).toBeNull()
    expect(effectiveRun(runs, null, 'f', 1)?.id).toBe('r1')
  })
  it('a run of another flowchart never matches', () => {
    expect(effectiveRun([{ ...run('x', 2), flowchart: { id: 'g', version: 2 } }], 'x', 'f', 2)).toBeNull()
  })
})

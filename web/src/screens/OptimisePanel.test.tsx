import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiCtx } from '../ApiContext'
import type { Api } from '../api'
import type { Flowchart, Optimisation } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { OptimisePanel } from './OptimisePanel'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]

const done: Optimisation = {
  id: 'o_1', status: 'succeeded', progress: 1, message: '', flowchart: { id: fc.id, version: fc.version },
  summary: { n_changes: 2, n_blocked: 1, heldout_before: 0.125, heldout_after: 0.1875 },
  honesty: 'Numbers shown are from patients the search never saw.',
  changes: [
    { index: 0, kind: 'relax', target: 'a', label: 'Do A while B runs', records_reading: 'A was held back by B', linked_with: [], heldout_after_this_change: { on_time: 0.3, median_days: 97 } },
    { index: 1, kind: 'standardise', target: 'c', label: 'Always book C', linked_with: [] },
  ],
  blocked: [{ label: 'Skip D', reason: 'would raise tests per patient' }],
}

describe('optimise panel', () => {
  it('starts a search, lists changes with evidence and applies the chosen subset', async () => {
    const api = {
      kind: 'mock', listOptimisations: async () => [],
      startOptimisation: vi.fn(async () => ({ ...done, status: 'queued', changes: undefined })),
      getOptimisation: vi.fn(async () => done), getFlowchart: vi.fn(async () => fc), compareRuns: vi.fn(async () => new Promise(() => {})), getRun: vi.fn(async () => new Promise(() => {})),
      applyOptimisation: vi.fn(async () => ({ flowchart: { id: fc.id, version: 2 }, based_on: { id: fc.id, version: 1 }, accepted: [0] })),
    } as unknown as Api
    render(<ApiCtx.Provider value={api}><OptimisePanel pid="p" flowchart={fc} world={null} onOpen={() => {}} onRunsChanged={() => {}} /></ApiCtx.Provider>)
    fireEvent.click(screen.getByTestId('start-optimise'))
    await waitFor(() => expect(screen.getByTestId('optimise-result')).toBeTruthy(), { timeout: 4000 })
    expect(screen.getByText('A was held back by B')).toBeTruthy()
    expect(screen.getByTestId('honesty').textContent).toContain('never saw')
    expect(screen.getByTestId('optimise-blocked').textContent).toContain('Skip D')
    fireEvent.click(screen.getByLabelText('Accept change 2'))
    fireEvent.click(screen.getByTestId('apply-changes'))
    await waitFor(() => expect(api.applyOptimisation).toHaveBeenCalled())
    expect(api.applyOptimisation).toHaveBeenCalledWith('p', 'o_1', expect.objectContaining({ accept: [0], rerun: true }))
    fireEvent.click(await screen.findByTestId('show-diff'))
    expect(await screen.findByTestId('diff-view')).toBeTruthy()
    expect(api.getFlowchart).toHaveBeenCalledWith('p', fc.id, 1)
    expect(api.getFlowchart).toHaveBeenCalledWith('p', fc.id, 2)
  })
})

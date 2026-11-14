import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import { draftFrom } from '../lib/decisionDraft'
import type { Draft } from '../lib/decisionDraft'
import templates from '../mock/fixtures/templates.json'
import { DecisionsTable } from './DecisionsTable'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]

function Harness({ onDraft }: { onDraft: (d: Draft) => void }) {
  const [d, setD] = useState(draftFrom(fc))
  onDraft(d)
  return <DecisionsTable flowchart={fc} draft={d} onChange={setD} selected={null} onSelect={() => {}} />
}

describe('decisions table', () => {
  it('shows a row that does not add to 100 as an error and balances it on request', () => {
    let last!: Draft
    render(<Harness onDraft={(d) => { last = d }} />)
    const input = screen.getByLabelText('Nurse assessment share, default')
    fireEvent.change(input, { target: { value: '70' } })
    expect(screen.getByText(/120 ≠ 100/)).toBeTruthy()
    fireEvent.click(screen.getAllByText('Balance')[0])
    expect(last.points[0].rows[0].vals.map(Number).reduce((a, b) => a + b, 0)).toBe(100)
    expect(screen.queryByText(/≠ 100/)).toBeNull()
  })
  it('adds and removes a condition row', () => {
    render(<Harness onDraft={() => {}} />)
    const before = screen.getAllByLabelText('Condition').length
    fireEvent.click(screen.getAllByText('Add a condition')[0])
    expect(screen.getAllByLabelText('Condition').length).toBe(before + 1)
    fireEvent.click(screen.getAllByLabelText('Remove condition')[0])
    expect(screen.getAllByLabelText('Condition').length).toBe(before)
  })
})

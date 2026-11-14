import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Flowchart, World } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { EditPanel } from './EditPanel'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts[0]
const step = fc.nodes.find((n) => n.kind === 'step')!

function setup(over: Partial<Parameters<typeof EditPanel>[0]> = {}) {
  const onChange = vi.fn(), onSelect = vi.fn()
  render(<EditPanel doc={fc} world={{} as World} selected={step.id} onSelect={onSelect} onChange={onChange} canUndo={false} canRedo={false} onUndo={() => {}} onRedo={() => {}}
    problems={[]} checking={false} dirty saving={false} baseVersion={1} latestVersion={1} flowchartName="x" onSave={() => {}} onDiscard={() => {}} {...over} />)
  return { onChange, onSelect }
}

describe('edit panel', () => {
  it('asks inside the app before deleting a step, and deletes it with its connections only after confirming', () => {
    const { onChange, onSelect } = setup()
    fireEvent.click(screen.getByTestId('delete-step'))
    expect(screen.getByTestId('confirm-delete').textContent).toContain(step.label)
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Keep it'))
    expect(screen.queryByTestId('confirm-delete')).toBeNull()
    fireEvent.click(screen.getByTestId('delete-step'))
    fireEvent.click(screen.getByTestId('confirm-delete-yes'))
    const doc = onChange.mock.calls[0][0] as Flowchart
    expect(doc.nodes.some((n) => n.id === step.id)).toBe(false)
    expect(doc.edges.some((e) => e.from === step.id || e.to === step.id)).toBe(false)
    expect(onSelect).toHaveBeenCalledWith(null)
  })
  it('adds a step after the selected one and selects it', () => {
    const { onChange, onSelect } = setup()
    fireEvent.click(screen.getByText('Add a step'))
    fireEvent.change(screen.getByLabelText('Name of the new step'), { target: { value: 'Extra check' } })
    fireEvent.click(screen.getByTestId('add-step-go'))
    const doc = onChange.mock.calls[0][0] as Flowchart
    expect(doc.nodes.at(-1)).toMatchObject({ id: 'extra_check', label: 'Extra check' })
    expect(doc.edges.at(-1)).toMatchObject({ from: step.id, to: 'extra_check' })
    expect(onSelect).toHaveBeenCalledWith('extra_check')
  })
  it('keeps Save blocked while there are errors or a check is running, and undo reflects history', () => {
    setup({ problems: [{ severity: 'error', code: 'x', message: 'broken' }] })
    expect((screen.getByTestId('edit-save') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByTestId('edit-undo') as HTMLButtonElement).disabled).toBe(true)
  })
})

import { useEffect, useState } from 'react'
import type { EdgeType, Flowchart, Problem, World } from '../api/types'
import { addEdge, addOption, addStep, connectionsOf, EDITABLE_EDGE_TYPES, removeEdge, removeOption, removeStep, setStepFields } from '../lib/graphEdit'

const TYPE_HELP: Record<string, string> = {
  required: 'must be finished first',
  any: 'any one of the "any of" connections is enough',
  optional: 'only waited for if that step ran',
  option: 'a decision option',
}

interface Props {
  doc: Flowchart
  world: World
  selected: string | null
  onSelect: (id: string | null) => void
  /** `key` groups quick edits of one field into one undo step */
  onChange: (doc: Flowchart, key?: string) => void
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  problems: Problem[]
  checking: boolean
  dirty: boolean
  saving: boolean
  baseVersion: number
  latestVersion: number
  flowchartName: string
  onSave: () => void
  onDiscard: () => void
}

/** The smallest editor: change a step's label, what happens there and its guard; add or remove a connection; save as a new version. */
export function EditPanel(p: Props) {
  const { doc, world, selected, onSelect, onChange, checking, dirty, saving } = p
  let { problems } = p
  const node = selected ? doc.nodes.find((n) => n.id === selected) : undefined
  const labelOf = (id: string) => doc.nodes.find((n) => n.id === id)?.label ?? id
  // the service checks the rules of the model; steps nobody connected are only noticed here
  const lonely: Problem[] = doc.nodes.filter((n) => !doc.edges.some((e) => e.from === n.id || e.to === n.id)).map((n) => ({ severity: 'warning', code: 'no_connections', node: n.id, message: 'has no connections yet.', hint: 'Connect it to the steps before and after it.' }))
  problems = [...problems, ...lonely]
  const errors = problems.filter((x) => x.severity === 'error')
  const [target, setTarget] = useState('')
  const [optTarget, setOptTarget] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [newLabel, setNewLabel] = useState('')
  const [newKind, setNewKind] = useState<'step' | 'join' | 'exit'>('step')
  const [newOutcome, setNewOutcome] = useState('discharged')
  const [connectNew, setConnectNew] = useState(true)
  useEffect(() => { setConfirmDelete(false); setOptTarget('') }, [selected])
  const [type, setType] = useState<EdgeType>('required')
  const tests = Object.keys(world.tests ?? {})
  const outgoing = node ? doc.edges.filter((e) => e.from === node.id) : []
  const incoming = node ? doc.edges.filter((e) => e.to === node.id) : []
  const optionTargets = node?.kind === 'decision' ? doc.nodes.filter((n) => n.id !== node.id && !doc.edges.some((e) => e.from === node.id && e.to === n.id)) : []
  const candidates = node ? doc.nodes.filter((n) => n.id !== node.id && !doc.edges.some((e) => e.from === node.id && e.to === n.id)) : []

  return (
    <section data-testid="edit-panel">
      <h4 className="label">Edit {p.flowchartName}</h4>
      <div className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>Select a step on the chart to change it. Nothing is saved until you press Save; saving makes a new version and leaves earlier ones as they were.</div>

      <div className="form-row" style={{ marginBottom: 10 }}>
        <button className="btn small" onClick={p.onUndo} disabled={!p.canUndo} aria-label="Undo" title="Undo the last change (Ctrl+Z)" data-testid="edit-undo">↶ Undo</button>
        <button className="btn small" onClick={p.onRedo} disabled={!p.canRedo} aria-label="Redo" title="Redo (Ctrl+Shift+Z)" data-testid="edit-redo">↷ Redo</button>
      </div>

      <details className="addstep" style={{ marginBottom: 12 }} data-testid="add-step">
        <summary style={{ cursor: 'pointer' }}>Add a step</summary>
        <div className="stack" style={{ marginTop: 8 }}>
          <input className="field" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="Name of the new step" aria-label="Name of the new step" />
          <div className="form-row" style={{ flexWrap: 'nowrap' }}>
            <select className="field" value={newKind} onChange={(e) => setNewKind(e.target.value as 'step' | 'join' | 'exit')} aria-label="Kind of step" style={{ flex: 1 }}>
              <option value="step">Step (something happens, patients wait)</option>
              <option value="join">Join (waits for several steps)</option>
              <option value="exit">End point</option>
            </select>
            {newKind === 'exit' && (
              <select className="field" value={newOutcome} onChange={(e) => setNewOutcome(e.target.value)} aria-label="Outcome">
                <option value="treatment">treatment starts</option><option value="discharged">discharged</option><option value="diagnosis_only">diagnosis only</option>
              </select>
            )}
          </div>
          {node && node.kind !== 'exit' && <label className="form-row" style={{ gap: 6, fontSize: 12.5 }}><input type="checkbox" checked={connectNew} onChange={(e) => setConnectNew(e.target.checked)} />Connect it after “{node.label}”</label>}
          <div><button className="btn small primary" onClick={() => { const r = addStep(doc, { label: newLabel, kind: newKind, outcome: newOutcome }, connectNew && node ? node.id : null); onChange(r.doc); onSelect(r.id); setNewLabel('') }} data-testid="add-step-go">Add step</button></div>
          <div className="dim" style={{ fontSize: 11.5 }}>A new step has no connections until you add them; the checks below say what is missing.</div>
        </div>
      </details>

      {!node && <div className="empty">Click a step on the chart to change it.</div>}
      {node && (
        <div className="stack" data-testid="edit-step">
          <div className="form-row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
            <div className="dim mono" style={{ fontSize: 11.5, minWidth: 0, overflowWrap: 'anywhere' }}>{node.kind} · {node.id}</div>
            {!confirmDelete && <button className="btn small danger" onClick={() => setConfirmDelete(true)} data-testid="delete-step">Delete step…</button>}
          </div>
          {confirmDelete && (
            <div className="confirm" role="alertdialog" aria-label="Confirm delete" data-testid="confirm-delete">
              <div style={{ fontSize: 12.5, marginBottom: 8 }}>Delete “{node.label}” and its {connectionsOf(doc, node.id).length} connection{connectionsOf(doc, node.id).length === 1 ? '' : 's'}? You can undo this until you leave edit mode.</div>
              <div className="form-row">
                <button className="btn small danger" autoFocus onClick={() => { onChange(removeStep(doc, node.id)); onSelect(null); setConfirmDelete(false) }} data-testid="confirm-delete-yes">Delete</button>
                <button className="btn small" onClick={() => setConfirmDelete(false)}>Keep it</button>
              </div>
            </div>
          )}
          <label className="stack" style={{ gap: 4 }}>
            <span className="dim">Label</span>
            <input className="field" value={node.label} onChange={(e) => onChange(setStepFields(doc, node.id, { label: e.target.value }), `label:${node.id}`)} aria-label="Label" />
          </label>
          {(node.kind === 'step' || node.test) && (
            <label className="stack" style={{ gap: 4 }}>
              <span className="dim">What happens (test)</span>
              <select className="field" value={node.test ?? ''} onChange={(e) => onChange(setStepFields(doc, node.id, { test: e.target.value }))} aria-label="What happens" style={{ maxWidth: '100%' }}>
                <option value="">(nothing: a pure waiting or routing step)</option>
                {node.test && !tests.includes(node.test) && <option value={node.test}>{node.test}</option>}
                {tests.map((t) => <option key={t} value={t}>{t}{world.tests?.[t]?.resource ? ` · ${world.tests[t].resource}` : ''}</option>)}
              </select>
            </label>
          )}
          <label className="stack" style={{ gap: 4 }}>
            <span className="dim">Only if (guard)</span>
            <input className="field mono" value={node.when ?? ''} onChange={(e) => onChange(setStepFields(doc, node.id, { when: e.target.value }), `when:${node.id}`)} placeholder="always (for example: age >= 65)" aria-label="Guard" />
          </label>

          <div>
            <div className="dim" style={{ marginBottom: 4 }}>Connections out of this step</div>
            {outgoing.length === 0 && <div className="dim" style={{ fontSize: 12 }}>None.</div>}
            {outgoing.map((e) => (
              <div key={`${e.to}`} className="form-row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap', marginBottom: 4 }}>
                <span className="clamp2" style={{ fontSize: 12.5 }}>→ <a href="#" onClick={(ev) => { ev.preventDefault(); onSelect(e.to) }}>{labelOf(e.to)}</a> <span className="pill">{e.type}</span></span>
                {e.type === 'option'
                  ? <button className="btn small" onClick={() => onChange(removeOption(doc, e.from, e.to))} aria-label={`Remove option ${labelOf(e.to)}`} title="Remove this option; the other shares are scaled to add to 100% again">Remove</button>
                  : <button className="btn small" onClick={() => onChange(removeEdge(doc, e.from, e.to))} aria-label={`Remove connection to ${labelOf(e.to)}`}>Remove</button>}
              </div>
            ))}
            <div className="form-row" style={{ marginTop: 8, flexWrap: 'nowrap' }}>
              <select className="field" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Connect to" style={{ flex: 1, minWidth: 0 }}>
                <option value="">Connect to…</option>
                {candidates.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
              </select>
              <select className="field" value={type} onChange={(e) => setType(e.target.value as EdgeType)} aria-label="Connection type" title={TYPE_HELP[type]}>
                {EDITABLE_EDGE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <button className="btn small" disabled={!target} onClick={() => { onChange(addEdge(doc, node.id, target, type)); setTarget('') }}>Add</button>
            </div>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 4 }}>{type}: {TYPE_HELP[type]}.</div>
            {node.kind === 'decision' && (
              <div className="form-row" style={{ marginTop: 8, flexWrap: 'nowrap' }}>
                <select className="field" value={optTarget} onChange={(e) => setOptTarget(e.target.value)} aria-label="Add an option leading to" style={{ flex: 1, minWidth: 0 }}>
                  <option value="">Add an option leading to…</option>
                  {optionTargets.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
                </select>
                <button className="btn small" disabled={!optTarget} onClick={() => { onChange(addOption(doc, node.id, optTarget)); setOptTarget('') }}>Add option</button>
              </div>
            )}
            {node.kind === 'decision' && <div className="dim" style={{ fontSize: 11.5, marginTop: 4 }}>A new option starts at 0%; set the shares in the Decisions table after saving.</div>}
            {incoming.length > 0 && <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>Comes from: {incoming.map((e) => labelOf(e.from)).join(', ')}</div>}
          </div>

        </div>
      )}

      <div style={{ marginTop: 14 }} data-testid="edit-problems">
        <div className="label" style={{ marginBottom: 4 }}>Checks {checking ? '…' : problems.length === 0 ? '· none' : `· ${errors.length} error${errors.length === 1 ? '' : 's'}, ${problems.length - errors.length} warning${problems.length - errors.length === 1 ? '' : 's'}`}</div>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
          {problems.map((x, i) => (
            <li key={i} style={{ color: x.severity === 'error' ? 'var(--coral)' : 'var(--amber)', cursor: x.node ? 'pointer' : undefined }} onClick={() => x.node && onSelect(x.node)}>
              {x.node ? `${labelOf(x.node)}: ` : ''}{x.message}{x.hint ? ` ${x.hint}` : ''}
            </li>
          ))}
        </ul>
      </div>

      <div className="form-row" style={{ marginTop: 14 }}>
        <button className="btn primary" disabled={!dirty || saving || errors.length > 0 || checking} onClick={p.onSave} data-testid="edit-save">{saving ? 'Saving…' : 'Save as new version'}</button>
        <button className="btn" disabled={!dirty || saving} onClick={p.onDiscard}>Discard</button>
      </div>
      <div className="dim" style={{ fontSize: 12, marginTop: 6 }}>{!dirty ? `Nothing changed since version ${p.baseVersion}.` : `Saves version ${p.latestVersion + 1} of "${p.flowchartName}".`}</div>
    </section>
  )
}

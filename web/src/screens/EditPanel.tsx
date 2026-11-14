import { useState } from 'react'
import type { EdgeType, Flowchart, Problem, World } from '../api/types'
import { addEdge, EDITABLE_EDGE_TYPES, removeEdge, setStepFields } from '../lib/graphEdit'

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
  onChange: (doc: Flowchart) => void
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
  const { doc, world, selected, onSelect, onChange, problems, checking, dirty, saving } = p
  const node = selected ? doc.nodes.find((n) => n.id === selected) : undefined
  const labelOf = (id: string) => doc.nodes.find((n) => n.id === id)?.label ?? id
  const errors = problems.filter((x) => x.severity === 'error')
  const [target, setTarget] = useState('')
  const [type, setType] = useState<EdgeType>('required')
  const tests = Object.keys(world.tests ?? {})
  const outgoing = node ? doc.edges.filter((e) => e.from === node.id) : []
  const incoming = node ? doc.edges.filter((e) => e.to === node.id) : []
  const candidates = node ? doc.nodes.filter((n) => n.id !== node.id && !doc.edges.some((e) => e.from === node.id && e.to === n.id)) : []

  return (
    <section data-testid="edit-panel">
      <h4 className="label">Edit {p.flowchartName}</h4>
      <div className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>Select a step on the chart to change it. Nothing is saved until you press Save; saving makes a new version and leaves earlier ones as they were.</div>

      {!node && <div className="empty">Click a step.</div>}
      {node && (
        <div className="stack" data-testid="edit-step">
          <div className="dim mono" style={{ fontSize: 11.5 }}>{node.kind} · {node.id}</div>
          <label className="stack" style={{ gap: 4 }}>
            <span className="dim">Label</span>
            <input className="field" value={node.label} onChange={(e) => onChange(setStepFields(doc, node.id, { label: e.target.value }))} aria-label="Label" />
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
            <input className="field mono" value={node.when ?? ''} onChange={(e) => onChange(setStepFields(doc, node.id, { when: e.target.value }))} placeholder="always (for example: age >= 65)" aria-label="Guard" />
          </label>

          <div>
            <div className="dim" style={{ marginBottom: 4 }}>Connections out of this step</div>
            {outgoing.length === 0 && <div className="dim" style={{ fontSize: 12 }}>None.</div>}
            {outgoing.map((e) => (
              <div key={`${e.to}`} className="form-row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap', marginBottom: 4 }}>
                <span className="clamp2" style={{ fontSize: 12.5 }}>→ <a href="#" onClick={(ev) => { ev.preventDefault(); onSelect(e.to) }}>{labelOf(e.to)}</a> <span className="pill">{e.type}</span></span>
                {e.type === 'option'
                  ? <span className="dim" style={{ fontSize: 11 }} title="Decision options are edited with the decision's table">table</span>
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

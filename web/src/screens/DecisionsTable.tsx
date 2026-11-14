import type { Flowchart } from '../api/types'
import type { Draft, PointDraft, RowDraft } from '../lib/decisionDraft'
import { rowNumbers, rowTotal } from '../lib/decisionDraft'
import { normalisePct, parsePct, rowOk } from '../lib/probs'

interface Props {
  flowchart: Flowchart
  draft: Draft
  onChange: (d: Draft) => void
  selected: string | null
  onSelect: (id: string | null) => void
}

export function DecisionsTable({ flowchart, draft, onChange, selected, onSelect }: Props) {
  const label = (id: string) => flowchart.nodes.find((n) => n.id === id)?.label ?? id

  const setPoint = (i: number, p: PointDraft) => onChange({ ...draft, points: draft.points.map((q, j) => (j === i ? p : q)) })
  const setRow = (i: number, ri: number, r: RowDraft) => setPoint(i, { ...draft.points[i], rows: draft.points[i].rows.map((x, j) => (j === ri ? r : x)) })

  return (
    <div data-testid="decisions-table">
      <div className="form-row" style={{ marginBottom: 16, gap: 24 }}>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Who decides</div>
          <select className="field" aria-label="Decision source" defaultValue="stub" disabled><option value="stub">Hardcoded probabilities</option><option>JEV API (not connected yet)</option></select>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>How a choice is made</div>
          {draft.ruleBackend ? <div className="muted" style={{ fontSize: 12.5, maxWidth: 260 }}>Older document: each patient is sent by sampling from the shares.</div> : <div className="tabs" role="radiogroup" aria-label="Sample or most likely">
            {([['sample', 'Sample from the probabilities'], ['argmax', 'Take the most likely']] as const).map(([v, t]) => (
              <button key={v} role="radio" aria-checked={draft.mode === v} className={`tab ${draft.mode === v ? 'on' : ''}`} onClick={() => onChange({ ...draft, mode: v })}>{t}</button>
            ))}
          </div>}
        </div>
        <div className="muted" style={{ maxWidth: 520, fontSize: 12.5 }}>
          Each row is the share of patients sent each way at that decision point; a row must add to 100. A condition row applies first when it holds for the patient (for example <span className="mono">location == 'central'</span>); the first row without a condition is the default.
        </div>
      </div>

      {draft.points.length === 0 && <div className="empty">This flowchart has no decision points.</div>}
      {draft.points.map((p, i) => (
        <div key={p.id} className={`card dcard ${selected === p.id ? 'sel' : ''}`} onClick={() => onSelect(p.id)} data-testid={`decision-${p.id}`}>
          <h3>{label(p.id)}</h3>
          <div className="dim" style={{ fontSize: 12, marginBottom: 10 }}>
            <span className="mono">{p.id}</span> · source: {p.unset ? <span style={{ color: 'var(--amber)' }}>none set, equal shares shown</span> : p.source || 'assumption'}
          </div>
          <table className="t" style={{ maxWidth: 1000 }}>
            <thead>
              <tr>
                <th style={{ width: '28%' }}>When</th>
                {p.options.map((o) => <th key={o} title={o} style={{ textAlign: 'right' }}>{label(o)} %</th>)}
                <th style={{ textAlign: 'right' }}>Total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {p.rows.map((r, ri) => {
                const ok = rowOk(rowNumbers(r))
                return (
                  <tr key={ri}>
                    <td>
                      {r.when === null ? <span className="muted">Otherwise (default)</span> : r.fixed ? <span className="mono" title="A fixed choice from the original document">{r.when}</span> : (
                        <input className={`field mono ${r.when.trim() ? '' : 'bad'}`} style={{ width: '100%' }} aria-label="Condition" value={r.when} placeholder="location == 'central'" onChange={(e) => setRow(i, ri, { ...r, when: e.target.value })} />
                      )}
                    </td>
                    {p.options.map((o, oi) => {
                      const bad = parsePct(r.vals[oi]) === null || (parsePct(r.vals[oi]) as number) < 0 || (parsePct(r.vals[oi]) as number) > 100
                      return (
                        <td key={o} style={{ textAlign: 'right' }}>
                          <input disabled={r.fixed} className={`field num-in ${bad ? 'bad' : ''}`} aria-label={`${label(o)} share, ${r.when ?? 'default'}`} value={r.vals[oi]} inputMode="decimal"
                            onChange={(e) => setRow(i, ri, { ...r, vals: r.vals.map((v, k) => (k === oi ? e.target.value : v)) })} />
                        </td>
                      )
                    })}
                    <td style={{ textAlign: 'right' }}><span className={`sum ${ok ? 'ok' : 'bad'}`}>{rowTotal(r)}{ok ? '' : ' ≠ 100'}</span></td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {!ok ? (
                        <button className="btn small" title="Scale the numbers so they add to 100" onClick={() => { const nums = rowNumbers(r).map((v) => Math.max(0, v ?? 0)); setRow(i, ri, { ...r, vals: normalisePct(nums).map(String) }) }}>Balance</button>
                      ) : null}
                      {r.when !== null && !r.fixed && <button className="btn small danger" style={{ marginLeft: 6 }} aria-label="Remove condition" onClick={() => setPoint(i, { ...p, rows: p.rows.filter((_, j) => j !== ri) })}>Remove</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div style={{ marginTop: 10 }}>
            {p.legacy
              ? <span className="dim" style={{ fontSize: 12 }}>Conditions are fixed in this older document; only the default shares can change here.</span>
              : <button className="btn small" onClick={() => setPoint(i, { ...p, rows: [...p.rows, { when: '', vals: p.rows[0].vals.slice() }] })}>Add a condition</button>}
          </div>
        </div>
      ))}
    </div>
  )
}

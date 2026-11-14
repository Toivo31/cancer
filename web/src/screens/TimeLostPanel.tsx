import type { FlowData } from '../api/types'

export function TimeLostPanel({ flow, selected, onSelect }: { flow: FlowData; selected: string | null; onSelect: (id: string) => void }) {
  const rows = flow.time_lost.slice(0, 10)
  const max = Math.max(0.01, ...rows.map((r) => r.wait))
  return (
    <section data-testid="time-lost">
      <h4 className="label">Where time is lost</h4>
      <div className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>Days waiting at each step on the way to treatment, averaged over patients who were treated. Click a step to find it on the graph.</div>
      {rows.length === 0 && <div className="empty">No waiting recorded.</div>}
      <div className="stack" style={{ gap: 6 }}>
        {rows.map((r) => (
          <button key={r.node} className={`lostrow ${selected === r.node ? 'on' : ''}`} onClick={() => onSelect(r.node)}>
            <div className="form-row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
              <span className="clamp2" style={{ textAlign: 'left' }}>{r.label}</span>
              <span className="num" style={{ color: 'var(--amber)', whiteSpace: 'nowrap' }}>{(Math.round(r.wait * 10) / 10).toFixed(1)} d</span>
            </div>
            <div className="bar"><div style={{ width: `${(r.wait / max) * 100}%` }} /></div>
            <div className="dim num" style={{ fontSize: 11 }}>{Math.round(r.wait_share * 100)}% of all waiting{r.wait_median != null ? ` · median wait ${(Math.round(r.wait_median * 10) / 10).toFixed(1)} d` : ''} · {r.n_critical} patients</div>
          </button>
        ))}
      </div>
    </section>
  )
}

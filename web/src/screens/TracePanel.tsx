import type { FlowData } from '../api/types'
import type { PPatient } from '../graph/playback'

const d1 = (x: number) => (Math.round(x * 10) / 10).toFixed(1)
const RESULT: Record<string, string> = { '1': 'positive', '0': 'negative', null: '–' }

export function TracePanel({ flow, pp, labelOf, patients, onPick }: { flow: FlowData; pp: PPatient | null; labelOf: (id: string) => string; patients: PPatient[]; onPick: (idx: number | null) => void }) {
  if (!pp) {
    return (
      <section data-testid="trace-empty">
        <h4 className="label">Patient trace</h4>
        <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>Click a dot on the graph, or pick a patient here, to see the steps they went through.</div>
        <div className="patientlist">
          {patients.slice(0, 60).map((q) => (
            <button key={q.idx} className="btn small" onClick={() => onPick(q.idx)} title={`${q.p.g}, age ${q.p.age}`}>#{String(q.p.id)} <span className={q.treated ? (q.late ? 'dim' : 'okc') : 'badc'}>{q.treated ? (q.late ? 'late' : 'on time') : q.missed ? 'missed' : 'left'}</span></button>
          ))}
        </div>
      </section>
    )
  }
  const p = pp.p
  const visits = p.v.slice().sort((a, b) => a[1] - b[1] || a[2] - b[2])
  const target = flow.target_days
  return (
    <section data-testid="trace">
      <div className="form-row" style={{ justifyContent: 'space-between' }}>
        <h4 className="label" style={{ margin: 0 }}>Patient #{String(p.id)}</h4>
        <button className="btn small" onClick={() => onPick(null)}>Close</button>
      </div>
      <div className="kv" style={{ fontSize: 12.5, margin: '10px 0' }}>
        <span className="dim">Group</span><span>{p.g}, age {Math.round(p.age)}</span>
        <span className="dim">Has cancer</span><span>{p.cancer ? 'yes' : 'no'}</span>
        <span className="dim">Outcome</span><span>{p.out === 'treatment' ? `Treatment started on day ${p.t_treat != null ? d1(p.t_treat) : '?'}` : p.out === 'discharged' ? `Left the pathway on day ${p.t_exit != null ? d1(p.t_exit) : '?'}${p.cancer ? ' (cancer not treated)' : ''}` : p.out}</span>
        {p.t_diag != null && <><span className="dim">Diagnosis</span><span className="num">day {d1(p.t_diag)}</span></>}
        {pp.treated && p.t_treat != null && <><span className="dim">Target</span><span className="num" style={{ color: p.t_treat <= target ? 'var(--mint)' : 'var(--coral)' }}>{p.t_treat <= target ? 'within' : 'over'} {target} days</span></>}
      </div>
      <table className="t" style={{ fontSize: 12 }}>
        <thead><tr><th>Step</th><th style={{ textAlign: 'right' }}>Waited</th><th style={{ textAlign: 'right' }}>Took</th><th>Result</th></tr></thead>
        <tbody>
          {visits.map((v, i) => (
            <tr key={i}>
              <td>{v[6] ? <span title="On the critical path" style={{ color: 'var(--text)' }}>● </span> : <span className="dim">○ </span>}{labelOf(v[0])}<div className="dim num" style={{ fontSize: 10.5 }}>from day {d1(v[1])}</div></td>
              <td className="num" style={{ textAlign: 'right', whiteSpace: 'nowrap', color: v[2] - v[1] > 7 ? 'var(--amber)' : undefined }}>{d1(v[2] - v[1])} d</td>
              <td className="num" style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>{d1(Math.max(0, v[4] - v[2]))} d</td>
              <td>{RESULT[String(v[5])]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="dim" style={{ fontSize: 11.5, margin: '6px 0 12px' }}>● on the critical path (shown in white on the graph), ○ ran in parallel.</div>
      {p.c.length > 0 && (
        <>
          <h4 className="label">Decisions</h4>
          <div className="stack" style={{ gap: 8 }}>
            {p.c.map((c, i) => (
              <div key={i} style={{ fontSize: 12.5 }}>
                <div><span className="num dim">day {d1(c[1])}</span> {labelOf(c[0])}: <strong style={{ color: 'var(--violet)' }}>{labelOf(c[2])}</strong></div>
                <div className="dim num" style={{ fontSize: 11.5 }}>offered: {c[3].map((o) => `${labelOf(o)} ${Math.round((c[4][o] ?? 0) * 100)}%`).join(' · ')}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}

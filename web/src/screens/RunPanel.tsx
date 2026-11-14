import { useState } from 'react'
import { useApi } from '../ApiContext'
import type { Flowchart, Run, World } from '../api/types'

const pct = (v?: number | null) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const days = (v?: number | null) => (v == null ? '–' : v.toFixed(1))

export function parseSeeds(text: string): number[] | null {
  const parts = text.split(/[,\s]+/).filter(Boolean)
  if (parts.length === 0 || parts.length > 5) return null
  const nums = parts.map(Number)
  return nums.every((x) => Number.isInteger(x) && x >= 0) ? nums : null
}

interface Props {
  pid: string
  flowchart: Flowchart
  world: World | null
  runs: Run[]
  runsError: string | null
  selectedRun: string | null
  onSelectRun: (id: string | null) => void
  onChanged: () => void
  dirty: boolean
}

export function RunPanel({ pid, flowchart, world, runs, runsError, selectedRun, onSelectRun, onChanged, dirty }: Props) {
  const api = useApi()
  const [n, setN] = useState(String(world?.default_n ?? 1000))
  const [seeds, setSeeds] = useState('301')
  const [label, setLabel] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const nNum = Number(n)
  const seedList = parseSeeds(seeds)
  const valid = Number.isInteger(nNum) && nNum >= 10 && nNum <= 50000 && seedList !== null

  async function start() {
    if (!valid || !seedList) return
    setBusy(true); setErr(null)
    try {
      const r = await api.startRun(pid, { flowchart: { id: flowchart.id, version: flowchart.version }, n: nNum, seeds: seedList, decision_policy: null, label: label.trim() || `${flowchart.id} v${flowchart.version}` })
      onSelectRun(r.run_id)
      onChanged()
      setLabel('')
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  async function cancel(r: Run) {
    if (r.job_id) await api.cancelJob(r.job_id).catch((e) => setErr(e.message))
    onChanged()
  }

  const active = runs.filter((r) => r.status === 'queued' || r.status === 'running')
  return (
    <>
      <section data-testid="run-panel">
        <h4 className="label">Run this version</h4>
        <div className="stack">
          <div className="kv">
            <span className="dim">Flowchart</span><span className="clamp2" title={flowchart.name}>{flowchart.name} <span className="num dim">v{flowchart.version}</span></span>
            <span className="dim">Decisions</span><span>{flowchart.decision_policy.backend === 'stub' ? 'Hardcoded probabilities (stored in this version)' : flowchart.decision_policy.backend}</span>
            <label className="dim" htmlFor="run-n">Patients</label><input id="run-n" className={`field num-in ${valid || !n ? '' : 'bad'}`} style={{ width: 96 }} value={n} onChange={(e) => setN(e.target.value)} inputMode="numeric" />
            <label className="dim" htmlFor="run-seeds">Seeds</label><input id="run-seeds" className={`field num-in ${seedList ? '' : 'bad'}`} style={{ width: 120, textAlign: 'left' }} value={seeds} onChange={(e) => setSeeds(e.target.value)} placeholder="301, 302" />
            <label className="dim" htmlFor="run-label">Label</label><input id="run-label" className="field" value={label} onChange={(e) => setLabel(e.target.value)} placeholder={`${flowchart.id} v${flowchart.version}`} />
          </div>
          {dirty && <div className="muted" style={{ fontSize: 12 }}>You have unsaved changes in the decisions table. A run uses the saved version.</div>}
          {!valid && <div className="dim" style={{ fontSize: 12 }}>Patients: whole number from 10 to 50,000. Seeds: up to five whole numbers.</div>}
          <div className="form-row">
            <button className="btn primary" disabled={!valid || busy} onClick={start} data-testid="start-run">{busy ? 'Starting…' : 'Run'}</button>
          </div>
          {err && <div className="error" role="alert">{err}</div>}
        </div>
      </section>

      {active.map((r) => (
        <section key={r.id} data-testid="run-progress">
          <div className="form-row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <span className="clamp2">{r.label || r.id}</span><span className="num muted">{Math.round(r.progress * 100)}%</span>
          </div>
          <div className="progress" role="progressbar" aria-valuenow={Math.round(r.progress * 100)} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${r.progress * 100}%` }} /></div>
          <div className="form-row" style={{ marginTop: 10 }}>
            <span className="dim" style={{ fontSize: 12 }}>{r.n.toLocaleString('en')} patients, {r.seeds.length} seed{r.seeds.length > 1 ? 's' : ''}</span>
            <span className="spacer" />
            <button className="btn small" onClick={() => cancel(r)}>Cancel</button>
          </div>
        </section>
      ))}

      <section style={{ flex: 1 }}>
        <h4 className="label">Run history</h4>
        {runsError && <div className="error">{runsError}</div>}
        {runs.length === 0 ? <div className="empty">No runs yet.</div> : (
          <div data-testid="run-history" className="stack" style={{ gap: 8 }}>
            {runs.map((r) => (
              <div key={r.id} className={`runrow ${selectedRun === r.id ? 'on' : ''}`} onClick={() => onSelectRun(selectedRun === r.id ? null : r.id)} role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') onSelectRun(selectedRun === r.id ? null : r.id) }}>
                <div className="form-row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
                  <div className="clamp2" title={r.label} style={{ fontWeight: 600 }}>{r.label || r.id}</div>
                  {r.status !== 'succeeded' && <span className={`pill ${r.status === 'failed' ? 'bad' : r.status === 'cancelled' ? 'warn' : 'run'}`}>{r.status}</span>}
                </div>
                <div className="dim" style={{ fontSize: 11.5 }}>{r.flowchart.id} v{r.flowchart.version} · {r.n.toLocaleString('en')} patients · {r.seeds.length} seed{r.seeds.length === 1 ? '' : 's'}{r.created_at ? ` · ${new Date(r.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}` : ''}</div>
                <div className="metrics">
                  <div><div className="label">On time</div><div className="num">{pct(r.metrics?.on_time_share)}</div></div>
                  <div><div className="label">Median days</div><div className="num">{days(r.metrics?.median_days)}</div></div>
                  <div><div className="label">Missed</div><div className="num">{r.metrics?.missed_cancers == null ? '–' : Math.round(r.metrics.missed_cancers)}</div></div>
                </div>
                {r.error && <div style={{ color: r.status === 'failed' ? 'var(--coral)' : 'var(--amber)', fontSize: 11.5 }}>{r.error}</div>}
              </div>
            ))}
          </div>
        )}
        <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>On time = treated within {world?.target_days ?? '?'} days of the clock start. Missed = cancers never treated.</div>
      </section>
    </>
  )
}

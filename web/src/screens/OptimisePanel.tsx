import { useCallback, useEffect, useMemo, useState } from 'react'
import { useApi } from '../ApiContext'
import type { ApplyResult, Comparison, CompareValue, Flowchart, Optimisation, Run, World } from '../api/types'
import { KIND_LABEL, toggleChange } from '../lib/optimise'

const pct = (v?: number | null) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const num1 = (v?: number | null) => (v == null ? '–' : v.toFixed(1))
const done = (s?: string) => s === 'succeeded' || s === 'failed' || s === 'cancelled'

interface Props {
  pid: string
  flowchart: Flowchart
  world: World | null
  /** open a flowchart version, optionally with a run selected (the screen reloads its flowchart list first) */
  onOpen: (fid: string, version: number, run: string | null) => void
  onRunsChanged: () => void
}

/** Optimise a flowchart version: start the search, follow it, pick changes, apply them, rerun on unseen patients, compare. */
export function OptimisePanel({ pid, flowchart, world, onOpen, onRunsChanged }: Props) {
  const api = useApi()
  const [n, setN] = useState(String(world?.default_n ?? 1000))
  const [maxChanges, setMaxChanges] = useState('4')
  const [opts, setOpts] = useState<Optimisation[]>([])
  const [opt, setOpt] = useState<Optimisation | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [applied, setApplied] = useState<ApplyResult | null>(null)
  const [runs, setRuns] = useState<{ before: Run | null; after: Run | null }>({ before: null, after: null })
  const [cmp, setCmp] = useState<Comparison | null>(null)
  const [cmpErr, setCmpErr] = useState<string | null>(null)

  const nNum = Number(n), mNum = Number(maxChanges)
  const valid = Number.isInteger(nNum) && nNum >= 100 && nNum <= 50000 && Number.isInteger(mNum) && mNum >= 1 && mNum <= 10

  const loadList = useCallback(async () => { try { setOpts(await api.listOptimisations(pid)) } catch (e) { setErr((e as Error).message) } }, [api, pid])
  useEffect(() => { void loadList() }, [loadList])

  const show = useCallback((o: Optimisation) => {
    setOpt(o); setApplied(null); setCmp(null); setCmpErr(null); setRuns({ before: null, after: null })
    setSelected(new Set((o.changes ?? []).map((c) => c.index)))
  }, [])

  // follow a running search once a second
  const optId = opt?.id
  const optStatus = opt?.status
  useEffect(() => {
    if (!optId || done(optStatus)) return
    let stop = false
    const h = window.setInterval(async () => {
      try {
        const o = await api.getOptimisation(pid, optId)
        if (stop) return
        if (done(o.status)) { show(o); void loadList() } else setOpt(o)
      } catch { /* keep trying; a transient error should not end the search in the UI */ }
    }, 1000)
    return () => { stop = true; window.clearInterval(h) }
  }, [api, pid, optId, optStatus, show, loadList])

  async function start() {
    if (!valid) return
    setBusy(true); setErr(null)
    try {
      const o = await api.startOptimisation(pid, { flowchart: { id: flowchart.id, version: flowchart.version }, n: nNum, max_changes: mNum })
      show({ ...o, changes: undefined }); void loadList()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  async function cancel() {
    if (!opt) return
    try { show(await api.cancelOptimisation(pid, opt.id)); void loadList() } catch (e) { setErr((e as Error).message) }
  }
  async function pick(id: string) {
    setErr(null)
    try { show(await api.getOptimisation(pid, id)) } catch (e) { setErr((e as Error).message) }
  }

  const changes = opt?.changes ?? []
  async function apply() {
    if (!opt || selected.size === 0) return
    setBusy(true); setErr(null)
    try {
      const all = selected.size === changes.length
      const r = await api.applyOptimisation(pid, opt.id, { ...(all ? {} : { accept: [...selected].sort((a, b) => a - b) }), rerun: true, label: `after ${selected.size} accepted change${selected.size === 1 ? '' : 's'}` })
      setApplied(r); setCmp(null); setCmpErr(null)
      onRunsChanged(); void loadList()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  // after an apply, wait for the two held-out runs and then compare them (same patients, so the difference is real)
  const appliedKey = applied?.run_id ?? null
  useEffect(() => {
    if (!applied?.run_id || !applied.baseline_run_id) return
    let stop = false
    const before = applied.baseline_run_id, after = applied.run_id
    const tick = async () => {
      try {
        const [b, a] = await Promise.all([api.getRun(pid, before), api.getRun(pid, after)])
        if (stop) return
        setRuns({ before: b, after: a })
        onRunsChanged()
        if (b.status === 'succeeded' && a.status === 'succeeded') {
          window.clearInterval(h)
          try { const c = await api.compareRuns(pid, before, after); if (!stop) setCmp(c) } catch (e) { if (!stop) setCmpErr((e as Error).message) }
        } else if (b.status === 'failed' || a.status === 'failed' || b.status === 'cancelled' || a.status === 'cancelled') {
          window.clearInterval(h)
          setCmpErr('A rerun did not finish, so there is nothing to compare.')
        }
      } catch { /* transient */ }
    }
    const h = window.setInterval(tick, 1500)
    void tick()
    return () => { stop = true; window.clearInterval(h) }
  }, [appliedKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const running = opt && !done(opt.status)
  const rerunProgress = useMemo(() => (runs.before && runs.after ? (runs.before.progress + runs.after.progress) / 2 : 0), [runs])
  const alreadyApplied = opt?.applied ?? []

  return (
    <>
      <section data-testid="optimise-panel">
        <h4 className="label">Optimise {flowchart.name} v{flowchart.version}</h4>
        <div className="stack">
          <div className="muted" style={{ fontSize: 12.5 }}>Searches for changes to the order of steps that bring treatment forward. The search uses one set of simulated patients; the numbers it reports come from other patients it never saw.</div>
          <div className="kv">
            <label className="dim" htmlFor="opt-n">Patients</label><input id="opt-n" className={`field num-in ${nNum >= 100 && nNum <= 50000 ? '' : 'bad'}`} style={{ width: 96 }} value={n} onChange={(e) => setN(e.target.value)} inputMode="numeric" />
            <label className="dim" htmlFor="opt-max">At most</label><span><input id="opt-max" className={`field num-in ${mNum >= 1 && mNum <= 10 ? '' : 'bad'}`} style={{ width: 56 }} value={maxChanges} onChange={(e) => setMaxChanges(e.target.value)} inputMode="numeric" /> <span className="dim">changes</span></span>
          </div>
          {!valid && <div className="dim" style={{ fontSize: 12 }}>Patients: 100 to 50,000. Changes: 1 to 10.</div>}
          <div className="form-row">
            <button className="btn primary" disabled={!valid || busy || !!running} onClick={start} data-testid="start-optimise">{busy && !opt ? 'Starting…' : 'Optimise'}</button>
            {opts.length > 0 && (
              <select className="field" aria-label="Earlier searches" value={opt?.id ?? ''} onChange={(e) => e.target.value && void pick(e.target.value)} style={{ maxWidth: 190 }}>
                <option value="">Earlier searches</option>
                {opts.map((o) => <option key={o.id} value={o.id}>{o.flowchart.id} v{o.flowchart.version} · {o.status}{o.summary?.n_changes != null ? ` · ${o.summary.n_changes} changes` : ''}</option>)}
              </select>
            )}
          </div>
          {err && <div className="error" role="alert">{err}</div>}
        </div>
      </section>

      {running && opt && (
        <section data-testid="optimise-progress">
          <div className="form-row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <span className="clamp2">{opt.message || (opt.status === 'queued' ? 'Waiting to start' : 'Searching')}</span><span className="num muted">{Math.round(opt.progress * 100)}%</span>
          </div>
          <div className="progress" role="progressbar" aria-valuenow={Math.round(opt.progress * 100)} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${opt.progress * 100}%` }} /></div>
          <div className="form-row" style={{ marginTop: 10 }}>
            <span className="dim" style={{ fontSize: 12 }}>A search can take a minute or more.</span><span className="spacer" />
            <button className="btn small" onClick={cancel}>Cancel</button>
          </div>
        </section>
      )}

      {opt && (opt.status === 'failed' || opt.status === 'cancelled') && (
        <section><div className={opt.status === 'failed' ? 'error' : 'muted'}>{opt.status === 'failed' ? `The search failed: ${opt.error ?? 'unknown error'}` : 'The search was cancelled.'}</div></section>
      )}

      {opt?.status === 'succeeded' && (
        <section data-testid="optimise-result">
          <h4 className="label">Result on patients the search never saw</h4>
          <div className="metrics" style={{ marginBottom: 8 }}>
            <div><div className="label">On time before</div><div className="num">{pct(opt.summary?.heldout_before)}</div></div>
            <div><div className="label">On time after</div><div className="num" style={{ color: 'var(--mint)' }}>{pct(opt.summary?.heldout_after)}</div></div>
            <div><div className="label">Median days</div><div className="num">{num1(opt.heldout?.before?.median_days_to_treatment)} → {num1(opt.heldout?.after?.median_days_to_treatment)}</div></div>
          </div>
          {opt.selection_optimism_pp != null && <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>On the patients used for the search the gain looked {opt.selection_optimism_pp.toFixed(1)} points larger than on the unseen ones. The unseen number is the one to trust.</div>}
          {opt.honesty && <div className="muted" style={{ fontSize: 12, marginBottom: 10 }} data-testid="honesty">{opt.honesty}</div>}

          {changes.length === 0 ? <div className="empty">The search found no change that helps and passes the safety checks.</div> : (
            <>
              <div className="form-row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
                <h4 className="label" style={{ margin: 0 }}>Suggested changes ({changes.length})</h4>
                <span className="form-row" style={{ gap: 6 }}>
                  <button className="btn small" onClick={() => setSelected(new Set(changes.map((c) => c.index)))}>All</button>
                  <button className="btn small" onClick={() => setSelected(new Set())}>None</button>
                </span>
              </div>
              <div className="stack" style={{ gap: 8 }} data-testid="optimise-changes">
                {changes.map((c) => {
                  const linked = (c.linked_with ?? []).length > 0
                  return (
                    <label key={c.index} className={`runrow ${selected.has(c.index) ? 'on' : ''}`} style={{ display: 'block', cursor: 'pointer' }}>
                      <div className="form-row" style={{ flexWrap: 'nowrap', alignItems: 'flex-start', gap: 8 }}>
                        <input type="checkbox" checked={selected.has(c.index)} onChange={() => setSelected((s) => toggleChange(changes, s, c.index))} aria-label={`Accept change ${c.index + 1}`} style={{ marginTop: 3 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600 }}>{c.label}</div>
                          <div className="dim" style={{ fontSize: 11.5, marginTop: 2 }}><span className="pill">{KIND_LABEL[c.kind] ?? c.kind}</span>{linked ? ' · must be accepted together with change ' + (c.linked_with ?? []).map((i) => i + 1).join(', ') : ''}</div>
                          {c.records_reading && <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{c.records_reading}</div>}
                          <div className="dim num" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.5 }}>
                            {c.predicted_days_saved != null && <div>Records suggest about {c.predicted_days_saved.toFixed(2)} days saved per patient</div>}
                            {c.train && <div>Search patients: on time {pct(c.train.on_time_before)} → {pct(c.train.on_time_after)}, median {num1(c.train.median_before)} → {num1(c.train.median_after)} d</div>}
                            {c.heldout_after_this_change && <div style={{ color: 'var(--text)' }}>Unseen patients, with this and the changes above: on time {pct(c.heldout_after_this_change.on_time)}, median {num1(c.heldout_after_this_change.median_days)} d</div>}
                          </div>
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            </>
          )}

          {(opt.blocked ?? []).length > 0 && (
            <div style={{ marginTop: 12 }} data-testid="optimise-blocked">
              <h4 className="label">Blocked by safety checks ({opt.blocked!.length})</h4>
              <ul className="muted" style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12 }}>
                {opt.blocked!.map((b, i) => <li key={i}>{String(b.label ?? b.target ?? 'A change')}{b.reason || b.message ? `: ${String(b.reason ?? b.message)}` : ''}</li>)}
              </ul>
            </div>
          )}

          {changes.length > 0 && (
            <div className="form-row" style={{ marginTop: 12 }}>
              <button className="btn primary" disabled={busy || selected.size === 0} onClick={apply} data-testid="apply-changes">{busy ? 'Applying…' : `Apply ${selected.size === changes.length ? 'all' : selected.size} as a new version and rerun`}</button>
            </div>
          )}
          {alreadyApplied.length > 0 && !applied && <div className="dim" style={{ fontSize: 12, marginTop: 8 }}>Applied before: {alreadyApplied.map((a) => `${a.accepted.length} change${a.accepted.length === 1 ? '' : 's'} as v${a.flowchart.version}`).join('; ')}.</div>}
        </section>
      )}

      {applied && (
        <section data-testid="optimise-compare">
          <h4 className="label">New version {applied.flowchart.version}: before and after</h4>
          {!cmp && !cmpErr && (
            <>
              <div className="muted" style={{ fontSize: 12.5, marginBottom: 6 }}>Running both versions on the same unseen patients…</div>
              <div className="progress"><div style={{ width: `${rerunProgress * 100}%` }} /></div>
            </>
          )}
          {cmpErr && <div className="error">{cmpErr}</div>}
          {cmp && <CompareTable cmp={cmp} />}
          <div className="form-row" style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => onOpen(applied.flowchart.id, applied.flowchart.version, applied.run_id ?? null)}>Open the new version</button>
            <button className="btn small" onClick={() => onOpen(applied.based_on.id, applied.based_on.version, applied.baseline_run_id ?? null)}>Open the old one</button>
          </div>
        </section>
      )}
    </>
  )
}

const ROWS: { key: string; label: string; fmt: (v: number | null) => string; better: 'up' | 'down' }[] = [
  { key: 'share_within_target', label: 'On time', fmt: pct, better: 'up' },
  { key: 'median_days_to_treatment', label: 'Median days to treatment', fmt: num1, better: 'down' },
  { key: 'median_days_to_diagnosis', label: 'Median days to diagnosis', fmt: num1, better: 'down' },
  { key: 'missed_cancers', label: 'Missed cancers', fmt: num1, better: 'down' },
  { key: 'tests_per_patient', label: 'Tests per patient', fmt: (v) => (v == null ? '–' : v.toFixed(3)), better: 'down' },
]

function tone(v: CompareValue | undefined, better: 'up' | 'down'): string | undefined {
  if (!v || v.delta == null || v.delta === 0) return undefined
  return (v.delta > 0) === (better === 'up') ? 'var(--mint)' : 'var(--coral)'
}

export function CompareTable({ cmp }: { cmp: Comparison }) {
  const groups = Object.entries(cmp.by_group ?? {}).filter(([, g]) => g.share_within_target?.a != null || g.share_within_target?.b != null)
  return (
    <div data-testid="compare-table">
      <table className="cmp" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
        <thead><tr className="label"><th style={{ textAlign: 'left' }}></th><th style={{ textAlign: 'right' }}>Before</th><th style={{ textAlign: 'right' }}>After</th></tr></thead>
        <tbody>
          {ROWS.map((r) => {
            const v = cmp.headline[r.key]
            if (!v) return null
            return <tr key={r.key}><td>{r.label}</td><td className="num" style={{ textAlign: 'right' }}>{r.fmt(v.a)}</td><td className="num" style={{ textAlign: 'right', color: tone(v, r.better) }}>{r.fmt(v.b)}</td></tr>
          })}
          {groups.map(([g, d]) => (
            <tr key={g}><td className="dim">On time, {g.replace(/_/g, ' ')}</td><td className="num" style={{ textAlign: 'right' }}>{pct(d.share_within_target.a)}</td><td className="num" style={{ textAlign: 'right', color: tone(d.share_within_target, 'up') }}>{pct(d.share_within_target.b)}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>{cmp.n.toLocaleString('en')} patients per seed, seeds {cmp.seeds.join(', ')}; both versions ran on the same simulated patients.</div>
    </div>
  )
}

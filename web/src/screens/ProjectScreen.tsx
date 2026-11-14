import { useCallback, useEffect, useMemo, useState } from 'react'
import { useApi } from '../ApiContext'
import type { Flowchart, FlowchartSummary, Problem, Project, World } from '../api/types'
import { FlowCanvas, STAGE_LABEL, stageOf } from '../graph/FlowCanvas'
import { allValid, applyDraft, draftFrom, isDirty } from '../lib/decisionDraft'
import type { Draft } from '../lib/decisionDraft'
import { go, replace } from '../lib/route'
import type { Route } from '../lib/route'
import { useRuns } from '../lib/useRuns'
import { DecisionsTable } from './DecisionsTable'
import { RunPanel } from './RunPanel'

type Tab = 'flowchart' | 'decisions'

export function ProjectScreen({ pid, route }: { pid: string; route: Route }) {
  const api = useApi()
  const [project, setProject] = useState<Project | null>(null)
  const [world, setWorld] = useState<World | null>(null)
  const [list, setList] = useState<FlowchartSummary[]>([])
  const [fc, setFc] = useState<Flowchart | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const { runs, reload: reloadRuns, error: runsError } = useRuns(api, pid)

  const tab: Tab = route.q.get('tab') === 'decisions' ? 'decisions' : 'flowchart'
  const fid = route.q.get('f')
  const ver = route.q.get('v')
  const selectedRun = route.q.get('run')
  const q = (over: Record<string, string | number | null>) => ({ f: fid, v: ver, tab: tab === 'flowchart' ? null : tab, run: selectedRun, ...over })
  const nav = (over: Record<string, string | number | null>) => go(`p/${pid}`, q(over))

  useEffect(() => {
    Promise.all([api.getProject(pid), api.getWorld(pid), api.listFlowcharts(pid)])
      .then(([p, w, l]) => { setProject(p); setWorld(w); setList(l) })
      .catch((e) => setError(e.message))
  }, [api, pid])

  // pick the flowchart and version from the address, defaulting to the first flowchart's latest version
  const cur = list.find((f) => f.id === fid) ?? list[0]
  const curVer = cur ? (ver && cur.versions.includes(Number(ver)) ? Number(ver) : cur.latest_version) : null
  useEffect(() => {
    if (!cur || curVer === null) return
    let live = true
    api.getFlowchart(pid, cur.id, curVer).then((d) => { if (live) { setFc(d); setSelected(null) } }).catch((e) => setError(e.message))
    return () => { live = false }
  }, [api, pid, cur?.id, curVer]) // eslint-disable-line react-hooks/exhaustive-deps

  const initial = useMemo(() => (fc ? draftFrom(fc) : null), [fc])
  const [draft, setDraft] = useState<Draft | null>(null)
  useEffect(() => setDraft(initial), [initial])
  const dirty = !!(initial && draft && isDirty(initial, draft))

  const [problems, setProblems] = useState<Problem[]>([])
  const [saving, setSaving] = useState(false)
  const save = useCallback(async () => {
    if (!fc || !initial || !draft || !cur) return
    setSaving(true); setProblems([]); setError(null)
    try {
      const doc = applyDraft(fc, initial, draft)
      const v = await api.validate(pid, doc)
      const errs = v.problems.filter((p) => p.severity === 'error')
      setProblems(v.problems)
      if (errs.length) return
      const saved = await api.saveFlowchart(pid, cur.id, doc)
      setList(await api.listFlowcharts(pid))
      go(`p/${pid}`, { f: cur.id, v: saved.version, tab: 'decisions', run: selectedRun })
    } catch (e) {
      const err = e as Error & { problems?: Problem[] }
      if (err.problems) setProblems(err.problems as Problem[]); else setError(err.message)
    } finally { setSaving(false) }
  }, [api, pid, fc, initial, draft, cur, selectedRun])

  if (error && !fc) return <div className="page"><div className="error">{error}</div><p><a href="#/">Back to projects</a></p></div>
  if (!fc || !cur || curVer === null || !draft || !world) return <div className="page"><div className="empty">Loading…</div></div>

  const sel = selected ? fc.nodes.find((n) => n.id === selected) : null
  const valid = allValid(draft)

  return (
    <>
      <div className="subbar">
        <a href="#/" onClick={(e) => { e.preventDefault(); go('') }} className="muted">‹ Projects</a>
        <strong>{project?.name}</strong>
        <span className="sep dim">/</span>
        <select className="field" aria-label="Flowchart" value={cur.id} onChange={(e) => nav({ f: e.target.value, v: null })}>
          {list.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <select className="field" aria-label="Version" value={curVer} onChange={(e) => nav({ v: e.target.value })}>
          {cur.versions.slice().reverse().map((v) => <option key={v} value={v}>version {v}{v === cur.latest_version ? ' (latest)' : ''}{cur.locked.includes(v) ? ' · has runs' : ''}</option>)}
        </select>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'flowchart'} className={`tab ${tab === 'flowchart' ? 'on' : ''}`} onClick={() => nav({ tab: null })}>Flowchart</button>
          <button role="tab" aria-selected={tab === 'decisions'} className={`tab ${tab === 'decisions' ? 'on' : ''}`} onClick={() => nav({ tab: 'decisions' })}>Decisions{dirty ? ' •' : ''}</button>
          <button role="tab" className="tab" disabled title="The dashboard report arrives with ticket M3-7">Report</button>
        </div>
        <span className="spacer" />
        <span className="dim" style={{ fontSize: 12 }}>{fc.nodes.length} steps · {fc.nodes.filter((n) => n.kind === 'decision').length} decisions{world.target_days ? ` · target ${world.target_days} days` : ''}</span>
      </div>

      {tab === 'flowchart' ? (
        <div className="workspace">
          <div className="canvas-wrap">
            <FlowCanvas flowchart={fc} world={world} selected={selected} onSelect={setSelected} />
          </div>
          <aside className="side" aria-label="Side panel">
            {sel && (
              <section data-testid="step-panel">
                <div className="label" style={{ marginBottom: 6 }}>{sel.kind === 'decision' ? 'Decision' : 'Step'}{stageOf(sel, world) ? ` · ${STAGE_LABEL[stageOf(sel, world)!] ?? stageOf(sel, world)}` : ''}</div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{sel.label}</div>
                <div className="kv" style={{ fontSize: 12.5 }}>
                  <span className="dim">Id</span><span className="mono">{sel.id}</span>
                  {sel.test && <><span className="dim">What happens</span><span className="mono">{sel.test}</span></>}
                  {sel.test && world.tests?.[sel.test]?.resource && <><span className="dim">Resource</span><span className="mono">{world.tests[sel.test].resource}</span></>}
                  {sel.when && <><span className="dim">Only if</span><span className="mono">{sel.when}</span></>}
                  {sel.outcome && <><span className="dim">Outcome</span><span>{sel.outcome}</span></>}
                </div>
                {sel.kind === 'decision' && (
                  <div style={{ marginTop: 10 }}>
                    <button className="btn small" onClick={() => nav({ tab: 'decisions' })}>Edit probabilities</button>
                  </div>
                )}
              </section>
            )}
            <RunPanel pid={pid} flowchart={fc} world={world} runs={runs} runsError={runsError} selectedRun={selectedRun}
              onSelectRun={(id) => replace(`p/${pid}`, q({ run: id }))} onChanged={reloadRuns} dirty={dirty} />
          </aside>
        </div>
      ) : (
        <>
          <div className="decisions-page">
            <DecisionsTable flowchart={fc} draft={draft} onChange={setDraft} selected={selected} onSelect={setSelected} />
          </div>
          <div className="savebar">
            <button className="btn primary" disabled={!dirty || !valid || saving} onClick={save} data-testid="save-version">{saving ? 'Saving…' : 'Save as new version'}</button>
            <button className="btn" disabled={!dirty} onClick={() => setDraft(initial)}>Discard changes</button>
            <span className="muted" style={{ fontSize: 12.5 }}>
              {!dirty ? `Nothing changed since version ${fc.version}.` : !valid ? 'Every row must add to 100, and a condition needs text.' : `Saves version ${cur.latest_version + 1} of "${cur.name}". Earlier versions stay as they were.`}
            </span>
            {fc.version !== cur.latest_version && <span className="pill warn">Editing an older version: saving makes a new latest version</span>}
            <span className="spacer" />
            {error && <span className="error" role="alert">{error}</span>}
            {problems.length > 0 && (
              <ul data-testid="problems" style={{ margin: 0, paddingLeft: 18, color: 'var(--coral)', fontSize: 12.5 }}>
                {problems.map((p, i) => <li key={i}>{p.node ? `${p.node}: ` : ''}{p.message}{p.hint ? ` ${p.hint}` : ''}</li>)}
              </ul>
            )}
          </div>
        </>
      )}
    </>
  )
}

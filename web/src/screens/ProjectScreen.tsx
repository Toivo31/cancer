import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useApi } from '../ApiContext'
import type { Flowchart, FlowchartSummary, Problem, Project, World } from '../api/types'
import { Clock } from '../graph/clock'
import { FlowCanvas, STAGE_LABEL, stageOf } from '../graph/FlowCanvas'
import { buildOverlay, LAYERS } from '../graph/layers'
import type { Layer } from '../graph/layers'
import { adjacency, patientPath, preparePatients } from '../graph/playback'
import { useFlow } from '../lib/useFlow'
import { PlaybackBar } from './PlaybackBar'
import { TimeLostPanel } from './TimeLostPanel'
import { TracePanel } from './TracePanel'
import { allValid, applyDraft, draftFrom, isDirty } from '../lib/decisionDraft'
import type { Draft } from '../lib/decisionDraft'
import { go, replace } from '../lib/route'
import type { Route } from '../lib/route'
import { useRuns } from '../lib/useRuns'
import { effectiveRun } from '../lib/runSelect'
import { DecisionsTable } from './DecisionsTable'
import { RunPanel } from './RunPanel'
import { OptimisePanel } from './OptimisePanel'
import { EditPanel } from './EditPanel'
import { DiffDialog } from './DiffDialog'
import { pushHistory, redoHistory, startHistory, undoHistory } from '../lib/history'
import type { History } from '../lib/history'

type Tab = 'flowchart' | 'decisions'

export function ProjectScreen({ pid, route }: { pid: string; route: Route }) {
  const api = useApi()
  const [project, setProject] = useState<Project | null>(null)
  const [world, setWorld] = useState<World | null>(null)
  const [list, setList] = useState<FlowchartSummary[]>([])
  const [fc, setFc] = useState<Flowchart | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const { runs, reload: reloadRuns, error: runsError, loaded: runsLoaded } = useRuns(api, pid)

  const tab: Tab = route.q.get('tab') === 'decisions' ? 'decisions' : 'flowchart'
  const fid = route.q.get('f')
  const ver = route.q.get('v')
  const selectedRun = route.q.get('run')
  const q = (over: Record<string, string | number | null>) => ({ f: fid, v: ver, tab: tab === 'flowchart' ? null : tab, run: selectedRun, layer: route.q.get('layer'), ...over })
  const nav = (over: Record<string, string | number | null>) => go(`p/${pid}`, q(over))

  useEffect(() => {
    // flowcharts in the order the template lists them, so the project opens on today's pathway (not the alphabetical first)
    Promise.all([api.getProject(pid), api.getWorld(pid), api.listFlowcharts(pid), api.templates().catch(() => [])])
      .then(([p, w, l, ts]) => {
        const order = ((ts as { id: string; flowcharts?: { id: string }[] }[]).find((t) => t.id === p.template)?.flowcharts ?? []).map((f) => f.id)
        const rank = (id: string) => { const i = order.indexOf(id); return i < 0 ? 999 : i }
        setProject(p); setWorld(w); setList(order.length ? l.slice().sort((a, b) => rank(a.id) - rank(b.id)) : l)
      })
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
      go(`p/${pid}`, { f: cur.id, v: saved.version, tab: 'decisions' })
    } catch (e) {
      const err = e as Error & { problems?: Problem[] }
      if (err.problems) setProblems(err.problems as Problem[]); else setError(err.message)
    } finally { setSaving(false) }
  }, [api, pid, fc, initial, draft, cur])

  // ---- edit mode: a working copy of the flowchart, checked by the validator as it changes ----
  const [editing, setEditing] = useState(false)
  const [hist, setHist] = useState<History<Flowchart> | null>(null)
  const editDoc = hist?.present ?? null
  const setEditDoc = useCallback((d: Flowchart | null) => setHist(d ? startHistory(d) : null), [])
  const [checkedDoc, setCheckedDoc] = useState<Flowchart | null>(null)
  const [editProblems, setEditProblems] = useState<Problem[]>([])
  const [checking, setChecking] = useState(false)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  useEffect(() => { setEditing(false); setEditDoc(null); setEditProblems([]); setEditError(null) }, [fc])
  const editDirty = !!(editing && editDoc && fc && JSON.stringify(editDoc) !== JSON.stringify(fc))
  useEffect(() => {
    if (!editing || !editDoc) return
    let live = true
    setChecking(true)
    const h = window.setTimeout(() => {
      api.validate(pid, editDoc).then((v) => { if (live) { setEditProblems(v.problems); setCheckedDoc(editDoc) } })
        .catch((e) => { const err = e as Error & { problems?: Problem[] }; if (live) { setEditProblems(err.problems ?? [{ severity: 'error', code: 'check_failed', message: err.message }]); setCheckedDoc(editDoc) } })
        .finally(() => { if (live) setChecking(false) })
    }, 400)
    return () => { live = false; window.clearTimeout(h) }
  }, [api, pid, editing, editDoc])
  // undo and redo with the keyboard while editing (inside a text field the browser's own undo keeps working)
  useEffect(() => {
    if (!editing) return
    const k = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'z') return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      e.preventDefault()
      setHist((h) => (h ? (e.shiftKey ? redoHistory(h) : undoHistory(h)) : h))
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [editing])
  const startEdit = () => { if (fc) { setEditDoc(JSON.parse(JSON.stringify(fc))); setEditing(true); setEditProblems([]) } }
  const stopEdit = () => { setEditing(false); setEditDoc(null); setEditProblems([]); setEditError(null) }
  const saveEdit = async () => {
    if (!editDoc || !cur) return
    setEditSaving(true); setEditError(null)
    try {
      const v = await api.validate(pid, editDoc)
      setEditProblems(v.problems)
      if (v.problems.some((x) => x.severity === 'error')) return
      const saved = await api.saveFlowchart(pid, cur.id, editDoc)
      setList(await api.listFlowcharts(pid))
      setEditing(false); setEditDoc(null)
      go(`p/${pid}`, { f: cur.id, v: saved.version })
    } catch (e) {
      const err = e as Error & { problems?: Problem[] }
      if (err.problems) setEditProblems(err.problems as Problem[]); else setEditError(err.message)
    } finally { setEditSaving(false) }
  }

  // a project just created from a template starts one default run, so the graph fills with patients without a click
  const autoStarted = useRef(false)
  useEffect(() => {
    if (route.q.get('autorun') !== '1' || autoStarted.current || !runsLoaded || !fc || !cur || !world) return
    autoStarted.current = true
    if (runs.length > 0) { replace(`p/${pid}`, { f: cur.id, v: curVer, run: runs[0].id }); return }
    api.startRun(pid, { flowchart: { id: fc.id, version: fc.version }, n: world.default_n ?? 1000, seeds: [301], decision_policy: null, label: `${fc.id} v${fc.version}, default run` })
      .then((r) => { replace(`p/${pid}`, { f: fc.id, v: fc.version, run: r.run_id }); void reloadRuns() })
      .catch(() => replace(`p/${pid}`, { f: cur.id, v: curVer }))
  }, [route.q, runsLoaded, fc, cur, world, runs, api, pid, curVer, reloadRuns])

  // ---- run layers: the selected run's flow document drawn on the same canvas ----
  const runObj = effectiveRun(runs, selectedRun, cur?.id ?? null, curVer)
  const effRun = runObj?.id ?? null
  const { flow, error: flowError, loading: flowLoading } = useFlow(api, pid, effRun, runObj?.status === 'succeeded')
  const layerQ = route.q.get('layer') as Layer | null
  const layer: Layer = flow ? (layerQ && LAYERS.some((l) => l.id === layerQ) ? layerQ : 'flow') : 'structure'
  const labelOf = useCallback((id: string) => fc?.nodes.find((n) => n.id === id)?.label ?? flow?.graph.nodes.find((n) => n.id === id)?.label ?? id, [fc, flow])
  const overlay = useMemo(() => (fc && flow ? buildOverlay(fc, flow, layer, labelOf) : null), [fc, flow, layer, labelOf])
  const clock = useMemo(() => (flow ? new Clock(flow.cohort.horizon) : null), [flow])
  useEffect(() => { if (!clock) return; clock.play(); return () => clock.dispose() }, [clock])
  const pps = useMemo(() => (flow && fc ? preparePatients(flow, new Set(fc.nodes.map((n) => n.id))) : []), [flow, fc])
  const adj = useMemo(() => adjacency(fc?.edges ?? []), [fc])
  const [patientIdx, setPatientIdx] = useState<number | null>(null)
  const [panelOpen, setPanelOpen] = useState(true)
  const [compareWith, setCompareWith] = useState<number | null>(null)
  const [sideTab, setSideTab] = useState<'run' | 'time' | 'patient' | 'optimise'>('run')
  useEffect(() => { setPatientIdx(null) }, [flow])
  const pickPatient = useCallback((idx: number | null) => { setPatientIdx(idx); if (idx !== null) setSideTab('patient') }, [])
  const patient = patientIdx !== null ? pps.find((p) => p.idx === patientIdx) ?? null : null
  const path = useMemo(() => (patient ? patientPath(patient, adj) : null), [patient, adj])
  const transit = flow ? Math.max(0.5, flow.cohort.horizon / 110) : 1
  const selectRun = (id: string | null) => {
    const r = runs.find((x) => x.id === id)
    replace(`p/${pid}`, q({ run: id, ...(r ? { f: r.flowchart.id, v: r.flowchart.version } : {}) }))
  }

  // after the optimiser saved a new version: refresh the list of versions, then show it with its run
  const openVersion = useCallback(async (fid: string, version: number, run: string | null) => {
    try { setList(await api.listFlowcharts(pid)) } catch { /* the address still works */ }
    go(`p/${pid}`, { f: fid, v: version, run })
  }, [api, pid])

  if (error && !fc) return <div className="page"><div className="error" role="alert">Could not open this project: {error}</div><p><button className="btn" onClick={() => window.location.reload()}>Try again</button> <a href="#/" style={{ marginLeft: 10 }}>Back to projects</a></p></div>
  if (!fc || !cur || curVer === null || !draft || !world) return <div className="page"><div className="empty" role="status">Loading the project…</div></div>

  const shown = editing && editDoc ? editDoc : fc
  const sel = selected ? fc.nodes.find((n) => n.id === selected) : null
  const valid = allValid(draft)

  return (
    <>
      <div className="subbar">
        <a href="#/" onClick={(e) => { e.preventDefault(); go('') }} className="muted">‹ Projects</a>
        <strong className="ellipsis" style={{ maxWidth: 260 }} title={project?.name}>{project?.name}</strong>
        <span className="sep dim">/</span>
        <select className="field ellipsis" style={{ maxWidth: 280 }} aria-label="Flowchart" value={cur.id} onChange={(e) => nav({ f: e.target.value, v: null, run: null })}>
          {list.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <select className="field" aria-label="Version" value={curVer} onChange={(e) => nav({ v: e.target.value, run: null })}>
          {cur.versions.slice().reverse().map((v) => <option key={v} value={v}>version {v}{v === cur.latest_version ? ' (latest)' : ''}{cur.locked.includes(v) ? ' · has runs' : ''}</option>)}
        </select>
        {cur.versions.length > 1 && (
          <select className="field" aria-label="Compare with another version" value="" onChange={(e) => e.target.value && setCompareWith(Number(e.target.value))} title="Draw this version next to another one and mark what changed" style={{ maxWidth: 150 }}>
            <option value="">Compare with…</option>
            {cur.versions.filter((v) => v !== curVer).reverse().map((v) => <option key={v} value={v}>version {v}</option>)}
          </select>
        )}
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'flowchart'} className={`tab ${tab === 'flowchart' ? 'on' : ''}`} onClick={() => nav({ tab: null })}>Flowchart</button>
          <button role="tab" aria-selected={tab === 'decisions'} className={`tab ${tab === 'decisions' ? 'on' : ''}`} onClick={() => nav({ tab: 'decisions' })}>Decisions{dirty ? ' •' : ''}</button>
        </div>
        <span className="spacer" />
        <span className="dim" style={{ fontSize: 12 }}>{fc.nodes.length} steps · {fc.nodes.filter((n) => n.kind === 'decision').length} decisions{world.target_days ? ` · target ${world.target_days} days` : ''}</span>
      </div>

      {error && tab === 'flowchart' && <div className="error" role="alert" style={{ margin: '8px 20px', display: 'flex', gap: 10, alignItems: 'center' }}><span style={{ flex: 1 }}>{error}</span><button className="btn small" onClick={() => setError(null)}>Dismiss</button></div>}
      {tab === 'flowchart' ? (
        <div className="workspace">
          <div className="canvas-col">
            <div className="canvas-wrap" style={{ flex: 1 }}>
              <FlowCanvas layoutKey={`${pid}/${cur.id}`} refit={`${panelOpen ? 'p' : 'c'}${flow && layer !== 'structure' ? 'b' : ''}`} flowchart={shown} world={world} selected={selected} onSelect={setSelected} overlay={editing ? null : overlay} path={editing ? null : path}
                playback={clock && layer !== 'structure' && !editing ? { clock, patients: pps, transit, selectedPatient: patientIdx, onPick: pickPatient } : null} />
              <button className="btn small panelbtn" onClick={() => setPanelOpen((o) => !o)} aria-pressed={panelOpen} title={panelOpen ? 'Hide the side panel for more room' : 'Show the side panel'}>{panelOpen ? 'Hide panel ›' : '‹ Panel'}</button>
              {!editing && <button className="btn small optbtn" onClick={() => { setPanelOpen(true); setSideTab('optimise') }} title="Search for changes to the order of steps that bring treatment forward" data-testid="open-optimise">Optimise…</button>}
              <button className={`btn small editbtn ${editing ? 'primary' : ''}`} onClick={() => (editing ? stopEdit() : startEdit())} aria-pressed={editing} title={editing ? 'Leave edit mode (unsaved changes are dropped)' : 'Change steps and connections and save them as a new version'}>{editing ? 'Done editing' : 'Edit'}</button>
              {flow && !editing && (
                <>
                  <div className="toolbar" role="tablist" aria-label="Layers">
                    {LAYERS.map((l) => <button key={l.id} role="tab" aria-selected={layer === l.id} className={`tab ${layer === l.id ? 'on' : ''}`} onClick={() => nav({ layer: l.id })}>{l.label}</button>)}
                  </div>
                  <div className="toolhint"><strong>{runObj ? runObj.label || runObj.id : ''}</strong> · {overlay?.legend || LAYERS.find((l) => l.id === layer)?.hint}</div>
                </>
              )}
              {!flow && !flowLoading && !flowError && !editing && runsLoaded && <div className="toolhint" style={{ top: 12 }} data-testid="no-run-hint">No finished run of this version yet. Press Run in the side panel to see patients flow through it, or Optimise to search for improvements.</div>}
              {!flow && (flowLoading || flowError) && <div className="toolhint" style={{ top: 12 }}>{flowLoading ? 'Loading the run…' : flowError}</div>}
            </div>
            {flow && clock && layer !== 'structure' && !editing && <PlaybackBar clock={clock} patients={pps} sampleLabel={`Dots: ${pps.length} sampled patients of ${flow.totals.n.toLocaleString('en')}. Counts and colours use everyone.`} />}
          </div>
          {panelOpen && editing && editDoc && <aside className="side" aria-label="Side panel">
            <EditPanel doc={editDoc} world={world} selected={selected} onSelect={setSelected} onChange={(d, key) => setHist((h) => (h ? pushHistory(h, d, key) : h))}
              canUndo={!!hist?.past.length} canRedo={!!hist?.future.length} onUndo={() => setHist((h) => (h ? undoHistory(h) : h))} onRedo={() => setHist((h) => (h ? redoHistory(h) : h))}
              problems={editProblems} checking={checking || checkedDoc !== editDoc} dirty={editDirty} saving={editSaving}
              baseVersion={fc.version} latestVersion={cur.latest_version} flowchartName={cur.name} onSave={saveEdit} onDiscard={() => setHist((h) => (h ? pushHistory(h, JSON.parse(JSON.stringify(fc)) as Flowchart) : h))} />
            {editError && <div className="error" role="alert">{editError}</div>}
          </aside>}
          {panelOpen && !editing && <aside className="side" aria-label="Side panel">
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
                  {flow?.steps[sel.id] && <><span className="dim">Patients</span><span className="num">{flow.steps[sel.id].n.toLocaleString('en')}</span></>}
                  {flow?.steps[sel.id]?.wait_median != null && <><span className="dim">Median wait</span><span className="num">{flow.steps[sel.id].wait_median!.toFixed(1)} d</span></>}
                </div>
                {sel.kind === 'decision' && (
                  <div style={{ marginTop: 10 }}>
                    <button className="btn small" onClick={() => nav({ tab: 'decisions' })}>Edit probabilities</button>
                  </div>
                )}
              </section>
            )}
            {(
              <div className="tabs" role="tablist">
                {([['run', 'Run'], ['optimise', 'Optimise'], ...(flow ? [['time', 'Where time is lost'], ['patient', 'Patient']] : [])] as ['run' | 'time' | 'patient' | 'optimise', string][]).map(([id, t]) => <button key={id} role="tab" aria-selected={sideTab === id} className={`tab ${sideTab === id ? 'on' : ''}`} onClick={() => setSideTab(id)}>{t}</button>)}
              </div>
            )}
            {flow && sideTab === 'time' && <TimeLostPanel flow={flow} selected={selected} onSelect={setSelected} />}
            {flow && sideTab === 'patient' && <TracePanel flow={flow} pp={patient} labelOf={labelOf} patients={pps} onPick={pickPatient} />}
            {sideTab === 'optimise' && (
              <OptimisePanel pid={pid} flowchart={fc} world={world} onRunsChanged={reloadRuns} onOpen={openVersion} />
            )}
            {((!flow && sideTab !== 'optimise') || sideTab === 'run') && (
              <RunPanel pid={pid} flowchart={fc} world={world} runs={runs} runsError={runsError} selectedRun={effRun}
                onSelectRun={selectRun} onChanged={reloadRuns} dirty={dirty} />
            )}
          </aside>}
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
      {compareWith !== null && (
        <DiffDialog pid={pid} onClose={() => setCompareWith(null)}
          a={{ fid: cur.id, version: Math.min(compareWith, curVer), label: `Version ${Math.min(compareWith, curVer)}` }}
          b={{ fid: cur.id, version: Math.max(compareWith, curVer), label: `Version ${Math.max(compareWith, curVer)}` }} />
      )}
    </>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { useApi } from '../ApiContext'
import type { Project, Template } from '../api/types'
import { go } from '../lib/route'

export function Projects() {
  const api = useApi()
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [templates, setTemplates] = useState<Template[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [name, setName] = useState('')

  const load = useCallback(() => {
    api.listProjects().then(setProjects).catch((e) => setError(e.message))
    api.templates().then(setTemplates).catch((e) => setError(e.message))
  }, [api])
  useEffect(load, [load])

  async function create(t: Template) {
    setBusy(t.id); setError(null)
    try {
      const p = await api.createProject(name.trim() || t.name, t.id)
      go(`p/${p.id}`, { autorun: 1 })
    } catch (e) { setError((e as Error).message); setBusy(null) }
  }
  async function remove(p: Project) {
    if (!window.confirm(`Delete project "${p.name}" and its runs?`)) return
    await api.deleteProject(p.id).catch((e) => setError(e.message))
    load()
  }

  return (
    <div className="page">
      <div className="eyebrow">Care pathway simulator</div>
      <h1>Projects</h1>
      <p className="lead">A project holds one world, its flowcharts, runs and decisions. Start from a template, change what the decision points do, and run the same synthetic patients through the flowchart.</p>
      {error && <div className="error" role="alert">{error}</div>}

      <h2 className="label section-title">Start from a template</h2>
      <div className="form-row" style={{ marginBottom: 12 }}>
        <label className="dim" htmlFor="pname">Project name</label>
        <input id="pname" className="field" style={{ width: 300 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="Same as the template" />
      </div>
      <div className="grid">
        {templates.map((t) => (
          <div key={t.id} className="card tile" data-testid={`template-${t.id}`}>
            <h3>{t.name}</h3>
            <p>{t.description}</p>
            <div className="row"><button className="btn primary" disabled={busy !== null} onClick={() => create(t)}>{busy === t.id ? 'Creating…' : 'Create project'}</button></div>
          </div>
        ))}
        {templates.length === 0 && !error && <div className="empty">Loading templates…</div>}
      </div>

      <h2 className="label section-title">Your projects</h2>
      {projects === null ? <div className="empty">Loading…</div> : projects.length === 0 ? (
        <div className="empty">No projects yet. Create one from a template above.</div>
      ) : (
        <div className="grid">
          {projects.map((p) => (
            <div key={p.id} className="card tile" data-testid="project-tile">
              <h3>{p.name}</h3>
              <p className="dim">{p.template ? `From template: ${templates.find((t) => t.id === p.template)?.name ?? p.template}` : 'Blank'}{p.created_at ? ` · ${new Date(p.created_at).toLocaleDateString('en-GB')}` : ''}</p>
              <div className="row">
                <button className="btn" onClick={() => go(`p/${p.id}`)}>Open</button>
                <button className="btn small danger" onClick={() => remove(p)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

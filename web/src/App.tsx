import { useEffect, useState } from 'react'
import { chooseApi } from './api'
import type { Api } from './api'
import { ApiCtx } from './ApiContext'
import { go, useRoute } from './lib/route'
import { Projects } from './screens/Projects'
import { ProjectScreen } from './screens/ProjectScreen'

export function App() {
  const [state, setState] = useState<{ api: Api; reason: string | null } | null>(null)
  const route = useRoute()
  useEffect(() => { chooseApi().then(setState) }, [])
  if (!state) return <div className="app"><div className="topbar"><span className="brand">Pathway <b>platform</b></span></div></div>
  const { api, reason } = state
  const onProject = route.path[0] === 'p' && route.path[1]
  return (
    <ApiCtx.Provider value={api}>
      <div className="app">
        <header className="topbar">
          <a className="brand" href="#/" onClick={(e) => { e.preventDefault(); go('') }}>Pathway <b>platform</b></a>
          <div className="spacer" />
          {reason && <span className="badge" title={reason}>{api.kind === 'mock' ? 'Demo data' : 'Service'}</span>}
          {api.kind === 'mock' && (
            <a className="dim" style={{ fontSize: 12 }} href="#/" onClick={(e) => { e.preventDefault(); localStorage.removeItem('pathway-api-mode'); window.location.search = '?mock=0'; }}>try the service</a>
          )}
        </header>
        <div className="main">{onProject ? <ProjectScreen key={route.path[1]} pid={route.path[1]} route={route} /> : <Projects />}</div>
      </div>
    </ApiCtx.Provider>
  )
}

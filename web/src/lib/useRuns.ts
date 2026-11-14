import { useCallback, useEffect, useRef, useState } from 'react'
import type { Api } from '../api'
import type { Run } from '../api/types'

const ACTIVE = (r: Run) => r.status === 'queued' || r.status === 'running'

/** Runs of a project. While any run is active, polls its job once a second (spec 03) and refreshes the list when it ends. */
export function useRuns(api: Api, pid: string) {
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const runsRef = useRef(runs)
  runsRef.current = runs

  const reload = useCallback(async () => {
    try { setRuns(await api.listRuns(pid)); setError(null) } catch (e) { setError((e as Error).message) } finally { setLoaded(true) }
  }, [api, pid])
  useEffect(() => { void reload() }, [reload])

  const anyActive = runs.some(ACTIVE)
  useEffect(() => {
    if (!anyActive) return
    let stop = false
    const tick = async () => {
      const active = runsRef.current.filter(ACTIVE)
      let ended = false
      const upd = new Map<string, { progress: number; message?: string }>()
      await Promise.all(active.map(async (r) => {
        if (!r.job_id) { ended = true; return }
        try {
          const j = await api.getJob(r.job_id)
          upd.set(r.id, { progress: j.progress, message: j.message })
          if (j.state !== 'queued' && j.state !== 'running') ended = true
        } catch { /* keep polling; a transient error should not end the run in the UI */ }
      }))
      if (stop) return
      if (ended) await reload()
      else setRuns((rs) => rs.map((r) => (upd.has(r.id) ? { ...r, progress: upd.get(r.id)!.progress } : r)))
    }
    const h = window.setInterval(tick, 1000)
    return () => { stop = true; window.clearInterval(h) }
  }, [anyActive, api, reload])

  return { runs, reload, error, loaded }
}

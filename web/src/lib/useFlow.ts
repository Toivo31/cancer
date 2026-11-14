import { useEffect, useState } from 'react'
import type { Api } from '../api'
import type { FlowData } from '../api/types'

const cache = new Map<string, FlowData>()

/** The flow document of a finished run (per-step counts, waits, queues, decisions and a sampled cohort for playback). */
export function useFlow(api: Api, pid: string, runId: string | null, ready: boolean) {
  const [flow, setFlow] = useState<FlowData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    setError(null)
    if (!runId || !ready) { setFlow(null); return }
    const key = `${api.kind}/${pid}/${runId}`
    const hit = cache.get(key)
    if (hit) { setFlow(hit); return }
    let live = true
    setLoading(true); setFlow(null)
    api.getFlow(pid, runId)
      .then((f) => { cache.set(key, f); if (live) setFlow(f) })
      .catch((e) => { if (live) setError(e.message) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [api, pid, runId, ready])
  return { flow, error, loading }
}

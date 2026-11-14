import { useEffect, useRef, useState } from 'react'
import { useApi } from '../ApiContext'
import type { Flowchart } from '../api/types'
import { DiffView } from '../graph/DiffView'

interface Ref { fid: string; version: number; label?: string }
interface Props { pid: string; a: Ref; b: Ref; onClose: () => void }

/** A full-width overlay that loads two versions of a flowchart and draws them side by side with the differences marked. */
export function DiffDialog({ pid, a, b, onClose }: Props) {
  const api = useApi()
  const [docs, setDocs] = useState<[Flowchart, Flowchart] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    let live = true
    setDocs(null); setErr(null)
    Promise.all([api.getFlowchart(pid, a.fid, a.version), api.getFlowchart(pid, b.fid, b.version)])
      .then((d) => { if (live) setDocs(d) }).catch((e) => { if (live) setErr((e as Error).message) })
    return () => { live = false }
  }, [api, pid, a.fid, a.version, b.fid, b.version])
  useEffect(() => {
    closeRef.current?.focus()
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  const name = (r: Ref) => r.label ?? `${r.fid} v${r.version}`
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Compare two versions" data-testid="diff-dialog" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="dialog wide">
        <div className="form-row" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>What changed: {name(a)} → {name(b)}</h3>
          <span className="spacer" />
          <button ref={closeRef} className="btn small" onClick={onClose}>Close</button>
        </div>
        {err && <div className="error" role="alert">Could not load the two versions: {err}</div>}
        {!err && !docs && <div className="empty">Loading both versions…</div>}
        {docs && <DiffView a={docs[0]} b={docs[1]} labelA={name(a)} labelB={name(b)} />}
      </div>
    </div>
  )
}

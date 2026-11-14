import { useEffect, useState } from 'react'

export interface Route { path: string[]; q: URLSearchParams }

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, '')
  const [p, qs] = h.split('?')
  return { path: p.split('/').filter(Boolean), q: new URLSearchParams(qs ?? '') }
}

export function useRoute(): Route {
  const [r, setR] = useState(() => parseHash(window.location.hash))
  useEffect(() => {
    const f = () => setR(parseHash(window.location.hash))
    window.addEventListener('hashchange', f)
    return () => window.removeEventListener('hashchange', f)
  }, [])
  return r
}

export function go(path: string, q?: Record<string, string | number | null | undefined>) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(q ?? {})) if (v !== null && v !== undefined && v !== '') qs.set(k, String(v))
  const s = qs.toString()
  window.location.hash = `#/${path}${s ? '?' + s : ''}`
}

export function replace(path: string, q?: Record<string, string | number | null | undefined>) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(q ?? {})) if (v !== null && v !== undefined && v !== '') qs.set(k, String(v))
  const s = qs.toString()
  window.history.replaceState(null, '', `#/${path}${s ? '?' + s : ''}`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}

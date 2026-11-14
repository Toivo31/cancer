// A view-only layout: where the user dragged and how big they made each step box, kept per flowchart in the
// browser. It never changes the flowchart itself.
export interface ViewLayout { pos: Record<string, { x: number; y: number }>; size: Record<string, { w: number; h: number }> }

export const emptyView = (): ViewLayout => ({ pos: {}, size: {} })
export const isEmptyView = (v: ViewLayout) => !Object.keys(v.pos).length && !Object.keys(v.size).length
const storageKey = (k: string) => `pathway:view-layout:${k}`
const num = (v: unknown) => typeof v === 'number' && Number.isFinite(v)

export function loadView(key: string): ViewLayout {
  try {
    const raw = window.localStorage.getItem(storageKey(key))
    if (!raw) return emptyView()
    const o = JSON.parse(raw) as Partial<ViewLayout>
    const v = emptyView()
    for (const [id, p] of Object.entries(o.pos ?? {})) if (p && num(p.x) && num(p.y)) v.pos[id] = { x: p.x, y: p.y }
    for (const [id, s] of Object.entries(o.size ?? {})) if (s && num(s.w) && num(s.h)) v.size[id] = { w: s.w, h: s.h }
    return v
  } catch { return emptyView() }
}

export function saveView(key: string, v: ViewLayout): void {
  try {
    if (isEmptyView(v)) window.localStorage.removeItem(storageKey(key))
    else window.localStorage.setItem(storageKey(key), JSON.stringify(v))
  } catch { /* storage unavailable or full: the layout then lasts for this visit only */ }
}

/** Boxes after the user's moves and resizes (`moved` = steps whose position changed); ids that are not in `base` (the structure changed) are ignored. */
export function applyView<B extends { x: number; y: number; w: number; h: number }>(base: Record<string, B>, v: ViewLayout): { boxes: Record<string, B>; moved: Set<string> } {
  const boxes: Record<string, B> = {}
  const moved = new Set<string>()
  for (const [id, b] of Object.entries(base)) {
    const p = v.pos[id], s = v.size[id]
    if (p) moved.add(id)
    boxes[id] = p || s ? { ...b, ...(p ?? {}), ...(s ? { w: s.w, h: s.h } : {}) } : b
  }
  return { boxes, moved }
}

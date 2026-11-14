// Undo and redo for one edit session. Pure, so it can be tested without a screen.
export interface History<T> { past: T[]; present: T; future: T[]; /** key of the last coalescable edit and when it happened */ last?: { key: string; at: number } }

export const startHistory = <T,>(doc: T): History<T> => ({ past: [], present: doc, future: [] })

const LIMIT = 100
const COALESCE_MS = 1200

/** Record a new document. Consecutive edits with the same `key` inside a short time (typing in one field) become one undo step. */
export function pushHistory<T>(h: History<T>, next: T, key?: string, now = Date.now()): History<T> {
  if (next === h.present) return h
  const merge = !!key && !!h.last && h.last.key === key && now - h.last.at < COALESCE_MS && h.past.length > 0
  const past = merge ? h.past : [...h.past, h.present].slice(-LIMIT)
  return { past, present: next, future: [], last: key ? { key, at: now } : undefined }
}

export function undoHistory<T>(h: History<T>): History<T> {
  if (!h.past.length) return h
  return { past: h.past.slice(0, -1), present: h.past[h.past.length - 1], future: [h.present, ...h.future], last: undefined }
}

export function redoHistory<T>(h: History<T>): History<T> {
  if (!h.future.length) return h
  return { past: [...h.past, h.present], present: h.future[0], future: h.future.slice(1), last: undefined }
}

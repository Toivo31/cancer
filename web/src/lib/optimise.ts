import type { OptChange } from '../api/types'

/** The changes that must be accepted together with `i` (it and everything linked to it, directly or through others). */
export function linkedGroup(changes: OptChange[], i: number): number[] {
  const by = new Map(changes.map((c) => [c.index, c]))
  const seen = new Set<number>([i])
  const q = [i]
  while (q.length) {
    const u = q.pop()!
    for (const v of by.get(u)?.linked_with ?? []) if (!seen.has(v)) { seen.add(v); q.push(v) }
    for (const c of changes) if ((c.linked_with ?? []).includes(u) && !seen.has(c.index)) { seen.add(c.index); q.push(c.index) }
  }
  return [...seen].sort((a, b) => a - b)
}

/** Tick or untick one change, taking its linked partners with it so the selection can always be applied. */
export function toggleChange(changes: OptChange[], selected: Set<number>, i: number): Set<number> {
  const group = linkedGroup(changes, i)
  const next = new Set(selected)
  const on = !selected.has(i)
  for (const g of group) { if (on) next.add(g); else next.delete(g) }
  return next
}

export const KIND_LABEL: Record<string, string> = {
  detach: 'Skip a step', relax: 'Run in parallel', standardise: 'Standardise a decision', fast_track: 'Fast track',
}

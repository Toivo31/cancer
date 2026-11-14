import type { Flowchart, FlowNode, StubPoint } from '../api/types'
import { fractions, fromPercent, normalisePct, parsePct, rowOk, sumPct, toPercent } from './probs'

export interface RowDraft { when: string | null; vals: string[] }
export interface PointDraft { id: string; options: string[]; unset: boolean; source: string; rows: RowDraft[] }
export interface Draft { mode: string; points: PointDraft[] }

export function optionsOf(fc: Flowchart, n: FlowNode): string[] {
  if (n.options?.length) return n.options
  return fc.edges.filter((e) => e.type === 'option' && e.from === n.id).sort((a, b) => (a.index ?? 0) - (b.index ?? 0)).map((e) => e.to)
}

const fmt = (x: number) => String(x)

function rowFrom(options: string[], probs: Record<string, number> | undefined, when: string | null): RowDraft {
  const pct = probs ? options.map((o) => toPercent(probs[o] ?? 0)) : normalisePct(options.map(() => 1))
  return { when, vals: pct.map(fmt) }
}

export function draftFrom(fc: Flowchart): Draft {
  const points: PointDraft[] = fc.nodes.filter((n) => n.kind === 'decision').map((n) => {
    const options = optionsOf(fc, n)
    const pt: StubPoint | undefined = fc.decision_policy.points[n.id]
    const unset = !pt || !pt.default
    return {
      id: n.id, options, unset, source: pt?.source ?? (unset ? '' : 'assumption'),
      rows: [rowFrom(options, pt?.default, null), ...(pt?.rules ?? []).map((r) => rowFrom(options, r.probs, r.when))],
    }
  })
  return { mode: String(fc.decision_policy.mode ?? 'sample'), points }
}

export const rowNumbers = (r: RowDraft) => r.vals.map(parsePct)
export const rowTotal = (r: RowDraft) => sumPct(rowNumbers(r))
export const rowValid = (r: RowDraft) => rowOk(rowNumbers(r)) && (r.when === null || r.when.trim() !== '')

export function pointChanged(a: PointDraft, b: PointDraft): boolean {
  return JSON.stringify(a.rows.map((r) => [r.when, rowNumbers(r)])) !== JSON.stringify(b.rows.map((r) => [r.when, rowNumbers(r)]))
}

export function isDirty(initial: Draft, now: Draft): boolean {
  return initial.mode !== now.mode || now.points.some((p, i) => pointChanged(initial.points[i], p))
}

export function allValid(d: Draft): boolean {
  return d.points.every((p) => p.rows.every(rowValid))
}

/** The flowchart document with the draft's tables stored in `decision_policy` (unchanged points are left byte-for-byte). */
export function applyDraft(fc: Flowchart, initial: Draft, now: Draft): Flowchart {
  const doc: Flowchart = JSON.parse(JSON.stringify(fc))
  doc.decision_policy.mode = now.mode
  now.points.forEach((p, i) => {
    const changed = pointChanged(initial.points[i], p)
    if (!changed) return
    const toProbs = (r: RowDraft) => fractions(p.options, rowNumbers(r).map((v) => v ?? 0))
    const [def, ...rules] = p.rows
    const old = fc.decision_policy.points[p.id]
    const src = old?.source && !old.source.startsWith('user edit') ? `user edit (was ${old.source})` : old?.source ?? 'user edit'
    doc.decision_policy.points[p.id] = {
      ...(old ?? {}),
      default: toProbs(def),
      ...(rules.length ? { rules: rules.map((r) => ({ when: (r.when ?? '').trim(), probs: toProbs(r) })) } : {}),
      source: src,
    }
    if (!rules.length) delete doc.decision_policy.points[p.id].rules
  })
  return doc
}

export { fromPercent }

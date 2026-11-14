import type { Flowchart, FlowNode, StubPoint } from '../api/types'
import { fractions, fromPercent, normalisePct, parsePct, rowOk, sumPct, toPercent } from './probs'

export interface RowDraft { when: string | null; vals: string[]; /** a fixed choice from an older document: shown, not editable */ fixed?: boolean }
export interface PointDraft { id: string; options: string[]; unset: boolean; source: string; legacy: boolean; rows: RowDraft[] }
export interface Draft { mode: string; /** the older 'rule' backend samples its own shares; the mode switch does not apply */ ruleBackend: boolean; points: PointDraft[] }

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
    // two stored forms: tables (default + rules with probs) and the older rule form (mix + rules that choose)
    const legacy = !!pt && (!!pt.mix || (pt.rules ?? []).some((r) => r.choose !== undefined && !r.probs) || (typeof pt.default === 'string'))
    const onehot = (o: string) => Object.fromEntries(options.map((x) => [x, x === o ? 1 : 0]))
    const base: Record<string, number> | undefined = !pt ? undefined
      : pt.mix ?? (pt.default && typeof pt.default === 'object' ? pt.default : undefined)
        ?? (typeof pt.default === 'string' ? onehot(pt.default) : pt.prefer?.length ? onehot(pt.prefer[0]) : undefined)
    const unset = !base
    return {
      id: n.id, options, unset, legacy, source: pt?.source ?? (unset ? '' : 'assumption'),
      rows: [rowFrom(options, base, null), ...(pt?.rules ?? []).map((r): RowDraft => ({ ...rowFrom(options, r.probs ?? (r.choose ? onehot(r.choose) : undefined), r.when), fixed: !r.probs }))],
    }
  })
  return { mode: String(fc.decision_policy.mode ?? 'sample'), ruleBackend: fc.decision_policy.backend === 'rule', points }
}

export const rowNumbers = (r: RowDraft) => r.vals.map(parsePct)
export const rowTotal = (r: RowDraft) => sumPct(rowNumbers(r))
export const rowValid = (r: RowDraft) => rowOk(rowNumbers(r)) && (r.when === null || r.when.trim() !== '')

export function pointChanged(a: PointDraft, b: PointDraft): boolean {
  return JSON.stringify(a.rows.map((r) => [r.when, rowNumbers(r)])) !== JSON.stringify(b.rows.map((r) => [r.when, rowNumbers(r)]))
}

export function isDirty(initial: Draft, now: Draft): boolean {
  return (!now.ruleBackend && initial.mode !== now.mode) || now.points.some((p, i) => pointChanged(initial.points[i], p))
}

export function allValid(d: Draft): boolean {
  return d.points.every((p) => p.rows.every(rowValid))
}

/** The flowchart document with the draft's tables stored in `decision_policy` (unchanged points are left byte-for-byte). */
export function applyDraft(fc: Flowchart, initial: Draft, now: Draft): Flowchart {
  const doc: Flowchart = JSON.parse(JSON.stringify(fc))
  if (!now.ruleBackend && now.mode !== initial.mode) doc.decision_policy.mode = now.mode
  now.points.forEach((p, i) => {
    const changed = pointChanged(initial.points[i], p)
    if (!changed) return
    const toProbs = (r: RowDraft, order = p.options) => fractions(order, order.map((o) => rowNumbers(r)[p.options.indexOf(o)] ?? 0))
    const [def, ...rules] = p.rows
    const old = fc.decision_policy.points[p.id]
    const src = old?.source && !old.source.startsWith('user edit') ? `user edit (was ${old.source})` : old?.source ?? 'user edit'
    if (p.legacy) {
      // keep the older form: edit the shares in place, in the order the document listed them (the draw walks that order)
      const order = [...Object.keys(old?.mix ?? {}).filter((o) => p.options.includes(o)), ...p.options.filter((o) => !(old?.mix ?? {})[o])]
      doc.decision_policy.points[p.id] = { ...(old ?? {}), mix: toProbs(def, order), source: src }
      delete doc.decision_policy.points[p.id].default
      return
    }
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

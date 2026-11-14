import { describe, expect, it } from 'vitest'
import type { Flowchart } from '../api/types'
import templates from '../mock/fixtures/templates.json'
import { allValid, applyDraft, draftFrom, isDirty } from './decisionDraft'

const fc = (templates as unknown as { id: string; flowcharts: Flowchart[] }[]).find((t) => t.id === 'finland_lung')!.flowcharts.find((f) => f.id === 'baseline')!

describe('decisions draft', () => {
  it('starts clean and valid for a shipped flowchart', () => {
    const d = draftFrom(fc)
    expect(d.points.map((p) => p.id)).toEqual(['first_contact', 'sample_choice'])
    expect(allValid(d)).toBe(true)
    expect(isDirty(d, draftFrom(fc))).toBe(false)
  })
  it('an unchanged draft leaves the policy untouched', () => {
    const d = draftFrom(fc)
    expect(applyDraft(fc, d, draftFrom(fc)).decision_policy).toEqual(fc.decision_policy)
  })
  it('round-trips an edit, including a new condition', () => {
    const base = draftFrom(fc)
    const d = draftFrom(fc)
    d.points[0].rows[0].vals = ['70', '30']
    d.points[1].rows.push({ when: "age >= 70", vals: ['10', '90'] })
    expect(isDirty(base, d)).toBe(true)
    expect(allValid(d)).toBe(true)
    const doc = applyDraft(fc, base, d)
    expect(doc.decision_policy.points.first_contact.default).toEqual({ nurse_visit: 0.7, gp_visit: 0.3 })
    expect(doc.decision_policy.points.sample_choice.rules!.at(-1)).toEqual({ when: 'age >= 70', probs: { bronch: 0.1, ttnb: 0.9 } })
    expect(doc.decision_policy.points.first_contact.source).toBe('user edit (was KHALIFE2025)')
    const again = draftFrom(doc)
    expect(again.points[0].rows[0].vals).toEqual(['70', '30'])
    expect(again.points[1].rows.at(-1)!.when).toBe('age >= 70')
    expect(JSON.stringify(fc)).not.toContain('user edit') // input untouched
  })
  it('flags a row that does not add to 100 or a condition with no text', () => {
    const d = draftFrom(fc)
    d.points[0].rows[0].vals = ['70', '40']
    expect(allValid(d)).toBe(false)
    const e = draftFrom(fc)
    e.points[1].rows.push({ when: ' ', vals: ['50', '50'] })
    expect(allValid(e)).toBe(false)
  })
  it('edits the older rule form in place (mix, fixed choices)', () => {
    const old: Flowchart = JSON.parse(JSON.stringify(fc))
    old.decision_policy = { backend: 'rule', mode: 'argmax', points: {
      first_contact: { mix: { nurse_visit: 0.5, gp_visit: 0.5 }, source: 'KHALIFE2025' },
      sample_choice: { rules: [{ when: "location == 'central'", choose: 'bronch' }], mix: { ttnb: 0.65, bronch: 0.35 }, source: 'assumption' },
    } }
    const base = draftFrom(old)
    expect(base.points[1].legacy).toBe(true)
    expect(base.points[1].rows[1].fixed).toBe(true)
    expect(base.points[1].rows[1].vals).toEqual(['100', '0'])
    const d = draftFrom(old)
    d.points[1].rows[0].vals = ['40', '60']
    const doc = applyDraft(old, base, d)
    const pt = doc.decision_policy.points.sample_choice
    expect(Object.keys(pt.mix!)).toEqual(['ttnb', 'bronch']) // the order the document listed
    expect(pt.mix).toEqual({ ttnb: 0.6, bronch: 0.4 })
    expect(pt.rules).toEqual([{ when: "location == 'central'", choose: 'bronch' }])
    expect(pt.default).toBeUndefined()
    expect(doc.decision_policy.points.first_contact).toEqual(old.decision_policy.points.first_contact)
  })
})

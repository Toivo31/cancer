import { describe, expect, it } from 'vitest'
import { fractions, normalisePct, parsePct, rowOk, sumPct } from './probs'

describe('probabilities as percentages', () => {
  it('accepts rows that add to 100', () => {
    expect(rowOk([35, 65])).toBe(true)
    expect(rowOk([33.3, 33.3, 33.4])).toBe(true)
  })
  it('rejects rows that do not, and bad numbers', () => {
    expect(rowOk([35, 60])).toBe(false)
    expect(rowOk([null, 100])).toBe(false)
    expect(rowOk([-10, 110])).toBe(false)
    expect(rowOk([101, -1])).toBe(false)
  })
  it('parses typed text', () => {
    expect(parsePct('35,5')).toBe(35.5)
    expect(parsePct(' 40 % ')).toBe(40)
    expect(parsePct('')).toBeNull()
    expect(parsePct('abc')).toBeNull()
  })
  it('sums without float residue', () => { expect(sumPct([0.1 * 3, 99.7])).toBe(100) })
  it('balances to exactly 100', () => {
    const b = normalisePct([1, 1, 1])
    expect(sumPct(b)).toBe(100)
    expect(normalisePct([0, 0])).toEqual([50, 50])
  })
  it('stores fractions that add to 1', () => {
    const f = fractions(['a', 'b', 'c'], [33.3, 33.3, 33.4])
    expect(Object.values(f).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12)
    expect(f.a).toBe(0.333)
  })
})

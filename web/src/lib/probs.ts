// Helpers for the decisions table: probabilities are edited as percentages (rows must add to 100)
// and stored as fractions in the flowchart document.

/** Tolerance in percentage points: one decimal is shown, so allow rounding noise below that. */
export const SUM_TOLERANCE = 0.05

export const toPercent = (p: number) => Math.round(p * 1000) / 10
export const fromPercent = (pct: number) => pct / 100

export function sumPct(values: (number | null | undefined)[]): number {
  return Math.round(values.reduce<number>((a, v) => a + (v ?? 0), 0) * 10) / 10
}

export function rowOk(values: (number | null | undefined)[]): boolean {
  if (values.some((v) => v == null || Number.isNaN(v) || (v as number) < 0 || (v as number) > 100)) return false
  return Math.abs(sumPct(values) - 100) <= SUM_TOLERANCE
}

/** Parse what the user typed: "35", "35.5", "35,5"; empty or garbage gives null. */
export function parsePct(text: string): number | null {
  const t = text.trim().replace(',', '.').replace('%', '')
  if (t === '') return null
  const v = Number(t)
  return Number.isFinite(v) ? v : null
}

/** Percentages that add to exactly 100 after rounding to one decimal: the last option takes the remainder. */
export function normalisePct(values: number[]): number[] {
  const total = values.reduce((a, b) => a + b, 0)
  if (total <= 0) return values.map(() => Math.round(1000 / values.length) / 10)
  const scaled = values.map((v) => Math.round((v / total) * 1000) / 10)
  const rest = Math.round((100 - scaled.slice(0, -1).reduce((a, b) => a + b, 0)) * 10) / 10
  scaled[scaled.length - 1] = rest
  return scaled
}

/** Stored fractions from percentages, with the last option fixed so the sum is exactly 1 (no float residue). */
export function fractions(options: string[], pct: number[]): Record<string, number> {
  const out: Record<string, number> = {}
  let acc = 0
  options.forEach((o, i) => {
    if (i < options.length - 1) { out[o] = Math.round(pct[i] * 10) / 1000; acc += out[o] } else out[o] = Math.round((1 - acc) * 1e6) / 1e6
  })
  return out
}

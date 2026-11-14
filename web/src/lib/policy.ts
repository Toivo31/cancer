import type { StubPoint } from '../api/types'

/** The shares a decision point offers when no condition applies, whichever stored form it is in. */
export function defaultShares(pt?: StubPoint): Record<string, number> | undefined {
  if (!pt) return undefined
  if (pt.mix) return pt.mix
  if (pt.default && typeof pt.default === 'object') return pt.default
  if (typeof pt.default === 'string') return { [pt.default]: 1 }
  if (pt.prefer?.length) return { [pt.prefer[0]]: 1 }
  return undefined
}

import type { Run } from '../api/types'

/**
 * Which run the screen should show for a flowchart version. A run named in the address only counts when it belongs to
 * this exact flowchart and version (an address left over from before a save or a version switch must not highlight an
 * older version's run); otherwise the newest finished run of this version is used, if there is one.
 */
export function effectiveRun(runs: Run[], requested: string | null, fid: string | null, version: number | null): Run | null {
  if (fid === null || version === null) return null
  const mine = (r: Run) => r.flowchart.id === fid && r.flowchart.version === version
  const asked = requested ? runs.find((r) => r.id === requested) : undefined
  if (asked && mine(asked)) return asked
  // a run that is not loaded yet (just started) is kept so it can appear in the list
  if (requested && !asked) return null
  return runs.find((r) => r.status === 'succeeded' && mine(r)) ?? null
}

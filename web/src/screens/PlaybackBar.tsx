import { useEffect, useState } from 'react'
import type { Clock } from '../graph/clock'
import { counters } from '../graph/playback'
import type { PPatient } from '../graph/playback'

const SPEEDS = [0.5, 1, 2, 4, 8]

export function PlaybackBar({ clock, patients, sampleLabel }: { clock: Clock; patients: PPatient[]; sampleLabel: string }) {
  const [, force] = useState(0)
  // counters and slider refresh a few times a second; the dots themselves are drawn straight from the clock
  useEffect(() => {
    let last = 0
    const off = clock.subscribe(() => { const now = performance.now(); if (now - last > 90 || !clock.playing) { last = now; force((x) => x + 1) } })
    return off
  }, [clock])
  const c = counters(patients, clock.t)
  const Stat = ({ label, value, color }: { label: string; value: number; color: string }) => (
    <div className="stat"><div className="label" style={{ color }}>{label}</div><div className="num">{value}</div></div>
  )
  return (
    <div className="playbar" data-testid="playback-bar">
      <button className="btn small playbtn" onClick={() => clock.toggle()} aria-label={clock.playing ? 'Pause' : 'Play'}>{clock.playing ? '❚❚' : '▶'}</button>
      <div className="clockbox"><div className="label">Day</div><div className="num bigday">{Math.floor(clock.t)}</div></div>
      <input type="range" aria-label="Time" min={0} max={clock.horizon} step={clock.horizon / 600} value={clock.t} onChange={(e) => clock.seek(Number(e.target.value))} style={{ flex: 1, minWidth: 120 }} />
      <div className="speeds" role="group" aria-label="Speed">
        {SPEEDS.map((s) => <button key={s} className={`tab ${clock.rate === s ? 'on' : ''}`} onClick={() => { clock.setRate(s); force((x) => x + 1) }}>{s}×</button>)}
      </div>
      <div className="stats">
        <Stat label="Waiting" value={c.waiting} color="var(--amber)" />
        <Stat label="Being served" value={c.served} color="var(--blue)" />
        <Stat label="Diagnosed" value={c.diagnosed} color="var(--text)" />
        <Stat label="Treated" value={c.treated} color="var(--mint)" />
        <Stat label="Discharged" value={c.left} color="var(--muted)" />
        <Stat label="Cancer missed" value={c.missed} color="var(--coral)" />
      </div>
      <div className="dim" style={{ fontSize: 11, maxWidth: 150 }}>{sampleLabel}</div>
    </div>
  )
}

/** Playback clock: simulated days since each patient's first contact. Lives outside React so 60 frames a second cost no re-renders. */
export class Clock {
  t = 0
  playing = false
  /** speed multiplier; 1 plays the whole horizon in `seconds` */
  rate = 1
  private listeners = new Set<() => void>()
  private raf = 0
  private last = 0

  constructor(public horizon: number, public seconds = 45) {}

  subscribe(fn: () => void): () => void { this.listeners.add(fn); return () => this.listeners.delete(fn) }
  private emit() { this.listeners.forEach((f) => f()) }

  setHorizon(h: number) { this.horizon = h; if (this.t > h) this.t = h; this.emit() }
  seek(t: number) { this.t = Math.max(0, Math.min(this.horizon, t)); this.emit() }
  setRate(r: number) { this.rate = r }

  play() {
    if (this.playing) return
    if (this.t >= this.horizon) this.t = 0
    this.playing = true
    this.last = performance.now()
    const tick = (now: number) => {
      if (!this.playing) return
      const dt = Math.min(0.1, (now - this.last) / 1000)
      this.last = now
      this.t += (dt * this.rate * this.horizon) / this.seconds
      if (this.t >= this.horizon) { this.t = this.horizon; this.playing = false; this.emit(); return }
      this.emit()
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
    this.emit()
  }
  pause() { this.playing = false; cancelAnimationFrame(this.raf); this.emit() }
  toggle() { this.playing ? this.pause() : this.play() }
  dispose() { this.playing = false; cancelAnimationFrame(this.raf); this.listeners.clear() }
}

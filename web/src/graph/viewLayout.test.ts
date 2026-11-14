import { beforeEach, describe, expect, it } from 'vitest'
import { applyView, emptyView, loadView, saveView } from './viewLayout'

describe('view layout', () => {
  beforeEach(() => window.localStorage.clear())
  it('round-trips through localStorage and drops garbage', () => {
    saveView('p/a', { pos: { x: { x: 1, y: 2 } }, size: { x: { w: 200, h: 90 } } })
    expect(loadView('p/a')).toEqual({ pos: { x: { x: 1, y: 2 } }, size: { x: { w: 200, h: 90 } } })
    expect(loadView('p/b')).toEqual(emptyView())
    window.localStorage.setItem('pathway:view-layout:bad', '{"pos":{"x":{"x":"1"}}')
    expect(loadView('bad')).toEqual(emptyView())
  })
  it('an empty layout removes the stored entry', () => {
    saveView('k', { pos: { x: { x: 1, y: 2 } }, size: {} }); saveView('k', emptyView())
    expect(window.localStorage.getItem('pathway:view-layout:k')).toBeNull()
  })
  it('applies moves and sizes and ignores unknown steps', () => {
    const base = { a: { x: 0, y: 0, w: 10, h: 10, row: 0 }, b: { x: 50, y: 0, w: 10, h: 10, row: 0 } }
    const { boxes, moved } = applyView(base, { pos: { a: { x: 5, y: 6 }, gone: { x: 1, y: 1 } }, size: { b: { w: 99, h: 40 } } })
    expect(boxes.a).toMatchObject({ x: 5, y: 6, w: 10 })
    expect(boxes.b).toMatchObject({ x: 50, w: 99, h: 40 })
    expect([...moved]).toEqual(['a'])
    expect(boxes.gone).toBeUndefined()
  })
})

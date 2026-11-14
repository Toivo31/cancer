import { describe, expect, it } from 'vitest'
import { pushHistory, redoHistory, startHistory, undoHistory } from './history'

describe('edit history', () => {
  it('undoes and redoes, and a new edit clears what could be redone', () => {
    let h = startHistory('a')
    h = pushHistory(h, 'b'); h = pushHistory(h, 'c')
    h = undoHistory(h); expect(h.present).toBe('b')
    h = undoHistory(h); expect(h.present).toBe('a')
    h = undoHistory(h); expect(h.present).toBe('a')
    h = redoHistory(h); expect(h.present).toBe('b')
    h = pushHistory(h, 'x'); expect(h.future).toEqual([])
    expect(redoHistory(h).present).toBe('x')
  })
  it('merges quick edits of the same field into one step', () => {
    let h = startHistory('')
    h = pushHistory(h, 'a', 'label', 1000)
    h = pushHistory(h, 'ab', 'label', 1300)
    h = pushHistory(h, 'abc', 'label', 1500)
    expect(h.past).toEqual([''])
    h = pushHistory(h, 'abcd', 'label', 5000)
    expect(h.past).toEqual(['', 'abc'])
    h = pushHistory(h, 'other', 'guard', 5100)
    expect(h.past.length).toBe(3)
  })
})

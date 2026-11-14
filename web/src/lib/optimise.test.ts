import { describe, expect, it } from 'vitest'
import type { OptChange } from '../api/types'
import { linkedGroup, toggleChange } from './optimise'

const ch = (index: number, linked_with: number[] = []): OptChange => ({ index, kind: 'relax', target: 't', label: `c${index}`, linked_with })

describe('optimise selection', () => {
  const cs = [ch(0), ch(1, [2]), ch(2), ch(3)]
  it('finds linked partners in either direction', () => {
    expect(linkedGroup(cs, 1)).toEqual([1, 2])
    expect(linkedGroup(cs, 2)).toEqual([1, 2])
    expect(linkedGroup(cs, 0)).toEqual([0])
  })
  it('toggles a linked pair together', () => {
    const all = new Set([0, 1, 2, 3])
    expect([...toggleChange(cs, all, 2)].sort()).toEqual([0, 3])
    expect([...toggleChange(cs, new Set([0]), 1)].sort()).toEqual([0, 1, 2])
  })
})

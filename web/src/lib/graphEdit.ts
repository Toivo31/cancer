import type { EdgeType, Flowchart } from '../api/types'

// Small, pure edits of a flowchart document for the editor. Each returns a new document and leaves the old one alone.
const clone = (fc: Flowchart): Flowchart => JSON.parse(JSON.stringify(fc))

export interface StepFields { label?: string; test?: string; when?: string }

/** Change a step's label, what happens there (test) or its guard. An empty test or guard removes the field. */
export function setStepFields(fc: Flowchart, id: string, f: StepFields): Flowchart {
  const doc = clone(fc)
  const n = doc.nodes.find((x) => x.id === id)
  if (!n) return doc
  if (f.label !== undefined) n.label = f.label
  if (f.test !== undefined) { if (f.test.trim()) n.test = f.test.trim(); else delete n.test }
  if (f.when !== undefined) { if (f.when.trim()) n.when = f.when; else delete n.when }
  return doc
}

export const EDITABLE_EDGE_TYPES: EdgeType[] = ['required', 'any', 'optional']

export function hasEdge(fc: Flowchart, from: string, to: string): boolean {
  return fc.edges.some((e) => e.from === from && e.to === to)
}

/** Add a connection; a duplicate, a self loop or an unknown step leaves the document unchanged. */
export function addEdge(fc: Flowchart, from: string, to: string, type: EdgeType): Flowchart {
  const ids = new Set(fc.nodes.map((n) => n.id))
  if (from === to || !ids.has(from) || !ids.has(to) || hasEdge(fc, from, to)) return fc
  const doc = clone(fc)
  doc.edges.push({ from, to, type })
  return doc
}

/** Remove a connection. Decision options (type "option") belong to the decision's table and are not removed here. */
export function removeEdge(fc: Flowchart, from: string, to: string): Flowchart {
  const doc = clone(fc)
  doc.edges = doc.edges.filter((e) => !(e.from === from && e.to === to && e.type !== 'option'))
  return doc
}

export function sameDoc(a: Flowchart, b: Flowchart): boolean {
  return JSON.stringify([a.nodes, a.edges]) === JSON.stringify([b.nodes, b.edges])
}

import type { EdgeType, FlowEdge, FlowNode, Flowchart, StubPoint } from '../api/types'

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

// ---- adding and deleting steps, and the options of a decision ----

const slug = (s: string) => s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 28) || 'step'

/** An id nobody uses yet, built from the label. */
export function uniqueId(fc: Pick<Flowchart, 'nodes'>, label: string): string {
  const taken = new Set(fc.nodes.map((n) => n.id))
  const base = slug(label)
  if (!taken.has(base)) return base
  for (let i = 2; ; i++) if (!taken.has(`${base}_${i}`)) return `${base}_${i}`
}

export interface NewStep { label: string; kind: 'step' | 'join' | 'exit'; outcome?: string; test?: string }

/** Add a step with no connections yet (connect it afterwards). Returns the new document and the step's id. */
export function addStep(fc: Flowchart, s: NewStep, after?: string | null): { doc: Flowchart; id: string } {
  const doc = clone(fc)
  const label = s.label.trim() || (s.kind === 'exit' ? 'New end point' : s.kind === 'join' ? 'New join' : 'New step')
  const id = uniqueId(fc, label)
  const node: FlowNode = { id, kind: s.kind, label }
  if (s.kind === 'exit') node.outcome = s.outcome ?? 'discharged'
  if (s.kind === 'step' && s.test) node.test = s.test
  doc.nodes.push(node)
  if (after && doc.nodes.some((n) => n.id === after && n.kind !== 'exit')) doc.edges.push({ from: after, to: id, type: 'required' })
  return { doc, id }
}

/** Connections that would go with a step if it were deleted. */
export function connectionsOf(fc: Flowchart, id: string): FlowEdge[] {
  return fc.edges.filter((e) => e.from === id || e.to === id)
}

type Probs = Record<string, number>
function dropKey(p: Probs, key: string): Probs {
  const rest = Object.entries(p).filter(([k]) => k !== key)
  const total = rest.reduce((a, [, v]) => a + v, 0)
  return Object.fromEntries(rest.map(([k, v]) => [k, total > 0 ? v / total : 1 / rest.length]))
}
function mapPoint(pt: StubPoint, f: (p: Probs) => Probs): StubPoint {
  const out = { ...pt }
  if (out.default && typeof out.default === 'object') out.default = f(out.default)
  if (out.mix) out.mix = f(out.mix)
  if (out.rules) out.rules = out.rules.map((r) => (r.probs ? { ...r, probs: f(r.probs) } : r))
  return out
}

function reindex(doc: Flowchart, decision: string) {
  doc.edges.filter((e) => e.from === decision && e.type === 'option').sort((a, b) => (a.index ?? 0) - (b.index ?? 0)).forEach((e, i) => { e.index = i })
}

/** Remove one option of a decision: its connection, its share (the others are scaled to add to 100 again) and its place in the options list. */
export function removeOption(fc: Flowchart, decision: string, target: string): Flowchart {
  const doc = clone(fc)
  doc.edges = doc.edges.filter((e) => !(e.from === decision && e.to === target && e.type === 'option'))
  reindex(doc, decision)
  const n = doc.nodes.find((x) => x.id === decision)
  if (n?.options) n.options = n.options.filter((o) => o !== target)
  const pt = doc.decision_policy?.points?.[decision]
  if (pt) doc.decision_policy.points[decision] = mapPoint(pt, (p) => (target in p ? dropKey(p, target) : p))
  return doc
}

/** Add an option to a decision, leading to `target`, with a share of 0 (set the share in the Decisions table). A duplicate or a self loop changes nothing. */
export function addOption(fc: Flowchart, decision: string, target: string): Flowchart {
  const ids = new Set(fc.nodes.map((n) => n.id))
  const d = fc.nodes.find((n) => n.id === decision)
  if (!d || d.kind !== 'decision' || decision === target || !ids.has(target) || fc.edges.some((e) => e.from === decision && e.to === target)) return fc
  const doc = clone(fc)
  const index = doc.edges.filter((e) => e.from === decision && e.type === 'option').length
  doc.edges.push({ from: decision, to: target, type: 'option', index })
  const n = doc.nodes.find((x) => x.id === decision)!
  if (n.options) n.options = [...n.options, target]
  const pt = doc.decision_policy?.points?.[decision]
  if (pt) doc.decision_policy.points[decision] = mapPoint(pt, (p) => ({ ...p, [target]: 0 }))
  return doc
}

/** Delete a step with its connections. Where it was an option of a decision, that option goes too (see removeOption). */
export function removeStep(fc: Flowchart, id: string): Flowchart {
  let doc = clone(fc)
  for (const e of fc.edges) if (e.to === id && e.type === 'option') doc = removeOption(doc, e.from, id)
  doc.nodes = doc.nodes.filter((n) => n.id !== id)
  doc.edges = doc.edges.filter((e) => e.from !== id && e.to !== id)
  if (doc.decision_policy?.points?.[id]) delete doc.decision_policy.points[id]
  return doc
}

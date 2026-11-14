// Compile-time check that the hand-written types in types.ts still accept what the service describes
// (src/api/schema.d.ts, regenerated with `npm run gen:api`). Nothing here runs.
import type { components } from './schema'
import type { Flowchart, Problem, Project, Template, ValidationResult } from './types'

type S = components['schemas']
export const _flowchart = (d: S['FlowchartDocument']): Flowchart => d as unknown as Flowchart
export const _project = (p: S['ProjectSummary']): Project => p
export const _template = (t: S['TemplateSummary']): Template => t
export const _problem = (p: S['Problem']): Problem => p as unknown as Problem
export const _validation = (v: S['ValidationResult']): ValidationResult => v as unknown as ValidationResult

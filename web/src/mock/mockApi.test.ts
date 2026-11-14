import { beforeEach, describe, expect, it } from 'vitest'
import { mock, resetMock } from './mockApi'

describe('mock service', () => {
  beforeEach(() => resetMock())
  it('creates a project from a template and saves a new version', async () => {
    const t = await mock.templates()
    expect(t.map((x) => x.id)).toContain('finland_scenario')
    const p = await mock.createProject('Test', 'finland_scenario')
    const list = await mock.listFlowcharts(p.id)
    const base = list.find((f) => f.id === 'baseline')!
    expect(base.versions).toEqual([1])
    const v1 = await mock.getFlowchart(p.id, 'baseline', 1)
    const edited = JSON.parse(JSON.stringify(v1))
    edited.decision_policy.points.first_contact.default = { nurse_visit: 0.7, gp_visit: 0.3 }
    const v2 = await mock.saveFlowchart(p.id, 'baseline', edited)
    expect(v2.version).toBe(2)
    expect(v2.parent_version).toBe(1)
    expect((await mock.getFlowchart(p.id, 'baseline', 1)).decision_policy.points.first_contact.default!.gp_visit).toBe(0.5)
  })
  it('refuses a version whose probabilities do not add to 1', async () => {
    const p = await mock.createProject('Test', 'finland_scenario')
    const v1 = await mock.getFlowchart(p.id, 'baseline', 1)
    v1.decision_policy.points.first_contact.default = { nurse_visit: 0.7, gp_visit: 0.4 }
    await expect(mock.saveFlowchart(p.id, 'baseline', v1)).rejects.toMatchObject({ status: 422 })
  })
  it('runs, reports progress and can be cancelled', async () => {
    const p = await mock.createProject('Test', 'norway_check')
    const r = await mock.startRun(p.id, { flowchart: { id: 'observed', version: 1 }, n: 100, seeds: [301] })
    const j = await mock.getJob(r.job_id)
    expect(j.state).toBe('running')
    await mock.cancelJob(r.job_id)
    expect((await mock.getRun(p.id, r.run_id)).status).toBe('cancelled')
  })
})

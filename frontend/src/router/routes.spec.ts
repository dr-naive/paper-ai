import { describe, expect, it } from 'vitest'
import router, { routes } from './index'

describe('project route foundation', () => {
  it.each([
    ['/projects/project-1/overview', 'ProjectOverview'],
    ['/projects/project-1/discover', 'ProjectDiscover'],
    ['/projects/project-1/papers', 'ProjectPapers'],
    ['/projects/project-1/writing', 'ProjectWriting'],
  ])('resolves %s to %s', (path, name) => {
    const resolved = router.resolve(path)
    expect(resolved.name).toBe(name)
    expect(resolved.params.projectId).toBe('project-1')
  })

  it('keeps the legacy project link as an overview redirect', () => {
    const legacy = routes.find(route => route.name === 'LegacyProjectWorkspace')
    expect(legacy?.path).toBe('/project/:id')
    expect(legacy?.redirect).toBeTypeOf('function')
  })

  it('gives each V1 project tab its own page boundary', () => {
    const names = ['ProjectOverview', 'ProjectDiscover', 'ProjectPapers', 'ProjectWriting']
    const components = names.map(name => routes.find(route => route.name === name)?.component)
    expect(components.every(Boolean)).toBe(true)
    expect(new Set(components).size).toBe(names.length)
  })

  it('preserves the independent Reader route', () => {
    const resolved = router.resolve('/paper/paper-1')
    expect(resolved.name).toBe('PaperReader')
    expect(resolved.params.id).toBe('paper-1')
  })
})

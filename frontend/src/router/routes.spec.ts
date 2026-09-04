import { describe, expect, it, vi } from 'vitest'
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

  it('does not expose the removed universal project chat surface', () => {
    const legacyChat = routes.find(route => route.name === 'LegacyProjectChat')
    expect(legacyChat?.path).toBe('/project/:id/chat')
    expect(legacyChat?.component).toBeUndefined()
    expect(legacyChat?.redirect).toBeTypeOf('function')
    expect((legacyChat?.redirect as (to: { params: { id: string } }) => unknown)({ params: { id: 'project-1' } })).toEqual({
      name: 'ProjectOverview',
      params: { projectId: 'project-1' },
    })
  })

  it('keeps only the four V1 project tabs in the project header contract', () => {
    expect(routes.map(route => route.name)).not.toContain('ProjectChat')
    expect(routes.map(route => route.name)).not.toContain('ProjectWorkspace')
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

  it('disables smooth anchor scrolling when reduced motion is requested', () => {
    const matchMedia = vi.fn().mockReturnValue({ matches: true } as MediaQueryList)
    vi.stubGlobal('matchMedia', matchMedia)
    const result = router.options.scrollBehavior?.(
      { hash: '#overview' } as any,
      {} as any,
      null,
    )

    expect(result).toEqual({ el: '#overview', top: 20, behavior: 'auto' })
    expect(matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)')
    vi.unstubAllGlobals()
  })
})

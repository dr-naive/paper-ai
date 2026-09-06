import { describe, expect, it, vi } from 'vitest'
import router, { routes } from './index'
import {
  projectReaderLocation,
  readerContextFromRoute,
  readerPaperIdFromRoute,
  readerProjectIdFromRoute,
  standaloneReaderLocation,
} from './reader'

describe('project route foundation', () => {
  it.each([
    ['/guide/overview', 'overview'],
    ['/guide/discover', 'discover'],
    ['/guide/papers', 'papers'],
    ['/guide/writing', 'writing'],
    ['/guide/reader', 'reader'],
    ['/guide/evidence', 'evidence'],
    ['/guide/troubleshooting', 'troubleshooting'],
  ])('resolves guide page %s to the GuideSection route', (path, section) => {
    const resolved = router.resolve(path)
    expect(resolved.name).toBe('GuideSection')
    expect(resolved.params.section).toBe(section)
  })

  it('redirects the guide entrypoint to the overview page', () => {
    const guide = routes.find(route => route.name === 'Guide')
    expect(guide?.component).toBeUndefined()
    expect(guide?.redirect).toEqual({ name: 'GuideSection', params: { section: 'overview' } })
  })

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
    expect(resolved.meta.readerContext).toBe('standalone')
  })

  it('adds a semantic project Reader route without duplicating the Reader implementation', () => {
    const resolved = router.resolve('/projects/project-1/papers/paper-1/read')
    expect(resolved.name).toBe('ProjectPaperReader')
    expect(resolved.params.projectId).toBe('project-1')
    expect(resolved.params.paperId).toBe('paper-1')
    expect(resolved.meta.readerContext).toBe('project')

    const standalone = routes.find(route => route.name === 'PaperReader')
    const project = routes.find(route => route.name === 'ProjectPaperReader')
    expect(project?.component).toBe(standalone?.component)
  })

  it('keeps legacy project query links readable while canonical locations carry context in params', () => {
    const legacy = router.resolve('/paper/paper-1?project_id=project-1')
    expect(readerContextFromRoute(legacy)).toBe('project')
    expect(readerPaperIdFromRoute(legacy)).toBe('paper-1')
    expect(readerProjectIdFromRoute(legacy)).toBe('project-1')
    expect(router.resolve(projectReaderLocation('project-1', 'paper-1')).href)
      .toBe('/projects/project-1/papers/paper-1/read')
    expect(router.resolve(standaloneReaderLocation('paper-1')).href).toBe('/paper/paper-1')

    const legacyRoute = routes.find(route => route.name === 'PaperReader')
    const redirected = (legacyRoute?.beforeEnter as (to: any) => any)(legacy)
    expect(redirected).toEqual({
      name: 'ProjectPaperReader',
      params: { projectId: 'project-1', paperId: 'paper-1' },
      query: {},
      hash: '',
    })
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

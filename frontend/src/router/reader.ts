import type { LocationQueryRaw, RouteLocationRaw } from 'vue-router'

/**
 * Reader entrypoints are deliberately named by business context.  Both
 * locations render the same PaperReader component, but only the project
 * location carries a project identity in the URL.
 */
export type ReaderContext = 'standalone' | 'project'

export interface ReaderRouteLike {
  name?: unknown
  meta?: Record<string, unknown>
  params?: Record<string, unknown>
  query?: Record<string, unknown>
}

export const readerContextFromRoute = (route: ReaderRouteLike): ReaderContext => (
  route.meta?.readerContext === 'project'
    || Boolean(String(route.params?.projectId || route.query?.project_id || ''))
    ? 'project'
    : 'standalone'
)

export const readerPaperIdFromRoute = (route: ReaderRouteLike) => (
  String(route.params?.paperId || route.params?.id || '')
)

/** `project_id` is accepted only to keep old bookmarks readable. */
export const readerProjectIdFromRoute = (route: ReaderRouteLike) => (
  readerContextFromRoute(route) === 'project'
    ? String(route.params?.projectId || route.query?.project_id || '')
    : ''
)

export const standaloneReaderLocation = (
  paperId: string,
  query?: LocationQueryRaw,
): RouteLocationRaw => ({
  name: 'PaperReader',
  params: { id: paperId },
  ...(query ? { query } : {}),
})

export const projectReaderLocation = (
  projectId: string,
  paperId: string,
  query?: LocationQueryRaw,
): RouteLocationRaw => ({
  name: 'ProjectPaperReader',
  params: { projectId, paperId },
  ...(query ? { query } : {}),
})

/** String URLs are used only for external links opened in a new tab. */
export const standaloneReaderPath = (paperId: string) => (
  `/paper/${encodeURIComponent(paperId)}`
)

export const projectReaderPath = (projectId: string, paperId: string) => (
  `/projects/${encodeURIComponent(projectId)}/papers/${encodeURIComponent(paperId)}/read`
)

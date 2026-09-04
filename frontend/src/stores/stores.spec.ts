import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from './project'
import { useWorkspaceStore } from './workspace'
import { useAuthStore } from './auth'
import { useExecutionsStore } from './executions'
import { useWritingStore } from './writing'

describe('workspace stores', () => {
  beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })
  it('keeps the active panel per project', () => {
    const store = useWorkspaceStore()
    store.setActivePanel('project-a', 'papers')
    store.setActivePanel('project-b', 'activity')
    expect(store.activePanel('project-a')).toBe('papers')
    expect(store.activePanel('project-b')).toBe('activity')
  })
  it('derives project paper count from the single project state', () => {
    const store = useProjectStore()
    store.setPapers([{ id: 'one' }, { id: 'two' }] as any)
    expect(store.paperCount).toBe(2)
    store.clear()
    expect(store.paperCount).toBe(0)
  })
  it('exposes typed project metadata from the current project', () => {
    const store = useProjectStore()
    store.setProject({
      id: 'project-a',
      research_scope: { field: 'Education', research_subject: 'Students', research_question: '', research_goal: '', keywords: ['AI'], method_direction: '', notes: '' },
    } as any)
    expect(store.projectId).toBe('project-a')
    expect(store.researchScope.field).toBe('Education')
    expect(store.researchScope.keywords).toEqual(['AI'])
    store.clear()
    expect(store.researchScope.keywords).toEqual([])
  })
  it('owns the persisted authentication session', () => {
    const store = useAuthStore()
    store.setSession({ access_token: 'token', user: { id: 'u1', username: 'reader', email: 'r@example.com', role: 'user', is_active: true, created_at: '' } })
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('token')
    store.clearSession()
    expect(store.user).toBeNull()
  })
  it('deduplicates and orders global execution state', () => {
    const store = useExecutionsStore()
    const older = { id: 'shared', goal: 'Older copy', status: 'running', updated_at: '2026-01-01T00:00:00Z' }
    const newer = { id: 'shared', goal: 'Newer copy', status: 'running', updated_at: '2026-01-02T00:00:00Z' }
    const completed = { id: 'done', goal: 'Done', status: 'completed', updated_at: '2026-01-03T00:00:00Z' }
    store.globalExecutions = [older, completed] as any
    store.byProject = { second: [newer] } as any
    expect(store.allExecutions.map(item => item.id)).toEqual(['done', 'shared'])
    expect(store.allExecutions[1].goal).toBe('Newer copy')
    expect(store.runningCount).toBe(1)
  })
  it('streams only non-terminal executions', () => {
    const store = useExecutionsStore()
    expect(store.shouldStream({ status: 'running' } as any)).toBe(true)
    expect(store.shouldStream({ status: 'waiting_user' } as any)).toBe(true)
    expect(store.shouldStream({ status: 'completed' } as any)).toBe(false)
    expect(store.shouldStream({ status: 'failed' } as any)).toBe(false)
  })
  it('keeps only bounded editor context in the writing store', () => {
    const store = useWritingStore()
    store.setWorkspace('project-a', 'document-a', 'revision-a')
    store.setEditorContext({ selectionFrom: 4, selectionTo: 8, selectedText: '证据', selectedCharacterCount: 2, currentHeading: '讨论', sectionPath: ['正文', '讨论'], nearbyText: '附近正文' })
    expect(store.hasSelection).toBe(true)
    expect(store.editorContext.currentHeading).toBe('讨论')
    expect(store.documentId).toBe('document-a')
    expect('documentContent' in store).toBe(false)
    store.clear()
    expect(store.hasSelection).toBe(false)
  })
  it('tracks proposal request state without copying document content', () => {
    const store = useWritingStore()
    store.appendMessage({ id: 'user-1', role: 'user', content: '写一段研究现状' })
    store.startRequest('正在准备项目论文和证据…')
    expect(store.requestStatus).toBe('generating')
    expect(store.requestStage).toContain('项目论文')
    store.failRequest('当前项目没有足够证据。')
    expect(store.requestStatus).toBe('error')
    expect(store.requestError).toContain('证据')
    expect('contentJson' in store).toBe(false)
    store.clearAgent()
    expect(store.messages).toHaveLength(0)
  })
})

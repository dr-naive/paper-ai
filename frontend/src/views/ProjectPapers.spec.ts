import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import ProjectPapers from './ProjectPapers.vue'
import type { ResearchProject } from '@/api/projects'

const routerPush = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ params: { projectId: 'project-1' } }))
const getProject = vi.hoisted(() => vi.fn())
const listProjectPapers = vi.hoisted(() => vi.fn())
const executionStore = vi.hoisted(() => ({
  projectExecutions: vi.fn().mockReturnValue([]),
  loadProject: vi.fn().mockResolvedValue(undefined),
  createResearch: vi.fn().mockResolvedValue({ id: 'execution-1', project_id: 'project-1', status: 'queued', input_payload: { goal_type: 'READ_PAPERS' }, updated_at: '2026-09-06T00:00:00Z' }),
  loadEvents: vi.fn().mockResolvedValue(undefined),
  startStream: vi.fn().mockResolvedValue(undefined),
  stopStream: vi.fn(),
  shouldStream: vi.fn().mockReturnValue(false),
  act: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: routerPush }), useRoute: () => routeState }
})
vi.mock('@/api/projects', async () => {
  const actual = await vi.importActual<typeof import('@/api/projects')>('@/api/projects')
  return { ...actual, getProject, listProjectPapers }
})
vi.mock('@/stores/executions', () => ({ useExecutionsStore: () => executionStore }))

const project: ResearchProject = {
  id: 'project-1', user_id: 'user-1', title: '检索研究', research_topic: '比较检索策略',
  abstract: '', phase: 'research', status: 'active', memory: { summary: '', notes: [] }, preferences: {},
  research_scope: { field: '', research_subject: '', research_question: '', research_goal: '', keywords: [], method_direction: '', notes: '' },
}
const paper = {
  id: 'membership-1', project_id: 'project-1', paper_id: 'paper-1', role: 'core', tags: [], notes: '',
  analysis_card: {}, reading_plan: { status: 'pending' as const }, reading_priority: 3, added_at: '2026-08-31T00:00:00Z',
  paper: { id: 'paper-1', title: 'Paper One', authors: 'Ada Lin', abstract: '', keywords: [], publication_year: 2026, venue: null, doi: null, reading_progress: 0 },
}

const mountView = () => mount(ProjectPapers, {
  global: {
    stubs: {
      ProjectShell: { template: '<div><slot /></div>' },
      ProjectHeader: { template: '<header />' },
      PaperUploadModal: {
        props: ['visible', 'projectId', 'projectTitle'],
        template: '<section v-if="visible" class="upload-modal-stub">{{ projectId }} · {{ projectTitle }}</section>',
      },
      'a-spin': { template: '<div><slot /></div>' },
      'a-input': { template: '<input />' },
      'a-select': { template: '<select><slot /></select>' },
      'a-option': { template: '<option><slot /></option>' },
      'a-button': {
        props: ['disabled'],
        template: '<button :disabled="disabled" type="button" @click="$emit(\'click\')"><slot /></button>',
      },
      'a-empty': { template: '<div />' },
    },
  },
})

describe('ProjectPapers navigation context', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    routerPush.mockReset()
    getProject.mockReset().mockResolvedValue(project)
    listProjectPapers.mockReset().mockResolvedValue({ items: [paper], total: 1 })
    executionStore.projectExecutions.mockReset().mockReturnValue([])
    executionStore.loadProject.mockClear()
    executionStore.createResearch.mockClear()
  })

  it('opens the local upload flow in the current project instead of leaving for the library', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.page-heading__actions button:last-child').trigger('click')
    expect(wrapper.get('.upload-modal-stub').text()).toContain('project-1')
    expect(routerPush).not.toHaveBeenCalledWith('/library')
  })

  it('starts project Reading through a READ_PAPERS GoalExecution', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.page-heading__actions button:first-child').trigger('click')
    await flushPromises()

    expect(executionStore.createResearch).toHaveBeenCalledWith('project-1', expect.objectContaining({
      agent_type: 'research_goal',
      input: expect.objectContaining({ goal_type: 'READ_PAPERS', paper_ids: ['paper-1'] }),
    }))
    expect(executionStore.loadEvents).toHaveBeenCalledWith('execution-1')
  })

  it('enters the semantic project Reader route and keeps the project id in params', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.paper-action button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith({
      name: 'ProjectPaperReader',
      params: { projectId: 'project-1', paperId: 'paper-1' },
    })
  })
})

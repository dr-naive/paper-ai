import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteProject, listProjects, type ResearchProject } from '@/api/projects'
import ResearchProjectList from './ResearchProjectList.vue'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: routerPush }) }
})

vi.mock('@/api/projects', async () => {
  const actual = await vi.importActual<typeof import('@/api/projects')>('@/api/projects')
  return { ...actual, createProject: vi.fn(), deleteProject: vi.fn(), listProjects: vi.fn() }
})

const projects: ResearchProject[] = [
  {
    id: 'project-1', user_id: 'user-1', title: '检索增强生成研究', research_topic: '比较不同检索策略',
    abstract: '', phase: 'research', status: 'active', memory: { summary: '', notes: [] }, preferences: {},
    research_scope: { field: '', research_subject: '', research_question: '', research_goal: '', keywords: [], method_direction: '', notes: '' },
    paper_count: 2, artifact_count: 1, created_at: '2026-08-25T00:00:00Z', updated_at: '2026-08-26T00:00:00Z',
  },
  {
    id: 'project-2', user_id: 'user-1', title: '引用验证研究', research_topic: '验证引文与证据的一致性',
    abstract: '', phase: 'writing', status: 'active', memory: { summary: '', notes: [] }, preferences: {},
    research_scope: { field: '', research_subject: '', research_question: '', research_goal: '', keywords: [], method_direction: '', notes: '' },
    paper_count: 1, artifact_count: 0, created_at: '2026-08-24T00:00:00Z', updated_at: '2026-08-25T00:00:00Z',
  },
]

const mountView = () => mount(ResearchProjectList, {
  global: {
    stubs: {
      ProjectShell: { template: '<div><slot /></div>' },
      ProductHeader: { template: '<header><slot name="actions" /></header>' },
      RouterLink: { props: ['to'], template: '<a href="#"><slot /></a>' },
      'a-spin': { template: '<div><slot /></div>' },
      'a-button': {
        props: ['disabled', 'loading'],
        template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
      },
      'a-modal': {
        props: ['visible'],
        template: '<section v-if="visible" class="modal-stub"><slot /><slot name="footer" /></section>',
      },
      'a-form': { template: '<form><slot /></form>' },
      'a-form-item': { template: '<label><slot /></label>' },
      'a-input': { template: '<input />' },
      'a-textarea': { template: '<textarea />' },
    },
  },
})

describe('ResearchProjectList', () => {
  beforeEach(() => {
    vi.mocked(listProjects).mockReset().mockResolvedValue({ items: projects, total: 2, page: 1, page_size: 50 })
    vi.mocked(deleteProject).mockReset().mockResolvedValue(null)
    routerPush.mockReset()
  })

  it('requires explicit confirmation and removes only the deleted project after success', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAll('.project-card')).toHaveLength(2)
    await wrapper.get('[aria-label="删除项目 检索增强生成研究"]').trigger('click')

    expect(wrapper.get('.delete-confirmation').text()).toContain('检索增强生成研究')
    expect(wrapper.get('.delete-confirmation').text()).toContain('无法撤销')
    const deleteButtons = wrapper.findAll('button').filter(button => button.text() === '删除项目')
    await deleteButtons.at(-1)!.trigger('click')
    await flushPromises()

    expect(deleteProject).toHaveBeenCalledOnce()
    expect(deleteProject).toHaveBeenCalledWith('project-1')
    expect(wrapper.findAll('.project-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('检索增强生成研究')
    expect(wrapper.text()).toContain('引用验证研究')
  })

  it('keeps the project visible when deletion fails', async () => {
    vi.mocked(deleteProject).mockRejectedValueOnce({ response: { data: { detail: '项目正在处理中' } } })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[aria-label="删除项目 检索增强生成研究"]').trigger('click')
    const deleteButtons = wrapper.findAll('button').filter(button => button.text() === '删除项目')
    await deleteButtons.at(-1)!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.project-card')).toHaveLength(2)
    expect(wrapper.get('.delete-confirmation').text()).toContain('检索增强生成研究')
  })
})

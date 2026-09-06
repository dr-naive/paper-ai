import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GlobalTaskCenter from './GlobalTaskCenter.vue'

const store = vi.hoisted(() => ({
  allExecutions: [] as Array<Record<string, unknown>>, runningCount: 1,
  loadGlobal: vi.fn().mockResolvedValue(undefined), loadEvents: vi.fn().mockResolvedValue(undefined),
  loadTrace: vi.fn().mockResolvedValue(undefined), stopStream: vi.fn(), shouldStream: vi.fn().mockReturnValue(false),
  executionEvents: vi.fn().mockReturnValue([]), executionTrace: vi.fn().mockReturnValue(null),
  executionEvaluation: vi.fn().mockReturnValue(null), respond: vi.fn().mockResolvedValue(undefined), act: vi.fn(),
}))
vi.mock('@/stores/executions', () => ({ useExecutionsStore: () => store }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

beforeEach(() => {
  vi.clearAllMocks()
  store.allExecutions = [{ id: 'e', project_id: 'p', goal: '生成研究草稿', status: 'waiting_user',
    updated_at: '2026-09-06T00:00:00', plan_version: 1,
    progress: [{ id: 't', label: '整理可用论文证据', status: 'completed' }],
    blockers: [{ task_id: 't2', context: { options: [
      { result_id: 'r', title: 'Selected research paper', import_available: true },
      { result_id: 'closed', title: 'Unavailable paper', import_available: false },
    ] } }],
  }]
})

describe('goal execution progress', () => {
  it('shows understandable progress and submits only explicit paper selection', async () => {
    const wrapper = mount(GlobalTaskCenter, { global: { stubs: { Teleport: true } } })
    await wrapper.get('.task-trigger').trigger('click')
    await flushPromises()
    await wrapper.get('.task-item').trigger('click')
    await flushPromises()
    expect(wrapper.get('[aria-label="研究进度"]').text()).toContain('整理可用论文证据')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('input')[1].attributes('disabled')).toBeDefined()
    await wrapper.findAll('input')[0].setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(store.respond).toHaveBeenCalledWith('e', ['r'])
    expect(wrapper.text()).not.toMatch(/Worker|ToolCall|DAG|Skill/)
  })

  it('keeps partial and blocked executions visible', async () => {
    store.allExecutions[0].status = 'partial'
    const wrapper = mount(GlobalTaskCenter, { global: { stubs: { Teleport: true } } })
    await wrapper.get('.task-trigger').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('需要处理')
    await wrapper.get('.task-item').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('部分完成')
    expect(wrapper.text()).not.toContain('取消任务')
  })
})

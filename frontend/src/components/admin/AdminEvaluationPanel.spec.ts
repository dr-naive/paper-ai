import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminEvaluationPanel from './AdminEvaluationPanel.vue'
import type { AdminEvaluationDetail, AdminEvaluationRun } from '@/api/admin'

const listAdminEvaluations = vi.hoisted(() => vi.fn())
const startAdminEvaluation = vi.hoisted(() => vi.fn())
const getAdminEvaluation = vi.hoisted(() => vi.fn())

vi.mock('@/api/admin', () => ({
  listAdminEvaluations,
  startAdminEvaluation,
  getAdminEvaluation,
}))

const completedRun: AdminEvaluationRun = {
  id: 'run-1', evaluation_type: 'runtime', status: 'completed', config: {},
  summary: { execution_count: 2 }, attempt_count: 1, max_attempts: 4,
  created_at: '2026-09-07T10:00:00', started_at: '2026-09-07T10:01:00',
  updated_at: '2026-09-07T10:02:00', completed_at: '2026-09-07T10:02:00',
  report_available: true, markdown_available: true, error: null,
}
const detail: AdminEvaluationDetail = {
  ...completedRun,
  report: {
    report_type: 'agent_runtime',
    generated_at: '2026-09-07T10:02:00',
    sample_size: { executions: 2, tasks: 0, tool_calls: 0, model_calls: 0 },
    diagnostic: { analysis_mode: 'insufficient', sample_quality: { label: '样本不足，仅供调试' } },
    summary: { execution_count: 2 },
  },
}

const global = {
  stubs: {
    'a-select': { props: ['modelValue'], template: '<select><slot /></select>' },
    'a-option': { props: ['value'], template: '<option :value="value"><slot /></option>' },
    'a-button': { props: ['loading', 'disabled'], template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>' },
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  listAdminEvaluations.mockResolvedValue({ items: [completedRun] })
  getAdminEvaluation.mockResolvedValue(detail)
  startAdminEvaluation.mockResolvedValue({ ...completedRun, id: 'run-2', status: 'queued', completed_at: null, report_available: false, markdown_available: false })
})

describe('管理员测评面板', () => {
  it('显示历史记录日期和已完成的结构化结果', async () => {
    const wrapper = mount(AdminEvaluationPanel, { global })
    await flushPromises()

    expect(wrapper.text()).toContain('历史测评')
    expect(wrapper.text()).toContain('2026年9月7日')
    expect(wrapper.text()).toContain('运行样本')
    expect(wrapper.text()).toContain('样本不足，仅供调试')
  })

  it('点击开始测评后创建后台运行并读取结果', async () => {
    listAdminEvaluations.mockResolvedValue({ items: [] })
    const queuedRun = { ...completedRun, id: 'run-2', status: 'queued', completed_at: null, report_available: false, markdown_available: false } as AdminEvaluationRun
    startAdminEvaluation.mockResolvedValue(queuedRun)
    getAdminEvaluation.mockResolvedValue({ ...queuedRun, status: 'completed', report: detail.report })
    const wrapper = mount(AdminEvaluationPanel, { global })
    await flushPromises()

    await wrapper.get('.evaluation-controls button').trigger('click')
    await flushPromises()

    expect(startAdminEvaluation).toHaveBeenCalledWith('runtime')
    expect(getAdminEvaluation).toHaveBeenCalledWith('run-2')
    expect(wrapper.text()).toContain('已完成')
  })
})

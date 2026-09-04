import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WritingAgentPanel from './WritingAgentPanel.vue'
import WritingOutlinePanel from './WritingOutlinePanel.vue'

const context = {
  selectionFrom: 12,
  selectionTo: 18,
  selectedText: '样本文本',
  selectedCharacterCount: 4,
  currentHeading: '研究方法',
  sectionPath: ['引言', '研究方法'],
  nearbyText: '附近正文',
}

const agentProps = (overrides: Record<string, unknown> = {}) => ({
  context,
  collapsed: false,
  revisionVersion: 3,
  messages: [],
  proposal: null,
  requestStatus: 'idle' as const,
  requestStage: '',
  requestError: '',
  canSubmit: true,
  replaceDisabled: false,
  replaceDisabledReason: '',
  evidence: [],
  projectId: 'project-1',
  ...overrides,
})

describe('Writing Workspace panels', () => {
  it('shows the current section and selection context in the Agent shell', async () => {
    const wrapper = mount(WritingAgentPanel, { props: agentProps() })
    expect(wrapper.text()).toContain('研究方法')
    expect(wrapper.text()).toContain('引言 / 研究方法')
    expect(wrapper.text()).toContain('已选择 4 字')
    expect(wrapper.text()).toContain('v3')
    await wrapper.get('.panel-toggle').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('keeps the collapsed Agent control accessible', () => {
    const wrapper = mount(WritingAgentPanel, { props: agentProps({ collapsed: true }) })
    expect(wrapper.get('.panel-toggle').attributes('aria-label')).toBe('展开 Writing Agent')
    expect(wrapper.find('.agent-content').exists()).toBe(false)
  })

  it('submits free-form instructions and exposes loading/error feedback', async () => {
    const wrapper = mount(WritingAgentPanel, { props: agentProps() })
    await wrapper.get('#writing-agent-instruction').setValue('请润色得更学术')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toEqual([['请润色得更学术']])

    await wrapper.setProps({ requestStatus: 'error', requestError: '正文已发生变化，请重新选择。' })
    expect(wrapper.get('[role="alert"]').text()).toContain('正文已发生变化')
  })

  it('renders document outline hierarchy and marks the current section', async () => {
    const wrapper = mount(WritingOutlinePanel, {
      props: {
        documents: [{ id: 'document-1', title: '论文草稿', status: 'draft', updated_at: '2026-08-24T00:00:00Z' }] as never,
        activeDocumentId: 'document-1',
        outline: [{ text: '引言', level: 1, pos: 0 }, { text: '研究方法', level: 2, pos: 8 }],
        currentHeading: '研究方法',
        loading: false,
        collapsed: false,
      },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })
    const current = wrapper.get('[aria-current="location"]')
    expect(current.text()).toBe('研究方法')
    expect(current.attributes('style')).toContain('padding-left: 22px')
    await current.trigger('click')
    expect(wrapper.emitted('focus-heading')).toEqual([[8]])
  })

  it('exposes a keyboard-accessible outline collapse control', async () => {
    const wrapper = mount(WritingOutlinePanel, {
      props: { documents: [], outline: [], currentHeading: '正文开头', loading: false, collapsed: false },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.get('.outline-toggle').attributes('aria-label')).toBe('收起论文结构')
    await wrapper.get('.outline-toggle').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })
})

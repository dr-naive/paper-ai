import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Guide from './Guide.vue'
import Home from './Home.vue'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: routerPush }) }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: null,
    validate: vi.fn().mockResolvedValue(null),
    setSession: vi.fn(),
    clearSession: vi.fn(),
  }),
}))

const global = {
  mocks: { $router: { push: routerPush } },
  stubs: {
    ProductHeader: { template: '<header><slot /><slot name="actions" /></header>' },
    BrandMark: { template: '<span>PaperAI</span>' },
    RouterLink: { props: ['to'], template: '<a :data-to="String(to)"><slot /></a>' },
    'a-button': { template: '<button @click="$emit(\'click\')"><slot name="icon" /><slot /></button>' },
    'a-dropdown': { template: '<div><slot /><slot name="content" /></div>' },
    'a-modal': { template: '<div><slot /></div>' },
    'a-form': { template: '<form><slot /></form>' },
    'a-form-item': { template: '<label><slot /></label>' },
    'a-input': { template: '<input />' },
    'a-input-password': { template: '<input />' },
  },
}

afterEach(() => {
  routerPush.mockReset()
  vi.clearAllTimers()
})

describe('public product guidance', () => {
  it('separates the Guide into the implemented user-facing modules', () => {
    const wrapper = mount(Guide, { global })

    expect(wrapper.findAll('.guide-content > section').map(section => section.attributes('id'))).toEqual([
      'overview', 'discover', 'papers', 'writing', 'reader', 'evidence', 'troubleshooting',
    ])
    expect(wrapper.find('.guide-intro').exists()).toBe(false)
    expect(wrapper.find('.entry-paths').exists()).toBe(false)
    expect(wrapper.get('h1').classes()).toContain('pa-sr-only')
    expect(wrapper.get('.guide-nav a').attributes('aria-current')).toBe('location')
    expect(wrapper.text()).toContain('收藏只保存检索元数据')
    expect(wrapper.text()).toContain('明确选择“替换”或“复制”')
    expect(wrapper.text()).toContain('bbox')
    expect(wrapper.text()).not.toContain('Agent Center')
    expect(wrapper.text()).not.toContain('Skill Runtime')
  })

  it('keeps homepage claims and actions aligned with both product modes', async () => {
    vi.useFakeTimers()
    const wrapper = mount(Home, { global })

    expect(wrapper.text()).toContain('从阅读走向写作')
    expect(wrapper.text()).toContain('项目研究的四个阶段')
    expect(wrapper.text()).toContain('真实文献发现')
    expect(wrapper.text()).toContain('论文结构化解析')
    expect(wrapper.text()).toContain('证据支持的写作')
    expect(wrapper.text()).toContain('可追踪的质量检查')
    expect(wrapper.text()).toContain('本地论文库')

    await wrapper.find('.hero-actions button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/projects')
    wrapper.unmount()
  })
})

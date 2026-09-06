import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Guide from './Guide.vue'
import Home from './Home.vue'

const routerPush = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ params: { section: 'overview' } }))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: routerPush }), useRoute: () => routeState }
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
  routeState.params.section = 'overview'
  vi.clearAllTimers()
})

describe('public product guidance', () => {
  it('renders a real documentation shell with task-oriented overview content', () => {
    const wrapper = mount(Guide, { global })

    expect(wrapper.find('.guide-workspace').exists()).toBe(true)
    expect(wrapper.find('.guide-sidebar').exists()).toBe(true)
    expect(wrapper.find('.guide-document').exists()).toBe(true)
    expect(wrapper.findAll('.guide-nav__link')).toHaveLength(7)
    expect(wrapper.get('.guide-nav__link').attributes('aria-current')).toBe('page')
    expect(wrapper.get('h1').text()).toBe('把研究问题变成一个项目')
    expect(wrapper.findAll('.guide-steps li')).toHaveLength(4)
    expect(wrapper.text()).toContain('从哪里开始')
    expect(wrapper.text()).toContain('完成后你会看到')
    expect(wrapper.text()).toContain('点击“创建项目”')
    expect(wrapper.text()).not.toContain('Agent Center')
    expect(wrapper.text()).not.toContain('Skill Runtime')
  })

  it('renders each guide module from its own route section', () => {
    routeState.params.section = 'discover'
    const wrapper = mount(Guide, { global })

    expect(wrapper.get('h1').text()).toBe('在项目中发现真实文献')
    expect(wrapper.findAll('.guide-steps li')).toHaveLength(4)
    expect(wrapper.text()).toContain('收藏、下载和导入的区别')
    expect(wrapper.text()).toContain('年份、语言、领域和出版类型')
    expect(wrapper.get('.guide-nav__link.is-active').text()).toBe('文献发现')
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
    expect(wrapper.text()).toContain('独立阅读')

    await wrapper.find('.hero-actions button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/projects')
    wrapper.unmount()
  })
})

import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProductHeader from './ProductHeader.vue'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: routerPush }) }
})

describe('ProductHeader navigation contract', () => {
  beforeEach(() => routerPush.mockReset())

  it('accepts a typed route location for Back and renders breadcrumb hierarchy', async () => {
    const backTo = { name: 'ProjectPapers', params: { projectId: 'project-1' } }
    const wrapper = mount(ProductHeader, {
      props: {
        showBrand: false,
        backTo,
        backLabel: '项目论文',
        breadcrumbs: [
          { label: '项目' },
          { label: '项目论文' },
          { label: '阅读' },
        ],
      },
      global: {
        stubs: {
          BrandMark: { template: '<span>PaperAI</span>' },
          GlobalTaskCenter: { template: '<span />' },
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
          },
        },
      },
    })

    await wrapper.get('.product-header__back').trigger('click')
    expect(routerPush).toHaveBeenCalledWith(backTo)
    expect(wrapper.get('[aria-label="页面层级"]').text()).toContain('项目论文')
    expect(wrapper.findAll('[aria-current="page"]').at(-1)?.text()).toBe('阅读')
  })
})

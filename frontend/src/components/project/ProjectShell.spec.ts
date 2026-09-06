import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ProjectShell from './ProjectShell.vue'
import type { ResearchProject } from '@/api/projects'

const routeState = vi.hoisted(() => ({ params: { projectId: 'project-1' } }))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRoute: () => routeState }
})

const project: ResearchProject = {
  id: 'project-1',
  user_id: 'user-1',
  title: '检索研究',
  research_topic: '比较检索策略',
  abstract: '',
  phase: 'research',
  status: 'active',
  memory: { summary: '', notes: [] },
  preferences: {},
  research_scope: {
    field: '',
    research_subject: '',
    research_question: '',
    research_goal: '',
    keywords: [],
    method_direction: '',
    notes: '',
  },
}

describe('ProjectShell navigation hierarchy', () => {
  it('keeps Home separate from workspace navigation and removes duplicate shortcuts', () => {
    const wrapper = mount(ProjectShell, {
      props: { recentProjects: [project] },
      global: {
        stubs: {
          BrandMark: { template: '<span>PaperAI</span>' },
          IconApps: { template: '<span />' },
          IconBook: { template: '<span />' },
          IconHome: { template: '<span />' },
          RouterLink: {
            props: ['to', 'title'],
            template: '<a :href="typeof to === \'string\' ? to : \'#\'" :title="title"><slot /></a>',
          },
        },
      },
    })

    expect(wrapper.get('.sidebar-home').text()).toContain('首页')
    expect(wrapper.get('.global-nav__section-label').text()).toBe('工作区')
    expect(wrapper.get('.global-nav').text()).toContain('项目')
    expect(wrapper.get('.global-nav').text()).toContain('独立阅读')
    expect(wrapper.get('.global-nav').findAll('a')).toHaveLength(2)
    expect(wrapper.find('.sidebar-footer').exists()).toBe(false)
  })

  it('keeps the current project state in the contextual Recent Projects group', () => {
    const wrapper = mount(ProjectShell, {
      props: { recentProjects: [project] },
      global: {
        stubs: {
          BrandMark: { template: '<span />' },
          IconApps: { template: '<span />' },
          IconBook: { template: '<span />' },
          IconHome: { template: '<span />' },
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.get('.recent-project').classes()).toContain('is-active')
    expect(wrapper.get('.recent-projects').text()).toContain('检索研究')
  })
})

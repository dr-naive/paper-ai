import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { PaperSearchResult } from '@/api/discovery'
import PaperResultGrid from './PaperResultGrid.vue'

const paper = (id: string): PaperSearchResult => ({
  result_id: id,
  source: 'semantic_scholar',
  source_paper_id: id,
  title: `Paper ${id}`,
  authors: [],
  year: null,
  venue: null,
  abstract: null,
  doi: null,
  paper_url: null,
  pdf_url: null,
  language: null,
  publication_type: null,
  fields: [],
  citation_count: null,
  open_access: null,
  recommendation_reason: null,
  is_favorite: false,
  download_available: false,
  import_available: false,
})

const globalStubs = {
  'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  PaperResultCard: { template: '<article class="paper-card-stub" />' },
}

describe('PaperResultGrid', () => {
  it('renders a truthful zero-result state with next actions', () => {
    const wrapper = mount(PaperResultGrid, {
      props: { status: 'completed', resultCount: 0, favoriteCount: 0, filter: 'all', papers: [], favoritePending: {}, importStates: {}, importMessages: {} },
      global: { stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('没有找到符合当前条件的论文')
    expect(wrapper.text()).toContain('修改搜索条件')
  })

  it('uses the two-column grid container for real results and supports favorites filter', async () => {
    const wrapper = mount(PaperResultGrid, {
      props: { status: 'completed', resultCount: 2, favoriteCount: 1, filter: 'all', papers: [paper('one'), paper('two')], favoritePending: {}, importStates: {}, importMessages: {} },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.paper-grid').exists()).toBe(true)
    expect(wrapper.findAll('.paper-card-stub')).toHaveLength(2)
    await wrapper.get('[role="tab"][aria-selected="false"]').trigger('click')
    expect(wrapper.emitted('update:filter')?.[0]).toEqual(['favorites'])
  })
})

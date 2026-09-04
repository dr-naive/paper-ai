import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { PaperSearchResult } from '@/api/discovery'
import PaperDetailDrawer from './PaperDetailDrawer.vue'

const paper: PaperSearchResult = {
  result_id: 'paper-1',
  source: 'semantic_scholar',
  source_paper_id: 'paper-1',
  title: 'A Reliable Retrieval Study',
  authors: ['Ada Lovelace'],
  year: 2026,
  venue: 'Research Venue',
  abstract: 'Full abstract',
  doi: null,
  paper_url: null,
  pdf_url: null,
  language: 'en',
  publication_type: 'JournalArticle',
  fields: ['Computer Science'],
  citation_count: 8,
  open_access: false,
  recommendation_reason: null,
  is_favorite: false,
  download_available: false,
  import_available: false,
}

describe('PaperDetailDrawer', () => {
  it('emits one close request when the Drawer cancel control is used', async () => {
    const wrapper = mount(PaperDetailDrawer, {
      props: { paper },
      global: {
        stubs: {
          'a-drawer': {
            props: ['visible'],
            emits: ['cancel'],
            template: '<aside :data-visible="visible"><button class="drawer-close" @click="$emit(\'cancel\')">关闭</button><slot /></aside>',
          },
          'a-button': { template: '<button><slot /></button>' },
          'a-tooltip': { template: '<span><slot /></span>' },
        },
      },
    })

    expect(wrapper.get('aside').attributes('data-visible')).toBe('true')
    await wrapper.get('.drawer-close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})

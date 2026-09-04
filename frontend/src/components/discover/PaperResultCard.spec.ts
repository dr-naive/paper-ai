import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { PaperSearchResult } from '@/api/discovery'
import PaperResultCard from './PaperResultCard.vue'

const paper: PaperSearchResult = {
  result_id: 'result-1',
  source: 'doi',
  source_paper_id: '10.1234/example',
  title: 'A Paper With A Complete Abstract',
  authors: ['Ada Lovelace', 'Alan Turing'],
  year: 2024,
  venue: 'Research Venue',
  abstract: 'A'.repeat(320),
  doi: '10.1234/example',
  paper_url: 'https://example.com/paper',
  pdf_url: null,
  language: 'en',
  publication_type: 'JournalArticle',
  fields: ['Computer Science'],
  citation_count: 12,
  open_access: false,
  recommendation_reason: 'Directly relevant.',
  is_favorite: false,
  download_available: false,
  import_available: false,
}

const mountCard = () => mount(PaperResultCard, {
  props: { paper },
  global: {
    stubs: {
      'a-button': {
        props: ['disabled', 'loading'],
        template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
      },
      'a-tooltip': { template: '<span><slot /></span>' },
    },
  },
})

describe('PaperResultCard', () => {
  it('clamps long abstracts by default and allows keyboard-accessible expansion', async () => {
    const wrapper = mountCard()
    const abstract = wrapper.get('.paper-abstract p')
    expect(abstract.classes()).not.toContain('is-expanded')
    expect(wrapper.get('.expand-button').text()).toBe('展开')

    await wrapper.get('.expand-button').trigger('click')
    expect(abstract.classes()).toContain('is-expanded')
    expect(wrapper.get('.expand-button').text()).toBe('收起')
    expect(wrapper.get('.expand-button').attributes('aria-expanded')).toBe('true')
  })

  it('keeps unavailable download and import actions disabled in their fixed slots', () => {
    const wrapper = mountCard()
    expect(wrapper.get('button[aria-label="暂无可用下载链接"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[aria-label="暂无可导入的论文全文"]').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('.action-button')).toHaveLength(4)
  })
})

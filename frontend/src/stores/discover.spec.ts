import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  importDiscoveryPaper,
  listDiscoveryFavorites,
  removeDiscoveryFavorite,
  saveDiscoveryFavorite,
  searchLiterature,
  type PaperSearchResult,
} from '@/api/discovery'
import { useDiscoverStore } from './discover'

vi.mock('@/api/discovery', async () => {
  const actual = await vi.importActual<typeof import('@/api/discovery')>('@/api/discovery')
  return {
    ...actual,
    importDiscoveryPaper: vi.fn(),
    listDiscoveryFavorites: vi.fn(),
    removeDiscoveryFavorite: vi.fn(),
    saveDiscoveryFavorite: vi.fn(),
    searchLiterature: vi.fn(),
  }
})

const mockedSearch = vi.mocked(searchLiterature)
const mockedListFavorites = vi.mocked(listDiscoveryFavorites)
const mockedSaveFavorite = vi.mocked(saveDiscoveryFavorite)
const mockedRemoveFavorite = vi.mocked(removeDiscoveryFavorite)
const mockedImport = vi.mocked(importDiscoveryPaper)

const result = (overrides: Partial<PaperSearchResult> = {}): PaperSearchResult => ({
  result_id: 'result-1',
  source: 'arxiv',
  source_paper_id: '2401.12345',
  title: 'A Retrieval Study',
  authors: ['Ada Lovelace'],
  year: 2024,
  venue: 'Research Venue',
  abstract: 'A complete abstract',
  doi: null,
  paper_url: 'https://arxiv.org/abs/2401.12345',
  pdf_url: 'https://arxiv.org/pdf/2401.12345.pdf',
  language: 'en',
  publication_type: 'JournalArticle',
  fields: ['Computer Science'],
  citation_count: 12,
  open_access: true,
  recommendation_reason: 'Directly relevant.',
  is_favorite: false,
  download_available: true,
  import_available: true,
  ...overrides,
})

describe('discover store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedSearch.mockReset()
    mockedListFavorites.mockReset()
    mockedSaveFavorite.mockReset()
    mockedRemoveFavorite.mockReset()
    mockedImport.mockReset()
  })

  it('seeds a clarifying session from the project profile', () => {
    const store = useDiscoverStore()
    store.reset('project-1', '生成式 AI 与大学生学习', {
      field: 'Education',
      research_question: '影响是什么？',
      keywords: ['generative AI'],
      method_direction: 'empirical study',
    })

    expect(store.status).toBe('clarifying')
    expect(store.searchIntent.topic).toBe('生成式 AI 与大学生学习')
    expect(store.searchIntent.target_contexts).toEqual(['Education'])
    expect(store.searchIntent.preferred_methods).toEqual(['empirical study'])
    expect(store.messages[0].role).toBe('assistant')
  })

  it('turns a user requirement into an editable ready intent', () => {
    const store = useDiscoverStore()
    store.reset('project-1')

    expect(store.submitRequirement('  找大学生使用生成式 AI 的实证研究  ')).toBe(true)
    expect(store.status).toBe('ready_for_search')
    expect(store.searchIntent.topic).toBe('找大学生使用生成式 AI 的实证研究')
    expect(store.messages[store.messages.length - 1]?.role).toBe('assistant')
    expect(store.canSearch).toBe(true)
  })

  it('submits typed intent and filters, then exposes a truthful result summary', async () => {
    mockedSearch.mockResolvedValue({
      execution_id: 'execution-1',
      provider: 'semantic_scholar',
      result_count: 2,
      search_rounds: 2,
      warnings: ['语言筛选未被当前 Provider 支持'],
      papers: [],
    })
    const store = useDiscoverStore()
    store.reset('project-1')
    store.submitRequirement('生成式 AI 对学习动机的影响')
    store.setIntent({ research_question: '对大学生是否有影响？' })
    store.setFilters({ year_from: 2020, year_to: 2026, fields: ['Education'] })

    await expect(store.submitSearch()).resolves.toBe(true)
    expect(mockedSearch).toHaveBeenCalledWith('project-1', {
      intent: expect.objectContaining({ topic: '生成式 AI 对学习动机的影响', research_question: '对大学生是否有影响？' }),
      filters: expect.objectContaining({ year_from: 2020, year_to: 2026, fields: ['Education'] }),
      max_results: 10,
    })
    expect(store.status).toBe('completed')
    expect(store.executionId).toBe('execution-1')
    expect(store.resultCount).toBe(2)
    expect(store.searchRounds).toBe(2)
    expect(store.warnings).toEqual(['语言筛选未被当前 Provider 支持'])
  })

  it('maps provider failures to a user-readable failed state without retrying', async () => {
    mockedSearch.mockRejectedValue({ response: { data: { detail: { message: '论文搜索服务暂时不可用，请稍后重试。' } } } })
    const store = useDiscoverStore()
    store.reset('project-1')
    store.submitRequirement('寻找可靠的教育研究')

    await expect(store.submitSearch()).resolves.toBe(false)
    expect(store.status).toBe('failed')
    expect(store.statusMessage).toBe('论文搜索服务暂时不可用')
    expect(store.errorMessage).toBe('论文搜索服务暂时不可用，请稍后重试。')
    expect(mockedSearch).toHaveBeenCalledTimes(1)
  })

  it('persists favorite state through the project-scoped API and supports filtering', async () => {
    mockedSearch.mockResolvedValue({ execution_id: 'execution-1', provider: 'arxiv', result_count: 1, search_rounds: 1, warnings: [], papers: [result()] })
    mockedSaveFavorite.mockResolvedValue({ ...result(), favorite_id: 'favorite-1', saved_at: '2026-08-23T00:00:00Z' })
    mockedRemoveFavorite.mockResolvedValue({ favorite_id: 'favorite-1', removed: true })
    const store = useDiscoverStore()
    store.reset('project-1')
    store.submitRequirement('检索可复现的检索研究')
    await store.submitSearch()

    await expect(store.toggleFavorite(store.results[0])).resolves.toBe(true)
    expect(mockedSaveFavorite).toHaveBeenCalledWith('project-1', expect.objectContaining({ source: 'arxiv', source_paper_id: '2401.12345' }))
    expect(store.results[0].is_favorite).toBe(true)
    expect(store.favoriteCount).toBe(1)

    store.setFavoriteFilter('favorites')
    expect(store.visibleResults).toHaveLength(1)
    await expect(store.toggleFavorite(store.results[0])).resolves.toBe(true)
    expect(mockedRemoveFavorite).toHaveBeenCalledWith('project-1', 'favorite-1')
    expect(store.visibleResults).toHaveLength(0)
  })

  it('keeps import progress explicit and does not invent a completed state', async () => {
    const paper = result()
    mockedSearch.mockResolvedValue({ execution_id: 'execution-1', provider: 'arxiv', result_count: 1, search_rounds: 1, warnings: [], papers: [paper] })
    mockedImport.mockResolvedValue({ source: 'arxiv', source_paper_id: paper.source_paper_id, status: 'processing', message: '正在导入，task_id=task-1', task_id: 'task-1', paper_id: null })
    const store = useDiscoverStore()
    store.reset('project-1')
    store.submitRequirement('检索可复现的检索研究')
    await store.submitSearch()

    await expect(store.importPaper(store.results[0])).resolves.toBe(true)
    expect(mockedImport).toHaveBeenCalledWith('project-1', expect.objectContaining({ source: 'arxiv', source_paper_id: '2401.12345', result_id: 'result-1' }))
    expect(store.importStates['result-1']).toBe('importing')
    expect(store.importMessages['result-1']).toContain('正在导入')
    await expect(store.importPaper(store.results[0])).resolves.toBe(false)
    expect(mockedImport).toHaveBeenCalledTimes(1)
  })

  it('resolves a favorite id before unfavoriting a result returned by search', async () => {
    const paper = result({ is_favorite: true })
    mockedSearch.mockResolvedValue({ execution_id: 'execution-1', provider: 'arxiv', result_count: 1, search_rounds: 1, warnings: [], papers: [paper] })
    mockedListFavorites.mockResolvedValue([{ ...paper, favorite_id: 'favorite-2', saved_at: '2026-08-23T00:00:00Z' }])
    mockedRemoveFavorite.mockResolvedValue({ favorite_id: 'favorite-2', removed: true })
    const store = useDiscoverStore()
    store.reset('project-1')
    store.submitRequirement('检索可复现的检索研究')
    await store.submitSearch()

    await expect(store.toggleFavorite(store.results[0])).resolves.toBe(true)
    expect(mockedListFavorites).toHaveBeenCalledWith('project-1')
    expect(mockedRemoveFavorite).toHaveBeenCalledWith('project-1', 'favorite-2')
  })
})

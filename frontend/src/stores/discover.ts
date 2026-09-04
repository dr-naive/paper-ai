import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  importDiscoveryPaper,
  listDiscoveryFavorites,
  removeDiscoveryFavorite,
  saveDiscoveryFavorite,
  searchLiterature,
  type DiscoveryFavoriteRequest,
  type PaperSearchResult,
  type SearchFilters,
  type SearchIntent,
} from '@/api/discovery'
import { getTaskStatus } from '@/api/paper'

export type DiscoveryStatus =
  | 'idle'
  | 'clarifying'
  | 'ready_for_search'
  | 'searching'
  | 'completed'
  | 'failed'

export interface RequirementMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
}

export type FavoriteFilter = 'all' | 'favorites'
export type ImportState = 'idle' | 'importing' | 'imported' | 'failed'

const IMPORT_POLL_INTERVAL_MS = 1500
// Remote import includes a bounded download (up to five minutes) followed by
// the existing parse/index pipeline. Keep the UI monitor bounded, but long
// enough to observe the Worker-owned terminal state on slower direct links.
const IMPORT_POLL_ATTEMPTS = 400

const emptyIntent = (): SearchIntent => ({
  topic: '',
  research_question: null,
  keywords: [],
  preferred_methods: [],
  target_contexts: [],
})

const emptyFilters = (): SearchFilters => ({
  year_from: null,
  year_to: null,
  language: null,
  fields: [],
  publication_types: [],
})

const initialAssistantMessage = '你想找哪一类论文？可以先描述研究主题、对象或你关心的问题。'

export const useDiscoverStore = defineStore('discover', () => {
  const projectId = ref('')
  const messages = ref<RequirementMessage[]>([])
  const searchIntent = ref<SearchIntent>(emptyIntent())
  const filters = ref<SearchFilters>(emptyFilters())
  const status = ref<DiscoveryStatus>('idle')
  const statusMessage = ref('')
  const errorMessage = ref('')
  const executionId = ref('')
  const provider = ref('')
  const searchRounds = ref(0)
  const resultCount = ref(0)
  const warnings = ref<string[]>([])
  const results = ref<PaperSearchResult[]>([])
  const favoriteFilter = ref<FavoriteFilter>('all')
  const favoriteIds = ref<Record<string, string>>({})
  const favoritePending = ref<Record<string, boolean>>({})
  const importStates = ref<Record<string, ImportState>>({})
  const importMessages = ref<Record<string, string>>({})
  const actionError = ref('')
  const activePaper = ref<PaperSearchResult | null>(null)
  const importWatchTokens = new Map<string, number>()

  const isWorking = computed(() => status.value === 'searching')
  const isReady = computed(() => status.value === 'ready_for_search' || status.value === 'completed' || status.value === 'failed')
  const canSearch = computed(() => Boolean(searchIntent.value.topic.trim()) && !isWorking.value)
  const favoriteCount = computed(() => results.value.filter(item => item.is_favorite).length)
  const visibleResults = computed(() => favoriteFilter.value === 'favorites' ? results.value.filter(item => item.is_favorite) : results.value)

  const reset = (id: string, topic = '', scope?: { field?: string; research_question?: string; keywords?: string[]; method_direction?: string }) => {
    projectId.value = id
    const normalizedTopic = topic.trim()
    searchIntent.value = {
      ...emptyIntent(),
      topic: normalizedTopic,
      research_question: scope?.research_question?.trim() || null,
      keywords: scope?.keywords || [],
      preferred_methods: scope?.method_direction ? [scope.method_direction] : [],
      target_contexts: scope?.field ? [scope.field] : [],
    }
    filters.value = emptyFilters()
    status.value = normalizedTopic ? 'clarifying' : 'idle'
    statusMessage.value = ''
    errorMessage.value = ''
    executionId.value = ''
    provider.value = ''
    searchRounds.value = 0
    resultCount.value = 0
    warnings.value = []
    results.value = []
    favoriteFilter.value = 'all'
    favoriteIds.value = {}
    favoritePending.value = {}
    importStates.value = {}
    importMessages.value = {}
    importWatchTokens.clear()
    actionError.value = ''
    activePaper.value = null
    messages.value = [{ id: 'assistant-1', role: 'assistant', content: initialAssistantMessage }]
  }

  const setIntent = (value: Partial<SearchIntent>) => {
    searchIntent.value = {
      ...searchIntent.value,
      ...value,
      topic: String(value.topic ?? searchIntent.value.topic),
      keywords: value.keywords ?? searchIntent.value.keywords,
      preferred_methods: value.preferred_methods ?? searchIntent.value.preferred_methods,
      target_contexts: value.target_contexts ?? searchIntent.value.target_contexts,
    }
  }

  const setFilters = (value: Partial<SearchFilters>) => {
    filters.value = {
      ...filters.value,
      ...value,
      fields: value.fields ?? filters.value.fields,
      publication_types: value.publication_types ?? filters.value.publication_types,
    }
  }

  const submitRequirement = (content: string) => {
    const text = content.trim()
    if (!text || isWorking.value) return false
    messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: text })
    setIntent({ topic: text })
    status.value = 'ready_for_search'
    statusMessage.value = '已整理检索需求，请确认或修改搜索条件。'
    messages.value.push({
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '我已把这段描述整理成检索需求。你可以先修改 Search Intent 和筛选条件，再开始搜索。',
    })
    return true
  }

  const markClarifying = () => { status.value = 'clarifying' }

  const submitSearch = async (id = projectId.value) => {
    if (!canSearch.value || !id) return false
    projectId.value = id
    status.value = 'searching'
    statusMessage.value = '正在搜索相关论文并筛选结果'
    errorMessage.value = ''
    warnings.value = []
    actionError.value = ''
    results.value = []
    resultCount.value = 0
    searchRounds.value = 0
    try {
      const response = await searchLiterature(id, {
        intent: searchIntent.value,
        filters: filters.value,
        max_results: 10,
      })
      executionId.value = response.execution_id
      provider.value = response.provider
      searchRounds.value = response.search_rounds
      resultCount.value = response.result_count
      warnings.value = response.warnings || []
      results.value = (response.papers || []).map(item => favoriteIds.value[item.result_id] ? { ...item, is_favorite: true } : item)
      status.value = 'completed'
      statusMessage.value = response.result_count
        ? `已完成检索，找到 ${response.result_count} 篇论文`
        : '检索完成，但没有找到符合条件的论文'
      return true
    } catch (error: any) {
      status.value = 'failed'
      statusMessage.value = '论文搜索服务暂时不可用'
      errorMessage.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || '请稍后重试。'
      return false
    }
  }

  const setFavoriteFilter = (value: FavoriteFilter) => { favoriteFilter.value = value }

  const updateResult = (resultId: string, update: Partial<PaperSearchResult>) => {
    results.value = results.value.map(item => item.result_id === resultId ? { ...item, ...update } : item)
    if (activePaper.value?.result_id === resultId) activePaper.value = { ...activePaper.value, ...update }
  }

  const favoritePayload = (paper: PaperSearchResult): DiscoveryFavoriteRequest => ({
    result_id: paper.result_id,
    source: paper.source,
    source_paper_id: paper.source_paper_id,
    title: paper.title,
    authors: paper.authors,
    year: paper.year,
    venue: paper.venue,
    abstract: paper.abstract,
    doi: paper.doi,
    paper_url: paper.paper_url,
    pdf_url: paper.pdf_url,
    language: paper.language,
    publication_type: paper.publication_type,
    fields: paper.fields,
    citation_count: paper.citation_count,
    open_access: paper.open_access,
  })

  const loadFavorites = async (id = projectId.value) => {
    if (!id) return []
    const records = await listDiscoveryFavorites(id)
    const mapping: Record<string, string> = {}
    records.forEach(record => {
      mapping[record.result_id] = record.favorite_id
    })
    favoriteIds.value = { ...favoriteIds.value, ...mapping }
    records.forEach(record => updateResult(record.result_id, { is_favorite: true }))
    return records
  }

  const toggleFavorite = async (paper: PaperSearchResult) => {
    if (!projectId.value || favoritePending.value[paper.result_id]) return false
    favoritePending.value = { ...favoritePending.value, [paper.result_id]: true }
    actionError.value = ''
    try {
      if (paper.is_favorite) {
        let favoriteId: string | undefined = favoriteIds.value[paper.result_id]
        if (!favoriteId) {
          const records = await loadFavorites()
          favoriteId = records.find(record => record.result_id === paper.result_id)?.favorite_id
        }
        if (!favoriteId) throw new Error('无法定位收藏记录，请刷新后重试。')
        await removeDiscoveryFavorite(projectId.value, favoriteId)
        const nextIds = { ...favoriteIds.value }
        delete nextIds[paper.result_id]
        favoriteIds.value = nextIds
        updateResult(paper.result_id, { is_favorite: false })
      } else {
        const saved = await saveDiscoveryFavorite(projectId.value, favoritePayload(paper))
        favoriteIds.value = { ...favoriteIds.value, [paper.result_id]: saved.favorite_id }
        updateResult(paper.result_id, { is_favorite: true })
      }
      return true
    } catch (error: any) {
      actionError.value = error?.response?.data?.detail || error?.message || '收藏操作失败，请稍后重试。'
      return false
    } finally {
      const pending = { ...favoritePending.value }
      delete pending[paper.result_id]
      favoritePending.value = pending
    }
  }

  const importPaper = async (paper: PaperSearchResult) => {
    if (!projectId.value || !paper.import_available || paper.source.toLowerCase() !== 'arxiv' || importStates.value[paper.result_id] === 'importing') return false
    importStates.value = { ...importStates.value, [paper.result_id]: 'importing' }
    importMessages.value = { ...importMessages.value, [paper.result_id]: '正在提交导入任务…' }
    actionError.value = ''
    try {
      const response = await importDiscoveryPaper(projectId.value, {
        source: 'arxiv',
        source_paper_id: paper.source_paper_id,
        approved_pdf_locator: paper.pdf_url || undefined,
        result_id: paper.result_id,
      })
      const nextState: ImportState = response.status === 'failed' ? 'failed' : response.status === 'imported' ? 'imported' : 'importing'
      importStates.value = { ...importStates.value, [paper.result_id]: nextState }
      importMessages.value = { ...importMessages.value, [paper.result_id]: response.message }
      // A duplicate import can return the existing task without a paper_id.
      // The owned task-status endpoint resolves the paper identity, so task_id
      // alone is sufficient to keep the UI state truthful and recoverable.
      if (nextState === 'importing' && response.task_id) {
        const token = (importWatchTokens.get(paper.result_id) || 0) + 1
        importWatchTokens.set(paper.result_id, token)
        void monitorImport(paper.result_id, response.task_id, token, projectId.value)
      }
      return nextState !== 'failed'
    } catch (error: any) {
      importStates.value = { ...importStates.value, [paper.result_id]: 'failed' }
      importMessages.value = { ...importMessages.value, [paper.result_id]: error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || '导入失败，请稍后重试。' }
      return false
    }
  }

  const monitorImport = async (resultId: string, taskId: string, token: number, watchedProjectId: string) => {
    const isCurrent = () => importWatchTokens.get(resultId) === token
      && importStates.value[resultId] === 'importing'
      && projectId.value === watchedProjectId

    for (let attempt = 0; attempt < IMPORT_POLL_ATTEMPTS && isCurrent(); attempt += 1) {
      if (attempt > 0) await new Promise(resolve => window.setTimeout(resolve, IMPORT_POLL_INTERVAL_MS))
      if (!isCurrent()) return
      try {
        const task = await getTaskStatus(taskId)
        if (!isCurrent()) return
        // `ready` means the core Reader/RAG assets are available, but the
        // arXiv Worker attaches ProjectPaper only after the shared media stage
        // reaches its terminal `completed` state. Keep polling so Discover
        // never reports an import before it appears in Project Papers.
        if (task.status === 'completed') {
          importStates.value = { ...importStates.value, [resultId]: 'imported' }
          importMessages.value = { ...importMessages.value, [resultId]: task.message || '论文已导入项目，可在项目论文中打开。' }
          return
        }
        if (task.status === 'failed') {
          importStates.value = { ...importStates.value, [resultId]: 'failed' }
          importMessages.value = { ...importMessages.value, [resultId]: task.message || '论文解析失败，请稍后重试。' }
          return
        }
        importMessages.value = {
          ...importMessages.value,
          [resultId]: task.message || `正在导入…${task.progress ? ` ${task.progress}%` : ''}`,
        }
      } catch (error: any) {
        if (!isCurrent()) return
        const statusCode = error?.response?.status ?? error?.status
        if (statusCode === 401 || statusCode === 403 || statusCode === 404) {
          importStates.value = { ...importStates.value, [resultId]: 'failed' }
          importMessages.value = { ...importMessages.value, [resultId]: '导入任务不可用，请刷新后重试。' }
          return
        }
        importMessages.value = { ...importMessages.value, [resultId]: '正在确认导入进度…' }
      }
    }

    if (isCurrent()) {
      importMessages.value = { ...importMessages.value, [resultId]: '导入仍在处理中，请稍后到项目论文中刷新。' }
    }
  }

  const openPaperDetails = (paper: PaperSearchResult) => { activePaper.value = paper }
  const closePaperDetails = () => { activePaper.value = null }

  return {
    projectId,
    messages,
    searchIntent,
    filters,
    status,
    statusMessage,
    errorMessage,
    executionId,
    provider,
    searchRounds,
    resultCount,
    warnings,
    results,
    favoriteFilter,
    favoriteCount,
    visibleResults,
    favoriteIds,
    favoritePending,
    importStates,
    importMessages,
    actionError,
    activePaper,
    isWorking,
    isReady,
    canSearch,
    reset,
    setIntent,
    setFilters,
    submitRequirement,
    markClarifying,
    submitSearch,
    setFavoriteFilter,
    loadFavorites,
    toggleFavorite,
    importPaper,
    openPaperDetails,
    closePaperDetails,
  }
})

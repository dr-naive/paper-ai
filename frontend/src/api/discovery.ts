import request from './index'

export interface SearchIntent {
  topic: string
  research_question: string | null
  keywords: string[]
  preferred_methods: string[]
  target_contexts: string[]
}

export interface SearchFilters {
  year_from: number | null
  year_to: number | null
  language: string | null
  fields: string[]
  publication_types: string[]
}

export interface DiscoverySearchRequest {
  intent: SearchIntent
  filters: SearchFilters
  max_results: number
}

export interface PaperSearchResult {
  result_id: string
  source: string
  source_paper_id: string
  title: string
  authors: string[]
  year: number | null
  venue: string | null
  abstract: string | null
  doi: string | null
  paper_url: string | null
  pdf_url: string | null
  language: string | null
  publication_type: string | null
  fields: string[]
  citation_count: number | null
  open_access: boolean | null
  recommendation_reason: string | null
  is_favorite: boolean
  download_available: boolean
  import_available: boolean
}

export interface DiscoverySearchResponse {
  execution_id: string
  papers: PaperSearchResult[]
  provider: string
  result_count: number
  search_rounds: number
  warnings: string[]
}

export interface DiscoveryExecutionState {
  execution_id: string
  project_id: string
  status: string
  stage: string
  message: string
  search_rounds: number
  result_count: number
  warnings: string[]
  papers: PaperSearchResult[]
  error?: string
}

export interface DiscoveryFavoriteRequest {
  result_id: string
  source: string
  source_paper_id: string
  title: string
  authors: string[]
  year: number | null
  venue: string | null
  abstract: string | null
  doi: string | null
  paper_url: string | null
  pdf_url: string | null
  language: string | null
  publication_type: string | null
  fields: string[]
  citation_count: number | null
  open_access: boolean | null
}

export interface DiscoveryFavorite extends DiscoveryFavoriteRequest {
  favorite_id: string
  saved_at: string
  download_available: boolean
  import_available: boolean
}

export interface DiscoveryImportRequest {
  source: 'arxiv'
  source_paper_id: string
  approved_pdf_locator?: string
  result_id?: string
  role?: 'core' | 'related' | 'background'
  tags?: string[]
  notes?: string
  reading_priority?: number
}

export interface DiscoveryImportResponse {
  source: 'arxiv'
  source_paper_id: string
  status: 'queued' | 'processing' | 'imported' | 'failed'
  message: string
  task_id: string | null
  paper_id: string | null
}

export const searchLiterature = (projectId: string, data: DiscoverySearchRequest) =>
  request.post<DiscoverySearchResponse>(`/api/v1/projects/${projectId}/discovery/search`, data)

export const getDiscoveryExecution = (projectId: string, executionId: string) =>
  request.get<DiscoveryExecutionState>(`/api/v1/projects/${projectId}/discovery/executions/${executionId}`)

export const listDiscoveryFavorites = (projectId: string) =>
  request.get<DiscoveryFavorite[]>(`/api/v1/projects/${projectId}/discovery/favorites`)

export const saveDiscoveryFavorite = (projectId: string, data: DiscoveryFavoriteRequest) =>
  request.post<DiscoveryFavorite>(`/api/v1/projects/${projectId}/discovery/favorites`, data)

export const removeDiscoveryFavorite = (projectId: string, favoriteId: string) =>
  request.delete<{ favorite_id: string; removed: boolean }>(`/api/v1/projects/${projectId}/discovery/favorites/${favoriteId}`)

export const importDiscoveryPaper = (projectId: string, data: DiscoveryImportRequest) =>
  request.post<DiscoveryImportResponse>(`/api/v1/projects/${projectId}/discovery/import`, data)

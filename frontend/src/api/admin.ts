import request from './index'

export interface AdminDashboardData {
  generated_at: string
  system: {
    database: 'healthy' | 'degraded'
    redis: 'healthy' | 'degraded'
    worker: 'healthy' | 'degraded'
  }
  users: {
    total: number
    active: number
    admins: number
    disabled: number
    new_7d: number
  }
  usage: {
    papers_total: number
    papers_7d: number
    sessions_total: number
    questions_total: number
    questions_today: number
  }
  ai: {
    answer_runs: number
    successful_runs: number
    success_rate: number | null
    thinking_tokens: number
    answer_tokens: number
    total_tokens: number
    avg_total_ms: number | null
    avg_first_token_ms: number | null
    avg_retrieval_ms: number | null
    citations_total: number
    token_count_type: 'estimated'
  }
  trend: Array<{
    date: string
    papers: number
    questions: number
    tokens: number
  }>
  evaluations: {
    retrieval: EvaluationReport | null
    e2e: EvaluationReport | null
  }
  recent: {
    users: Array<{
      id: string
      username: string
      role: 'admin' | 'user'
      is_active: boolean
      created_at: string
    }>
    papers: Array<{
      id: string
      title: string
      username: string
      uploaded_at: string
    }>
  }
}

interface EvaluationReport {
  name: string
  generated_at: string | null
  summary: Record<string, number | null>
}

export const getAdminDashboard = () =>
  request.get<AdminDashboardData>('/api/admin/dashboard')

// ==================== 链路追踪 API ====================

export interface TraceListItem {
  trace_id: string
  task_id: string
  user_id: string
  username: string
  session_id: string
  status: string
  total_ms: number | null
  first_token_ms: number | null
  retrieval_ms: number | null
  thinking_tokens: number
  answer_tokens: number
  model_calls: number
  retry_count: number
  citation_count: number
  recorded_at: string | null
}

export interface TraceListStats {
  count: number
  first_token_ms: { p50: number | null; p90: number | null; p95: number | null }
  total_ms: { p50: number | null; p90: number | null; p95: number | null }
}

export interface TraceListResponse {
  total: number
  page: number
  page_size: number
  items: TraceListItem[]
  stats: TraceListStats
}

export interface TraceDetailResponse {
  trace_id: string
  task_id: string
  user: { id: string; username: string | null }
  session: { id: string; title: string | null }
  status: string
  total_ms: number | null
  first_token_ms: number | null
  retrieval_ms: number | null
  thinking_tokens: number
  answer_tokens: number
  citation_count: number
  model_calls: number
  retry_count: number
  used_second_pass: boolean
  recorded_at: string | null
  question: string | null
  answer: string | null
  retrieval_query: string | null
  retrieval_top_k: number | null
  intent: string | null
  iterations: number | null
  tool_calls: Array<{ name: string; args: any; elapsed_ms: number; ok: boolean }> | null
  intent_analysis: any
  fast_path: boolean | null
  failure_stage: string | null
  worker_retry_count: number | null
}

export const listTraces = (params: {
  page?: number
  page_size?: number
  status?: string
  user_id?: string
  min_total_ms?: number
  max_age_days?: number
}) => request.get<TraceListResponse>('/api/admin/traces', { params })

export const getTraceDetail = (traceId: string) =>
  request.get<TraceDetailResponse>(`/api/admin/traces/${traceId}`)

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

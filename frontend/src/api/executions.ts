import request from './index'
import type { WritingGenerateRequest, WritingGenerationProposal } from './documents'

export interface AgentExecution {
  id: string
  project_id?: string | null
  agent_type: string
  goal: string
  status: 'pending' | 'queued' | 'running' | 'waiting_user' | 'paused' | 'retrying' | 'completed' | 'partial' | 'blocked' | 'failed' | 'cancelled'
  plan_version?: number
  progress?: Array<{ id: string; label: string; status: AgentExecution['status'] }> | null
  blockers?: Array<{ task_id?: string; context?: { prompt?: string; options?: Array<{ result_id: string; title: string; import_available: boolean }> } }> | null
  current_stage?: string | null
  active_skill?: string | null
  tool_call_count: number
  model_call_count: number
  created_at: string
  updated_at: string
  completed_at?: string | null
  error_message?: string | null
  input_payload: Record<string, unknown>
  result_payload?: {
    proposal?: WritingGenerationProposal
    completion?: Record<string, unknown>
  } | null
}

export interface WritingExecutionCreate {
  agent_type: 'writing_generate'
  goal: string
  input: WritingGenerateRequest
}

export type ResearchGoalType = 'READ_PAPERS' | 'WRITE_SECTION' | 'DISCOVER_AND_IMPORT'

export interface ResearchGoalInput {
  goal_type: ResearchGoalType
  paper_ids?: string[]
  evidence_ids?: string[]
  document_id?: string | null
  base_revision_id?: string | null
  instruction?: string
  section_path?: string[]
  nearby_text?: string
  citation_style?: 'apa' | 'ieee' | 'gbt7714'
  search?: Record<string, unknown> | null
  require_import_confirmation?: boolean
}

export interface ResearchExecutionCreate {
  agent_type: 'research_goal'
  goal: string
  input: ResearchGoalInput
}

export interface AgentEvent {
  id: string
  seq: number
  execution_id: string
  type: string
  timestamp: string
  stage?: string | null
  message: string
  data: Record<string, unknown>
}

export interface ExecutionTraceReport {
  trace_id: string
  status: AgentExecution['status']
  total_ms?: number | null
  budget: {
    tool_calls: { used: number; limit: number }
    model_calls: { used: number; limit: number }
    tokens: { input: number; output: number; limit: number }
  }
  quality: {
    completion_gate_passed: boolean
    proposal_status?: string | null
    citation_count: number
    verified_count: number
    weak_count: number
    unsupported_count: number
    skill_id?: string | null
    skill_completion_passed?: boolean
    reviewer_status?: string | null
    repair_count?: number
  }
}

export interface ExecutionEvaluation {
  evaluation_version: string
  trace_id: string
  verdict: 'pass' | 'fail' | 'incomplete'
  score: number
  maximum_score: number
  checks: Array<{ name: string; passed: boolean; earned: number; maximum: number; detail: string }>
}

export const listProjectExecutions = (projectId: string, limit = 50) =>
  request.get<{ items: AgentExecution[] }>(`/api/v1/projects/${projectId}/executions`, { params: { limit } })

export const listUserExecutions = (limit = 100) =>
  request.get<{ items: AgentExecution[] }>('/api/v1/executions', { params: { limit } })

export const createWritingExecution = (projectId: string, data: WritingExecutionCreate) =>
  request.post<AgentExecution>(`/api/v1/projects/${projectId}/executions`, data)

export const createResearchExecution = (projectId: string, data: ResearchExecutionCreate) =>
  request.post<AgentExecution>(`/api/v1/projects/${projectId}/executions`, data)

export const listExecutionEvents = (executionId: string, after = 0) =>
  request.get<{ items: AgentEvent[] }>(`/api/v1/executions/${executionId}/events`, { params: { after } })

export const getExecutionTrace = (executionId: string) =>
  request.get<ExecutionTraceReport>(`/api/v1/executions/${executionId}/trace`)

export const getExecutionEvaluation = (executionId: string) =>
  request.get<ExecutionEvaluation>(`/api/v1/executions/${executionId}/evaluation`)

export const streamExecutionEvents = async (
  executionId: string,
  after: number,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
) => {
  const token = localStorage.getItem('access_token')
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  const response = await fetch(`${baseURL}/api/v1/executions/${encodeURIComponent(executionId)}/stream?after=${after}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  })
  if (!response.ok) throw new Error(`恢复任务事件失败 (${response.status})`)
  if (!response.body) throw new Error('当前浏览器不支持任务事件流')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const dispatch = (block: string) => {
    const data = block.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
    if (data) onEvent(JSON.parse(data) as AgentEvent)
  }
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    blocks.forEach(dispatch)
    if (done) break
  }
  if (buffer.trim()) dispatch(buffer)
}

export const cancelExecution = (executionId: string) => request.post<AgentExecution>(`/api/v1/executions/${executionId}/cancel`)
export const pauseExecution = (executionId: string) => request.post<AgentExecution>(`/api/v1/executions/${executionId}/pause`)
export const resumeExecution = (executionId: string) => request.post<AgentExecution>(`/api/v1/executions/${executionId}/resume`)
export const approveExecution = (executionId: string) => request.post<AgentExecution>(`/api/v1/executions/${executionId}/approve`)

export const getExecution = (executionId: string) => request.get<AgentExecution>(`/api/v1/executions/${executionId}`)
export const respondExecution = (executionId: string, selectedResultIds: string[]) => request.post<AgentExecution>(`/api/v1/executions/${executionId}/respond`, { selected_result_ids: selectedResultIds })

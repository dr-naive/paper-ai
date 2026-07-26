import request from './index'

export const uploadPaper = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  const token = localStorage.getItem('access_token')
  return request.post('/api/v1/papers/upload', formData, { 
    timeout: 900000,
    headers: { 
      'Authorization': token ? `Bearer ${token}` : undefined,
      'Content-Type': undefined 
    } 
  })
}

export const getPaperList = (params?: { skip?: number; limit?: number; status?: string; search?: string }) =>
  request.get('/api/v1/papers/', { params })

export const getPaper = (paperId: string) => request.get(`/api/v1/papers/${paperId}`)

export const getPaperSections = (paperId: string) => request.get(`/api/v1/papers/${paperId}/sections`)

export const rebuildPaperSections = (paperId: string) =>
  request.post(`/api/v1/papers/${paperId}/sections/rebuild`)

export const deletePaper = (paperId: string) => request.delete(`/api/v1/papers/${paperId}`)

export const getTaskStatus = (taskId: string) => {
  const token = localStorage.getItem('access_token')
  return request.get(`/api/v1/papers/tasks/${taskId}`, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : undefined
    }
  })
}

export const updateReadingStatus = (paperId: string, data: { status?: string; progress?: number; favorite?: boolean }) =>
  request.patch(`/api/v1/papers/${paperId}/status`, data)

// 对话会话管理
export const listSessions = (paperId?: string, skip = 0, limit = 20) =>
  request.get('/api/v1/chat/sessions', { params: { paper_id: paperId, skip, limit } })

export const createSession = (paperId: string, title?: string) =>
  request.post('/api/v1/chat/sessions', { paper_id: paperId, title })

export const deleteSession = (sessionId: string) =>
  request.delete(`/api/v1/chat/sessions/${sessionId}`)

export const getSessionMessages = (sessionId: string) =>
  request.get(`/api/v1/chat/sessions/${sessionId}/messages`)

export const askInSession = (sessionId: string, question: string) =>
  request.post(`/api/v1/chat/sessions/${sessionId}/ask`, { question })

export interface AskStreamHandlers {
  onTask?: (data: { task_id: string; question?: string; status?: string; enable_thinking?: boolean }) => void
  onStatus?: (data: { stage: string; message: string; source_count?: number }) => void
  onReasoningDelta?: (text: string) => void
  onReasoningDone?: () => void
  onDelta?: (text: string) => void
  onCitations?: (items: any[]) => void
  onDone?: (data: any) => void
  onStopped?: (data: { message: string; answer_length: number }) => void
}

const consumeAskStream = async (
  response: Response,
  handlers: AskStreamHandlers,
) => {
  if (response.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
    throw new Error('登录状态已失效')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error: any = new Error(payload.detail || `请求失败（${response.status}）`)
    error.retriable = false
    error.status = response.status
    throw error
  }
  if (!response.body) throw new Error('当前浏览器不支持流式回答')
  const headerTaskId = response.headers.get('X-Chat-Task-Id')
  if (headerTaskId) handlers.onTask?.({ task_id: headerTaskId })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (block: string) => {
    let event = 'message'
    const dataLines: string[] = []
    block.split(/\r?\n/).forEach(line => {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    })
    if (!dataLines.length) return
    const payload = JSON.parse(dataLines.join('\n'))
    if (event === 'task') handlers.onTask?.(payload)
    if (event === 'status') handlers.onStatus?.(payload)
    if (event === 'reasoning_delta') handlers.onReasoningDelta?.(payload.text || '')
    if (event === 'reasoning_done') handlers.onReasoningDone?.()
    if (event === 'answer_delta') handlers.onDelta?.(payload.text || '')
    if (event === 'citations') handlers.onCitations?.(payload.items || [])
    if (event === 'done') handlers.onDone?.(payload)
    if (event === 'stopped') handlers.onStopped?.(payload)
    if (event === 'error') {
      const error: any = new Error(payload.message || '回答生成失败')
      error.retriable = false
      error.stage = payload.stage
      throw error
    }
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

const chatFetch = (path: string, init: RequestInit = {}) => {
  const token = localStorage.getItem('access_token')
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  return fetch(`${baseURL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {})
    }
  })
}

export const streamAskInSession = async (
  sessionId: string,
  question: string,
  enableThinking: boolean,
  handlers: AskStreamHandlers,
  signal?: AbortSignal
) => {
  const response = await chatFetch(
    `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/ask/stream`,
    {
      method: 'POST',
      body: JSON.stringify({ question, enable_thinking: enableThinking }),
      signal
    }
  )
  return consumeAskStream(response, handlers)
}

export const resumeAnswerTask = async (
  taskId: string,
  offset: number,
  reasoningOffset: number,
  handlers: AskStreamHandlers,
  signal?: AbortSignal
) => {
  const response = await chatFetch(
    `/api/v1/chat/answer-tasks/${encodeURIComponent(taskId)}/stream?offset=${offset}&reasoning_offset=${reasoningOffset}`,
    { signal }
  )
  return consumeAskStream(response, handlers)
}

export const getAnswerTask = (taskId: string) =>
  request.get(`/api/v1/chat/answer-tasks/${encodeURIComponent(taskId)}`)

export const stopAnswerTask = (taskId: string) =>
  request.post(`/api/v1/chat/answer-tasks/${encodeURIComponent(taskId)}/stop`)

// 结构化摘要（带缓存）
export const generateSummary = (paperId: string) =>
  request.post(`/api/v1/chat/papers/${paperId}/summarize`)

export const getSummaryCache = (paperId: string) =>
  request.get(`/api/v1/chat/papers/${paperId}/summary`)

// 深度解读（带缓存）
export const interpretPaper = (paperId: string, type: string) =>
  request.post(`/api/v1/chat/papers/${paperId}/interpret/${type}`)

export const getInterpretCache = (paperId: string, type: string) =>
  request.get(`/api/v1/chat/papers/${paperId}/interpret/${type}`)

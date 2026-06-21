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

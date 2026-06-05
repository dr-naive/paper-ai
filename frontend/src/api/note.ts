import request from './index'

export const createNote = (data: { title: string; content: string; tags?: string[] }) =>
  request.post('/api/v1/notes', data)

export const getNoteList = (params?: { skip?: number; limit?: number; search?: string }) =>
  request.get('/api/v1/notes', { params })

export const getNote = (noteId: string) => request.get(`/api/v1/notes/${noteId}`)

export const updateNote = (noteId: string, data: { title?: string; content?: string; tags?: string[] }) =>
  request.put(`/api/v1/notes/${noteId}`, data)

export const deleteNote = (noteId: string) => request.delete(`/api/v1/notes/${noteId}`)
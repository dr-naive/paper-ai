import request from './index'

export interface LoginResponse {
  access_token: string
  user: {
    id: number
    username: string
    email: string
  }
}

export interface LoginData {
  username: string
  password: string
}

export const login = (data: LoginData) => {
  return request.post<LoginResponse>('/api/auth/login', data)
}

export const register = (data: LoginData & { email: string }) => {
  return request.post<LoginResponse>('/api/auth/register', data)
}

export const getCurrentUser = () => {
  return request.get('/api/auth/me')
}

export const logout = () => {
  return request.post('/api/auth/logout')
}
import request from './index'

export interface LoginResponse {
  access_token: string
  user: {
    id: string
    username: string
    email: string
  }
}

export interface UserResponse {
  id: string
  username: string
  email: string
  created_at: string
}

export interface LoginData {
  username: string
  password: string
}

export const login = (data: LoginData) => {
  return request.post<LoginResponse>('/api/auth/login', data)
}

export const register = (data: LoginData & { email: string }) => {
  return request.post<UserResponse>('/api/auth/register', data)
}

export const getCurrentUser = () => {
  return request.get<UserResponse>('/api/auth/users/me')
}

export const logout = () => {
  return request.post('/api/auth/logout')
}

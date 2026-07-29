import request from './index'

export interface LoginResponse {
  access_token: string
  user: UserResponse
}

export interface UserResponse {
  id: string
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
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

export const listUsers = () => {
  return request.get<UserResponse[]>('/api/auth/admin/users')
}

export const updateUserPermissions = (
  userId: string,
  data: Partial<Pick<UserResponse, 'role' | 'is_active'>>
) => {
  return request.patch<UserResponse>(`/api/auth/admin/users/${userId}`, data)
}

export const logout = () => {
  return request.post('/api/auth/logout')
}

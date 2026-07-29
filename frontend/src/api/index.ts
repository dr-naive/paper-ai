import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (
      error.response?.status === 401
      && error.config?.url !== '/api/auth/login'
    ) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const request = {
  get: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> => apiClient.get<T>(url, config) as Promise<T>,
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => apiClient.post<T>(url, data, config) as Promise<T>,
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => apiClient.put<T>(url, data, config) as Promise<T>,
  delete: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> => apiClient.delete<T>(url, config) as Promise<T>,
  patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => apiClient.patch<T>(url, data, config) as Promise<T>,
}

export default request

export * as paper from './paper'

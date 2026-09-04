import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getCurrentUser, type LoginResponse, type UserResponse } from '@/api/auth'

const readUser = (): UserResponse | null => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') }
  catch { return null }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<UserResponse | null>(readUser())
  const validatedToken = ref('')
  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const setSession = (response: LoginResponse) => {
    token.value = response.access_token; user.value = response.user; validatedToken.value = response.access_token
    localStorage.setItem('access_token', response.access_token); localStorage.setItem('user', JSON.stringify(response.user))
  }
  const clearSession = () => {
    token.value = ''; user.value = null; validatedToken.value = ''
    localStorage.removeItem('access_token'); localStorage.removeItem('user')
  }
  const validate = async () => {
    const storedToken = localStorage.getItem('access_token') || ''
    if (!storedToken) { clearSession(); return null }
    token.value = storedToken
    if (validatedToken.value === storedToken && user.value) return user.value
    try {
      user.value = await getCurrentUser(); validatedToken.value = storedToken
      localStorage.setItem('user', JSON.stringify(user.value)); return user.value
    } catch { clearSession(); return null }
  }
  return { token, user, isAuthenticated, isAdmin, setSession, clearSession, validate }
})

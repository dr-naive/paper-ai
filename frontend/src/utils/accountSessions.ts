import type { LoginResponse, UserResponse } from '@/api/auth'

const STORAGE_KEY = 'paperai_saved_accounts'

export interface SavedAccount {
  access_token: string
  user: UserResponse
}

export const getSavedAccounts = (): SavedAccount[] => {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

const saveAccounts = (accounts: SavedAccount[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(accounts))
}

export const rememberAccount = (session: LoginResponse) => {
  const accounts = getSavedAccounts().filter(
    account => account.user.id !== session.user.id
  )
  accounts.push({ access_token: session.access_token, user: session.user })
  saveAccounts(accounts)
}

export const rememberCurrentAccount = (user: UserResponse) => {
  const accessToken = localStorage.getItem('access_token')
  if (!accessToken) return
  rememberAccount({ access_token: accessToken, user })
}

export const activateAccount = (account: SavedAccount) => {
  localStorage.setItem('access_token', account.access_token)
  localStorage.setItem('user', JSON.stringify(account.user))
}

export const removeSavedAccount = (userId: string) => {
  const accounts = getSavedAccounts().filter(account => account.user.id !== userId)
  saveAccounts(accounts)
  return accounts
}

import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { getCurrentUser } from '@/api/auth'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/guide', name: 'Guide', component: () => import('@/views/Guide.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
  { path: '/papers', name: 'PaperList', component: () => import('@/views/PaperList.vue') },
  { path: '/paper/:id', name: 'PaperReader', component: () => import('@/views/PaperReader.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

let validatedToken = ''

router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  const isPublicRoute = to.path === '/login' || to.path === '/home' || to.path === '/guide' || to.path === '/register'

  if (!token) {
    validatedToken = ''
    return isPublicRoute ? true : '/login'
  }

  if (validatedToken !== token) {
    try {
      const user = await getCurrentUser()
      localStorage.setItem('user', JSON.stringify(user))
      validatedToken = token
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      validatedToken = ''
      return isPublicRoute ? true : '/login'
    }
  }

  return to.path === '/login' || to.path === '/register' ? '/home' : true
})

export default router

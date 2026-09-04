import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { getCurrentUser } from '@/api/auth'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/guide', name: 'Guide', component: () => import('@/views/Guide.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
  { path: '/papers', name: 'PaperWorkbench', component: () => import('@/views/ResearchProjectList.vue') },
  { path: '/library', name: 'PaperList', component: () => import('@/views/PaperList.vue') },
  { path: '/paper/:id', name: 'PaperReader', component: () => import('@/views/PaperReader.vue') },
  { path: '/projects', name: 'ResearchProjects', component: () => import('@/views/ResearchProjectList.vue') },
  { path: '/project/:id', name: 'ProjectWorkspace', component: () => import('@/views/ProjectWorkspace.vue') },
  { path: '/project/:id/chat', name: 'ProjectChat', component: () => import('@/views/ProjectChat.vue') },
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: () => import('@/views/AdminDashboard.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/admin/traces',
    name: 'AdminTraces',
    component: () => import('@/views/AdminTraces.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('@/views/AdminUsers.vue'),
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, top: 20, behavior: 'smooth' }
    return { top: 0 }
  },
})

let validatedToken = ''

router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  const isPublicRoute = to.path === '/login' || to.path === '/home' || to.path === '/guide' || to.path === '/register'

  if (!token) {
    validatedToken = ''
    return isPublicRoute ? true : '/login'
  }

  let currentUser: any = null
  if (validatedToken !== token) {
    try {
      currentUser = await getCurrentUser()
      localStorage.setItem('user', JSON.stringify(currentUser))
      validatedToken = token
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      validatedToken = ''
      return isPublicRoute ? true : '/login'
    }
  } else {
    try {
      currentUser = JSON.parse(localStorage.getItem('user') || 'null')
    } catch {
      currentUser = null
    }
  }

  if (to.meta.requiresAdmin && currentUser?.role !== 'admin') return '/home'
  return to.path === '/login' || to.path === '/register' ? '/home' : true
})

export default router

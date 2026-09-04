import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { pinia } from '@/stores'
import { useAuthStore } from '@/stores/auth'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/guide', name: 'Guide', component: () => import('@/views/Guide.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
  { path: '/papers', name: 'PaperWorkbench', component: () => import('@/views/ResearchProjectList.vue') },
  { path: '/library', name: 'PaperList', component: () => import('@/views/PaperList.vue') },
  { path: '/paper/:id', name: 'PaperReader', component: () => import('@/views/PaperReader.vue') },
  { path: '/projects', name: 'ResearchProjects', component: () => import('@/views/ResearchProjectList.vue') },
  {
    path: '/project/:id',
    name: 'LegacyProjectWorkspace',
    redirect: to => ({
      name: 'ProjectOverview',
      params: { projectId: to.params.id },
      query: to.query,
      hash: to.hash,
    }),
  },
  {
    path: '/project/:id/chat',
    name: 'LegacyProjectChat',
    redirect: to => ({
      name: 'ProjectOverview',
      params: { projectId: to.params.id },
    }),
  },
  {
    path: '/projects/:projectId',
    name: 'ProjectRoot',
    redirect: to => ({ name: 'ProjectOverview', params: { projectId: to.params.projectId } }),
  },
  { path: '/projects/:projectId/overview', name: 'ProjectOverview', component: () => import('@/views/ProjectOverview.vue') },
  { path: '/projects/:projectId/discover', name: 'ProjectDiscover', component: () => import('@/views/LiteratureDiscover.vue') },
  { path: '/projects/:projectId/papers', name: 'ProjectPapers', component: () => import('@/views/ProjectPapers.vue') },
  { path: '/projects/:projectId/writing', name: 'ProjectWriting', component: () => import('@/views/ProjectWriting.vue') },
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
    if (to.hash) {
      const reduceMotion = typeof window !== 'undefined'
        && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      return { el: to.hash, top: 20, behavior: reduceMotion ? 'auto' : 'smooth' }
    }
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  const token = localStorage.getItem('access_token')
  const isPublicRoute = to.path === '/login' || to.path === '/home' || to.path === '/guide' || to.path === '/register'

  if (!token) {
    auth.clearSession()
    return isPublicRoute ? true : '/login'
  }

  const currentUser = await auth.validate()
  if (!currentUser) return isPublicRoute ? true : '/login'

  if (to.meta.requiresAdmin && currentUser?.role !== 'admin') return '/home'
  return to.path === '/login' || to.path === '/register' ? '/home' : true
})

export default router

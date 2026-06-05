import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
  { path: '/papers', name: 'PaperList', component: () => import('@/views/PaperList.vue') },
  { path: '/paper/:id', name: 'PaperReader', component: () => import('@/views/PaperReader.vue') },
  { path: '/paper/:id/qa', name: 'PaperQA', component: () => import('@/views/PaperQA.vue') },
  { path: '/notes', name: 'Notes', component: () => import('@/views/Notes.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  // 已登录用户访问登录/注册页，重定向到首页
  if (token && (to.path === '/login' || to.path === '/register')) {
    next('/home')
    return
  }
  // 未登录用户访问需要认证的页面，重定向到登录页
  if (!token && to.path !== '/login' && to.path !== '/home' && to.path !== '/register') {
    next('/login')
    return
  }
  next()
})

export default router

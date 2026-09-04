<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <div class="sidebar-top">
        <button class="home-button" type="button" aria-label="返回首页" @click="router.push('/home')">←</button>
        <BrandMark :size="27" />
      </div>

      <div class="workspace-label">管理员工作台</div>
      <nav class="admin-nav" aria-label="管理页面导航">
        <button
          v-for="item in navigation"
          :key="item.label"
          type="button"
          :class="{ active: isActive(item) }"
          @click="navigate(item)"
        >
          <span class="nav-icon" aria-hidden="true">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-account">
        <span class="account-avatar" aria-hidden="true">{{ userInitial }}</span>
        <span><strong>{{ username }}</strong><small>管理员</small></span>
      </div>
    </aside>

    <div class="admin-main">
      <header class="admin-header">
        <div>
          <h1>{{ title }}</h1>
          <p>{{ subtitle }}</p>
        </div>
        <div v-if="$slots.actions" class="header-actions"><slot name="actions" /></div>
      </header>
      <main class="admin-content"><slot /></main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from '@/components/BrandMark.vue'

defineProps<{ title: string; subtitle: string }>()
const route = useRoute()
const router = useRouter()
const navigation = [
  { label: '运行概览', icon: '⌂', path: '/admin', hash: '' },
  { label: 'AI 使用', icon: '◫', path: '/admin', hash: '#ai-usage' },
  { label: '质量评测', icon: '✓', path: '/admin', hash: '#evaluations' },
  { label: '链路追踪', icon: '⟶', path: '/admin/traces', hash: '' },
  { label: '用户与权限', icon: '♙', path: '/admin/users', hash: '' },
]
const storedUser = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || '{}') }
  catch { return {} }
})
const username = computed(() => storedUser.value.username || 'admin')
const userInitial = computed(() => username.value.charAt(0).toUpperCase())
const isActive = (item: typeof navigation[number]) =>
  route.path === item.path && route.hash === item.hash
const navigate = (item: typeof navigation[number]) =>
  router.push({ path: item.path, hash: item.hash })
</script>

<style scoped>
.admin-layout { min-height: 100vh; background: var(--pa-bg); }
.admin-sidebar { position: fixed; inset: 0 auto 0 0; z-index: 20; display: flex; width: 236px; flex-direction: column; border-right: 1px solid var(--pa-border); background: var(--pa-surface); }
.sidebar-top { display: flex; min-height: 68px; align-items: center; gap: 13px; padding: 0 18px; border-bottom: 1px solid var(--pa-border); }
.home-button { display: grid; width: 32px; height: 36px; flex: none; place-items: center; border: 0; border-radius: 5px; background: transparent; color: var(--pa-muted); font-size: 21px; cursor: pointer; }
.home-button:hover { background: var(--pa-surface-soft); color: var(--pa-ink); }
.home-button:focus-visible, .admin-nav button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.workspace-label { padding: 24px 20px 9px; color: var(--pa-muted); font-size: 11px; font-weight: 600; }
.admin-nav { display: flex; flex-direction: column; gap: 3px; padding: 0 10px; }
.admin-nav button { display: flex; width: 100%; align-items: center; gap: 11px; padding: 10px 11px; border: 0; border-radius: 7px; background: transparent; color: var(--pa-muted); font-size: 13px; text-align: left; cursor: pointer; }
.admin-nav button:hover { background: var(--pa-surface-soft); color: var(--pa-ink); }
.admin-nav button.active { background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-weight: 650; }
.nav-icon { display: grid; width: 19px; place-items: center; color: inherit; font-size: 15px; }
.sidebar-account { display: flex; align-items: center; gap: 10px; margin-top: auto; padding: 17px 18px; border-top: 1px solid var(--pa-border); }
.account-avatar { display: grid; width: 32px; height: 32px; flex: none; place-items: center; border-radius: 50%; background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-size: 12px; font-weight: 700; }
.sidebar-account > span:last-child { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.sidebar-account strong { overflow: hidden; color: var(--pa-ink); font-size: 12px; text-overflow: ellipsis; }
.sidebar-account small { color: var(--pa-muted); font-size: 10px; }
.admin-main { min-height: 100vh; margin-left: 236px; }
.admin-header { display: flex; min-height: 112px; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 26px max(28px, calc((100vw - 236px - 1280px) / 2)) 22px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface); }
.admin-header h1 { color: var(--pa-ink); font-size: 25px; line-height: 1.2; }
.admin-header p { margin-top: 7px; color: var(--pa-muted); font-size: 13px; }
.header-actions { display: flex; align-items: center; flex: none; }
.admin-content { width: min(1280px, calc(100% - 56px)); margin: 0 auto; padding: 26px 0 72px; }
@media (max-width: 780px) {
  .admin-sidebar { position: sticky; top: 0; width: 100%; height: auto; border-right: 0; border-bottom: 1px solid var(--pa-border); }
  .sidebar-top { min-height: 56px; }
  .workspace-label, .sidebar-account { display: none; }
  .admin-nav { flex-direction: row; overflow-x: auto; padding: 7px 10px; }
  .admin-nav button { width: auto; flex: none; white-space: nowrap; }
  .admin-main { margin-left: 0; }
  .admin-header { min-height: 100px; align-items: flex-start; padding: 22px 18px 18px; }
  .admin-content { width: min(100% - 28px, 1280px); padding-top: 18px; }
}
@media (max-width: 520px) {
  .admin-header { flex-direction: column; gap: 12px; }
  .nav-icon { display: none; }
}
@media (pointer: coarse) {
  .home-button { width: 44px; height: 44px; }
  .admin-nav button { min-height: 44px; }
}
</style>

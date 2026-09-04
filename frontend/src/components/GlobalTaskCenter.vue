<template>
  <button
    class="task-trigger"
    type="button"
    :aria-expanded="open"
    aria-controls="global-task-center"
    @click="open = true"
  >
    <span aria-hidden="true">◷</span>
    <span>任务</span>
    <strong v-if="executionStore.runningCount">{{ executionStore.runningCount }}</strong>
  </button>

  <Teleport to="body">
    <div v-if="open" class="task-center-layer" @click.self="open = false">
      <aside id="global-task-center" class="task-center" aria-label="全局任务中心">
        <header>
          <div><span>后台工作</span><h2>任务中心</h2></div>
          <button type="button" aria-label="关闭任务中心" @click="open = false">×</button>
        </header>
        <div class="task-center__body">
          <p v-if="!executionStore.allExecutions.length" class="empty">当前没有任务。进入项目并开始研究后，后台进度会显示在这里。</p>
          <section v-for="group in populatedGroups" :key="group.key">
            <h3>{{ group.label }} <span>{{ group.items.length }}</span></h3>
            <button v-for="item in group.items" :key="item.id" type="button" class="task-item" @click="openExecution(item)">
              <span :class="['status-dot', `status-dot--${group.key}`]" aria-hidden="true"></span>
              <span class="task-item__content"><strong>{{ item.goal }}</strong><small>{{ item.current_stage || statusLabel(item.status) }} · {{ formatTime(item.updated_at) }}</small><em v-if="item.error_message">{{ item.error_message }}</em></span>
              <span v-if="item.project_id" aria-hidden="true">→</span>
            </button>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { AgentExecution } from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'

const router = useRouter()
const executionStore = useExecutionsStore()
const open = ref(false)
const groups = computed(() => [
  { key: 'running', label: '进行中', items: executionStore.allExecutions.filter(item => ['queued', 'running', 'paused'].includes(item.status)) },
  { key: 'approval', label: '等待确认', items: executionStore.allExecutions.filter(item => item.status === 'waiting_user') },
  { key: 'failed', label: '需要处理', items: executionStore.allExecutions.filter(item => item.status === 'failed') },
  { key: 'completed', label: '最近完成', items: executionStore.allExecutions.filter(item => ['completed', 'cancelled'].includes(item.status)).slice(0, 8) },
])
const populatedGroups = computed(() => groups.value.filter(group => group.items.length))
const statusLabel = (status: AgentExecution['status']) => ({ queued: '排队中', running: '执行中', waiting_user: '等待确认', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }[status])
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
const openExecution = (execution: AgentExecution) => {
  if (!execution.project_id) return
  open.value = false
  router.push({ name: 'ProjectOverview', params: { projectId: execution.project_id } })
}
onMounted(() => executionStore.loadGlobal().catch(() => undefined))
</script>

<style scoped>
.task-trigger { display: inline-flex; min-height: 34px; align-items: center; gap: 6px; padding: 0 10px; border: 1px solid transparent; border-radius: 999px; background: transparent; color: var(--pa-muted); cursor: pointer; font-size: 12px; font-weight: 600; }.task-trigger:hover { border-color: var(--pa-border); background: var(--pa-surface-soft); color: var(--pa-ink); }.task-trigger:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.task-trigger strong { display: grid; min-width: 20px; height: 20px; place-items: center; padding: 0 5px; border-radius: 999px; background: var(--pa-primary); color: white; font-size: 11px; }.task-center-layer { position: fixed; z-index: 1000; inset: 0; background: rgba(40,32,28,.24); }.task-center { position: absolute; top: 0; right: 0; width: min(390px, 100vw); height: 100%; overflow-y: auto; border-left: 1px solid var(--pa-border); background: var(--pa-surface); box-shadow: -12px 0 36px rgba(40,32,28,.14); }.task-center header { position: sticky; z-index: 1; top: 0; display: flex; align-items: center; justify-content: space-between; padding: 20px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface); }.task-center header span { color: var(--pa-muted); font-size: 11px; letter-spacing: .08em; }.task-center h2 { margin: 3px 0 0; font-size: 20px; }.task-center header button { width: 36px; height: 36px; border: 0; border-radius: 50%; background: var(--pa-surface-soft); color: var(--pa-muted); cursor: pointer; font-size: 24px; }.task-center__body { padding: 14px 20px 28px; }.task-center section + section { margin-top: 22px; }.task-center h3 { display: flex; align-items: center; gap: 7px; margin: 0 0 8px; color: var(--pa-muted); font-size: 12px; font-weight: 600; }.task-center h3 span { color: var(--pa-subtle); }.task-item { display: flex; width: 100%; align-items: flex-start; gap: 10px; padding: 12px 8px; border: 0; border-top: 1px solid var(--pa-border); background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }.task-item:hover { background: var(--pa-surface-soft); }.task-item__content { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.task-item strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.task-item small { color: var(--pa-muted); }.task-item em { color: var(--pa-danger); font-size: 11px; font-style: normal; }.status-dot { width: 8px; height: 8px; flex: none; margin-top: 5px; border-radius: 50%; background: var(--pa-muted); }.status-dot--running { background: var(--pa-primary); box-shadow: 0 0 0 4px var(--color-primary-light-1); }.status-dot--approval { background: #d97706; }.status-dot--failed { background: var(--pa-danger); }.status-dot--completed { background: var(--pa-success); }.empty { margin: 32px 10px; color: var(--pa-muted); font-size: 13px; line-height: 1.7; text-align: center; }@media (prefers-reduced-motion: no-preference) { .task-center { animation: slide-in 180ms ease-out; } @keyframes slide-in { from { transform: translateX(24px); opacity: .5; } } }@media (pointer: coarse) { .task-trigger { min-height: 44px; }.task-center header button { width: 44px; height: 44px; } }
</style>

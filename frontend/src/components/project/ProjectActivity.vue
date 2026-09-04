<template>
  <section class="activity" aria-labelledby="activity-title">
    <header class="activity-toolbar">
      <div><h3 id="activity-title">Agent 活动</h3><p>查看可恢复的执行记录、公开进度和错误。系统不会展示模型内部推理。</p></div>
      <a-button :loading="loading" @click="loadExecutions">刷新活动</a-button>
    </header>
    <a-spin :loading="loading">
      <div v-if="!loading && !executions.length" class="activity-empty"><h4>还没有 Agent 活动</h4><p>从项目工作区向 Agent 发起任务后，执行进度会保存在这里。</p></div>
      <ol v-else class="execution-list">
        <li v-for="item in executions" :key="item.id" class="execution-item">
          <button type="button" class="execution-main" :aria-expanded="selectedId === item.id" @click="toggleExecution(item)">
            <span class="status" :class="`status-${item.status}`">{{ statusLabel(item.status) }}</span>
            <span class="execution-copy"><strong>{{ item.goal }}</strong><small>{{ item.agent_type }} · {{ formatTime(item.updated_at) }}</small></span>
            <span class="stage">{{ item.current_stage || '等待阶段信息' }}</span>
          </button>
          <div v-if="selectedId === item.id" class="event-panel">
            <div class="execution-actions">
              <template v-if="item.status === 'waiting_user'">
                <p class="approval-impact">该任务需要你确认后才能继续：{{ item.goal }}</p>
                <a-button size="mini" type="primary" @click="act(item, 'approve')">批准并继续</a-button>
                <a-button size="mini" status="danger" @click="act(item, 'cancel')">拒绝并取消</a-button>
              </template>
              <a-button v-if="item.status === 'running'" size="mini" @click="act(item, 'pause')">暂停执行</a-button>
              <a-button v-if="item.status === 'paused'" size="mini" type="primary" @click="act(item, 'resume')">恢复执行</a-button>
              <a-button v-if="!terminal(item.status) && item.status !== 'waiting_user'" size="mini" status="danger" @click="act(item, 'cancel')">取消执行</a-button>
            </div>
            <p v-if="eventsLoading" class="event-message">正在加载事件…</p>
            <p v-else-if="!events.length" class="event-message">该执行还没有公开事件。</p>
            <ol v-else class="event-list"><li v-for="event in events" :key="event.id"><time>{{ formatTime(event.timestamp) }}</time><div><strong>{{ event.stage || event.type }}</strong><p>{{ event.message }}</p></div></li></ol>
          </div>
        </li>
      </ol>
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { AgentExecution } from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'

const props = defineProps<{ projectId: string }>()
const executionStore = useExecutionsStore()
const executions = computed(() => executionStore.projectExecutions(props.projectId))
const events = computed(() => executionStore.executionEvents(selectedId.value))
const loading = ref(false)
const eventsLoading = ref(false)
const selectedId = ref('')
const labels: Record<string, string> = { queued: '排队中', running: '执行中', waiting_user: '等待确认', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }
const statusLabel = (value: string) => labels[value] || value
const terminal = (value: string) => ['completed', 'failed', 'cancelled'].includes(value)
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未知时间'

const loadExecutions = async () => {
  loading.value = true
  try { await executionStore.loadProject(props.projectId) }
  catch (error: any) { Message.error(error?.response?.data?.detail?.message || '加载 Agent 活动失败') }
  finally { loading.value = false }
}
const toggleExecution = async (item: AgentExecution) => {
  const previousId = selectedId.value
  selectedId.value = selectedId.value === item.id ? '' : item.id
  if (previousId) executionStore.stopStream(previousId)
  if (!selectedId.value) return
  eventsLoading.value = true
  try {
    await executionStore.loadEvents(item.id)
    if (executionStore.shouldStream(item)) void executionStore.startStream(props.projectId, item.id).catch(() => Message.error('实时活动连接中断，请刷新后重试'))
  }
  catch { Message.error('加载执行事件失败') }
  finally { eventsLoading.value = false }
}
const act = async (item: AgentExecution, action: 'pause' | 'resume' | 'cancel' | 'approve') => {
  try {
    await executionStore.act(props.projectId, item.id, action)
    Message.success(action === 'pause' ? '执行已暂停' : action === 'resume' ? '执行已恢复' : action === 'approve' ? '已批准，任务将继续' : '执行已取消')
  } catch (error: any) { Message.error(error?.response?.data?.detail?.message || '更新执行状态失败') }
}
watch(() => props.projectId, loadExecutions)
onMounted(loadExecutions)
onBeforeUnmount(() => { if (selectedId.value) executionStore.stopStream(selectedId.value) })
</script>

<style scoped>
.activity-toolbar { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 16px; }
.activity-toolbar h3 { margin: 0 0 4px; color: var(--pa-text); font-size: 18px; }
.activity-toolbar p { max-width: 70ch; margin: 0; color: var(--pa-muted); line-height: 1.5; }
.activity-empty { padding: 40px 24px; border: 1px solid var(--pa-border); border-radius: 8px; text-align: center; }
.activity-empty h4 { margin: 0 0 6px; }.activity-empty p { margin: 0; color: var(--pa-muted); }
.execution-list, .event-list { margin: 0; padding: 0; list-style: none; }
.execution-item { border-bottom: 1px solid var(--pa-border); }
.execution-main { display: flex; width: 100%; min-height: 64px; align-items: center; gap: 12px; padding: 12px 4px; border: 0; background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }
.execution-main:hover { background: var(--pa-surface-soft); }.execution-main:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.status { min-width: 62px; padding: 3px 8px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 12px; text-align: center; }
.status-running { background: var(--color-primary-light-1); color: var(--pa-primary); }.status-completed { color: var(--pa-success); }.status-failed,.status-cancelled { color: var(--pa-danger); }
.execution-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.execution-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.execution-copy small,.stage { color: var(--pa-muted); }
.event-panel { padding: 0 8px 16px 86px; }.execution-actions { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }.approval-impact { width: 100%; margin: 0 0 4px; color: var(--pa-text); font-size: 13px; }
.event-list li { display: flex; gap: 16px; padding: 8px 0; }.event-list time { width: 150px; flex-shrink: 0; color: var(--pa-muted); font-size: 12px; }.event-list strong { font-size: 13px; }.event-list p,.event-message { margin: 3px 0 0; color: var(--pa-muted); }
@media (max-width: 767px) { .activity-toolbar { flex-direction: column; }.execution-main { align-items: flex-start; flex-wrap: wrap; }.stage { width: 100%; padding-left: 74px; }.event-panel { padding-left: 4px; }.event-list li { flex-direction: column; gap: 3px; }.event-list time { width: auto; } }
</style>

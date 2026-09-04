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
            <button v-for="item in group.items" :key="item.id" type="button" class="task-item" :class="{ selected: selectedExecutionId === item.id }" @click="selectExecution(item)">
              <span :class="['status-dot', `status-dot--${group.key}`]" aria-hidden="true"></span>
              <span class="task-item__content"><strong>{{ item.goal }}</strong><small>{{ item.current_stage || statusLabel(item.status) }} · {{ formatTime(item.updated_at) }}</small><em v-if="item.error_message">{{ item.error_message }}</em></span>
              <span v-if="item.project_id" aria-hidden="true">→</span>
            </button>
          </section>
          <section v-if="selectedExecution" class="execution-detail" aria-labelledby="execution-detail-title">
            <div class="execution-detail__header">
              <div><span>执行详情</span><h3 id="execution-detail-title">{{ selectedExecution.goal }}</h3></div>
              <span class="execution-status">{{ statusLabel(selectedExecution.status) }}</span>
            </div>
            <div class="execution-actions">
              <button v-if="['queued', 'running'].includes(selectedExecution.status)" type="button" @click="perform('pause')">暂停任务</button>
              <button v-if="selectedExecution.status === 'paused'" type="button" @click="perform('resume')">继续任务</button>
              <button v-if="!['completed', 'failed', 'cancelled'].includes(selectedExecution.status)" type="button" class="danger" @click="perform('cancel')">取消任务</button>
              <button v-if="selectedExecution.project_id" type="button" @click="openProject(selectedExecution)">打开项目</button>
            </div>
            <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>
            <section v-if="selectedTrace && selectedEvaluation" class="quality-summary" aria-labelledby="quality-summary-title">
              <div class="quality-summary__score">
                <div><span id="quality-summary-title">质量评估</span><strong>{{ selectedEvaluation.score }}<small>/{{ selectedEvaluation.maximum_score }}</small></strong></div>
                <span :class="['verdict', `verdict--${selectedEvaluation.verdict}`]">{{ verdictLabel(selectedEvaluation.verdict) }}</span>
              </div>
              <dl>
                <div><dt>总耗时</dt><dd>{{ durationLabel(selectedTrace.total_ms) }}</dd></div>
                <div><dt>引用验证</dt><dd>{{ selectedTrace.quality.verified_count }}/{{ selectedTrace.quality.citation_count }}</dd></div>
                <div><dt>模型调用</dt><dd>{{ selectedTrace.budget.model_calls.used }}/{{ selectedTrace.budget.model_calls.limit }}</dd></div>
                <div><dt>Skill 完成</dt><dd>{{ selectedTrace.quality.skill_completion_passed ? '通过' : '未通过' }}</dd></div>
              </dl>
              <ul class="quality-checks">
                <li v-for="check in selectedEvaluation.checks" :key="check.name">
                  <span :class="check.passed ? 'check-pass' : 'check-fail'">{{ check.passed ? '✓' : '!' }}</span>
                  <span>{{ checkLabel(check.name) }}</span><small>{{ check.earned }}/{{ check.maximum }}</small>
                </li>
              </ul>
            </section>
            <ol v-if="selectedEvents.length" class="event-timeline" aria-label="任务执行时间线">
              <li v-for="event in selectedEvents" :key="event.id">
                <span class="timeline-marker" aria-hidden="true"></span>
                <div><strong>{{ event.message }}</strong><small>{{ stageLabel(event.stage) }} · {{ formatTime(event.timestamp) }}</small></div>
              </li>
            </ol>
            <p v-else class="event-empty">正在读取执行记录…</p>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { AgentExecution } from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'

const router = useRouter()
const executionStore = useExecutionsStore()
const open = ref(false)
const selectedExecutionId = ref('')
const actionError = ref('')
const groups = computed(() => [
  { key: 'running', label: '进行中', items: executionStore.allExecutions.filter(item => ['queued', 'running', 'paused'].includes(item.status)) },
  { key: 'approval', label: '等待确认', items: executionStore.allExecutions.filter(item => item.status === 'waiting_user') },
  { key: 'failed', label: '需要处理', items: executionStore.allExecutions.filter(item => item.status === 'failed') },
  { key: 'completed', label: '最近完成', items: executionStore.allExecutions.filter(item => ['completed', 'cancelled'].includes(item.status)).slice(0, 8) },
])
const populatedGroups = computed(() => groups.value.filter(group => group.items.length))
const selectedExecution = computed(() => executionStore.allExecutions.find(item => item.id === selectedExecutionId.value) || null)
const selectedEvents = computed(() => selectedExecutionId.value ? executionStore.executionEvents(selectedExecutionId.value) : [])
const selectedTrace = computed(() => selectedExecutionId.value ? executionStore.executionTrace(selectedExecutionId.value) : null)
const selectedEvaluation = computed(() => selectedExecutionId.value ? executionStore.executionEvaluation(selectedExecutionId.value) : null)
const statusLabel = (status: AgentExecution['status']) => ({ queued: '排队中', running: '执行中', waiting_user: '等待确认', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }[status])
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
const stageLabel = (stage?: string | null) => ({ queued: '排队', starting: '启动', skill_activated: 'Skill 激活', context_started: '查找论文', context_ready: '证据就绪', generation_started: '生成段落', proposal_generated: '草案生成', review_started: '审查草案', review_passed: '审查通过', review_repair_required: '需要修复', review_repair_completed: '修复完成', evidence_persisted: '保存证据', verification_started: '验证引用', citation_verified: '验证完成', skill_completion: 'Skill 完成评估', completion_gate: '质量检查', completed: '完成', failed: '失败', cancelled: '取消' }[stage || ''] || stage || '执行中')
const verdictLabel = (verdict: 'pass' | 'fail' | 'incomplete') => ({ pass: '通过', fail: '未通过', incomplete: '未完成' }[verdict])
const checkLabel = (name: string) => ({ terminal_success: '任务正常完成', completion_gate: '完成质量门', citation_support: '引用支持强度', trace_completeness: '执行链路完整', budget_compliance: '预算未超限', latency_integrity: '耗时数据完整' }[name] || name)
const durationLabel = (value?: number | null) => value == null ? '—' : value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`
const selectExecution = async (execution: AgentExecution) => {
  selectedExecutionId.value = execution.id
  actionError.value = ''
  await Promise.all([executionStore.loadEvents(execution.id), executionStore.loadTrace(execution.id)])
  if (execution.project_id && executionStore.shouldStream(execution)) void executionStore.startStream(execution.project_id, execution.id).catch(error => { actionError.value = error instanceof Error ? error.message : '任务事件流连接失败' })
}
const perform = async (action: 'pause' | 'resume' | 'cancel') => {
  const execution = selectedExecution.value
  if (!execution?.project_id) return
  actionError.value = ''
  try { await executionStore.act(execution.project_id, execution.id, action) }
  catch (error) { actionError.value = error instanceof Error ? error.message : '任务操作失败，请稍后重试。' }
}
const openProject = (execution: AgentExecution) => {
  if (!execution.project_id) return
  open.value = false
  router.push({ name: 'ProjectOverview', params: { projectId: execution.project_id } })
}
onMounted(() => executionStore.loadGlobal().catch(() => undefined))
onBeforeUnmount(() => { if (selectedExecutionId.value) executionStore.stopStream(selectedExecutionId.value) })
</script>

<style scoped>
.task-trigger { display: inline-flex; min-height: 34px; align-items: center; gap: 6px; padding: 0 10px; border: 1px solid transparent; border-radius: 999px; background: transparent; color: var(--pa-muted); cursor: pointer; font-size: 12px; font-weight: 600; }.task-trigger:hover { border-color: var(--pa-border); background: var(--pa-surface-soft); color: var(--pa-ink); }.task-trigger:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.task-trigger strong { display: grid; min-width: 20px; height: 20px; place-items: center; padding: 0 5px; border-radius: 999px; background: var(--pa-primary); color: white; font-size: 11px; }.task-center-layer { position: fixed; z-index: 1000; inset: 0; background: rgba(40,32,28,.24); }.task-center { position: absolute; top: 0; right: 0; width: min(390px, 100vw); height: 100%; overflow-y: auto; border-left: 1px solid var(--pa-border); background: var(--pa-surface); box-shadow: -12px 0 36px rgba(40,32,28,.14); }.task-center header { position: sticky; z-index: 1; top: 0; display: flex; align-items: center; justify-content: space-between; padding: 20px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface); }.task-center header span { color: var(--pa-muted); font-size: 11px; letter-spacing: .08em; }.task-center h2 { margin: 3px 0 0; font-size: 20px; }.task-center header button { width: 36px; height: 36px; border: 0; border-radius: 50%; background: var(--pa-surface-soft); color: var(--pa-muted); cursor: pointer; font-size: 24px; }.task-center__body { padding: 14px 20px 28px; }.task-center section + section { margin-top: 22px; }.task-center h3 { display: flex; align-items: center; gap: 7px; margin: 0 0 8px; color: var(--pa-muted); font-size: 12px; font-weight: 600; }.task-center h3 span { color: var(--pa-subtle); }.task-item { display: flex; width: 100%; align-items: flex-start; gap: 10px; padding: 12px 8px; border: 0; border-top: 1px solid var(--pa-border); background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }.task-item:hover { background: var(--pa-surface-soft); }.task-item__content { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.task-item strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.task-item small { color: var(--pa-muted); }.task-item em { color: var(--pa-danger); font-size: 11px; font-style: normal; }.status-dot { width: 8px; height: 8px; flex: none; margin-top: 5px; border-radius: 50%; background: var(--pa-muted); }.status-dot--running { background: var(--pa-primary); box-shadow: 0 0 0 4px var(--color-primary-light-1); }.status-dot--approval { background: #d97706; }.status-dot--failed { background: var(--pa-danger); }.status-dot--completed { background: var(--pa-success); }.empty { margin: 32px 10px; color: var(--pa-muted); font-size: 13px; line-height: 1.7; text-align: center; }@media (prefers-reduced-motion: no-preference) { .task-center { animation: slide-in 180ms ease-out; } @keyframes slide-in { from { transform: translateX(24px); opacity: .5; } } }@media (pointer: coarse) { .task-trigger { min-height: 44px; }.task-center header button { width: 44px; height: 44px; } }
.task-item.selected { background: var(--pa-surface-soft); }.task-item:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: -2px; }.execution-detail { padding-top: 18px; border-top: 1px solid var(--pa-border); }.execution-detail__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.execution-detail__header h3 { margin-top: 4px; color: var(--pa-ink); font-size: 14px; }.execution-status { color: var(--pa-muted); font-size: 12px; white-space: nowrap; }.execution-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }.execution-actions button { min-height: 34px; padding: 6px 10px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-sm); background: var(--pa-surface); color: var(--pa-text); cursor: pointer; }.execution-actions button:hover { border-color: var(--pa-primary); transform: translateY(-1px); }.execution-actions button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.execution-actions .danger { color: var(--pa-danger); }.action-error { color: var(--pa-danger); font-size: 12px; }.event-timeline { margin: 14px 0 0; padding: 0; list-style: none; }.event-timeline li { position: relative; display: flex; gap: 10px; padding: 0 0 14px 3px; }.event-timeline li::after { position: absolute; top: 10px; bottom: 0; left: 6px; width: 1px; background: var(--pa-border); content: ''; }.event-timeline li:last-child::after { display: none; }.timeline-marker { z-index: 1; width: 8px; height: 8px; flex: none; margin-top: 4px; border-radius: 50%; background: var(--pa-info); }.event-timeline div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }.event-timeline strong { color: var(--pa-text); font-size: 12px; font-weight: 600; }.event-timeline small,.event-empty { color: var(--pa-muted); font-size: 11px; }.event-empty { margin: 14px 0; }
.quality-summary { margin-top: 14px; padding: 12px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface-soft); }.quality-summary__score { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.quality-summary__score > div { display: flex; flex-direction: column; gap: 3px; }.quality-summary__score span { color: var(--pa-muted); font-size: 11px; }.quality-summary__score strong { color: var(--pa-ink); font-size: 22px; }.quality-summary__score strong small { color: var(--pa-muted); font-size: 11px; font-weight: 500; }.quality-summary__score .verdict { padding: 4px 8px; border-radius: 999px; font-weight: 650; }.verdict--pass { background: var(--pa-success-soft); color: var(--pa-success) !important; }.verdict--fail { background: var(--pa-danger-soft); color: var(--pa-danger) !important; }.verdict--incomplete { background: var(--pa-surface); color: var(--pa-muted) !important; }.quality-summary dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }.quality-summary dl div { min-width: 0; }.quality-summary dt { color: var(--pa-muted); font-size: 10px; }.quality-summary dd { margin: 3px 0 0; color: var(--pa-text); font-size: 12px; font-weight: 650; }.quality-checks { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 10px 0 0; border-top: 1px solid var(--pa-border); list-style: none; }.quality-checks li { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 6px; color: var(--pa-text); font-size: 11px; }.quality-checks li > span:first-child { display: grid; width: 16px; height: 16px; place-items: center; border-radius: 50%; font-size: 10px; font-weight: 700; }.check-pass { background: var(--pa-success-soft); color: var(--pa-success); }.check-fail { background: var(--pa-danger-soft); color: var(--pa-danger); }.quality-checks small { color: var(--pa-muted); }
</style>

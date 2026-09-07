<template>
  <section class="panel evaluation-run-panel" aria-labelledby="evaluation-run-title">
    <div class="panel-heading">
      <div>
        <h2 id="evaluation-run-title">运行一次测评</h2>
        <p>选择已有评测类型。后台完成后，结果会保存到历史记录。</p>
      </div>
      <div class="evaluation-controls">
        <a-select v-model="selectedType" size="small" :style="{ width: '170px' }" aria-label="评测类型">
          <a-option value="runtime">运行观测报告</a-option>
          <a-option value="retrieval">检索质量评测</a-option>
          <a-option value="e2e">端到端回答评测</a-option>
        </a-select>
        <a-button type="primary" size="small" :loading="starting" :disabled="Boolean(activeRun)" @click="startEvaluation">
          开始测评
        </a-button>
      </div>
    </div>

    <div v-if="loadError" class="evaluation-alert error" role="alert">{{ loadError }}</div>

    <div v-if="activeRun" class="evaluation-current" :class="activeRun.status">
      <div class="evaluation-current-top">
        <div>
          <span class="evaluation-status" :class="activeRun.status">{{ statusLabel(activeRun.status) }}</span>
          <strong>{{ evaluationTypeLabel(activeRun.evaluation_type) }}</strong>
        </div>
        <time>{{ formatDate(activeRun.created_at) }}</time>
      </div>
      <p>{{ statusDescription(activeRun.status) }}</p>
      <small v-if="activeRun.error">{{ activeRun.error.message || activeRun.error.code }}</small>
    </div>

    <div class="evaluation-content">
      <section class="evaluation-history" aria-labelledby="evaluation-history-title">
        <div class="subheading">
          <h3 id="evaluation-history-title">历史测评</h3>
          <span>{{ history.length }} 条</span>
        </div>
        <div v-if="history.length" class="history-list">
          <button
            v-for="run in history"
            :key="run.id"
            type="button"
            class="history-item"
            :class="{ selected: selectedRunId === run.id }"
            @click="selectRun(run.id)"
          >
            <span class="history-item-main">
              <strong>{{ evaluationTypeLabel(run.evaluation_type) }}</strong>
              <small>{{ formatDate(run.created_at) }}</small>
            </span>
            <span class="evaluation-status" :class="run.status">{{ statusLabel(run.status) }}</span>
          </button>
        </div>
        <p v-else class="empty-copy">还没有测评记录，点击“开始测评”创建第一条。</p>
      </section>

      <section class="evaluation-result" aria-live="polite" aria-labelledby="evaluation-result-title">
        <div class="subheading">
          <h3 id="evaluation-result-title">测评结果</h3>
          <span v-if="detail">{{ formatDate(detail.completed_at || detail.created_at) }}</span>
        </div>
        <div v-if="detailLoading" class="result-placeholder">正在读取测评结果…</div>
        <div v-else-if="detail?.report" class="result-body">
          <div class="result-title">
            <strong>{{ evaluationTypeLabel(detail.evaluation_type) }}</strong>
            <span>{{ reportSourceLabel(detail.report) }}</span>
          </div>
          <div class="result-metrics">
            <div v-for="metric in visibleMetrics(detail)" :key="metric.label">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
            </div>
          </div>
          <p v-if="detail.evaluation_type === 'runtime'" class="result-note">
            运行观测报告来自后台已保存的运行数据；样本不足时只显示诊断提示。
          </p>
          <p v-else class="result-note">指标来自现有评测脚本的确定性汇总；原始明细仍保存在后台报告中。</p>
        </div>
        <div v-else-if="detail?.status === 'failed'" class="result-placeholder error-copy">
          本次测评失败：{{ detail.error?.message || '后台没有返回可用报告' }}
        </div>
        <div v-else class="result-placeholder">选择一条已完成记录查看结果。</div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getAdminEvaluation,
  listAdminEvaluations,
  startAdminEvaluation,
  type AdminEvaluationDetail,
  type AdminEvaluationReport,
  type AdminEvaluationRun,
  type AdminEvaluationStatus,
  type AdminEvaluationType,
} from '@/api/admin'

const selectedType = ref<AdminEvaluationType>('runtime')
const history = ref<AdminEvaluationRun[]>([])
const detail = ref<AdminEvaluationDetail | null>(null)
const selectedRunId = ref<string | null>(null)
const starting = ref(false)
const detailLoading = ref(false)
const loadError = ref('')
let pollTimer: number | undefined

const activeRun = computed(() => history.value.find((run) =>
  ['queued', 'running', 'retrying'].includes(run.status)
) || null)

const evaluationTypeLabel = (type: AdminEvaluationType) => ({
  runtime: '运行观测报告',
  retrieval: '检索质量评测',
  e2e: '端到端回答评测',
}[type] || type)

const statusLabel = (status: AdminEvaluationStatus) => ({
  queued: '排队中',
  running: '执行中',
  retrying: '重试中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}[status] || status)

const statusDescription = (status: AdminEvaluationStatus) => ({
  queued: '评测已创建，正在等待后台处理。',
  running: '后台正在执行已有评测脚本，完成后会自动刷新结果。',
  retrying: '本次执行遇到可重试错误，系统会按既有策略再次执行。',
  completed: '测评已完成，结果已保存，可以在右侧查看。',
  failed: '测评未完成，请检查错误信息或确认外部 Provider 配置。',
  cancelled: '本次测评已取消。',
}[status] || '正在处理。')

const formatDate = (date: string | null) => date
  ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date))
  : '日期未记录'

const number = (value: unknown) => typeof value === 'number'
  ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
  : '暂无数据'

const text = (value: unknown) => typeof value === 'string' && value ? value : '暂无数据'
const percent = (value: unknown) => typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '暂无数据'
const metric = (label: string, value: unknown, formatter: (input: unknown) => string = number) => ({ label, value: formatter(value) })

const reportSourceLabel = (report: AdminEvaluationReport) => report.generated_at
  ? `生成于 ${formatDate(report.generated_at)}`
  : '已保存结果'

const visibleMetrics = (run: AdminEvaluationDetail) => {
  const summary = run.report?.summary || {}
  if (run.evaluation_type === 'runtime') {
    const sample = run.report?.sample_size || {}
    const diagnostic = run.report?.diagnostic || {}
    const quality = (diagnostic.sample_quality || {}) as Record<string, unknown>
    return [
      metric('运行样本', sample.executions),
      metric('任务样本', sample.tasks),
      metric('操作次数', sample.tool_calls),
      metric('生成次数', sample.model_calls),
      metric('样本判断', quality.label || (diagnostic.analysis_mode === 'diagnostic' ? '可分析' : '样本不足'), text),
    ]
  }
  if (run.evaluation_type === 'retrieval') {
    return [
      metric('评测样本', summary.case_count),
      metric('Hit@K', summary.hit_at_k, percent),
      metric('证据召回率', summary.evidence_recall_at_k, percent),
      metric('MRR', summary.mrr),
      metric('表格命中率', summary.table_hit_at_k, percent),
    ]
  }
  return [
    metric('评测样本', summary.raw_case_count ?? summary.case_count),
    metric('有效回答率', summary.valid_answer_rate, percent),
    metric('引用支持率', summary.citation_precision, percent),
    metric('页码准确率', summary.page_accuracy, percent),
    metric('关键幻觉率', summary.critical_hallucination_rate, percent),
  ]
}

const clearPoll = () => {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = undefined
}

const schedulePoll = (runId: string) => {
  clearPoll()
  pollTimer = window.setTimeout(() => refreshRun(runId), 2500)
}

const refreshRun = async (runId: string) => {
  try {
    const latest = await getAdminEvaluation(runId)
    detail.value = latest
    const index = history.value.findIndex((run) => run.id === latest.id)
    if (index >= 0) history.value[index] = latest
    else history.value.unshift(latest)
    if (['queued', 'running', 'retrying'].includes(latest.status)) schedulePoll(runId)
    else clearPoll()
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || '测评状态读取失败'
    clearPoll()
  }
}

const loadHistory = async () => {
  try {
    const response = await listAdminEvaluations()
    history.value = response.items
    const current = activeRun.value || history.value[0]
    if (current) {
      selectedRunId.value = current.id
      await refreshRun(current.id)
    }
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || '测评历史读取失败'
  }
}

const selectRun = async (runId: string) => {
  selectedRunId.value = runId
  await refreshRun(runId)
}

const startEvaluation = async () => {
  if (activeRun.value) return
  starting.value = true
  loadError.value = ''
  try {
    const run = await startAdminEvaluation(selectedType.value)
    history.value = [run, ...history.value.filter((item) => item.id !== run.id)]
    selectedRunId.value = run.id
    detail.value = run as AdminEvaluationDetail
    await refreshRun(run.id)
    Message.success('测评已开始，后台完成后会自动显示结果')
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || '测评启动失败'
    Message.error(loadError.value)
  } finally {
    starting.value = false
  }
}

onMounted(loadHistory)
onUnmounted(clearPoll)
</script>

<style scoped>
.evaluation-run-panel { grid-column: 1 / -1; }
.evaluation-controls { display: flex; align-items: center; gap: 8px; }
.evaluation-alert { margin: 16px 22px 0; padding: 10px 12px; border-radius: 7px; font-size: 12px; }
.evaluation-alert.error { border: 1px solid var(--pa-danger); background: var(--pa-danger-soft); color: var(--pa-danger); }
.evaluation-current { margin: 16px 22px 0; padding: 13px 15px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface-soft); }
.evaluation-current.running, .evaluation-current.retrying { border-color: var(--pa-primary); }
.evaluation-current.failed { border-color: var(--pa-danger); background: var(--pa-danger-soft); }
.evaluation-current-top { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.evaluation-current-top > div { display: flex; align-items: center; gap: 9px; }
.evaluation-current-top strong { color: var(--pa-ink); font-size: 12px; }
.evaluation-current time, .evaluation-current p, .evaluation-current small { color: var(--pa-muted); font-size: 11px; }
.evaluation-current p { margin-top: 7px; }
.evaluation-current small { display: block; margin-top: 5px; color: var(--pa-danger); }
.evaluation-status { display: inline-flex; width: max-content; padding: 2px 7px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 10px; font-weight: 650; }
.evaluation-status.queued, .evaluation-status.running, .evaluation-status.retrying { background: var(--pa-primary-soft); color: var(--pa-primary-hover); }
.evaluation-status.completed { background: var(--pa-success-soft); color: var(--pa-success); }
.evaluation-status.failed, .evaluation-status.cancelled { background: var(--pa-danger-soft); color: var(--pa-danger); }
.evaluation-content { display: grid; grid-template-columns: minmax(250px, .8fr) minmax(0, 1.2fr); }
.evaluation-history, .evaluation-result { min-width: 0; padding: 18px 22px 22px; }
.evaluation-result { border-left: 1px solid var(--pa-border); }
.subheading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.subheading h3 { color: var(--pa-ink); font-size: 13px; }
.subheading > span { color: var(--pa-muted); font-size: 11px; }
.history-list { display: flex; max-height: 220px; flex-direction: column; gap: 5px; overflow-y: auto; }
.history-item { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 10px; border: 1px solid transparent; border-radius: 7px; background: transparent; color: var(--pa-text); text-align: left; cursor: pointer; }
.history-item:hover { background: var(--pa-surface-soft); }
.history-item.selected { border-color: var(--pa-border); background: var(--pa-surface-soft); }
.history-item:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 1px; }
.history-item-main { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.history-item-main strong { overflow: hidden; color: var(--pa-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.history-item-main small, .empty-copy, .result-placeholder, .result-note { color: var(--pa-muted); font-size: 11px; }
.empty-copy { margin: 22px 0 8px; }
.result-placeholder { display: grid; min-height: 150px; place-items: center; border: 1px dashed var(--pa-border); border-radius: 8px; text-align: center; }
.result-placeholder.error-copy { color: var(--pa-danger); }
.result-body { min-height: 150px; }
.result-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--pa-muted); font-size: 11px; }
.result-title strong { color: var(--pa-ink); font-size: 13px; }
.result-metrics { display: grid; grid-template-columns: repeat(5, minmax(80px, 1fr)); gap: 1px; margin-top: 14px; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-border); }
.result-metrics div { min-height: 73px; padding: 12px 10px; background: var(--pa-surface); }
.result-metrics span { display: block; color: var(--pa-muted); font-size: 10px; }
.result-metrics strong { display: block; margin-top: 7px; overflow: hidden; color: var(--pa-ink); font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
.result-note { margin-top: 12px; line-height: 1.6; }
@media (max-width: 900px) { .evaluation-content { grid-template-columns: 1fr; } .evaluation-result { border-top: 1px solid var(--pa-border); border-left: 0; } }
@media (max-width: 680px) { .evaluation-controls { align-items: stretch; flex-direction: column; } .evaluation-controls .arco-select { width: 100% !important; } .evaluation-current-top { align-items: flex-start; flex-direction: column; gap: 7px; } .result-metrics { grid-template-columns: repeat(2, 1fr); } }
</style>

<template>
  <section aria-label="项目文档库">
    <div class="tab-toolbar">
      <a-input v-model="search" placeholder="搜索项目中的论文" allow-clear style="max-width: 280px" />
      <div class="toolbar-actions">
        <a-button v-if="execution?.status === 'running' || execution?.status === 'queued'" @click="emit('pause')">暂停精读</a-button>
        <a-button v-else-if="execution?.status === 'paused' || execution?.status === 'failed'" type="primary" @click="emit('resume')">{{ execution.status === 'failed' ? '重试精读' : '继续精读' }}</a-button>
        <a-button v-else type="primary" :loading="executionLoading" @click="emit('start')">自动精读</a-button>
        <a-button @click="emit('add')">从论文库加入</a-button>
      </div>
    </div>
    <div v-if="execution" class="execution-status" role="status" aria-live="polite">
      <div><strong>{{ executionStatusLabel(execution.status) }}</strong><span>{{ execution.completed }}/{{ execution.total }}</span><span v-if="execution.current_paper_title">正在精读：{{ execution.current_paper_title }}</span></div>
      <a-progress :percent="execution.total ? execution.completed / execution.total : 0" :show-text="false" size="small" />
      <p v-if="execution.error" class="execution-error">{{ execution.error }}</p>
    </div>
    <a-spin :loading="loading">
      <div v-if="!loading && !papers.length" class="empty-tab"><p>项目文档库为空。从论文库中加入文献，开始你的调研。</p></div>
      <div v-else-if="!filteredPapers.length" class="empty-tab"><p>没有匹配当前搜索条件的项目论文。</p></div>
      <ul v-else class="paper-list">
        <li v-for="paper in filteredPapers" :key="paper.id" class="paper-item">
          <div class="paper-main">
            <div class="paper-title-row"><span v-if="paper.reading_plan?.order" class="reading-order">{{ paper.reading_plan.order }}</span><span class="role-tag" :class="`role-${paper.role}`">{{ roleLabel(paper.role) }}</span><span v-if="paper.reading_plan?.status" class="reading-status" :class="`status-${paper.reading_plan.status}`">{{ readingStatusLabel(paper.reading_plan.status) }}</span><button type="button" @click="emit('open', paper.paper_id)">{{ paper.paper?.title }}</button><span v-if="paper.paper?.publication_year" class="paper-year">{{ paper.paper.publication_year }}</span></div>
            <p v-if="paper.paper?.authors" class="paper-authors">{{ paper.paper.authors }}</p>
            <div v-if="paper.tags?.length" class="paper-tags"><a-tag v-for="tag in paper.tags" :key="tag" size="small">{{ tag }}</a-tag></div>
            <p v-if="paper.notes" class="paper-notes">{{ paper.notes }}</p>
            <div v-if="paper.reading_plan?.reason" class="reading-plan-summary"><p><strong>阅读理由：</strong>{{ paper.reading_plan.reason }}</p><p v-if="paper.reading_plan.focus?.length"><strong>阅读重点：</strong>{{ paper.reading_plan.focus.join('；') }}</p><p v-if="paper.reading_plan.questions?.length"><strong>读后回答：</strong>{{ paper.reading_plan.questions.join('；') }}</p></div>
            <details v-if="paper.analysis_card?.summary" class="paper-card-summary"><summary>查看论文卡片</summary><p>{{ paper.analysis_card.summary }}</p><div class="paper-card-facts"><span v-if="paper.analysis_card.methods?.length">方法 {{ paper.analysis_card.methods.length }}</span><span v-if="paper.analysis_card.datasets?.length">数据集 {{ paper.analysis_card.datasets.length }}</span><span v-if="paper.analysis_card.findings?.length">发现 {{ paper.analysis_card.findings.length }}</span><span v-if="paper.analysis_card.evidence?.length">证据 {{ paper.analysis_card.evidence.length }}</span></div></details>
          </div>
          <div class="paper-actions">
            <a-select v-if="paper.reading_plan?.order" :model-value="paper.reading_plan.status || 'pending'" size="small" style="width: 104px" aria-label="阅读状态" @update:model-value="value => emit('status', paper, String(value))"><a-option value="pending">待阅读</a-option><a-option value="reading">精读中</a-option><a-option value="completed">已完成</a-option><a-option value="skipped">已跳过</a-option></a-select>
            <a-select :model-value="paper.reading_priority" size="small" style="width: 90px" aria-label="阅读优先级" @update:model-value="value => emit('priority', paper, Number(value))"><a-option :value="5">P5 必读</a-option><a-option :value="4">P4 优先</a-option><a-option :value="3">P3</a-option><a-option :value="2">P2</a-option><a-option :value="1">P1 可选</a-option></a-select>
            <a-button size="small" status="danger" @click="emit('remove', paper)">移除论文</a-button>
          </div>
        </li>
      </ul>
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { PAPER_ROLE_LABELS, type ProjectPaperItem, type ReadingExecution } from '@/api/projects'

const props = defineProps<{ papers: ProjectPaperItem[]; loading: boolean; execution: ReadingExecution | null; executionLoading: boolean }>()
const emit = defineEmits<{ add: []; start: []; pause: []; resume: []; open: [paperId: string]; remove: [paper: ProjectPaperItem]; priority: [paper: ProjectPaperItem, priority: number]; status: [paper: ProjectPaperItem, status: string] }>()
const search = ref('')
const filteredPapers = computed(() => {
  const ordered = [...props.papers].sort((a, b) => (a.reading_plan?.order ?? Number.MAX_SAFE_INTEGER) - (b.reading_plan?.order ?? Number.MAX_SAFE_INTEGER) || b.reading_priority - a.reading_priority)
  const query = search.value.trim().toLowerCase()
  return query ? ordered.filter(item => `${item.paper?.title || ''} ${item.paper?.authors || ''}`.toLowerCase().includes(query)) : ordered
})
const roleLabel = (role: string) => PAPER_ROLE_LABELS[role] || role
const readingStatusLabel = (status: string) => ({ pending: '待阅读', reading: '精读中', completed: '已完成', skipped: '已跳过', failed: '执行失败' }[status] || status)
const executionStatusLabel = (status: string) => ({ queued: '等待执行', running: '自动精读中', paused: '已暂停', completed: '精读完成', failed: '精读失败' }[status] || status)
</script>

<style scoped>
.tab-toolbar,.toolbar-actions,.execution-status > div,.paper-title-row,.paper-tags,.paper-card-facts { display: flex; align-items: center; gap: 8px; }.tab-toolbar { justify-content: space-between; margin: 12px 0 16px; gap: 12px; }.toolbar-actions { flex-wrap: wrap; }.execution-status { margin-bottom: 16px; padding: 12px 16px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface-soft); }.execution-status > div { flex-wrap: wrap; margin-bottom: 8px; }.execution-status span,.paper-authors,.paper-notes { color: var(--pa-muted); font-size: 13px; }.execution-error { color: var(--pa-danger); }.empty-tab { padding: 48px 16px; border: 1px dashed var(--pa-border); border-radius: 8px; background: var(--pa-surface-soft); color: var(--pa-muted); text-align: center; }.paper-list { margin: 0; padding: 0; list-style: none; }.paper-item { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 8px; padding: 16px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface); }.paper-main { min-width: 0; }.paper-title-row { flex-wrap: wrap; margin-bottom: 4px; }.paper-title-row button { padding: 0; border: 0; background: transparent; color: var(--pa-primary); font-size: 15px; font-weight: 600; cursor: pointer; text-align: left; }.paper-title-row button:hover { text-decoration: underline; }.reading-order { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: var(--color-primary-light-1); color: var(--pa-primary); font-weight: 700; }.role-tag,.reading-status { padding: 2px 8px; border-radius: 999px; font-size: 11px; }.role-core { background: rgba(255,87,34,.1); color: #d9480f; }.role-related { background: rgba(32,145,255,.1); color: #1477bd; }.role-background,.status-pending { background: var(--color-fill-2); color: var(--pa-muted); }.status-reading { background: var(--color-primary-light-1); color: var(--pa-primary); }.status-completed { background: rgba(0,180,42,.12); color: var(--pa-success); }.status-skipped,.status-failed { background: rgba(245,63,63,.1); color: var(--pa-danger); }.paper-year { color: var(--pa-muted); font-size: 12px; }.paper-authors,.paper-notes { margin: 4px 0; }.paper-notes { font-style: italic; }.reading-plan-summary { max-width: 72ch; margin-top: 10px; padding: 10px 12px; border-radius: 8px; background: var(--pa-surface-soft); }.reading-plan-summary p { margin: 0; color: var(--pa-muted); font-size: 13px; }.paper-card-summary { margin-top: 10px; font-size: 12px; }.paper-card-summary summary { color: var(--pa-primary); cursor: pointer; font-weight: 600; }.paper-card-facts { flex-wrap: wrap; }.paper-card-facts span { padding: 2px 8px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); }.paper-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }@media (max-width: 767px) { .tab-toolbar,.paper-item { align-items: stretch; flex-direction: column; }.paper-actions { align-items: stretch; flex-direction: row; flex-wrap: wrap; } }
</style>

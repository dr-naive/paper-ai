<template>
  <div class="paper-list-page">
    <ProductHeader context="独立阅读" />

    <main class="paper-list-shell">
      <header class="library-header">
        <div class="header-left">
          <h1>我的论文</h1>
          <p>{{ papers.length ? `${papers.length} 篇论文，继续阅读或回到最近的研究问题。` : '上传论文，开始阅读与问答。' }}</p>
        </div>
        <a-button type="primary" size="large" @click="showUploadModal = true">上传论文</a-button>
      </header>

      <a-spin :loading="loading">
        <div v-if="!loading && papers.length === 0" class="empty-library">
          <div class="empty-document" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6">
              <path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h5"/>
            </svg>
          </div>
          <h2>从第一篇论文开始</h2>
          <p>上传 PDF 后即可阅读、生成摘要并核对 AI 引用。</p>
          <a-button type="primary" @click="showUploadModal = true">上传论文</a-button>
        </div>

        <template v-else>
          <section v-if="continuePaper" class="dashboard-row" aria-label="继续研究">
            <article class="continue-panel">
              <div class="section-heading">
                <span>继续阅读</span>
                <span>{{ lastReadLabel(continuePaper) }}</span>
              </div>
              <div class="continue-content">
                <div class="continue-document" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" stroke-width="1.7">
                    <path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h5"/>
                  </svg>
                </div>
                <div class="continue-copy">
                  <h2>{{ continuePaper.title }}</h2>
                  <p>{{ continuePaper.authors || '未知作者' }}</p>
                  <div class="reading-progress" aria-label="阅读进度">
                    <div class="reading-progress-track">
                      <span :style="{ transform: `scaleX(${paperProgress(continuePaper) / 100})` }"></span>
                    </div>
                    <span>{{ progressDescription(continuePaper) }}</span>
                  </div>
                </div>
                <div class="continue-actions">
                  <a-button type="primary" @click="openPaper(continuePaper)">继续阅读</a-button>
                </div>
              </div>
            </article>

            <aside class="recent-panel" aria-labelledby="recent-questions-title">
              <div class="section-heading">
                <span id="recent-questions-title">最近问答</span>
                <span>{{ recentMessages.length ? `${recentMessages.length} 条` : '' }}</span>
              </div>
              <div v-if="recentMessages.length" class="recent-list">
                <button
                  v-for="item in recentMessages.slice(0, 3)"
                  :key="item.id"
                  type="button"
                  class="recent-question"
                  @click="openRecentMessage(item)"
                >
                  <strong>{{ item.question }}</strong>
                </button>
              </div>
              <div v-else class="recent-empty">
                向论文提问后，最近的问题会出现在这里。
              </div>
            </aside>
          </section>

          <section class="library-section" aria-labelledby="all-papers-title">
            <div class="library-tools">
              <div>
                <h2 id="all-papers-title">全部论文</h2>
                <span>{{ filteredPapers.length }} 篇</span>
              </div>
              <div class="library-controls">
                <a-input
                  v-model="searchText"
                  allow-clear
                  placeholder="搜索标题或作者"
                  aria-label="搜索论文"
                />
                <a-select v-model="statusFilter" aria-label="筛选阅读状态">
                  <a-option value="all">全部状态</a-option>
                  <a-option value="unread">未读</a-option>
                  <a-option value="reading">阅读中</a-option>
                  <a-option value="completed">已读</a-option>
                  <a-option value="favorite">已收藏</a-option>
                </a-select>
                <a-select v-model="sortMode" aria-label="论文排序">
                  <a-option value="updated">最近阅读</a-option>
                  <a-option value="uploaded">最近上传</a-option>
                  <a-option value="title">标题排序</a-option>
                </a-select>
              </div>
            </div>

            <div v-if="filteredPapers.length || importTasks.length" class="paper-list">
              <article
                v-for="task in importTasks"
                :key="task.task_id"
                class="paper-row import-task-row"
              >
                <div class="paper-document import-document" aria-hidden="true">!</div>
                <div class="paper-content">
                  <div class="paper-title-line">
                    <h3>{{ task.filename }}</h3>
                    <a-tag size="small" :color="task.status === 'failed' ? 'red' : 'orange'">
                      {{ task.status === 'failed' ? '导入失败' : '正在导入' }}
                    </a-tag>
                  </div>
                  <p class="import-task-message">{{ task.message }}</p>
                </div>
                <div class="paper-actions">
                  <a-button
                    v-if="task.status === 'failed'"
                    size="small"
                    :loading="retryingTasks[task.task_id]"
                    :disabled="!task.retry_available"
                    @click="retryImport(task)"
                  >{{ task.retry_available ? '重试导入' : '请重新上传' }}</a-button>
                </div>
              </article>
              <article
                v-for="paper in filteredPapers"
                :key="paper.id"
                class="paper-row"
              >
                <button
                  type="button"
                  class="favorite-button"
                  :class="{ active: paper.is_favorite }"
                  :aria-label="paper.is_favorite ? '取消收藏' : '收藏论文'"
                  @click.stop="toggleFavorite(paper)"
                >
                  <span aria-hidden="true">{{ paper.is_favorite ? '★' : '☆' }}</span>
                </button>
                <div class="paper-document" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7">
                    <path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h5"/>
                  </svg>
                </div>
                <div class="paper-content">
                  <div class="paper-title-line">
                    <h3>{{ paper.title }}</h3>
                    <a-tag size="small" :color="readingStatusColor(paper.status)">
                      {{ readingStatusLabel(paper.status) }}
                    </a-tag>
                    <a-tag
                      v-if="paper.media_status && paper.media_status !== 'completed'"
                      size="small"
                      :color="mediaStatusColor(paper.media_status)"
                    >{{ paper.media_message }}</a-tag>
                  </div>
                  <div class="paper-meta">
                    <span>{{ paper.authors || '未知作者' }}</span>
                    <span aria-hidden="true">·</span>
                    <span>上传于 {{ formatDate(paper.uploaded_at) }}</span>
                  </div>
                  <p v-if="paper.abstract" class="paper-abstract">{{ paper.abstract }}</p>
                </div>
                <div class="paper-actions">
                  <a-button
                    v-if="['failed', 'interrupted', 'not_started'].includes(paper.media_status)"
                    size="small"
                    :loading="retryingTasks[`task_${paper.id}`]"
                    @click.stop="retryMediaEnhancement(paper)"
                  >重试图表增强</a-button>
                  <a-button type="primary" size="small" @click.stop="openPaper(paper)">{{ readerActionLabel(paper) }}</a-button>
                  <a-dropdown trigger="click" position="br">
                    <button
                      type="button"
                      class="paper-more"
                      aria-label="更多论文操作"
                      @click.stop
                    >•••</button>
                    <template #content>
                      <a-doption @click="toggleFavorite(paper)">
                        <template #icon><icon-star /></template>
                        {{ paper.is_favorite ? '取消收藏' : '收藏论文' }}
                      </a-doption>
                      <a-doption status="danger" @click="handleDelete(paper.id)">
                        <template #icon><icon-delete /></template>
                        删除论文
                      </a-doption>
                    </template>
                  </a-dropdown>
                </div>
              </article>
            </div>
            <div v-else class="filter-empty">
              <strong>没有匹配的论文</strong>
              <span>尝试清除搜索词或切换筛选条件。</span>
              <button type="button" @click="clearFilters">清除筛选</button>
            </div>
          </section>
        </template>
      </a-spin>
    </main>
    <PaperUploadModal v-model:visible="showUploadModal" @uploaded="handleUploadComplete" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  deletePaper,
  getPaperList,
  getRecentMessages,
  updateReadingStatus,
  retryPaperTask,
} from '@/api/paper'
import type { PaperImportTask } from '@/api/paper'
import dayjs from 'dayjs'
import ProductHeader from '@/components/ProductHeader.vue'
import PaperUploadModal from '@/components/PaperUploadModal.vue'
import { standaloneReaderLocation } from '@/router/reader'
import { removeCachedPdf } from '@/utils/pdfCache'
import { IconDelete, IconStar } from '@arco-design/web-vue/es/icon'

const loading = ref(false)
const router = useRouter()
const papers = ref<any[]>([])
const importTasks = ref<PaperImportTask[]>([])
const retryingTasks = ref<Record<string, boolean>>({})
const recentMessages = ref<any[]>([])
const searchText = ref('')
const statusFilter = ref('all')
const sortMode = ref('updated')
const showUploadModal = ref(false)
let mediaPollInterval: number | null = null

const readPosition = (paperId: string) => {
  try {
    return JSON.parse(localStorage.getItem(`paperai:reading-position:${paperId}`) || '{}')
  } catch {
    return {}
  }
}

const paperProgress = (paper: any) => Math.max(
  0,
  Math.min(100, Number(paper?.reading_progress || 0))
)

const continuePaper = computed(() => (
  [...papers.value].sort((left, right) => {
    const leftPosition = readPosition(left.id)
    const rightPosition = readPosition(right.id)
    const leftTime = new Date(leftPosition.updatedAt || left.updated_at || left.uploaded_at || 0).getTime()
    const rightTime = new Date(rightPosition.updatedAt || right.updated_at || right.uploaded_at || 0).getTime()
    return rightTime - leftTime
  })[0] || null
))

const filteredPapers = computed(() => {
  const query = searchText.value.trim().toLowerCase()
  const filtered = papers.value.filter(paper => {
    const matchesQuery = !query || `${paper.title || ''} ${paper.authors || ''}`
      .toLowerCase()
      .includes(query)
    const matchesStatus = statusFilter.value === 'all'
      || (statusFilter.value === 'favorite' ? paper.is_favorite : paper.status === statusFilter.value)
    return matchesQuery && matchesStatus
  })
  return filtered.sort((left, right) => {
    if (sortMode.value === 'title') {
      return String(left.title || '').localeCompare(String(right.title || ''), 'zh-CN')
    }
    const field = sortMode.value === 'uploaded' ? 'uploaded_at' : 'updated_at'
    return new Date(right[field] || 0).getTime() - new Date(left[field] || 0).getTime()
  })
})

const openPaper = (paper: any) => {
  router.push(standaloneReaderLocation(String(paper.id)))
}

const openRecentMessage = (item: any) => {
  router.push(standaloneReaderLocation(String(item.paper_id), {
    session: item.session_id,
    message: item.id,
  }))
}

const readerActionLabel = (paper: any) => paper.status === 'reading'
  ? '继续阅读'
  : paper.status === 'completed' ? '再次阅读' : '开始阅读'

const handleUploadComplete = () => {
  void loadPapers()
  void loadRecentMessages()
}

const progressDescription = (paper: any) => {
  const position = readPosition(paper.id)
  if (position.page && position.total) {
    return `第 ${position.page} / ${position.total} 页`
  }
  const progress = Math.round(paperProgress(paper))
  return progress > 0 ? `已阅读 ${progress}%` : '尚未开始阅读'
}

const lastReadLabel = (paper: any) => {
  const position = readPosition(paper.id)
  return relativeDate(position.updatedAt || paper.updated_at || paper.uploaded_at)
}

const relativeDate = (value: string) => {
  if (!value) return '刚刚'
  const target = dayjs(value)
  const days = dayjs().diff(target, 'day')
  if (days <= 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days} 天前`
  return target.format('MM-DD')
}

const readingStatusLabel = (status: string) => ({
  unread: '未读',
  reading: '阅读中',
  completed: '已读'
}[status] || '未读')

const readingStatusColor = (status: string) => ({
  unread: 'gray',
  reading: 'orange',
  completed: 'green'
}[status] || 'gray')

const toggleFavorite = async (paper: any) => {
  const previous = Boolean(paper.is_favorite)
  paper.is_favorite = !previous
  try {
    const result = await updateReadingStatus(paper.id, { favorite: paper.is_favorite }) as any
    paper.is_favorite = result.is_favorite
    paper.updated_at = result.updated_at
  } catch {
    paper.is_favorite = previous
    Message.error('更新收藏失败，请重试')
  }
}

const clearFilters = () => {
  searchText.value = ''
  statusFilter.value = 'all'
}

const syncMediaPolling = () => {
  const hasProcessingWork = papers.value.some(paper => paper.media_status === 'processing')
    || importTasks.value.some(task => task.status === 'pending' || task.status === 'processing')
  if (hasProcessingWork && !mediaPollInterval) {
    mediaPollInterval = window.setInterval(() => loadPapers(true), 5000)
  } else if (!hasProcessingWork && mediaPollInterval) {
    clearInterval(mediaPollInterval)
    mediaPollInterval = null
  }
}

const loadPapers = async (silent = false) => {
  if (!silent) loading.value = true
  try { 
    const response = await getPaperList({ limit: 100 })
    papers.value = response.items || response.papers || []
    importTasks.value = response.import_tasks || []
    syncMediaPolling()
  } catch (error) { 
    console.error('加载论文列表失败', error)
    if (!silent) Message.error('加载论文列表失败，请刷新页面或重新登录')
  } finally { 
    if (!silent) loading.value = false
  }
}

const loadRecentMessages = async () => {
  try {
    const response = await getRecentMessages(3) as any
    recentMessages.value = response.items || []
  } catch (error) {
    console.error('加载最近问答失败', error)
  }
}

const mediaStatusColor = (status: string) => ({
  processing: 'orange',
  completed: 'green',
  failed: 'red',
  not_started: 'gray'
}[status] || 'gray')

const retryTask = async (taskId: string, successMessage: string) => {
  retryingTasks.value = { ...retryingTasks.value, [taskId]: true }
  try {
    const result = await retryPaperTask(taskId)
    Message.success(result.message || successMessage)
    await loadPapers(true)
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    Message.error(typeof detail === 'string' ? detail : '重试失败，请稍后再试')
  } finally {
    retryingTasks.value = { ...retryingTasks.value, [taskId]: false }
  }
}

const retryImport = (task: PaperImportTask) => retryTask(task.task_id, '导入重试已排队')
const retryMediaEnhancement = (paper: any) => retryTask(`task_${paper.id}`, '图表增强重试已排队')


onUnmounted(() => {
  if (mediaPollInterval) {
    clearInterval(mediaPollInterval)
  }
})

const handleDelete = (paperId: string) => {
  Modal.warning({
    title: '确认删除',
    content: '确定要删除这篇论文吗？',
    okText: '删除',
    onOk: async () => {
      try {
        await deletePaper(paperId)
        await removeCachedPdf(paperId)
        Message.success('删除成功')
        loadPapers()
      } catch (error) {
        console.error('删除失败', error)
      }
    }
  })
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD')

onMounted(() => {
  loadPapers()
  loadRecentMessages()
})
</script>

<style scoped>
.paper-list-page {
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-ink);
}

.paper-list-shell {
  width: min(100% - 48px, 1440px);
  margin: 0 auto;
  padding: 38px 0 64px;
}

.paper-list-shell > :deep(.arco-spin) {
  display: block;
  width: 100%;
}

.library-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  min-width: 0;
}

.library-header h1 {
  margin: 0 0 6px;
  color: var(--pa-ink);
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.library-header p {
  margin: 0;
  color: var(--pa-muted);
  font-size: 14px;
}

.dashboard-row {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.continue-panel,
.recent-panel,
.library-section,
.empty-library {
  background: var(--pa-surface);
  border: 1px solid var(--pa-border);
  border-radius: 12px;
  box-shadow: 0 8px 30px oklch(0.35 0.02 45 / 0.05);
}

.continue-panel,
.recent-panel {
  padding: 15px 18px;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  color: var(--pa-ink);
  font-size: 13px;
  font-weight: 700;
}

.section-heading span:last-child {
  color: var(--pa-muted);
  font-size: 12px;
  font-weight: 400;
}

.continue-content {
  display: flex;
  align-items: center;
  gap: 13px;
}

.continue-document {
  display: grid;
  width: 46px;
  height: 56px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 9px;
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.continue-copy {
  flex: 1;
  min-width: 0;
}

.continue-copy h2 {
  display: -webkit-box;
  margin: 0 0 6px;
  overflow: hidden;
  color: var(--pa-ink);
  font-size: 15px;
  line-height: 1.35;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.continue-copy > p {
  margin: 0;
  overflow: hidden;
  color: var(--pa-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-progress {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 10px;
  color: var(--pa-muted);
  font-size: 11px;
}

.reading-progress-track {
  overflow: hidden;
  border-radius: 999px;
  background: var(--pa-border);
}

.reading-progress-track {
  width: min(220px, 55%);
  height: 5px;
}

.reading-progress-track span {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: var(--pa-primary);
  transform-origin: left;
  transition: transform 200ms ease;
}

.continue-actions {
  display: block;
  flex: 0 0 auto;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.recent-question {
  display: block;
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pa-text);
  cursor: pointer;
  text-align: left;
  transition: background-color 160ms ease;
}

.recent-question:hover {
  background: var(--pa-surface-soft);
}

.recent-question:focus-visible,
.favorite-button:focus-visible,
.paper-more:focus-visible,
.filter-empty button:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 1px;
}

.recent-question strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-question strong {
  color: var(--pa-ink);
  font-size: 12px;
  font-weight: 600;
}

.recent-empty {
  display: grid;
  min-height: 72px;
  place-items: center;
  color: var(--pa-muted);
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

.library-section {
  padding: 18px 20px 8px;
}

.library-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 16px;
}

.library-tools > div:first-child {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.library-tools h2 {
  margin: 0;
  color: var(--pa-ink);
  font-size: 16px;
}

.library-tools > div:first-child span {
  color: var(--pa-muted);
  font-size: 12px;
}

.library-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.library-controls :deep(.arco-input-wrapper) {
  width: 220px;
}

.library-controls :deep(.arco-select-view) {
  width: 120px;
}

.paper-list {
  border-top: 1px solid var(--pa-border);
}

.paper-row {
  display: flex;
  position: relative;
  align-items: center;
  gap: 14px;
  content-visibility: auto;
  contain-intrinsic-size: 130px;
  padding: 18px 8px;
  border-bottom: 1px solid var(--pa-border);
}

.paper-row:last-child {
  border-bottom: 0;
}

.import-task-row { background: oklch(0.985 0.012 28); }
.import-document { color: var(--pa-danger); background: oklch(0.95 0.025 28); font-size: 18px; font-weight: 700; }
.import-task-message { margin: 5px 0 0; color: var(--pa-danger); font-size: 12px; line-height: 1.45; }

.paper-document,
.empty-document {
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.paper-document {
  width: 44px;
  height: 54px;
  flex: 0 0 44px;
}

.favorite-button {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border: 1px solid var(--pa-border);
  border-radius: 8px;
  background: var(--pa-surface);
  color: var(--pa-text);
  cursor: pointer;
  font-size: 19px;
  line-height: 1;
  transition: color 160ms ease, background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
}

.favorite-button:hover {
  border-color: var(--pa-primary);
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
  transform: translateY(-1px);
}

.favorite-button.active {
  border-color: var(--pa-primary);
  background: var(--pa-primary);
  color: #fff;
}

.favorite-button.active:hover {
  background: var(--pa-primary-hover);
  color: #fff;
}

.favorite-button:active {
  transform: translateY(0);
}

.paper-content {
  flex: 1;
  min-width: 0;
}

.paper-title-line {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.paper-title-line h3 {
  overflow: hidden;
  margin: 0;
  color: var(--pa-ink);
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 5px;
  color: var(--pa-muted);
  font-size: 12px;
}

.paper-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
}

.paper-more {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pa-muted);
  cursor: pointer;
  font-weight: 700;
  letter-spacing: 1px;
}

.paper-more:hover {
  background: var(--pa-surface-soft);
  color: var(--pa-ink);
}

.paper-abstract {
  display: -webkit-box;
  max-width: 78ch;
  margin: 8px 0 0;
  overflow: hidden;
  color: var(--pa-text);
  font-size: 12px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.empty-library {
  display: flex;
  min-height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  padding: 40px 24px;
  text-align: center;
}

.empty-document {
  width: 52px;
  height: 52px;
  margin-bottom: 16px;
}

.empty-library h2 {
  margin: 0 0 8px;
  color: var(--pa-ink);
  font-size: 18px;
}

.empty-library p {
  margin: 0 0 20px;
  color: var(--pa-muted);
  font-size: 14px;
}

.upload-trigger {
  padding: 40px;
  border: 1px dashed var(--pa-border);
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  color: var(--pa-muted);
  background: var(--pa-bg);
}

.upload-trigger:hover { border-color: var(--pa-primary); }

.upload-progress {
  margin-top: 16px;
  padding: 16px;
  background: var(--pa-bg);
  border-radius: 8px;
}

.filter-empty {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--pa-muted);
  text-align: center;
}

.filter-empty strong {
  color: var(--pa-ink);
  font-size: 14px;
}

.filter-empty span {
  margin-top: 5px;
  font-size: 12px;
}

.filter-empty button {
  margin-top: 12px;
  border: 0;
  background: transparent;
  color: var(--pa-primary);
  cursor: pointer;
  font-size: 12px;
}

.progress-bar {
  height: 8px;
  background: var(--pa-border);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  width: 100%;
  height: 100%;
  background: var(--pa-primary);
  border-radius: 4px;
  transform-origin: left;
  transition: transform 0.3s ease;
}

.progress-text {
  margin: 0;
  font-size: 14px;
  color: var(--pa-text);
  text-align: center;
}

@media (max-width: 720px) {
  .paper-list-shell { width: calc(100% - 28px); padding-top: 28px; }
  .library-header { align-items: flex-start; gap: 20px; }
  .library-header h1 { font-size: 24px; }
  .dashboard-row { grid-template-columns: 1fr; }
  .continue-content { align-items: flex-start; flex-wrap: wrap; }
  .continue-actions { width: 100%; padding-left: 59px; }
  .library-tools { align-items: flex-start; flex-direction: column; }
  .library-controls { width: 100%; flex-wrap: wrap; }
  .library-controls :deep(.arco-input-wrapper) { width: 100%; }
  .library-controls :deep(.arco-select-view) { flex: 1; width: auto; }
  .paper-row { align-items: flex-start; flex-wrap: wrap; }
  .favorite-button { position: absolute; top: 15px; right: 8px; }
  .paper-title-line { padding-right: 28px; flex-wrap: wrap; }
  .paper-content { width: calc(100% - 60px); flex-basis: calc(100% - 60px); }
  .paper-actions { width: 100%; justify-content: flex-end; }
}

@media (prefers-reduced-motion: reduce) {
  .paper-row,
  .recent-question,
  .reading-progress-track span { transition: none; }
}
</style>

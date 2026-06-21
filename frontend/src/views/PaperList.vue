<template>
  <div class="paper-list-page">
    <ProductHeader context="论文工作台" />

    <main class="paper-list-shell">
      <div class="header">
        <div class="header-left">
          <h1>我的论文</h1>
          <p>管理已上传的论文，继续阅读或向论文提问。</p>
        </div>
        <a-button type="primary" size="large" @click="showUploadModal = true">上传论文</a-button>
      </div>
      <section class="paper-list" aria-label="论文列表">
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
          <a-list v-else :data="papers" :bordered="false">
            <template #item="{ item: paper }">
              <a-list-item :key="paper.id" class="paper-row">
                <a-list-item-meta>
                  <template #avatar>
                    <div class="paper-document" aria-hidden="true">
                      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7">
                        <path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h5"/>
                      </svg>
                    </div>
                  </template>
                  <template #title><a-link @click="$router.push(`/paper/${paper.id}`)">{{ paper.title }}</a-link></template>
                  <template #description>
                    <div class="paper-meta">
                      <span>{{ paper.authors || '未知作者' }}</span>
                      <span aria-hidden="true">·</span>
                      <span>{{ formatDate(paper.uploaded_at) }}</span>
                      <a-tag
                        v-if="paper.media_status"
                        size="small"
                        :color="mediaStatusColor(paper.media_status)"
                        class="media-status"
                      >{{ paper.media_message }}</a-tag>
                    </div>
                  </template>
                </a-list-item-meta>
                <template #actions>
                  <div class="paper-actions">
                    <a-button type="text" size="small" @click="$router.push(`/paper/${paper.id}`)">阅读</a-button>
                    <a-button type="text" size="small" @click="$router.push(`/paper/${paper.id}`)">问答</a-button>
                    <a-button type="text" size="small" status="danger" @click="handleDelete(paper.id)">删除</a-button>
                  </div>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-spin>
      </section>
    </main>
    <a-modal v-model:visible="showUploadModal" title="上传论文" :footer="false">
      <a-spin :spinning="uploading" tip="上传中...">
        <a-upload :limit="1" accept=".pdf" :auto-upload="false" action="" :custom-request="customUpload" @change="handleFileChange">
          <template #upload-button><div class="upload-trigger"><p>点击或拖拽上传 PDF 文件</p></div></template>
        </a-upload>
      </a-spin>
      <div v-if="uploading" class="upload-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ transform: `scaleX(${progressPercent / 100})` }"></div>
        </div>
        <p class="progress-text">{{ progressText }}</p>
      </div>
      <div v-if="!uploading && selectedFile" style="margin-top: 16px; text-align: right;">
        <a-button type="primary" @click="handleUpload" :disabled="!selectedFile">开始上传</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { FileItem } from '@arco-design/web-vue'
import type { RequestOption, UploadRequest } from '@arco-design/web-vue/es/upload/interfaces'
import { getPaperList, uploadPaper, deletePaper, getTaskStatus } from '@/api/paper'
import dayjs from 'dayjs'
import ProductHeader from '@/components/ProductHeader.vue'

const loading = ref(false)
const papers = ref<any[]>([])
const showUploadModal = ref(false)
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const progressPercent = ref(0)
const progressText = ref('')
let pollInterval: number | null = null
let mediaPollInterval: number | null = null

const syncMediaPolling = () => {
  const hasProcessingMedia = papers.value.some(paper => paper.media_status === 'processing')
  if (hasProcessingMedia && !mediaPollInterval) {
    mediaPollInterval = window.setInterval(() => loadPapers(true), 5000)
  } else if (!hasProcessingMedia && mediaPollInterval) {
    clearInterval(mediaPollInterval)
    mediaPollInterval = null
  }
}

const loadPapers = async (silent = false) => {
  if (!silent) loading.value = true
  try { 
    const response = await getPaperList()
    papers.value = response.items || response.papers || []
    syncMediaPolling()
  } catch (error) { 
    console.error('加载论文列表失败', error)
    if (!silent) Message.error('加载论文列表失败，请刷新页面或重新登录')
  } finally { 
    if (!silent) loading.value = false
  }
}

const mediaStatusColor = (status: string) => ({
  processing: 'orange',
  completed: 'green',
  failed: 'red',
  not_started: 'gray'
}[status] || 'gray')


const customUpload = (options: RequestOption): UploadRequest => {
  // 拦截 a-upload 的默认上传行为（包括重试按钮）
  // 不做任何事，所有上传由 handleUpload 按钮触发
  options.onSuccess?.({})
  return {
    abort: () => {}
  }
}

const handleFileChange = (fileList: FileItem[]) => {
  const latestFile = fileList[fileList.length - 1]
  if (latestFile && latestFile.file) {
    selectedFile.value = latestFile.file
  } else {
    selectedFile.value = null
  }
}

const pollTaskStatus = async (taskId: string) => {
  try {
    const response = await getTaskStatus(taskId)
    progressPercent.value = response.progress
    progressText.value = response.message
    
    if (response.status === 'ready' || response.status === 'completed') {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      progressPercent.value = 100
      const mediaEnhancing = response.status === 'ready'
      progressText.value = mediaEnhancing ? '论文已可用，图表继续后台增强' : '处理完成！'
      
      setTimeout(() => {
        Message.success(mediaEnhancing ? '论文已可用，图表将在后台继续增强' : '上传成功')
        showUploadModal.value = false
        selectedFile.value = null
        uploading.value = false
        progressPercent.value = 0
        progressText.value = ''
        loadPapers()
      }, 500)
    } else if (response.status === 'failed') {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      uploading.value = false
      Message.error(response.message || '处理失败')
    }
  } catch (error) {
    console.error('查询任务状态失败', error)
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) { 
    Message.warning('请选择文件')
    return 
  }
  
  uploading.value = true
  progressPercent.value = 0
  progressText.value = '上传文件...'
  
  try { 
    // 异步上传，立即返回任务ID
    const response = await uploadPaper(selectedFile.value)
    const taskId = response.task_id || response.taskId

    if (!taskId) {
      throw new Error('未能获取任务ID')
    }
    
    progressPercent.value = 5
    progressText.value = '上传成功，正在后台处理...'
    
    // 开始轮询任务状态
    pollInterval = window.setInterval(() => {
      pollTaskStatus(taskId)
    }, 2000)
    
  } catch (error: any) {
    uploading.value = false
    progressPercent.value = 0
    progressText.value = ''
    console.error('上传失败', error)
    Message.error(error?.response?.data?.detail || '上传失败，请检查文件格式')
  }
}

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
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
        Message.success('删除成功')
        loadPapers()
      } catch (error) {
        console.error('删除失败', error)
      }
    }
  })
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD')

onMounted(() => { loadPapers() })
</script>

<style scoped>
.paper-list-page {
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-ink);
}

.paper-list-shell {
  width: min(100% - 48px, 1280px);
  margin: 0 auto;
  padding: 42px 0 64px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.header-left {
  min-width: 0;
}

.header h1 {
  margin: 0 0 6px;
  color: var(--pa-ink);
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.header p {
  margin: 0;
  color: var(--pa-muted);
  font-size: 14px;
}

.paper-list {
  min-height: 220px;
  background: var(--pa-surface);
  border: 1px solid var(--pa-border);
  border-radius: 12px;
  padding: 8px 20px;
  box-shadow: 0 8px 30px oklch(0.35 0.02 45 / 0.05);
}

.paper-row {
  content-visibility: auto;
  contain-intrinsic-size: 82px;
  padding: 22px 8px !important;
  transition: background 0.2s ease;
}

.paper-row:hover { background: var(--pa-primary-soft); }

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
  height: 44px;
}

.paper-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.paper-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.empty-library {
  display: flex;
  min-height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
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

.media-status {
  margin-left: 8px;
  vertical-align: middle;
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
  .paper-list-shell { width: min(100% - 28px, 1280px); padding-top: 28px; }
  .header { align-items: flex-start; gap: 20px; }
  .header h1 { font-size: 24px; }
  .paper-list { padding-inline: 10px; }
  .paper-row :deep(.arco-list-item-main) { min-width: 0; }
  .paper-actions { flex-direction: column; align-items: stretch; }
}

@media (prefers-reduced-motion: reduce) {
  .paper-row { transition: none; }
}
</style>

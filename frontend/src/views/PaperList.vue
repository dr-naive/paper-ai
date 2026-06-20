<template>
  <div class="paper-list-page">
    <div class="header">
      <div class="header-left">
        <a-button type="text" @click="$router.push('/home')" style="margin-right: 8px">
          <template #icon>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
          </template>
          首页
        </a-button>
        <h1>📚 我的论文</h1>
      </div>
      <a-button type="primary" @click="showUploadModal = true">上传论文</a-button>
    </div>
    <div class="paper-list">
      <a-spin :loading="loading">
        <a-list :data="papers" :bordered="false">
          <template #item="{ item: paper }">
            <a-list-item :key="paper.id">
              <a-list-item-meta>
                <template #avatar><a-avatar :style="{ backgroundColor: '#6366f1' }"></a-avatar></template>
                <template #title><a-link @click="$router.push(`/paper/${paper.id}`)">{{ paper.title }}</a-link></template>
                <template #description>
                  <span>{{ paper.authors || '未知作者' }}</span><span> | </span><span>{{ formatDate(paper.uploaded_at) }}</span>
                  <a-tag
                    v-if="paper.media_status"
                    size="small"
                    :color="mediaStatusColor(paper.media_status)"
                    class="media-status"
                  >{{ paper.media_message }}</a-tag>
                </template>
              </a-list-item-meta>
              <template #actions>
                <a-button type="text" size="small" @click="$router.push(`/paper/${paper.id}`)">阅读</a-button>
                <a-button type="text" size="small" @click="$router.push(`/paper/${paper.id}/qa`)">问答</a-button>
                <a-button type="text" size="small" status="danger" @click="handleDelete(paper.id)">删除</a-button>
              </template>
            </a-list-item>
          </template>
        </a-list>
      </a-spin>
    </div>
    <a-modal v-model:visible="showUploadModal" title="上传论文" :footer="false">
      <a-spin :spinning="uploading" tip="上传中...">
        <a-upload :limit="1" accept=".pdf" :auto-upload="false" action="" :custom-request="customUpload" @change="handleFileChange">
          <template #upload-button><div class="upload-trigger"><p>点击或拖拽上传 PDF 文件</p></div></template>
        </a-upload>
      </a-spin>
      <div v-if="uploading" class="upload-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
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
    console.log('上传响应:', response)
    
    const taskId = response.task_id || response.taskId
    console.log('获取到的任务ID:', taskId)
    
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
  background: #f5f7fa;
  padding: 24px;
  color: #1d2129;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
}

.header h1 {
  margin: 0;
  color: #1d2129;
}

.paper-list {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px;
}

.upload-trigger {
  padding: 40px;
  border: 2px dashed #e5e6eb;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  color: #86909c;
}

.upload-progress {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.media-status {
  margin-left: 8px;
  vertical-align: middle;
}

.progress-bar {
  height: 8px;
  background: #e5e6eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  margin: 0;
  font-size: 14px;
  color: #646a73;
  text-align: center;
}
</style>

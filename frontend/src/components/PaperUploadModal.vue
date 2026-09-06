<template>
  <a-modal
    :visible="visible"
    title="上传论文"
    :footer="false"
    :closable="!uploading"
    :mask-closable="!uploading"
    @cancel="close"
  >
    <a-spin :spinning="uploading" tip="上传中...">
      <a-upload
        :limit="1"
        accept=".pdf"
        :auto-upload="false"
        action=""
        :custom-request="customUpload"
        @change="handleFileChange"
      >
        <template #upload-button>
          <div class="upload-trigger">
            <p>点击或拖拽上传 PDF 文件</p>
          </div>
        </template>
      </a-upload>
    </a-spin>

    <p v-if="projectId" class="upload-context-note">
      处理完成后，论文会自动加入当前项目「{{ projectTitle || '当前项目' }}」。
    </p>

    <div v-if="uploading || attachError" class="upload-progress" role="status" aria-live="polite">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ transform: `scaleX(${progressPercent / 100})` }"></div>
      </div>
      <p class="progress-text">{{ attachError || progressText }}</p>
      <a-button v-if="attachError" type="primary" size="small" @click="retryAttach">重试加入项目</a-button>
    </div>

    <div v-if="!uploading && !attachError && selectedFile" class="upload-actions">
      <a-button type="primary" @click="handleUpload" :disabled="!selectedFile">开始上传</a-button>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FileItem } from '@arco-design/web-vue'
import type { RequestOption, UploadRequest } from '@arco-design/web-vue/es/upload/interfaces'
import { addProjectPaper } from '@/api/projects'
import { getTaskStatus, type PaperTaskStatusResponse, uploadPaper, type PaperUploadResponse } from '@/api/paper'

const props = withDefaults(defineProps<{
  visible: boolean
  projectId?: string
  projectTitle?: string
}>(), {
  projectId: '',
  projectTitle: '',
})

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  uploaded: [payload: { paperId: string; taskId: string; projectId?: string }]
}>()

const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const progressPercent = ref(0)
const progressText = ref('')
const attachError = ref('')
const activeTaskId = ref('')
const activePaperId = ref('')
let pollInterval: number | null = null
let pollInFlight = false

const stopPolling = () => {
  if (pollInterval !== null) {
    window.clearInterval(pollInterval)
    pollInterval = null
  }
}

const reset = () => {
  stopPolling()
  selectedFile.value = null
  uploading.value = false
  progressPercent.value = 0
  progressText.value = ''
  attachError.value = ''
  activeTaskId.value = ''
  activePaperId.value = ''
}

const close = () => {
  if (uploading.value) return
  reset()
  emit('update:visible', false)
}

const customUpload = (options: RequestOption): UploadRequest => {
  // a-upload is used for file selection only; the request is sent explicitly
  // after the user confirms the upload action below.
  options.onSuccess?.({})
  return { abort: () => {} }
}

const handleFileChange = (fileList: FileItem[]) => {
  const latestFile = fileList[fileList.length - 1]
  selectedFile.value = latestFile?.file || null
  attachError.value = ''
}

const finishUpload = async () => {
  if (!activePaperId.value || !activeTaskId.value) return
  attachError.value = ''
  if (props.projectId) {
    try {
      await addProjectPaper(props.projectId, { paper_id: activePaperId.value })
    } catch (error) {
      console.error('上传论文后加入项目失败:', error)
      uploading.value = false
      attachError.value = '论文已上传，但加入当前项目失败，请重试。'
      return
    }
  }

  const paperId = activePaperId.value
  const taskId = activeTaskId.value
  const projectId = props.projectId || undefined
  uploading.value = false
  progressPercent.value = 100
  progressText.value = props.projectId ? '已上传并加入当前项目' : '处理完成'
  Message.success(props.projectId ? '论文已上传并加入当前项目' : '上传成功')
  emit('uploaded', { paperId, taskId, projectId })
  window.setTimeout(() => {
    if (!uploading.value && !attachError.value) {
      reset()
      emit('update:visible', false)
    }
  }, 350)
}

const pollTaskStatus = async () => {
  if (!activeTaskId.value || pollInFlight) return
  pollInFlight = true
  try {
    const response: PaperTaskStatusResponse = await getTaskStatus(activeTaskId.value)
    progressPercent.value = Math.max(0, Math.min(100, Number(response.progress || 0)))
    progressText.value = response.message || '正在处理论文...'
    if (response.status === 'ready' || response.status === 'completed') {
      stopPolling()
      await finishUpload()
    } else if (response.status === 'failed') {
      stopPolling()
      uploading.value = false
      progressText.value = response.message || '处理失败，请重新上传'
      Message.error(progressText.value)
    }
  } catch (error) {
    // Keep the polling session alive for transient network failures. The user
    // can still close the modal once the worker reports a terminal state.
    console.error('查询上传任务状态失败:', error)
  } finally {
    pollInFlight = false
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    Message.warning('请选择文件')
    return
  }

  uploading.value = true
  attachError.value = ''
  progressPercent.value = 0
  progressText.value = '正在上传文件...'
  try {
    const response: PaperUploadResponse = await uploadPaper(selectedFile.value)
    const taskId = response.task_id || response.taskId || ''
    const paperId = response.paper_id || response.paperId || ''
    if (!taskId || !paperId) throw new Error('未能获取论文处理任务')
    activeTaskId.value = taskId
    activePaperId.value = paperId
    progressPercent.value = 5
    progressText.value = response.message || '上传成功，正在处理论文...'
    await pollTaskStatus()
    if (activeTaskId.value && uploading.value) {
      pollInterval = window.setInterval(() => { void pollTaskStatus() }, 2000)
    }
  } catch (error: any) {
    uploading.value = false
    progressPercent.value = 0
    progressText.value = ''
    Message.error(error?.response?.data?.detail || '上传失败，请检查文件格式')
  }
}

const retryAttach = () => {
  if (!activePaperId.value || !activeTaskId.value) return
  uploading.value = true
  progressPercent.value = 100
  progressText.value = '正在加入当前项目...'
  void finishUpload()
}

onUnmounted(stopPolling)
</script>

<style scoped>
.upload-trigger { display: grid; min-height: 108px; place-items: center; padding: 18px 24px; border: 1px dashed var(--pa-border-strong); border-radius: var(--pa-radius-md); background: var(--pa-surface-soft); color: var(--pa-muted); text-align: center; }
.upload-trigger p { margin: 0; font-size: 13px; }
.upload-context-note { margin: 12px 0 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.upload-progress { margin-top: 16px; }
.progress-bar { height: 6px; overflow: hidden; border-radius: 999px; background: var(--pa-border); }
.progress-fill { width: 100%; height: 100%; transform-origin: left center; background: var(--pa-primary); transition: transform 180ms ease-out; }
.progress-text { margin: 8px 0 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.upload-progress :deep(.arco-btn) { margin-top: 10px; }
.upload-actions { display: flex; justify-content: flex-end; margin-top: 16px; }
@media (prefers-reduced-motion: reduce) { .progress-fill { transition: none; } }
</style>

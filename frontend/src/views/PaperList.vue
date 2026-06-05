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
                <template #description><span>{{ paper.authors || '未知作者' }}</span><span> | </span><span>{{ formatDate(paper.uploaded_at) }}</span></template>
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
    <a-modal v-model:visible="showUploadModal" title="上传论文" @ok="handleUpload">
      <a-upload :limit="1" accept=".pdf" :auto-upload="false" @change="handleFileChange">
        <template #upload-button><div class="upload-trigger"><p>点击或拖拽上传 PDF 文件</p></div></template>
      </a-upload>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { FileItem } from '@arco-design/web-vue' 
import { getPaperList, uploadPaper, deletePaper } from '@/api/paper'
import dayjs from 'dayjs'

const loading = ref(false)
const papers = ref<any[]>([])
const showUploadModal = ref(false)
const selectedFile = ref<File | null>(null)

const loadPapers = async () => {
  loading.value = true
  try { 
    const response = await getPaperList()
    papers.value = response.items || response.papers || []
  } catch (error) { 
    console.error('加载论文列表失败', error)
  } finally { 
    loading.value = false 
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

const handleUpload = async () => {
  if (!selectedFile.value) { 
    Message.warning('请选择文件')
    return 
  }
  try { 
    await uploadPaper(selectedFile.value)
    Message.success('上传成功')
    showUploadModal.value = false
    selectedFile.value = null
    loadPapers()
  } catch (error: any) {
    console.error('上传失败', error)
    Message.error(error?.response?.data?.detail || '上传失败，请检查文件格式')
  }
}

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
</style>

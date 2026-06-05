<template>
  <div class="notes-page">
    <a-page-header title="我的笔记" />
    <a-space direction="vertical" :style="{ width: '100%' }">
      <div class="search-bar">
        <a-input-search placeholder="搜索笔记" @search="handleSearch" />
        <a-button type="primary" @click="createNote">新建笔记</a-button>
      </div>
      <a-card :bordered="false" class="notes-list">
        <a-list
          v-if="notes.length > 0"
          :data-source="notes"
          render-item="note"
        >
          <template #renderItem="{ item }">
            <a-list-item
              class="note-item"
              @click="viewNote(item.id)"
            >
              <a-list-item-meta>
                <template #title>
                  <a>{{ item.title }}</a>
                </template>
                <template #description>
                  <span>{{ item.content.substring(0, 100) }}...</span>
                </template>
              </a-list-item-meta>
              <template #extra>
                <span>{{ formatDate(item.created_at) }}</span>
              </template>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无笔记" />
      </a-card>
    </a-space>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑笔记' : '新建笔记'"
      @ok="saveNote"
    >
      <a-form :model="noteForm">
        <a-form-item label="标题">
          <a-input v-model="noteForm.title" placeholder="请输入笔记标题" />
        </a-form-item>
        <a-form-item label="内容">
          <a-textarea
            v-model="noteForm.content"
            placeholder="请输入笔记内容"
            :rows="6"
          />
        </a-form-item>
        <a-form-item label="标签">
          <a-select v-model="noteForm.tags" mode="tags" placeholder="输入标签后回车">
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { note } from '@/api'
import dayjs from 'dayjs'

const notes = ref([])
const modalVisible = ref(false)
const isEdit = ref(false)
const noteForm = ref({
  id: '',
  title: '',
  content: '',
  tags: [] as string[]
})

const handleSearch = (value: string) => {
  console.log('搜索:', value)
}

const createNote = () => {
  isEdit.value = false
  noteForm.value = { id: '', title: '', content: '', tags: [] }
  modalVisible.value = true
}

const viewNote = (id: string) => {
  console.log('查看笔记:', id)
}

const saveNote = async () => {
  try {
    if (isEdit.value) {
      await note.updateNote(noteForm.value.id, noteForm.value)
    } else {
      await note.createNote(noteForm.value)
    }
    modalVisible.value = false
    loadNotes()
  } catch (error) {
    console.error('保存笔记失败:', error)
  }
}

const loadNotes = async () => {
  try {
    const response = await note.getNoteList()
    notes.value = response.data
  } catch (error) {
    console.error('加载笔记失败:', error)
  }
}

const formatDate = (date: string) => {
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  loadNotes()
})
</script>

<style scoped>
.notes-page {
  padding: 24px;
}

.search-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-bar :deep(.arco-input-wrapper) {
  flex: 1;
  max-width: 400px;
}

.notes-list {
  min-height: 400px;
}

.note-item {
  cursor: pointer;
  transition: all 0.3s;
}

.note-item:hover {
  background: #f5f5f5;
}
</style>
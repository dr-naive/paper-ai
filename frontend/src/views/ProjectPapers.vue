<template>
  <ProjectShell :recent-projects="project ? [project] : []">
    <template v-if="project">
      <ProjectHeader :project="project" />
      <main class="project-page papers-page">
        <header class="page-heading">
          <div>
            <h1>项目论文</h1>
            <p>只显示已经加入当前项目的论文；阅读时会保留当前项目上下文。</p>
          </div>
          <a-button type="primary" @click="showUploadModal = true">上传本地 PDF</a-button>
        </header>

        <section class="papers-toolbar" aria-label="项目论文筛选">
          <a-input v-model="search" allow-clear placeholder="搜索标题或作者" />
          <a-select v-model="statusFilter" style="width: 150px" aria-label="筛选阅读状态">
            <a-option value="all">全部状态</a-option>
            <a-option value="pending">待阅读</a-option>
            <a-option value="reading">阅读中</a-option>
            <a-option value="completed">已完成</a-option>
          </a-select>
          <span class="papers-count">{{ filteredPapers.length }} / {{ papers.length }} 篇</span>
        </section>

        <a-spin :loading="loading">
          <section v-if="!loading && !papers.length" class="papers-empty">
            <h2>项目中还没有论文</h2>
            <p>直接上传本地 PDF，处理完成后会自动加入当前项目。</p>
            <a-button type="primary" @click="showUploadModal = true">上传本地 PDF</a-button>
          </section>
          <section v-else-if="loading" class="papers-empty" aria-live="polite">
            <h2>正在加载项目论文</h2>
          </section>
          <section v-else-if="!filteredPapers.length" class="papers-empty">
            <h2>没有匹配的论文</h2>
            <p>调整搜索词或阅读状态筛选条件。</p>
          </section>
          <div v-else class="paper-table-wrap">
            <table class="paper-table">
              <caption class="pa-sr-only">当前项目论文列表</caption>
              <thead>
                <tr>
                  <th scope="col">论文</th>
                  <th scope="col">年份</th>
                  <th scope="col">状态</th>
                  <th scope="col"><span class="pa-sr-only">操作</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredPapers" :key="item.id">
                  <td class="paper-title">
                    <strong :title="item.paper?.title || undefined">{{ item.paper?.title || '论文信息待同步' }}</strong>
                    <span v-if="item.paper?.authors" class="paper-authors" :title="item.paper.authors">{{ item.paper.authors }}</span>
                    <span v-if="item.paper?.venue">{{ item.paper.venue }}</span>
                  </td>
                  <td>{{ item.paper?.publication_year || '—' }}</td>
                  <td><span class="reading-status" :class="`status-${readingStatus(item)}`">{{ readingStatusLabel(item) }}</span></td>
                  <td class="paper-action">
                    <a-button size="small" :disabled="!item.paper" @click="openReader(item)">{{ item.paper ? readerActionLabel(item) : '等待解析' }}</a-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </a-spin>
      </main>
      <PaperUploadModal
        v-model:visible="showUploadModal"
        :project-id="projectId"
        :project-title="project.title"
        @uploaded="handleUploaded"
      />
    </template>
    <main v-else-if="loading" class="project-loading" aria-live="polite">正在加载项目…</main>
    <a-empty v-else description="项目不存在或无访问权限" class="project-error" />
  </ProjectShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getProject, listProjectPapers, type ProjectPaperItem, type ResearchProject } from '@/api/projects'
import ProjectHeader from '@/components/project/ProjectHeader.vue'
import ProjectShell from '@/components/project/ProjectShell.vue'
import PaperUploadModal from '@/components/PaperUploadModal.vue'
import { useProjectStore } from '@/stores/project'
import { projectReaderLocation } from '@/router/reader'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const projectId = computed(() => String(route.params.projectId || ''))
const project = ref<ResearchProject | null>(null)
const papers = ref<ProjectPaperItem[]>([])
const loading = ref(false)
const search = ref('')
const statusFilter = ref('all')
const showUploadModal = ref(false)

const readingStatus = (item: ProjectPaperItem) => {
  if (item.reading_plan?.status) return item.reading_plan.status
  const progress = item.paper?.reading_progress || 0
  if (progress >= 100) return 'completed'
  if (progress > 0) return 'reading'
  return 'pending'
}

const readingStatusLabel = (item: ProjectPaperItem) => ({ pending: '未阅读', reading: '阅读中', completed: '已阅读', skipped: '已跳过', failed: '解析失败' }[readingStatus(item)] || '未阅读')
const readerActionLabel = (item: ProjectPaperItem) => ({ pending: '开始阅读', reading: '继续阅读', completed: '阅读', skipped: '阅读', failed: '阅读' }[readingStatus(item)] || '阅读')

const filteredPapers = computed(() => {
  const query = search.value.trim().toLowerCase()
  return papers.value.filter(item => {
    const text = `${item.paper?.title || ''} ${item.paper?.authors || ''}`.toLowerCase()
    return (!query || text.includes(query)) && (statusFilter.value === 'all' || readingStatus(item) === statusFilter.value)
  })
})

const loadPage = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const [projectResult, papersResult] = await Promise.all([getProject(projectId.value), listProjectPapers(projectId.value)])
    project.value = projectResult
    papers.value = papersResult.items || []
    projectStore.setProject(project.value)
    projectStore.setPapers(papers.value)
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '加载项目论文失败')
  } finally {
    loading.value = false
  }
}

const openReader = (item: ProjectPaperItem) => {
  if (!item.paper) return
  router.push(projectReaderLocation(projectId.value, item.paper_id))
}

const handleUploaded = async () => {
  await loadPage()
}

onMounted(loadPage)
</script>

<style scoped>
.project-page { max-width: var(--pa-content-max); margin: 0 auto; padding: 28px 28px 56px; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.page-heading h1 { margin: 0; color: var(--pa-ink); font-size: 26px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.25; text-wrap: balance; }
.page-heading p { margin: 5px 0 0; color: var(--pa-muted); font-size: 13px; line-height: 1.5; }
.papers-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.papers-toolbar :deep(.arco-input-wrapper) { max-width: 320px; }
.papers-count { margin-left: auto; color: var(--pa-muted); font-size: 12px; }
.paper-table-wrap { overflow-x: auto; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface); }
.paper-table { width: 100%; min-width: 720px; border-collapse: collapse; color: var(--pa-text); font-size: 13px; }
.paper-table th { padding: 10px 14px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 11px; font-weight: 650; text-align: left; }
.paper-table td { padding: 12px 14px; border-bottom: 1px solid var(--pa-border); vertical-align: middle; }
.paper-table tbody tr:last-child td { border-bottom: 0; }
.paper-table tbody tr:hover { background: var(--pa-surface-soft); }
.paper-table th:nth-child(2), .paper-table td:nth-child(2) { width: 88px; }
.paper-table th:nth-child(3), .paper-table td:nth-child(3) { width: 100px; }
.paper-table th:nth-child(4), .paper-table td:nth-child(4) { width: 112px; }
.paper-title { min-width: 420px; }
.paper-title strong { display: block; overflow: hidden; color: var(--pa-ink); font-size: 14px; font-weight: 650; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.paper-title span { display: block; margin-top: 4px; overflow: hidden; color: var(--pa-muted); font-size: 12px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.paper-title .paper-authors { margin-top: 3px; }
.reading-status { display: inline-flex; min-width: 64px; justify-content: center; padding: 4px 8px; border-radius: 999px; font-size: 11px; }
.status-pending { background: var(--pa-surface-soft); color: var(--pa-muted); }
.status-reading { background: var(--pa-primary-soft); color: var(--pa-primary-hover); }
.status-completed { background: var(--pa-success-soft); color: var(--pa-success); }
.status-skipped, .status-failed { background: var(--pa-danger-soft); color: var(--pa-danger); }
.paper-action { white-space: nowrap; text-align: right; }
.papers-empty { padding: 72px 24px; border: 1px dashed var(--pa-border); border-radius: var(--pa-radius-lg); background: var(--pa-surface); text-align: center; }
.papers-empty h2 { margin: 0; font-size: 18px; font-weight: 650; }
.papers-empty p { margin: 10px 0 22px; color: var(--pa-muted); font-size: 14px; }
.project-loading, .project-error { padding: 100px 32px; color: var(--pa-muted); text-align: center; }
@media (max-width: 680px) { .project-page { padding: 24px 16px 40px; } .page-heading { align-items: flex-start; flex-direction: column; } .page-heading :deep(.arco-btn) { width: 100%; } .papers-toolbar { align-items: stretch; flex-wrap: wrap; } .papers-toolbar :deep(.arco-input-wrapper) { max-width: none; flex: 1 1 100%; } .papers-count { margin-left: 0; } }
</style>

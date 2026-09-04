<template>
  <ProjectShell :recent-projects="projects">
    <ProductHeader context="项目">
      <template #actions>
        <a-button size="small" @click="router.push('/library')">打开论文库</a-button>
      </template>
    </ProductHeader>

    <main class="projects-page">
      <header class="projects-heading">
        <div>
          <p class="page-kicker">Research projects</p>
          <h1>我的科研项目</h1>
          <p class="page-description">把研究主题、项目论文和写作文档放在同一个工作区。</p>
        </div>
        <a-button type="primary" size="large" @click="showCreateModal = true">新建项目</a-button>
      </header>

      <a-spin :loading="loading">
        <section v-if="!loading && !projects.length" class="projects-empty" aria-live="polite">
          <div class="empty-mark" aria-hidden="true">＋</div>
          <h2>从一个研究主题开始</h2>
          <p>创建项目后，你可以在概览、文献发现、项目论文和写作之间切换。</p>
          <a-button type="primary" @click="showCreateModal = true">创建第一个项目</a-button>
        </section>

        <section v-else-if="!loading" class="project-grid" aria-label="科研项目列表">
          <article
            v-for="project in projects"
            :key="project.id"
            :class="['project-card', { 'is-deleting': deletingProjectId === project.id }]"
          >
            <RouterLink
              class="project-card__main"
              :to="{ name: 'ProjectOverview', params: { projectId: project.id } }"
            >
              <div class="project-card__topline">
                <span class="project-card__label">研究项目</span>
                <span v-if="project.updated_at" class="project-card__time">{{ formatTime(project.updated_at) }}</span>
              </div>
              <h2>{{ project.title }}</h2>
              <p class="project-card__topic">{{ project.research_topic }}</p>
              <div class="project-card__meta">
                <span>{{ project.paper_count ?? 0 }} 篇项目论文</span>
              </div>
              <span class="project-card__open">打开项目 <span aria-hidden="true">→</span></span>
            </RouterLink>
            <div class="project-card__actions">
              <button
                type="button"
                class="project-card__delete"
                :disabled="Boolean(deletingProjectId)"
                :aria-label="`删除项目 ${project.title}`"
                @click="openDeleteModal(project)"
              >
                {{ deletingProjectId === project.id ? '正在删除…' : '删除项目' }}
              </button>
            </div>
          </article>
        </section>
      </a-spin>
    </main>

    <a-modal v-model:visible="showCreateModal" title="新建研究项目" :ok-loading="creating" @ok="handleCreate">
      <a-form :model="createForm" layout="vertical">
        <a-form-item field="title" label="项目名称" required>
          <a-input v-model="createForm.title" placeholder="例如：多模态模型的可靠性研究" />
        </a-form-item>
        <a-form-item field="research_topic" label="研究主题" required>
          <a-input v-model="createForm.research_topic" placeholder="用一句话描述你要研究的问题" />
        </a-form-item>
        <details class="optional-fields">
          <summary>补充研究信息（可选）</summary>
          <div class="optional-fields__body">
            <a-form-item field="field" label="所属领域">
              <a-input v-model="createForm.research_scope.field" placeholder="例如：自然语言处理" />
            </a-form-item>
            <a-form-item field="research_question" label="核心问题">
              <a-textarea v-model="createForm.research_scope.research_question" :auto-size="{ minRows: 2, maxRows: 4 }" />
            </a-form-item>
            <a-form-item field="abstract" label="项目说明">
              <a-textarea v-model="createForm.abstract" :auto-size="{ minRows: 2, maxRows: 4 }" placeholder="研究背景或预期目标" />
            </a-form-item>
          </div>
        </details>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="showDeleteModal"
      title="删除项目"
      :footer="false"
      :closable="!deletingProjectId"
      :mask-closable="!deletingProjectId"
      @cancel="closeDeleteModal"
    >
      <div v-if="deleteTarget" class="delete-confirmation">
        <p>确定删除项目“<strong>{{ deleteTarget.title }}</strong>”吗？</p>
        <p class="delete-confirmation__detail">
          项目内的写作文档、证据、研究记录和论文关联会一并删除。论文库中的原始论文不会被删除，此操作无法撤销。
        </p>
        <div class="delete-confirmation__actions">
          <a-button :disabled="Boolean(deletingProjectId)" @click="closeDeleteModal">取消</a-button>
          <a-button type="primary" status="danger" :loading="Boolean(deletingProjectId)" @click="handleDelete">
            删除项目
          </a-button>
        </div>
      </div>
    </a-modal>
  </ProjectShell>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import ProductHeader from '@/components/ProductHeader.vue'
import ProjectShell from '@/components/project/ProjectShell.vue'
import { createProject, deleteProject, listProjects, type ResearchProject } from '@/api/projects'

const router = useRouter()
const projects = ref<ResearchProject[]>([])
const loading = ref(false)
const creating = ref(false)
const showCreateModal = ref(false)
const showDeleteModal = ref(false)
const deleteTarget = ref<ResearchProject | null>(null)
const deletingProjectId = ref('')
const createForm = reactive({
  title: '',
  research_topic: '',
  abstract: '',
  research_scope: {
    field: '',
    research_subject: '',
    research_question: '',
    research_goal: '',
    keywords: [] as string[],
    method_direction: '',
    notes: '',
  },
})

const formatTime = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000)
  if (days <= 0) return '今天更新'
  if (days < 7) return `${days} 天前更新`
  return date.toLocaleDateString('zh-CN')
}

const resetCreateForm = () => {
  createForm.title = ''
  createForm.research_topic = ''
  createForm.abstract = ''
  createForm.research_scope.field = ''
  createForm.research_scope.research_subject = ''
  createForm.research_scope.research_question = ''
  createForm.research_scope.research_goal = ''
  createForm.research_scope.keywords = []
  createForm.research_scope.method_direction = ''
  createForm.research_scope.notes = ''
}

const loadProjects = async () => {
  loading.value = true
  try {
    const response = await listProjects({ page: 1, page_size: 50 })
    projects.value = response.items || []
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createForm.title.trim() || !createForm.research_topic.trim()) {
    Message.warning('项目名称和研究主题必填')
    return
  }
  creating.value = true
  try {
    const created = await createProject({
      title: createForm.title.trim(),
      research_topic: createForm.research_topic.trim(),
      abstract: createForm.abstract.trim(),
      research_scope: createForm.research_scope,
    })
    showCreateModal.value = false
    resetCreateForm()
    Message.success('项目创建成功')
    await router.push({ name: 'ProjectOverview', params: { projectId: created.id } })
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '创建项目失败')
  } finally {
    creating.value = false
  }
}

const openDeleteModal = (project: ResearchProject) => {
  if (deletingProjectId.value) return
  deleteTarget.value = project
  showDeleteModal.value = true
}

const closeDeleteModal = () => {
  if (deletingProjectId.value) return
  showDeleteModal.value = false
  deleteTarget.value = null
}

const handleDelete = async () => {
  const project = deleteTarget.value
  if (!project || deletingProjectId.value) return
  deletingProjectId.value = project.id
  try {
    await deleteProject(project.id)
    projects.value = projects.value.filter(item => item.id !== project.id)
    showDeleteModal.value = false
    deleteTarget.value = null
    Message.success('项目已删除')
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '删除项目失败，请稍后重试')
  } finally {
    deletingProjectId.value = ''
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.projects-page { max-width: 1180px; margin: 0 auto; padding: 42px 32px 72px; }
.projects-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 30px; }
.page-kicker { margin: 0 0 8px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.projects-heading h1 { margin: 0; color: var(--pa-ink); font-size: clamp(26px, 3vw, 36px); letter-spacing: -0.025em; line-height: 1.2; text-wrap: balance; }
.page-description { max-width: 48ch; margin: 10px 0 0; color: var(--pa-muted); font-size: 14px; line-height: 1.6; }
.projects-empty { padding: 72px 24px; border: 1px dashed var(--pa-border); border-radius: 12px; background: var(--pa-surface); text-align: center; }
.empty-mark { display: grid; width: 48px; height: 48px; margin: 0 auto 18px; place-items: center; border-radius: 50%; background: var(--pa-primary-soft); color: var(--pa-primary); font-size: 28px; font-weight: 300; }
.projects-empty h2 { margin: 0; font-size: 20px; line-height: 1.3; }
.projects-empty p { max-width: 48ch; margin: 10px auto 22px; color: var(--pa-muted); font-size: 14px; line-height: 1.6; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.project-card { display: flex; min-height: 246px; flex-direction: column; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); transition: border-color 180ms ease-out, box-shadow 180ms ease-out, transform 180ms ease-out; }
.project-card:hover { border-color: var(--pa-primary); box-shadow: var(--pa-shadow-sm); transform: translateY(-2px); }
.project-card:focus-within { border-color: var(--pa-primary); }
.project-card.is-deleting { opacity: 0.68; transform: none; }
.project-card__main { display: flex; min-height: 0; flex: 1; flex-direction: column; padding: 20px; color: inherit; text-decoration: none; }
.project-card__main:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: -3px; }
.project-card__topline, .project-card__meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.project-card__label, .project-card__time, .project-card__meta { color: var(--pa-muted); font-size: 12px; }
.project-card__label { color: var(--pa-primary-hover); font-weight: 650; }
.project-card h2 { display: -webkit-box; margin: 22px 0 8px; overflow: hidden; font-size: 18px; line-height: 1.35; text-overflow: ellipsis; text-wrap: pretty; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.project-card__topic { display: -webkit-box; margin: 0; overflow: hidden; color: var(--pa-text); font-size: 14px; line-height: 1.55; text-overflow: ellipsis; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.project-card__meta { justify-content: flex-start; margin-top: auto; padding-top: 18px; }
.project-card__open { margin-top: 14px; color: var(--pa-primary-hover); font-size: 13px; font-weight: 650; }
.project-card__actions { display: flex; min-height: 42px; align-items: center; justify-content: flex-end; padding: 5px 12px; border-top: 1px solid var(--pa-border); background: var(--pa-surface-soft); }
.project-card__delete { min-height: 32px; padding: 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--pa-muted); cursor: pointer; font: inherit; font-size: 12px; transition: background-color 160ms ease-out, color 160ms ease-out; }
.project-card__delete:hover:not(:disabled) { background: oklch(0.96 0.025 28); color: var(--pa-danger); }
.project-card__delete:focus-visible { outline: 2px solid var(--pa-danger); outline-offset: 2px; }
.project-card__delete:disabled { cursor: not-allowed; opacity: 0.62; }
.delete-confirmation p { margin: 0; color: var(--pa-ink); font-size: 15px; line-height: 1.65; }
.delete-confirmation__detail { margin-top: 12px !important; color: var(--pa-muted) !important; font-size: 13px !important; }
.delete-confirmation__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.optional-fields { margin-top: 10px; border-top: 1px solid var(--pa-border); }
.optional-fields summary { padding: 14px 0 4px; color: var(--pa-muted); cursor: pointer; font-size: 13px; }
.optional-fields summary:hover { color: var(--pa-primary-hover); }
.optional-fields__body { padding-top: 12px; }
@media (max-width: 680px) { .projects-page { padding: 30px 16px 56px; } .projects-heading { align-items: stretch; flex-direction: column; } .projects-heading :deep(.arco-btn) { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .project-card, .project-card__delete { transition: none; } }
</style>

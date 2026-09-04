<template>
  <ProjectShell :recent-projects="project ? [project] : []">
    <template v-if="project">
      <ProjectHeader :project="project" />
      <main class="project-page project-overview">
        <header class="overview-heading">
          <div>
            <h1>{{ project.title }}</h1>
            <p class="overview-topic">{{ project.research_topic }}</p>
          </div>
          <a-button @click="openEditor">编辑项目</a-button>
        </header>

        <section class="overview-context" aria-label="项目研究主题">
          <div>
            <span class="context-label">研究主题</span>
            <p>{{ project.research_topic }}</p>
          </div>
          <div v-if="project.abstract">
            <span class="context-label">项目说明</span>
            <p>{{ project.abstract }}</p>
          </div>
          <div>
            <span class="context-label">项目论文</span>
            <p>{{ project.paper_count ?? 0 }} 篇</p>
          </div>
        </section>

        <section class="entry-grid" aria-label="项目入口">
          <RouterLink class="entry-card entry-card--primary" :to="{ name: 'ProjectDiscover', params: { projectId } }">
            <span class="entry-card__index">01</span>
            <div>
              <h2>开始发现文献</h2>
              <p>从研究主题出发，整理检索需求并寻找相关论文。</p>
            </div>
            <span class="entry-card__action">进入文献发现 <span aria-hidden="true">→</span></span>
          </RouterLink>
          <RouterLink class="entry-card" :to="{ name: 'ProjectPapers', params: { projectId } }">
            <span class="entry-card__index">02</span>
            <div>
              <h2>查看项目论文</h2>
              <p>集中查看已加入项目的论文，并继续进入 Reader。</p>
            </div>
            <span class="entry-card__action">打开项目论文 <span aria-hidden="true">→</span></span>
          </RouterLink>
          <RouterLink class="entry-card" :to="{ name: 'ProjectWriting', params: { projectId } }">
            <span class="entry-card__index">03</span>
            <div>
              <h2>继续写作</h2>
              <p>打开正式写作文档，在已有证据基础上继续组织内容。</p>
            </div>
            <span class="entry-card__action">进入写作 <span aria-hidden="true">→</span></span>
          </RouterLink>
        </section>
      </main>
    </template>

    <main v-else-if="loading" class="project-loading" aria-live="polite">正在加载项目…</main>
    <a-empty v-else description="项目不存在或无访问权限" class="project-error" />

    <a-modal v-model:visible="editing" title="编辑项目" :ok-loading="saving" @ok="saveProject">
      <a-form :model="editForm" layout="vertical">
        <a-form-item field="title" label="项目名称" required>
          <a-input v-model="editForm.title" />
        </a-form-item>
        <a-form-item field="research_topic" label="研究主题" required>
          <a-input v-model="editForm.research_topic" />
        </a-form-item>
        <a-form-item field="abstract" label="项目说明">
          <a-textarea v-model="editForm.abstract" :auto-size="{ minRows: 3, maxRows: 6 }" />
        </a-form-item>
      </a-form>
    </a-modal>
  </ProjectShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getProject, updateProject, type ResearchProject } from '@/api/projects'
import ProjectHeader from '@/components/project/ProjectHeader.vue'
import ProjectShell from '@/components/project/ProjectShell.vue'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const projectStore = useProjectStore()
const projectId = computed(() => String(route.params.projectId || ''))
const project = ref<ResearchProject | null>(null)
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const editForm = reactive({ title: '', research_topic: '', abstract: '' })

const loadProject = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    project.value = await getProject(projectId.value)
    projectStore.setProject(project.value)
  } catch (error: any) {
    project.value = null
    Message.error(error?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

const openEditor = () => {
  if (!project.value) return
  editForm.title = project.value.title
  editForm.research_topic = project.value.research_topic
  editForm.abstract = project.value.abstract || ''
  editing.value = true
}

const saveProject = async () => {
  if (!project.value || !editForm.title.trim() || !editForm.research_topic.trim()) {
    Message.warning('项目名称和研究主题必填')
    return
  }
  saving.value = true
  try {
    project.value = await updateProject(project.value.id, {
      title: editForm.title.trim(),
      research_topic: editForm.research_topic.trim(),
      abstract: editForm.abstract.trim(),
    })
    projectStore.setProject(project.value)
    editing.value = false
    Message.success('项目已更新')
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '更新项目失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadProject)
</script>

<style scoped>
.project-page { max-width: 1280px; margin: 0 auto; padding: 24px 24px 48px; }
.overview-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.overview-heading h1 { margin: 0; color: var(--pa-ink); font-size: 24px; letter-spacing: -0.02em; line-height: 1.25; text-wrap: balance; }
.overview-topic { max-width: 70ch; margin: 5px 0 0; color: var(--pa-text); font-size: 13px; line-height: 1.5; }
.overview-context { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 2fr) minmax(130px, 0.7fr); gap: 1px; margin-bottom: 18px; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 7px; background: var(--pa-border); }
.overview-context > div { min-width: 0; padding: 12px 14px; background: var(--pa-surface); }
.context-label { color: var(--pa-muted); font-size: 11px; font-weight: 650; }
.overview-context p { margin: 5px 0 0; color: var(--pa-text); font-size: 13px; line-height: 1.5; }
.entry-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.entry-card { display: flex; min-height: 176px; flex-direction: column; padding: 16px; border: 1px solid var(--pa-border); border-radius: 7px; background: var(--pa-surface); color: inherit; text-decoration: none; transition: border-color 180ms ease-out, box-shadow 180ms ease-out, transform 180ms ease-out; }
.entry-card:hover { border-color: var(--pa-primary); box-shadow: var(--pa-shadow-sm); transform: translateY(-2px); }
.entry-card:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 3px; }
.entry-card--primary { border-color: oklch(0.72 0.08 45); background: var(--pa-primary-soft); }
.entry-card__index { color: var(--pa-primary); font-size: 12px; font-weight: 700; }
.entry-card h2 { margin: 20px 0 5px; font-size: 16px; line-height: 1.3; text-wrap: balance; }
.entry-card p { margin: 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.entry-card__action { margin-top: auto; padding-top: 14px; color: var(--pa-primary-hover); font-size: 12px; font-weight: 650; }
.project-loading, .project-error { padding: 100px 32px; color: var(--pa-muted); text-align: center; }
@media (max-width: 880px) { .entry-grid { grid-template-columns: 1fr; } .entry-card { min-height: 180px; } .entry-card h2 { margin-top: 24px; } }
@media (max-width: 680px) { .project-page { padding: 18px 14px 36px; } .overview-heading { align-items: stretch; flex-direction: column; } .overview-context { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .entry-card { transition: none; } }
</style>

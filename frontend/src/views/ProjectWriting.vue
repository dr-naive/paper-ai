<template>
  <ProjectShell :recent-projects="project ? [project] : []">
    <template v-if="project">
      <ProjectHeader :project="project" />
      <main class="writing-page">
        <header class="writing-heading">
          <div>
            <p class="page-kicker">Writing workspace</p>
            <h1>写作</h1>
            <p>在可回溯的写作文档中组织论证，并从项目证据中插入引用。</p>
          </div>
        </header>
        <WritingDocumentEditor :project-id="projectId" />
      </main>
    </template>
    <main v-else-if="loading" class="project-loading" aria-live="polite">正在加载项目…</main>
    <a-empty v-else description="项目不存在或无访问权限" class="project-error" />
  </ProjectShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getProject, type ResearchProject } from '@/api/projects'
import ProjectHeader from '@/components/project/ProjectHeader.vue'
import ProjectShell from '@/components/project/ProjectShell.vue'
import WritingDocumentEditor from '@/components/project/WritingDocumentEditor.vue'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const projectStore = useProjectStore()
const projectId = computed(() => String(route.params.projectId || ''))
const project = ref<ResearchProject | null>(null)
const loading = ref(false)

const loadProject = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    project.value = await getProject(projectId.value)
    projectStore.setProject(project.value)
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadProject)
</script>

<style scoped>
.writing-page { padding: 34px clamp(18px, 3vw, 42px) 64px; }
.writing-heading { max-width: 1180px; margin: 0 auto 24px; }
.page-kicker { margin: 0 0 8px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.writing-heading h1 { margin: 0; color: var(--pa-ink); font-size: clamp(28px, 3vw, 38px); letter-spacing: -0.03em; line-height: 1.2; }
.writing-heading p:not(.page-kicker) { margin: 10px 0 0; color: var(--pa-muted); font-size: 14px; line-height: 1.55; }
.writing-page :deep(.writing-v2) { max-width: 1480px; margin: 0 auto; }
.project-loading, .project-error { padding: 100px 32px; color: var(--pa-muted); text-align: center; }
@media (max-width: 680px) { .writing-page { padding: 30px 12px 48px; } }
</style>

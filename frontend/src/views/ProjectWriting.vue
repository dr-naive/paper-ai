<template>
  <ProjectShell :recent-projects="project ? [project] : []">
    <template v-if="project">
      <ProjectHeader :project="project" />
      <main class="writing-page">
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
.writing-page { min-height: calc(100vh - 52px); }
.project-loading, .project-error { padding: 100px 32px; color: var(--pa-muted); text-align: center; }
</style>

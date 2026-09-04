<template>
  <ProjectShell :recent-projects="project ? [project] : []">
    <template v-if="project">
      <ProjectHeader :project="project" />
      <main class="project-page discover-page">
        <header class="page-heading">
          <div>
            <p class="page-kicker">Literature discovery</p>
            <h1>发现相关论文</h1>
            <p>先明确检索需求，再用结构化条件搜索真实学术文献。</p>
          </div>
          <RouterLink class="text-link" :to="{ name: 'ProjectOverview', params: { projectId } }">返回项目概览</RouterLink>
        </header>

        <div class="discover-layout">
          <RequirementChat
            :messages="discover.messages"
            :status="discover.status"
            :topic="discover.searchIntent.topic"
            @send="discover.submitRequirement"
            @reopen="discover.markClarifying"
          />

          <div v-if="discover.isReady" class="search-form-stack">
            <SearchIntentSummary
              :intent="discover.searchIntent"
              :disabled="discover.isWorking"
              @update:intent="discover.setIntent"
            />
            <SearchFilterForm
              :filters="discover.filters"
              :disabled="discover.isWorking"
              @update:filters="discover.setFilters"
              @search="submitSearch"
            />
          </div>

          <SearchExecutionStatus
            :status="discover.status"
            :message="discover.statusMessage"
            :result-count="discover.resultCount"
            :search-rounds="discover.searchRounds"
            :warnings="discover.warnings"
            :error-message="discover.errorMessage"
          />
          <PaperResultGrid
            :status="discover.status"
            :result-count="discover.resultCount"
            :favorite-count="discover.favoriteCount"
            :filter="discover.favoriteFilter"
            :papers="discover.visibleResults"
            :favorite-pending="discover.favoritePending"
            :import-states="discover.importStates"
            :import-messages="discover.importMessages"
            :action-error="discover.actionError"
            :error-message="discover.errorMessage"
            @update:filter="discover.setFavoriteFilter"
            @details="discover.openPaperDetails"
            @toggle-favorite="toggleFavorite"
            @download="downloadPaper"
            @import="importPaper"
            @modify="focusFilters"
            @reopen="discover.markClarifying"
            @retry="submitSearch"
          />
        </div>
        <PaperDetailDrawer
          :paper="discover.activePaper"
          :favorite-pending="activeFavoritePending"
          :import-state="activeImportState"
          :import-message="activeImportMessage"
          @close="discover.closePaperDetails"
          @toggle-favorite="toggleFavorite"
          @download="downloadPaper"
          @import="importPaper"
        />
      </main>
    </template>
    <main v-else-if="loading" class="project-loading" aria-live="polite">正在加载项目…</main>
    <a-empty v-else description="项目不存在或无访问权限" class="project-error" />
  </ProjectShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRoute } from 'vue-router'
import { getProject, type ResearchProject } from '@/api/projects'
import ProjectHeader from '@/components/project/ProjectHeader.vue'
import ProjectShell from '@/components/project/ProjectShell.vue'
import RequirementChat from '@/components/discover/RequirementChat.vue'
import PaperDetailDrawer from '@/components/discover/PaperDetailDrawer.vue'
import PaperResultGrid from '@/components/discover/PaperResultGrid.vue'
import SearchExecutionStatus from '@/components/discover/SearchExecutionStatus.vue'
import SearchFilterForm from '@/components/discover/SearchFilterForm.vue'
import SearchIntentSummary from '@/components/discover/SearchIntentSummary.vue'
import type { PaperSearchResult } from '@/api/discovery'
import { useDiscoverStore } from '@/stores/discover'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const projectStore = useProjectStore()
const discover = useDiscoverStore()
const projectId = computed(() => String(route.params.projectId || ''))
const project = ref<ResearchProject | null>(null)
const loading = ref(false)
const activeFavoritePending = computed(() => {
  const id = discover.activePaper?.result_id || ''
  return Boolean(id && discover.favoritePending[id])
})
const activeImportState = computed(() => {
  const id = discover.activePaper?.result_id || ''
  return id ? (discover.importStates[id] || 'idle') : 'idle'
})
const activeImportMessage = computed(() => {
  const id = discover.activePaper?.result_id || ''
  return id ? (discover.importMessages[id] || '') : ''
})

const loadProject = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    project.value = await getProject(projectId.value)
    projectStore.setProject(project.value)
    discover.reset(project.value.id, project.value.research_topic, {
      field: project.value.research_scope?.field,
      research_question: project.value.research_scope?.research_question,
      keywords: project.value.research_scope?.keywords,
      method_direction: project.value.research_scope?.method_direction,
    })
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

const submitSearch = () => { void discover.submitSearch(projectId.value) }

const toggleFavorite = (paper: PaperSearchResult) => { void discover.toggleFavorite(paper) }
const importPaper = (paper: PaperSearchResult) => { void discover.importPaper(paper) }
const downloadPaper = (paper: PaperSearchResult) => {
  if (!paper.download_available || !paper.pdf_url) return
  try {
    const url = new URL(paper.pdf_url)
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return
    window.open(url.toString(), '_blank', 'noopener,noreferrer')
  } catch {
    // Provider URLs are validated server-side; malformed values remain unavailable.
  }
}
const focusFilters = () => { document.getElementById('filter-title')?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }

onMounted(loadProject)
</script>

<style scoped>
.project-page { max-width: 1260px; margin: 0 auto; padding: 42px 32px 72px; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
.page-kicker { margin: 0 0 8px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.page-heading h1 { margin: 0; color: var(--pa-ink); font-size: clamp(28px, 3vw, 40px); letter-spacing: -0.03em; line-height: 1.2; text-wrap: balance; }
.page-heading p:not(.page-kicker) { margin: 10px 0 0; color: var(--pa-muted); font-size: 15px; line-height: 1.55; }
.text-link { color: var(--pa-primary-hover); font-size: 13px; font-weight: 650; text-decoration: none; }
.text-link:hover { text-decoration: underline; }
.discover-layout { display: grid; gap: 16px; }
.search-form-stack { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(360px, .85fr); gap: 16px; align-items: start; }
.project-loading, .project-error { padding: 100px 32px; color: var(--pa-muted); text-align: center; }
@media (max-width: 900px) { .search-form-stack { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .project-page { padding: 30px 16px 56px; } .page-heading { align-items: flex-start; flex-direction: column; } }
</style>

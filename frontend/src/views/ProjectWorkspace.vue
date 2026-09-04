<template>
  <div class="workspace-page">
    <ProductHeader
      :context="project?.title || '研究项目'"
      back-to="/projects"
      back-label="项目列表"
    >
      <template #actions>
        <a-button type="primary" @click="enterChat" :disabled="!project" :loading="enteringChat">
          进入项目对话
        </a-button>
        <a-button status="danger" @click="handleDelete" :disabled="!project">删除项目</a-button>
      </template>
    </ProductHeader>

    <main v-if="project" class="workspace-shell">
      <ProjectOverview :project="project" :workflow="workflowStatus" :paper-count="projectPapers.length" :artifact-count="artifacts.length" :active-area="activeArea" :active-tab="activeTab" :resources="resourceNavigation" @status="onStatusChange" @chat="enterChat" @area="openArea" @resource="activeTab = $event" />

      <div class="workbench-content">
        <section :class="['workspace-panel', { 'writing-mode': activeTab === 'paper-writing' }]" aria-label="当前研究工作区">
          <nav v-if="activeFunctionNavigation.length" class="function-navigation" aria-label="当前功能区工具">
            <button v-for="item in activeFunctionNavigation" :key="item.tab" type="button" :class="{ active: activeTab === item.tab }" @click="activeTab = item.tab">{{ item.label }}</button>
          </nav>
          <header class="workspace-panel-header"><div><span>{{ activeWorkspaceMeta.group }}</span><h2>{{ activeWorkspaceMeta.label }}</h2><p>{{ activeWorkspaceMeta.description }}</p></div><a-button type="primary" size="small" @click="enterChat(activeWorkspaceMeta.prompt)">在 Agent 中处理</a-button></header>
          <a-tabs v-model:active-key="activeTab" type="rounded" class="workspace-tabs">
        <a-tab-pane key="research-brief" title="研究任务书">
          <ProjectResearchBrief :artifact="researchBrief" :content="researchBriefContent" :loading="researchBriefLoading" @clarify="enterChat('请澄清当前题材并保存研究任务书；明确已知背景、约束、未知项、检索式和纳入排除标准。')" @open="openArtifact" />
        </a-tab-pane>

        <a-tab-pane key="literature-screening" title="候选文献">
          <TopicExplorer
            :project-id="projectId"
            :initial-query="project.research_topic"
            @imported="handleExternalImported"
          />
          <ProjectLiteratureScreening :artifact="literatureScreening" :content="literatureScreeningContent" :loading="literatureScreeningLoading" @open="openArtifact" />
        </a-tab-pane>

        <!-- ===== 领域地图 ===== -->
        <a-tab-pane key="research-map" title="领域地图">
          <ProjectResearchMap :artifact="researchMap" :content="researchMapContent" :loading="researchMapLoading" :has-papers="projectPapers.length > 0" :adopting-index="adoptingTopic" @chat="enterChat" @open="openArtifact" @adopt="adoptCandidateTopic" @continue-search="continueCandidateSearch" />
        </a-tab-pane>

        <!-- ===== 证据矩阵 ===== -->
        <a-tab-pane key="evidence-matrix" title="证据矩阵">
          <ProjectEvidenceMatrix :artifact="evidenceMatrix" :content="evidenceMatrixContent" :loading="evidenceMatrixLoading" :completed-cards="completedCardCount" @chat="enterChat" @open="openArtifact" @paper="openPaper" />
        </a-tab-pane>

        <!-- ===== 实验设计 ===== -->
        <a-tab-pane key="experiment-design" title="实验设计">
          <ProjectExperimentWorkspace :design="experimentDesign" :design-content="experimentDesignContent" :results="experimentResults" :results-content="experimentResultsContent" :loading="experimentDesignLoading" :has-evidence-matrix="!!evidenceMatrix" @chat="enterChat" @open="openArtifact" @register-results="enterChat('我将提供真实实验输出，请根据来源登记指标和运行信息；不要预测或编造任何数值。')" />
        </a-tab-pane>

        <!-- ===== 论文写作 ===== -->
        <a-tab-pane key="paper-writing" title="论文写作">
          <WritingDocumentEditor :project-id="projectId" />
          <details class="advanced-writing-state legacy-writing"><summary>旧版章节草稿工具</summary><WritingStudio :project-id="projectId" :papers="projectPapers" @saved="loadArtifacts" /></details>
          <ProjectWritingLifecycle :blueprint="paperBlueprint" :content="paperBlueprintContent" :artifacts="artifacts" :full-draft="fullDraft" :review-report="reviewReport" :final-manuscript="finalManuscript" :review-counts="reviewCounts" :loading="paperBlueprintLoading" :export-loading="exportLoading" @open="openArtifact" @section="openSectionDraft" @chat="enterChat" @download="downloadFinal" />
        </a-tab-pane>

        <!-- ===== 文档库 ===== -->
        <a-tab-pane key="papers" title="文档库">
          <ProjectLibrary :papers="projectPapers" :loading="papersLoading" :execution="readingExecution" :execution-loading="executionLoading" @add="showAddPaperModal = true" @start="startExecution" @pause="pauseExecution" @resume="resumeExecution" @open="openPaper" @remove="confirmRemovePaper" @priority="updatePaperPriority" @status="updatePaperStatus" />
        </a-tab-pane>

        <!-- ===== 写作产物 ===== -->
        <a-tab-pane key="artifacts" title="写作产物">
          <div class="tab-toolbar">
            <a-select
              v-model="artifactTypeFilter"
              placeholder="按类型筛选"
              allow-clear
              style="max-width: 200px"
            >
              <a-option v-for="(label, key) in ARTIFACT_TYPE_LABELS" :key="key" :value="key">{{ label }}</a-option>
            </a-select>
            <span class="tab-hint">{{ artifacts.length }} 份产物,点击查看详情或下载</span>
          </div>
          <a-spin :loading="artifactsLoading">
            <div v-if="!artifactsLoading && artifacts.length === 0" class="empty-tab">
              <p>还没有写作产物。在项目对话里让 agent 生成综述、大纲、章节草稿,产物会自动保存到这里。</p>
            </div>
            <div v-else-if="filteredArtifacts.length === 0" class="empty-tab">
              <p>没有符合当前筛选条件的写作产物。</p>
            </div>
            <ul v-else class="artifact-list">
              <li
                v-for="a in filteredArtifacts"
                :key="a.id"
                class="artifact-item"
                @click="openArtifact(a)"
              >
                <span class="artifact-type-tag" :class="`type-${a.artifact_type}`">
                  {{ artifactTypeLabel(a.artifact_type) }}
                </span>
                <div class="artifact-main">
                  <h4>{{ a.title }}</h4>
                  <p class="artifact-preview">{{ a.markdown_preview }}</p>
                </div>
                <div class="artifact-meta">
                  <span class="version">v{{ a.version }}</span>
                  <span class="time">{{ formatTime(a.updated_at) }}</span>
                </div>
              </li>
            </ul>
          </a-spin>
        </a-tab-pane>

        <!-- ===== Research Notes ===== -->
        <a-tab-pane key="notes" title="研究笔记">
          <ProjectResearchResources :project-id="projectId" mode="notes" :papers="projectPapers" @count="noteCount = $event" />
        </a-tab-pane>

        <a-tab-pane key="evidence" title="研究证据">
          <ProjectResearchResources :project-id="projectId" mode="evidence" :papers="projectPapers" @count="evidenceCount = $event" />
        </a-tab-pane>
        <a-tab-pane key="activity" title="Agent 活动">
          <ProjectActivity :project-id="projectId" />
        </a-tab-pane>
          </a-tabs>
        </section>
        <ProjectAgentDrawer :project-id="projectId" :context-group="activeWorkspaceMeta.group" :context-label="activeWorkspaceMeta.label" :context-description="activeWorkspaceMeta.description" :context-prompt="activeWorkspaceMeta.prompt" :submitting="enteringChat" @ask="enterChat" @activity="activeTab = 'activity'" />
      </div>
    </main>

    <a-empty v-else-if="!loading" description="项目不存在或无访问权限" style="padding: 80px" />

    <!-- 从论文库加入 Modal -->
    <a-modal v-model:visible="showAddPaperModal" title="从论文库加入项目" @ok="confirmAddPapers" :ok-loading="addingPapers">
      <a-input v-model="paperLibSearch" placeholder="搜索论文标题/作者" allow-clear style="margin-bottom: 12px" />
      <a-spin :loading="loadingPaperLib">
        <ul class="paper-lib-list">
          <li
            v-for="p in filteredPaperLib"
            :key="p.id"
            class="paper-lib-item"
            :class="{ selected: selectedPaperIds.includes(p.id) }"
            @click="toggleSelectPaper(p.id)"
          >
            <input type="checkbox" :checked="selectedPaperIds.includes(p.id)" />
            <div>
              <h5>{{ p.title }}</h5>
              <p>{{ p.authors || '未知作者' }}</p>
            </div>
          </li>
        </ul>
      </a-spin>
    </a-modal>


    <!-- 产物详情 Modal -->
    <a-modal
      v-model:visible="artifactModalVisible"
      :title="currentArtifact?.title || '产物详情'"
      width="80%"
      :footer="false"
      unmount-on-close
    >
      <div v-if="currentArtifact" class="artifact-detail">
        <div class="artifact-detail-meta">
          <span>类型: {{ artifactTypeLabel(currentArtifact.artifact_type) }}</span>
          <span>版本: v{{ currentArtifact.version }}</span>
          <span>状态: {{ currentArtifact.status }}</span>
          <span>更新: {{ formatTime(currentArtifact.updated_at) }}</span>
        </div>
        <a-button @click="downloadArtifact" size="small" style="margin: 12px 0">下载 Markdown</a-button>
        <pre class="artifact-markdown">{{ currentArtifact.markdown_text }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import ProductHeader from '@/components/ProductHeader.vue'
import TopicExplorer from '@/components/project/TopicExplorer.vue'
import WritingStudio from '@/components/project/WritingStudio.vue'
import WritingDocumentEditor from '@/components/project/WritingDocumentEditor.vue'
import ProjectActivity from '@/components/project/ProjectActivity.vue'
import ProjectResearchResources from '@/components/project/ProjectResearchResources.vue'
import ProjectLibrary from '@/components/project/ProjectLibrary.vue'
import ProjectOverview from '@/components/project/ProjectOverview.vue'
import ProjectAgentDrawer from '@/components/project/ProjectAgentDrawer.vue'
import ProjectResearchBrief from '@/components/project/ProjectResearchBrief.vue'
import ProjectLiteratureScreening from '@/components/project/ProjectLiteratureScreening.vue'
import ProjectResearchMap from '@/components/project/ProjectResearchMap.vue'
import ProjectEvidenceMatrix from '@/components/project/ProjectEvidenceMatrix.vue'
import ProjectExperimentWorkspace from '@/components/project/ProjectExperimentWorkspace.vue'
import ProjectWritingLifecycle from '@/components/project/ProjectWritingLifecycle.vue'
import { useProjectStore } from '@/stores/project'
import { useWorkspaceStore } from '@/stores/workspace'
import {
  getProject,
  getProjectWorkflowStatus,
  createResearchNote,
  updateProject,
  deleteProject,
  listProjectPapers,
  addProjectPaper,
  updateProjectPaper,
  removeProjectPaper,
  listArtifacts,
  getArtifact,
  downloadArtifactExport,
  createProjectSession,
  startReadingExecution,
  getReadingExecution,
  pauseReadingExecution,
  resumeReadingExecution,
  ARTIFACT_TYPE_LABELS,
  type ProjectPaperItem,
  type WritingArtifactItem,
  type ResearchBriefContent,
  type LiteratureScreeningContent,
  type ResearchMapContent,
  type EvidenceMatrixContent,
  type ExperimentDesignContent,
  type ExperimentResultsContent,
  type PaperBlueprintContent,
  type ReviewReportContent,
  type ReadingExecution,
} from '@/api/projects'
import { getPaperList } from '@/api/paper'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => String(route.params.id || ''))
const executionStorageKey = computed(() => `paperai:reading-execution:${projectId.value}`)
const projectStore = useProjectStore()
const workspaceStore = useWorkspaceStore()
const { currentProject: project, papers: projectPapers, workflowStatus } = storeToRefs(projectStore)

const loading = ref(false)
const activeTab = computed({
  get: () => workspaceStore.activePanel(projectId.value),
  set: value => workspaceStore.setActivePanel(projectId.value, value),
})
const enteringChat = ref(false)

const AREA_TAB = { topic: 'research-brief', reading: 'papers', writing: 'paper-writing' } as const
const applyRequestedArea = () => {
  const requestedPanel = String(route.query.panel || '')
  if (requestedPanel === 'activity') {
    activeTab.value = requestedPanel
    return
  }
  const area = String(route.query.area || '') as keyof typeof AREA_TAB
  if (AREA_TAB[area]) activeTab.value = AREA_TAB[area]
}
const FUNCTION_NAVIGATION = {
  topic: [
    { tab: 'research-brief', label: '研究范围' },
    { tab: 'literature-screening', label: '外部论文' },
    { tab: 'research-map', label: '候选方向' },
  ],
  reading: [
    { tab: 'papers', label: '论文库与阅读' },
    { tab: 'evidence-matrix', label: '多论文对比' },
  ],
  writing: [
    { tab: 'paper-writing', label: '论文与章节' },
    { tab: 'experiment-design', label: '研究设计与结果' },
  ],
} as const
const WORKSPACE_META: Record<string, { group: string; label: string; description: string; prompt: string }> = {
  'research-brief': { group: '选题研究', label: '研究范围', description: '记录你要研究的对象、目标、现实约束和仍不确定的问题。', prompt: '请帮助我明确当前研究的对象、目标和约束；只追问真正影响选题的未知信息。' },
  'literature-screening': { group: '选题研究', label: '外部论文', description: '搜索并查看候选论文，判断它们与当前题材的实际关系。', prompt: '请检索与当前题材直接相关的外部论文，给出可点击标题、论文简介、匹配点和保留或排除理由。' },
  'research-map': { group: '选题研究', label: '候选方向', description: '比较已有研究、发现仍值得解决的问题并形成候选题目。', prompt: '请基于已找到的论文比较候选研究方向，说明每个方向的价值、证据基础、风险和可行性。' },
  'evidence-matrix': { group: '论文阅读', label: '多论文对比', description: '比较论文解决的问题、方法、数据、结论、局限与分歧。', prompt: '请比较当前项目论文，重点解释它们的研究问题、方法差异、证据强弱、冲突和局限。' },
  'experiment-design': { group: '论文写作', label: '研究设计与结果', description: '管理论文需要描述的研究方案，并登记有来源的真实结果。', prompt: '请检查当前研究设计和结果材料；允许先规划，但不要预测或编造任何实验数值。' },
  'paper-writing': { group: '论文写作', label: '论文与章节', description: '确定核心主张、组织结构、撰写章节并检查引用与全文。', prompt: '请帮助我开始或继续论文写作，先确认论文类型、核心主张和已有材料，再处理当前最需要的章节。' },
  papers: { group: '论文阅读', label: '论文库与阅读', description: '添加论文、打开原文、记录理解并管理需要继续阅读的内容。', prompt: '请帮助我了解项目论文，解释每篇解决的问题、主要方法、可靠结论和局限，并建议下一篇该读什么。' },
  artifacts: { group: '项目资源', label: '全部研究产物', description: '查看任务书、地图、矩阵、设计、草稿、审计和终稿的历史版本。', prompt: '请检查项目研究产物的依赖关系和版本状态，指出过期、缺失或需要重建的产物。' },
  notes: { group: '项目资源', label: '研究笔记', description: '保留会影响后续研究的发现、问题、假设、决定与约束。', prompt: '请整理当前项目研究笔记，去除临时信息和重复内容，区分事实、假设、决定与待解决问题。' },
  evidence: { group: '项目资源', label: '研究证据', description: '保存可定位的论文原文及其支持的主张，供比较与写作复用。', prompt: '请检查当前研究证据的来源、覆盖范围和冲突，指出仍缺少哪些可定位证据。' },
  activity: { group: '项目资源', label: 'Agent 活动', description: '查看持久化执行、公开进度、失败原因，并暂停、恢复或取消任务。', prompt: '请总结当前项目最近的 Agent 执行结果，并指出失败或等待处理的任务。' },
}

// 文档库
const papersLoading = ref(false)
const showAddPaperModal = ref(false)
const paperLibSearch = ref('')
const paperLib = ref<any[]>([])
const loadingPaperLib = ref(false)
const selectedPaperIds = ref<string[]>([])
const addingPapers = ref(false)
const readingExecution = ref<ReadingExecution | null>(null)
const executionLoading = ref(false)
let executionPoll: number | undefined

// 产物
const artifacts = ref<WritingArtifactItem[]>([])
const artifactsLoading = ref(false)
const artifactTypeFilter = ref<string | undefined>(undefined)
const artifactModalVisible = ref(false)
const currentArtifact = ref<WritingArtifactItem | null>(null)
const researchBrief = ref<WritingArtifactItem | null>(null)
const researchBriefLoading = ref(false)
const literatureScreening = ref<WritingArtifactItem | null>(null)
const literatureScreeningLoading = ref(false)
const researchMap = ref<WritingArtifactItem | null>(null)
const researchMapLoading = ref(false)
const evidenceMatrix = ref<WritingArtifactItem | null>(null)
const evidenceMatrixLoading = ref(false)
const experimentDesign = ref<WritingArtifactItem | null>(null)
const experimentDesignLoading = ref(false)
const experimentResults = ref<WritingArtifactItem | null>(null)
const paperBlueprint = ref<WritingArtifactItem | null>(null)
const paperBlueprintLoading = ref(false)
const fullDraft = ref<WritingArtifactItem | null>(null)
const reviewReport = ref<WritingArtifactItem | null>(null)
const finalManuscript = ref<WritingArtifactItem | null>(null)
const exportLoading = ref<'md' | 'tex' | 'docx' | 'zip' | ''>('')

const noteCount = ref(0)
const evidenceCount = ref(0)
const adoptingTopic = ref<number | null>(null)

const activeArea = computed<'topic' | 'reading' | 'writing' | ''>(() => {
  if (['research-brief', 'literature-screening', 'research-map'].includes(activeTab.value)) return 'topic'
  if (['papers', 'evidence-matrix'].includes(activeTab.value)) return 'reading'
  if (['experiment-design', 'paper-writing'].includes(activeTab.value)) return 'writing'
  return ''
})
const activeFunctionNavigation = computed(() => activeArea.value ? FUNCTION_NAVIGATION[activeArea.value] : [])
const resourceNavigation = computed(() => [
  { tab: 'papers', icon: '▤', label: '文档库', count: projectPapers.value.length },
  { tab: 'artifacts', icon: '◇', label: '研究产物', count: artifacts.value.length },
  { tab: 'notes', icon: '⌁', label: '研究笔记', count: noteCount.value },
  { tab: 'evidence', icon: '◫', label: '研究证据', count: evidenceCount.value },
  { tab: 'activity', icon: '◷', label: 'Agent 活动', count: 0 },
])
const activeWorkspaceMeta = computed(() => WORKSPACE_META[activeTab.value] || WORKSPACE_META['research-brief'])

const openArea = (area: 'topic' | 'reading' | 'writing') => {
  activeTab.value = AREA_TAB[area]
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  requestAnimationFrame(() => document.querySelector('.workspace-panel')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' }))
}

const candidateTopicTitle = (item: Record<string, any>) => String(item.title || item.question || '').trim()
const adoptCandidateTopic = async (item: Record<string, any>, index: number) => {
  const title = candidateTopicTitle(item)
  if (!title || !project.value) return
  adoptingTopic.value = index
  try {
    const updated = await updateProject(projectId.value, { research_topic: title })
    project.value.research_topic = updated.research_topic
    await createResearchNote(projectId.value, {
      type: 'decision', title: '选定研究方向', content: title,
      tags: ['topic-selection'], confidence: 1,
    })
    Message.success('候选方向已写入项目，并记录为研究决定')
  } catch (error: any) { Message.error(error?.response?.data?.detail || '更新项目方向失败') }
  finally { adoptingTopic.value = null }
}
const continueCandidateSearch = (item: Record<string, any>) => {
  if (project.value) project.value.research_topic = candidateTopicTitle(item) || project.value.research_topic
  activeTab.value = 'literature-screening'
}

const filteredArtifacts = computed(() => {
  if (!artifactTypeFilter.value) return artifacts.value
  return artifacts.value.filter(a => a.artifact_type === artifactTypeFilter.value)
})

const researchMapContent = computed<ResearchMapContent>(() => ({
  topic_summary: String(researchMap.value?.content?.topic_summary || ''),
  keywords: researchMap.value?.content?.keywords || [],
  research_questions: researchMap.value?.content?.research_questions || [],
  method_families: researchMap.value?.content?.method_families || [],
  datasets: researchMap.value?.content?.datasets || [],
  research_gaps: researchMap.value?.content?.research_gaps || [],
  candidate_topics: researchMap.value?.content?.candidate_topics || [],
  evidence: researchMap.value?.content?.evidence || [],
}))
const researchBriefContent = computed<ResearchBriefContent>(() => ({
  topic: String(researchBrief.value?.content?.topic || ''),
  objective: String(researchBrief.value?.content?.objective || ''),
  known_context: researchBrief.value?.content?.known_context || [],
  constraints: researchBrief.value?.content?.constraints || [],
  unknowns: researchBrief.value?.content?.unknowns || [],
  seed_keywords: researchBrief.value?.content?.seed_keywords || [],
  search_queries: researchBrief.value?.content?.search_queries || [],
  inclusion_criteria: researchBrief.value?.content?.inclusion_criteria || [],
  exclusion_criteria: researchBrief.value?.content?.exclusion_criteria || [],
  evaluation_criteria: researchBrief.value?.content?.evaluation_criteria || [],
  next_actions: researchBrief.value?.content?.next_actions || [],
}))
const literatureScreeningContent = computed<LiteratureScreeningContent>(() => ({
  research_brief_id: String(literatureScreening.value?.content?.research_brief_id || ''),
  research_brief_version: Number(literatureScreening.value?.content?.research_brief_version || 0),
  query_runs: literatureScreening.value?.content?.query_runs || [],
  candidates: literatureScreening.value?.content?.candidates || [],
  coverage_summary: literatureScreening.value?.content?.coverage_summary || [],
  stopping_reason: String(literatureScreening.value?.content?.stopping_reason || ''),
  included_count: Number(literatureScreening.value?.content?.included_count || 0),
  excluded_count: Number(literatureScreening.value?.content?.excluded_count || 0),
  maybe_count: Number(literatureScreening.value?.content?.maybe_count || 0),
  deduplicated_count: Number(literatureScreening.value?.content?.deduplicated_count || 0),
}))

const completedCardCount = computed(() => projectPapers.value.filter(item => item.analysis_card?.summary).length)
const evidenceMatrixContent = computed<EvidenceMatrixContent>(() => ({
  research_question: String(evidenceMatrix.value?.content?.research_question || ''),
  rows: evidenceMatrix.value?.content?.rows || [],
  conflicts: evidenceMatrix.value?.content?.conflicts || [],
  evidence_gaps: evidenceMatrix.value?.content?.evidence_gaps || [],
  generated_from_cards: Number(evidenceMatrix.value?.content?.generated_from_cards || 0),
}))

const experimentDesignContent = computed<ExperimentDesignContent>(() => ({
  research_question: String(experimentDesign.value?.content?.research_question || ''),
  hypothesis: String(experimentDesign.value?.content?.hypothesis || ''),
  rationale: String(experimentDesign.value?.content?.rationale || ''),
  independent_variables: experimentDesign.value?.content?.independent_variables || [],
  dependent_variables: experimentDesign.value?.content?.dependent_variables || [],
  controls: experimentDesign.value?.content?.controls || [],
  datasets: experimentDesign.value?.content?.datasets || [],
  baselines: experimentDesign.value?.content?.baselines || [],
  metrics: experimentDesign.value?.content?.metrics || [],
  experiment_steps: experimentDesign.value?.content?.experiment_steps || [],
  ablations: experimentDesign.value?.content?.ablations || [],
  success_criteria: experimentDesign.value?.content?.success_criteria || [],
  falsification_criteria: experimentDesign.value?.content?.falsification_criteria || [],
  risks: experimentDesign.value?.content?.risks || [],
  evidence_refs: experimentDesign.value?.content?.evidence_refs || [],
  requires_empirical_results: experimentDesign.value?.content?.requires_empirical_results !== false,
}))
const experimentResultsContent = computed<ExperimentResultsContent>(() => ({
  experiment_design_id: String(experimentResults.value?.content?.experiment_design_id || ''),
  experiment_design_version: Number(experimentResults.value?.content?.experiment_design_version || 0),
  run_id: String(experimentResults.value?.content?.run_id || ''),
  sources: experimentResults.value?.content?.sources || [],
  metrics: experimentResults.value?.content?.metrics || [],
  hypothesis_outcome: experimentResults.value?.content?.hypothesis_outcome || 'inconclusive',
  qualitative_findings: experimentResults.value?.content?.qualitative_findings || [],
  protocol_deviations: experimentResults.value?.content?.protocol_deviations || [],
  analysis_notes: experimentResults.value?.content?.analysis_notes || [],
}))

const paperBlueprintContent = computed<PaperBlueprintContent>(() => ({
  working_title: String(paperBlueprint.value?.content?.working_title || ''),
  central_claim: String(paperBlueprint.value?.content?.central_claim || ''),
  target_audience: String(paperBlueprint.value?.content?.target_audience || ''),
  target_venue: String(paperBlueprint.value?.content?.target_venue || ''),
  experiment_design_id: String(paperBlueprint.value?.content?.experiment_design_id || ''),
  sections: paperBlueprint.value?.content?.sections || [],
}))
const reviewReportContent = computed<ReviewReportContent>(() => ({
  full_draft_id: String(reviewReport.value?.content?.full_draft_id || ''),
  full_draft_version: Number(reviewReport.value?.content?.full_draft_version || 0),
  blueprint_id: String(reviewReport.value?.content?.blueprint_id || ''),
  passed: Boolean(reviewReport.value?.content?.passed),
  counts: reviewReport.value?.content?.counts || { blocker: 0, major: 0, minor: 0 },
  issues: reviewReport.value?.content?.issues || [],
}))
const reviewCounts = computed(() => reviewReportContent.value.counts)

const filteredPaperLib = computed(() => {
  if (!paperLibSearch.value) return paperLib.value
  const q = paperLibSearch.value.toLowerCase()
  return paperLib.value.filter(p =>
    (p.title || '').toLowerCase().includes(q) || (p.authors || '').toLowerCase().includes(q)
  )
})

const artifactTypeLabel = (t: string) => ARTIFACT_TYPE_LABELS[t] || t
const readingStatusLabel = (status: string) => ({
  pending: '待阅读',
  reading: '精读中',
  completed: '已完成',
  skipped: '已跳过',
  failed: '执行失败',
}[status] || status)
const formatTime = (iso?: string) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const loadProject = async () => {
  loading.value = true
  try {
    project.value = await getProject(projectId.value)
  } catch (e: any) {
    project.value = null
    Message.error(e?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

const loadWorkflowStatus = async () => {
  try {
    workflowStatus.value = await getProjectWorkflowStatus(projectId.value)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载工作台状态失败')
  }
}

const loadPapers = async () => {
  papersLoading.value = true
  try {
    const res = await listProjectPapers(projectId.value)
    projectPapers.value = res.items || []
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载文档库失败')
  } finally {
    papersLoading.value = false
  }
}

const handleExternalImported = async () => {
  await Promise.all([loadPapers(), loadWorkflowStatus()])
}

const loadArtifacts = async () => {
  artifactsLoading.value = true
  researchBriefLoading.value = true
  literatureScreeningLoading.value = true
  researchMapLoading.value = true
  evidenceMatrixLoading.value = true
  experimentDesignLoading.value = true
  paperBlueprintLoading.value = true
  try {
    const res = await listArtifacts(projectId.value)
    artifacts.value = res.items || []
    const latestBrief = artifacts.value.find(item => item.artifact_type === 'research_brief')
    researchBrief.value = latestBrief ? await getArtifact(projectId.value, latestBrief.id) : null
    const latestScreening = artifacts.value.find(item => item.artifact_type === 'literature_screening')
    literatureScreening.value = latestScreening ? await getArtifact(projectId.value, latestScreening.id) : null
    const latestMap = artifacts.value.find(item => item.artifact_type === 'research_map')
    researchMap.value = latestMap ? await getArtifact(projectId.value, latestMap.id) : null
    const latestMatrix = artifacts.value.find(item => item.artifact_type === 'evidence_matrix')
    evidenceMatrix.value = latestMatrix ? await getArtifact(projectId.value, latestMatrix.id) : null
    const latestDesign = artifacts.value.find(item => item.artifact_type === 'experiment_design')
    experimentDesign.value = latestDesign ? await getArtifact(projectId.value, latestDesign.id) : null
    const latestResults = artifacts.value.find(item => item.artifact_type === 'experiment_results')
    const resultDetail = latestResults ? await getArtifact(projectId.value, latestResults.id) : null
    experimentResults.value = resultDetail?.content?.experiment_design_id === latestDesign?.id ? resultDetail : null
    const latestBlueprint = artifacts.value.find(item => item.artifact_type === 'paper_blueprint')
    paperBlueprint.value = latestBlueprint ? await getArtifact(projectId.value, latestBlueprint.id) : null
    const latestFullDraft = artifacts.value.find(item => item.artifact_type === 'full_draft')
    fullDraft.value = latestFullDraft ? await getArtifact(projectId.value, latestFullDraft.id) : null
    const latestReport = artifacts.value.find(item => item.artifact_type === 'review_report' && item.meta?.audit_kind === 'full_draft' && item.parent_id === latestFullDraft?.id)
    reviewReport.value = latestReport ? await getArtifact(projectId.value, latestReport.id) : null
    const latestFinal = artifacts.value.find(item => item.artifact_type === 'final_manuscript' && item.parent_id === latestFullDraft?.id)
    finalManuscript.value = latestFinal ? await getArtifact(projectId.value, latestFinal.id) : null
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载产物失败')
  } finally {
    artifactsLoading.value = false
    researchBriefLoading.value = false
    literatureScreeningLoading.value = false
    researchMapLoading.value = false
    evidenceMatrixLoading.value = false
    experimentDesignLoading.value = false
    paperBlueprintLoading.value = false
  }
}

const loadAll = async () => {
  if (project.value?.id !== projectId.value) projectStore.clear()
  await Promise.all([loadProject(), loadPapers(), loadArtifacts(), loadWorkflowStatus()])
}

const onStatusChange = async (status: string) => {
  if (!project.value) return
  try {
    await updateProject(projectId.value, { status })
    project.value.status = status
    Message.success(`状态已更新`)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '更新失败')
  }
}

const handleDelete = () => {
  Modal.warning({
    title: '删除项目',
    content: '删除后无法恢复,关联的文档库/产物/记忆将一并清除。',
    hideCancel: false,
    onOk: async () => {
      try {
        await deleteProject(projectId.value)
        Message.success('项目已删除')
        router.push('/projects')
      } catch (e: any) {
        Message.error(e?.response?.data?.detail || '删除失败')
      }
    },
  })
}

const enterChat = async (promptOrEvent?: string | Event) => {
  const prompt = typeof promptOrEvent === 'string' ? promptOrEvent : ''
  enteringChat.value = true
  try {
    const session = await createProjectSession(projectId.value, `${project.value?.title || ''} 对话`)
    router.push({
      name: 'ProjectChat',
      params: { id: projectId.value },
      query: { session: session.id, project: projectId.value, ...(prompt ? { prompt } : {}) },
    })
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '创建对话失败,请重试')
  } finally {
    enteringChat.value = false
  }
}

const updatePaperPriority = async (pp: ProjectPaperItem, priority: number) => {
  try {
    await updateProjectPaper(projectId.value, pp.paper_id, { reading_priority: priority })
    pp.reading_priority = priority
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '更新失败')
  }
}

const updatePaperStatus = async (pp: ProjectPaperItem, status: string) => {
  if (!['pending', 'reading', 'completed', 'skipped', 'failed'].includes(status)) return
  try {
    const readingPlan: ProjectPaperItem['reading_plan'] = {
      ...(pp.reading_plan || {}),
      status: status as ProjectPaperItem['reading_plan']['status'],
    }
    await updateProjectPaper(projectId.value, pp.paper_id, { reading_plan: readingPlan })
    pp.reading_plan = readingPlan as ProjectPaperItem['reading_plan']
    Message.success(`阅读状态已更新为：${readingStatusLabel(status)}`)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '更新阅读状态失败')
  }
}

const stopExecutionPoll = () => {
  if (executionPoll !== undefined) window.clearInterval(executionPoll)
  executionPoll = undefined
}

const refreshExecution = async () => {
  if (!readingExecution.value?.task_id) return
  try {
    readingExecution.value = await getReadingExecution(projectId.value, readingExecution.value.task_id)
    if (['completed', 'failed', 'paused'].includes(readingExecution.value.status)) {
      stopExecutionPoll()
      await loadPapers()
    }
  } catch {
    stopExecutionPoll()
  }
}

const startExecutionPoll = () => {
  stopExecutionPoll()
  executionPoll = window.setInterval(refreshExecution, 2000)
}

const startExecution = async () => {
  executionLoading.value = true
  try {
    readingExecution.value = await startReadingExecution(projectId.value)
    localStorage.setItem(executionStorageKey.value, readingExecution.value.task_id)
    Message.success('自动精读任务已启动')
    startExecutionPoll()
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '启动自动精读失败')
  } finally {
    executionLoading.value = false
  }
}

const restoreExecution = async () => {
  const taskId = localStorage.getItem(executionStorageKey.value)
  if (!taskId) return
  try {
    readingExecution.value = await getReadingExecution(projectId.value, taskId)
    if (['queued', 'running'].includes(readingExecution.value.status)) startExecutionPoll()
  } catch {
    localStorage.removeItem(executionStorageKey.value)
  }
}

const pauseExecution = async () => {
  if (!readingExecution.value) return
  readingExecution.value = await pauseReadingExecution(projectId.value, readingExecution.value.task_id)
  Message.info('将在当前论文完成后暂停')
}

const resumeExecution = async () => {
  if (!readingExecution.value) return
  readingExecution.value = await resumeReadingExecution(projectId.value, readingExecution.value.task_id)
  startExecutionPoll()
  Message.success('精读任务已继续')
}

const removePaper = async (pp: ProjectPaperItem) => {
  try {
    await removeProjectPaper(projectId.value, pp.paper_id)
    projectPapers.value = projectPapers.value.filter(x => x.id !== pp.id)
    Message.success('已移除')
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '移除失败')
  }
}

const confirmRemovePaper = (pp: ProjectPaperItem) => {
  Modal.warning({
    title: '移除项目论文',
    content: `将“${pp.paper?.title || '这篇论文'}”移出当前项目，论文原文件仍保留在“我的论文”中。`,
    hideCancel: false,
    okText: '移除论文',
    cancelText: '取消',
    onOk: () => removePaper(pp),
  })
}

const openPaper = (paperId: string) => {
  router.push({ name: 'PaperReader', params: { id: paperId }, query: { project_id: projectId.value } })
}

const loadPaperLib = async () => {
  loadingPaperLib.value = true
  try {
    const res = await getPaperList({ limit: 100 })
    paperLib.value = (res as any).items || (res as any) || []
    // 排除已在项目里的
    const existing = new Set(projectPapers.value.map(pp => pp.paper_id))
    paperLib.value = paperLib.value.filter((p: any) => !existing.has(p.id))
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载论文库失败')
  } finally {
    loadingPaperLib.value = false
  }
}

watch(showAddPaperModal, (v) => {
  if (v && paperLib.value.length === 0) loadPaperLib()
  if (v) selectedPaperIds.value = []
})

const toggleSelectPaper = (id: string) => {
  const i = selectedPaperIds.value.indexOf(id)
  if (i >= 0) selectedPaperIds.value.splice(i, 1)
  else selectedPaperIds.value.push(id)
}

const confirmAddPapers = async () => {
  if (selectedPaperIds.value.length === 0) {
    Message.warning('请至少选择一篇')
    return
  }
  addingPapers.value = true
  try {
    for (const pid of selectedPaperIds.value) {
      await addProjectPaper(projectId.value, { paper_id: pid, role: 'related' })
    }
    Message.success(`已加入 ${selectedPaperIds.value.length} 篇`)
    showAddPaperModal.value = false
    await loadPapers()
    // 更新项目卡统计
    if (project.value) project.value.paper_count = projectPapers.value.length
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加入失败')
  } finally {
    addingPapers.value = false
  }
}

const openArtifact = async (a: WritingArtifactItem) => {
  try {
    const full = await getArtifact(projectId.value, a.id)
    currentArtifact.value = full
    artifactModalVisible.value = true
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载详情失败')
  }
}

const openSectionDraft = (sectionId: string) => {
  const draft = artifacts.value.find(item => item.artifact_type === 'section_draft' && item.parent_id === paperBlueprint.value?.id && item.meta?.section_id === sectionId)
  if (draft) openArtifact(draft)
}

const downloadArtifact = () => {
  if (!currentArtifact.value) return
  const blob = new Blob([currentArtifact.value.markdown_text || ''], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${currentArtifact.value.title}.md`
  a.click()
  URL.revokeObjectURL(url)
}

const downloadFinal = async (format: 'md' | 'tex' | 'docx' | 'zip') => {
  if (!finalManuscript.value || exportLoading.value) return
  exportLoading.value = format
  try {
    const blob = await downloadArtifactExport(projectId.value, finalManuscript.value.id, format)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${finalManuscript.value.title}.${format}`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '导出终稿失败')
  } finally {
    exportLoading.value = ''
  }
}

onMounted(() => {
  applyRequestedArea()
  loadAll()
  restoreExecution()
})
onBeforeUnmount(stopExecutionPoll)
watch(projectId, () => {
  applyRequestedArea()
  stopExecutionPoll()
  readingExecution.value = null
  loadAll()
  restoreExecution()
})
watch(() => [route.query.area, route.query.panel], applyRequestedArea)
</script>

<style scoped>
.workspace-page {
  min-height: 100vh;
  background: var(--color-bg-1);
}
.workspace-shell {
  max-width: 1600px;
  margin: 0 auto;
  padding: 16px;
}
.research-workbench { margin-bottom: 12px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); overflow: hidden; }
.workbench-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 13px 16px; background: var(--pa-toolbar); color: white; }
.workbench-heading h1 { margin: 0 0 2px; font-size: 18px; line-height: 1.3; }
.workbench-heading p { max-width: 76ch; margin: 0; color: oklch(0.84 0.012 65); font-size: 12px; line-height: 1.45; }
.workbench-areas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.workbench-area { display: flex; min-width: 0; flex-direction: column; align-items: flex-start; gap: 8px; padding: 11px 14px; border-right: 1px solid var(--pa-border); background: var(--pa-surface); }
.workbench-area:last-child { border-right: 0; }
.workbench-area.active { background: var(--color-primary-light-1); }
.area-open { width: 100%; padding: 0; border: 0; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.area-open:focus-visible { border-radius: 4px; outline: 2px solid var(--pa-primary); outline-offset: 5px; }
.area-status { display: inline-flex; min-height: 22px; align-items: center; padding: 0 8px; border-radius: 5px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 11px; font-weight: 600; }
.workbench-area.active .area-status { background: var(--pa-surface); color: var(--pa-primary); }
.area-open h2 { margin: 7px 0 3px; font-size: 15px; text-wrap: balance; }
.area-open p { min-height: 34px; margin: 0 0 5px; color: var(--pa-muted); font-size: 11px; line-height: 1.45; text-wrap: pretty; }
.area-open strong { color: var(--pa-text); font-size: 11px; }
.shared-resources { display: flex; min-height: 40px; align-items: center; gap: 4px; padding: 4px 10px; border-top: 1px solid var(--pa-border); background: var(--pa-surface-soft); }
.shared-resources > strong { margin: 0 10px; color: var(--pa-muted); font-size: 12px; }
.shared-resources button { display: inline-flex; min-height: 29px; align-items: center; gap: 6px; padding: 0 8px; border: 0; border-radius: 5px; background: transparent; color: var(--pa-text); cursor: pointer; font: inherit; font-size: 11px; }
.shared-resources button:hover, .shared-resources button.active { background: var(--pa-surface); color: var(--pa-primary); }
.shared-resources button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.shared-resources small { color: var(--pa-muted); }
.workbench-content { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 12px; min-width: 0; }
.function-navigation { display: flex; gap: 3px; margin: -2px 0 10px; padding-bottom: 7px; border-bottom: 1px solid var(--pa-border); overflow-x: auto; }
.function-navigation button { min-height: 34px; flex: none; padding: 0 11px; border: 0; border-radius: 6px; background: transparent; color: var(--pa-muted); cursor: pointer; font: inherit; font-size: 13px; }
.function-navigation button:hover { background: var(--pa-surface-soft); color: var(--pa-text); }
.function-navigation button.active { background: var(--color-primary-light-1); color: var(--pa-primary); font-weight: 600; }
.function-navigation button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.workspace-panel { min-width: 0; padding: 14px 16px 20px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); }
.workspace-panel.writing-mode { padding: 10px; }
.workspace-panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--pa-border); }
.workspace-panel-header span { color: var(--pa-muted); font-size: 12px; }
.workspace-panel-header h2 { margin: 2px 0 3px; font-size: 18px; text-wrap: balance; }
.workspace-panel-header p { max-width: 76ch; margin: 0; color: var(--pa-muted); font-size: 12px; line-height: 1.45; }
.workspace-tabs :deep(.arco-tabs-nav) { display: none; }
.workspace-tabs :deep(.arco-tabs-content) { padding-top: 0; }
.advanced-writing-state { margin-top: 10px; border: 1px solid var(--pa-border); border-radius: 7px; background: var(--pa-surface); }
.advanced-writing-state > summary { padding: 9px 12px; color: var(--pa-muted); font-size: 11px; cursor: pointer; }
.advanced-writing-state[open] > summary { border-bottom: 1px solid var(--pa-border); color: var(--pa-text); }
.advanced-writing-state > .arco-spin { display: block; padding: 14px; }
.saved-screening { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--pa-border); }
.project-info-card {
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}
.info-row {
  display: flex;
  gap: 32px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.info-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-label {
  font-size: 12px;
  color: var(--color-text-3);
}
.info-value {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
}
.info-abstract {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-2);
}
.info-abstract p {
  margin: 8px 0 0;
  color: var(--color-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 0 16px;
  gap: 12px;
}
.toolbar-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.execution-status {
  margin-bottom: 16px;
  padding: 12px 16px;
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  background: var(--color-bg-2);
}
.execution-status > div { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.execution-status span { color: var(--pa-muted); font-size: 13px; }
.execution-error { margin: 8px 0 0; color: var(--pa-danger); font-size: 13px; }
.tab-hint {
  font-size: 13px;
  color: var(--color-text-3);
}
.empty-tab {
  padding: 48px 16px;
  text-align: center;
  color: var(--color-text-3);
  background: var(--color-bg-2);
  border-radius: 8px;
  border: 1px dashed var(--color-border-2);
}
.empty-tab p {
  margin: 0;
  font-size: 14px;
}
/* 论文列表 */
.paper-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.paper-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  margin-bottom: 8px;
}
.paper-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.reading-order {
  display: grid;
  place-items: center;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary-light-1);
  color: var(--pa-primary);
  font-size: 12px;
  font-weight: 700;
}
.reading-status { padding: 2px 8px; border-radius: 999px; font-size: 11px; white-space: nowrap; }
.reading-status.status-pending { background: var(--color-fill-2); color: var(--pa-muted); }
.reading-status.status-reading { background: var(--color-primary-light-1); color: var(--pa-primary); }
.reading-status.status-completed { background: rgba(0, 180, 42, 0.12); color: var(--pa-success); }
.reading-status.status-skipped { background: rgba(245, 63, 63, 0.1); color: var(--pa-danger); }
.reading-status.status-failed { background: rgba(245, 63, 63, 0.1); color: var(--pa-danger); }
.reading-plan-summary {
  max-width: 72ch;
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--color-fill-1);
  border-radius: 8px;
}
.reading-plan-summary p { margin: 0; color: var(--pa-muted); font-size: 13px; line-height: 1.55; }
.reading-plan-summary p + p { margin-top: 4px; }
.reading-plan-summary strong { color: var(--pa-text); }
.paper-title-row h4 {
  margin: 0;
  font-size: 15px;
  cursor: pointer;
  color: rgb(var(--primary-6));
}
.paper-title-row h4:hover {
  text-decoration: underline;
}
.role-tag {
  padding: 1px 8px;
  font-size: 11px;
  border-radius: 8px;
  font-weight: 500;
}
.role-tag.role-core { background: rgba(255, 87, 34, 0.1); color: #ff5722; }
.role-tag.role-related { background: rgba(32, 145, 255, 0.1); color: #2091ff; }
.role-tag.role-background { background: var(--color-fill-2); color: var(--color-text-3); }
.paper-year { font-size: 12px; color: var(--color-text-3); }
.paper-authors { margin: 0 0 4px; font-size: 13px; color: var(--color-text-2); }
.paper-tags { display: flex; gap: 4px; margin-bottom: 4px; }
.paper-notes { margin: 4px 0 0; font-size: 12px; color: var(--color-text-3); font-style: italic; }
.paper-card-summary { margin-top: 10px; color: var(--pa-text); font-size: 12px; }
.paper-card-summary summary { color: var(--pa-primary); cursor: pointer; font-weight: 600; }
.paper-card-summary summary:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.paper-card-summary p { max-width: 72ch; margin: 8px 0; line-height: 1.6; }
.paper-card-facts { display: flex; flex-wrap: wrap; gap: 6px; }
.paper-card-facts span { padding: 2px 8px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); }
.paper-actions { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
/* 产物列表 */
.artifact-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.artifact-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 180ms ease-out, background-color 180ms ease-out;
}
.artifact-item:hover {
  border-color: rgb(var(--primary-6));
  background: var(--color-bg-3);
}
.artifact-type-tag {
  padding: 2px 10px;
  font-size: 12px;
  border-radius: 10px;
  font-weight: 500;
  flex-shrink: 0;
  background: rgba(0, 180, 42, 0.1);
  color: #00b42a;
}
.artifact-type-tag.type-outline { background: rgba(168, 127, 226, 0.12); color: #8a5cf6; }
.artifact-type-tag.type-literature_review { background: rgba(0, 180, 42, 0.12); color: #00b42a; }
.artifact-type-tag.type-research_map { background: var(--color-primary-light-1); color: var(--pa-primary); }
.artifact-type-tag.type-reading_plan { background: rgba(22, 93, 255, 0.1); color: var(--pa-info); }
.artifact-type-tag.type-evidence_matrix { background: rgba(0, 180, 42, 0.1); color: var(--pa-success); }
.artifact-type-tag.type-experiment_design { background: rgba(255, 125, 0, 0.1); color: #b85c00; }
.artifact-type-tag.type-paper_blueprint { background: var(--color-primary-light-1); color: var(--pa-primary); }
.artifact-type-tag.type-reference_list { background: rgba(32, 145, 255, 0.12); color: #2091ff; }
.artifact-type-tag.type-section_draft { background: rgba(255, 156, 0, 0.12); color: #ff9c00; }
.artifact-type-tag.type-full_draft { background: rgba(255, 87, 34, 0.12); color: #ff5722; }
.artifact-type-tag.type-review_report { background: rgba(220, 38, 38, 0.12); color: #dc2626; }
.artifact-type-tag.type-submission_suggestion { background: rgba(168, 127, 226, 0.12); color: #8a5cf6; }
.artifact-main { flex: 1; min-width: 0; }
.artifact-main h4 { margin: 0 0 4px; font-size: 14px; }
.artifact-preview {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-3);
  flex-shrink: 0;
}
/* 记忆 */
.memory-summary {
  background: var(--color-bg-2);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
  border: 1px solid var(--pa-border);
}
.memory-summary h4 { margin: 0 0 6px; font-size: 13px; color: var(--color-text-3); }
.memory-summary p { margin: 0; font-size: 14px; line-height: 1.6; }
.memory-list { list-style: none; padding: 0; margin: 0; }
.memory-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: var(--color-bg-2);
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;
}
.memory-tag {
  padding: 1px 8px;
  font-size: 11px;
  border-radius: 8px;
  background: var(--color-fill-2);
  color: var(--color-text-2);
  flex-shrink: 0;
  margin-top: 2px;
}
.memory-tag.tag-finding { background: rgba(0, 180, 42, 0.12); color: #00b42a; }
.memory-tag.tag-method { background: rgba(32, 145, 255, 0.12); color: #2091ff; }
.memory-tag.tag-conclusion { background: rgba(168, 127, 226, 0.12); color: #8a5cf6; }
.memory-tag.tag-todo { background: rgba(255, 156, 0, 0.12); color: #ff9c00; }
.memory-tag.tag-risk { background: rgba(220, 38, 38, 0.12); color: #dc2626; }
.memory-tag.tag-preference { background: rgba(255, 87, 34, 0.12); color: #ff5722; }
.memory-tag.tag-decision { background: rgba(255, 156, 0, 0.12); color: #ff9c00; }
.memory-text { margin: 0; flex: 1; line-height: 1.5; }
.memory-text strong { display: block; margin-bottom: 4px; color: var(--pa-text); }
.memory-text p { max-width: 72ch; margin: 0; color: var(--pa-text); }
.memory-time { font-size: 11px; color: var(--color-text-3); flex-shrink: 0; margin-top: 2px; }
.memory-source { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }
.legacy-badge { padding: 2px 6px; border-radius: 6px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 11px; }
.memory-paper-link { max-width: 220px; padding: 0; overflow: hidden; border: 0; background: transparent; color: var(--pa-primary); cursor: pointer; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.memory-paper-link:hover { color: var(--pa-primary-hover); text-decoration: underline; }
.memory-paper-link:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.evidence-list { display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; list-style: none; }
.evidence-item { padding: 16px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--color-bg-2); }
.evidence-heading { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.evidence-heading .memory-paper-link { max-width: min(72ch, 80%); font-size: 13px; text-align: left; }
.evidence-item blockquote { max-width: 72ch; margin: 0 0 10px; padding: 0 0 0 12px; border-left: 1px solid var(--pa-border); color: var(--pa-text); line-height: 1.65; }
.evidence-claim { max-width: 72ch; margin: 0 0 8px; color: var(--pa-muted); line-height: 1.55; }
/* 论文库选择列表 */
.paper-lib-list { list-style: none; padding: 0; margin: 0; max-height: 360px; overflow-y: auto; }
.paper-lib-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
}
.paper-lib-item:hover { background: var(--color-fill-2); }
.paper-lib-item.selected { border-color: rgb(var(--primary-6)); background: rgba(var(--primary-6), 0.06); }
.paper-lib-item h5 { margin: 0 0 2px; font-size: 13px; }
.paper-lib-item p { margin: 0; font-size: 12px; color: var(--color-text-3); }
/* 产物详情 Modal */
.artifact-detail { padding: 8px 0; }
.artifact-detail-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-3);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-2);
}
.artifact-markdown {
  background: var(--color-bg-2);
  padding: 16px;
  border-radius: 6px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 60vh;
  overflow-y: auto;
  margin: 0;
}

@media (max-width: 1100px) {
  .workbench-areas { grid-template-columns: 1fr; }
  .workbench-area { border-right: 0; border-bottom: 1px solid var(--pa-border); }
  .workbench-area:last-child { border-bottom: 0; }
  .area-open p { min-height: 0; }
}

@media (max-width: 767px) {
  .workbench-heading { align-items: stretch; flex-direction: column; gap: 16px; padding: 20px; }
  .workbench-heading .arco-btn { min-height: 44px; }
  .workbench-area { padding: 18px; }
  .shared-resources { align-items: stretch; flex-direction: column; padding: 12px; }
  .shared-resources > strong { margin: 0 4px 4px; }
  .shared-resources button { justify-content: space-between; min-height: 42px; }
  .workspace-panel { padding: 18px 16px 24px; }
  .workspace-panel-header { align-items: stretch; flex-direction: column; gap: 14px; }
  .workspace-panel-header .arco-btn { min-height: 44px; }
  .workspace-shell { padding: 16px; }
  .toolbar-actions { width: 100%; }
  .toolbar-actions :deep(.arco-btn) { flex: 1 1 auto; min-height: 40px; }
  .info-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .info-block:first-child { grid-column: 1 / -1; }
  .tab-toolbar { align-items: stretch; flex-direction: column; }
  .tab-toolbar :deep(.arco-input-wrapper),
  .tab-toolbar :deep(.arco-select-view) { max-width: none !important; width: 100% !important; }
  .tab-toolbar :deep(.arco-btn) { min-height: 44px; }
  .paper-item { flex-direction: column; }
  .paper-title-row { align-items: flex-start; flex-wrap: wrap; }
  .paper-actions { width: 100%; flex-direction: row; align-items: center; }
  .paper-actions :deep(.arco-select-view) { flex: 1; width: auto !important; }
  .artifact-item { align-items: flex-start; flex-wrap: wrap; }
  .artifact-main { flex-basis: calc(100% - 120px); }
  .artifact-meta { width: 100%; flex-direction: row; justify-content: space-between; }
  .memory-note { flex-wrap: wrap; }
  .memory-text { flex-basis: calc(100% - 80px); }
  .memory-time { width: 100%; padding-left: 4px; }
  .artifact-detail-meta { flex-wrap: wrap; gap: 8px 16px; }
}

@media (max-width: 420px) {
  .info-row { grid-template-columns: 1fr; }
  .info-block:first-child { grid-column: auto; }
  .info-block :deep(.arco-select-view) { width: 100% !important; }
}

@media (prefers-reduced-motion: reduce) {
  .artifact-item { transition: none; }
}
</style>

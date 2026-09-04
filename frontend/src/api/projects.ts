import request from './index'

// ==================== 类型定义 ====================
export interface ResearchProject {
  id: string
  user_id: string
  title: string
  research_topic: string
  abstract: string
  phase: string  // research / reading / writing / refinement / archived
  status: string // active / paused / completed
  memory: { summary: string; notes: ProjectMemoryNote[] }
  preferences: Record<string, any>
  paper_count?: number
  artifact_count?: number
  created_at?: string
  updated_at?: string
}

export interface ProjectMemoryNote {
  time: string
  text: string
  tag: string
  source_type?: 'user' | 'agent' | 'paper' | string
  paper_id?: string | null
  paper_title?: string | null
  page?: number | null
  source_id?: string | null
}

export interface ProjectPaperCard {
  summary?: string
  research_questions?: string[]
  methods?: string[]
  datasets?: string[]
  metrics?: string[]
  contributions?: string[]
  findings?: string[]
  limitations?: string[]
  evidence?: Array<Record<string, any>>
  updated_at?: string
  generated_by?: string
}

export interface ProjectPaperItem {
  id: string
  project_id: string
  paper_id: string
  role: string  // core / related / background
  tags: string[]
  notes: string
  analysis_card: ProjectPaperCard
  reading_plan: {
    order?: number
    status?: 'pending' | 'reading' | 'completed' | 'skipped' | 'failed'
    reason?: string
    focus?: string[]
    questions?: string[]
    updated_at?: string
    completed_at?: string
  }
  reading_priority: number
  added_at: string
  paper?: {
    id: string
    title: string
    authors: string
    abstract: string
    keywords: string[]
    publication_year: number | null
    venue: string | null
    doi: string | null
    reading_progress: number
  }
}

export interface WritingArtifactItem {
  id: string
  project_id: string
  author_id: string
  artifact_type: string  // research_map / paper_blueprint / section_draft / full_draft / review_report / final_manuscript 等
  title: string
  version: number
  parent_id: string | null
  content: Record<string, any>
  markdown_text?: string  // 仅详情接口返回
  markdown_preview?: string  // 列表接口返回
  html_text: string
  status: string
  meta: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface ResearchMapContent {
  topic_summary: string
  keywords: string[]
  research_questions: Array<Record<string, any>>
  method_families: Array<Record<string, any>>
  datasets: Array<Record<string, any>>
  research_gaps: Array<Record<string, any>>
  candidate_topics: Array<Record<string, any>>
  evidence: Array<Record<string, any>>
}

export interface ResearchBriefContent {
  topic: string
  objective: string
  known_context: string[]
  constraints: string[]
  unknowns: string[]
  seed_keywords: string[]
  search_queries: string[]
  inclusion_criteria: string[]
  exclusion_criteria: string[]
  evaluation_criteria: string[]
  next_actions: string[]
}

export interface LiteratureScreeningContent {
  research_brief_id: string
  research_brief_version: number
  query_runs: Array<{ source: string; query: string; result_count: number; filters?: Record<string, any> }>
  candidates: Array<{
    title: string
    authors?: string[]
    year?: number
    venue?: string
    arxiv_id?: string
    doi?: string
    url?: string
    abstract?: string
    decision: 'include' | 'exclude' | 'maybe'
    reason: string
    relevance_score: number
    coverage?: string[]
  }>
  coverage_summary: Array<Record<string, any>>
  stopping_reason: string
  included_count: number
  excluded_count: number
  maybe_count: number
  deduplicated_count: number
}

export interface EvidenceMatrixContent {
  research_question: string
  rows: Array<{
    paper_id: string
    paper_title: string
    role: string
    methods: string[]
    datasets: string[]
    metrics: string[]
    findings: string[]
    limitations: string[]
    evidence: Array<Record<string, any>>
  }>
  conflicts: Array<Record<string, any>>
  evidence_gaps: Array<Record<string, any>>
  generated_from_cards: number
}

export interface ExperimentDesignContent {
  research_question: string
  hypothesis: string
  rationale: string
  independent_variables: string[]
  dependent_variables: string[]
  controls: string[]
  datasets: Array<Record<string, any>>
  baselines: Array<Record<string, any>>
  metrics: Array<Record<string, any>>
  experiment_steps: string[]
  ablations: Array<Record<string, any>>
  success_criteria: string[]
  falsification_criteria: string[]
  risks: Array<Record<string, any>>
  evidence_refs: Array<Record<string, any>>
  requires_empirical_results: boolean
}

export interface ExperimentResultsContent {
  experiment_design_id: string
  experiment_design_version: number
  run_id: string
  sources: Array<{
    source_id: string
    source_type: string
    locator: string
    checksum?: string
    recorded_at?: string
  }>
  metrics: Array<{
    metric: string
    value: number
    unit?: string
    dataset?: string
    split?: string
    method?: string
    baseline?: string
    sample_size?: number
    uncertainty?: string
    source_id: string
  }>
  hypothesis_outcome: 'supported' | 'not_supported' | 'mixed' | 'inconclusive'
  qualitative_findings: string[]
  protocol_deviations: string[]
  analysis_notes: string[]
}

export interface PaperBlueprintContent {
  working_title: string
  central_claim: string
  target_audience: string
  target_venue: string
  experiment_design_id: string
  sections: Array<{
    section_id: string
    title: string
    order: number
    purpose: string
    key_claims: string[]
    evidence_refs: Array<Record<string, any>>
    citation_needs: string[]
    word_target: number
    status: string
  }>
}

export interface ReviewReportContent {
  full_draft_id: string
  full_draft_version: number
  blueprint_id: string
  passed: boolean
  counts: { blocker: number; major: number; minor: number }
  issues: Array<{
    severity: 'blocker' | 'major' | 'minor'
    category: string
    section_id?: string
    description: string
    recommendation: string
    evidence_refs: Array<Record<string, any>>
  }>
}

export interface ProjectMemoryPayload {
  project_id: string
  summary: string
  notes: ProjectMemoryNote[]
  note_count: number
}

export interface ReadingExecution {
  task_id: string
  project_id: string
  status: 'queued' | 'running' | 'paused' | 'completed' | 'failed'
  total: number
  completed: number
  current_paper_id?: string | null
  current_paper_title?: string | null
  error?: string | null
  results: Array<{ paper_id: string; paper_title: string; status: string }>
}

export interface ProjectWorkflowStatus {
  mode?: 'workbench'
  areas?: Array<{
    key: 'topic' | 'reading' | 'writing'
    label: string
    description: string
    status: 'empty' | 'active' | 'ready'
    summary: string
    primary_action: string
    prompt: string
    metrics: Record<string, number | boolean>
  }>
  stages: Array<{ key: string; label: string; status: 'completed' | 'current' | 'pending' }>
  completed: number
  total: number
  progress_percent: number
  next_stage: string
  next_prompt: string
  paper_count: number
  completed_cards: number
  unresolved_items: number
  active_imports: number
  imports: Array<{ arxiv_id: string; paper_id: string; task_id: string; status: string; error?: string }>
}

// ==================== 项目 CRUD ====================
export const listProjects = (params?: { page?: number; page_size?: number; status?: string; q?: string }) =>
  request.get<{ items: ResearchProject[]; total: number; page: number; page_size: number }>(
    '/api/v1/projects',
    { params }
  )

export const createProject = (data: {
  title: string
  research_topic: string
  abstract?: string
  phase?: string
  preferences?: Record<string, any>
}) => request.post<ResearchProject>('/api/v1/projects', data)

export const getProject = (projectId: string) =>
  request.get<ResearchProject>(`/api/v1/projects/${projectId}`)

export const getProjectWorkflowStatus = (projectId: string) =>
  request.get<ProjectWorkflowStatus>(`/api/v1/projects/${projectId}/workflow-status`)

export interface ExternalPaperCandidate {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  published: string
  pdf_url: string
  arxiv_url: string
}

export const searchExternalPapers = (projectId: string, query: string, maxResults = 10) =>
  request.post<{ query: string; count: number; papers: ExternalPaperCandidate[] }>(
    `/api/v1/projects/${projectId}/external-papers/search`,
    { query, max_results: maxResults },
  )

export const importExternalPaper = (projectId: string, data: {
  arxiv_id: string
  role?: 'core' | 'related' | 'background'
  notes?: string
  reading_priority?: number
}) => request.post<{ message: string; arxiv_id: string }>(
  `/api/v1/projects/${projectId}/external-papers/import`, data,
)

export const updateProject = (projectId: string, data: Partial<{
  title: string
  research_topic: string
  abstract: string
  phase: string
  status: string
  preferences: Record<string, any>
}>) => request.patch<ResearchProject>(`/api/v1/projects/${projectId}`, data)

export const deleteProject = (projectId: string) =>
  request.delete<null>(`/api/v1/projects/${projectId}`)

// ==================== 项目文档库 ====================
export const listProjectPapers = (projectId: string, role?: string) =>
  request.get<{ items: ProjectPaperItem[]; total: number }>(
    `/api/v1/projects/${projectId}/papers`,
    { params: role ? { role } : undefined }
  )

export const addProjectPaper = (projectId: string, data: {
  paper_id: string
  role?: string
  tags?: string[]
  notes?: string
  reading_priority?: number
}) => request.post<ProjectPaperItem & { _action: string }>(
  `/api/v1/projects/${projectId}/papers`,
  data
)

export const updateProjectPaper = (projectId: string, paperId: string, data: Partial<{
  role: string
  tags: string[]
  notes: string
  reading_priority: number
  reading_plan: ProjectPaperItem['reading_plan']
}>) => request.patch<ProjectPaperItem>(
  `/api/v1/projects/${projectId}/papers/${paperId}`,
  data
)

export const removeProjectPaper = (projectId: string, paperId: string) =>
  request.delete<null>(`/api/v1/projects/${projectId}/papers/${paperId}`)

export const getProjectPaperCard = (projectId: string, paperId: string) =>
  request.get<{ project_id: string; paper_id: string; card: ProjectPaperCard }>(
    `/api/v1/projects/${projectId}/papers/${paperId}/card`
  )

export const updateProjectPaperCard = (projectId: string, paperId: string, card: ProjectPaperCard) =>
  request.patch<{ project_id: string; paper_id: string; card: ProjectPaperCard }>(
    `/api/v1/projects/${projectId}/papers/${paperId}/card`,
    card
  )

// ==================== 写作产物 ====================
export const listArtifacts = (projectId: string, type?: string) =>
  request.get<{ items: WritingArtifactItem[]; total: number }>(
    `/api/v1/projects/${projectId}/artifacts`,
    { params: type ? { type } : undefined }
  )

export const createArtifact = (projectId: string, data: {
  artifact_type: string
  title: string
  content?: Record<string, any>
  markdown_text?: string
  html_text?: string
  status?: string
  parent_id?: string | null
  meta?: Record<string, any>
}) => request.post<WritingArtifactItem>(`/api/v1/projects/${projectId}/artifacts`, data)

export const getArtifact = (projectId: string, artifactId: string) =>
  request.get<WritingArtifactItem>(`/api/v1/projects/${projectId}/artifacts/${artifactId}`)

export const updateArtifact = (projectId: string, artifactId: string, data: Partial<{
  title: string
  content: Record<string, any>
  markdown_text: string
  html_text: string
  status: string
  parent_id: string | null
  meta: Record<string, any>
}>) => request.patch<WritingArtifactItem>(
  `/api/v1/projects/${projectId}/artifacts/${artifactId}`,
  data
)

export const deleteArtifact = (projectId: string, artifactId: string) =>
  request.delete<null>(`/api/v1/projects/${projectId}/artifacts/${artifactId}`)

export const downloadArtifactExport = (
  projectId: string,
  artifactId: string,
  format: 'md' | 'tex' | 'docx' | 'zip',
) => request.get<Blob>(
  `/api/v1/projects/${projectId}/artifacts/${artifactId}/download`,
  { params: { format }, responseType: 'blob' },
)

// ==================== 自动精读执行器 ====================
export const startReadingExecution = (projectId: string, maxItems = 10) =>
  request.post<ReadingExecution>(`/api/v1/projects/${projectId}/reading-executions`, { max_items: maxItems })

export const getReadingExecution = (projectId: string, taskId: string) =>
  request.get<ReadingExecution>(`/api/v1/projects/${projectId}/reading-executions/${taskId}`)

export const pauseReadingExecution = (projectId: string, taskId: string) =>
  request.post<ReadingExecution>(`/api/v1/projects/${projectId}/reading-executions/${taskId}/pause`)

export const resumeReadingExecution = (projectId: string, taskId: string) =>
  request.post<ReadingExecution>(`/api/v1/projects/${projectId}/reading-executions/${taskId}/resume`)

// ==================== 长期记忆 ====================
export const getProjectMemory = (projectId: string) =>
  request.get<ProjectMemoryPayload>(`/api/v1/projects/${projectId}/memory`)

export const overwriteProjectMemory = (projectId: string, data: {
  summary?: string
  notes?: ProjectMemoryNote[]
}) => request.patch<ProjectMemoryPayload>(`/api/v1/projects/${projectId}/memory`, data)

export const appendProjectMemoryNote = (projectId: string, data: {
  text: string
  tag?: string
  source_type?: string
  paper_id?: string | null
  paper_title?: string | null
  page?: number | null
  source_id?: string | null
}) =>
  request.post<{ project_id: string; note: ProjectMemoryNote; note_count: number }>(
    `/api/v1/projects/${projectId}/memory/note`,
    data
  )

// ==================== 项目对话会话 ====================
/**
 * 创建项目模式对话会话(只传 project_id,paper_id 可空)。
 * 与 paper.ts 的 createSession 区别:那个是单论文模式(必传 paper_id)。
 */
export const createProjectSession = (projectId: string, title?: string) =>
  request.post<{ id: string; paper_id: string | null; project_id: string; title: string }>(
    '/api/v1/chat/sessions',
    { project_id: projectId, title }
  )

export const listProjectSessions = (projectId: string, skip = 0, limit = 20) =>
  request.get<{ items: any[]; total: number }>(
    '/api/v1/chat/sessions',
    { params: { project_id: projectId, skip, limit } }
  )

// ==================== 便捷常量(供 UI 渲染) ====================
export const PHASE_LABELS: Record<string, string> = {
  research: '选题调研',
  reading: '深度阅读',
  writing: '写作中',
  refinement: '完善中',
  archived: '已归档',
}

export const STATUS_LABELS: Record<string, string> = {
  active: '进行中',
  paused: '已暂停',
  completed: '已完成',
}

export const PAPER_ROLE_LABELS: Record<string, string> = {
  core: '核心文献',
  related: '相关工作',
  background: '背景知识',
}

export const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  research_brief: '研究任务书',
  literature_screening: '候选文献筛选',
  research_map: '领域地图',
  reading_plan: '精读计划',
  evidence_matrix: '证据矩阵',
  experiment_design: '实验设计',
  experiment_results: '实验结果',
  paper_blueprint: '论文蓝图',
  outline: '章节大纲',
  literature_review: '文献综述',
  reference_list: '参考文献列表',
  section_draft: '章节草稿',
  full_draft: '完整全文',
  review_report: '审稿报告',
  submission_suggestion: '投稿建议',
  final_manuscript: '论文终稿',
}

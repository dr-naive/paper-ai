<template>
  <div class="paper-reader">
    <!-- 顶部工具栏 -->
    <ProductHeader>
      <template #navigation>
        <a-button @click="goBack" size="small" type="text">
          <template #icon><icon-arrow-left /></template>
          我的论文
        </a-button>
      </template>
      <div class="paper-title-bar">
        <h2 class="paper-title">{{ paper?.title || '加载中...' }}</h2>
        <span class="paper-authors">{{ paper?.authors }}</span>
      </div>
      <template #actions>
        <div class="top-actions">
          <span class="layout-label">工作区</span>
          <div class="layout-switcher" role="group" aria-label="工作区布局">
            <button
              v-for="option in layoutOptions"
              :key="option.value"
              type="button"
              class="layout-option"
              :class="{ active: layoutMode === option.value }"
              :aria-pressed="layoutMode === option.value"
              :title="option.description"
              @click="applyLayoutPreset(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </template>
    </ProductHeader>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧 PDF 查看器 -->
      <div class="pdf-viewer">
        <PdfViewer
          v-if="pdfUrl"
          ref="pdfViewerRef"
          :pdf-url="pdfUrl"
        />
        <div v-if="pdfError" class="pdf-error">
          <a-result status="warning" title="PDF 加载失败">
            <template #subtitle>
              无法加载 PDF 文件，请检查文件是否存在或重新上传
            </template>
            <template #extra>
              <a-button type="primary" @click="retryLoadPdf">重试</a-button>
            </template>
          </a-result>
        </div>
        <div v-else-if="!pdfUrl" class="pdf-loading">
          <a-spin :size="32" />
          <p>加载 PDF 中...</p>
        </div>
      </div>

      <!-- 拖拽调节条 -->
      <div
        v-if="showSidebar"
        class="sidebar-resizer"
        @mousedown="startResize"
      >
        <div class="resizer-handle"></div>
      </div>

      <!-- 右侧 AI 侧边栏 -->
      <div v-if="showSidebar" class="ai-sidebar" :style="{ width: sidebarWidth + 'px', minWidth: sidebarWidth + 'px' }">
        <!-- Tab 切换 -->
        <a-tabs default-active-key="qa" size="small" class="sidebar-tabs">
          <a-tab-pane key="qa" title="问答">
            <div class="qa-panel">
              <!-- 会话管理 -->
              <div class="session-bar">
                <a-select
                  v-model="currentSessionId"
                  placeholder="选择对话"
                  size="small"
                  style="flex: 1; min-width: 0"
                  @change="handleSessionChange"
                >
                  <a-option v-for="s in sessions" :key="s.id" :value="s.id">
                    {{ s.title }}
                  </a-option>
                </a-select>
                <a-button size="mini" @click="createNewSession" title="新对话">
                  + 新对话
                </a-button>
                <a-button
                  v-if="currentSessionId"
                  size="mini"
                  status="danger"
                  @click="handleDeleteSession(currentSessionId)"
                  title="删除当前对话"
                >
                  <template #icon><icon-delete /></template>
                </a-button>
              </div>
              <!-- 问答历史 -->
              <div class="qa-history">
                <div v-if="!qaHistory.length && !qaLoading" class="qa-empty">
                  <div class="qa-empty-mark">AI</div>
                  <strong>从论文内容开始提问</strong>
                  <p>回答会附带引用，点击引用可回到 PDF 核对原文。</p>
                </div>
                <div v-for="qa in qaHistory" :key="qa.id" class="qa-item">
                  <div class="qa-question">
                    <span class="qa-label">问</span>
                    <span>{{ qa.question }}</span>
                  </div>
                  <div class="qa-answer">
                    <span class="qa-label">答</span>
                    <div class="qa-answer-content">
                      <div class="markdown-answer" v-html="renderMarkdown(qa.answer)"></div>
                      <!-- 引用溯源 -->
                      <div v-if="qa.citations && qa.citations.length" class="qa-citations">
                        <div class="citation-title">
                          <span>引用溯源</span>
                          <span class="citation-hint">点击引用可定位到原文</span>
                        </div>
                        <div
                          v-for="(cite, ci) in visibleCitations(qa)"
                          :key="ci"
                          class="citation-item"
                          :class="{ active: activeCitationKey === citationKey(qa.id, ci) }"
                          @click="locateInPdf(cite, citationKey(qa.id, ci))"
                        >
                          <div class="citation-header">
                            <a-tag size="small" color="arcoblue">{{ cite.section }}</a-tag>
                            <span v-if="cite.position" class="citation-position">{{ cite.position }}</span>
                            <span
                              v-if="activeCitationKey === citationKey(qa.id, ci) && activeCitationPage"
                              class="citation-located"
                            >
                              已定位第 {{ activeCitationPage }} 页
                            </span>
                          </div>
                          <p class="citation-text">{{ cite.text }}</p>
                        </div>
                        <button
                          v-if="qa.citations.length > 2"
                          type="button"
                          class="citation-toggle"
                          @click="toggleCitationGroup(qa.id)"
                        >
                          {{ isCitationGroupExpanded(qa.id) ? '收起引用' : `查看全部 ${qa.citations.length} 条引用` }}
                        </button>
                      </div>
                      <!-- 智能追问 -->
                      <div v-if="qa.follow_up_questions && qa.follow_up_questions.length" class="qa-followup">
                        <div class="followup-title">智能追问</div>
                        <a-tag
                          v-for="(fq, fi) in qa.follow_up_questions.slice(0, 3)"
                          :key="fi"
                          clickable
                          size="small"
                          @click="askQuestion(fq)"
                        >
                          {{ fq }}
                        </a-tag>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="qaLoading" class="qa-loading">
                  <a-spin :size="12" /> 思考中...
                </div>
              </div>
              <div class="qa-composer">
                <!-- 快捷问题 -->
                <div class="quick-question-header">
                  <span>你可以这样问</span>
                  <button type="button" @click="showAllQuickQuestions = !showAllQuickQuestions">
                    {{ showAllQuickQuestions ? '收起' : '更多' }}
                  </button>
                </div>
                <div class="quick-questions">
                  <a-tag
                    v-for="q in visibleQuickQuestions"
                    :key="q"
                    clickable
                    size="small"
                    @click="question = q"
                  >
                    {{ q }}
                  </a-tag>
                </div>
                <!-- 输入区 -->
                <div class="qa-input">
                  <a-textarea
                    v-model="question"
                    placeholder="向这篇论文提问..."
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                    @keydown.enter.ctrl="handleAsk"
                  />
                  <div class="qa-input-actions">
                    <span>Ctrl + Enter 提问</span>
                    <a-button
                      type="primary"
                      size="small"
                      :loading="qaLoading"
                      :disabled="!question.trim()"
                      @click="handleAsk"
                    >
                      提问
                    </a-button>
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="summary" title="结构化摘要">
            <div class="summary-panel">
              <!-- 生成按钮 -->
              <div v-if="!structuredSummary" class="summary-actions">
                <a-button
                  type="primary"
                  :loading="summaryLoading"
                  @click="handleGenerateSummary"
                  style="width: 100%"
                >
                  {{ summaryLoading ? 'AI 分析中...' : '生成结构化摘要' }}
                </a-button>
                <p class="summary-hint">AI 将自动提取论文的核心信息</p>
              </div>

              <!-- 结构化摘要内容 -->
              <div v-else class="structured-summary">
                <!-- 操作栏 -->
                <div class="summary-actions-bar">
                  <a-tag size="small" color="green">已缓存</a-tag>
                  <a-button
                    type="outline"
                    size="mini"
                    :loading="summaryLoading"
                    @click="handleGenerateSummary"
                  >
                    <template #icon><icon-refresh /></template>
                    重新生成
                  </a-button>
                </div>
                <!-- 概述 -->
                <div class="summary-section">
                  <h4 class="section-title">
                    <span class="section-icon"></span> 论文概述
                  </h4>
                  <div class="section-content">
                    <div class="info-item">
                      <span class="info-label">一句话总结</span>
                      <p>{{ structuredSummary.overview?.one_sentence_summary }}</p>
                    </div>
                    <div class="info-item">
                      <span class="info-label">研究领域</span>
                      <p>{{ structuredSummary.overview?.research_field }}</p>
                    </div>
                    <div class="info-item">
                      <span class="info-label">核心问题</span>
                      <p>{{ structuredSummary.overview?.core_problem }}</p>
                    </div>
                    <div class="info-item">
                      <span class="info-label">论文类型</span>
                      <a-tag size="small" color="blue">{{ structuredSummary.overview?.paper_type }}</a-tag>
                    </div>
                  </div>
                </div>

                <!-- 方法论 -->
                <div class="summary-section">
                  <h4 class="section-title">
                    <span class="section-icon">️</span> 方法论
                  </h4>
                  <div class="section-content">
                    <div class="info-item">
                      <span class="info-label">方法名称</span>
                      <p>{{ structuredSummary.methodology?.method_name }}</p>
                    </div>
                    <div class="info-item">
                      <span class="info-label">核心思想</span>
                      <p>{{ structuredSummary.methodology?.method_description }}</p>
                    </div>
                    <div v-if="structuredSummary.methodology?.key_techniques?.length" class="info-item">
                      <span class="info-label">关键技术</span>
                      <div class="tag-list">
                        <a-tag v-for="(tech, i) in structuredSummary.methodology.key_techniques" :key="i" size="small">
                          {{ tech }}
                        </a-tag>
                      </div>
                    </div>
                    <div v-if="structuredSummary.methodology?.input_output" class="info-item">
                      <span class="info-label">输入输出</span>
                      <p>{{ structuredSummary.methodology.input_output }}</p>
                    </div>
                  </div>
                </div>

                <!-- 实验 -->
                <div class="summary-section">
                  <h4 class="section-title">
                    <span class="section-icon"></span> 实验
                  </h4>
                  <div class="section-content">
                    <div v-if="structuredSummary.experiments?.datasets?.length" class="info-item">
                      <span class="info-label">数据集</span>
                      <div class="tag-list">
                        <a-tag v-for="(ds, i) in structuredSummary.experiments.datasets" :key="i" size="small" color="green">
                          {{ ds }}
                        </a-tag>
                      </div>
                    </div>
                    <div v-if="structuredSummary.experiments?.baselines?.length" class="info-item">
                      <span class="info-label">基线方法</span>
                      <div class="tag-list">
                        <a-tag v-for="(bl, i) in structuredSummary.experiments.baselines" :key="i" size="small" color="orange">
                          {{ bl }}
                        </a-tag>
                      </div>
                    </div>
                    <div v-if="structuredSummary.experiments?.metrics?.length" class="info-item">
                      <span class="info-label">评估指标</span>
                      <div class="tag-list">
                        <a-tag v-for="(m, i) in structuredSummary.experiments.metrics" :key="i" size="small" color="purple">
                          {{ m }}
                        </a-tag>
                      </div>
                    </div>
                    <div class="info-item">
                      <span class="info-label">主要结果</span>
                      <p>{{ structuredSummary.experiments?.main_results }}</p>
                    </div>
                    <div v-if="structuredSummary.experiments?.best_performance" class="info-item">
                      <span class="info-label">最佳性能</span>
                      <p class="highlight">{{ structuredSummary.experiments.best_performance }}</p>
                    </div>
                  </div>
                </div>

                <!-- 贡献与创新 -->
                <div class="summary-section">
                  <h4 class="section-title">
                    <span class="section-icon">💡</span> 贡献与创新
                  </h4>
                  <div class="section-content">
                    <div v-if="structuredSummary.contributions?.contributions?.length" class="info-item">
                      <span class="info-label">主要贡献</span>
                      <ul class="bullet-list">
                        <li v-for="(c, i) in structuredSummary.contributions.contributions" :key="i">{{ c }}</li>
                      </ul>
                    </div>
                    <div v-if="structuredSummary.contributions?.innovations?.length" class="info-item">
                      <span class="info-label">创新点</span>
                      <ul class="bullet-list">
                        <li v-for="(inn, i) in structuredSummary.contributions.innovations" :key="i">{{ inn }}</li>
                      </ul>
                    </div>
                    <div v-if="structuredSummary.contributions?.limitations?.length" class="info-item">
                      <span class="info-label">局限性</span>
                      <ul class="bullet-list warning">
                        <li v-for="(lim, i) in structuredSummary.contributions.limitations" :key="i">{{ lim }}</li>
                      </ul>
                    </div>
                    <div v-if="structuredSummary.contributions?.future_work" class="info-item">
                      <span class="info-label">未来工作</span>
                      <p>{{ structuredSummary.contributions.future_work }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="interpret" title="深度解读">
            <div class="interpret-panel">
              <!-- 解读类型选择 -->
              <div class="interpret-actions">
                <a-radio-group v-model="interpretType" type="button" size="small">
                  <a-radio value="concept">概念解释</a-radio>
                  <a-radio value="compare">方法对比</a-radio>
                  <a-radio value="key_info">关键信息</a-radio>
                </a-radio-group>
                <div class="interpret-actions-row">
                  <a-button
                    type="primary"
                    :loading="interpretLoading"
                    @click="handleInterpret"
                    style="flex: 1"
                  >
                    {{ interpretLoading ? 'AI 分析中...' : (interpretResult ? '重新解读' : '开始解读') }}
                  </a-button>
                  <a-tag v-if="interpretResult" size="small" color="green" style="margin-left: 8px">已缓存</a-tag>
                </div>
              </div>

              <!-- 解读结果 -->
              <div v-if="interpretResult" class="interpret-result">
                <!-- 概念解释 -->
                <div v-if="interpretType === 'concept' && interpretResult.data?.concepts">
                  <div v-for="(c, i) in interpretResult.data.concepts" :key="i" class="concept-item">
                    <h5 class="concept-name">{{ c.name }}</h5>
                    <p class="concept-explanation">{{ c.explanation }}</p>
                    <p class="concept-context" v-if="c.context">💡 {{ c.context }}</p>
                  </div>
                </div>

                <!-- 方法对比 -->
                <div v-if="interpretType === 'compare' && interpretResult.data?.comparisons">
                  <div v-for="(comp, i) in interpretResult.data.comparisons" :key="i" class="compare-item">
                    <div class="compare-header">
                      <a-tag color="arcoblue">{{ comp.item_a }}</a-tag>
                      <span class="vs">VS</span>
                      <a-tag color="orangered">{{ comp.item_b }}</a-tag>
                    </div>
                    <p class="compare-diff"><strong>差异：</strong>{{ comp.difference }}</p>
                    <p class="compare-adv"><strong>优势：</strong>{{ comp.advantage }}</p>
                  </div>
                </div>

                <!-- 关键信息 -->
                <div v-if="interpretType === 'key_info' && interpretResult.data">
                  <div v-if="interpretResult.data.key_formulas?.length" class="info-section">
                    <h5>关键公式/算法</h5>
                    <ul class="bullet-list">
                      <li v-for="(f, i) in interpretResult.data.key_formulas" :key="i">{{ f }}</li>
                    </ul>
                  </div>
                  <div v-if="interpretResult.data.key_figures?.length" class="info-section">
                    <h5>关键图表</h5>
                    <ul class="bullet-list">
                      <li v-for="(fig, i) in interpretResult.data.key_figures" :key="i">{{ fig }}</li>
                    </ul>
                  </div>
                  <div v-if="interpretResult.data.key_findings?.length" class="info-section">
                    <h5>关键发现</h5>
                    <ul class="bullet-list">
                      <li v-for="(kf, i) in interpretResult.data.key_findings" :key="i">{{ kf }}</li>
                    </ul>
                  </div>
                  <div v-if="interpretResult.data.takeaways?.length" class="info-section">
                    <h5>值得关注</h5>
                    <ul class="bullet-list">
                      <li v-for="(t, i) in interpretResult.data.takeaways" :key="i">{{ t }}</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconArrowLeft, IconRefresh, IconDelete } from '@arco-design/web-vue/es/icon'
import type PdfViewerComponent from '@/components/PdfViewer.vue'
import ProductHeader from '@/components/ProductHeader.vue'
import { renderMarkdown } from '@/utils/markdown'
import {
  getPaper, getPaperSections,
  listSessions, createSession, deleteSession, getSessionMessages, askInSession,
  generateSummary, getSummaryCache,
  interpretPaper, getInterpretCache
} from '@/api/paper'

const route = useRoute()
const router = useRouter()
const PdfViewer = defineAsyncComponent(() => import('@/components/PdfViewer.vue'))
const paperId = route.params.id as string
const paper = ref<any>(null)
const pdfUrl = ref('')
const pdfError = ref(false)
const pdfViewerRef = ref<InstanceType<typeof PdfViewerComponent> | null>(null)
const showSidebar = ref(true)
const sidebarWidth = ref(420)
type LayoutMode = 'read' | 'compare' | 'ai'
const layoutMode = ref<LayoutMode>('compare')
const layoutOptions: Array<{ value: LayoutMode; label: string; description: string }> = [
  { value: 'read', label: '阅读', description: '隐藏 AI 助手，专注阅读论文' },
  { value: 'compare', label: '对照', description: '并排查看论文与 AI 回答' },
  { value: 'ai', label: 'AI', description: '扩大 AI 助手区域' }
]
const sections = ref<any[]>([])
const paperTables = ref<any[]>([])

// 结构化摘要相关
const structuredSummary = ref<any>(null)
const summaryLoading = ref(false)

// 深度解读相关
const interpretType = ref('concept')
const interpretResult = ref<any>(null)
const interpretLoading = ref(false)

// QA 相关 - 基于会话
const question = ref('')
const qaHistory = ref<any[]>([])
const qaLoading = ref(false)
const currentSessionId = ref<string>('')
const sessions = ref<any[]>([])
const showAllQuickQuestions = ref(false)
const expandedCitationGroups = ref<Set<string>>(new Set())
const activeCitationKey = ref('')
const activeCitationPage = ref<number | null>(null)
const quickQuestions = [
  '这篇论文的主要贡献是什么？',
  '论文使用的主要方法是什么？',
  '实验结果如何？',
  '论文的创新性有哪些？',
  '这篇论文的局限性是什么？'
]
const visibleQuickQuestions = computed(() => (
  showAllQuickQuestions.value ? quickQuestions : quickQuestions.slice(0, 3)
))

const clampSidebarWidth = (width: number) => {
  const viewportLimit = Math.max(360, window.innerWidth - 420)
  return Math.round(Math.min(1120, viewportLimit, Math.max(360, width)))
}

const applyLayoutPreset = (mode: LayoutMode) => {
  layoutMode.value = mode
  if (mode === 'read') {
    showSidebar.value = false
    void nextTick(() => pdfViewerRef.value?.fitWidth())
    return
  }

  showSidebar.value = true
  const ratio = mode === 'compare' ? 0.38 : 0.56
  sidebarWidth.value = clampSidebarWidth(window.innerWidth * ratio)
  void nextTick(() => pdfViewerRef.value?.fitWidth())
}

const citationKey = (qaId: string | number, index: number) => `${qaId}:${index}`

const isCitationGroupExpanded = (qaId: string | number) => expandedCitationGroups.value.has(String(qaId))

const visibleCitations = (qa: any) => (
  isCitationGroupExpanded(qa.id) ? qa.citations : qa.citations.slice(0, 2)
)

const toggleCitationGroup = (qaId: string | number) => {
  const next = new Set(expandedCitationGroups.value)
  const key = String(qaId)
  next.has(key) ? next.delete(key) : next.add(key)
  expandedCitationGroups.value = next
}

const handleWindowResize = () => {
  if (showSidebar.value) sidebarWidth.value = clampSidebarWidth(sidebarWidth.value)
}

// 加载会话列表
const loadSessions = async () => {
  try {
    const res = await listSessions(paperId)
    sessions.value = res.items || []
    
    // 如果有会话且当前没有选中会话，自动选择第一个会话
    if (sessions.value.length > 0 && !currentSessionId.value) {
      currentSessionId.value = sessions.value[0].id
      await switchSession(sessions.value[0].id)
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
  }
}

// 创建新会话
const createNewSession = async () => {
  try {
    const res = await createSession(paperId)
    currentSessionId.value = res.id
    qaHistory.value = []
    await loadSessions()
    Message.success('已创建新对话')
  } catch (error) {
    Message.error('创建会话失败')
  }
}

// 切换会话
const switchSession = async (sessionId: string) => {
  currentSessionId.value = sessionId
  try {
    const res = await getSessionMessages(sessionId)
    qaHistory.value = res.messages.map((m: any) => ({
      id: m.id,
      question: m.question,
      answer: m.answer,
      citations: m.citations || [],
      follow_up_questions: m.follow_up_questions || []
    }))
  } catch (error) {
    Message.error('加载会话失败')
  }
}

const syncPendingQaMessage = async (sessionId: string, messageId: string) => {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 3000))
    if (currentSessionId.value !== sessionId) return

    try {
      const res = await getSessionMessages(sessionId)
      const remoteMessage = (res.messages || []).find((m: any) => m.id === messageId)
      if (!remoteMessage) continue

      const localMessage = qaHistory.value.find(item => item.id === messageId)
      if (localMessage) {
        localMessage.follow_up_questions = remoteMessage.follow_up_questions || []
      }

      if (remoteMessage.follow_up_questions?.length) {
        await loadSessions()
        return
      }
    } catch (error) {
      console.error('同步后台追问失败:', error)
    }
  }
  await loadSessions()
}

const handleSessionChange = (value: string | number | boolean | Record<string, any> | Array<string | number | boolean | Record<string, any>>) => {
  if (typeof value === 'string') {
    switchSession(value)
  }
}

// 删除会话
const handleDeleteSession = async (sessionId: string) => {
  Modal.confirm({
    title: '确认删除',
    content: '删除后将无法恢复该对话记录',
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteSession(sessionId)
        if (currentSessionId.value === sessionId) {
          currentSessionId.value = ''
          qaHistory.value = []
        }
        await loadSessions()
        Message.success('已删除')
      } catch (error) {
        Message.error('删除失败')
      }
    }
  })
}

// 侧边栏拖拽调节
const startResize = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = sidebarWidth.value
  
  const onMouseMove = (e: MouseEvent) => {
    const delta = startX - e.clientX
    sidebarWidth.value = clampSidebarWidth(startWidth + delta)
  }
  
  const onMouseUp = () => {
    layoutMode.value = sidebarWidth.value / window.innerWidth >= 0.48 ? 'ai' : 'compare'
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

const goBack = () => {
  router.push('/papers')
}

const loadPaper = async () => {
  try {
    const response = await getPaper(paperId)
    paper.value = response
    pdfError.value = false
    const token = localStorage.getItem('access_token')
    pdfUrl.value = `/api/v1/papers/${paperId}/pdf?token=${token}`
  } catch (error) {
    console.error('加载论文失败:', error)
    Message.error('加载论文失败')
  }
}

const retryLoadPdf = () => {
  pdfError.value = false
  const token = localStorage.getItem('access_token')
  pdfUrl.value = `/api/v1/papers/${paperId}/pdf?token=${token}&t=${Date.now()}`
}

const normalizeLocationText = (value: unknown) => String(value || '')
  .normalize('NFKC')
  .toLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, '')

const findCitationPage = (cite: any): number | null => {
  const explicitPage = Number(cite?.page)
  if (Number.isInteger(explicitPage) && explicitPage > 0) return explicitPage

  const sectionText = String(cite?.section || '')
  const numberMatch = sectionText.match(/(?:表|table)\s*(\d+)/i)
  const tableNumber = Number(cite?.table_number || numberMatch?.[1])
  const normalizedSection = normalizeLocationText(sectionText)
  const tables = [
    ...paperTables.value,
    ...sections.value.flatMap(section => section.tables || [])
  ]

  const matchedTable = tables.find((table: any) => {
    const caption = normalizeLocationText(table.caption || table.title || '')
    const captionMatches = caption && normalizedSection && (
      caption.includes(normalizedSection) || normalizedSection.includes(caption)
    )
    const numberMatches = Number.isInteger(tableNumber) && tableNumber > 0
      && Number(table.table_number) === tableNumber
    return captionMatches || numberMatches
  })

  const page = Number(matchedTable?.page || matchedTable?.page_number)
  return Number.isInteger(page) && page > 0 ? page : null
}

// 定位引用到 PDF 原文
const locateInPdf = async (cite: any, key: string) => {
  activeCitationKey.value = key
  activeCitationPage.value = null

  if (!cite?.section) {
    Message.warning('引用信息不完整')
    return
  }
  
  // 检查章节数据是否已加载
  if (sections.value.length === 0) {
    Message.warning('章节数据尚未加载，正在尝试重新加载...')
    // 尝试重新加载章节数据
    await loadSections()
    if (sections.value.length === 0) {
      Message.warning('无法加载章节数据')
      return
    }
  }
  
  // 查找对应章节（支持多种匹配方式）
  let targetSection = sections.value.find(s => s.section_title === cite.section)
  
  // 如果精确匹配失败，尝试模糊匹配
  if (!targetSection) {
    targetSection = sections.value.find(s => 
      s.section_title.includes(cite.section) || cite.section.includes(s.section_title)
    )
  }
  
  // 如果还是没找到，使用第一个章节（通常是"全文"）
  if (!targetSection && sections.value.length > 0) {
    targetSection = sections.value[0]
  }

  if (!pdfViewerRef.value) {
    Message.warning('PDF 阅读器尚未加载完成')
    return
  }

  const citationPage = findCitationPage(cite)
  if (citationPage) {
    Message.info(`正在定位到第 ${citationPage} 页...`)
    await pdfViewerRef.value.scrollToPage(citationPage)
    pdfViewerRef.value.highlightPage(citationPage)
    activeCitationPage.value = citationPage
    Message.success(`已定位到第 ${citationPage} 页`)
    return
  }

  const searchCandidates = [cite.search_text, cite.text, cite.section]
    .map(value => String(value || '').trim())
    .filter(Boolean)

  if (searchCandidates.length) {
    Message.info(`正在定位：${searchCandidates[0].substring(0, 30)}...`)
    const foundPage = await pdfViewerRef.value.searchText(searchCandidates)
    if (foundPage) {
      pdfViewerRef.value.highlightPage(foundPage)
      activeCitationPage.value = foundPage
      Message.success(`已定位到第 ${foundPage} 页`)
    } else {
      Message.warning('未在 PDF 中找到匹配的原文内容')
    }
  } else {
    Message.info(`引用来源：${cite.section}`)
  }
}

const loadSections = async () => {
  try {
    const response = await getPaperSections(paperId)
    sections.value = response.sections || []
    paperTables.value = response.tables || []
  } catch (error) {
    console.error('加载章节失败:', error)
  }
}

const handleAsk = async () => {
  if (!question.value.trim()) {
    Message.warning('请输入问题')
    return
  }
  await askQuestion(question.value)
}

const askQuestion = async (q: string) => {
  if (!currentSessionId.value) {
    await createNewSession()
  }
  
  question.value = q
  qaLoading.value = true
  try {
    const response = await askInSession(currentSessionId.value, q)
    qaHistory.value.push({
      id: response.message_id,
      question: q,
      answer: response.answer,
      citations: response.citations || [],
      follow_up_questions: response.follow_up_questions || []
    })
    question.value = ''
    if (response.follow_up_pending && response.message_id) {
      void syncPendingQaMessage(currentSessionId.value, response.message_id)
    }
    // 刷新会话列表（更新标题）
    await loadSessions()
  } catch (error) {
    Message.error('回答生成失败')
  } finally {
    qaLoading.value = false
  }
}

const handleGenerateSummary = async () => {
  summaryLoading.value = true
  try {
    const response = await generateSummary(paperId)
    structuredSummary.value = response
    Message.success('摘要已更新')
  } catch (error) {
    Message.error('摘要生成失败')
  } finally {
    summaryLoading.value = false
  }
}

// 加载缓存的摘要
const loadSummaryCache = async () => {
  try {
    const response = await getSummaryCache(paperId)
    if (response.cached) {
      structuredSummary.value = response
    }
  } catch (error) {
    console.error('加载摘要缓存失败:', error)
  }
}

const handleInterpret = async () => {
  interpretLoading.value = true
  try {
    const response = await interpretPaper(paperId, interpretType.value)
    interpretResult.value = response
    Message.success('解读完成')
  } catch (error) {
    Message.error('解读失败')
  } finally {
    interpretLoading.value = false
  }
}

// 加载缓存的解读
const loadInterpretCache = async () => {
  try {
    const response = await getInterpretCache(paperId, interpretType.value)
    if (response.cached) {
      interpretResult.value = response
    }
  } catch (error) {
    console.error('加载解读缓存失败:', error)
  }
}

onMounted(() => {
  applyLayoutPreset('compare')
  window.addEventListener('resize', handleWindowResize)
  loadPaper()
  loadSections()
  loadSessions()
  loadSummaryCache()
  loadInterpretCache()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})

// 监听解读类型变化，加载对应缓存
watch(interpretType, () => {
  interpretResult.value = null
  loadInterpretCache()
})
</script>

<style scoped>
.paper-reader {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--pa-bg);
}

.paper-title-bar {
  flex: 1;
  min-width: 0;
}

.paper-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--pa-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.paper-authors {
  font-size: 12px;
  color: var(--pa-muted);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.layout-label {
  font-size: 12px;
  color: var(--pa-muted);
}

.layout-switcher {
  display: flex;
  padding: 3px;
  border: 1px solid var(--pa-border);
  border-radius: 7px;
  background: var(--pa-bg);
}

.layout-option {
  min-width: 48px;
  min-height: 30px;
  padding: 4px 12px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pa-text);
  font-size: 13px;
  cursor: pointer;
}

.layout-option:hover { color: var(--pa-primary); }

.layout-option.active {
  background: var(--pa-surface);
  color: var(--pa-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(29, 33, 41, 0.12);
}

.layout-option:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* PDF 查看器 */
.pdf-viewer {
  flex: 1;
  min-width: 0;
  background: oklch(0.36 0.012 45);
  overflow: hidden;
}

.pdf-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--pa-ink);
  gap: 16px;
}

.pdf-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 24px;
}

/* 拖拽调节条 */
.sidebar-resizer {
  position: relative;
  width: 12px;
  cursor: col-resize;
  background: var(--pa-surface-soft);
  flex-shrink: 0;
}

.sidebar-resizer::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 5px;
  width: 2px;
  background: var(--pa-border);
  transition: background 0.2s ease;
}

.sidebar-resizer:hover::after { background: var(--pa-primary); }

.resizer-handle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 6px;
  height: 36px;
  border: 1px solid var(--pa-border);
  border-radius: 6px;
  background: var(--pa-surface);
  z-index: 1;
}

/* AI 侧边栏 */
.ai-sidebar {
  width: 380px;
  min-width: 380px;
  background: var(--pa-surface);
  border-left: 1px solid var(--pa-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-tabs :deep(.arco-tabs-content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.sidebar-tabs :deep(.arco-tabs-content-list) {
  height: 100%;
}

.sidebar-tabs :deep(.arco-tabs-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* QA 面板 */
.qa-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

/* 会话管理栏 */
.session-bar {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 10px 12px;
  margin: 0;
  border-bottom: 1px solid var(--pa-border);
}

.session-bar :deep(.arco-select) {
  min-width: 0;
}

/* 摘要操作栏 */
.summary-actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--pa-bg);
  border-radius: 6px;
}

/* 解读操作栏 */
.interpret-actions-row {
  display: flex;
  align-items: center;
  margin-top: 12px;
}

.qa-history {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 20px;
}

.qa-item {
  margin-bottom: 24px;
}

.qa-empty {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
  color: var(--pa-text);
}

.qa-empty-mark {
  display: grid;
  width: 36px;
  height: 36px;
  margin-bottom: 12px;
  place-items: center;
  border-radius: 8px;
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
  font-size: 12px;
  font-weight: 700;
}

.qa-empty strong { color: var(--pa-ink); font-size: 14px; }
.qa-empty p { max-width: 30em; margin: 6px 0 0; font-size: 12px; line-height: 1.6; }

.qa-question,
.qa-answer {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.qa-answer-content {
  flex: 1;
  min-width: 0;
}

.markdown-answer {
  margin-bottom: 8px;
  color: var(--pa-ink);
  overflow-x: auto;
  overflow-wrap: anywhere;
  line-height: 1.72;
}

.markdown-answer :deep(p) {
  margin: 0 0 10px;
}

.markdown-answer :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-answer :deep(ul),
.markdown-answer :deep(ol) {
  margin: 6px 0 10px;
  padding-left: 24px;
}

.markdown-answer :deep(li) {
  margin: 4px 0;
}

.markdown-answer :deep(h2),
.markdown-answer :deep(h3),
.markdown-answer :deep(h4) {
  margin: 14px 0 6px;
  line-height: 1.4;
}

.markdown-answer :deep(h2) { font-size: 17px; }
.markdown-answer :deep(h3) { font-size: 15px; }
.markdown-answer :deep(h4) { font-size: 14px; }

.markdown-answer :deep(table) {
  width: max-content;
  min-width: 100%;
  margin: 10px 0 12px;
  border-collapse: collapse;
  font-size: 12px;
}

.markdown-answer :deep(th),
.markdown-answer :deep(td) {
  padding: 7px 10px;
  border: 1px solid var(--pa-border);
  text-align: left;
  white-space: nowrap;
}

.markdown-answer :deep(th) {
  background: var(--pa-surface-soft);
  font-weight: 600;
}

.markdown-answer :deep(tr:nth-child(even) td) {
  background: var(--pa-bg);
}

.markdown-answer :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--pa-surface-soft);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.92em;
}

.qa-label {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
}

.qa-question .qa-label {
  background: var(--pa-info);
}

.qa-answer .qa-label {
  background: var(--pa-success);
}

.qa-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--pa-muted);
  font-size: 13px;
  padding: 12px;
}

.qa-composer {
  flex-shrink: 0;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--pa-border);
  background: var(--pa-surface);
  box-shadow: 0 -6px 18px rgba(29, 33, 41, 0.04);
}

.quick-question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--pa-muted);
}

.quick-question-header button,
.citation-toggle {
  border: 0;
  padding: 2px 4px;
  background: transparent;
  color: var(--pa-primary);
  font: inherit;
  cursor: pointer;
}

.quick-question-header button:focus-visible,
.citation-toggle:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.quick-questions :deep(.arco-tag),
.qa-followup :deep(.arco-tag) {
  border-color: oklch(0.82 0.07 55);
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.qa-input {
  padding: 8px;
  border: 1px solid var(--pa-border);
  border-radius: 8px;
  background: var(--pa-surface);
}

.qa-input:focus-within {
  border-color: var(--pa-primary);
  box-shadow: 0 0 0 2px oklch(0.50 0.16 45 / 0.1);
}

.qa-input :deep(.arco-textarea) {
  padding: 2px 4px;
  border: 0;
  box-shadow: none;
  resize: none;
}

.qa-input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 6px;
}

.qa-input-actions > span {
  font-size: 11px;
  color: var(--pa-muted);
}

/* 引用溯源 */
.qa-citations {
  margin-top: 10px;
  padding: 10px;
  background: var(--pa-info-soft);
  border-radius: 8px;
  border: 1px solid oklch(0.82 0.05 250);
}

.citation-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--pa-info);
  margin-bottom: 8px;
}

.citation-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--pa-muted);
}

.citation-item {
  background: var(--pa-surface);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid var(--pa-border);
}

.citation-item:hover {
  border-color: var(--pa-info);
  box-shadow: 0 2px 8px oklch(0.51 0.12 250 / 0.15);
}

.citation-item.active {
  border-color: var(--pa-info);
  background: var(--pa-info-soft);
  box-shadow: 0 0 0 2px oklch(0.51 0.12 250 / 0.1);
}

.citation-item:last-child {
  margin-bottom: 0;
}

.citation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.citation-position {
  font-size: 11px;
  color: var(--pa-muted);
}

.citation-located {
  margin-left: auto;
  color: var(--pa-info);
  font-size: 11px;
  font-weight: 600;
}

.citation-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--pa-ink);
  word-break: break-word;
}

.citation-toggle {
  display: block;
  margin: 2px auto 0;
  font-size: 12px;
}

/* 智能追问 */
.qa-followup {
  margin-top: 8px;
  padding: 8px;
  background: var(--pa-info-soft);
  border-radius: 6px;
}

.followup-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--pa-info);
  margin-bottom: 6px;
}

.qa-followup .arco-tag {
  margin: 2px;
}

@media (max-width: 900px) {
  .layout-label { display: none; }
  .layout-option { min-width: 42px; padding-inline: 8px; }
  .paper-authors { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-resizer::after,
  .citation-item { transition: none; }
}

/* 摘要面板 */
.summary-panel {
  padding: 12px;
  overflow-y: auto;
  flex: 1;
}

.summary-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.summary-hint {
  font-size: 12px;
  color: var(--pa-muted);
  margin: 0;
}

.structured-summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-section {
  background: var(--pa-bg);
  border-radius: 8px;
  padding: 12px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--pa-ink);
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-icon {
  width: 4px;
  height: 14px;
  background: var(--pa-info);
  border-radius: 2px;
}

.section-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--pa-muted);
}

.info-item p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--pa-ink);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.highlight {
  color: var(--pa-success);
  font-weight: 500;
}

.bullet-list {
  margin: 0;
  padding-left: 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--pa-ink);
}

.bullet-list.warning {
  color: #f97316;
}

.bullet-list li {
  margin-bottom: 4px;
}

/* 深度解读面板 */
.interpret-panel {
  padding: 12px;
  overflow-y: auto;
  flex: 1;
}

.interpret-actions {
  margin-bottom: 16px;
}

.interpret-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.concept-item {
  background: var(--pa-bg);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}

.concept-name {
  margin: 0 0 6px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--pa-ink);
}

.concept-explanation {
  margin: 0 0 6px 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--pa-ink);
}

.concept-context {
  margin: 0;
  font-size: 12px;
  color: var(--pa-muted);
  font-style: italic;
}

.compare-item {
  background: var(--pa-bg);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}

.compare-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.vs {
  font-size: 12px;
  font-weight: 600;
  color: var(--pa-muted);
}

.compare-diff,
.compare-adv {
  margin: 0 0 4px 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--pa-ink);
}

.info-section {
  margin-bottom: 12px;
}

.info-section h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--pa-ink);
}
</style>

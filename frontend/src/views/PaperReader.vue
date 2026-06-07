<template>
  <div class="paper-reader">
    <!-- 顶部工具栏 -->
    <div class="top-bar">
      <a-button @click="goBack" size="small">
        <template #icon><icon-arrow-left /></template>
        返回
      </a-button>
      <div class="paper-title-bar">
        <h2 class="paper-title">{{ paper?.title || '加载中...' }}</h2>
        <span class="paper-authors">{{ paper?.authors }}</span>
      </div>
      <div class="top-actions">
        <a-button size="small" @click="toggleSidebar">
          <template #icon><icon-menu /></template>
          AI 助手
        </a-button>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧 PDF 查看器 -->
      <div class="pdf-viewer" :style="{ flex: sidebarWidth > 0 ? `0 0 calc(100% - ${sidebarWidth}px)` : '1' }">
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
                  size="mini"
                  style="flex: 1; min-width: 0"
                  @change="switchSession"
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
                <div v-for="qa in qaHistory" :key="qa.id" class="qa-item">
                  <div class="qa-question">
                    <span class="qa-label">问</span>
                    <span>{{ qa.question }}</span>
                  </div>
                  <div class="qa-answer">
                    <span class="qa-label">答</span>
                    <div class="qa-answer-content">
                      <span>{{ qa.answer }}</span>
                      <!-- 引用溯源 -->
                      <div v-if="qa.citations && qa.citations.length" class="qa-citations">
                        <div class="citation-title">
                          <span>引用溯源</span>
                          <span class="citation-hint">点击引用可定位到原文</span>
                        </div>
                        <div
                          v-for="(cite, ci) in qa.citations"
                          :key="ci"
                          class="citation-item"
                          @click="locateInPdf(cite)"
                        >
                          <div class="citation-header">
                            <a-tag size="mini" color="arcoblue">{{ cite.section }}</a-tag>
                            <span v-if="cite.position" class="citation-position">{{ cite.position }}</span>
                          </div>
                          <p class="citation-text">{{ cite.text }}</p>
                        </div>
                      </div>
                      <!-- 智能追问 -->
                      <div v-if="qa.follow_up_questions && qa.follow_up_questions.length" class="qa-followup">
                        <div class="followup-title">智能追问</div>
                        <a-tag
                          v-for="(fq, fi) in qa.follow_up_questions"
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
                  <a-spin size="mini" /> 思考中...
                </div>
              </div>
              <!-- 快捷问题 -->
              <div class="quick-questions">
                <a-tag
                  v-for="q in quickQuestions"
                  :key="q"
                  clickable
                  size="small"
                  @click="askQuestion(q)"
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
                <a-button
                  type="primary"
                  size="small"
                  :loading="qaLoading"
                  @click="handleAsk"
                  style="margin-top: 8px; width: 100%"
                >
                  提问
                </a-button>
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
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconArrowLeft, IconMenu, IconRefresh, IconDelete } from '@arco-design/web-vue/es/icon'
import PdfViewer from '@/components/PdfViewer.vue'
import {
  getPaper, getPaperSections,
  listSessions, createSession, deleteSession, getSessionMessages, askInSession,
  generateSummary, getSummaryCache,
  interpretPaper, getInterpretCache
} from '@/api/paper'

const route = useRoute()
const router = useRouter()
const paperId = route.params.id as string
const paper = ref<any>(null)
const pdfUrl = ref('')
const pdfError = ref(false)
const pdfViewerRef = ref<InstanceType<typeof PdfViewer> | null>(null)
const showSidebar = ref(true)
const sidebarWidth = ref(420)
const sections = ref<any[]>([])
const highlightedSection = ref('')

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
const quickQuestions = [
  '这篇论文的主要贡献是什么？',
  '论文使用的主要方法是什么？',
  '实验结果如何？',
  '论文的创新性有哪些？',
  '这篇论文的局限性是什么？'
]

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

const toggleSidebar = () => {
  showSidebar.value = !showSidebar.value
}

// 侧边栏拖拽调节
const startResize = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = sidebarWidth.value
  
  const onMouseMove = (e: MouseEvent) => {
    const delta = startX - e.clientX
    const newWidth = Math.min(800, Math.max(300, startWidth + delta))
    sidebarWidth.value = newWidth
  }
  
  const onMouseUp = () => {
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
    // 动态获取当前服务器地址，支持其他电脑访问
    const token = localStorage.getItem('access_token')
    const baseUrl = window.location.origin.replace(':5173', ':8000')
    pdfUrl.value = `${baseUrl}/api/v1/papers/${paperId}/pdf?token=${token}`
  } catch (error) {
    console.error('加载论文失败:', error)
    Message.error('加载论文失败')
  }
}

const retryLoadPdf = () => {
  pdfError.value = false
  const token = localStorage.getItem('access_token')
  const baseUrl = window.location.origin.replace(':5173', ':8000')
  pdfUrl.value = `${baseUrl}/api/v1/papers/${paperId}/pdf?token=${token}&t=${Date.now()}`
}

// 定位引用到 PDF 原文
const locateInPdf = async (cite: any) => {
  console.log('locateInPdf called with:', cite)
  console.log('Current sections:', sections.value)
  
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
    console.log('未找到匹配章节，使用默认章节:', targetSection.section_title)
  }
  
  console.log('Found section:', targetSection)
  
  if (!pdfViewerRef.value) {
    Message.warning('PDF 阅读器尚未加载完成')
    return
  }
  
  // 优先使用引用文本进行搜索定位
  const searchText = cite.text ? cite.text.substring(0, 100).trim() : cite.section
  
  if (searchText) {
    Message.info(`正在定位：${searchText.substring(0, 30)}...`)
    const foundPage = await pdfViewerRef.value.searchText(searchText)
    if (foundPage) {
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
  loadPaper()
  loadSections()
  loadSessions()
  loadSummaryCache()
  loadInterpretCache()
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
  background: #f5f7fa;
}

/* 顶部工具栏 */
.top-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  min-height: 48px;
}

.paper-title-bar {
  flex: 1;
  min-width: 0;
}

.paper-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.paper-authors {
  font-size: 12px;
  color: #86909c;
}

.top-actions {
  display: flex;
  gap: 8px;
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
  background: #525659;
  overflow: hidden;
}

.pdf-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #1d2129;
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
  width: 4px;
  cursor: col-resize;
  background: #e5e6eb;
  transition: background 0.2s;
  flex-shrink: 0;
}

.sidebar-resizer:hover {
  background: #6366f1;
}

.resizer-handle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 32px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 1px;
}

/* AI 侧边栏 */
.ai-sidebar {
  width: 380px;
  min-width: 380px;
  background: #fff;
  border-left: 1px solid #e5e6eb;
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
  padding: 12px;
}

/* 会话管理栏 */
.session-bar {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5e6eb;
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
  background: #f5f7fa;
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
  margin-bottom: 12px;
}

.qa-item {
  margin-bottom: 16px;
}

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

.qa-answer-content > span {
  display: block;
  margin-bottom: 8px;
  color: #1d2129;
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
  background: #6366f1;
}

.qa-answer .qa-label {
  background: #10b981;
}

.qa-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #86909c;
  font-size: 13px;
  padding: 12px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.qa-input {
  border-top: 1px solid #e5e6eb;
  padding-top: 12px;
}

/* 引用溯源 */
.qa-citations {
  margin-top: 10px;
  padding: 10px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 8px;
  border-left: 3px solid #6366f1;
}

.citation-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
  margin-bottom: 8px;
}

.citation-hint {
  font-size: 11px;
  font-weight: 400;
  color: #86909c;
}

.citation-item {
  background: #fff;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e5e6eb;
}

.citation-item:hover {
  border-color: #6366f1;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
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
  color: #86909c;
}

.citation-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #1d2129;
  word-break: break-word;
}

/* 智能追问 */
.qa-followup {
  margin-top: 8px;
  padding: 8px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 6px;
}

.followup-title {
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  margin-bottom: 6px;
}

.qa-followup .arco-tag {
  margin: 2px;
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
  color: #86909c;
  margin: 0;
}

.structured-summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-section {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-icon {
  width: 4px;
  height: 14px;
  background: #6366f1;
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
  color: #86909c;
}

.info-item p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #1d2129;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.highlight {
  color: #10b981;
  font-weight: 500;
}

.bullet-list {
  margin: 0;
  padding-left: 16px;
  font-size: 13px;
  line-height: 1.6;
  color: #1d2129;
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
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}

.concept-name {
  margin: 0 0 6px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.concept-explanation {
  margin: 0 0 6px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #1d2129;
}

.concept-context {
  margin: 0;
  font-size: 12px;
  color: #86909c;
  font-style: italic;
}

.compare-item {
  background: #f5f7fa;
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
  color: #86909c;
}

.compare-diff,
.compare-adv {
  margin: 0 0 4px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #1d2129;
}

.info-section {
  margin-bottom: 12px;
}

.info-section h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}
</style>

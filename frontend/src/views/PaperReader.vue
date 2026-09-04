<template>
  <div class="paper-reader">
    <!-- 顶部工具栏 -->
    <ProductHeader edge back-to="/library" back-label="我的论文">
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

    <div class="mobile-workspace-nav" role="tablist" aria-label="阅读工作区">
      <button
        v-for="pane in mobilePanes"
        :key="pane.value"
        type="button"
        role="tab"
        :aria-selected="mobilePane === pane.value"
        :class="{ active: mobilePane === pane.value }"
        @click="selectMobilePane(pane.value)"
      >
        {{ pane.label }}
      </button>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <PaperOutline
        class="reader-outline"
        :class="{ 'mobile-pane-active': mobilePane === 'outline' }"
        v-model:collapsed="outlineCollapsed"
        :sections="sections"
        :current-page="currentPdfPage"
        :loading="sectionsLoading"
        :refreshing="sectionsRebuilding"
        @navigate="navigateToSection"
        @refresh="rebuildSections"
      />

      <!-- 左侧 PDF 查看器 -->
      <div class="pdf-viewer" :class="{ 'mobile-pane-active': mobilePane === 'pdf' }">
        <PdfViewer
          v-if="pdfUrl"
          ref="pdfViewerRef"
          :pdf-url="pdfUrl"
          @page-change="handlePdfPageChange"
          @load-error="pdfError = true"
          @load-success="handlePdfLoaded"
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
        role="separator"
        tabindex="0"
        aria-label="调整 PDF 与 AI 助手的宽度"
        aria-orientation="vertical"
        :aria-valuemin="360"
        :aria-valuemax="1120"
        :aria-valuenow="sidebarWidth"
        @pointerdown="startResize"
        @keydown="handleResizeKeydown"
      >
        <div class="resizer-handle"></div>
      </div>

      <!-- 右侧 AI 侧边栏 -->
      <div
        v-if="showSidebar"
        class="ai-sidebar"
        :class="{ 'mobile-pane-active': mobilePane === 'ai' }"
        :style="{ width: sidebarWidth + 'px', minWidth: sidebarWidth + 'px' }"
      >
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
              <div class="qa-history-shell">
                <div
                  ref="qaHistoryRef"
                  class="qa-history"
                  @scroll.passive="handleQaHistoryScroll"
                  @wheel.passive="handleQaHistoryWheel"
                >
                  <div v-if="!qaHistory.length && !qaLoading" class="qa-empty">
                    <div class="qa-empty-mark">AI</div>
                    <strong>从论文内容开始提问</strong>
                    <p>回答会附带引用，点击引用可回到 PDF 核对原文。</p>
                  </div>
                  <div
                    v-for="qa in qaHistory"
                    :id="`qa-${qa.id}`"
                    :key="qa.id"
                    class="qa-item"
                  >
                  <div class="qa-question">
                    <span class="qa-label">问</span>
                    <span class="qa-question-text">{{ qa.question }}</span>
                    <a-dropdown trigger="click" position="br">
                      <button
                        type="button"
                        class="qa-more-button"
                        :disabled="deletingMessageIds.has(String(qa.id))"
                        :aria-label="`管理问题：${qa.question}`"
                        title="编辑或删除这条问答"
                      >
                        <span aria-hidden="true">•••</span>
                      </button>
                      <template #content>
                        <a-doption @click="editQaMessage(qa)">
                          <template #icon><icon-edit /></template>
                          编辑
                        </a-doption>
                        <a-doption
                          status="danger"
                          :disabled="qa.streaming || String(qa.id).startsWith('stream-')"
                          @click="confirmDeleteQaMessage(qa)"
                        >
                          <template #icon><icon-delete /></template>
                          删除
                        </a-doption>
                      </template>
                    </a-dropdown>
                  </div>
                  <div class="qa-answer">
                    <span class="qa-label">答</span>
                    <div class="qa-answer-content">
                      <div v-if="qa.thinking" class="qa-thinking">
                        <button
                          type="button"
                          class="qa-thinking-header"
                          :aria-expanded="qa.thinkingExpanded"
                          @click="qa.thinkingExpanded = !qa.thinkingExpanded"
                        >
                          <span class="qa-thinking-title">
                            <a-spin v-if="qa.thinkingStreaming" :size="11" />
                            {{ qa.thinkingStreaming ? '正在思考' : '思考过程' }}
                          </span>
                          <span>{{ qa.thinkingExpanded ? '收起' : '展开' }}</span>
                        </button>
                        <div v-show="qa.thinkingExpanded" class="qa-thinking-content">
                          {{ qa.thinking }}
                        </div>
                      </div>
                      <div
                        v-if="qa.answer"
                        class="markdown-answer"
                        :class="{ streaming: qa.streaming }"
                        v-html="renderMarkdown(qa.answer)"
                      ></div>
                      <div v-if="qa.streaming && !qa.answer" class="qa-stream-status">
                        <a-spin :size="12" />
                        <span>{{ qa.status || '正在准备回答' }}</span>
                      </div>
                      <div v-else-if="qa.streaming" class="qa-stream-progress">
                        {{ qa.status || '正在生成' }}
                      </div>
                      <div v-if="projectId && qa.answer && !qa.streaming" class="research-save-actions">
                        <a-button size="mini" @click="saveAnswerAsNote(qa)">保存为研究笔记</a-button>
                        <a-button size="mini" @click="compareInProject">与项目论文比较</a-button>
                      </div>
                      <div
                        v-if="qa.streamError"
                        class="qa-stream-error"
                        role="alert"
                        aria-live="assertive"
                      >
                        <span class="qa-stream-error-icon" aria-hidden="true">!</span>
                        <div class="qa-stream-error-content">
                          <strong>{{ qa.errorStage ? `${qa.errorStage}失败` : '回答生成失败' }}</strong>
                          <p>{{ qa.streamError }}</p>
                          <button
                            type="button"
                            :disabled="qaLoading"
                            @click="askQuestion(qa.question)"
                          >
                            重新生成
                          </button>
                        </div>
                      </div>
                      <div v-if="!qa.streaming && !qa.streamError" class="qa-message-actions">
                        <button type="button" @click="askQuestion(qa.question)">
                          重新生成
                        </button>
                      </div>
                      <!-- Agent 过程 -->
                      <div v-if="qa.agentTrace" class="qa-agent-trace">
                        <button
                          type="button"
                          class="qa-agent-trace-header"
                          :aria-expanded="qa.agentTraceExpanded"
                          @click="qa.agentTraceExpanded = !qa.agentTraceExpanded"
                        >
                          <span class="qa-agent-trace-title">Agent 过程</span>
                          <span class="qa-agent-trace-summary">
                            {{ qa.agentTrace.iterations || 0 }} 轮 · {{ (qa.agentTrace.tool_calls || []).length }} 次工具调用 · {{ qa.agentTrace.total_tokens || 0 }} tokens
                          </span>
                          <span>{{ qa.agentTraceExpanded ? '收起' : '展开' }}</span>
                        </button>
                        <div v-show="qa.agentTraceExpanded" class="qa-agent-trace-content">
                          <div class="qa-agent-trace-stats">
                            <span>迭代: {{ qa.agentTrace.iterations || 0 }}</span>
                            <span>LLM 调用: {{ qa.agentTrace.llm_calls || 0 }}</span>
                            <span>耗时: {{ ((qa.agentTrace.total_ms || 0) / 1000).toFixed(1) }}s</span>
                            <span>Tokens: {{ qa.agentTrace.total_tokens || 0 }}</span>
                          </div>
                          <div v-if="(qa.agentTrace.tool_calls || []).length" class="qa-agent-trace-tools">
                            <div
                              v-for="(tc, ti) in qa.agentTrace.tool_calls"
                              :key="ti"
                              class="qa-agent-trace-tool"
                              :class="{ ok: tc.ok !== false, fail: tc.ok === false }"
                            >
                              <span class="qa-agent-trace-tool-name">{{ tc.name }}</span>
                              <span class="qa-agent-trace-tool-args">{{ tc.args }}</span>
                              <span v-if="tc.elapsed_ms" class="qa-agent-trace-tool-time">{{ (tc.elapsed_ms / 1000).toFixed(2) }}s</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <!-- 引用溯源 -->
                      <div v-if="qa.citations && qa.citations.length" class="qa-citations">
                        <div class="citation-title">
                          <span>引用溯源</span>
                          <span class="citation-hint">当前论文可直接定位，跨论文引用会打开来源论文</span>
                        </div>
                        <div
                          v-for="(cite, ci) in visibleCitations(qa)"
                          :key="ci"
                          class="citation-row"
                        >
                        <button type="button" class="citation-item"
                          :class="{ active: activeCitationKey === citationKey(qa.id, ci) }"
                          :aria-label="`查看引用：${cite.paper_title || cite.section || '原文引用'}`"
                          @click="handleCitationClick(cite, citationKey(qa.id, ci))"
                        >
                          <div class="citation-header">
                            <span v-if="cite.paper_title" class="citation-paper">{{ cite.paper_title }}</span>
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
                        </button>
                        <a-button v-if="projectId" size="mini" class="save-evidence-button" @click="saveCitationAsEvidence(cite)">保存证据</a-button>
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
                </div>
                <button
                  v-if="!isFollowingLatest && qaHistory.length"
                  type="button"
                  class="qa-scroll-latest"
                  aria-label="回到最新回答并继续自动跟随"
                  @click="scrollQaToLatest(true)"
                >
                  回到最新
                </button>
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
                    ref="questionInputRef"
                    v-model="question"
                    placeholder="向这篇论文提问..."
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                    @keydown.enter.ctrl="handleAsk"
                  />
                  <div class="qa-input-actions">
                    <div class="qa-input-options">
                      <div
                        class="qa-thinking-option"
                        title="开启后会展示模型的思考过程，回答时间可能更长"
                      >
                        <a-switch
                          v-model="thinkingEnabled"
                          size="small"
                          :disabled="qaLoading"
                        />
                        <button
                          type="button"
                          :disabled="qaLoading"
                          @click="thinkingEnabled = !thinkingEnabled"
                        >
                          深度思考
                        </button>
                      </div>
                      <span>Ctrl + Enter 发送</span>
                    </div>
                    <a-button
                      v-if="qaLoading"
                      size="small"
                      status="danger"
                      @click="stopCurrentAnswer"
                    >
                      停止生成
                    </a-button>
                    <a-button
                      v-else
                      type="primary"
                      size="small"
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
import { IconRefresh, IconDelete, IconEdit } from '@arco-design/web-vue/es/icon'
import type PdfViewerComponent from '@/components/PdfViewer.vue'
import type { OutlineNode } from '@/components/PaperOutlineNode.vue'
import PaperOutline from '@/components/PaperOutline.vue'
import ProductHeader from '@/components/ProductHeader.vue'
import { renderMarkdown } from '@/utils/markdown'
import {
  getPaper, getPaperSections, rebuildPaperSections,
  updateReadingStatus,
  listSessions, createSession, deleteSession, deleteSessionMessage, getSessionMessages,
  getAnswerTask, resumeAnswerTask, stopAnswerTask, streamAskInSession,
  generateSummary, getSummaryCache,
  interpretPaper, getInterpretCache
} from '@/api/paper'
import type { AskStreamHandlers } from '@/api/paper'
import { createEvidence, createResearchNote } from '@/api/projects'

const route = useRoute()
const router = useRouter()
const PdfViewer = defineAsyncComponent(() => import('@/components/PdfViewer.vue'))
const paperId = route.params.id as string
const projectId = computed(() => String(route.query.project_id || ''))
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
type MobilePane = 'outline' | 'pdf' | 'ai'
const mobilePane = ref<MobilePane>('pdf')
const mobilePanes: Array<{ value: MobilePane; label: string }> = [
  { value: 'outline', label: '目录' },
  { value: 'pdf', label: '论文' },
  { value: 'ai', label: 'AI 助手' }
]
const selectMobilePane = (pane: MobilePane) => {
  mobilePane.value = pane
  if (pane === 'outline') outlineCollapsed.value = false
}
const sections = ref<any[]>([])
const paperTables = ref<any[]>([])
const sectionsLoading = ref(true)
const sectionsRebuilding = ref(false)
const outlineCollapsed = ref(false)
const currentPdfPage = ref(1)
const totalPdfPages = ref(0)
let readingProgressTimer: number | null = null

// 结构化摘要相关
const structuredSummary = ref<any>(null)
const summaryLoading = ref(false)

// 深度解读相关
const interpretType = ref('concept')
const interpretResult = ref<any>(null)
const interpretLoading = ref(false)

// QA 相关 - 基于会话
const question = ref('')
const questionInputRef = ref<any>(null)
const qaHistory = ref<any[]>([])
const qaLoading = ref(false)
const thinkingEnabled = ref(false)
const qaHistoryRef = ref<HTMLElement | null>(null)
const isFollowingLatest = ref(true)
let lastQaScrollTop = 0
let qaAbortController: AbortController | null = null
const currentAnswerTaskId = ref('')
const currentSessionId = ref<string>('')
const sessions = ref<any[]>([])
const showAllQuickQuestions = ref(false)
const expandedCitationGroups = ref<Set<string>>(new Set())
const activeCitationKey = ref('')
const activeCitationPage = ref<number | null>(null)
const deletingMessageIds = ref<Set<string>>(new Set())
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

const isQaHistoryNearBottom = (element: HTMLElement, threshold = 72) => (
  element.scrollHeight - element.scrollTop - element.clientHeight <= threshold
)

const handleQaHistoryScroll = () => {
  const element = qaHistoryRef.value
  if (!element) return
  const isMovingUp = element.scrollTop < lastQaScrollTop - 1
  lastQaScrollTop = element.scrollTop
  if (isMovingUp) {
    isFollowingLatest.value = false
    return
  }
  if (isFollowingLatest.value) {
    isFollowingLatest.value = isQaHistoryNearBottom(element)
  } else if (isQaHistoryNearBottom(element, 12)) {
    isFollowingLatest.value = true
  }
}

const handleQaHistoryWheel = (event: WheelEvent) => {
  if (event.deltaY < 0) isFollowingLatest.value = false
}

const scrollQaToLatest = (smooth = false) => {
  isFollowingLatest.value = true
  void nextTick(() => {
    const element = qaHistoryRef.value
    if (!element) return
    element.scrollTo({
      top: element.scrollHeight,
      behavior: smooth && !window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'smooth'
        : 'auto'
    })
  })
}

const followQaLatestAfterRender = () => {
  if (isFollowingLatest.value) scrollQaToLatest()
}

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
  const ratio = mode === 'compare' ? 0.34 : 0.56
  sidebarWidth.value = clampSidebarWidth(window.innerWidth * ratio)
  void nextTick(() => pdfViewerRef.value?.fitWidth())
}

const citationKey = (qaId: string | number, index: number) => `${qaId}:${index}`

const isCitationGroupExpanded = (qaId: string | number) => expandedCitationGroups.value.has(String(qaId))

const visibleCitations = (qa: any) => (
  isCitationGroupExpanded(qa.id) ? qa.citations : qa.citations.slice(0, 2)
)

const citationPage = (cite: any): number | undefined => {
  const value = Number(cite.page || cite.page_number || String(cite.position || '').match(/\d+/)?.[0])
  return Number.isFinite(value) && value > 0 ? value : undefined
}

const saveCitationAsEvidence = async (cite: any) => {
  if (!projectId.value || !cite.text) return
  try {
    await createEvidence(projectId.value, {
      paper_id: String(cite.paper_id || paperId), evidence_type: 'quote', snippet: String(cite.text),
      normalized_claim: '', page_number: citationPage(cite),
    })
    Message.success('引用已保存为研究证据')
  } catch (error: any) { Message.error(error?.response?.data?.detail || '保存证据失败') }
}

const saveAnswerAsNote = async (qa: any) => {
  if (!projectId.value || !qa.answer) return
  try {
    await createResearchNote(projectId.value, { type: 'finding', title: String(qa.question || '论文问答记录').slice(0, 300), content: String(qa.answer), tags: ['paper-reader'] })
    Message.success('回答已保存为研究笔记')
  } catch (error: any) { Message.error(error?.response?.data?.detail || '保存笔记失败') }
}

const compareInProject = () => router.push({ name: 'ProjectWorkspace', params: { id: projectId.value }, query: { area: 'reading' } })

const toggleCitationGroup = (qaId: string | number) => {
  const next = new Set(expandedCitationGroups.value)
  const key = String(qaId)
  next.has(key) ? next.delete(key) : next.add(key)
  expandedCitationGroups.value = next
}

const handleWindowResize = () => {
  if (showSidebar.value) sidebarWidth.value = clampSidebarWidth(sidebarWidth.value)
  if (window.innerWidth <= 1100) outlineCollapsed.value = true
}

const navigateToSection = async (section: OutlineNode) => {
  if (!pdfViewerRef.value) return
  mobilePane.value = 'pdf'
  await pdfViewerRef.value.scrollToPage(section.startPage)
  pdfViewerRef.value.highlightPage(section.startPage)
}

const readingPositionKey = `paperai:reading-position:${paperId}`

const persistReadingProgress = async () => {
  if (!totalPdfPages.value) return
  const progress = Math.min(
    100,
    Math.max(0, currentPdfPage.value / totalPdfPages.value * 100)
  )
  const status = progress >= 98 ? 'completed' : progress > 0 ? 'reading' : 'unread'
  localStorage.setItem(readingPositionKey, JSON.stringify({
    page: currentPdfPage.value,
    total: totalPdfPages.value,
    updatedAt: new Date().toISOString()
  }))
  try {
    await updateReadingStatus(paperId, { progress, status })
  } catch (error) {
    console.error('保存阅读进度失败:', error)
  }
}

const scheduleReadingProgressSave = () => {
  if (readingProgressTimer !== null) window.clearTimeout(readingProgressTimer)
  readingProgressTimer = window.setTimeout(() => {
    readingProgressTimer = null
    void persistReadingProgress()
  }, 800)
}

const handlePdfPageChange = (page: number) => {
  currentPdfPage.value = page
  scheduleReadingProgressSave()
}

const handlePdfLoaded = async (pages: number) => {
  pdfError.value = false
  totalPdfPages.value = pages
  await nextTick()
  await pdfViewerRef.value?.fitWidth()
  try {
    const saved = JSON.parse(localStorage.getItem(readingPositionKey) || '{}')
    const savedPage = Math.min(pages, Math.max(1, Number(saved.page || 1)))
    if (savedPage > 1) {
      await pdfViewerRef.value?.scrollToPage(savedPage)
      currentPdfPage.value = savedPage
    }
  } catch {
    // Ignore a damaged local reading-position record and start from page one.
  }
  scheduleReadingProgressSave()
}

// 加载会话列表
const loadSessions = async () => {
  try {
    const res = await listSessions(paperId)
    sessions.value = res.items || []
    
    // 如果有会话且当前没有选中会话，自动选择第一个会话
    if (sessions.value.length > 0 && !currentSessionId.value) {
      const requestedSession = String(route.query.session || '')
      const target = sessions.value.find(item => item.id === requestedSession) || sessions.value[0]
      currentSessionId.value = target.id
      await switchSession(target.id)
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
  } catch {
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
      follow_up_questions: m.follow_up_questions || [],
      thinking: '',
      thinkingExpanded: false,
      thinkingStreaming: false
    }))
    const requestedMessage = String(route.query.message || '')
    if (requestedMessage) {
      await nextTick()
      document.getElementById(`qa-${requestedMessage}`)?.scrollIntoView({
        block: 'center',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      })
    }
    await recoverActiveAnswer(sessionId)
    const requestedPrompt = String(route.query.prompt || '')
    if (requestedPrompt && !question.value) {
      question.value = requestedPrompt
      await router.replace({ query: { ...route.query, prompt: undefined } })
      await nextTick()
      questionInputRef.value?.focus?.()
    }
  } catch {
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
      } catch {
        Message.error('删除失败')
      }
    }
  })
}

const editQaMessage = (qa: any) => {
  question.value = String(qa?.question || '')
  void nextTick(() => {
    questionInputRef.value?.focus?.()
  })
}

const confirmDeleteQaMessage = (qa: any) => {
  if (!currentSessionId.value || qa?.streaming || String(qa?.id || '').startsWith('stream-')) {
    return
  }
  Modal.confirm({
    title: '删除这条问答？',
    content: '问题、回答和引用将一起删除，此操作无法撤销。',
    okText: '删除问答',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      const messageId = String(qa.id)
      deletingMessageIds.value = new Set(deletingMessageIds.value).add(messageId)
      try {
        await deleteSessionMessage(currentSessionId.value, messageId)
        qaHistory.value = qaHistory.value.filter(item => String(item.id) !== messageId)
        const expanded = new Set(expandedCitationGroups.value)
        expanded.delete(messageId)
        expandedCitationGroups.value = expanded
        await loadSessions()
        Message.success('已删除这条问答')
      } catch (error: any) {
        const detail = error?.response?.data?.detail
        Message.error(detail || '删除问答失败，请重试')
        throw error
      } finally {
        const next = new Set(deletingMessageIds.value)
        next.delete(messageId)
        deletingMessageIds.value = next
      }
    }
  })
}

// 侧边栏拖拽调节
const startResize = (e: PointerEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = sidebarWidth.value
  
  const onPointerMove = (moveEvent: PointerEvent) => {
    const delta = startX - moveEvent.clientX
    sidebarWidth.value = clampSidebarWidth(startWidth + delta)
  }
  
  const onPointerUp = () => {
    layoutMode.value = sidebarWidth.value / window.innerWidth >= 0.48 ? 'ai' : 'compare'
    document.removeEventListener('pointermove', onPointerMove)
    document.removeEventListener('pointerup', onPointerUp)
  }
  
  document.addEventListener('pointermove', onPointerMove)
  document.addEventListener('pointerup', onPointerUp)
}

const handleResizeKeydown = (event: KeyboardEvent) => {
  const step = event.shiftKey ? 64 : 20
  if (event.key === 'ArrowLeft') sidebarWidth.value = clampSidebarWidth(sidebarWidth.value + step)
  else if (event.key === 'ArrowRight') sidebarWidth.value = clampSidebarWidth(sidebarWidth.value - step)
  else if (event.key === 'Home') sidebarWidth.value = 360
  else if (event.key === 'End') sidebarWidth.value = clampSidebarWidth(1120)
  else return
  event.preventDefault()
  layoutMode.value = sidebarWidth.value / window.innerWidth >= 0.48 ? 'ai' : 'compare'
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
  const directBbox = Array.isArray(cite.bbox) ? cite.bbox : null
  const cellBboxes = Array.isArray(cite.cell_bboxes) ? cite.cell_bboxes : []
  if (citationPage && (directBbox?.length === 4 || cellBboxes.length)) {
    const location = await pdfViewerRef.value.highlightBbox(
      citationPage,
      directBbox,
      cellBboxes
    )
    if (location) {
      activeCitationPage.value = location.page
      Message.success(`已框选第 ${location.page} 页引用位置`)
      return
    }
  }
  const searchCandidates = [cite.search_text, cite.text]
    .map(value => String(value || '').trim())
    .filter(Boolean)

  if (searchCandidates.length) {
    Message.info(`正在定位：${searchCandidates[0].substring(0, 30)}...`)
    const location = await pdfViewerRef.value.highlightCitation(
      citationPage,
      searchCandidates
    )
    if (location) {
      activeCitationPage.value = location.page
      Message.success(`已框选第 ${location.page} 页引用原文`)
      return
    }
  }

  if (citationPage) {
    await pdfViewerRef.value.scrollToPage(citationPage)
    pdfViewerRef.value.highlightPage(citationPage)
    activeCitationPage.value = citationPage
    Message.warning(`已定位到第 ${citationPage} 页，未匹配到具体原文`)
    return
  }

  Message.warning('未在 PDF 中找到匹配的引用原文')
}

const handleCitationClick = async (cite: any, key: string) => {
  const sourcePaperId = String(cite?.paper_id || '')
  if (sourcePaperId && sourcePaperId !== paperId) {
    const target = router.resolve({ name: 'PaperReader', params: { id: sourcePaperId } })
    window.open(target.href, '_blank', 'noopener,noreferrer')
    Message.info(`已打开来源论文：${cite.paper_title || sourcePaperId}`)
    return
  }
  await locateInPdf(cite, key)
}

const loadSections = async () => {
  sectionsLoading.value = true
  try {
    const response = await getPaperSections(paperId)
    sections.value = response.sections || []
    paperTables.value = response.tables || []
  } catch (error) {
    console.error('加载章节失败:', error)
  } finally {
    sectionsLoading.value = false
  }
}

const rebuildSections = async () => {
  if (sectionsRebuilding.value) return
  sectionsRebuilding.value = true
  try {
    const result = await rebuildPaperSections(paperId) as any
    await loadSections()
    Message.success(result.added > 0
      ? `目录已更新，补充 ${result.added} 个章节`
      : '目录已重新校验')
  } catch (error) {
    console.error('重新抽取目录失败:', error)
    Message.error('重新抽取目录失败')
  } finally {
    sectionsRebuilding.value = false
  }
}

const handleAsk = async () => {
  if (!question.value.trim()) {
    Message.warning('请输入问题')
    return
  }
  await askQuestion(question.value)
}

const activeTaskStorageKey = (sessionId: string) => `paperai:active-answer:${sessionId}`

const rememberActiveTask = (sessionId: string, taskId: string, taskQuestion: string) => {
  localStorage.setItem(
    activeTaskStorageKey(sessionId),
    JSON.stringify({ taskId, question: taskQuestion })
  )
}

const forgetActiveTask = (sessionId: string) => {
  localStorage.removeItem(activeTaskStorageKey(sessionId))
}

const answerStageLabel = (stage = '') => {
  const labels: Record<string, string> = {
    load_context: '读取论文',
    classify_intent: '理解问题',
    retrieve_evidence: '检索论文',
    evaluate_evidence: '检查证据',
    generate_answer: '模型生成',
    organize_citations: '整理引用',
    persist_message: '保存回答',
    worker: '后台处理',
    queue: '任务排队',
    loading_context: '读取论文',
    agent: 'Agent 分析',
    agent_thinking: 'Agent 分析',
    generating: '生成回答',
    persisting: '保存回答'
  }
  return labels[stage] || ''
}

/** 把技术错误消息转译成用户可读的友好消息 */
const friendlyErrorMessage = (error: any): string => {
  if (error?.name === 'AbortError') return '回答已停止'
  const msg = (error?.message || '').toLowerCase()
  if (!msg) return '回答生成失败，请稍后重试'
  // 网络类
  if (msg.includes('failed to fetch') || msg.includes('networkerror') || msg.includes('network request failed'))
    return '网络连接失败，请检查网络后重试'
  if (msg.includes('timeout') || msg.includes('timed out'))
    return '请求超时，请稍后重试或简化问题'
  // HTTP 状态码
  if (msg.includes('401') || msg.includes('unauthorized'))
    return '登录已过期，请重新登录'
  if (msg.includes('403') || msg.includes('forbidden'))
    return '没有权限，请重新登录'
  if (msg.includes('429') || msg.includes('rate limit'))
    return '请求过于频繁，请稍等片刻再试'
  if (msg.includes('500') || msg.includes('502') || msg.includes('503') || msg.includes('504'))
    return '服务器繁忙，请稍后重试'
  // AI 服务类
  if (msg.includes('connection error') || msg.includes('connect error'))
    return 'AI 服务连接失败，请稍后重试'
  if (msg.includes('overloaded') || msg.includes('service unavailable'))
    return 'AI 服务繁忙，请稍后重试'
  if (msg.includes('quota'))
    return 'AI 服务配额已用尽，请联系管理员'
  if (msg.includes('content filter'))
    return '问题内容被安全策略拦截，请调整后重试'
  if (msg.includes('context length') || msg.includes('maximum context'))
    return '对话过长，请尝试新建会话或简化问题'
  // 通用兜底
  return error?.message || '回答生成失败，请稍后重试'
}

const recoverActiveAnswer = async (sessionId: string) => {
  if (qaLoading.value) return
  const raw = localStorage.getItem(activeTaskStorageKey(sessionId))
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    if (!saved.taskId || !saved.question) {
      forgetActiveTask(sessionId)
      return
    }
    const task = await getAnswerTask(saved.taskId)
    if (
      task.status === 'completed'
      && task.result?.message_id
      && qaHistory.value.some(item => item.id === task.result.message_id)
    ) {
      forgetActiveTask(sessionId)
      return
    }
    await askQuestion(saved.question, saved.taskId, Boolean(task.enable_thinking))
  } catch (error: any) {
    forgetActiveTask(sessionId)
    if (error?.response?.status !== 404) {
      console.error('恢复回答任务失败:', error)
    }
  }
}

const stopCurrentAnswer = async () => {
  if (!currentAnswerTaskId.value) {
    qaAbortController?.abort()
    return
  }
  const pending = qaHistory.value.find(item => item.streaming)
  if (pending) pending.status = '正在停止生成'
  try {
    await stopAnswerTask(currentAnswerTaskId.value)
  } catch {
    Message.error('停止生成失败，请重试')
  }
}

const askQuestion = async (
  q: string,
  resumeTaskId = '',
  resumeThinking: boolean | null = null
) => {
  const normalizedQuestion = q.trim()
  if (!normalizedQuestion || qaLoading.value) return
  if (!currentSessionId.value) {
    await createNewSession()
  }

  const sessionId = currentSessionId.value
  const enableThinking = resumeThinking ?? thinkingEnabled.value
  const temporaryId = `stream-${Date.now()}`
  const pendingMessageData: any = {
    id: temporaryId,
    question: normalizedQuestion,
    answer: '',
    citations: [],
    follow_up_questions: [],
    streaming: true,
    status: '正在检索论文',
    streamError: '',
    errorStage: '',
    thinking: '',
    thinkingExpanded: enableThinking,
    thinkingStreaming: false,
    agentTrace: null as any,
    agentTraceExpanded: false
  }
  qaHistory.value.push(pendingMessageData)
  // Mutate the reactive proxy stored in the array, not the original raw object.
  const pendingMessage = qaHistory.value[qaHistory.value.length - 1]
  question.value = ''
  qaLoading.value = true
  currentAnswerTaskId.value = resumeTaskId
  qaAbortController = new AbortController()
  let receivedAnswer = ''
  let receivedReasoning = ''
  let displayedOffset = 0
  let typingTimer: number | null = null
  let reasoningTimer: number | null = null
  let streamDoneData: any = null
  let streamStopped = false
  let pendingCitations: any[] = []
  let resolveTyping: (() => void) | null = null
  const typingComplete = new Promise<void>(resolve => {
    resolveTyping = resolve
  })
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const updateDisplayedAnswer = (answer: string) => {
    pendingMessage.answer = answer
    followQaLatestAfterRender()
  }

  const scheduleTyping = () => {
    if (typingTimer !== null) return
    typingTimer = window.setTimeout(() => {
      typingTimer = null
      const remaining = receivedAnswer.slice(displayedOffset)
      if (remaining) {
        const backlog = Array.from(remaining)
        const batchSize = prefersReducedMotion
          ? backlog.length
          : backlog.length > 240
            ? 10
            : backlog.length > 100
              ? 5
              : backlog.length > 40
                ? 3
                : 2
        const nextText = backlog.slice(0, batchSize).join('')
        displayedOffset += nextText.length
        updateDisplayedAnswer(receivedAnswer.slice(0, displayedOffset))
      }

      if (displayedOffset < receivedAnswer.length) {
        scheduleTyping()
      } else if (streamDoneData) {
        resolveTyping?.()
        resolveTyping = null
      }
    }, prefersReducedMotion ? 0 : 28)
  }

  const scheduleReasoning = () => {
    if (reasoningTimer !== null) return
    reasoningTimer = window.setTimeout(() => {
      reasoningTimer = null
      const displayedLength = pendingMessage.thinking.length
      const remaining = receivedReasoning.slice(displayedLength)
      if (!remaining) return
      const characters = Array.from(remaining)
      const batchSize = prefersReducedMotion
        ? characters.length
        : characters.length > 160 ? 8 : characters.length > 60 ? 4 : 2
      pendingMessage.thinking += characters.slice(0, batchSize).join('')
      followQaLatestAfterRender()
      if (pendingMessage.thinking.length < receivedReasoning.length) {
        scheduleReasoning()
      }
    }, prefersReducedMotion ? 0 : 28)
  }

  try {
    scrollQaToLatest()
    const handlers: AskStreamHandlers = {
      onTask: (data: any) => {
        currentAnswerTaskId.value = data.task_id
        rememberActiveTask(sessionId, data.task_id, normalizedQuestion)
      },
      onReasoningDelta: text => {
        receivedReasoning += text
        pendingMessage.thinkingStreaming = true
        pendingMessage.thinkingExpanded = true
        pendingMessage.status = '正在深度思考'
        scheduleReasoning()
      },
      onReasoningDone: () => {
        pendingMessage.thinkingStreaming = false
        window.setTimeout(() => {
          pendingMessage.thinkingExpanded = false
        }, prefersReducedMotion ? 0 : 220)
      },
      onStatus: data => {
        pendingMessage.status = data.message
      },
      onDelta: text => {
        receivedAnswer += text
        pendingMessage.status = '正在生成回答'
        scheduleTyping()
      },
      onCitations: items => {
        pendingCitations = items
      },
      onDone: data => {
        streamDoneData = data
        if (data.agent_trace) {
          pendingMessage.agentTrace = data.agent_trace
        }
        if (displayedOffset >= receivedAnswer.length) {
          resolveTyping?.()
          resolveTyping = null
        } else {
          scheduleTyping()
        }
      },
      onStopped: () => {
        streamStopped = true
        streamDoneData = { stopped: true }
        if (displayedOffset >= receivedAnswer.length) {
          resolveTyping?.()
          resolveTyping = null
        } else {
          scheduleTyping()
        }
      }
    }

    let reconnectAttempt = 0
    while (true) {
      try {
        if (resumeTaskId || reconnectAttempt > 0) {
          const taskId = currentAnswerTaskId.value || resumeTaskId
          await resumeAnswerTask(
            taskId,
            receivedAnswer.length,
            receivedReasoning.length,
            handlers,
            qaAbortController.signal
          )
        } else {
          await streamAskInSession(
            sessionId,
            normalizedQuestion,
            enableThinking,
            handlers,
            qaAbortController.signal
          )
        }
        break
      } catch (connectionError: any) {
        const canReconnect = currentAnswerTaskId.value
          && connectionError?.name !== 'AbortError'
          && connectionError?.retriable !== false
          && reconnectAttempt < 3
        if (!canReconnect) throw connectionError
        reconnectAttempt += 1
        pendingMessage.status = `网络中断，正在恢复连接（${reconnectAttempt}/3）`
        await new Promise(resolve => setTimeout(resolve, reconnectAttempt * 800))
      }
    }
    await typingComplete
    forgetActiveTask(sessionId)
    if (streamStopped) {
      pendingMessage.streaming = false
      pendingMessage.status = ''
      pendingMessage.streamError = '回答已停止'
      return
    }
    pendingMessage.citations = pendingCitations
    pendingMessage.id = streamDoneData.message_id
    pendingMessage.streaming = false
    pendingMessage.status = ''
    if (streamDoneData.follow_up_pending && streamDoneData.message_id) {
      void syncPendingQaMessage(sessionId, streamDoneData.message_id)
    }
    await loadSessions()
  } catch (error: any) {
    if (typingTimer !== null) window.clearTimeout(typingTimer)
    if (reasoningTimer !== null) window.clearTimeout(reasoningTimer)
    updateDisplayedAnswer(receivedAnswer)
    pendingMessage.thinking = receivedReasoning
    pendingMessage.thinkingStreaming = false
    pendingMessage.streaming = false
    pendingMessage.streamError = friendlyErrorMessage(error)
    pendingMessage.errorStage = answerStageLabel(error?.stage)
    if (error?.retriable === false) forgetActiveTask(sessionId)
    if (!question.value) question.value = normalizedQuestion
  } finally {
    qaAbortController = null
    currentAnswerTaskId.value = ''
    qaLoading.value = false
  }
}

const handleGenerateSummary = async () => {
  summaryLoading.value = true
  try {
    const response = await generateSummary(paperId)
    structuredSummary.value = response
    Message.success('摘要已更新')
  } catch {
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
  } catch {
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
  outlineCollapsed.value = window.innerWidth <= 1100
  window.addEventListener('resize', handleWindowResize)
  loadPaper()
  loadSections()
  loadSessions()
  loadSummaryCache()
  loadInterpretCache()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
  qaAbortController?.abort()
  if (readingProgressTimer !== null) window.clearTimeout(readingProgressTimer)
  void persistReadingProgress()
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
  box-shadow: var(--pa-shadow-sm);
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
.sidebar-resizer:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: -2px;
}

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

.qa-history-shell {
  flex: 1;
  min-height: 0;
  position: relative;
}

.qa-history {
  height: 100%;
  overflow-y: auto;
  overflow-anchor: none;
  padding: 14px 16px 20px;
  overscroll-behavior: contain;
}

.qa-scroll-latest {
  position: absolute;
  right: 16px;
  bottom: 12px;
  padding: 6px 11px;
  border: 1px solid var(--pa-border);
  border-radius: 16px;
  background: var(--pa-surface);
  box-shadow: 0 4px 14px rgba(29, 33, 41, 0.12);
  color: var(--pa-primary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.qa-scroll-latest:hover {
  border-color: var(--pa-primary);
  box-shadow: 0 5px 16px rgba(29, 33, 41, 0.16);
  transform: translateY(-1px);
}

.qa-scroll-latest:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.qa-scroll-latest:active {
  transform: translateY(0);
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

.qa-question {
  align-items: flex-start;
}

.qa-question-text {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.qa-more-button {
  display: inline-grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  margin: -3px -4px 0 4px;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pa-muted);
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  line-height: 1;
  transition: background-color 160ms ease, color 160ms ease;
}

.qa-more-button:hover {
  background: var(--pa-surface-soft);
  color: var(--pa-ink);
}

.qa-more-button:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 1px;
}

.qa-more-button:active {
  background: var(--pa-primary-soft);
}

.qa-more-button:disabled {
  cursor: wait;
  opacity: 0.45;
}

.qa-answer-content {
  flex: 1;
  min-width: 0;
}

.qa-thinking {
  margin-bottom: 9px;
  border: 1px solid var(--pa-border);
  border-radius: 7px;
  background: var(--pa-surface-soft);
}

.qa-thinking-header {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 7px 9px;
  border: 0;
  background: transparent;
  color: var(--pa-muted);
  cursor: pointer;
  font-size: 11px;
}

.qa-thinking-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--pa-text);
  font-weight: 600;
}

.qa-thinking-content {
  max-height: 220px;
  overflow: auto;
  padding: 0 9px 9px;
  color: var(--pa-text);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
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

.qa-stream-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--pa-muted);
  font-size: 13px;
  min-height: 28px;
}

.qa-stream-progress {
  margin-top: 5px;
  color: var(--pa-muted);
  font-size: 11px;
}

.qa-stream-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 8px;
  padding: 11px 12px;
  border: 1px solid #efb5aa;
  border-radius: 8px;
  background: #fff5f2;
  color: #71261c;
  font-size: 12px;
}

.qa-stream-error-icon {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 19px;
  height: 19px;
  margin-top: 1px;
  border-radius: 50%;
  background: #b73b2b;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.qa-stream-error-content {
  min-width: 0;
}

.qa-stream-error-content strong {
  display: block;
  font-size: 13px;
  line-height: 20px;
}

.qa-stream-error-content p {
  margin: 2px 0 8px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.qa-stream-error-content button {
  padding: 4px 9px;
  border: 1px solid #cf695b;
  border-radius: 5px;
  background: #fff;
  color: #8d2f23;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}

.qa-stream-error-content button:hover:not(:disabled) {
  border-color: #a7382a;
  background: #fffaf8;
}

.qa-stream-error-content button:focus-visible {
  outline: 2px solid #a7382a;
  outline-offset: 2px;
}

.qa-stream-error-content button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.qa-message-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.qa-message-actions button {
  padding: 2px 0;
  border: 0;
  background: transparent;
  color: var(--pa-muted);
  cursor: pointer;
  font-size: 11px;
}

.qa-message-actions button:hover {
  color: var(--pa-primary);
}

.qa-message-actions button:focus-visible {
  border-radius: 3px;
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.markdown-answer.streaming::after {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 3px;
  background: var(--pa-primary);
  content: '';
  vertical-align: -0.12em;
  animation: qa-cursor 0.9s steps(1) infinite;
}

@keyframes qa-cursor {
  50% { opacity: 0; }
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

.qa-input-options {
  display: flex;
  align-items: center;
  gap: 10px;
}

.qa-thinking-option {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--pa-text);
  font-size: 11px;
}

.qa-thinking-option :deep(.arco-switch) {
  min-width: 30px;
  background-color: oklch(0.72 0.018 50) !important;
  box-shadow: inset 0 0 0 1px oklch(0.58 0.02 50 / 0.35);
}

.qa-thinking-option :deep(.arco-switch-checked) {
  background-color: var(--pa-primary) !important;
  box-shadow: none;
}

.qa-thinking-option :deep(.arco-switch-handle) {
  background-color: white !important;
  box-shadow: 0 1px 3px oklch(0 0 0 / 0.22);
}

.qa-thinking-option :deep(.arco-switch:focus-visible) {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.qa-thinking-option button {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
}

.qa-thinking-option button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.qa-thinking-option button:focus-visible {
  border-radius: 3px;
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.qa-input-options > span {
  font-size: 11px;
  color: var(--pa-muted);
}

/* Agent 过程 */
.qa-agent-trace {
  margin-top: 10px;
  border: 1px solid oklch(0.88 0.03 250);
  border-radius: 8px;
  overflow: hidden;
}
.qa-agent-trace-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  background: var(--pa-info-soft);
  border: none;
  font-size: 12px;
  color: var(--pa-text-secondary);
  cursor: pointer;
  transition: background 0.15s;
}
.qa-agent-trace-header:hover {
  background: oklch(0.95 0.02 250);
}
.qa-agent-trace-title {
  font-weight: 600;
  color: var(--pa-text-primary);
}
.qa-agent-trace-summary {
  flex: 1;
  text-align: left;
  font-size: 11px;
  color: var(--pa-text-tertiary);
}
.qa-agent-trace-content {
  padding: 8px 10px;
  font-size: 12px;
}
.qa-agent-trace-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 6px;
  color: var(--pa-text-secondary);
}
.qa-agent-trace-tools {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.qa-agent-trace-tool {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.qa-agent-trace-tool.ok {
  background: oklch(0.95 0.03 145);
}
.qa-agent-trace-tool.fail {
  background: oklch(0.95 0.04 25);
}
.qa-agent-trace-tool-name {
  font-weight: 600;
  color: var(--pa-text-primary);
  white-space: nowrap;
}
.qa-agent-trace-tool-args {
  flex: 1;
  color: var(--pa-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}
.qa-agent-trace-tool-time {
  color: var(--pa-text-tertiary);
  white-space: nowrap;
}

/* 引用溯源 */
.research-save-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.qa-citations {
  margin-top: 10px;
  padding: 10px;
  background: var(--pa-info-soft);
  border-radius: 8px;
  border: 1px solid oklch(0.82 0.05 250);
}

.citation-row { position: relative; margin-bottom: 6px; }
.citation-row .citation-item { padding-right: 92px; }
.save-evidence-button { position: absolute; top: 8px; right: 8px; }

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
  display: block;
  width: 100%;
  text-align: start;
  color: inherit;
  background: var(--pa-surface);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid var(--pa-border);
}

.citation-item:focus-visible {
  outline: 2px solid var(--pa-info);
  outline-offset: 2px;
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

.citation-paper {
  max-width: min(320px, 48vw);
  overflow: hidden;
  color: var(--pa-ink);
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.mobile-workspace-nav { display: none; }

@media (max-width: 767px) {
  .paper-reader { height: 100dvh; }
  .top-actions { display: none; }
  .mobile-workspace-nav {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding: 6px 8px;
    border-bottom: 1px solid var(--pa-border);
    background: var(--pa-surface);
  }
  .mobile-workspace-nav button {
    min-height: 40px;
    border: 0;
    border-radius: 7px;
    background: transparent;
    color: var(--pa-muted);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .mobile-workspace-nav button.active {
    color: var(--pa-primary);
    background: var(--pa-primary-soft);
    font-weight: 600;
  }
  .mobile-workspace-nav button:focus-visible {
    outline: 2px solid var(--pa-primary);
    outline-offset: -2px;
  }
  .reader-outline,
  .pdf-viewer,
  .ai-sidebar {
    display: none !important;
  }
  .reader-outline.mobile-pane-active,
  .pdf-viewer.mobile-pane-active,
  .ai-sidebar.mobile-pane-active {
    display: flex !important;
    flex: 1 1 auto;
    width: 100% !important;
    min-width: 0 !important;
    border: 0;
  }
  .pdf-viewer.mobile-pane-active { display: block !important; }
  .sidebar-resizer { display: none; }
  .paper-title { font-size: 14px; }
}

@media (pointer: coarse) {
  .layout-option,
  .qa-more-button,
  .citation-toggle,
  .mobile-workspace-nav button {
    min-height: 44px;
  }
  .qa-more-button { min-width: 44px; }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-resizer::after,
  .citation-item,
  .qa-scroll-latest { transition: none; }

  .qa-scroll-latest:hover { transform: none; }
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

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
      <!-- 项目信息卡 -->
      <section class="project-info-card">
        <div class="info-row">
          <div class="info-block">
            <span class="info-label">研究主题</span>
            <p class="info-value">{{ project.research_topic }}</p>
          </div>
          <div class="info-block"><span class="info-label">项目资料</span><p class="info-value">{{ projectPapers.length }} 篇论文 · {{ artifacts.length }} 个产物</p></div>
          <div class="info-block">
            <span class="info-label">状态</span>
            <a-select
              :model-value="project.status"
              @update:model-value="(value) => onStatusChange(String(value))"
              size="small"
              style="width: 120px"
            >
              <a-option v-for="(label, key) in STATUS_LABELS" :key="key" :value="key">{{ label }}</a-option>
            </a-select>
          </div>
        </div>
        <div v-if="project.abstract" class="info-abstract">
          <span class="info-label">项目摘要</span>
          <p>{{ project.abstract }}</p>
        </div>
      </section>

      <section v-if="workflowStatus" class="research-workbench" aria-labelledby="workbench-title">
        <header class="workbench-heading"><div><h1 id="workbench-title">研究工作台</h1><p>选择你现在要解决的问题。三个区域可以独立使用，项目资料会在它们之间共享。</p></div><a-button type="primary" @click="enterChat">自由提问</a-button></header>
        <div class="workbench-areas">
          <article v-for="area in workbenchAreas" :key="area.key" :class="['workbench-area', `area-${area.key}`, { active: activeArea === area.key }]">
            <button type="button" class="area-open" @click="openArea(area.key)">
              <span class="area-status">{{ areaStatusLabel(area.status) }}</span>
              <h2>{{ area.label }}</h2><p>{{ area.description }}</p><strong>{{ area.summary }}</strong>
            </button>
            <a-button :type="activeArea === area.key ? 'primary' : 'secondary'" size="small" @click="openArea(area.key)">{{ area.primary_action }}</a-button>
          </article>
        </div>
        <nav class="shared-resources" aria-label="项目共享资料">
          <strong>共享资料</strong>
          <button v-for="item in resourceNavigation" :key="item.tab" type="button" :class="{ active: activeTab === item.tab }" @click="activeTab = item.tab"><span>{{ item.label }}</span><small>{{ item.count }}</small></button>
        </nav>
      </section>

      <div class="workbench-content">
        <section :class="['workspace-panel', { 'writing-mode': activeTab === 'paper-writing' }]" aria-label="当前研究工作区">
          <nav v-if="activeFunctionNavigation.length" class="function-navigation" aria-label="当前功能区工具">
            <button v-for="item in activeFunctionNavigation" :key="item.tab" type="button" :class="{ active: activeTab === item.tab }" @click="activeTab = item.tab">{{ item.label }}</button>
          </nav>
          <header class="workspace-panel-header"><div><span>{{ activeWorkspaceMeta.group }}</span><h2>{{ activeWorkspaceMeta.label }}</h2><p>{{ activeWorkspaceMeta.description }}</p></div><a-button type="primary" size="small" @click="enterChat(activeWorkspaceMeta.prompt)">在 Agent 中处理</a-button></header>
          <a-tabs v-model:active-key="activeTab" type="rounded" class="workspace-tabs">
        <a-tab-pane key="research-brief" title="研究任务书">
          <a-spin :loading="researchBriefLoading">
            <div v-if="!researchBrief" class="empty-tab research-map-empty">
              <h3>先把模糊兴趣变成可执行调研任务</h3>
              <p>让 Agent 区分已知背景、用户约束和待验证假设，并产出中英文关键词、检索式、纳入排除标准与选题评价准则。</p>
              <a-button type="primary" @click="enterChat('请澄清当前题材并保存研究任务书；明确已知背景、约束、未知项、检索式和纳入排除标准。')">和 Agent 澄清题材</a-button>
            </div>
            <article v-else class="research-map research-brief" aria-label="研究任务书">
              <header class="research-map-header">
                <div>
                  <span class="info-label">当前版本 v{{ researchBrief.version }}</span>
                  <h2>{{ researchBrief.title }}</h2>
                  <p><strong>{{ researchBriefContent.topic }}</strong></p>
                  <p>{{ researchBriefContent.objective }}</p>
                </div>
                <a-button size="small" @click="openArtifact(researchBrief)">查看完整产物</a-button>
              </header>
              <div v-if="researchBriefContent.seed_keywords.length" class="map-keywords">
                <a-tag v-for="keyword in researchBriefContent.seed_keywords" :key="keyword">{{ keyword }}</a-tag>
              </div>
              <div class="map-columns">
                <section class="map-section"><h3>已知背景</h3><ul class="brief-list"><li v-for="item in researchBriefContent.known_context" :key="item">{{ item }}</li></ul><p v-if="!researchBriefContent.known_context.length" class="map-muted">尚无用户确认的背景。</p></section>
                <section class="map-section"><h3>现实约束</h3><ul class="brief-list"><li v-for="item in researchBriefContent.constraints" :key="item">{{ item }}</li></ul><p v-if="!researchBriefContent.constraints.length" class="map-muted">尚未明确资源与时间约束。</p></section>
              </div>
              <section class="map-section"><h3>待确认与待验证</h3><ul class="brief-list"><li v-for="item in researchBriefContent.unknowns" :key="item">{{ item }}</li></ul><p v-if="!researchBriefContent.unknowns.length" class="map-muted">当前没有登记的未知项。</p></section>
              <section class="map-section"><h3>可执行检索式</h3><ol class="map-question-list"><li v-for="query in researchBriefContent.search_queries" :key="query"><code>{{ query }}</code></li></ol></section>
              <div class="map-columns">
                <section class="map-section"><h3>纳入标准</h3><ul class="brief-list"><li v-for="item in researchBriefContent.inclusion_criteria" :key="item">{{ item }}</li></ul></section>
                <section class="map-section"><h3>排除标准</h3><ul class="brief-list"><li v-for="item in researchBriefContent.exclusion_criteria" :key="item">{{ item }}</li></ul></section>
              </div>
              <section class="map-section"><h3>选题评价准则</h3><ul class="brief-list"><li v-for="item in researchBriefContent.evaluation_criteria" :key="item">{{ item }}</li></ul></section>
            </article>
          </a-spin>
        </a-tab-pane>

        <a-tab-pane key="literature-screening" title="候选文献">
          <TopicExplorer
            :project-id="projectId"
            :initial-query="project.research_topic"
            @imported="handleExternalImported"
          />
          <a-spin :loading="literatureScreeningLoading">
            <section v-if="literatureScreening" class="literature-screening saved-screening" aria-label="候选文献筛选台账">
              <header class="matrix-header">
                <div><span class="info-label">研究任务书 v{{ literatureScreeningContent.research_brief_version || '—' }}</span><h2>{{ literatureScreening.title }}</h2><p>{{ literatureScreeningContent.stopping_reason || '尚未说明检索停止条件。' }}</p></div>
                <a-button size="small" @click="openArtifact(literatureScreening)">查看完整产物</a-button>
              </header>
              <div class="screening-stats" aria-label="筛选统计">
                <span><strong>{{ literatureScreeningContent.included_count }}</strong> 纳入</span>
                <span><strong>{{ literatureScreeningContent.maybe_count }}</strong> 待定</span>
                <span><strong>{{ literatureScreeningContent.excluded_count }}</strong> 排除</span>
                <span><strong>{{ literatureScreeningContent.deduplicated_count }}</strong> 去重</span>
              </div>
              <section class="map-section"><h3>检索记录</h3><ul class="search-run-list"><li v-for="(run, index) in literatureScreeningContent.query_runs" :key="`${run.source}-${index}`"><span>{{ run.source }}</span><code>{{ run.query }}</code><strong>{{ run.result_count }} 条</strong></li></ul></section>
              <section class="map-section"><h3>候选论文</h3><div class="screening-list">
                <article v-for="(candidate, index) in literatureScreeningContent.candidates" :key="`${candidate.arxiv_id || candidate.doi || candidate.title}-${index}`" :class="`screening-item decision-${candidate.decision}`">
                  <div class="screening-item-head"><span>{{ screeningDecisionLabel(candidate.decision) }}</span><strong>{{ candidate.relevance_score }}/100</strong></div>
                  <h4>{{ candidate.title }}</h4><p>{{ candidate.reason }}</p>
                  <div class="candidate-meta"><span v-if="candidate.year">{{ candidate.year }}</span><span v-if="candidate.venue">{{ candidate.venue }}</span><span v-if="candidate.arxiv_id">arXiv:{{ candidate.arxiv_id }}</span><span v-else-if="candidate.doi">DOI:{{ candidate.doi }}</span></div>
                  <div v-if="candidate.coverage?.length" class="map-keywords"><a-tag v-for="item in candidate.coverage" :key="item">{{ item }}</a-tag></div>
                </article>
              </div></section>
              <section v-if="literatureScreeningContent.coverage_summary.length" class="map-section"><h3>覆盖度与缺口</h3><ul class="map-gap-list"><li v-for="(item, index) in literatureScreeningContent.coverage_summary" :key="index"><strong>{{ item.dimension || `维度 ${index + 1}` }}</strong><p>{{ item.count ?? 0 }} 篇候选<span v-if="item.gap"> · 缺口：{{ item.gap }}</span></p><p v-if="item.next_query">下一检索：<code>{{ item.next_query }}</code></p></li></ul></section>
            </section>
          </a-spin>
        </a-tab-pane>

        <!-- ===== 领域地图 ===== -->
        <a-tab-pane key="research-map" title="领域地图">
          <a-spin :loading="researchMapLoading">
            <div v-if="!researchMap" class="empty-tab research-map-empty">
              <h3>从项目文献形成选题依据</h3>
              <p>进入项目对话并提出“梳理领域地图并给出候选选题”。Agent 会交叉检索项目论文，保存研究问题、方法版图、研究空白和下一步验证动作。</p>
              <a-button type="primary" :disabled="projectPapers.length === 0" @click="enterChat">进入项目对话</a-button>
            </div>
            <article v-else class="research-map" aria-label="领域研究地图">
              <header class="research-map-header">
                <div>
                  <span class="info-label">当前版本 v{{ researchMap.version }}</span>
                  <h2>{{ researchMap.title }}</h2>
                  <p>{{ researchMapContent.topic_summary }}</p>
                </div>
                <a-button size="small" @click="openArtifact(researchMap)">查看完整产物</a-button>
              </header>

              <div v-if="researchMapContent.keywords.length" class="map-keywords" aria-label="检索关键词">
                <a-tag v-for="keyword in researchMapContent.keywords" :key="keyword">{{ keyword }}</a-tag>
              </div>

              <section class="map-section">
                <h3>研究问题</h3>
                <ol v-if="researchMapContent.research_questions.length" class="map-question-list">
                  <li v-for="(item, index) in researchMapContent.research_questions" :key="index">
                    <strong>{{ mapItemTitle(item, 'question', 'title') }}</strong>
                    <p v-if="item.importance">{{ item.importance }}</p>
                  </li>
                </ol>
                <p v-else class="map-muted">尚未形成研究问题。</p>
              </section>

              <div class="map-columns">
                <section class="map-section">
                  <h3>方法版图</h3>
                  <ul v-if="researchMapContent.method_families.length" class="map-compact-list">
                    <li v-for="(item, index) in researchMapContent.method_families" :key="index">
                      <strong>{{ mapItemTitle(item, 'name', 'method') }}</strong>
                      <span>{{ item.strengths || item.weaknesses || '待进一步比较' }}</span>
                    </li>
                  </ul>
                  <p v-else class="map-muted">尚无方法分类。</p>
                </section>
                <section class="map-section">
                  <h3>关键数据集</h3>
                  <ul v-if="researchMapContent.datasets.length" class="map-compact-list">
                    <li v-for="(item, index) in researchMapContent.datasets" :key="index">
                      <strong>{{ mapItemTitle(item, 'name', 'dataset') }}</strong>
                      <span>{{ item.task || item.limitations || '待补充适用任务' }}</span>
                    </li>
                  </ul>
                  <p v-else class="map-muted">尚无数据集归纳。</p>
                </section>
              </div>

              <section class="map-section map-gaps">
                <h3>研究空白与风险</h3>
                <ul v-if="researchMapContent.research_gaps.length" class="map-gap-list">
                  <li v-for="(item, index) in researchMapContent.research_gaps" :key="index">
                    <strong>{{ mapItemTitle(item, 'gap', 'title') }}</strong>
                    <p v-if="item.opportunity">机会：{{ item.opportunity }}</p>
                    <p v-if="item.risk">风险：{{ item.risk }}</p>
                  </li>
                </ul>
                <p v-else class="map-muted">现有证据尚不足以判断研究空白。</p>
              </section>

              <section class="map-section">
                <h3>候选选题</h3>
                <div v-if="researchMapContent.candidate_topics.length" class="candidate-topic-list">
                  <div v-for="(item, index) in researchMapContent.candidate_topics" :key="index" class="candidate-topic">
                    <span class="candidate-index">{{ index + 1 }}</span>
                    <div>
                      <strong>{{ mapItemTitle(item, 'title', 'question') }}</strong>
                      <p v-if="item.novelty">创新点：{{ item.novelty }}</p>
                      <p v-if="item.feasibility">可行性：{{ item.feasibility }}</p>
                      <p v-if="item.next_step">下一步：{{ item.next_step }}</p>
                    </div>
                  </div>
                </div>
                <p v-else class="map-muted">尚未生成候选选题。</p>
              </section>
            </article>
          </a-spin>
        </a-tab-pane>

        <!-- ===== 证据矩阵 ===== -->
        <a-tab-pane key="evidence-matrix" title="证据矩阵">
          <a-spin :loading="evidenceMatrixLoading">
            <div v-if="!evidenceMatrix" class="empty-tab research-map-empty">
              <h3>把精读结果变成可比较的证据</h3>
              <p>至少完成两篇论文卡片后，在项目对话中提出“生成跨论文证据矩阵”。矩阵会区分方法、数据集、指标、发现、局限、冲突结论和待补证据。</p>
              <a-button type="primary" :disabled="completedCardCount < 2" @click="enterChat">进入项目对话</a-button>
            </div>
            <section v-else class="evidence-matrix" aria-label="跨论文证据矩阵">
              <header class="matrix-header">
                <div>
                  <span class="info-label">来自 {{ evidenceMatrixContent.generated_from_cards }} 张论文卡片</span>
                  <h2>{{ evidenceMatrix.title }}</h2>
                  <p>{{ evidenceMatrixContent.research_question }}</p>
                </div>
                <a-button size="small" @click="openArtifact(evidenceMatrix)">查看完整产物</a-button>
              </header>
              <div class="matrix-table-wrap" tabindex="0" aria-label="证据矩阵，可横向滚动">
                <table class="matrix-table">
                  <thead><tr><th>论文</th><th>方法</th><th>数据集</th><th>指标</th><th>主要发现</th><th>局限</th></tr></thead>
                  <tbody>
                    <tr v-for="row in evidenceMatrixContent.rows" :key="row.paper_id">
                      <th scope="row"><button type="button" @click="openPaper(row.paper_id)">{{ row.paper_title }}</button></th>
                      <td>{{ matrixCell(row.methods) }}</td><td>{{ matrixCell(row.datasets) }}</td><td>{{ matrixCell(row.metrics) }}</td>
                      <td>{{ matrixCell(row.findings) }}</td><td>{{ matrixCell(row.limitations) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="matrix-insights">
                <section>
                  <h3>冲突结论</h3>
                  <ul v-if="evidenceMatrixContent.conflicts.length">
                    <li v-for="(item, index) in evidenceMatrixContent.conflicts" :key="index">
                      <strong>{{ item.explanation || item.claim_a || '待核对冲突' }}</strong>
                      <span v-if="item.source_ids?.length">来源 {{ item.source_ids.join('、') }}</span>
                    </li>
                  </ul>
                  <p v-else class="map-muted">尚未发现有来源支持的冲突结论。</p>
                </section>
                <section>
                  <h3>证据缺口</h3>
                  <ul v-if="evidenceMatrixContent.evidence_gaps.length">
                    <li v-for="(item, index) in evidenceMatrixContent.evidence_gaps" :key="index">
                      <strong>{{ item.dimension || '未分类缺口' }}</strong>
                      <span>{{ item.missing_evidence || item.next_action || '需要继续补证' }}</span>
                    </li>
                  </ul>
                  <p v-else class="map-muted">当前未记录证据缺口。</p>
                </section>
              </div>
            </section>
          </a-spin>
        </a-tab-pane>

        <!-- ===== 实验设计 ===== -->
        <a-tab-pane key="experiment-design" title="实验设计">
          <a-spin :loading="experimentDesignLoading">
            <div v-if="!experimentDesign" class="empty-tab research-map-empty">
              <h3>用证据约束研究假设</h3>
              <p>先生成证据矩阵，再让 Agent 设计可证伪假设、变量、基线、评价指标、消融实验以及成功和失败判据。</p>
              <a-button type="primary" :disabled="!evidenceMatrix" @click="enterChat">进入项目对话</a-button>
            </div>
            <article v-else class="experiment-design">
              <header class="matrix-header">
                <div><span class="info-label">研究设计</span><h2>{{ experimentDesign.title }}</h2></div>
                <a-button size="small" @click="openArtifact(experimentDesign)">查看完整产物</a-button>
              </header>
              <section class="hypothesis-block">
                <span>研究问题</span><p>{{ experimentDesignContent.research_question }}</p>
                <span>可证伪假设</span><h3>{{ experimentDesignContent.hypothesis }}</h3>
                <p>{{ experimentDesignContent.rationale }}</p>
              </section>
              <div class="design-columns">
                <section><h3>变量与控制</h3><dl>
                  <dt>自变量</dt><dd>{{ matrixCell(experimentDesignContent.independent_variables) }}</dd>
                  <dt>因变量</dt><dd>{{ matrixCell(experimentDesignContent.dependent_variables) }}</dd>
                  <dt>控制项</dt><dd>{{ matrixCell(experimentDesignContent.controls) }}</dd>
                </dl></section>
                <section><h3>实验步骤</h3><ol><li v-for="step in experimentDesignContent.experiment_steps" :key="step">{{ step }}</li></ol></section>
              </div>
              <div class="criteria-grid">
                <section><h3>成功判据</h3><ul><li v-for="item in experimentDesignContent.success_criteria" :key="item">{{ item }}</li></ul></section>
                <section><h3>证伪判据</h3><ul><li v-for="item in experimentDesignContent.falsification_criteria" :key="item">{{ item }}</li></ul></section>
              </div>
              <section v-if="experimentDesignContent.requires_empirical_results" class="experiment-results-panel">
                <header>
                  <div><span class="info-label">真实结果关口</span><h3>{{ experimentResults ? '结果已登记' : '等待实验输出' }}</h3></div>
                  <a-button v-if="experimentResults" size="small" @click="openArtifact(experimentResults)">查看完整结果</a-button>
                  <a-button v-else type="primary" size="small" @click="enterChat('我将提供真实实验输出，请根据来源登记指标和运行信息；不要预测或编造任何数值。')">登记真实结果</a-button>
                </header>
                <p v-if="!experimentResults" class="map-muted">论文蓝图和结果章节不会越过此关口。请提供实际文件、实验追踪记录、数据库导出或明确的人工报告。</p>
                <template v-else>
                  <div class="result-summary">
                    <span>运行标识<strong>{{ experimentResultsContent.run_id }}</strong></span>
                    <span>假设结论<strong>{{ hypothesisOutcomeLabel(experimentResultsContent.hypothesis_outcome) }}</strong></span>
                    <span>来源<strong>{{ experimentResultsContent.sources.length }}</strong></span>
                    <span>指标<strong>{{ experimentResultsContent.metrics.length }}</strong></span>
                  </div>
                  <div v-if="experimentResultsContent.metrics.length" class="matrix-table-wrap" tabindex="0" aria-label="实验指标，可横向滚动">
                    <table class="matrix-table result-table"><thead><tr><th>方法</th><th>数据集/划分</th><th>指标</th><th>数值</th><th>不确定性</th><th>来源</th></tr></thead><tbody>
                      <tr v-for="(metric, index) in experimentResultsContent.metrics" :key="`${metric.metric}-${index}`"><td>{{ metric.method || metric.baseline || '—' }}</td><td>{{ [metric.dataset, metric.split].filter(Boolean).join('/') || '—' }}</td><td>{{ metric.metric }}</td><td><strong>{{ metric.value }} {{ metric.unit || '' }}</strong></td><td>{{ metric.uncertainty || '—' }}</td><td>{{ metric.source_id }}</td></tr>
                    </tbody></table>
                  </div>
                  <div class="design-columns">
                    <section><h3>结果来源</h3><ul class="brief-list"><li v-for="source in experimentResultsContent.sources" :key="source.source_id"><strong>[{{ source.source_id }}]</strong> {{ source.source_type }} · {{ source.locator }}<small v-if="source.checksum">SHA-256：{{ source.checksum }}</small></li></ul></section>
                    <section><h3>相对设计的偏差</h3><ul v-if="experimentResultsContent.protocol_deviations.length" class="brief-list"><li v-for="item in experimentResultsContent.protocol_deviations" :key="item">{{ item }}</li></ul><p v-else class="map-muted">未登记协议偏差。</p></section>
                  </div>
                </template>
              </section>
              <section v-else class="non-empirical-note"><strong>非实证研究</strong><span>当前设计明确不要求新实验结果，可以直接进入论文蓝图。</span></section>
            </article>
          </a-spin>
        </a-tab-pane>

        <!-- ===== 论文写作 ===== -->
        <a-tab-pane key="paper-writing" title="论文写作">
          <WritingStudio :project-id="projectId" :papers="projectPapers" @saved="loadArtifacts" />
          <details v-if="paperBlueprint || fullDraft || reviewReport || finalManuscript" class="advanced-writing-state">
            <summary>论文蓝图、审计与导出</summary>
            <a-spin :loading="paperBlueprintLoading">
            <article v-if="paperBlueprint" class="paper-writing">
              <header class="matrix-header">
                <div><span class="info-label">论文蓝图</span><h2>{{ paperBlueprintContent.working_title }}</h2><p>{{ paperBlueprintContent.central_claim }}</p></div>
                <a-button size="small" @click="openArtifact(paperBlueprint)">查看完整蓝图</a-button>
              </header>
              <ol class="blueprint-sections">
                <li v-for="section in paperBlueprintContent.sections" :key="section.section_id">
                  <span class="candidate-index">{{ section.order }}</span>
                  <div class="blueprint-main">
                    <div class="blueprint-title-row">
                      <h3>{{ section.title }}</h3>
                      <span class="reading-status" :class="`status-${sectionDraftStatus(section.section_id)}`">{{ sectionDraftStatusLabel(section.section_id) }}</span>
                    </div>
                    <p>{{ section.purpose }}</p>
                    <div class="blueprint-meta">
                      <span>目标 {{ section.word_target }} 字</span>
                      <span>主张 {{ section.key_claims?.length || 0 }}</span>
                      <span>证据 {{ section.evidence_refs?.length || 0 }}</span>
                      <span>待引文 {{ section.citation_needs?.length || 0 }}</span>
                      <span v-if="sectionDraft(section.section_id)?.meta?.unresolved_items?.length" class="unresolved-count">
                        未解决 {{ sectionDraft(section.section_id)?.meta?.unresolved_items?.length }}
                      </span>
                    </div>
                  </div>
                  <a-button v-if="sectionDraft(section.section_id)" size="small" @click="openSectionDraft(section.section_id)">查看草稿</a-button>
                </li>
              </ol>
              <section v-if="fullDraft || reviewReport || finalManuscript" class="refinement-summary" aria-label="全文审校状态">
                <header>
                  <div><h3>全文审校</h3><p>全文必须通过阻断项检查后才能定稿。</p></div>
                  <a-button v-if="fullDraft && !reviewReport" size="small" @click="enterChat">开始全文审计</a-button>
                </header>
                <div class="refinement-flow">
                  <button class="refinement-step" :class="{ ready: !!fullDraft }" :disabled="!fullDraft" @click="fullDraft && openArtifact(fullDraft)">
                    <span>完整草稿</span><strong>{{ fullDraft ? '已组装' : '未组装' }}</strong>
                  </button>
                  <button class="refinement-step" :class="{ ready: !!reviewReport, blocked: reviewCounts.blocker > 0 }" :disabled="!reviewReport" @click="reviewReport && openArtifact(reviewReport)">
                    <span>审计报告</span><strong v-if="reviewReport">阻断 {{ reviewCounts.blocker }} · 重要 {{ reviewCounts.major }}</strong><strong v-else>待审计</strong>
                  </button>
                  <button class="refinement-step" :class="{ ready: !!finalManuscript }" :disabled="!finalManuscript" @click="finalManuscript && openArtifact(finalManuscript)">
                    <span>论文终稿</span><strong>{{ finalManuscript ? '可下载' : '未定稿' }}</strong>
                  </button>
                </div>
                <p v-if="reviewReport && reviewCounts.blocker > 0" class="audit-guidance">请在项目对话中按审计报告定向修订对应章节，然后重新组装并审计。</p>
                <div v-if="finalManuscript" class="submission-actions" aria-label="终稿导出">
                  <span>导出终稿</span>
                  <a-button size="small" :loading="exportLoading === 'md'" @click="downloadFinal('md')">下载 Markdown</a-button>
                  <a-button size="small" :loading="exportLoading === 'tex'" @click="downloadFinal('tex')">下载 LaTeX</a-button>
                  <a-button size="small" :loading="exportLoading === 'docx'" @click="downloadFinal('docx')">下载 Word</a-button>
                  <a-button type="primary" size="small" :loading="exportLoading === 'zip'" @click="downloadFinal('zip')">下载投稿包</a-button>
                </div>
              </section>
            </article>
            </a-spin>
          </details>
        </a-tab-pane>

        <!-- ===== 文档库 ===== -->
        <a-tab-pane key="papers" title="文档库">
          <div class="tab-toolbar">
            <a-input
              v-model="paperSearch"
              placeholder="搜索项目中的论文"
              allow-clear
              style="max-width: 280px"
            />
            <div class="toolbar-actions">
              <a-button
                v-if="readingExecution?.status === 'running' || readingExecution?.status === 'queued'"
                @click="pauseExecution"
              >暂停精读</a-button>
              <a-button
                v-else-if="readingExecution?.status === 'paused' || readingExecution?.status === 'failed'"
                type="primary"
                @click="resumeExecution"
              >{{ readingExecution.status === 'failed' ? '重试精读' : '继续精读' }}</a-button>
              <a-button v-else type="primary" :loading="executionLoading" @click="startExecution">自动精读</a-button>
              <a-button @click="showAddPaperModal = true">从论文库加入</a-button>
            </div>
          </div>
          <div v-if="readingExecution" class="execution-status" role="status" aria-live="polite">
            <div>
              <strong>{{ executionStatusLabel(readingExecution.status) }}</strong>
              <span>{{ readingExecution.completed }}/{{ readingExecution.total }}</span>
              <span v-if="readingExecution.current_paper_title">正在精读：{{ readingExecution.current_paper_title }}</span>
            </div>
            <a-progress
              :percent="readingExecution.total ? readingExecution.completed / readingExecution.total : 0"
              :show-text="false"
              size="small"
            />
            <p v-if="readingExecution.error" class="execution-error">{{ readingExecution.error }}</p>
          </div>
          <a-spin :loading="papersLoading">
            <div v-if="!papersLoading && projectPapers.length === 0" class="empty-tab">
              <p>项目文档库为空。从论文库中加入文献,开始你的调研。</p>
            </div>
            <div v-else-if="filteredPapers.length === 0" class="empty-tab">
              <p>没有匹配当前搜索条件的项目论文。</p>
            </div>
            <ul v-else class="paper-list">
              <li v-for="pp in filteredPapers" :key="pp.id" class="paper-item">
                <div class="paper-main">
                  <div class="paper-title-row">
                    <span v-if="pp.reading_plan?.order" class="reading-order">{{ pp.reading_plan.order }}</span>
                    <span class="role-tag" :class="`role-${pp.role}`">{{ roleLabel(pp.role) }}</span>
                    <span v-if="pp.reading_plan?.status" class="reading-status" :class="`status-${pp.reading_plan.status}`">
                      {{ readingStatusLabel(pp.reading_plan.status) }}
                    </span>
                    <h4 @click="openPaper(pp.paper_id)">{{ pp.paper?.title }}</h4>
                    <span v-if="pp.paper?.publication_year" class="paper-year">{{ pp.paper.publication_year }}</span>
                  </div>
                  <p v-if="pp.paper?.authors" class="paper-authors">{{ pp.paper.authors }}</p>
                  <div v-if="pp.tags?.length" class="paper-tags">
                    <a-tag v-for="t in pp.tags" :key="t" size="small">{{ t }}</a-tag>
                  </div>
                  <p v-if="pp.notes" class="paper-notes">{{ pp.notes }}</p>
                  <div v-if="pp.reading_plan?.reason" class="reading-plan-summary">
                    <p><strong>阅读理由：</strong>{{ pp.reading_plan.reason }}</p>
                    <p v-if="pp.reading_plan.focus?.length"><strong>阅读重点：</strong>{{ pp.reading_plan.focus.join('；') }}</p>
                    <p v-if="pp.reading_plan.questions?.length"><strong>读后回答：</strong>{{ pp.reading_plan.questions.join('；') }}</p>
                  </div>
                  <details v-if="pp.analysis_card?.summary" class="paper-card-summary">
                    <summary>查看论文卡片</summary>
                    <p>{{ pp.analysis_card.summary }}</p>
                    <div class="paper-card-facts">
                      <span v-if="pp.analysis_card.methods?.length">方法 {{ pp.analysis_card.methods.length }}</span>
                      <span v-if="pp.analysis_card.datasets?.length">数据集 {{ pp.analysis_card.datasets.length }}</span>
                      <span v-if="pp.analysis_card.findings?.length">发现 {{ pp.analysis_card.findings.length }}</span>
                      <span v-if="pp.analysis_card.evidence?.length">证据 {{ pp.analysis_card.evidence.length }}</span>
                    </div>
                  </details>
                </div>
                <div class="paper-actions">
                  <a-select
                    v-if="pp.reading_plan?.order"
                    :model-value="pp.reading_plan.status || 'pending'"
                    size="small"
                    style="width: 104px"
                    aria-label="阅读状态"
                    @update:model-value="(value) => updatePaperStatus(pp, String(value))"
                  >
                    <a-option value="pending">待阅读</a-option>
                    <a-option value="reading">精读中</a-option>
                    <a-option value="completed">已完成</a-option>
                    <a-option value="skipped">已跳过</a-option>
                  </a-select>
                  <a-select
                    :model-value="pp.reading_priority"
                    size="small"
                    style="width: 90px"
                    @update:model-value="(value) => updatePaperPriority(pp, Number(value))"
                  >
                    <a-option :value="5">P5 必读</a-option>
                    <a-option :value="4">P4 优先</a-option>
                    <a-option :value="3">P3</a-option>
                    <a-option :value="2">P2</a-option>
                    <a-option :value="1">P1 可选</a-option>
                  </a-select>
                  <a-button size="small" status="danger" @click="confirmRemovePaper(pp)">移除论文</a-button>
                </div>
              </li>
            </ul>
          </a-spin>
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

        <!-- ===== 长期记忆 ===== -->
        <a-tab-pane key="memory" title="长期记忆">
          <div class="tab-toolbar">
            <span class="tab-hint">{{ memory.notes.length }} 条记忆要点 · {{ memory.summary ? '已有摘要' : '尚无摘要' }}</span>
            <a-button @click="showAddNoteModal = true">手动添加笔记</a-button>
          </div>
          <a-spin :loading="memoryLoading">
            <div v-if="memory.summary" class="memory-summary">
              <h4>摘要</h4>
              <p>{{ memory.summary }}</p>
            </div>
            <div v-if="!memoryLoading && memory.notes.length === 0" class="empty-tab">
              <p>项目记忆为空。在项目对话里让 agent 记录调研要点,或手动添加笔记。</p>
            </div>
            <ul v-else class="memory-list">
              <li v-for="(n, idx) in memory.notes" :key="idx" class="memory-note">
                <span v-if="n.tag" class="memory-tag" :class="`tag-${n.tag}`">{{ n.tag }}</span>
                <p class="memory-text">{{ n.text }}</p>
                <div class="memory-source">
                  <button
                    v-if="n.paper_id"
                    type="button"
                    class="memory-paper-link"
                    @click="openPaper(n.paper_id)"
                  >
                    {{ n.paper_title || '来源论文' }}<template v-if="n.page"> · p.{{ n.page }}</template>
                  </button>
                  <span class="memory-time">{{ formatTime(n.time) }}</span>
                </div>
              </li>
            </ul>
          </a-spin>
        </a-tab-pane>
          </a-tabs>
        </section>
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

    <!-- 添加记忆笔记 Modal -->
    <a-modal v-model:visible="showAddNoteModal" title="添加记忆笔记" @ok="confirmAddNote" :ok-loading="addingNote">
      <a-form :model="noteForm" layout="vertical">
        <a-form-item label="标签(可选)">
          <a-select v-model="noteForm.tag" placeholder="选择标签" allow-create allow-search>
            <a-option value="finding">finding(发现)</a-option>
            <a-option value="method">method(方法)</a-option>
            <a-option value="conclusion">conclusion(结论)</a-option>
            <a-option value="todo">todo(待办)</a-option>
            <a-option value="risk">risk(风险)</a-option>
            <a-option value="preference">preference(偏好)</a-option>
            <a-option value="decision">decision(决策)</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="笔记内容" required>
          <a-textarea v-model="noteForm.text" :auto-size="{ minRows: 3, maxRows: 8 }" placeholder="一句话记录要点" />
        </a-form-item>
      </a-form>
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
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import ProductHeader from '@/components/ProductHeader.vue'
import TopicExplorer from '@/components/project/TopicExplorer.vue'
import WritingStudio from '@/components/project/WritingStudio.vue'
import {
  getProject,
  getProjectWorkflowStatus,
  updateProject,
  deleteProject,
  listProjectPapers,
  addProjectPaper,
  updateProjectPaper,
  removeProjectPaper,
  listArtifacts,
  getArtifact,
  downloadArtifactExport,
  getProjectMemory,
  appendProjectMemoryNote,
  createProjectSession,
  startReadingExecution,
  getReadingExecution,
  pauseReadingExecution,
  resumeReadingExecution,
  STATUS_LABELS,
  PAPER_ROLE_LABELS,
  ARTIFACT_TYPE_LABELS,
  type ResearchProject,
  type ProjectPaperItem,
  type WritingArtifactItem,
  type ProjectMemoryNote,
  type ResearchBriefContent,
  type LiteratureScreeningContent,
  type ResearchMapContent,
  type EvidenceMatrixContent,
  type ExperimentDesignContent,
  type ExperimentResultsContent,
  type PaperBlueprintContent,
  type ReviewReportContent,
  type ReadingExecution,
  type ProjectWorkflowStatus,
} from '@/api/projects'
import { getPaperList } from '@/api/paper'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => String(route.params.id || ''))
const executionStorageKey = computed(() => `paperai:reading-execution:${projectId.value}`)

const project = ref<ResearchProject | null>(null)
const loading = ref(false)
const activeTab = ref('research-brief')
const enteringChat = ref(false)
const workflowStatus = ref<ProjectWorkflowStatus | null>(null)

const AREA_TAB = { topic: 'research-brief', reading: 'papers', writing: 'paper-writing' } as const
const applyRequestedArea = () => {
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
  memory: { group: '项目资源', label: '长期研究记忆', description: '保留跨会话的发现、判断、决策、偏好和待办。', prompt: '请整理当前项目长期记忆，区分已确认结论、研究决策、风险和下一步待办。' },
}

// 文档库
const projectPapers = ref<ProjectPaperItem[]>([])
const papersLoading = ref(false)
const paperSearch = ref('')
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

// 记忆
const memory = ref<{ summary: string; notes: ProjectMemoryNote[] }>({ summary: '', notes: [] })
const memoryLoading = ref(false)
const showAddNoteModal = ref(false)
const addingNote = ref(false)
const noteForm = ref({ tag: '', text: '' })

const filteredPapers = computed(() => {
  const ordered = [...projectPapers.value].sort((a, b) => {
    const aOrder = a.reading_plan?.order ?? Number.MAX_SAFE_INTEGER
    const bOrder = b.reading_plan?.order ?? Number.MAX_SAFE_INTEGER
    return aOrder - bOrder || b.reading_priority - a.reading_priority
  })
  if (!paperSearch.value) return ordered
  const q = paperSearch.value.toLowerCase()
  return ordered.filter(pp => {
    const t = pp.paper?.title || ''
    const a = pp.paper?.authors || ''
    return t.toLowerCase().includes(q) || a.toLowerCase().includes(q)
  })
})
const workbenchAreas = computed(() => workflowStatus.value?.areas || [])
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
  { tab: 'memory', icon: '⌁', label: '长期记忆', count: memory.value.notes.length },
])
const activeWorkspaceMeta = computed(() => WORKSPACE_META[activeTab.value] || WORKSPACE_META['research-brief'])

const openArea = (area: 'topic' | 'reading' | 'writing') => {
  activeTab.value = AREA_TAB[area]
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  requestAnimationFrame(() => document.querySelector('.workspace-panel')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' }))
}
const areaStatusLabel = (status: 'empty' | 'active' | 'ready') => ({ empty: '尚未开始', active: '已有内容', ready: '可继续使用' }[status])

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

const sectionDraft = (sectionId: string) => artifacts.value.find(item =>
  item.artifact_type === 'section_draft' && item.parent_id === paperBlueprint.value?.id && item.meta?.section_id === sectionId
)
const sectionDraftStatus = (sectionId: string) => {
  const draft = sectionDraft(sectionId)
  if (!draft) return 'pending'
  return draft.meta?.unresolved_items?.length ? 'failed' : 'completed'
}
const sectionDraftStatusLabel = (sectionId: string) => {
  const status = sectionDraftStatus(sectionId)
  return status === 'completed' ? '草稿完成' : status === 'failed' ? '待修订' : '未开始'
}

const matrixCell = (values?: string[]) => values?.length ? values.join('；') : '未报告'
const screeningDecisionLabel = (decision: 'include' | 'exclude' | 'maybe') => ({ include: '纳入', exclude: '排除', maybe: '待定' })[decision]
const hypothesisOutcomeLabel = (outcome: ExperimentResultsContent['hypothesis_outcome']) => ({ supported: '支持', not_supported: '不支持', mixed: '部分支持', inconclusive: '证据不足' })[outcome]

const mapItemTitle = (item: Record<string, any>, ...keys: string[]) => {
  for (const key of keys) {
    if (item?.[key]) return String(item[key])
  }
  return '待补充'
}

const filteredPaperLib = computed(() => {
  if (!paperLibSearch.value) return paperLib.value
  const q = paperLibSearch.value.toLowerCase()
  return paperLib.value.filter(p =>
    (p.title || '').toLowerCase().includes(q) || (p.authors || '').toLowerCase().includes(q)
  )
})

const roleLabel = (r: string) => PAPER_ROLE_LABELS[r] || r
const artifactTypeLabel = (t: string) => ARTIFACT_TYPE_LABELS[t] || t
const readingStatusLabel = (status: string) => ({
  pending: '待阅读',
  reading: '精读中',
  completed: '已完成',
  skipped: '已跳过',
  failed: '执行失败',
}[status] || status)
const executionStatusLabel = (status: string) => ({
  queued: '等待执行', running: '自动精读中', paused: '已暂停', completed: '精读完成', failed: '精读失败',
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

const loadMemory = async () => {
  memoryLoading.value = true
  try {
    const res = await getProjectMemory(projectId.value)
    memory.value = { summary: res.summary, notes: res.notes || [] }
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载记忆失败')
  } finally {
    memoryLoading.value = false
  }
}

const loadAll = async () => {
  await Promise.all([loadProject(), loadPapers(), loadArtifacts(), loadMemory(), loadWorkflowStatus()])
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
  router.push({ name: 'PaperReader', params: { id: paperId } })
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
  const draft = sectionDraft(sectionId)
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

const confirmAddNote = async () => {
  if (!noteForm.value.text.trim()) {
    Message.warning('笔记内容必填')
    return
  }
  addingNote.value = true
  try {
    await appendProjectMemoryNote(projectId.value, {
      text: noteForm.value.text.trim(),
      tag: noteForm.value.tag || '',
    })
    Message.success('笔记已添加')
    showAddNoteModal.value = false
    noteForm.value = { tag: '', text: '' }
    await loadMemory()
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '添加失败')
  } finally {
    addingNote.value = false
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
watch(() => route.query.area, applyRequestedArea)
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
.workbench-content { min-width: 0; }
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
.research-map-empty { max-width: 680px; margin: 0 auto; }
.research-map-empty h3 { margin: 0 0 8px; color: var(--pa-text); font-size: 20px; }
.research-map-empty p { max-width: 65ch; margin: 0 0 20px; line-height: 1.7; }
.research-map { display: flex; flex-direction: column; gap: 24px; }
.research-map-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--color-border-2);
}
.research-map-header h2 { margin: 4px 0 8px; color: var(--pa-text); font-size: 24px; text-wrap: balance; }
.research-map-header p { max-width: 72ch; margin: 0; color: var(--pa-muted); line-height: 1.7; text-wrap: pretty; }
.map-keywords { display: flex; flex-wrap: wrap; gap: 8px; }
.map-section { min-width: 0; }
.map-section h3 { margin: 0 0 12px; color: var(--pa-text); font-size: 17px; }
.map-question-list { display: grid; gap: 8px; margin: 0; padding-left: 24px; }
.map-question-list li { padding: 10px 12px; border-bottom: 1px solid var(--color-border-2); }
.map-question-list p,
.map-gap-list p,
.candidate-topic p { margin: 4px 0 0; color: var(--pa-muted); line-height: 1.55; }
.map-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }
.map-compact-list,
.map-gap-list { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.map-compact-list li { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: var(--color-fill-1); border-radius: 8px; }
.map-compact-list span { color: var(--pa-muted); line-height: 1.5; }
.map-gap-list li { padding: 14px 16px; border: 1px solid var(--color-border-2); border-radius: 8px; }
.candidate-topic-list { display: grid; gap: 12px; }
.candidate-topic { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 12px; align-items: start; }
.candidate-index {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-light-1);
  color: var(--pa-primary);
  font-weight: 700;
}
.map-muted { color: var(--pa-muted); }
.brief-list { margin: 0; padding-left: 22px; line-height: 1.7; }
.research-brief code { white-space: normal; overflow-wrap: anywhere; color: var(--pa-text); }
.literature-screening { display: flex; flex-direction: column; gap: 24px; }
.screening-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.screening-stats span { padding: 14px; border: 1px solid var(--pa-border); border-radius: 8px; color: var(--pa-muted); }
.screening-stats strong { display: block; color: var(--pa-text); font-size: 22px; }
.search-run-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.search-run-list li { display: grid; grid-template-columns: 120px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding: 10px 12px; background: var(--pa-surface-soft); border-radius: 8px; }
.search-run-list code { overflow-wrap: anywhere; white-space: normal; }
.screening-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.screening-item { padding: 16px; border: 1px solid var(--pa-border); border-radius: 8px; }
.screening-item.decision-include { border-color: oklch(0.75 0.07 145); background: oklch(0.98 0.012 145); }
.screening-item.decision-exclude { border-color: oklch(0.78 0.07 28); background: oklch(0.98 0.012 28); }
.screening-item.decision-maybe { border-color: oklch(0.80 0.07 80); background: oklch(0.98 0.014 80); }
.screening-item-head { display: flex; justify-content: space-between; color: var(--pa-muted); font-size: 12px; }
.screening-item h4 { margin: 8px 0; font-size: 16px; line-height: 1.45; }
.screening-item p { margin: 0 0 10px; color: var(--pa-muted); line-height: 1.55; }
.candidate-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-bottom: 10px; color: var(--pa-muted); font-size: 12px; }
.evidence-matrix { display: flex; flex-direction: column; gap: 24px; }
.matrix-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
.matrix-header h2 { margin: 4px 0 8px; color: var(--pa-text); font-size: 22px; }
.matrix-header p { margin: 0; color: var(--pa-muted); line-height: 1.6; }
.matrix-table-wrap { overflow-x: auto; border: 1px solid var(--color-border-2); border-radius: 8px; }
.matrix-table-wrap:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.matrix-table { width: 100%; min-width: 960px; border-collapse: collapse; font-size: 13px; }
.matrix-table th,
.matrix-table td { padding: 12px; border-bottom: 1px solid var(--color-border-2); text-align: left; vertical-align: top; line-height: 1.5; }
.matrix-table thead th { position: sticky; top: 0; background: var(--color-fill-1); color: var(--pa-text); font-weight: 600; }
.matrix-table tbody th { min-width: 180px; background: var(--color-bg-2); }
.matrix-table button { padding: 0; border: 0; background: none; color: var(--pa-primary); text-align: left; cursor: pointer; font: inherit; font-weight: 600; }
.matrix-table button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.matrix-insights { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }
.matrix-insights h3 { margin: 0 0 12px; font-size: 17px; }
.matrix-insights ul { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.matrix-insights li { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid var(--color-border-2); border-radius: 8px; }
.matrix-insights span { color: var(--pa-muted); font-size: 13px; }
.experiment-design { display: flex; flex-direction: column; gap: 24px; }
.hypothesis-block { padding: 20px; border: 1px solid var(--color-border-2); border-radius: 8px; background: var(--color-bg-2); }
.hypothesis-block span { display: block; margin-bottom: 4px; color: var(--pa-muted); font-size: 12px; }
.hypothesis-block h3 { margin: 4px 0 12px; color: var(--pa-text); font-size: 19px; text-wrap: balance; }
.hypothesis-block p { max-width: 72ch; margin: 0 0 16px; line-height: 1.65; }
.design-columns,
.criteria-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }
.design-columns section,
.criteria-grid section { min-width: 0; }
.design-columns h3,
.criteria-grid h3 { margin: 0 0 12px; font-size: 17px; }
.design-columns dl { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px 12px; margin: 0; }
.design-columns dt { color: var(--pa-muted); }
.design-columns dd { margin: 0; color: var(--pa-text); }
.design-columns ol,
.criteria-grid ul { margin: 0; padding-left: 22px; line-height: 1.65; }
.criteria-grid section { padding: 16px; border: 1px solid var(--color-border-2); border-radius: 8px; }
.experiment-results-panel { display: flex; flex-direction: column; gap: 16px; padding: 20px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface-soft); }
.experiment-results-panel > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.experiment-results-panel h3 { margin: 3px 0 0; font-size: 19px; }
.result-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.result-summary span { padding: 12px; border-radius: 8px; background: var(--pa-surface); color: var(--pa-muted); font-size: 12px; }
.result-summary strong { display: block; margin-top: 4px; color: var(--pa-text); font-size: 15px; overflow-wrap: anywhere; }
.result-table { min-width: 780px; }
.experiment-results-panel small { display: block; margin-top: 3px; color: var(--pa-muted); overflow-wrap: anywhere; }
.non-empirical-note { display: flex; gap: 10px; padding: 14px 16px; border-radius: 8px; background: var(--pa-surface-soft); color: var(--pa-muted); }
.non-empirical-note strong { color: var(--pa-text); }
.paper-writing { display: flex; flex-direction: column; gap: 24px; }
.advanced-writing-state { margin-top: 10px; border: 1px solid var(--pa-border); border-radius: 7px; background: var(--pa-surface); }
.advanced-writing-state > summary { padding: 9px 12px; color: var(--pa-muted); font-size: 11px; cursor: pointer; }
.advanced-writing-state[open] > summary { border-bottom: 1px solid var(--pa-border); color: var(--pa-text); }
.advanced-writing-state > .arco-spin { display: block; padding: 14px; }
.saved-screening { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--pa-border); }
.refinement-summary { border-top: 1px solid var(--pa-border); padding-top: 24px; }
.refinement-summary > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.refinement-summary h3 { margin: 0 0 4px; font-size: 16px; }
.refinement-summary p { margin: 0; color: var(--pa-muted); }
.refinement-flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--pa-border); border-radius: 10px; overflow: hidden; background: var(--pa-border); }
.refinement-step { min-height: 76px; padding: 14px 16px; border: 0; background: var(--pa-surface); color: var(--pa-muted); text-align: left; cursor: pointer; }
.refinement-step:disabled { cursor: default; }
.refinement-step.ready { color: var(--pa-text); background: var(--color-primary-light-1); }
.refinement-step.blocked { background: rgba(220, 38, 38, 0.08); }
.refinement-step span, .refinement-step strong { display: block; }
.refinement-step strong { margin-top: 6px; font-size: 13px; }
.refinement-step:not(:disabled):hover { background: var(--color-primary-light-2); }
.refinement-step:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: -2px; }
.audit-guidance { margin-top: 12px !important; color: var(--pa-danger) !important; }
.submission-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.submission-actions > span { margin-right: 4px; color: var(--pa-muted); font-size: 13px; }
.blueprint-sections { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.blueprint-sections > li { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding: 16px; border: 1px solid var(--color-border-2); border-radius: 8px; }
.blueprint-main { min-width: 0; }
.blueprint-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.blueprint-title-row h3 { margin: 0; color: var(--pa-text); font-size: 16px; }
.blueprint-main > p { max-width: 72ch; margin: 6px 0 10px; color: var(--pa-muted); line-height: 1.55; }
.blueprint-meta { display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--pa-muted); font-size: 12px; }
.blueprint-meta .unresolved-count { color: var(--pa-danger); font-weight: 600; }
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
.memory-time { font-size: 11px; color: var(--color-text-3); flex-shrink: 0; margin-top: 2px; }
.memory-source { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }
.memory-paper-link { max-width: 220px; padding: 0; overflow: hidden; border: 0; background: transparent; color: var(--pa-primary); cursor: pointer; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.memory-paper-link:hover { color: var(--pa-primary-hover); text-decoration: underline; }
.memory-paper-link:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
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
  .refinement-flow { grid-template-columns: 1fr; }
  .refinement-step { border-right: 0; border-bottom: 1px solid var(--pa-border); }
  .refinement-step:last-child { border-bottom: 0; }
  .workspace-shell { padding: 16px; }
  .research-map-header { flex-direction: column; }
  .map-columns { grid-template-columns: 1fr; }
  .screening-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .screening-list { grid-template-columns: 1fr; }
  .search-run-list li { grid-template-columns: 1fr auto; }
  .search-run-list code { grid-column: 1 / -1; grid-row: 2; }
  .matrix-header { flex-direction: column; }
  .matrix-insights { grid-template-columns: 1fr; }
  .design-columns,
  .criteria-grid { grid-template-columns: 1fr; }
  .experiment-results-panel > header { flex-direction: column; }
  .result-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .blueprint-sections > li { grid-template-columns: 32px minmax(0, 1fr); }
  .blueprint-sections > li > :deep(.arco-btn) { grid-column: 2; justify-self: start; }
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

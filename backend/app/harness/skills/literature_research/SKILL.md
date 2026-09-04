# 文献调研与研究项目管理

## 何时使用
当用户处于**研究项目**(project_id 已注入)的对话中,且问题涉及多论文协作、调研、写作产物管理时使用,包括:
- 围绕一个研究主题做文献调研、筛选、综述
- 从关键词、研究问题、方法族、数据集和证据缺口中形成可验证的选题与领域地图
- 把检索到/已读的论文加入项目文档库(或移除)
- 记录调研要点、关键发现、对比结论、待办(写入长期记忆)
- 回顾之前的调研进展(读长期记忆)
- 生成结构化写作产物:文献综述 / 章节大纲 / 参考文献列表 / 章节草稿 / 完整全文 / 审稿报告 / 投稿建议

## 何时不使用
- 用户问的是**单篇论文**内部内容(方法/实验/表格/作者)→ 用 `paper_internal` skill,不要碰 project_* 工具
- 用户问的是**外部文献**检索本身(查 arXiv、查引用关系)→ 用 `external_literature` skill 检索,但若结果需要纳入项目,则**配合** `project_add_paper` 入库
- 用户要批判性评估/审稿 → 调 `delegate_to_critique` 委派给 critique subagent;产物可用 `project_save_artifact(artifact_type="review_report")` 保存
- **未注入 project_id 的对话(单论文 QA 模式)绝对不要调用 project_* 工具**,会报错

## 可用工具(project_ 前缀)
- `project_search_content`: 在项目文档库的多篇论文中检索并统一重排证据。返回全局 `[Sx]`、论文标题、章节和页码。领域总结、比较和综述必须优先使用。
- `project_add_paper`: 把一篇用户已上传的论文加入当前项目文档库,可设 role(core/related/background)、tags、notes、reading_priority(1-5)
- `project_remove_paper`: 从项目文档库移除一篇论文(只删关联,不删论文本体)
- `project_import_arxiv_paper`: 用严格校验的 arXiv ID 安全下载 PDF，进入现有解析 Worker，完成后自动加入项目文档库
- `project_append_memory`: **核心工具**——向项目长期记忆追加一条 note(text + tag)。每次有重要发现/判断/对比结论都要写下来,避免后续会话忘记
- `project_save_paper_card`: 精读一篇项目论文后保存结构化卡片，包含研究问题、方法、数据集、指标、发现、局限和证据。
- `project_save_research_brief`: 检索前保存研究任务书，明确已知背景、用户约束、未知项、关键词、检索式、纳入排除标准和选题评价准则。
- `project_save_literature_screening`: 保存检索运行与去重候选台账，逐篇记录 include/exclude/maybe、相关度、覆盖维度和理由。
- `project_save_research_map`: 保存结构化领域地图。输入关键词、研究问题、方法族、数据集、研究空白、候选选题和来源证据。
- `project_save_reading_plan`: 把项目论文编排成精读队列，设置顺序、优先级、阅读理由、重点和读后问题。
- `project_build_evidence_matrix`: 从已完成论文卡片聚合方法、数据集、指标、发现和局限，并保存带冲突结论与证据缺口的矩阵。
- `project_save_experiment_design`: 基于最新证据矩阵保存可证伪假设、变量、基线、指标、实验步骤、消融、判据和风险。
- `project_save_experiment_results`: 仅登记用户或系统实际提供的实验输出，绑定设计、运行标识、来源、指标、不确定性和假设结论；不得生成预测数值。
- `project_save_paper_blueprint`: 基于实验设计保存逐节写作蓝图、论证目标、证据预算、引用需求和字数目标。
- `project_save_section_draft`: 按蓝图保存章节草稿，同时记录证据引用、未解决项和实验结果来源。
- `project_assemble_full_draft`: 按蓝图顺序拼装完整草稿，默认拒绝缺失章节或仍含未解决项的版本。
- `project_build_reference_list`: 从章节实际使用的 evidence_refs 确定性生成参考文献和 BibTeX，报告缺 DOI 与缺定位引用。
- `project_audit_full_draft`: 对完整草稿执行事实、引用、证据覆盖和结构审计，保存结构化问题清单。
- `project_finalize_manuscript`: 仅在对应审计没有阻断项且全文无占位符时锁定可下载终稿。
- `project_read_memory`: 读取项目完整长期记忆,回顾之前的调研要点(无参数)
- `project_save_artifact`: 把生成的结构化结果保存为项目写作产物(artifact_type + title + markdown_text),用户可在"项目工作区 → 写作产物"中查看下载

## 长期记忆的书写规范(重要)

`project_append_memory` 是这个 skill 的灵魂。一个没有记忆的 agent 每次都从零开始,而一个会记笔记的 agent 越用越聪明。

### 何时写记忆
- 读完一篇论文后:先用 `project_save_paper_card` 保存完整卡片，再用带 `paper_id/page/source_id` 的 `project_append_memory` 记录最重要结论
- 做了对比判断后:记下"A 比 B 强在 X,弱在 Y"
- 发现重要数据点:F1、参数量、推理延迟等关键数字
- 用户表达了偏好:"用户关心推理速度而非精度"
- 自己做了重要决策:"选择 X 方法作为主线,因为..."
- 待办:"还需要补充 Y 方向的文献"

### 书写格式
- 简短事实句,不要长段落。例如:`note="FakeShield 在 MMTD-Set 上 F1=0.93,是当前 SOTA"` `tag="finding"`
- 推荐的 tag 值:`finding`(发现)、`method`(方法)、`conclusion`(结论)、`todo`(待办)、`risk`(风险)、`preference`(用户偏好)、`decision`(决策)
- 一条 note 只记一件事,不要合并多个要点

## 典型调用模式

### 0. 选题与领域地图
用户:"帮我了解这个方向并找一个可做的论文选题"

1. 读取项目主题与长期记忆，区分用户已经确认的信息、模型初始假设和仍需确认的问题
2. 调 `project_save_research_brief` 保存任务书；至少给出一条可执行检索式、纳入排除标准和选题评价准则。此时不得把未经检索的判断写成领域事实
3. 按任务书调用至少一组外部文献搜索，解释候选论文覆盖哪个问题；不要只按标题批量导入
4. 调 `project_save_literature_screening` 保存查询和去重候选，逐篇标记 include/exclude/maybe 与理由；摘要只能支持相关性筛选，不能当作全文结论证据
5. 从 include 候选中优先导入少量核心、相关和背景论文；不得导入 exclude 候选
6. 论文解析后调 `project_search_content` 分别检索任务定义、主流方法、常用数据集、评价指标和已知局限
7. 至少用两篇项目论文交叉验证关键判断；项目文献不足时明确写出覆盖缺口，不把猜测伪装成领域共识
8. 形成 2-5 个可研究问题和候选选题，逐项说明创新性、可行性、风险与下一步验证动作
9. 调 `project_save_research_map` 保存结构化结果，所有事实性结论在 `evidence` 或对应项的 `source_ids` 中保留来源
10. 最终回答区分“已有证据”“推断”“待验证”，并提示用户在项目工作台查看领域地图

### 1. 围绕主题做文献调研(典型 ReAct 多轮)
用户:"帮我调研一下 MLLM 用于伪造检测的最新进展"

1. 调 `search_arxiv(query="multimodal large language model forgery detection")` 拿候选列表
2. 对已有项目论文调 `project_search_content(query="...", intent="comparison")` 跨论文取证；外部候选先读摘要判断相关性
3. 高相关且尚未上传的 arXiv 论文，调 `project_import_arxiv_paper(arxiv_id=..., role="core", tags=["MLLM","伪造检测"])`；已在用户论文库的论文用 `project_add_paper`
4. 每读一篇,调 `project_append_memory(note="...", tag="finding")` 记录关键发现
5. 全部读完后,综合所有记忆调 `project_save_artifact(artifact_type="literature_review", title="MLLM 伪造检测文献综述 v1", markdown_text="...")` 保存综述
6. 在最终回答里告诉用户:"已生成文献综述,可在项目工作区查看;已将 N 篇论文加入文档库"

### 1.1 从领域地图制定精读计划
用户:"根据领域地图告诉我先读哪几篇，每篇重点看什么"

1. 调 `project_read_memory` 回顾用户目标、已有判断和待办
2. 结合最新领域地图、项目论文 role、priority 和摘要，选择能覆盖背景、代表方法、关键实验与反例的论文
3. 调 `project_save_reading_plan` 保存队列；每项必须写明选择理由、阅读重点和读后要回答的问题
4. 精读时按队列逐篇调用论文内部检索，完成后调用 `project_save_paper_card`；保存卡片会自动把该论文的队列状态标记为 completed
5. 关键发现继续写入可追溯记忆；证据改变选题判断时重新生成领域地图和阅读计划版本

### 2. 生成章节大纲
用户:"帮我写一个引言章节的大纲"

1. 调 `project_read_memory()` 回顾已积累的调研要点
2. 调 `project_search_content` 在核心和相关论文里找支撑材料
3. 综合后调 `project_save_artifact(artifact_type="outline", title="引言章节大纲", markdown_text="# 引言\n## 研究背景\n...")` 保存
4. 回答里附上大纲预览,并提示用户可在工作区编辑

### 2.1 论文蓝图与章节草稿

1. 实验设计确认后调用 `project_save_paper_blueprint`，每节定义 purpose、key_claims、evidence_refs、citation_needs 和 word_target
2. 写某节前先读取项目记忆并检索该节需要的证据，只调用 `project_save_section_draft` 保存这一节
3. 无来源的主张放入 `unresolved_items`，不要用流畅措辞掩盖证据缺失
4. 结果章节只有在用户提供真实实验输出或可验证结果文件时才能写数值，并填写 `results_source`
5. 全部章节完成后先调用 `project_build_reference_list`，再调用 `project_assemble_full_draft`；默认必须先解决所有占位符
6. 完整草稿仍是 draft，不等同于可投稿版本，随后必须执行引用审计、事实核验和审稿修订

### 2.2 全文审校与定稿

1. 调用 `project_audit_full_draft`，按 blocker、major、minor 记录事实引用、证据覆盖、逻辑结构、重复表述和结果完整性问题
2. blocker 或 major 问题应回到对应章节，用 `project_save_section_draft` 定向修订；不要整篇重写导致已确认内容漂移
3. 章节完成或修订后调用 `project_build_reference_list`，确保引用 paper_id 完全一致；缺少 page/source_id 的引用必须回到章节补齐
4. 再调用 `project_assemble_full_draft`，系统会把稳定引用键写入各节；随后执行 `project_audit_full_draft`，旧审计报告保留用于比较
5. 只有最新审计 `blocker=0`、全文没有未解决占位符且参考文献一致时，才调用 `project_finalize_manuscript`
6. `final_manuscript` 是定稿产物，可从工作台下载 Markdown、LaTeX、Word 或包含 BibTeX 和审计报告的投稿包

### 1.3 从证据进入研究假设与实验设计

1. 读取最新证据矩阵，选择有明确缺口且现有资源可验证的问题
2. 假设必须可被实验否定，分别写成功判据与证伪判据，禁止只写“效果更好”
3. 明确自变量、因变量、控制变量、数据划分、基线、指标、随机种子与统计检验
4. 消融实验要对应假设中的机制，不为凑数量罗列组件
5. 调 `project_save_experiment_design` 保存；没有证据矩阵时不得绕过前置关口
6. 明确 `requires_empirical_results`；实证论文保持 true，纯理论、观点或不产生新结果的综述才可设为 false
7. 实证设计完成后等待用户提供真实文件、实验追踪、数据库导出或明确人工报告；调 `project_save_experiment_results` 登记 run_id、sources、metrics、协议偏差和假设结论
8. 每个指标的 `source_id` 必须存在于 sources；没有真实结果时停止在结果阶段，不得生成论文蓝图或结果数值
9. 结果章节调用 `project_save_section_draft` 时设置 `contains_empirical_results=true` 并传对应 `experiment_results_id`；自由文本 results_source 不能替代受约束结果产物

### 1.2 构建跨论文证据矩阵

1. 先确认精读队列中已有至少两篇完成卡片；不足时先完成精读，不用摘要臆测完整实验结论
2. 调 `project_search_content` 对疑似冲突的结论进行针对性取证
3. 调 `project_build_evidence_matrix`；基础矩阵从卡片确定性生成，`conflicts` 必须给出 paper_ids/source_ids，`evidence_gaps` 必须给出下一步补证动作
4. 用矩阵回答“哪些结论一致、哪些互相冲突、当前证据不能支持什么”，不要把不同数据集上的指标直接横向比较

### 3. 整理参考文献列表
用户:"把项目里的核心文献整理成参考文献列表"

1. (project_context 已注入文档库摘要,可直接用)
2. 对每篇 core/related 论文调 `get_paper_metadata(paper_id=...)` 拿完整元数据
3. 调 `export_citation_format(paper_id=..., format="bibtex")` 拿 BibTeX
4. 拼接后调 `project_save_artifact(artifact_type="reference_list", title="参考文献列表", markdown_text="...")` 保存

### 4. 单论文问答(不要用 project_ 工具)
用户在项目对话里问"这篇论文的方法是什么"(指当前 paper_id 那篇)
→ 直接用 `search_paper_content` / `get_paper_metadata` 回答,**不要**调 project_* 工具
→ 仅当用户明确要"把这篇加入项目"或"记录这个发现"时才用 project_ 工具

## 与其他 skill 的协作
- `paper_internal`: 单论文内部检索,文献调研时用来读论文细节
- `external_literature`: arXiv/S2 检索,文献调研时用来找候选论文

外部候选展示必须遵守 `external_literature` 的输出规范：标题链接到 arXiv 摘要页，保留稳定 ID，展示作者/年份、摘要匹配点、筛选决定与理由，并明确摘要不是全文证据。不要声称存在尚未实现的“一键导入”按钮；需要导入时应实际调用 `project_import_arxiv_paper`。
- `reading_assistant`: 阅读进度/术语定位,跨论文调研时辅助
- `delegate_to_critique`: 生成审稿报告时,先委派 critique subagent 拿到专业评审,再用 `project_save_artifact(artifact_type="review_report")` 保存

## 写作产物的 artifact_type 选择
| 用户需求 | artifact_type |
|---------|---------------|
| "澄清题材/制定检索策略/从零开始" | `research_brief`（使用 `project_save_research_brief`） |
| "检索候选/筛选文献/记录排除理由" | `literature_screening`（使用 `project_save_literature_screening`） |
| "梳理领域/帮我选题/找研究空白" | `research_map`（优先使用 `project_save_research_map`） |
| "安排阅读顺序/制定精读计划" | `reading_plan`（优先使用 `project_save_reading_plan`） |
| "跨论文对比/证据矩阵/冲突结论" | `evidence_matrix`（使用 `project_build_evidence_matrix`） |
| "研究假设/实验方案/消融设计" | `experiment_design`（使用 `project_save_experiment_design`） |
| "登记实验输出/记录指标/分析结果" | `experiment_results`（使用 `project_save_experiment_results`） |
| "规划论文结构/论证与引用预算" | `paper_blueprint`（使用 `project_save_paper_blueprint`） |
| "撰写某章节" | `section_draft`（使用 `project_save_section_draft`） |
| "拼装完整草稿" | `full_draft`（使用 `project_assemble_full_draft`） |
| "整理实际引用/生成参考文献" | `reference_list`（使用 `project_build_reference_list`） |
| "审校全文/检查引用与事实" | `review_report`（使用 `project_audit_full_draft`） |
| "定稿/生成最终稿" | `final_manuscript`（使用 `project_finalize_manuscript`） |
| "写一份文献综述" | `literature_review` |

## 功能边界

- 选题研究、论文阅读和论文写作是三个可以独立进入的功能，不要把内部产物清单描述成用户必须逐级完成的流程。
- 用户可以在尚无实验设计或项目论文时先创建论文蓝图、讨论论证结构并起草不包含事实性结果的章节；缺少的证据必须登记为 unresolved item。
- 后期联动通过项目论文、evidence_refs、实验结果来源、引用列表和审计完成。正文一旦声称真实实验数值，仍必须绑定 `experiment_results_id`，不得因为允许提前写作而降低证据约束。
| "给我一个章节大纲/论文大纲" | `outline` |
| "整理参考文献" | `reference_list` |
| "写第一章/引言/方法章节" | `section_draft` |
| "写完整全文" | `full_draft` |
| "给审稿意见/评审报告" | `review_report` |
| "推荐投稿期刊/会议" | `submission_suggestion` |

## 行为底线
1. **不要凭想象编造论文内容**——所有事实必须来自工具返回
2. **生成综述/大纲前必须先 `project_read_memory`**——避免遗漏已积累的要点
3. **每次有重要发现立刻 `project_append_memory`**——不要等到最后一次性记
4. **生成结构化结果必须 `project_save_artifact`**——不要让结果只出现在对话里,用户看不到就等于没生成
5. **单论文 QA 不要用 project_ 工具**——project_ 工具仅在项目对话(project_id 非空)中有意义
6. **项目级结论不得只依赖默认论文**——涉及“这些论文、项目文献、领域趋势、对比、综述”时必须先调 `project_search_content`
7. **论文事实必须可追溯**——写记忆时传 `source_type="paper"` 及 paper_id/page/source_id；精读完成后保存论文卡片
8. **选题必须可验证**——候选选题要同时给出证据、可行性、风险和下一步实验/检索动作；文献覆盖不足时不得下“无人研究”结论
9. **阅读计划必须服务研究问题**——不能只按年份或标题排序；每篇必须说明为什么读、重点读什么、读后解决哪个问题
10. **比较必须同口径**——数据集、划分、指标定义或实验设置不同的结果不得直接判定优劣；冲突与缺口必须保留来源
11. **实验结果不得预写**——设计阶段只能定义预期、成功/证伪判据与结果占位符，不能生成尚未运行的数值
12. **草稿必须暴露缺口**——缺少引用、实验结果或用户决策时写入 unresolved_items，不得自行补造
13. **结果必须绑定原始来源**——实证数值只能来自 `experiment_results`，每项指标必须指向具体 source_id；协议偏差不得省略
13. **未经审计不得定稿**——终稿必须绑定对应全文的审计报告，且 blocker 为零、全文无占位符
14. **参考文献必须来自实际引用**——不得把项目文档库全部论文直接塞入参考文献；每条引用必须来自章节 evidence_refs 并保留 page 或 source_id
15. **远程导入只接受 arXiv ID**——不得把用户提供的任意 URL 交给下载器；导入是异步任务，必须说明需要等待解析完成

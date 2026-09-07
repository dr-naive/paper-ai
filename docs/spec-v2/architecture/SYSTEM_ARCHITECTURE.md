# PaperAI System Architecture

> STATUS: CURRENT IMPLEMENTATION
> 本文描述当前分支已经落地并通过回归验证的主要架构事实与长期边界。
> 产品与功能合同位于 `docs/spec-v2/`；实施状态以
> `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md` 为准。
>
> 本文不把未实现的未来 endpoint、UI 或 Agent 能力写成当前事实。
> 历史方案和已移除的原型只在 `docs/archive/` 中保留。
>
> - `docs/spec-v2/product/PRODUCT_SCOPE.md`
> - `docs/spec-v2/features/`
> - `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
>
> 用于解释产品行为与施工顺序，不替代本文件对当前代码的描述。

---

## 1. 系统定位

PaperAI 当前由以下稳定能力组成：

```text
独立论文阅读、PDF 解析与 RAG
+
Project → Discover → Papers → Writing 工作流
+
Agent Runtime / Execution 基础
+
WritingDocument / Citation / Export 基础
```

Project 面向用户的 V1 产品面固定为：

```text
Project
├── Overview
├── Discover
├── Papers
└── Writing
```

Research Map、Reading Plan、Evidence Matrix、Experiment Design、Agent Activity 和通用 Project Chat
不作为 V1 的一级导航或主流程；仍存在的兼容代码不改变这一产品边界。

---

## 2. 顶层结构

```text
paper-ai/
├── backend/
│   └── app/
│       ├── agent/
│       ├── api/
│       ├── application/
│       ├── harness/
│       ├── infrastructure/
│       ├── llm/
│       ├── models/
│       ├── parsers/
│       ├── rag/
│       ├── services/
│       ├── utils/
│       ├── config.py
│       ├── database.py
│       ├── job_queue.py
│       ├── redis_client.py
│       ├── worker.py
│       └── main.py
│
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── router/
│       ├── stores/
│       ├── utils/
│       ├── views/
│       ├── App.vue
│       └── main.ts
│
├── docs/
└── deploy/
```

---

## 3. 运行环境

PaperAI 主要通过 Docker Compose 管理运行环境。

核心运行组件包括：

```text
frontend
backend
worker
postgres
redis
```

数据责任：

- PostgreSQL：durable relational state
- Redis：queue / live execution state / temporary runtime coordination
- `/app/data` / persistent volume：上传 PDF、解析产物和相关文件数据
- vector storage：现有 RAG / Hybrid Retrieval 使用的向量索引

### 外部网络与可选代理

`backend` 和 `worker` 访问学术 Provider、模型服务及批准的远程 PDF。两者都支持
通过 Compose 注入可选的 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`；未设置
`PAPERAI_HTTP_PROXY` 或 `PAPERAI_HTTPS_PROXY` 时保持直连。Linux Docker 使用宿主机
代理时，应在宿主机代理中允许 Docker 网桥访问，并在 `.env` 使用
`http://host.docker.internal:<port>`，而不是容器内无效的 `127.0.0.1:<port>`。

代理只改变容器的出站网络路径，不改变 Provider 决策、导入安全校验或超时边界。
代理凭证只能保存在本地 `.env` / Secret 管理中，不得提交到仓库。

不要使用 `docker compose down -v`，除非明确要删除持久化数据。

---

## 4. Backend 分层

当前后端已经不是纯 API + RAG 结构。

V1 使用以下逻辑边界理解现有代码：

```text
API
  ↓
Application Service
  ↓
Workflow / Agent Runtime
  ↓
Retrieval / Domain Services
  ↓
Infrastructure / Database / External Provider
```

部分历史模块仍保留跨层实现，但新的 V1 用例通过对应 Application Service、Workflow 和 Provider
边界进入；这属于已知长期技术债，不是额外的产品入口。

---

## 5. API Layer

目录：

```text
backend/app/api/
```

职责应限制为：

- HTTP request / response
- authentication
- authorization
- validation
- serialization
- SSE transport
- application-service invocation
- HTTP error mapping

当前 API 包括认证、论文/Reader、Project、Discovery、Writing/Citation、Execution/SSE
以及受 feature flag 保护的 Research Notes/Evidence 接口。HTTP 层负责校验、鉴权、序列化、
SSE 和错误映射；业务编排位于 Application Service / Workflow。
稳定接口清单见 `docs/API.md`。

---

## 6. Application Layer

目录：

```text
backend/app/application/
```

当前已至少存在：

```text
execution_service.py
writing_service.py
```

Application Service 的实际职责：

- 用例入口
- transaction boundary
- ownership / permission coordination
- 调用 workflow / repositories / services
- 返回稳定 DTO

当前 `writing_service.py` 承担 selection rewrite proposal 和 evidence-backed paragraph proposal；
它复用既有 WritingDocument、Evidence、Citation Verification 和 revision/export 基础，
没有建立第二套 Writing backend。

---

## 7. Agent Runtime / Harness

目录：

```text
backend/app/harness/
```

当前包含 Agent、Runtime、Tool、Skill 等基础。

关键方向：

```text
harness/
├── agents/
├── runtime/
├── tools/
└── skills/
```

### `lead_agent.py`

Legacy chat/Reader 路径中的 Lead Agent 仍承担：

- model tool-calling / ReAct loop
- 意图与上下文处理
- iteration budget
- tool dispatch
- execution / checkpoint / streaming 等相关职责

V1 用例通过独立的 Context、Discovery、Writing 和 Citation application/workflow 边界接入通用
Runtime；`lead_agent.py` 仍保留通用 tool-calling、checkpoint 和 streaming 职责。Goal-driven
ResearchTask 则必须传入 `TaskScope`：只加载当前 Skill 的工具，只允许当前 Project/Paper 资源，
在每次 ToolCall 前检查权限与预算，并以结构化 TaskResult 返回。Goal 场景下 Lead Agent 不规划
整个 Execution、不创建无关 Task，也不推进生命周期。

ResearchTask 的 Lead Agent 调用由 Worker 上下文关联到当前 `task_id` 和
`skill_id`。每次模型调用只记录无提示词的 `ModelCall` 元数据（模型、用途、
token、状态、耗时和错误码）；工具调用继续复用 `ToolCall`，任务执行时补充
可空的任务/Skill 关联。即时旧路径可以没有这两类关联，但不得把完整提示词、
原始推理或密钥写入观测数据。

### Tool Runtime

现有 Tool Runtime 是 V1 复用资产。

Tool 继续要求：

- atomic
- typed
- permission classified
- timeout bounded
- ownership checked
- auditable

### Skill Runtime

继续作为内部工程能力。

Skill 不作为 V1 用户产品界面。

---

## 8. Legacy `backend/app/agent/`

目录：

```text
backend/app/agent/
```

主要承载：

- PDF parsing pipeline
- summarizer
- QA fallback / legacy workflow
- Agent state definitions

这部分不等同于新的 Project Agent Runtime。

Project 功能不重写成熟的 PDF parse / Reader QA 基础。

---

## 9. PDF Ingestion / Parse Pipeline

现有主链大致为：

```text
PDF upload / approved remote import
→ Paper record
→ background worker
→ text / section / multimedia parse
→ database persistence
→ chunking / indexing
→ Reader / RAG available
```

Project Paper Profile 的当前生命周期是在：

```text
parse / index ready
```

之后作为非阻塞 enrichment 生成。

Paper Profile 失败不得导致 Reader 不可用。

---

## 10. RAG / Retrieval

核心位于：

```text
backend/app/rag/
```

现有能力包括：

- chunking
- embeddings
- vector retrieval
- Hybrid / Table retrieval related foundations
- Reader QA retrieval

V1 原则：

- 保留现有 RAG
- 不建立第二套向量库
- Writing Evidence Retrieval 在现有 retrieval 上增加 Project / Paper candidate filter
- Paper Profile 用来先缩小候选论文
- Evidence 才作为最终引用支撑

---

## 11. External Literature

现有：

```text
backend/app/harness/tools/external_literature.py
backend/app/harness/tools/literature_research.py
```

当前 Provider 边界和决策为：

```text
Semantic Scholar Academic Graph (unauthenticated-first)
→ normalized discovery papers
→ bounded Search Workflow
Crossref REST → metadata enrichment / fallback metadata
arXiv → preprint search metadata and approved PDF import source
```

`SEMANTIC_SCHOLAR_API_KEY` 仅是可选的限流增强，不是 V1 启动条件。401/403/429/超时由
Provider 层做有界错误映射；不会因为缺少 key 无限重试或静默切换未批准的 Provider。
Search Provider 与 PDF Remote Import 是不同架构层，结果统一为结构化 normalized paper，
不会把搜索结果拼成前端需要解析的 prose。

---

## 12. Remote Paper Import

现有远程论文导入能力应继续作为安全边界。

它负责：

- approved source resolution
- host / identifier validation
- size checks
- PDF validation
- temporary file handling
- cleanup
- 接入现有 Paper parse pipeline

它不应升级为 arbitrary URL downloader。

---

## 13. Project Domain

当前模型已经存在 Project 相关结构。

V1 核心：

```text
ResearchProject
ProjectPaper
```

ResearchProject 用于承载：

- title
- research topic
- optional structured research scope

ProjectPaper 表示：

> 已正式进入当前 Project 的 Paper 关系。

Discover 的 Favorite 不是 ProjectPaper。

---

## 14. Project Context

当前系统已有 memory / research / evidence 相关基础，Project Context 由以下类型化对象组成，
不作为一个大字符串发送：

```text
Project Context
├── Project Profile
├── Literature Memory
├── Paper Profile
├── Evidence
└── Writing Context
```

### Project Profile

描述用户正在研究什么。

### Literature Memory

保存少量长期有价值的检索偏好与确认后的 Search Intent。

### Paper Profile

描述已导入论文大致研究什么。

优先演化现有：

```text
ProjectPaper.analysis_card
```

### Evidence

来自真实 Project Paper 全文、可定位并可用于支持 claim 的来源对象。

继续复用现有 Evidence 基础。

### Writing Context

一次 Writing Agent 请求临时构造的上下文，不作为长期 Memory blob。

详细规则：

`docs/spec-v2/features/PROJECT_CONTEXT_AND_EVIDENCE.md`

---

## 15. Execution / Event

当前系统已经具有 execution service / execution state / event 恢复基础。

用途包括：

- long-running Agent run
- progress events
- pause / resume / cancel
- checkpoint / recovery
- SSE

内部可以记录细粒度 execution event。

用户界面只显示产品可理解的阶段，不展示 raw tool log 或 chain-of-thought。

### 15.1 Goal-driven Research Orchestration

Goal-driven 执行复用上述 `AgentExecution`、Redis Queue、Worker、checkpoint、retry、dead-letter、
trace、pause/cancel 基础，不维护第二套 execution runtime。`AgentExecution` 在 Goal 场景的
语义别名是 `ResearchExecution` / `GoalExecution`，并在原记录上持久化 `plan`、`plan_version`、
`progress`、`blockers` 和 `completion_reason`；旧 execution 行仍按原字段读取。

唯一业务执行链为：

```text
ResearchExecution (AgentExecution)
  → persisted ExecutionPlan
  → ResearchTask
  → WorkerJob (Redis queue carrier)
  → TaskDispatcher
  → AGENT / WORKFLOW / DETERMINISTIC executor
  → Artifact / Evidence / Project state
  → CompletionEvaluator
  → next task / waiting_user / blocked / completed
```

职责边界固定如下：

| 概念 | 当前职责 |
| --- | --- |
| ResearchExecution / GoalExecution | 一个用户目标的生命周期、预算、事件、恢复入口 |
| ExecutionPlan | 持久化的 goal、plan version、任务 DAG、依赖、复用资产和缺失依赖 |
| ResearchTask | 可独立执行、可重试、能产出明确结构化引用的业务步骤 |
| WorkerJob | 现有 Redis Queue 的传输与重试载体，不承载业务计划 |
| ResearchOrchestrator | 只负责 Goal、统一 ProjectStateSnapshot、Dependency、Plan、Dispatch、Completion |
| Lead Agent | 当前 ResearchTask 范围内的语义执行器，不接管整个 Execution |
| Skill | Task 的输入、产物、Tool 白名单、预算和 completion criteria 约束 |
| Tool | 原子、类型化、权限分类、超时和 ownership 校验的操作 |
| Artifact / Evidence | 可被后续任务通过结构化引用复用的项目产物 |
| ModelCall | ResearchTask 范围内的无提示词模型调用事实记录 |
| ToolCall | 原子工具调用事实记录；可关联 ResearchTask/Skill，不是业务任务 |
| Agent Runtime 报告 | 从 PostgreSQL Execution/Task/ToolCall/ModelCall/AgentEvent 聚合的开发评测产物；同时输出机器可读 JSON 与中文 Markdown |

第一版任务类型只包括 `DISCOVER`、`IMPORT_PAPER`、`READ_PAPER`、`BUILD_EVIDENCE`、
`WRITE_SECTION`、`AUDIT_DRAFT`；ToolCall 不拆成 ResearchTask。确定性搜索过滤、导入、解析/索引、
retrieval、reference builder、citation integrity、final gate 和 dependency check 继续由既有
Workflow/Service/Deterministic executor 负责，Agent 只处理语义判断、深度阅读、跨论文综合和写作。

恢复从 PostgreSQL 中的 Plan 与 Task 状态继续，绝不因为重启重新规划；重复 queue 消息通过稳定
task/artifact ID、Project advisory lock 和输出复用保持幂等。用户确认论文列表时，等待输入、schema、
候选上下文和对应 Task 均保存在当前 Execution 上，响应后恢复同一链路。

### 15.2 Agent Evaluation & Observability

内部观测不改变上述生命周期，也不新增 Agent Runtime 或第二套指标系统。`backend/evals`
继续从 PostgreSQL 确定性聚合 Execution、Task、AgentEvent、ToolCall、ModelCall、预算、
重复动作和 Failure Taxonomy；完整原始指标、失败记录和 trace 只保留在 JSON，供 Dashboard
和离线工具使用。

Markdown/HTML 采用诊断优先策略。报告先判断样本是否具备分析价值：没有 ResearchTask、
ToolCall 或 ModelCall，样本全部命中 Mock/测试标记，或 ResearchTask 少于 20 个时，只说明
无法评价真实 Agent 的原因、缺失数据、真实/Mock 样本、建议运行的真实链路和趋势阈值；不
输出空表、无意义的分位数、预算明细或完整字段字典。20–50 个 ResearchTask 仅观察初步
趋势，超过 50 个才适合进行 task_type、tool 和 failure 对比。样本充足时 Markdown/HTML
固定压缩为样本有效性、前三项问题、Task 类型对比、Failure/Tool/Duplicate、资源与 Budget
异常、Execution/ResearchTask 下钻六部分。缺失观测显示“暂无数据”，不得解释成零。

现有 Writing `execution_trace_report()` / `evaluate_execution_trace()` 仍是 Writing 专用
评估入口，Agent Runtime 报告只扩展运行事实，不替换或复制它。现有静态评测面板仅增加
开发/评测用 Agent Runtime 区块，不进入产品导航；不新增用户侧 Agent 页面。

管理员控制台的主动测评也不建立第二套执行基础设施。管理员点击测评后，API 持久化
`EvaluationRun`，再以同一个运行 ID 投递既有 Redis `WorkerJob`；Worker 复用当前
`run_agent_runtime_report`、`run_retrieval_eval` 或 `run_e2e_eval + score_e2e_eval`，
将 JSON/Markdown 报告引用和结构化汇总写回 `EvaluationRun`。前端只读取运行状态、
结果和历史日期，不直接暴露 Worker、ToolCall 或内部执行细节。重复启动由同一评测类型
的活动运行保护，重复消费使用稳定报告路径复用已完成结果；Provider/LLM 配置缺失时
记录失败原因，不把失败或空结果伪装成成功。

### 项目级 Goal 与即时交互边界

项目级 Reading / Writing 只有一个生命周期来源：

```text
Project Reading
  → READ_PAPERS GoalExecution
  → ResearchOrchestrator
  → ResearchTask(READ_PAPER)
  → TaskScope Lead Agent / existing workflow

Project Writing
  → WRITE_SECTION GoalExecution
  → ResearchOrchestrator
  → BUILD_EVIDENCE（按需）
  → WRITE_SECTION
  → AUDIT_DRAFT
```

旧 `writing_generate` 和旧 Project Reading HTTP 入口只保留兼容适配职责，
不得自行创建另一套 execution、WorkerJob 生命周期或项目级状态推进。旧的
项目 Reading Worker 循环已废弃；历史队列消息只允许转换到上述统一链路。

独立单论文问答、章节/公式/段落解释、当前论文局部总结以及选中文本的短
proposal 仍保留即时路径：

```text
API → Agent / Workflow → Tool → Result
```

即时请求不创建 GoalExecution，也不能被 Lead Agent 自行升级为项目级 Goal。
项目级入口统一由 `project_execution_entrypoint.py` 分类后交给
ResearchOrchestrator；Worker 只执行已持久化的 WorkerJob，Lead Agent 只执行
当前 ResearchTask。

---

## 16. Writing Domain

当前系统已经存在正式写作能力基础，包括：

- WritingDocument
- revision
- Tiptap editor
- AI proposal / diff 基础
- Citation Node
- citation audit
- export foundations

V1 不重建编辑器。

当前 Writing 主链：

```text
Editor selection/current section
→ Writing API
→ WritingService
→ Project Context
→ candidate Paper Profiles
→ Evidence Retrieval
→ generation / rewrite
→ Citation Mapping
→ Citation Verification
→ Proposal
```

AI 不直接覆盖正文。

用户通过：

```text
Replace selected content
Copy
```

决定是否采用 Proposal。

---

## 17. Citation Architecture

内部引用不能只保存：

```text
[1]
```

结构化 Citation 至少关联：

```text
paper_id
citation_key
evidence_id
```

V1 Citation Verification 分为：

```text
Referential Integrity
→ lexical / retrieval gate
→ semantic support verification
```

输出：

```text
verified
weak
unsupported
```

Citation style（GB/T 7714 / APA / IEEE）只影响渲染，不改变底层关联。

---

## 18. Frontend State

当前前端已经使用 Pinia 基础。

V1 推荐职责：

```text
authStore
projectStore
discoverStore
writingStore
executionStore
workspaceStore
```

原则：

- business entity state 与 UI shell state 分离
- Tiptap document 不重复存成第二份全局正文真值
- 不把 raw execution trace / provider payload 放进全局 store

---

## 19. Frontend Product Architecture

V1 Global：

```text
Home / Projects
Independent Reading
Settings
```

Project：

```text
Overview
Discover
Papers
Writing
```

不再存在一个承担全部研究功能的 `ProjectWorkspace.vue` 主入口；该旧 view 与旧 Project Chat
view 已删除。当前 canonical Project routes 是 Overview、Discover、Papers、Writing；旧
`/project/:id` 和 `/project/:id/chat` 仅作兼容重定向到 Overview。`PaperReader.vue` 继续作为
受保护的独立 Reader 资产，`WritingDocumentEditor.vue` 保留 Tiptap/revision/export 核心。

---

## 20. Reader Boundary

独立论文阅读是 V1 明确保留的另一条产品路径。

V1 不要求：

- 独立 Reader 自动加入 Project
- Reader 大规模 UI 重构
- 新增复杂高亮 / memory 工作流

Project Papers 只需要能稳定进入现有 Reader。

---

## 21. Literature Discovery Flow

当前 V1 主链：

```text
Requirement Chat
→ SearchIntent
→ user-editable structured filters
→ Search Planner
→ Semantic Scholar（未认证优先）
→ Crossref metadata enrichment / bounded fallback
→ Normalize
→ Deduplicate
→ relevance / coverage check
→ bounded retry
→ <= 10 real papers
```

结果返回结构化对象。

前端渲染 2-column cards。

操作：

```text
Details
Favorite
Download
Import
```

结果返回结构化对象；摘要保留 Provider 返回的完整内容。Favorite、Download、Import 是独立
动作，只有合法 arXiv 标识和 approved locator 才能进入现有安全导入/解析队列。

---

## 22. Writing Flow

当前 V1 主链：

```text
Instruction
→ current section / selection
→ Project Profile
→ Paper Profile shortlist
→ Evidence Retrieval
→ generation
→ Citation Mapping
→ Citation Verification
→ Proposal
```

只允许引用：

> 当前 Project 已正式导入并可检索的论文。

Writing 不自动联网搜索新论文；只允许当前 Project 中已正式导入、可检索并满足
Paper Profile / Evidence 条件的论文。生成和重写都先返回 proposal，用户显式 Replace 或
Copy 后才会创建新 revision。

---

## 23. API / Frontend Contract

所有新 V1 主链接口应使用稳定 schema。

重点包括：

```text
SearchIntent
SearchFilters
Normalized Paper Search Result
Writing Request
Writing Proposal
Citation Mapping
Citation Verification
Execution Progress
```

Execution Progress 只映射为“正在搜索相关论文”“已整理可用论文证据”“正在生成章节草稿”等
用户可理解的 ProgressStep；Worker、ToolCall、DAG 内部名称和 raw execution event 不作为产品 UI。

前端不得通过正则从 Agent prose 中解析论文卡片或 Citation。

---

## 24. Database Migration

Schema 修改必须走 Alembic。

禁止：

- startup `ALTER TABLE`
- 无兼容计划地删除列
- 为 V1 创建大量平行 V2 表

优先扩展现有：

- ResearchProject
- ProjectPaper
- MemoryItem
- EvidenceItem
- WritingDocument
- existing analysis-card structures

---

## 25. Documentation Architecture

当前文档分三层：

```text
docs/spec-v2/
= 当前产品、系统与功能合同

docs/*.md
= 长期维护 / 当前系统文档

docs/archive/
= 历史设计与历史代码快照
```

`docs/archive/` 不具有当前施工权威。

实施状态只由：

```text
docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md
```

持续维护。

---

## 26. Compatibility 保护项

不得无兼容方案破坏：

- PDF ingestion
- Paper IDs / file paths
- section / bbox / Reader定位
- Hybrid Retrieval
- Reader QA
- existing chat compatibility
- Project ownership
- execution / SSE recovery
- WritingDocument / revision
- Citation Node
- export
- remote import safety
- PostgreSQL / Redis deployment

---

## 27. 当前主要架构风险

详见：

`docs/TODO_OR_RISKS.md`

当前仍需持续监控的风险包括：

- Lead Agent God Object
- literature research Tool / Workflow 混合
- Context 退化为大 Prompt
- Citation semantic verification
- Writing / Reader regression
- remote import boundary
- lead_agent / literature workflow 职责过宽

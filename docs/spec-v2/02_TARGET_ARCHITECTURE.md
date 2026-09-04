# PaperAI V1 Target Architecture

> 文档状态：ACTIVE / AUTHORITATIVE
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文定义 **PaperAI V1 完成后的目标架构、层级边界、模块职责与允许依赖关系**。
> 本文不重复产品需求，也不逐文件列迁移步骤；迁移处置见 `01_CODEBASE_MIGRATION_MAP.md`。

---

# 0. 目标

V1 的技术目标不是构建一个通用 Agent Platform，而是建立一套足够稳定、可维护、可测试的科研工作流架构，使以下主链成立：

```text
Project
  ↓
Discover
  ↓
Import
  ↓
Read
  ↓
Project Context / Paper Profile / Evidence
  ↓
Writing
  ↓
Citation Verification
```

架构必须服务于产品，而不是反过来让产品适应 Agent Runtime。

---

# 1. 总体分层

推荐目标分层：

```text
Frontend
    ↓
API Layer
    ↓
Application Layer
    ↓
Workflow / Agent Orchestration
    ↓
Context / Retrieval / Verification Services
    ↓
Domain / Repositories
    ↓
Infrastructure / External Providers
```

各层职责必须清晰。

---

# 2. Frontend

前端负责：

- 页面与路由
- 用户输入
- 本地 UI 状态
- SSE / progress 展示
- editor selection
- structured citation rendering
- 调用 API

前端不得负责：

- academic search strategy
- evidence retrieval
- citation truth checking
- project context assembly
- Agent tool routing
- provider normalization
- business retry logic

---

# 3. API Layer

API 只负责：

```text
HTTP Request
  ↓
Auth
  ↓
Request validation
  ↓
Application Service
  ↓
Response serialization
```

API 不允许直接：

- 拼接长 Prompt
- 调 LLM
- 调多个 Provider 做 orchestration
- 查询多个表后直接构造 Project Context
- 判断 citation 是否可靠
- 写多轮 Agent loop
- 在 endpoint 中实现业务状态机

---

# 4. Application Layer

Application Layer 是业务用例入口。

建议至少存在以下服务职责：

```text
ProjectService
LiteratureDiscoveryService
ProjectPaperService
ProjectContextService
WritingService
CitationVerificationService
```

具体命名可根据现有结构调整，但职责不可混淆。

Application Service 负责：

- transaction boundary
- permission / project ownership
- 调用 workflow / domain service
- orchestrate repositories
- 返回稳定 DTO

Application Service 不应包含 provider-specific HTTP 细节。

---

# 5. Agent Runtime

## 5.1 定位

Agent Runtime 是通用执行底座，不是业务大脑。

保留现有 `lead_agent` 的核心 tool-calling loop，但其职责必须缩小。

目标：

```text
AgentRuntime
├── run()
├── model tool-call loop
├── iteration budget
├── tool dispatch
├── execution events
├── checkpoint
└── final result
```

## 5.2 不负责

Agent Runtime 不负责：

- 具体 Literature Discovery workflow
- 具体 Writing workflow
- Project Context retrieval
- Evidence retrieval
- Citation verification
- provider query building
- UI stage 文案

---

# 6. Workflow Layer

核心业务场景必须使用显式 workflow。

V1 至少需要：

```text
LiteratureDiscoveryWorkflow
WritingGenerationWorkflow
WritingRewriteWorkflow
CitationVerificationWorkflow
PaperProfileGenerationWorkflow
```

不是每个 workflow 都必须是 LangGraph。

优先级：

1. 普通 Python application workflow
2. 明确状态机
3. 只有确实需要复杂 branching / resume 时才考虑 graph

不要为了“Agent 化”强行把每个流程都建成图。

---

# 7. Literature Discovery Workflow

目标流程：

```text
Requirement Clarification
      ↓
SearchIntent
      ↓
User-editable Filters
      ↓
Search Plan
      ↓
Provider Query
      ↓
Normalize
      ↓
Merge / Deduplicate
      ↓
Result Quality Check
      ↓
Need retry?
  ├── yes → adjust query
  └── no
      ↓
Return <= 10 Papers
```

Agent 可做：

- clarification
- query strategy
- query rewrite
- relevance judgment
- retry decision

确定性代码做：

- filter validation
- pagination
- provider invocation
- normalization
- duplicate merge
- max-round enforcement
- result count limit

---

# 8. SearchIntent

必须有稳定结构，不允许仅用一段字符串传递。

建议 DTO：

```python
class SearchIntent:
    topic: str
    research_question: str | None
    detailed_need: str | None
    keywords: list[str]
    preferred_methods: list[str]
    exclusion_notes: list[str]
```

结构化固定筛选条件单独存在：

```python
class SearchFilters:
    year_from: int | None
    year_to: int | None
    language: str | None
    field: str | None
    publication_types: list[str]
```

禁止把 `SearchFilters` 全部回写成 Prompt 再交给 LLM“理解”。

---

# 9. Academic Search Provider

## 9.1 目标

外部论文数据源必须通过统一 Provider interface 接入。

建议：

```python
class AcademicSearchProvider(Protocol):
    async def search(
        self,
        query: str,
        filters: SearchFilters,
        limit: int,
    ) -> list[ProviderPaper]:
        ...
```

## 9.2 Normalize

Provider-specific result 必须转换为统一对象：

```python
class NormalizedPaper:
    source: str
    source_paper_id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    abstract: str | None
    doi: str | None
    paper_url: str | None
    pdf_url: str | None
    language: str | None
    publication_type: str | None
    fields: list[str]
    citation_count: int | None
    open_access: bool | None
```

缺字段允许为空。

## 9.3 V1 Provider 策略

V1 不要求一次接入很多 Provider。

推荐：

```text
Primary Search Provider
+
Optional Metadata / Citation Enrichment Provider
+
Existing arXiv Remote Import
```

实际选择在 `04_LITERATURE_DISCOVERY.md` 固定。

---

# 10. Search Provider 与 Import Provider 分离

必须明确：

```text
AcademicSearchProvider
≠
RemotePaperImporter
```

Search 负责：

- metadata
- abstract
- DOI
- links

Importer 负责：

- 获取真实 PDF
- 安全下载
- 文件验证
- 接入现有 parse pipeline

禁止把任意 search result URL 直接交给通用 downloader。

---

# 11. Context Architecture

核心结构：

```text
ProjectContext
├── ProjectProfile
├── LiteratureMemory
├── PaperProfiles
├── Evidence
└── WritingContext
```

Context 不应作为一大段字符串保存在单字段中。

---

# 12. Project Context Manager

建议新增明确服务：

```text
ProjectContextManager
```

职责：

- 根据当前业务任务决定需要哪些 context source
- 查询稳定结构化信息
- 控制 token budget
- 返回 RuntimeContext

示例：

```python
class RuntimeContext:
    project_profile: dict
    current_section: dict | None
    paper_profiles: list[dict]
    evidence: list[dict]
    nearby_text: str | None
```

Context Manager 不直接生成最终用户内容。

---

# 13. Context Retrieval Strategy

## Discover

读取：

```text
ProjectProfile
+
recent useful LiteratureMemory
```

不读取整篇 writing document。

## Writing

读取：

```text
ProjectProfile
+
current document / section
+
selection or nearby text
+
candidate PaperProfiles
+
Evidence
```

## Independent Reader

V1 不要求加载 Project Context。

---

# 14. Paper Profile

Paper Profile 是论文级轻量结构化摘要。

建议最终结构：

```python
class PaperProfile:
    paper_id: str
    project_id: str
    topic: str | None
    research_questions: list[str]
    research_subjects: list[str]
    methods: list[str]
    datasets_or_samples: list[str]
    main_results: list[str]
    conclusions: list[str]
    contributions: list[str]
    limitations: list[str]
    keywords: list[str]
    project_relevance: str | None
```

优先演化自：

```text
ProjectPaper.analysis_card
```

而不是新建重复体系。

---

# 15. Paper Profile Generation

导入并解析完成后，可触发轻量异步生成：

```text
Paper parsed
    ↓
PaperProfileGenerationWorkflow
    ↓
Profile persisted
```

要求：

- 失败不阻塞 PDF Reader
- 可重试
- 有 model / version metadata
- 可重新生成
- 不把 profile 当作引用真相

---

# 16. Evidence Retrieval

Evidence Retrieval 必须建立在真实 chunk / page / paper 来源上。

推荐流程：

```text
Writing Need
    ↓
Select Candidate Papers
    ↓
Hybrid Retrieval within candidates
    ↓
Relevant Chunks
    ↓
Evidence Candidate
    ↓
Claim-level validation
```

不得：

```text
Paper Profile
→ 直接生成引用
```

Paper Profile 只能用于缩小候选范围。

---

# 17. Evidence Service

建议存在稳定职责：

```text
EvidenceService
```

负责：

- normalize evidence
- validate provenance
- check project ownership
- deduplicate
- persist verified evidence
- fetch evidence for citation

不负责生成最终段落。

---

# 18. Writing Architecture

写作核心：

```text
Writing UI
    ↓
Writing API
    ↓
WritingService
    ↓
Writing Workflow
    ↓
ContextManager
    ↓
PaperProfile candidate selection
    ↓
Evidence Retrieval
    ↓
LLM generation
    ↓
Citation Mapping
    ↓
CitationVerification
    ↓
Proposal
```

---

# 19. Writing Rewrite Workflow

有 selection 时：

```text
selection
+
user instruction
+
current section context
    ↓
LLM rewrite
    ↓
proposal
```

默认不强制做 Evidence Retrieval，除非用户明确要求：

- 添加引用
- 保留论证依据
- 基于项目资料重写

但如果原 selection 已包含 structured citations，rewrite 不得无声丢失 citation mapping。

---

# 20. Writing Generation Workflow

无 selection 时，用户要求生成一段。

默认流程：

```text
instruction
+
current section
+
project context
    ↓
candidate paper selection
    ↓
evidence retrieval
    ↓
generation
    ↓
citation mapping
    ↓
verification
    ↓
proposal
```

V1 目标是“一段”，不是自动生成整章 / 整篇。

---

# 21. Citation Mapping

LLM 输出不允许只有纯文本 citation marker。

必须同时返回结构化映射：

```python
class GeneratedCitation:
    paper_id: str
    evidence_id: str | None
    claim_text: str
    citation_key: str
```

正文引用在前端通过现有 Citation Node 落地。

---

# 22. Citation Verification

Verification 至少分三层：

## Layer 1: Referential Integrity

确定性检查：

- paper exists
- paper belongs to project
- evidence exists
- evidence belongs to paper
- evidence belongs to project

## Layer 2: Lexical / Retrieval Gate

可复用现有 lexical audit 作为快速 gate：

- claim 与 evidence 是否完全无关
- evidence chunk 是否有效
- citation 是否明显错配

## Layer 3: Semantic Verification

需要更可靠判断：

```text
Does this evidence support this claim?
```

可由 verifier model / constrained LLM 执行。

输出：

```python
status: verified | weak | unsupported
reason: str
confidence: float | None
```

V1 用户结果只允许：

- verified
- 明确提示 weak / unsupported

不得把 unsupported citation 当成成功。

---

# 23. Retrieval Layer

优先复用现有 Hybrid Retrieval。

新增能力：

- project_id filter
- paper_id filter
- candidate paper restriction
- evidence-oriented query
- current section query

禁止建第二套 embedding pipeline。

---

# 24. Domain / Repository 边界

Agent / Workflow 不允许直接使用 ORM session。

应通过 repository / service：

```text
ProjectRepository
PaperRepository
WritingDocumentRepository
EvidenceRepository
ExecutionRepository
```

具体是否已有 repository 要基于当前代码逐步迁移，不要求一次性形式主义重写全部。

原则：

> 业务编排层不得依赖 SQLAlchemy Query 细节。

---

# 25. Infrastructure

Infrastructure 负责：

- PostgreSQL
- Redis
- vector store
- external APIs
- LLM provider
- filesystem
- remote download
- background worker

这些实现不得泄漏到 domain DTO。

---

# 26. LLM Provider

V1 不需要为了此重构建立复杂的多模型调度平台。

只要求：

- 通过现有 provider abstraction 接入
- 可明确区分不同用途的 model config
- generation / verifier 可配置
- timeout / retry 有边界
- 不在业务层硬编码 vendor-specific payload

---

# 27. Tool Registry

继续使用现有 Tool Runtime。

Tool 应保持：

```text
single responsibility
typed input
typed-ish result
timeout
side-effect classification
permission metadata
```

V1 新 Tool 示例：

```text
academic_search
retrieve_project_context
retrieve_paper_evidence
verify_citation
```

但注意：

并不是所有 Application Service 都要包装成 Tool。

只有 Agent 需要动态调用时才暴露为 Tool。

---

# 28. Skill

Skill 继续作为内部能力组合层。

V1 不要求所有 workflow 都写成 Skill。

可以有：

```text
literature_discovery
academic_writing
```

但用户不可见。

---

# 29. Execution Events

后端内部可记录细粒度事件：

```text
tool.started
tool.completed
workflow.step
verification.failed
retry
```

前端用户态映射为稳定阶段：

```text
clarifying
searching
screening
retrying
retrieving_evidence
generating
verifying
completed
failed
```

不要把内部事件名称直接暴露给 UI。

---

# 30. Failure Model

每个 workflow 必须明确失败边界。

## Literature Discovery

失败情况：

- provider unavailable
- timeout
- invalid filters
- zero results
- results too few
- repeated low relevance

正确行为：

- 不生成假论文
- 返回已有真实结果
- 提供可理解原因
- 允许用户修改条件后重试

## Writing

失败情况：

- no imported papers
- no relevant paper
- no evidence
- verification failed
- model timeout

正确行为：

- 不伪造引用
- 可以返回无引用的普通改写（仅用户明确允许时）
- 明确提示证据不足

---

# 31. Retry Budget

任何 Agent / Workflow 都必须有限预算。

建议：

```text
Literature search max rounds: 3
Tool retry per transient error: 1–2
Citation retrieval retries: finite
Agent loop max iterations: existing bounded runtime
```

具体数字在 feature spec 中锁定。

---

# 32. Persistence

必须区分：

## Durable

- Project
- ProjectPaper
- WritingDocument
- Revision
- Citation Node data
- Evidence
- Paper Profile
- selected Literature Memory
- execution summary / state

## Ephemeral

- raw search candidate cache
- temporary ranking scores
- intermediate Agent thoughts
- provider transient payload
- UI-only loading state

不要把所有中间结果都持久化成产品数据。

---

# 33. Cache

Academic Search 结果可有短期缓存，以减少重复 API 调用。

Cache key 应考虑：

```text
provider
query
filters
page/limit
```

Cache 不能替代 durable favorites / imported papers。

---

# 34. Frontend Architecture

推荐：

```text
frontend/src/
├── views/
│   ├── ProjectsHome.vue
│   ├── ProjectOverview.vue
│   ├── LiteratureDiscover.vue
│   ├── ProjectPapers.vue
│   ├── ProjectWriting.vue
│   └── PaperReader.vue
│
├── components/
│   ├── project/
│   ├── discover/
│   ├── writing/
│   └── shared/
│
├── stores/
│   ├── project.ts
│   ├── discover.ts
│   ├── writing.ts
│   └── workspace.ts
│
└── api/
```

实际重命名须尽量复用当前文件，避免无意义搬家。

---

# 35. Project Route

推荐：

```text
/projects/:projectId/overview
/projects/:projectId/discover
/projects/:projectId/papers
/projects/:projectId/writing
```

`/projects/:projectId` redirect 到 overview。

独立 Reader route 保留。

---

# 36. Discover UI 数据流

```text
Requirement Chat
   ↓
SearchIntent
   ↓
Search Form
   ↓
POST Search
   ↓
Execution / SSE
   ↓
Normalized Paper Cards
```

UI 不直接调用 Semantic Scholar / arXiv。

---

# 37. Writing UI 数据流

```text
Tiptap Selection / Cursor
   ↓
writingStore
   ↓
Writing Agent Request
   ↓
Proposal
   ↓
Citation Mapping
   ↓
Verification Status
   ↓
Replace / Copy
```

UI 不自己构造 evidence query。

---

# 38. Data Contracts

所有新主链 API 都必须有明确 schema。

至少需要：

```text
SearchIntentDTO
SearchFiltersDTO
PaperSearchResultDTO
PaperDetailDTO
PaperProfileDTO
WritingAgentRequestDTO
WritingProposalDTO
CitationMappingDTO
CitationVerificationDTO
ExecutionProgressDTO
```

禁止前后端靠“随便一个 dict”长期耦合。

---

# 39. Security

必须延续现有安全边界：

- remote import host allowlist
- file size limits
- PDF validation
- auth / project ownership
- side-effect tool confirmation rules
- no arbitrary URL fetch

Academic Search Provider 的 URL 仅用于 metadata / approved provider API。

---

# 40. Observability

关键 workflow 至少记录：

```text
execution_id
project_id
workflow_type
provider
search_rounds
tool_count
duration
failure_reason
verification_failures
```

不要记录用户不可见的 chain-of-thought。

---

# 41. Testing Strategy

## Unit

- SearchIntent validation
- provider normalize
- dedup
- filter mapping
- Paper Profile parser
- citation referential integrity
- verifier schema

## Service

- Discover workflow
- Writing generation workflow
- rewrite workflow
- evidence retrieval
- remote import

## API

- project ownership
- discover request / response
- writing proposal
- citation verification

## Integration

- Discover → import
- import → parse → Paper Profile
- Writing → evidence → citation verification

## Frontend

至少保证：

- build
- route
- basic interaction
- card states
- disabled download / import
- editor selection / replace
- writing proposal rendering

---

# 42. Recommended Backend Target Structure

不要求一次性全创建，但最终建议趋向：

```text
backend/app/
├── api/
│   ├── projects.py
│   ├── project_papers.py
│   ├── literature_discovery.py
│   └── writing.py
│
├── application/
│   ├── project_service.py
│   ├── literature_discovery_service.py
│   ├── project_context_service.py
│   ├── writing_service.py
│   └── citation_verification_service.py
│
├── harness/
│   ├── agents/
│   │   └── lead_agent.py
│   ├── runtime/
│   ├── tools/
│   └── skills/
│
├── research/
│   ├── discovery/
│   │   ├── schemas.py
│   │   ├── workflow.py
│   │   ├── providers/
│   │   └── normalize.py
│   │
│   ├── context/
│   │   ├── manager.py
│   │   ├── paper_profile.py
│   │   └── retrieval.py
│   │
│   └── citation/
│       ├── verifier.py
│       └── schemas.py
│
├── models/
├── rag/
├── repositories/
├── infrastructure/
└── services/
```

说明：

- `research/` 是否最终采用该目录名，由 Codex 根据现有 import 结构和冲突检查决定。
- 不允许为了严格匹配本文目录而机械移动大量稳定代码。
- 目标是职责边界，不是目录美学。

---

# 43. Recommended Frontend Target Structure

```text
frontend/src/
├── views/
│   ├── ResearchProjectList.vue
│   ├── ProjectOverview.vue
│   ├── LiteratureDiscover.vue
│   ├── ProjectPapers.vue
│   ├── ProjectWriting.vue
│   └── PaperReader.vue
│
├── components/
│   ├── discover/
│   │   ├── RequirementChat.vue
│   │   ├── SearchFilterForm.vue
│   │   ├── PaperResultCard.vue
│   │   └── PaperDetailDrawer.vue
│   │
│   ├── writing/
│   │   ├── WritingDocumentEditor.vue
│   │   ├── WritingAgentPanel.vue
│   │   ├── SelectionContextBadge.vue
│   │   └── WritingProposalCard.vue
│   │
│   └── project/
│
├── stores/
│   ├── project.ts
│   ├── discover.ts
│   ├── writing.ts
│   └── workspace.ts
│
└── api/
```

---

# 44. Anti-Patterns

以下实现直接视为不符合 V1 架构：

## Anti-pattern A

在 `lead_agent.py` 继续增加所有业务。

## Anti-pattern B

一个 `literature_research` Tool 完成搜索、筛选、导入、总结、写作。

## Anti-pattern C

Frontend 直接根据 Agent 文本正则解析论文卡片。

## Anti-pattern D

LLM 返回 `[1]`，系统不知道它对应哪篇 Paper。

## Anti-pattern E

把全部 Project Memory / Paper 全文塞进 Prompt。

## Anti-pattern F

为了 Project Writing 新建第二套 RAG。

## Anti-pattern G

因为搜索 Provider 能返回 URL，就允许任意 remote import。

## Anti-pattern H

前端显示 Tool / Skill / raw execution log。

## Anti-pattern I

Citation verification 失败后仍然标记为可信。

## Anti-pattern J

为旧 Research Map / Experiment 功能继续扩展新 API。

---

# 45. Architecture Decision Summary

V1 冻结以下决策：

1. **一个主 Agent Runtime，不建通用多 Agent 平台。**
2. **核心业务使用显式 workflow，Agent 只做有限不确定决策。**
3. **Tool 保持原子。**
4. **Academic Search Provider 与 PDF Import 分离。**
5. **Project Context 由 Context Manager 按需构造。**
6. **Paper Profile 用于找候选论文，Evidence 用于真实引用。**
7. **Writing 必须走真实 Evidence + Citation Mapping。**
8. **Citation Verification 是固定步骤，不允许被 Agent 跳过。**
9. **现有 Reader / RAG / Tool Runtime / Tiptap / Revision / Evidence 基础优先复用。**
10. **不建立重复的 V2 平行基础设施。**

---

# 46. 完成标准

当目标架构落地后，应满足：

```text
User Action
    ↓
Stable API
    ↓
Application Use Case
    ↓
Explicit Workflow
    ↓
Agent Decision only where needed
    ↓
Context / Retrieval / Tool
    ↓
Deterministic verification
    ↓
Structured Result
    ↓
Frontend Product UI
```

而不是：

```text
User
  ↓
Huge Agent Prompt
  ↓
LLM decides everything
  ↓
Tool chaos
  ↓
Text response
```

PaperAI V1 的架构目标是“让 Agent 成为稳定科研工作流中的智能判断层”，而不是让整个产品变成一个不可预测的 Agent Demo。

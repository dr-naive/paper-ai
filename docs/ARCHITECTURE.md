# Architecture

> STATUS: CURRENT IMPLEMENTATION
> 本文档描述 `agent-rearchitecture-v1` 分支当前已经落地并通过回归验证的主要架构事实。
> `docs/spec-v2/` 仍是 V1 的产品/施工合同；实施状态以
> `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md` 为准。
>
> 本文不把未实现的未来 endpoint、UI 或 Agent 能力写成当前事实。
> 历史方案和已移除的原型只在 `docs/archive/` 中保留。
>
> - `docs/spec-v2/02_TARGET_ARCHITECTURE.md`
> - `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`
>
> 用于解释设计边界与施工顺序，不替代本文件对当前代码的描述。

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

当前 Lead Agent 已经承担：

- model tool-calling / ReAct loop
- 意图与上下文处理
- iteration budget
- tool dispatch
- execution / checkpoint / streaming 等相关职责

V1 用例通过独立的 Context、Discovery、Writing 和 Citation application/workflow 边界接入通用
Runtime；`lead_agent.py` 仍保留通用 tool-calling、checkpoint 和 streaming 职责。
其职责过宽是已记录的长期风险，不通过新增用户界面来扩大。

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

V1 不因 Project 重构而重写成熟 PDF parse / Reader QA 基础。

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

`docs/spec-v2/03_PROJECT_CONTEXT_AND_EVIDENCE.md`

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
= 当前 V1 施工合同

docs/*.md
= 长期维护 / 当前系统文档

docs/archive/
= 历史设计与历史代码快照
```

`docs/archive/` 不具有当前施工权威。

实施状态只由：

```text
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
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

# Architecture

> STATUS: PARTIALLY OUTDATED DURING V1 MIGRATION
> Current implementation target: `docs/spec-v2/02_TARGET_ARCHITECTURE.md`
> 本文档描述 **当前 `agent-rearchitecture-v1` 分支已经存在的主要架构事实**，并标明 V1 重构期间的稳定边界。
> V1 的目标架构和施工顺序分别以：
>
> - `docs/spec-v2/02_TARGET_ARCHITECTURE.md`
> - `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`
>
> 为准。
>
> 本文不能用来推断“计划中的功能已经实现”。当 V1 Phase 9 完成后，应再次按最终代码同步本文。

---

## 1. 系统定位

PaperAI 当前已经从单纯的 PDF 阅读 + RAG 应用演化为：

```text
独立论文阅读系统
+
Project / Research Workspace 原型
+
Agent Runtime / Execution 基础
+
WritingDocument / Citation 基础
```

V1 产品正在收敛为：

```text
Project
├── Overview
├── Discover
├── Papers
└── Writing
```

现有 Research Map、Reading Plan、Evidence Matrix、Experiment Design、Agent Activity 等原型不代表 V1 继续扩展这些产品方向。

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

现有代码还没有完全按该目标拆干净，因此迁移期间会存在部分跨层历史代码。

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

已有 API 包括认证、论文、聊天、Project / execution / research-related endpoints 等。

V1 迁移方向：

- 不继续把复杂业务 orchestration 堆进单个 `projects.py`
- Literature Discovery 建立独立 use case / endpoint
- Writing Agent 建立独立 use case / endpoint
- `docs/API.md` 只记录真实已经实现并测试的接口

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

Application Service 的目标职责：

- 用例入口
- transaction boundary
- ownership / permission coordination
- 调用 workflow / repositories / services
- 返回稳定 DTO

当前 `writing_service.py` 仍主要是早期写作辅助能力，V1 会把它逐步扩展为 context-aware writing use case，而不是重新创建第二套 Writing backend。

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

V1 将保留通用 Runtime 核心，但迁出：

- Project Context assembly
- Literature Discovery workflow
- Writing workflow
- Evidence retrieval
- Citation Verification

`lead_agent.py` 不应继续变成所有科研业务的 God Object。

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

V1 新增的 Project Paper Profile 应在：

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

已经具备 arXiv / Semantic Scholar 相关能力。

当前问题：

- Provider 访问、搜索策略、workflow 职责还没有彻底分离
- arXiv 搜索能力较基础
- V1 尚未冻结 Primary Academic Search Provider
- 搜索结果 schema 需要统一

V1 目标：

```text
Academic Search Provider
→ Normalized Paper
→ Literature Discovery Workflow
→ bounded Agent result-quality decisions
```

Search Provider 与 PDF Remote Import 是不同架构层。

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

当前系统已有 memory / research / evidence 相关基础，但 V1 不再把 Project Context 理解为一个大字符串。

目标语义：

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

目标 Writing 主链：

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

不再继续扩大一个万能 `ProjectWorkspace.vue`。

迁移目标：

- `ProjectWorkspace.vue` 退化为 shell 或最终拆除
- Project route 拆成清晰子页面
- `ProjectChat.vue` 不再作为 Project 主入口
- `PaperReader.vue` 冻结为成熟资产
- `WritingDocumentEditor.vue` 保留 editor core，重构三栏 layout 与右侧 Agent

---

## 20. Reader Boundary

独立论文阅读是 V1 明确保留的另一条产品路径。

V1 不要求：

- 独立 Reader 自动加入 Project
- Reader 大规模 UI 重构
- 新增复杂高亮 / memory 工作流

Project Papers 只需要能稳定进入现有 Reader。

---

## 21. Literature Discovery Target Flow

V1 目标：

```text
Requirement Chat
→ SearchIntent
→ user-editable structured filters
→ Search Planner
→ Academic Search Provider
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

完整实现见：

`docs/spec-v2/04_LITERATURE_DISCOVERY.md`

---

## 22. Writing Target Flow

V1 目标：

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

Writing 不在 V1 自动联网搜索新论文。

完整实现见：

`docs/spec-v2/05_WRITING_WORKSPACE.md`

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

## 26. V1 迁移期间的关键保护项

不得无明确迁移计划破坏：

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

当前重点包括：

- Lead Agent God Object
- literature research Tool / Workflow 混合
- ProjectWorkspace 产品过载
- Academic Search Provider 选型
- Context 退化为大 Prompt
- Citation semantic verification
- Writing / Reader regression
- 文档权威冲突

---

## 28. 施工完成后的同步要求

Phase 9 时必须重新核对：

- 实际目录结构
- 实际 API
- actual provider
- actual Context implementation
- actual Writing workflow
- actual citation verifier
- actual routes / stores

然后删除本文中的“V1 目标 / 迁移方向”措辞，使 `ARCHITECTURE.md` 只描述已经存在的稳定系统。

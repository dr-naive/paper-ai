# PaperAI V1 Codebase Migration Map

> 文档状态：ACTIVE / AUTHORITATIVE
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文只回答一个问题：**当前代码库中的关键模块，在 PaperAI V1 中应该如何处理。**
>
> 本文不是产品需求文档，不重复 `00_PRODUCT_SCOPE.md` 的产品定义；
> 本文也不是最终架构文档，不在此重新发明 Runtime、Context、Tool 或数据库模型。

---

# 0. 使用规则

执行任何 V1 改造前，必须先根据本文判断当前文件属于哪一类：

- `KEEP`：保留并继续使用，只允许小范围修复 / 适配。
- `REFACTOR`：保留核心能力，但必须拆职责或调整结构。
- `EXTEND`：现有方向正确，在原基础上增加 V1 所需能力。
- `FREEZE`：当前能力已经足够，V1 原则上不主动修改。
- `HIDE`：底层可保留，但 V1 前端不再暴露。
- `ARCHIVE`：文档 / 旧实现只作为历史参考，不再作为当前行为来源。
- `REMOVE-LATER`：当前不强制删除，先断开主流程，待 V1 稳定后清理。

禁止 Codex 在没有查阅本文的情况下，仅因为“已有文件看起来复杂”就进行大规模删除或重写。

---

# 1. 总体迁移原则

## 1.1 不是推倒重来

当前 `agent-rearchitecture-v1` 已经具备以下可复用资产：

- 现有 PDF Reader
- RAG / Hybrid Retrieval
- Project 模型
- ProjectPaper 关联
- WritingDocument / revision 基础
- Tiptap 编辑器
- Citation Node
- Citation Audit 雏形
- Evidence 模型
- Tool Runtime
- Skill Runtime
- Execution / Event 基础
- Remote arXiv import
- Pinia 基础
- 一批 Agent / Runtime / Project / Evidence / Writing 测试

V1 应进行：

> **产品主线收敛 + Runtime 职责拆分 + Context / Discover / Writing 主链打通**

而不是建立第二套平行系统。

## 1.2 优先改“主线”，不要先删“旁支”

当前代码中已有：

- Research Map
- Reading Plan
- Evidence Matrix
- Experiment Design
- Activity
- Submission Suggestion
- 多种 Artifact type

这些超出 V1 产品范围。

第一阶段不要为了“代码干净”立即大规模删除数据库字段、模型 enum、旧 API。

优先做：

1. 新主线不再依赖它们；
2. 前端不再作为一级功能展示；
3. 新代码禁止继续扩展它们；
4. V1 稳定后再建立清理 Phase。

---

# 2. 后端目录级迁移

当前后端应继续维持分层：

```text
backend/app/
├── api/
├── application/
├── harness/
├── infrastructure/
├── models/
├── rag/
├── services/
└── ...
```

V1 禁止再新建一套平行的：

```text
backend/app/new_agent_runtime/
backend/app/v2_agent/
backend/app/research_platform/
```

后续功能必须优先落入现有分层。

---

# 3. `backend/app/harness/agents/lead_agent.py`

## Decision

`REFACTOR`

## 当前价值

该文件目前已经承担：

- Lead Agent 主入口
- LLM tool-calling / ReAct loop
- iteration limit
- conversation context
- project context 拼接
- critique / retry
- execution state
- checkpoint
- event / streaming
- tool dispatch
- 最终回答生成

其核心“主 Agent 执行循环”有价值，不应直接删除。

## 当前问题

职责过重。

继续在该文件加入：

- Literature Discovery 分支
- Writing Agent 分支
- Context retrieval
- Citation verification
- Search plan
- Paper ranking

会使该文件继续膨胀并变成不可维护的 God Object。

## V1 目标职责

`lead_agent.py` 最终只允许承担：

1. Agent run 的统一入口；
2. 调用模型；
3. 维护有限 tool-calling loop；
4. 接收已构造好的 Runtime Context；
5. 调用 Tool Runtime；
6. 将执行事件交给现有 execution/event 基础；
7. 返回标准 Agent Result。

## 必须迁出的职责

至少迁出：

- Project Context 拼接
- Paper Context 选择
- Literature Discovery workflow
- Search strategy orchestration
- Writing context retrieval
- Evidence retrieval
- Citation verification
- 业务级 retry 策略

## 禁止

禁止在 `lead_agent.py` 中加入：

```python
if mode == "discover":
    ...
elif mode == "writing":
    ...
elif mode == "citation":
    ...
```

这种不断累积业务分支的实现。

---

# 4. `backend/app/harness/runtime/tool_runtime.py`

## Decision

`KEEP`

## 当前价值

当前 Tool Runtime 已具备较完整的工程约束，包括但不限于：

- `ToolSpec`
- 输入 schema
- side effect metadata
- confirmation
- timeout
- idempotency
- standard `ToolResult`

这与 V1 需求一致。

## V1 处理

不重写 Tool Runtime。

只允许：

- 修 bug
- 补缺失类型
- 补测试
- 为新 Tool 接入标准 spec

## 禁止

禁止重新引入另一套：

```python
BaseTool
ToolRegistryV2
ResearchTool
SmartTool
```

除非现有 runtime 无法满足明确需求，并且先在 `02_TARGET_ARCHITECTURE.md` 中修改架构约束。

---

# 5. `backend/app/harness/runtime/skill_runtime.py`

## Decision

`KEEP / LOW-PRIORITY`

## 当前价值

已有：

- skill definition
- permission
- budget
- versioning

## V1 产品边界

Skill 是内部工程概念。

V1 前端不提供：

- Skill 选择器
- Skill 商店
- 用户配置 Skill
- “当前正在使用某 Skill”展示

## V1 处理

底层可继续保留。

新主链不要为了“统一成 Skill”而强迫所有 workflow 经过 Skill。

---

# 6. `backend/app/harness/tools/external_literature.py`

## Decision

`REFACTOR + EXTEND`

## 当前价值

已有：

- arXiv 外部搜索
- Semantic Scholar citations / references
- 外部论文 metadata 获取基础

说明远程学术数据访问不是从零开始。

## 当前问题

1. 搜索能力过度绑定具体 Provider。
2. arXiv query 过于简单。
3. Abstract 当前存在截断行为，不符合 V1。
4. 缺少统一 normalized paper result。
5. 缺少结构化 filter。
6. 缺少 provider capability 声明。
7. “搜索 Provider”与“PDF 导入来源”尚未清晰分离。

## V1 目标

该文件中的具体 Provider 调用应逐步下沉 / 拆分为类似：

```text
academic_search/
├── base.py
├── schemas.py
├── normalize.py
├── arxiv.py
├── semantic_scholar.py
└── ...
```

实际目录由 `02_TARGET_ARCHITECTURE.md` 最终确定。

统一输出必须支持：

```text
source
source_paper_id
title
authors
year
venue
abstract
doi
paper_url
pdf_url
language
publication_type
fields
citation_count
open_access
```

字段缺失允许为 `None`，但 schema 必须固定。

## Abstract 规则

后端返回完整 Abstract。

禁止：

```python
abstract = abstract[:500]
```

UI 截断由前端负责。

---

# 7. `backend/app/harness/tools/literature_research.py`

## Decision

`REFACTOR`

## 当前问题

该文件体量过大，已经承担超出“原子 Tool”应承担的职责。

从 V1 目标看，这类文件非常容易混入：

- Query planning
- Provider search
- ranking
- paper analysis
- project mutation
- report generation
- evidence
- workflow

## V1 迁移原则

必须拆成至少三个不同层次的能力：

```text
Search Provider / Atomic Tools
        ↓
Literature Discovery Application Workflow
        ↓
Agent Decision Layer
```

## 禁止

不得让一个 Tool 同时完成：

```text
理解需求
→ 搜索
→ 多轮重试
→ 排序
→ 推荐
→ 导入
→ 生成研究报告
```

Tool 必须保持原子能力。

---

# 8. `backend/app/services/remote_paper_import.py`

## Decision

`KEEP`

## 当前价值

现有实现已经具备较好的安全约束：

- arXiv ID 校验
- host allowlist
- PDF magic bytes
- Content-Length
- 最大大小
- 临时 `.part`
- SHA256
- 失败清理

## V1 目标

继续作为“远程全文安全导入”的基础。

## 关键边界

Academic Search Provider 与 Remote Import Provider 必须解耦。

允许：

```text
搜索来源：Semantic Scholar
PDF 来源：arXiv
```

也允许：

```text
搜索到论文
但没有合法可用 PDF
→ download / import disabled
```

## 禁止

不得因为 Discover 支持更多搜索 API，就把 importer 改成“任意 URL 下载器”。

---

# 9. `backend/app/models/project.py`

## Decision

`EXTEND / CONSERVATIVE REFACTOR`

## 当前已有关键资产

- `ResearchProject`
- `ProjectPaper`
- `WritingArtifact`
- project preferences / memory 等字段
- 多种 artifact 类型

## V1 处理原则

### ResearchProject

保留。

根据 `00_PRODUCT_SCOPE.md` 调整 / 扩展可选字段，目标是承载：

- title
- research_topic
- field
- research_subject
- research_question
- research_goal
- keywords
- method_direction
- notes / description

具体数据库字段是否拆列还是进入结构化 JSON，由后续架构文档决定。

### ProjectPaper

保留。

作为 Project 与正式导入 Paper 的关系层。

### WritingArtifact

不立即删除。

但 V1 禁止继续把所有新业务都塞进 `WritingArtifact`。

如果现有正式 WritingDocument 已经有独立模型，则 Writing Workspace 应以正式文档模型为主。

## 旧 artifact 类型

以下类型即使存在，也不等于 V1 必须实现对应产品：

- research_map
- reading_plan
- evidence_matrix
- experiment_design
- submission_suggestion
- paper_blueprint
- final_manuscript
- 其他超出 V1 的 artifact

处理：

`HIDE / REMOVE-LATER`

---

# 10. `backend/app/models/research.py`

## Decision

`KEEP + EXTEND`

## 当前已有关键资产

- `MemoryItem`
- `EvidenceItem`

## EvidenceItem

### Decision

`KEEP + STRENGTHEN`

当前已有：

- project_id
- paper_id
- section_id
- chunk_id
- page_number
- bbox
- snippet
- normalized_claim
- DOI / metadata

与 V1 的真实引用需求高度一致。

V1 应在现有模型基础上强化：

- evidence origin
- evidence status
- verifier result
- optional confidence
- generated / user-created provenance
- stale / invalidation semantics（若需要）

不得另建重复的 `CitationEvidenceV2` 表，除非现有表确实无法扩展。

## MemoryItem

### Decision

`REFACTOR SEMANTICS`

不允许继续使用一个“大而泛”的 Memory 模型承载所有聊天内容。

后续必须区分：

- Project Profile
- Literature Memory
- Paper Profile
- Writing Context
- ordinary conversation history

是否继续使用单表 + type，或拆结构化表，由 `03_PROJECT_CONTEXT_AND_EVIDENCE.md` 定义。

---

# 11. `ProjectPaper.analysis_card`

## Decision

`EVOLVE INTO PAPER PROFILE`

当前 `analysis_card` 已存在结构化论文分析雏形。

V1 不应再次创建完全平行的：

```text
paper_memory
paper_summary
paper_profile_v2
paper_context_card
```

优先评估将 `analysis_card` 演化为稳定 `Paper Profile`。

目标字段由 `03_PROJECT_CONTEXT_AND_EVIDENCE.md` 定义。

---

# 12. `backend/app/application/writing_service.py`

## Decision

`REFACTOR + EXTEND`

## 当前价值

现有实现已有：

- writing action
- selection
- LLM rewrite
- 不直接覆盖用户正文的基本思想

## 当前问题

能力仍偏“固定 action 字典”，距离 V1 Writing Agent 较远。

## V1 目标

该 Application Service 应逐步承担写作用例编排：

```text
selection rewrite
context-aware generation
paper profile retrieval
evidence retrieval
citation generation
citation verification
proposal return
```

其中：

- retrieval 不直接写在 API
- verifier 不直接写在 Vue
- Agent 不直接访问 ORM

## 禁止

不得只继续增加：

```python
ACTION_PROMPTS = {
    "academic": ...,
    "concise": ...,
    "longer": ...,
    ...
}
```

来伪装完整 Writing Agent。

---

# 13. Writing Document / Revision Backend

## Decision

`KEEP + EXTEND`

当前分支已存在正式 WritingDocument / Revision / citation audit 等能力。

V1 必须优先复用：

- document persistence
- revision
- restore / save
- structured content
- citation audit

不得重新建立另一个 `ProjectDraftV2` 平行体系。

---

# 14. Citation Audit / Citation Verification

## Decision

`KEEP FOUNDATION + REFACTOR VERIFICATION QUALITY`

当前已有 citation audit / lexical gate 等雏形。

## V1 目标

必须演化成：

```text
Citation exists
    ↓
Paper belongs to current Project
    ↓
Evidence exists
    ↓
Evidence belongs to same Paper
    ↓
Evidence supports claim
```

当前 lexical overlap 只能作为第一层 deterministic gate，不能作为最终语义真实性的唯一判断依据。

具体方案由 `03_PROJECT_CONTEXT_AND_EVIDENCE.md` 定义。

---

# 15. Execution / Event / Checkpoint 基础

## Decision

`KEEP`

当前已有 durable execution / event / checkpoint 基础。

V1 应继续使用它支持：

- long-running Agent run
- progress state
- SSE
- resume / failure
- timeout
- observability

## 产品约束

前端普通用户只显示：

```text
正在搜索
正在检查相关性
正在补充检索
正在验证引用
```

不得直接将 raw execution event 全量暴露给用户。

---

# 16. `backend/app/api/projects.py`

## Decision

`REFACTOR / SPLIT`

## 当前价值

已有：

- Project CRUD
- Project papers
- remote import
- memory
- evidence
- artifact
- research-oriented endpoints

## 当前问题

文件职责过多，已经承载大量不同 use case。

## V1 目标

API 层必须按资源 / 用例拆分。

建议最终至少区分：

```text
projects
project_papers
literature_discovery
writing_documents
project_context / evidence
```

具体文件名由目标架构文档确定。

## API 层规则

API 只能：

- auth
- request validation
- application service call
- response serialization
- HTTP error mapping

禁止：

- 写 Agent workflow
- 直接实现搜索策略
- 直接做 citation verifier
- 直接拼复杂 project context

---

# 17. RAG / Hybrid Retrieval

## Decision

`KEEP / EXTEND ONLY WHERE NEEDED`

现有 Reader / QA 已依赖 RAG。

V1 不重写现有 RAG 主体。

新增 Project Writing Retrieval 时：

- 优先复用现有 chunk / embedding / retrieval 基础
- 新增必要的 Project / Paper filter
- 增加 Paper Profile → candidate paper → evidence chunk 的分层检索

禁止建立第二套完整向量数据库。

---

# 18. Worker / PDF Parse Pipeline

## Decision

`FREEZE`

现有 PDF 上传 → parse → index 主链属于成熟资产。

V1 不因 Discover / Project / Writing 改造而重写 Worker。

允许：

- remote import 接入同一 parse pipeline
- Project 关联
- parse completed 后触发轻量 Paper Profile 任务

禁止：

- 复制一套 “Project PDF Parser”
- 复制一套 “Agent PDF Parser”

---

# 19. Frontend `ProjectWorkspace.vue`

## Decision

`MAJOR REFACTOR`

## 当前问题

当前页面承载过多功能：

- task brief
- candidate literature
- research map
- evidence matrix
- experiment design
- writing
- docs
- artifacts
- notes
- evidence
- Agent activity
- 等

这正是当前产品“功能很多但主线弱”的主要表现。

## V1 目标

不得继续向该页面加 Tab。

Project 应拆成明确 route / page：

```text
Project Overview
Project Discover
Project Papers
Project Writing
```

`ProjectWorkspace.vue` 最终应：

- 退化为 Project Shell，或
- 被拆分并删除

由前端施工文档决定。

---

# 20. Frontend `ProjectChat.vue`

## Decision

`HIDE / REUSE INTERNAL PARTS / REMOVE-LATER`

V1 不再以“Project Chat”作为整个 Project 的核心入口。

可复用：

- conversation UI
- streaming
- message rendering
- retry
- status

但应被嵌入：

- Discover Requirement Chat
- Writing Agent

而不是继续保留一个“所有科研任务都扔进 Chat”的主页面。

---

# 21. Frontend `PaperReader.vue`

## Decision

`FREEZE`

用户已经明确要求：

> 阅读界面暂时不改。

V1 原则：

- 保留现有阅读体验
- 保留独立阅读模式
- Project Papers 只需要能进入 Reader
- 不新增强制 Project Memory UI
- 不新增高亮 / 笔记改造要求
- 不为了 Writing 重构 Reader

只允许必要 bugfix 与 route / project linkage 的最小适配。

---

# 22. Frontend `WritingDocumentEditor.vue`

## Decision

`KEEP CORE + REFACTOR LAYOUT / EXTEND AGENT`

## 当前已有价值

当前已经具备：

- Tiptap
- Document rail
- Outline
- revision
- AI proposal / diff
- Citation Node
- citation audit
- Evidence sidebar 雏形

这部分是 V1 的重要资产。

## V1 目标

保留：

- Tiptap
- Document
- Revision
- Citation Node
- existing editor commands

重构：

- 页面整体三栏布局
- 右侧变成 Writing Agent
- selection state 提示
- Agent 结果动作
- citation result display
- context / evidence flow

## 用户交互目标

### 有 selection

```text
选中文本
→ 右侧提示已选中文字
→ 用户输入修改要求
→ Agent 返回修改稿
→ [替换选中内容] [复制]
```

### 无 selection

```text
用户输入生成要求
→ Agent 读取当前章节 + Project Context
→ 检索真实 Evidence
→ 生成一段
→ Citation Verify
→ [复制]
```

---

# 23. Frontend `ResearchProjectList.vue`

## Decision

`REFACTOR INTO PROJECTS HOME`

目标：

- 项目卡片
- 创建项目
- 最近项目
- 简洁入口

不做复杂统计 Dashboard。

---

# 24. Frontend Stores

## 当前

已有：

- `project.ts`
- `workspace.ts`

## Decision

`EXTEND`

建议最终拆分职责：

```text
projectStore
discoverStore
writingStore
workspaceStore
```

不要建立巨型：

```text
agentStore
researchPlatformStore
globalResearchState
```

## projectStore

负责：

- current project
- project metadata
- project papers summary

## discoverStore

负责：

- requirement chat state
- search intent
- structured filters
- result cards
- favorites
- search execution state

## writingStore

负责：

- current writing document
- selection context
- writing agent conversation
- proposal / citation verification status

## workspaceStore

只负责 UI shell：

- sidebar
- drawer
- pane size
- responsive state

---

# 25. Frontend Routing

## Decision

`REFACTOR`

Project 内部最终应有明确 route，而不是所有功能挂在一个大 Workspace：

建议：

```text
/projects/:projectId
/projects/:projectId/overview
/projects/:projectId/discover
/projects/:projectId/papers
/projects/:projectId/writing
```

是否默认 redirect 到 overview 由前端施工文档固定。

现有独立 Reader route 保留。

---

# 26. 前端设计系统

## Decision

`KEEP EXISTING TOKENS WHERE VALID + REBUILD PRODUCT LAYOUT`

不得为了 V1 大规模换技术栈或引入整套重量级 UI 框架。

视觉原则由 `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md` 定义。

现有可复用：

- button
- modal
- tooltip
- drawer
- loading
- empty state
- typography
- form

能复用则复用。

---

# 27. 测试

## Decision

`KEEP + EXPAND`

当前已有较多后端测试：

- runtime
- tool
- skill
- project contracts
- retrieval
- evidence
- remote import
- writing
- export
- hybrid retrieval

新施工必须沿用现有测试体系。

## 禁止

不得新写完功能后只做手工点击验收。

每个 Phase 至少需要：

- unit / service tests
- API contract tests（有 API 变化时）
- frontend build
- type check / lint（按项目当前工具）
- smoke / integration checklist

---

# 28. 文档迁移

## 28.1 `docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md`

### Decision

`ARCHIVE`

原因：

- 4591 行左右，职责过多
- 混合产品、架构、实施、历史现状
- 大量内容已部分实现
- 部分内容与当前重新确认的 V1 冲突
- 继续作为最高权威会误导 Codex

迁移：

```text
docs/archive/PROJECT_AGENT_IMPLEMENTATION_SPEC_V1.md
```

文件头增加：

```text
STATUS: ARCHIVED
This document is historical context only.
Do not use it as the current implementation contract.
Current authority: docs/spec-v2/
```

## 28.2 `docs/PROJECT_AGENT_UPGRADE_CONTEXT.md`

### Decision

`ARCHIVE`

迁移：

```text
docs/archive/PROJECT_AGENT_UPGRADE_CONTEXT_2026-08-17.md
```

原因：

它是某一时间点的代码事实快照，不应继续代表当前仓库。

## 28.3 `AGENTS.md`

### Decision

`REWRITE AUTHORITY SECTION`

保留现有有价值的工程约束。

必须修改文档读取顺序为：

```text
1. AGENTS.md
2. docs/spec-v2/00_PRODUCT_SCOPE.md
3. docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md
4. relevant spec-v2 feature document
5. docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md
6. docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

并明确：

```text
docs/archive/*
```

不得覆盖 `spec-v2`。

## 28.4 `docs/ARCHITECTURE.md`

### Decision

`REWRITE`

原因：

当前描述已经滞后于：

- application layer
- execution
- harness
- Writing V2
- Evidence / citation
- project evolution

新版本应以 `02_TARGET_ARCHITECTURE.md` 为依据更新成当前正式架构说明。

区别：

- `spec-v2/02_TARGET_ARCHITECTURE.md` 是施工目标
- `ARCHITECTURE.md` 是施工完成后的长期维护架构文档

在施工结束前可暂时标记：

```text
STATUS: PARTIALLY OUTDATED — see docs/spec-v2/
```

## 28.5 `docs/API.md`

### Decision

`KEEP + UPDATE CONTINUOUSLY`

API.md 只记录真实 API Contract。

不得放产品愿景。

每次 API Phase 完成必须同步更新。

## 28.6 `docs/TODO_OR_RISKS.md`

### Decision

`KEEP + REWRITE CURRENT FACTS`

删除 / 更新已经过时的风险描述。

新增当前真实风险，例如：

- `lead_agent.py` God Object
- `literature_research.py` God Object
- ProjectWorkspace product overload
- academic search provider limitation
- citation verification quality
- old/new docs authority conflict
- discover / writing integration risk

## 28.7 专项技术文档

以下文档原则上继续保留：

- `HYBRID_RETRIEVAL.md`
- `ANSWER_OBSERVABILITY.md`
- `QA_WORKFLOW.md`
- `WORKER_ARCHITECTURE.md`
- `SMOKE_TESTS.md`

只在对应能力实际发生变化时更新。

---

# 29. 不允许重复建设的能力

以下基础已有，除非后续规范明确要求，否则禁止重新实现：

```text
PDF Reader
PDF parse pipeline
RAG base
Tool Runtime
Skill Runtime
Execution / Event
WritingDocument persistence
Revision
Tiptap editor
Citation Node
Evidence model
Remote arXiv importer
ProjectPaper relation
```

---

# 30. 优先重构清单

施工优先级最高的三个“大职责”区域：

## P0

```text
backend/app/harness/agents/lead_agent.py
backend/app/harness/tools/literature_research.py
frontend/src/views/ProjectWorkspace.vue
```

目标不是删除，而是拆职责。

## P1

```text
backend/app/harness/tools/external_literature.py
backend/app/application/writing_service.py
backend/app/api/projects.py
frontend/src/components/project/WritingDocumentEditor.vue
frontend/src/views/ProjectChat.vue
frontend/src/stores/*
```

## P2

旧 Artifact / Research Map / Experiment / Activity 等非 V1 代码清理。

P2 必须在主链稳定后再做。

---

# 31. 迁移结果应满足的代码形态

完成 V1 后，仓库应呈现以下行为：

```text
旧系统能力
├── Reader                         KEEP
├── RAG                            KEEP
├── Parse / Worker                 KEEP
├── Tool Runtime                   KEEP
├── Execution                      KEEP
│
新主线
├── Project Overview               NEW / REFACTOR
├── Literature Discover            NEW / REFACTOR
├── Project Papers                 REFACTOR
└── Writing Workspace              EXTEND
    ├── Project Context
    ├── Evidence Retrieval
    ├── Real Citation
    └── Citation Verification
```

而以下内容不再主导产品：

```text
Research Map
Reading Plan
Experiment Design
Evidence Matrix page
Agent Activity page
Universal Project Chat
```

---

# 32. 每次修改前的文件级检查模板

Codex 在修改关键文件前，必须先写入实施进度文档：

```text
Target file:
Current responsibility:
Migration decision:
Why change is required:
What must be preserved:
What will move out:
Tests protecting this file:
```

修改完成后记录：

```text
Files changed:
Behavior changed:
Behavior intentionally preserved:
Tests added / updated:
Tests passed:
Known risk:
Follow-up:
```

此规则由 `08_IMPLEMENTATION_PROGRESS.md` 最终模板化。

---

# 33. 完成标准

本迁移不是以“旧文件变少”为完成标准。

完成标准是：

1. V1 主线不再依赖旧的过度产品功能；
2. God Object 的业务职责被合理拆出；
3. 已有成熟资产继续正常工作；
4. 没有建立重复 Runtime / RAG / Editor / Evidence 系统；
5. Project、Discover、Papers、Writing 有清晰边界；
6. 文档权威关系唯一；
7. Codex 可以根据文件级映射明确知道该改哪里、不该改哪里；
8. 所有 Phase 均可通过测试与 `08_IMPLEMENTATION_PROGRESS.md` 追踪。

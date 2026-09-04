# Archived

Status: COMPLETED / HISTORICAL

This document records completed PaperAI V1 implementation work.
It is no longer an active implementation authority.

Do not use this document for current implementation decisions unless
historical context is explicitly required.

# PaperAI V1 Codex Implementation Plan

> 文档状态：ARCHIVED / HISTORICAL
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文是 PaperAI V1 的**唯一实施顺序文档**。
> 其他 `spec-v2` 文档定义产品、架构与专项规则；本文只回答：**Codex 应该按什么顺序修改代码、每个阶段允许改什么、什么时候算完成。**

---

# 0. 执行总原则

Codex 不允许收到“完成整个 Agent 重构”后一次性修改几十个模块。

整个 V1 必须按 Phase 施工。

每个 Phase 由一个或多个完整的 **Implementation Block** 组成。

固定流程：

```text
Read Spec
    ↓
Inspect Current Code
    ↓
Update 08_IMPLEMENTATION_PROGRESS.md / Phase Start
    ↓
Define Implementation Blocks
    ↓
Implement Block A completely
    ↓
Run Block-level Tests / Acceptance
    ↓
Commit Block A
    ↓
Implement Block B completely
    ↓
Run Block-level Tests / Acceptance
    ↓
Commit Block B
    ↓
Phase-level Regression / Acceptance
    ↓
Update Documentation
    ↓
Update 08_IMPLEMENTATION_PROGRESS.md / Phase Complete
    ↓
Only then enter next Phase
```

不要把单个 DTO、helper、字段、样式调整、单个测试或同一功能板块里的小修复当成独立 Implementation Block。

---

# 1. Codex 会话读取顺序

不要在每个 Codex 会话开始时全文读取全部 `spec-v2` 文档。

每个正常实施会话固定读取：

```text
1. AGENTS.md
2. docs/spec-v2/EXECUTION_INDEX.md
3. docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
   - Overall Status
   - Current Implementation Block
   - Current Blockers
   - Latest Handoff
4. EXECUTION_INDEX 为当前 Block 指定的 spec headings
5. 当前 Block 直接相关代码和测试
```

只有当前 Block 确实需要时，才读取：

- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/HYBRID_RETRIEVAL.md`
- `docs/WORKER_ARCHITECTURE.md`
- `docs/QA_WORKFLOW.md`
- `docs/TODO_OR_RISKS.md`

`docs/archive/*` 只作历史参考，不得覆盖 `spec-v2`。

不要递归读取一份文档里提到的所有其它文档。

# 2. 禁止跨阶段实现

除非当前 Phase 明确依赖，否则禁止：

- 同时重构 Discover + Writing + Reader
- 同时大规模重构后端与 UI
- 在未建立 DTO / tests 前先写复杂 Agent prompt
- 在后端接口未稳定前先写假前端数据
- 为未来功能预建大量页面
- 清理所有旧 Research Map / Experiment code

优先让主链一步一步可运行。

---

# 3. Implementation Block、测试与提交节奏

一个 Phase 可以包含一个或多个 Implementation Block。

Implementation Block 是一个具有完整工程意义、能够独立描述和验收的功能板块，例如：

```text
Academic Search Foundation
Discovery Workflow and API
Discovery Result UI
Paper Profile Generation
Citation Verification
Writing Backend
Writing Agent UI
```

以下内容不能单独作为一个 Block：

```text
一个 DTO
一个 helper
一个字段
一个按钮样式
一个测试
一个同一 Block 内的小 bug fix
```

## 3.1 Development Check

开发过程中允许为了排错按需运行：

- 单个 test
- 单个 test file
- 局部 typecheck
- 局部 API 检查
- 某个 migration 的针对性验证

这些属于 **Development Check**。

它们的目的是快速发现局部问题，不是阶段验收。

不要每修改一点代码就运行完整测试套件。

## 3.2 Block Acceptance

当一个完整 Implementation Block 实现完成后：

1. 集中运行该 Block 相关测试；
2. 修复所有失败；
3. 执行该 Block 必要的手工 / Contract 验收；
4. 确认 Block 内没有遗留的临时 mock、假数据或失效按钮；
5. 更新 `08_IMPLEMENTATION_PROGRESS.md` 中该 Block 的结果；
6. 再创建一个有意义的 commit。

## 3.3 Phase Acceptance

一个 Phase 中所有 Block 完成后，再运行更广范围的：

- regression tests
- frontend build
- migration checks
- Reader regression（涉及时）
- export regression（涉及时）
- Phase acceptance checklist

Phase 级回归测试不是每个小改动后都运行。

## 3.4 Commit 规则

不要每个小改动都 commit。

一个 commit 应代表一个完整 Implementation Block。

例如 Phase 2 可以合理产生：

```text
feat(discovery): implement academic search provider foundation

feat(discovery): implement bounded discovery workflow and API

feat(discovery): integrate favorites and safe paper import
```

而不要产生：

```text
add SearchIntent
add filter field
fix provider
add dedup
fix test
update button
fix previous commit
```

复杂 Phase 通常应有少量有意义的 Block commits；小 Phase 可以只有一个 commit。

不同 Phase 的实现不要混进同一个 commit。

在同一个 Block 内出现的小修复、测试修补、样式调整和调试修改，应作为该 Block 的一部分完成，而不是制造额外 micro-commit。

## 3.5 分支

建议继续在当前：

```text
agent-rearchitecture-v1
```

或由维护者决定创建新的施工分支。

无论使用哪个分支，都以 Implementation Block 作为 commit 边界，而不是以文件修改次数作为 commit 边界。


# 4. Phase 0 — Documentation Authority & Baseline

## Goal

先解决“Codex 到底信哪个文档”以及当前代码基线。

## Required Reads

- `00_PRODUCT_SCOPE.md`
- `01_CODEBASE_MIGRATION_MAP.md`
- 当前 `AGENTS.md`
- 当前 `docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md`
- 当前 `docs/PROJECT_AGENT_UPGRADE_CONTEXT.md`
- 当前 `ARCHITECTURE.md`
- 当前 `TODO_OR_RISKS.md`

## Changes

### 4.1 新建目录

```text
docs/spec-v2/
docs/archive/
```

把本套新规范放入 `docs/spec-v2/`。

### 4.2 Archive

移动：

```text
docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md
→ docs/archive/PROJECT_AGENT_IMPLEMENTATION_SPEC_V1.md

docs/PROJECT_AGENT_UPGRADE_CONTEXT.md
→ docs/archive/PROJECT_AGENT_UPGRADE_CONTEXT_2026-08-17.md
```

历史文件开头加：

```text
STATUS: ARCHIVED
Historical context only.
Do not use as current implementation contract.
Current authority: docs/spec-v2/
```

### 4.3 AGENTS.md

保留已有工程规范，修改“权威文档”部分。

必须指向 `spec-v2`。

### 4.4 ARCHITECTURE.md

不要立即全文重写。

先在顶部加：

```text
STATUS: PARTIALLY OUTDATED DURING V1 MIGRATION
Current implementation target: docs/spec-v2/02_TARGET_ARCHITECTURE.md
```

等最终 Phase 再同步为长期文档。

### 4.5 TODO_OR_RISKS.md

更新已经明显过时的测试描述。

新增：

- lead_agent God Object
- literature_research God Object
- ProjectWorkspace overload
- provider limitation
- citation verification quality
- documentation authority conflict

## Tests

Phase 0 不改运行时代码。

至少：

```bash
git diff --check
```

确认文档链接无明显错误。

## Acceptance

- [ ] `docs/spec-v2/` 存在
- [ ] Archive 文档不再为 current authority
- [ ] AGENTS.md 明确 spec-v2 优先级
- [ ] Progress 文档建立
- [ ] 不修改业务代码

---

# 5. Phase 1 — Project Foundation & Navigation

## Recommended Implementation Blocks

### Block 1A — Project Contract and Route Foundation

Includes:

- Project metadata contract
- Project routes
- Project ownership / API compatibility
- projectStore adjustments

### Block 1B — Project Product Shell

Includes:

- Projects Home
- Project Header
- Overview
- Discover shell
- Papers page shell
- Writing shell around existing editor

Block-level tests and one meaningful commit should happen after each complete Block, not after each file edit.


## Goal

先把 V1 主产品骨架建立出来：

```text
Project
├── Overview
├── Discover
├── Papers
└── Writing
```

不在此阶段实现完整 Discover / Writing Agent。

## Backend Scope

检查 /调整：

```text
ResearchProject
ProjectPaper
Project CRUD
Project metadata DTO
```

实现产品要求字段：

- title
- research_topic
- optional research scope fields

如果当前模型已有 flexible JSON / preferences，可先用兼容方式，不强制过度 migration。

## Frontend Scope

重构：

```text
ResearchProjectList.vue
ProjectWorkspace.vue
router
projectStore
```

新增 /拆：

```text
ProjectOverview.vue
LiteratureDiscover.vue   # skeleton only
ProjectPapers.vue
ProjectWriting.vue       # shell around existing editor
```

## Required UI

### Projects Home

- 创建项目
- 项目卡片
- 项目名称
- 研究主题
- 论文数（能可靠拿到时）

### Project Header

固定 tabs：

```text
概览
文献发现
项目论文
写作
```

### Overview

三个入口：

```text
开始找论文
查看项目论文
开始写作
```

### Papers

先复用当前 Project papers 数据。

### Writing

先嵌入当前 WritingDocumentEditor，不重构 Agent。

## Forbidden

Phase 1 不做：

- Academic Search Provider 重构
- Context Manager
- Semantic Citation Verifier
- Writing Agent 新流程
- Reader 改造
- Research Map 清理

## Tests

Backend：

- project create
- optional metadata
- project ownership
- project paper list

Frontend：

```text
build
router navigation
refresh deep route
```

Manual：

- 新建 Project
- 默认进入 Overview
- 四个 tab 均可进入
- Reader 原 route 不受影响

## Acceptance Gate

主导航不完成，不进入 Phase 2。

---

# 6. Phase 2 — Literature Discovery Backend

## Recommended Implementation Blocks

### Block 2A — Academic Search Foundation

Includes:

- Search DTOs
- Provider interface
- Primary Provider adapter
- arXiv normalization
- normalized result schema
- deterministic filters
- deduplication
- full abstract preservation

### Block 2B — Discovery Workflow and API

Includes:

- Search Planner
- bounded multi-round search
- relevance / coverage check
- execution state
- discovery API
- error model

### Block 2C — Favorite and Import Integration

Includes:

- favorite persistence
- favorite isolation
- import availability
- safe remote import linkage
- duplicate import handling

Each Block is implemented first, then tested as a whole, then committed once.


## Goal

建立真实、稳定、结构化的 Discover 后端。

## Required Spec

`04_LITERATURE_DISCOVERY.md`

## Step 2.1 — DTO

新增：

```text
SearchIntentDTO
SearchFiltersDTO
SearchPlanDTO
ProviderPaperDTO
PaperSearchResultDTO
LiteratureSearchResponse
```

先有 schema 再写 workflow。

## Step 2.2 — Provider Adapter

重构：

```text
external_literature.py
literature_research.py
```

目标：

```text
Provider
Normalize
Workflow
```

至少建立一个稳定 Primary Provider。

在实现前，Codex 必须在 Progress 文档记录：

```text
Architecture Decision:
Primary Provider:
Why:
API constraints:
Rate limit:
Abstract coverage:
Filter support:
```

## Step 2.3 — Existing arXiv

保留 arXiv。

移除 Abstract 的 UI 截断。

接统一 Normalized schema。

## Step 2.4 — Search Workflow

实现：

```text
SearchIntent
→ Plan
→ Provider
→ Normalize
→ Dedup
→ Evaluate
→ Retry max 3
→ <= 10
```

## Step 2.5 — API

新增独立 discovery endpoint。

不要继续全部堆入 `projects.py`。

## Step 2.6 — Favorites Backend

收藏仅保存 metadata。

不得创建 ProjectPaper。

## Step 2.7 — Import

连接现有：

```text
remote_paper_import
→ parse
→ ProjectPaper
```

前端不可提交任意 URL。

## Tests

必须新增：

- Provider normalize
- Abstract full preservation
- filter mapping
- dedup DOI
- dedup title
- max 3 rounds
- <10 results
- 0 results
- provider failure
- no fabricated result
- favorite isolation
- import security
- duplicate import

## Acceptance

通过 API 能真实执行：

```text
search
→ <=10 real papers
→ favorite
→ import when PDF available
```

才进入 Phase 3。

---

# 7. Phase 3 — Literature Discovery Frontend

## Recommended Implementation Blocks

### Block 3A — Requirement and Search Form UX

Includes:

- Requirement Chat
- Search Intent ready state
- structured filters
- discoverStore request state
- search execution progress

### Block 3B — Search Result Experience

Includes:

- two-column result grid
- PaperResultCard
- abstract expand/collapse
- PaperDetailDrawer
- favorite / download / import states
- partial / zero / error states

Do not commit individual card tweaks or individual UI states separately while the same Block is still under construction.


## Goal

把 Phase 2 能力做成完整用户体验。

## Required Spec

- `04_LITERATURE_DISCOVERY.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`

## Components

建议：

```text
RequirementChat.vue
SearchIntentSummary.vue
SearchFilterForm.vue
SearchExecutionStatus.vue
PaperResultGrid.vue
PaperResultCard.vue
PaperDetailDrawer.vue
```

## Store

新增：

```text
discoverStore
```

## Step 3.1 — Requirement Chat

实现：

```text
clarifying
ready_for_search
```

## Step 3.2 — Search Form

结构化：

- 年份
- 语言
- 领域
- 文献类型

Search Intent 可编辑。

## Step 3.3 — Result Cards

固定：

```text
2 columns
10 max
abstract 4 lines
expand/collapse
```

## Step 3.4 — Actions

固定位置：

```text
详情
收藏
下载
导入
```

无 PDF：

```text
下载 disabled
导入 disabled
Tooltip
```

## Step 3.5 — Detail Drawer

内部详情。

原始页面作为 secondary action。

## Step 3.6 — Search State

显示：

```text
正在搜索
正在筛选
正在补充检索
```

不显示 Tool log。

## Tests

Frontend / manual：

- 双列
- 完整 Abstract 展开
- favorite toggle
- disabled actions
- tooltip
- drawer
- import
- zero / partial result
- Requirement collapse

## Acceptance

用户可以从 Project Overview：

```text
Discover
→ clarify
→ search
→ inspect
→ favorite
→ import
```

完整走通。

---

# 8. Phase 4 — Project Context & Paper Profile

## Recommended Implementation Blocks

### Block 4A — Typed Project Context Foundation

Includes:

- Project Profile access
- typed Literature Memory semantics
- removal of new generic memory dumping
- Context DTOs

### Block 4B — Paper Profile Generation

Includes:

- stable Paper Profile schema
- `analysis_card` evolution
- generation trigger
- retry / stale / version handling

### Block 4C — Candidate Paper and Evidence Retrieval

Includes:

- Context Manager
- candidate paper selector
- Project / Paper restricted Hybrid Retrieval
- Evidence provenance

Each Block gets one concentrated test cycle and one coherent commit.


## Goal

为 Writing 建立稳定上下文基础。

## Required Spec

`03_PROJECT_CONTEXT_AND_EVIDENCE.md`

## Step 4.1 — Define Typed Memory

明确：

```text
Project Profile
Literature Memory
Paper Profile
Evidence
```

停止新业务继续写 generic memory dump。

## Step 4.2 — Project Profile

建立 typed read / update。

不要求复杂 UI。

## Step 4.3 — Paper Profile Schema

优先升级：

```text
ProjectPaper.analysis_card
```

定义 schema version。

## Step 4.4 — Profile Generator

解析完成后异步生成。

要求：

- failure non-blocking
- retry
- status
- version

## Step 4.5 — Context Manager

新增：

```text
build_discovery_context()
build_writing_context()
```

停止新 workflow 直接拼：

```text
project.memory + papers + messages
```

## Step 4.6 — Candidate Paper Selector

实现 Paper Profile 级筛选。

默认目标：

```text
3–5 candidate papers
```

## Step 4.7 — Evidence Retrieval

复用现有 Hybrid Retrieval。

支持：

```text
project_id
paper ids
```

## Tests

- profile generation
- profile failure
- profile stale/regenerate
- no chat dump
- candidate restriction
- cross-project isolation
- evidence provenance

## Acceptance

给一个有多篇导入论文的 Project，可以通过 service：

```text
instruction
→ candidate papers
→ evidence chunks
```

稳定返回真实来源。

---

# 9. Phase 5 — Citation Verification Backend

## Recommended Implementation Blocks

### Block 5A — Deterministic Citation Integrity

Includes:

- Project / Paper / Evidence ownership
- Paper ↔ Evidence validation
- stale / missing Evidence handling
- reuse of current lexical audit

### Block 5B — Semantic Support Verification

Includes:

- verifier schema
- verified / weak / unsupported
- bounded retry / claim adjustment
- verification tests

Do not create separate commits for individual verifier prompts or test-case additions within the same Block.


## Goal

把“真实引用”变成系统约束，而不是 prompt 约束。

## Step 5.1 — Referential Integrity

实现确定性验证：

- Project
- Paper
- Evidence
- Paper ↔ Evidence
- Project ↔ Paper

## Step 5.2 — Existing Citation Audit

保留 lexical / deterministic gate。

不要删除旧 audit。

## Step 5.3 — Semantic Verifier

新增结构化 verifier：

```text
verified
weak
unsupported
```

## Step 5.4 — Retry / Claim Adjustment

只允许有限一次或两次保守改写 / 重新验证。

## Step 5.5 — API / Service

建立 CitationVerificationService。

## Tests

必须包括：

- valid
- wrong project
- wrong paper
- missing evidence
- stale evidence
- weak support
- unsupported
- correlation vs causation
- verifier timeout

## Acceptance

不得出现：

```text
citation mapping exists
but verifier not called
```

---

# 10. Phase 6 — Writing Backend

## Recommended Implementation Blocks

### Block 6A — Writing Service Contract

Includes:

- free-form rewrite
- section / selection context
- compatibility with current WritingDocument / revision / export
- structured proposal contract

### Block 6B — Evidence-backed Paragraph Generation

Includes:

- candidate papers
- Evidence Retrieval
- paragraph generation
- Citation Mapping
- Citation Verification
- failure codes

Each complete backend behavior Block should pass its related tests before commit.


## Goal

将现有固定 action 写作能力升级为 Context-aware Writing Agent。

## Required Spec

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `05_WRITING_WORKSPACE.md`

## Step 6.1 — Preserve Existing APIs

确认现有 WritingDocument / Revision / export 路径。

先写 compatibility tests。

## Step 6.2 — WritingService

目标：

```text
rewrite_selection
generate_paragraph
verify_proposal
```

## Step 6.3 — Rewrite

支持：

```text
selection
+
instruction
+
section context
```

已有 Citation 时保持映射。

## Step 6.4 — Generate

固定：

```text
Context
→ Paper candidate
→ Evidence
→ generation
→ citation mapping
→ verification
```

## Step 6.5 — Structured Output

LLM 返回 schema。

不靠 regex 猜 citation。

## Step 6.6 — Failure Codes

至少：

```text
NO_IMPORTED_PAPERS
NO_RELEVANT_PAPERS
NO_SUPPORTING_EVIDENCE
GENERATION_ERROR
VERIFICATION_ERROR
```

## Tests

- rewrite plain
- rewrite citation
- generate verified citation
- no papers
- no evidence
- structured output repair
- unsupported citation
- existing export regression
- revision regression

## Acceptance

后端独立 API 能：

```text
rewrite
generate one paragraph
return structured citations
return verification
```

---

# 11. Phase 7 — Writing Frontend

## Recommended Implementation Blocks

### Block 7A — Writing Workspace Layout and Editor Context

Includes:

- three-column layout
- outline integration
- section detection
- selection context
- Agent panel shell

### Block 7B — Proposal and Citation Interaction

Includes:

- rewrite proposal
- generate proposal
- replace / copy
- stale selection guard
- citation verification status
- Evidence detail
- loading / error states

Do not commit every style or button-state adjustment separately.


## Goal

把现有 WritingDocumentEditor 收敛为正式三栏 Writing Workspace。

## Step 7.1 — Preserve Editor

确认：

- Tiptap
- revision
- save
- undo
- citation node
- export

先不改业务。

## Step 7.2 — Layout

三栏：

```text
Outline
Editor
Agent
```

## Step 7.3 — Editor Context

捕获：

```text
section
selection
nearby text
```

## Step 7.4 — Agent Panel

实现：

- Context Badge
- multi-turn messages
- progress
- proposal

## Step 7.5 — Rewrite UX

有 selection：

```text
[替换选中内容] [复制]
```

替换前检查 selection stale。

## Step 7.6 — Generate UX

无 selection：

```text
[复制]
```

## Step 7.7 — Citation UX

展示：

```text
verified
weak
unsupported
```

Citation 可点开 Evidence detail。

## Tests

- selection
- stale selection
- replace
- undo
- copy
- proposal
- citation status
- panel collapse
- save
- export

## Acceptance

用户可真实完成：

```text
选一段 → 改写 → 替换
```

和：

```text
写要求 → 基于项目论文生成一段 → 查看真实引用 → 复制
```

---

# 12. Phase 8 — End-to-End Integration

## Recommended Implementation Block

### Block 8A — V1 Mainline Integration

Treat the four E2E journeys and required regressions as one integration Block unless a concrete failure requires a clearly separate repair Block.

Do not create a commit for every individual smoke-test fix.


## Goal

打通完整主链。

## Journey A

```text
Create Project
→ Overview
→ Discover
→ Import
```

## Journey B

```text
Project Papers
→ Reader
```

确认 Reader 没破。

## Journey C

```text
Writing
→ Generate
→ Evidence
→ Citation Verify
→ Copy
```

## Journey D

```text
Writing selection
→ Rewrite
→ Replace
→ Undo
```

## Tests

建议新增 integration / smoke：

```text
project_discover_import
import_parse_profile
writing_verified_generation
writing_rewrite
```

## Manual

以真实论文执行。

禁止只用 mock data 验收最终主链。

---

# 13. Phase 9 — Cleanup & Long-term Docs

## Goal

主链稳定后再清理旧原型和同步长期文档。

## Step 9.1 — Hide / Remove old product UI

确认：

- Research Map
- Reading Plan
- Experiment Design
- Evidence Matrix
- Activity
- old Project Chat

不再由 route / nav 暴露。

## Step 9.2 — Remove Later Candidates

根据实际依赖清理：

- unused components
- dead endpoints
- old artifact branches
- dead stores
- obsolete CSS

必须通过引用搜索和 tests 后删除。

## Step 9.3 — ARCHITECTURE.md

重写成最终实际架构。

## Step 9.4 — API.md

同步所有新接口。

## Step 9.5 — TODO_OR_RISKS.md

移除已解决问题。

保留真实剩余风险。

## Step 9.6 — SMOKE_TESTS.md

加入 V1 主链 smoke。

---

# 14. 每 Phase 的进度文档要求

`08_IMPLEMENTATION_PROGRESS.md` 是活文档。

开始 Phase 时：

```text
Status: IN_PROGRESS
Start commit:
Scope:
Implementation Blocks:
Current Block:
Target files:
Expected migrations:
Expected tests:
Known risks:
```

开始每个 Implementation Block 时记录：

```text
Block Status: IN_PROGRESS
Block Start Commit:
Includes:
Block Acceptance:
```

Block 完成后记录一次：

```text
Block Status: DONE
Block Commit:
Relevant tests:
Block acceptance:
```

完成时：

```text
Status: DONE / BLOCKED / PARTIAL
End commit:
Actual files changed:
Database migrations:
API changes:
Tests:
Manual acceptance:
Deviations from spec:
Known remaining issues:
Next phase readiness:
```

---

# 15. Phase 不通过时

若测试失败：

不得：

```text
标记 DONE
进入下一 Phase
```

允许：

```text
Status: BLOCKED
```

记录：

- failing test
- root cause
- needed decision

---

# 16. Spec Deviation

如果 Codex 发现施工规范与真实代码冲突：

不得静默自行改设计。

流程：

1. 记录 Progress：
   `SPEC_DEVIATION_PROPOSED`
2. 写清：
   - spec requirement
   - code reality
   - proposed deviation
   - impact
3. 优先采用最小偏离。
4. 修改 spec 后再继续。

对于明显小型实现细节，可以记录后继续；对于产品行为和架构边界，必须停止跨越该决策。

---

# 17. Database Migration Rule

任何 schema 变化：

- 必须 Alembic migration（若当前项目已启用）
- migration 可回滚
- 不允许启动时 `create_all` 偷改生产 schema
- Progress 记录 migration id

---

# 18. API Change Rule

新增 / 修改 API 后：

1. schema
2. service
3. endpoint
4. tests
5. `docs/API.md`

同一 Phase 内完成。

---

# 19. Frontend API Rule

前端禁止根据“预计接口”先长期写 fake adapter。

后端 contract 完成后接入。

短期开发 mock 必须在 Phase 完成前删除。

---

# 20. Test Commands

Codex 每个 Phase 应先读取项目实际 test command。

不得猜测。

至少记录：

```text
backend test command:
frontend build command:
frontend lint/typecheck:
```

Progress 中保留执行结果摘要。

---

# 21. No Fake Completion

以下不算完成：

```text
按钮已经放出来但 endpoint 未实现
页面用了静态 mock 数据
Agent 返回“模拟论文”
Citation status 永远写死 verified
Tooltip 写“coming soon”
```

---

# 22. Feature Flag

如果某 Phase 需要逐步上线，可以用明确 feature flag。

但不要永久留下：

```text
ENABLE_NEW_AGENT_V2_EXPERIMENTAL_BETA_FINAL
```

主线稳定后清理。

---

# 23. External Dependency Gate

当实现依赖外部服务时，先判断是否需要用户控制的外部配置。

外部依赖包括但不限于：

- Academic Search Provider
- LLM / Embedding Provider
- third-party storage / conversion / enrichment service

Codex 可以自行完成：

- 阅读官方 API 文档；
- 在规范限定范围内比较少量候选 Provider；
- 设计 Provider interface；
- 实现 adapter；
- 使用 mock HTTP response 编写 unit / contract test；
- 实现 401 / 403 / 429 / timeout 的确定性错误处理。

如果需要注册第三方账号、接受第三方条款、API Key、CAPTCHA、billing / quota、第三方控制台配置、用户授权或 secret，则不得不断尝试其它 Provider 或非官方 workaround。

必须：

1. 完成不依赖该凭证的代码；
2. 在 `08_IMPLEMENTATION_PROGRESS.md` 记录 `BLOCKED_BY_USER`；
3. 写清 provider、原因、用户需要执行的动作、环境变量、配置位置和后续验证方式；
4. 停止该依赖的真实集成验证；
5. 等待用户完成操作。

如果代码已完成但只缺真实外部验证，可记录：

```text
IMPLEMENTATION_COMPLETE_EXTERNAL_VALIDATION_BLOCKED
```

但相关 Phase 在真实 Provider 验证通过前不得标记完全 `DONE`。

Mock 可以满足 unit / contract tests，但不能满足：

- real-provider integration acceptance
- end-to-end acceptance
- production readiness

---

# 24. Performance Gate

Discover：

- 不允许无限 Provider 请求
- 结果 10 篇目标
- 最大 round 有边界

Writing：

- 不加载全部论文
- candidate 3–5
- verifier 只验证实际 citation

---

# 25. Security Gate

任何新 Remote Import：

- allowlist
- size
- PDF validation

任何 Project resource：

- ownership

任何 Evidence：

- cross-project isolation

---

# 26. Reader Regression Gate

Phase 1、4、8 都必须验证：

- 独立 Reader 正常
- Project Reader 正常
- QA 正常
- PDF loading 正常

V1 不允许以新 Agent 为代价破坏阅读。

---

# 27. Export Regression Gate

Phase 6、7、8：

验证当前已有：

- DOCX
- 其它稳定格式

Writing 重构不能让导出失效。

---

# 28. Recommended Phase Order Summary

```text
Phase 0
Docs Authority

Phase 1
Project Shell / Routes / Overview

Phase 2
Discovery Backend

Phase 3
Discovery Frontend

Phase 4
Project Context / Paper Profile / Evidence Retrieval

Phase 5
Citation Verification

Phase 6
Writing Backend

Phase 7
Writing Frontend

Phase 8
End-to-End Integration

Phase 9
Cleanup / Long-term Docs
```

---

# 29. Why This Order

## Discover before Context

先让用户能够：

```text
找到论文
→ 导入论文
```

否则后续 Context 没真实 Project Paper 数据。

## Context before Writing

Writing Agent 必须依赖稳定 Paper Profile / Evidence。

不能先写一个“暂时直接拼全部论文”的 Writing Agent，后面再重构。

## Verification before Writing UI finalization

Writing UI 的 citation status 依赖真实 verifier contract。

## Cleanup last

旧功能虽然乱，但提前删除容易破坏未梳理依赖。

---

# 30. Codex Session Size

不建议一个 Codex 会话跑完整 V1。

建议：

```text
1 session ≈ 1 Implementation Block
```

如果 Phase 很小，也可以：

```text
1 session ≈ 1 small Phase
```

复杂 Phase 应拆为多个完整 Block，例如：

```text
Phase 2
├── Block 2A — Academic Search Foundation
├── Block 2B — Discovery Workflow and API
└── Block 2C — Favorite and Import Integration
```

每个 Block 完成后：

```text
Implementation complete
→ Block-level tests
→ Block acceptance
→ one meaningful commit
```

所有 Block 完成后再做 Phase-level regression。

每次新会话读取 `08_IMPLEMENTATION_PROGRESS.md`，继续当前 Block 或进入下一个 Block。

不要因为会话即将结束就为一个未完成的 Block 强行提交半成品；应在 Progress 的 Handoff 中记录精确未完成状态。


# 31. Context Window Discipline

完整长规范是 reference，不是每会话的固定输入。

正常会话：

```text
AGENTS.md
→ EXECUTION_INDEX.md
→ Progress 的 current status / blocker / handoff
→ 当前 Block 指定 spec headings
→ 相关代码 / tests
```

不要每次全文重新读取：

```text
00 + 01 + 02 + 03 + 04 + 05 + 06 + 07 + 08
```

只有第一次进入某个 feature family、发生重大 spec/code 冲突，或 Handoff 无法提供足够上下文时，才扩大读取范围。

下一会话读取范围应优先由 `Latest Handoff` 进一步缩小。

# 32. Commit Message

推荐：

```text
feat(discovery): add normalized academic search provider
refactor(agent): move project context out of lead agent
feat(writing): add evidence-backed paragraph generation
docs(spec): archive legacy implementation spec
```

不要：

```text
update
fix things
agent final
```

---

# 33. Progress Must Reference Commits

每个 Phase 结束：

```text
Start commit:
End commit:
```

这样未来可以准确 diff。

---

# 34. Bug During Phase

如果发现与当前 Phase 无关 bug：

- 严重阻塞 → 修，并记录
- 非阻塞 → 写 `TODO_OR_RISKS.md`

不要顺手大改无关区域。

---

# 35. Existing Test Preservation

任何删旧代码前先找：

```text
tests referencing module
frontend imports
API consumers
docs references
```

通过后再删。

---

# 36. Definition of Done — Whole V1

整个 V1 只有以下全部成立才完成：

## Product

- [ ] Project 只突出 Overview / Discover / Papers / Writing
- [ ] 独立 Reader 保留
- [ ] Discover 可以真实搜索
- [ ] 搜索卡片可收藏 / 下载 / 导入
- [ ] Writing 是正式编辑器 + Agent
- [ ] Agent 可以基于 Project 论文生成一段
- [ ] 真实 Citation
- [ ] Citation Verification

## Architecture

- [ ] lead_agent 不再承担业务大全
- [ ] literature_research 被拆职责
- [ ] Context Manager 存在
- [ ] Search Provider normalized
- [ ] Paper Profile 存在
- [ ] Evidence provenance 稳定
- [ ] no duplicate RAG/runtime/editor

## Quality

- [ ] Backend tests pass
- [ ] Frontend build pass
- [ ] Reader regression pass
- [ ] Export regression pass
- [ ] E2E smoke pass
- [ ] docs updated
- [ ] Progress 完整

---

# 37. Codex Phase Start Template

复制到 `08_IMPLEMENTATION_PROGRESS.md`：

```markdown
## Phase X — <Name>

Status: IN_PROGRESS

### Goal

...

### Spec References

- ...

### Baseline

Start commit: `<sha>`

### Target Files

- ...

### Planned Changes

1. ...
2. ...

### Migrations

- none / ...

### Tests Planned

- ...

### Risks

- ...
```

---

# 38. Codex Phase Completion Template

```markdown
### Implementation Result

Status: DONE

End commit: `<sha>`

### Files Changed

- `...`
  - ...

### Database Migrations

- ...

### API Changes

- ...

### Tests Executed

```text
command
result
```

### Manual Acceptance

- [x] ...

### Deviations From Spec

- none

### Remaining Risks

- ...

### Next Phase Readiness

READY / NOT READY
```

---

# 39. Final Instruction to Codex

PaperAI V1 的施工原则是：

> **先把一条真实用户主链做深，再考虑扩展 Agent 能力。**

Codex 不应通过“多建几个 Agent、Tool、页面、Artifact”证明开发进度。

真正的进度是：

```text
用户能否更顺畅地
找论文
→ 导入
→ 阅读
→ 写作
→ 使用真实引用
```

每一个 Phase 都必须以这个目标作为最终验收标准。

# PaperAI Implementation Plan

Status: COMPLETE

## Phase 25 Maintenance Block — Agent Runtime 诊断优先报告

EVAL-OBS-3 在不新增指标体系、不重构 Agent Runtime 和不增加用户侧 Agent
页面的前提下，调整现有报告的展示决策。报告先判断 ResearchTask、ToolCall、
ModelCall 是否具备分析价值；空样本、Mock/测试样本或 ResearchTask 少于 20 个时，
只输出数据不足原因、缺失数据、样本分类、建议真实链路和趋势阈值。样本充足时，
Markdown/HTML 只展示最严重问题、Task 类型对比、Failure/Tool/Duplicate、资源
异常和下钻对象；完整原始指标继续保留在既有 JSON 中。

验收：覆盖空样本、Mock-only、20–50 和超过 50 个 ResearchTask 的样本质量判断；
确认 Markdown 不把缺失数据解释成 0，不默认输出无决策价值的空表、分位数、预算
明细或字段字典；确认现有 PostgreSQL Trace、Runtime Metrics、Failure Taxonomy、
静态 Dashboard 和报告命令保持兼容。

## Phase 25 Maintenance Block — Agent Runtime 报告可读性与覆盖增强

EVAL-OBS-2 在不新增执行基础设施、不改变 Agent Runtime 生命周期的前提下，
扩展既有报告读取范围：默认读取筛选范围内全部 Execution，加入 durable
AgentEvent、Execution 全状态分布、历史累计计数与明细追踪的覆盖对照，并同时
输出结构化 JSON 和中文 Markdown。Markdown 必须解释主要指标、显示样本范围、
空样本限制、取消/阻塞/等待用户状态和 Execution/Task 明细；没有分母的比例
指标显示“暂无数据”。

验收：报告命令默认不静默截断，显式 `--limit` 时记录截断信息；旧 JSON 消费者
和静态面板继续可用；空报告、历史 Execution、Task/Tool/Model 明细、AgentEvent、
取消状态、累计计数缺少明细和失败 Execution 均有测试覆盖。

## Phase 25 — Agent Evaluation & Observability

EVAL-OBS-1 is one coherent internal engineering block. Reuse the existing
AgentExecution, ResearchTask, ToolCall, Redis Queue, Worker, checkpoint,
retry, trace and Skill Runtime paths. Add only the durable correlation and
metrics needed to answer how the current runtime actually executes: which
tasks succeed, which tools fail or repeat, how model calls and budgets behave,
and where deterministic failure categories occur.

The block must keep old executions readable, preserve the existing Writing
evaluator, avoid chain-of-thought and full prompts, avoid an LLM judge and
avoid any product-facing Agent Center or Tool/Skill UI. The report is a
developer/evaluation artifact and the existing dashboard is extended rather
than duplicated.

Acceptance: migration `0008_agent_runtime_observability`; nullable ToolCall
task/skill correlation; durable ResearchTask ModelCall trace; deterministic
runtime report and failure taxonomy; duplicate-action observation; dashboard
Agent Runtime section; and focused persistence, aggregation, migration,
retry, blocked/waiting, budget, dashboard and Writing-evaluator regression
tests. Record actual coverage and any uninstrumented paths in
`IMPLEMENTATION_PROGRESS.md`.

## Current Phase

Phase 25 — Agent Evaluation & Observability.

## Current Implementation Block

EVAL-OBS-1 — completed. Backend `348 passed`, frontend `79 passed`, frontend
typecheck/lint/build passed, targeted Ruff passed, migration head
`0008_agent_runtime_observability` and schema preflight passed. The local
database report command produced an explicit empty task sample; no real model
credentials were used.

## Phase 24 — Project Execution Lifecycle Closure

LIFE-1 is one coherent block: route project Reading and Writing through the
existing GoalExecution/ResearchOrchestrator lifecycle, remove the duplicate
project-reading worker lifecycle, centralize project-goal entry classification,
preserve independent single-paper interaction paths, and expose only the
durable GoalExecution progress projection in project UI. Do not redesign the
Orchestrator, Queue, RAG, Skill Runtime or stable Writing foundations.

The acceptance gate covers the legacy project Reading adapter, the
`writing_generate` compatibility adapter, the Reading/Writing/instant
interaction boundary, GoalExecution progress and blocker projections, waiting
user recovery, and existing Discover/Reader/Chat/PDF/RAG/Writing regressions.

LIFE-1 acceptance result: COMPLETE. Backend `339 passed`, frontend `79 passed`,
frontend typecheck/lint/build passed, targeted backend Ruff passed, and no
database migration was required. See `IMPLEMENTATION_PROGRESS.md` for the
actual compatibility boundaries and remaining risks.

## Phase 23 — Goal-driven Research Orchestration

ORCH-1 is one coherent block: extend AgentExecution in place; persist typed
ResearchTask and plans; adapt existing capabilities through Queue/Worker;
centralize deterministic state/completion; scope Lead tools; expose compatible
progress and resumable user input. Acceptance covers READ_PAPERS, WRITE_SECTION,
DISCOVER_AND_IMPORT, asset reuse, retry, duplicate consumption, interruption,
waiting_user, blocked, partial and cancel plus existing regressions.

ORCH-1 acceptance result: COMPLETE. Backend `333 passed`, frontend `78 passed`,
frontend typecheck/lint/build passed, Alembic head `0007_research_tasks` and
schema preflight passed. See `IMPLEMENTATION_PROGRESS.md` for the exact file,
chain, migration and remaining-risk handoff.

## Historical Phase 23 Reference

Phase 23 — Goal-driven Research Orchestration. ORCH-1 is complete and is the
foundation used by Phase 24; the current block is recorded above.

## Phase 22 Goal

Make the shared Reader tolerant of stale or truncated PDF responses and avoid
unbounded progress-save requests when a user leaves the Reader. Preserve the
existing PDF range endpoint, manual cache, Reader implementation and status
payload contract.

## Phase 22 Acceptance

- PDF 200 and 206 responses advertise the exact body length and revalidate
  instead of treating partial responses as immutable;
- range delivery detects a short read before returning the body;
- PDF.js keeps the range fast path and has one bounded complete-download
  recovery path for a network/worker failure;
- stale/manual PDF cache entries are isolated by a new namespace and invalid
  bytes are discarded;
- Reader progress saves have a bounded timeout, do not duplicate a request on
  teardown and do not surface background teardown failures as application
  errors;
- frontend tests, lint, typecheck, build and backend syntax/range checks pass.

## Phase 22 Block

1. READER-TRANSPORT-1 — PDF delivery/recovery and progress persistence

## Phase 21 Goal

Make navigation context explicit across Independent Reading, Project Papers
and the shared Reader. Reuse Reader and upload capabilities without leaking the
wrong business context, losing project identity, or sending project users to
the global paper library.

## Phase 21 Acceptance

- the canonical Standalone Reader route is `/paper/:id` and the canonical
  Project Reader route is `/projects/:projectId/papers/:paperId/read`;
- both routes render the same `PaperReader.vue` implementation;
- a Standalone Reader returns to Independent Reading, while a Project Reader
  returns to the current Project Papers page with project identity intact;
- ProductHeader accepts Vue Router `RouteLocationRaw` Back and breadcrumb
  locations and exposes a consistent header hierarchy;
- Project-only Reader actions, project title/context and cross-paper evidence
  links remain scoped to the active project;
- local upload from Project Papers uses the existing paper upload pipeline and
  attaches the ready paper to the current project before refreshing the list;
- legacy project query links remain compatible without being the primary
  navigation model;
- focused route, deep-link, Reader-context, Header and project-upload tests,
  frontend lint, typecheck and production build pass.

## Phase 21 Block

1. NAV-1 — Semantic Reader Context and Project Upload.

## Phase 20 Goal

Keep the Guide's top navigation and desktop sidebar visible while the reader
scrolls, reserve their occupied space in the layout, and reduce the main
surface's horizontal gutter to exactly three pixels.

## Phase 20 Acceptance

- the Guide top navigation is fixed to the viewport;
- the desktop sidebar is fixed below the top navigation;
- content begins below the fixed header and beside the fixed sidebar without
  overlap;
- the horizontal main gutter is three pixels at desktop and mobile widths;
- responsive navigation and existing Guide routes/content remain intact;
- focused frontend tests, ESLint, typecheck and production build pass.

## Phase 20 Block

1. GUIDE-7 — Fixed Header and Sidebar.

## Phase 19 Goal

Connect the Guide reading surface directly to the global header. Remove the
remaining top gray band and rounded-card treatment while keeping the small
horizontal gutter requested for the main content.

## Phase 19 Acceptance

- the main content begins immediately below the global header;
- the Guide document has no rounded top or card-like corner treatment;
- the six-pixel horizontal gutter remains on desktop;
- tablet and mobile layouts do not reintroduce a top gray gap;
- existing Guide routes, navigation states and content remain intact;
- focused frontend tests, ESLint, typecheck and production build pass.

## Phase 19 Block

1. GUIDE-6 — Remove Top Gap and Card Corners.

## Phase 18 Goal

Make the documentation hierarchy immediately legible and remove the excessive
gray framing around the Guide document. Group titles should read as section
headers, while chapter links remain the navigable items. The main document
surface should run almost to the content area's edges with only a small gutter.

## Phase 18 Acceptance

- sidebar group titles have a clearly stronger typographic and structural
  treatment than their chapter links;
- desktop main content keeps only a small horizontal gutter and no broad gray
  side bands;
- responsive navigation still collapses cleanly without horizontal page
  overflow;
- existing Guide routes, content and accessibility states remain intact;
- frontend tests, ESLint, typecheck and production build pass.

## Phase 18 Block

1. GUIDE-5 — Sidebar Hierarchy and Main Surface Spacing.

## Phase 17 Goal

Turn the public Guide into a true documentation workspace. Each user-facing
module must have its own URL and a concise task sequence that explains where to
start, what to do, what success looks like and how to recover from common
failures. The sidebar must be an edge-aligned, full-height navigation surface
rather than an inset table of contents.

## Phase 17 Acceptance

- `/guide` redirects to the Overview guide page and each guide module resolves
  at a distinct `/guide/:section` URL;
- Overview, Discover, Papers and Writing are separate navigable pages;
- Reader, Evidence and troubleshooting remain separate navigable pages;
- every page includes concrete entry instructions, ordered actions, expected
  outcomes and relevant limits/recovery guidance;
- the sidebar is flush with the viewport edge below the global header and uses
  a full-height documentation layout on desktop;
- responsive navigation remains usable at tablet and mobile widths;
- focused content/router tests, ESLint, typecheck and production build pass.

## Phase 17 Block

1. GUIDE-4 — Multi-page Guide Shell and Task-oriented Content.

## Phase 16 Goal

Resolve all verified findings from the Impeccable v4.1.1 technical audit of
the public Guide without changing its restrained information architecture.

## Phase 16 Acceptance

- the Guide has a page-level heading without restoring the removed hero block;
- hash navigation respects reduced-motion preferences;
- Guide navigation meets 44px touch-target guidance on coarse pointers;
- local surface and shadow values use existing `--pa-*` tokens;
- the current visible Guide section is exposed visually and through
  `aria-current="location"`;
- focused tests, detector, lint, build and Docker verification pass.

## Phase 15 Goal

Reduce the Guide's visual density while preserving the module-specific V1
content introduced in Phase 14.

## Phase 15 Acceptance

- remove the redundant top introduction/path selector;
- restore the previous Guide's restrained side navigation and single-column
  reading rhythm;
- remove repeated labels, nested visual groups and unnecessary calls to action;
- preserve clear module boundaries, current product wording and real routes;
- focused tests, lint and frontend build pass.

## Phase Goal

Make the public user guidance match the implemented V1 product model, separate
instructions by user-facing module and synchronize the homepage narrative with
the same capabilities and boundaries.

## Phase 14 Block

1. GUIDE-1 — Modular User Guide and Homepage Capability Narrative

## Phase 14 Acceptance

- the Guide separates Project Overview, Discover, Project Papers, Writing and
  Independent Reading into clear, directly navigable modules;
- the Guide explains Evidence, Citation Verification and durable task status in
  user language without exposing Tool, Skill, raw events or chain-of-thought;
- the homepage presents both supported modes and the canonical
  `Project → Discover → Papers → Writing` workflow;
- homepage and Guide actions route to real product surfaces and make no claims
  beyond implemented behavior;
- keyboard focus, responsive layouts and reduced-motion behavior remain valid;
- focused content tests, frontend lint and typecheck/build pass; responsive,
  focus and reduced-motion behavior are verified in source when browser
  screenshot infrastructure is unavailable.

## Phase 13 Blocks

1. SK-1 — Unified Skill Runtime and Completion Evaluation
2. SK-2 — Writing Reviewer and One Bounded Repair
3. SK-3 — Durable Integration and Acceptance

## Phase Acceptance

- Writing uses the same strict Skill Runtime policy/completion boundary as the
  migrated research Skills;
- a versioned `writing_evidence_generation` Skill declares permissions,
  budgets, criteria and required completion metadata;
- Writing Reviewer produces a typed public-safe verdict;
- a failed review may trigger exactly one repair and never an unbounded loop;
- repaired output still passes Evidence persistence, Citation Verification,
  Skill completion evaluation and Completion Gate;
- durable events expose review/repair outcomes without raw reasoning;
- completion eval fixtures execute real evaluator logic and relevant regression
  suites pass.

## Persistent Product Boundary

The PaperAI V1 Project workspace remains limited to:

1. Overview
2. Literature Discovery
3. Project Papers
4. Writing

Any future Phase must preserve the active product, architecture, ownership,
Reader, retrieval, citation, writing, execution and deployment contracts in
`AGENTS.md` and the active feature specifications.

## Required Phase Setup

Before a future Phase starts:

1. inspect the actual current code;
2. identify one coherent Implementation Block;
3. record the approved Phase, Block goal and acceptance gate here;
4. add the Block-specific specification, source and test boundary to
   `docs/spec-v2/execution/EXECUTION_INDEX.md`;
5. record the baseline commit and target files in
   `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`, then mark the Block
   `IN_PROGRESS`.

Archived plans are historical context only and must not be reused as current
implementation authority.

# PaperAI Execution Index

> Status: COMPLETE / SESSION HANDOFF
>
> This file is the sole entry point for deciding the current PaperAI
> Implementation Block reading boundary. It does not replace active product,
> architecture or feature specifications.

## Session Read Order

Codex must first read:

1. `/AGENTS.md`
2. this file
3. `IMPLEMENTATION_PROGRESS.md`

For the repository-level entrypoint map and test selection rules, read
`docs/architecture/CODE_MAP.md` when the current Block has a matching feature map.

Do not read all active specifications by default. Do not read
`docs/archive/` during normal implementation.

## Current Phase

Phase 25 — Agent Evaluation & Observability.

## Current Implementation Block

PAPER-BOUNDARY-1 — 项目论文隔离、解析容错与失败导入清理。

PAPER-BOUNDARY-1 status: COMPLETE。该维护块只适配现有论文上传、解析、Redis
Worker、任务状态和向量清理能力，不新增第二套论文处理流程；目标是让项目内新建论文
与独立阅读范围分离，清理 PDF 文本中的 PostgreSQL 非法 NUL 字符，并允许用户删除
失败导入留下的任务和文件。

## PAPER-BOUNDARY-1 Reading Boundary

- `backend/app/api/papers.py`
- `backend/app/models/paper.py`
- `backend/app/models/project.py`
- `backend/app/services/paper_files.py`
- `backend/app/services/paper_upload.py`
- `backend/app/services/paper_core_processing.py`
- `backend/app/harness/tools/literature_research.py`
- `backend/app/worker.py`
- `backend/app/utils/task_manager.py`
- `backend/alembic/versions/0011_paper_scope.py`
- `backend/app/infrastructure/db/migrations.py`
- `backend/tests/test_paper_processing_services.py`
- `backend/tests/test_paper_retry.py`
- `backend/tests/test_paper_scope.py`
- `backend/tests/test_paper_router_structure.py`
- `backend/tests/test_database_migrations.py`
- `frontend/src/api/paper.ts`
- `frontend/src/components/PaperUploadModal.vue`
- `frontend/src/components/PaperUploadModal.spec.ts`
- `frontend/src/views/PaperList.vue`
- `frontend/src/views/ProjectPapers.vue`
- `docs/API.md`
- `docs/architecture/CODE_MAP.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- `ProjectPapers` 上传将项目标识传入现有上传接口；新建论文标记为项目专属，不进入
  独立论文列表；已有独立论文加入项目时不改变其独立范围。
- PyMuPDF、pdfplumber、解析器输出、数据库字段和索引输入统一去除 NUL 字符；历史论文
  通过兼容迁移默认保持独立论文语义。
- 失败导入可按所有权删除持久化任务、残留 PDF、向量数据和可能存在的部分论文记录；
  进行中的任务不能被误删，重试仍复用现有 Worker 队列。
- 旧 `/api/v1/papers/upload`、独立 Reading、项目 Papers、Discover/项目 arXiv 导入和
  现有 Redis Worker 调用保持兼容。

ADMIN-EVAL-1 — 管理员测评启动、结果渲染与历史记录。

ADMIN-EVAL-1 status: COMPLETE。复用现有评测脚本、Redis Queue 和 Worker，新增
管理员测评运行记录的持久化接口；前端通过管理员控制台启动测评、轮询结果、渲染完成
报告并显示带日期的历史记录。该 Block 不新增 Agent Runtime、Tool、RAG 或用户侧
Agent 页面。

## ADMIN-EVAL-1 Reading Boundary

- `backend/app/api/admin.py`
- `backend/app/models/evaluation.py`
- `backend/app/application/evaluation_run_service.py`
- `backend/app/application/admin_evaluation_runner.py`
- `backend/app/job_queue.py`
- `backend/app/worker.py`
- `backend/evals/run_agent_runtime_report.py`
- `backend/evals/run_retrieval_eval.py`
- `backend/evals/run_e2e_eval.py`
- `backend/evals/score_e2e_eval.py`
- `backend/alembic/versions/0009_admin_evaluation_runs.py`
- `backend/alembic/versions/0010_admin_evaluation_active_guard.py`
- `backend/app/infrastructure/db/migrations.py`
- `backend/alembic/env.py`
- `backend/scripts/check_schema_revision.py`
- `backend/tests/test_admin_evaluations.py`
- `backend/tests/test_database_migrations.py`
- `frontend/src/api/admin.ts`
- `frontend/src/components/admin/AdminEvaluationPanel.vue`
- `frontend/src/views/AdminDashboard.vue`
- `frontend/src/components/admin/AdminEvaluationPanel.spec.ts`
- `docs/API.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- 管理员可以选择现有 `runtime`、`retrieval` 或 `e2e` 评测类型，创建一条持久化运行
  记录并通过现有 Redis Worker 异步执行；不直接在 API 进程执行长任务。
- Worker 只适配现有评测脚本，结果写入稳定的 JSON/Markdown 报告路径，并把结构化
  汇总和错误写回数据库；队列重试、死信和 Worker 恢复继续由既有基础设施负责。
- API 提供运行记录列表和详情；详情包含完成后的结构化报告，前端显示状态、结果和
  日期，刷新页面后仍可恢复历史记录和当前运行状态。
- 重复点击不会为同一评测类型创建并行运行；重复消费使用稳定运行 ID 和稳定报告路径，
  已完成结果直接复用。旧 `/api/admin/dashboard`、Discover、Reading、Writing
  接口保持兼容。
- 覆盖启动、完成/失败、历史日期、Worker 派发、重试幂等和前端渲染测试；外部
  Provider/LLM 仅在已有配置可用时做真实运行，测试使用确定性 mock。

## EVAL-OBS-4 Reading Boundary

EVAL-OBS-4 — 基于现有 PaperQA 与 Skill Case 建立 Agent 行为约束数据集。

EVAL-OBS-4 status: COMPLETE。该评测数据集只描述三个核心 Goal 的
expected、allowed、forbidden、completion 和 budget 约束，复用现有 PaperQA
问题与 Skill `cases.yaml` 作为输入来源和行为场景，不引入 LLM 自动评分或新的
运行时指标体系。

## EVAL-OBS-4 Reading Boundary

- `backend/evals/datasets/paperqa_v1.jsonl`
- `backend/app/harness/skills/*/evals/cases.yaml`
- `backend/app/harness/skills/*/skill.yaml`
- `backend/app/research/task_contracts.py`
- `backend/app/application/research_planning.py`
- `backend/app/application/research_orchestrator.py`
- `backend/evals/agent_behavior_dataset.py`
- `backend/evals/generate_agent_behavior_dataset.py`
- `backend/evals/validate_agent_behavior_dataset.py`
- `backend/evals/datasets/agent_behavior_v1.jsonl`
- `backend/tests/test_agent_behavior_dataset.py`
- `backend/evals/README.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- 生成约 30–45 条可复现 JSONL Case，平均覆盖 `READ_PAPERS`、
  `WRITE_SECTION`、`DISCOVER_AND_IMPORT` 三个 Goal，并引用现有 PaperQA 与
  Skill Case。
- 每条 Case 只包含声明式 expected/allowed/forbidden/completion/budget 约束；
  不保存 reference answer，不调用 LLM，不自动给 Agent 行为打分。
- 校验器验证来源引用、Goal/task DAG、Skill 工具白名单、任务类型、预算上限、
  用户等待/阻塞约束和禁止评分字段；现有评测数据与 Runtime 不受影响。

## EVAL-OBS-3 Reading Boundary

EVAL-OBS-3 — 将 Agent Runtime 报告收口为诊断优先输出。

EVAL-OBS-3 status: COMPLETE。该维护块保留现有 PostgreSQL trace、运行指标、失败分类
和 Dashboard 基础，把样本有效性作为报告的第一判断。Markdown/HTML 不再默认展示
空指标清单，而是优先回答哪个 Task、Failure、Tool 或资源最需要处理；JSON 继续保留
完整原始指标。

## EVAL-OBS-3 Reading Boundary

- `backend/evals/agent_runtime_metrics.py`
- `backend/evals/agent_runtime_markdown.py`
- `backend/evals/build_dashboard.py`
- `backend/tests/test_agent_runtime_observability.py`
- `backend/tests/test_eval_dashboard.py`
- `backend/evals/README.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- 空样本、仅 Mock 和低于阈值的样本只输出数据质量诊断、缺失数据、真实/Mock 样本
  分类、建议真实链路和 20/50 ResearchTask 阈值。
- 样本充足时只输出六个诊断优先部分和要求的 Task 类型对比列；缺失指标不渲染为 0。
- JSON 报告保留现有详细指标和 trace，静态 Dashboard 不新增用户侧 Agent 页面。

## EVAL-OBS-2 Reading Boundary

EVAL-OBS-2 — 扩展 Agent Runtime 报告的真实数据覆盖、状态诊断和中文可读输出。

EVAL-OBS-2 status: COMPLETE. This maintenance block preserves the existing
runtime and report schema direction, adds AgentEvent and legacy counter
coverage, defaults to the full Execution sample, and emits a human-readable
Chinese Markdown report alongside JSON.

## EVAL-OBS-2 Reading Boundary

- `backend/evals/agent_runtime_metrics.py`
- `backend/evals/agent_runtime_markdown.py`
- `backend/evals/run_agent_runtime_report.py`
- `backend/evals/build_dashboard.py`
- `backend/tests/test_agent_runtime_observability.py`
- `backend/tests/test_eval_dashboard.py`
- `backend/evals/README.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- Default report reads all Execution rows in the selected time/filter range;
  an explicit limit is recorded as truncation.
- Durable AgentEvent, ResearchTask, ToolCall and ModelCall records are
  included, together with legacy AgentExecution counters and their coverage
  gaps.
- JSON remains machine-readable and the static dashboard remains compatible;
  a Chinese Markdown report includes definitions, status distribution,
  coverage diagnostics and execution/task drilldown.
- Empty denominators render as “暂无数据” in Markdown and do not imply a
  zero success rate.

## EVAL-OBS-1 Reading Boundary

EVAL-OBS-1 — add internal Agent Runtime evaluation and observability on the
existing GoalExecution/ResearchTask/Worker path.

EVAL-OBS-1 status: COMPLETE. This block adds task/skill/model/tool trace
correlation, deterministic runtime metrics, failure taxonomy, duplicate-action
observation, and an extension to the existing evaluation dashboard. It does
not add a user-facing Agent Center, a second runtime, an LLM judge, or a new
execution lifecycle.

## EVAL-OBS-1 Reading Boundary

- `backend/app/models/execution.py`
- `backend/app/harness/runtime/tool_runtime.py`
- `backend/app/harness/runtime/task_context.py`
- `backend/app/harness/runtime/task_scope.py`
- `backend/app/harness/runtime/skill_runtime.py`
- `backend/app/harness/agents/lead_agent.py`
- `backend/app/llm/client.py`
- `backend/app/application/research_task_worker.py`
- `backend/app/application/research_task_executors.py`
- `backend/app/application/research_orchestrator.py`
- `backend/app/research/task_contracts.py`
- `backend/alembic/versions/0008_agent_runtime_observability.py`
- `backend/evals/agent_runtime_metrics.py`
- `backend/evals/run_agent_runtime_report.py`
- `backend/evals/build_dashboard.py`
- `backend/tests/test_agent_runtime_observability.py`
- `backend/tests/test_database_migrations.py`
- `backend/tests/test_eval_dashboard.py`
- `backend/tests/test_execution_runtime.py`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Acceptance boundary:

- Existing `AgentExecution` remains the single execution lifecycle and old
  rows remain readable; `ToolCall` gains nullable task/skill correlation and
  `ModelCall` is added as a durable, prompt-free call trace.
- ResearchTask Lead Agent calls are observable through the existing worker
  context; instant legacy paths may remain uninstrumented.
- The generic report reads real PostgreSQL rows and computes execution, task,
  tool, model, budget, duplicate and deterministic failure metrics without a
  quality score or LLM judge.
- The existing Writing evaluator and dashboard remain compatible; the
  dashboard gains an internal Agent Runtime section only.
- Deterministic fixtures cover persistence, aggregation, slices, retries,
  duplicate detection, failure taxonomy, empty data, migration compatibility
  and the current Writing evaluator regression.

## LIFE-1 Reading Boundary

- `backend/app/api/projects.py`
- `backend/app/api/executions.py`
- `backend/app/application/reading_execution_service.py`
- `backend/app/application/research_orchestrator.py`
- `backend/app/application/research_planning.py`
- `backend/app/application/research_task_worker.py`
- `backend/app/application/research_task_executors.py`
- `backend/app/worker.py`
- `backend/app/harness/agents/lead_agent.py`
- `backend/app/api/chat.py`
- `backend/app/api/documents.py`
- `backend/app/application/writing_service.py`
- `backend/tests/test_research_orchestrator.py`
- `backend/tests/test_execution_runtime.py`
- `backend/tests/test_project_contracts.py`
- `backend/tests/test_project_router_structure.py`
- `backend/tests/test_agent_routing.py`
- `frontend/src/api/executions.ts`
- `frontend/src/api/projects.ts`
- `frontend/src/stores/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- `frontend/src/components/project/WritingDocumentEditor.vue`
- `frontend/src/views/ProjectPapers.vue`
- related frontend tests
- `docs/API.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`

## LIFE-1 Reading Boundary

User-authorized scope: project Reading compatibility adapter, project Writing
compatibility adapter, centralized instant-vs-goal entry classification,
GoalExecution progress projection, and minimal Project Papers/Writing/Global
Task Center frontend adaptation. Preserve independent single-paper Reader,
paper Chat, PDF, RAG, Writing, Queue, Worker, TaskScope and Skill Runtime.

Inspect:

- `backend/app/api/projects.py`
- `backend/app/api/executions.py`
- `backend/app/application/reading_execution_service.py`
- `backend/app/application/research_orchestrator.py`
- `backend/app/application/research_planning.py`
- `backend/app/application/research_task_worker.py`
- `backend/app/application/research_task_executors.py`
- `backend/app/worker.py`
- `backend/app/harness/agents/lead_agent.py`
- `backend/app/api/chat.py`
- `backend/app/api/documents.py`
- `backend/app/application/writing_service.py`
- `backend/tests/test_research_orchestrator.py`
- `backend/tests/test_execution_runtime.py`
- `backend/tests/test_project_contracts.py`
- `backend/tests/test_project_router_structure.py`
- `backend/tests/test_agent_routing.py`
- `frontend/src/api/executions.ts`
- `frontend/src/api/projects.ts`
- `frontend/src/stores/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- `frontend/src/components/project/WritingDocumentEditor.vue`
- `frontend/src/views/ProjectPapers.vue`
- related frontend tests
- `docs/API.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`

Acceptance boundary:

- Project Reading API remains compatible but creates only `READ_PAPERS`
  GoalExecution; the old Redis project-reading worker is no longer a new
  lifecycle and is removed or reduced to a compatibility adapter.
- `writing_generate` remains an accepted compatibility input but initializes
  `WRITE_SECTION` through the existing GoalExecution/ResearchOrchestrator;
  new requests do not enqueue an independent writing lifecycle.
- Independent single-paper Q&A, interpretation, summary and short local
  interactions continue through their existing Agent/Workflow paths.
- Project UI reads `status`, `progress`, `blockers`, `completion_reason` and
  `result_payload`; internal WorkerJob, ToolCall, executor and queue concepts
  stay out of user-facing UI.

## ORCH-1 Reading Boundary

- `docs/spec-v2/product/PRODUCT_SCOPE.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/features/PROJECT_CONTEXT_AND_EVIDENCE.md`
- `docs/spec-v2/features/LITERATURE_DISCOVERY.md`
- `docs/spec-v2/features/WRITING_WORKSPACE.md`
- `backend/app/models/`, `backend/app/application/`, `backend/app/research/`
- `backend/app/harness/`, `backend/app/job_queue.py`, `backend/app/worker.py`
- execution, discovery, project and writing APIs and their called services
- migrations, execution/worker/reading/writing/discovery/skill tests
- existing frontend execution API/store/task center and their tests
- `docs/API.md`, `docs/architecture/SKILL_RUNTIME.md`

User-authorized scope: three goal templates, deterministic dependencies, durable
Task/Plan, task-scoped execution, recovery/idempotency, compatible API/progress.
No new provider or execution runtime. Preserve existing uncommitted changes.

## Completed NAV-2 Reading Boundary

- `frontend/src/components/project/ProjectShell.vue`
- `frontend/src/components/project/ProjectShell.spec.ts`
- `frontend/DESIGN_SYSTEM.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

The block changes only the Project Shell's navigation grouping. Routes,
project context, Reader behavior and the global V1 product boundary remain
unchanged.

## PDF-PERF-1 Reading Boundary

- `backend/app/api/papers.py`
- `backend/app/main.py`
- `backend/tests/test_pdf_range.py`
- `frontend/nginx.conf`
- `frontend/src/components/PdfViewer.vue`
- `frontend/src/utils/pdfCache.ts`
- `frontend/src/views/PaperReader.vue`
- `frontend/src/api/paper.ts`
- `frontend/src/utils/pdfCache.spec.ts`
- `docs/API.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Relevant contract: the existing PDF 200/206 endpoint, authenticated Reader
context, manual Cache Storage cache and PDF.js range loading remain the only
PDF delivery path. This block adds no schema or durable telemetry storage.

## Completed READER-TRANSPORT-1 Boundary

- `backend/app/api/papers.py`
- `backend/app/services/paper_files.py`
- `backend/tests/test_pdf_range.py`
- `frontend/src/components/PdfViewer.vue`
- `frontend/src/utils/pdfCache.ts`
- `frontend/src/views/PaperReader.vue`
- `frontend/src/api/paper.ts`

Phase 22 acceptance passed at source/build level and in the rebuilt backend
image: PDF 200/206 responses now use exact lengths and revalidation, range
reads reject short bodies, PDF.js has one bounded full-download recovery path,
stale local cache bytes are discarded, and Reader progress saves are
bounded/deduplicated during teardown. The running services still reference
the previous images; recreate them before browser-level acceptance. The
handoff and deployment checks are recorded in
`IMPLEMENTATION_PROGRESS.md`.

## Completed NAV-1 Boundary

- `frontend/src/router/index.ts`
- `frontend/src/router/reader.ts`
- `frontend/src/components/ProductHeader.vue`
- `frontend/src/components/PaperUploadModal.vue`
- `frontend/src/components/project/ProjectHeader.vue`
- `frontend/src/components/project/ProjectShell.vue`
- `frontend/src/components/project/WritingProposalCard.vue`
- `frontend/src/components/project/WritingDocumentEditor.vue`
- `frontend/src/views/PaperList.vue`
- `frontend/src/views/PaperReader.vue`
- `frontend/src/views/ProjectPapers.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/Guide.vue`
- focused route, Header, upload, project-paper and writing-link tests

Phase 21 acceptance passed: Standalone Reader and Project Reader use explicit
semantic contexts with one Reader implementation; named Back and breadcrumb
locations preserve the correct destination; legacy project query links are
compatible and normalize to the project route; project-only actions and
cross-paper evidence links retain project identity; Project Papers uploads
attach ready papers in the current project; global and project terminology is
consistent; frontend tests, lint, typecheck and production build pass.

## Completed GUIDE-7 Boundary

- `frontend/DESIGN_SYSTEM.md`
- `frontend/src/components/ProductHeader.vue`
- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`

Phase 20 acceptance passed: the Guide top navigation and sidebar are fixed,
the main content reserves both navigation surfaces without overlap, and the
main horizontal gutter is three pixels on desktop and mobile.

## Completed GUIDE-6 Boundary

- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`

Phase 19 acceptance passed: the Guide content starts directly below
`ProductHeader`, the main document has square corners with no card shadow, and
the six-pixel horizontal gutter remains intact across responsive layouts.

## Completed GUIDE-5 Boundary

- `frontend/DESIGN_SYSTEM.md`
- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`

Phase 18 acceptance passed: sidebar group titles are visibly distinct from
chapter links, the desktop main surface has only a six-pixel horizontal gutter,
and existing route-driven content and responsive behavior remain intact.

## Completed GUIDE-4 Boundary

- `docs/spec-v2/product/PRODUCT_SCOPE.md`
- `docs/spec-v2/frontend/UI_SYSTEM.md`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/src/views/Guide.vue`
- `frontend/src/router/index.ts`
- `frontend/src/views/PublicGuidance.spec.ts`
- `frontend/src/router/routes.spec.ts`

Phase 17 acceptance passed: Guide modules use distinct route URLs, the
sidebar is edge-aligned and full-height on desktop, and all seven pages carry
task-oriented entry, action, outcome and recovery guidance. No product API or
backend contract changed.

## Completed GUIDE-3 Boundary

- `frontend/DESIGN_SYSTEM.md`
- `frontend/src/App.vue`
- `frontend/src/router/index.ts`
- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- Phase 16 execution documents

Do not change Guide content, homepage behavior or backend contracts.

## Completed GUIDE-2 Boundary

- `frontend/DESIGN_SYSTEM.md`
- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- previous Guide at commit `9b8a389`
- Phase 15 execution documents

Do not change homepage behavior or product contracts in this Block.

## Completed Phase 14 Acceptance

Read specifications:

- `docs/spec-v2/product/PRODUCT_SCOPE.md`
- `docs/spec-v2/frontend/UI_SYSTEM.md`
- `docs/spec-v2/features/LITERATURE_DISCOVERY.md`
- `docs/spec-v2/features/WRITING_WORKSPACE.md`
- `frontend/DESIGN_SYSTEM.md`

Inspect source:

- `frontend/src/views/Guide.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/router/index.ts`
- existing route/content tests only as required

Block acceptance:

- modular Guide and synchronized homepage copy satisfy Phase 14 acceptance;
- no internal Agent-platform concepts are exposed;
- focused tests, lint and production build pass.

## Completed Phase 13 Acceptance

Read specifications:

- Phase 13 acceptance in `IMPLEMENTATION_PLAN.md`
- Writing/Skill/Execution rules in `/AGENTS.md`
- `docs/API.md` Writing and Execution contracts

Inspect source:

- `backend/app/worker.py`
- `backend/app/application/execution_service.py`
- shared Skill Runtime and Writing Skill
- execution trace/evaluation projection
- related frontend stage labels only if required

Inspect tests:

- Writing, Skill Runtime, execution and quality tests
- repository-supported regression/build/lint commands

Block acceptance:

- durable execution activates `writing_evidence_generation`;
- review/repair stages are durable and replayable;
- Skill completion eval is persisted in result and required by Completion Gate;
- trace/evaluation reports include Skill/reviewer/repair completion evidence;
- complete regression, build and health acceptance pass.

Only make integration changes required by Phase 13 acceptance.

## Active Authority Map

```text
AGENTS.md
→ repository-wide implementation and product boundaries

product / architecture / features / frontend
→ active product, architecture, feature and UI design contracts

execution/IMPLEMENTATION_PLAN
→ latest completed Phase plan

execution/EXECUTION_INDEX
→ no active Block; define the next bounded read boundary before implementation

execution/IMPLEMENTATION_PROGRESS
→ current execution status and latest handoff

archive
→ completed execution history only
```

## Idle-State Rules

- Documentation maintenance may inspect only the documents directly needed.
- Read-only diagnosis may inspect the minimum relevant source and tests.
- Do not modify product behavior while there is no active Implementation Block.
- Define one coherent Block and exact read boundary before future implementation.

## Archived Execution History

- Archive index:
  `docs/archive/spec-v2/README.md`
- Phase 0–9 plans and progress:
  `docs/archive/spec-v2/`
- Phase 10 plan:
  `docs/archive/spec-v2/07_CODEX_IMPLEMENTATION_PLAN_PHASE_10.md`
- Phase 10 progress:
  `docs/archive/spec-v2/08_IMPLEMENTATION_PROGRESS_PHASE_10.md`
- Phase 10 execution index:
  `docs/archive/spec-v2/EXECUTION_INDEX_PHASE_10.md`

Archived documents are historical only. They must not override active
specifications or be used to reopen completed Blocks.

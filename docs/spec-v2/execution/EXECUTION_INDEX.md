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

Do not read all active specifications by default. Do not read
`docs/archive/` during normal implementation.

## Current Phase

Phase 25 — Agent Evaluation & Observability.

## Current Implementation Block

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

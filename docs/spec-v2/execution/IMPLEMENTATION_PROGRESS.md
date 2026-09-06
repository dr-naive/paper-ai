# PaperAI Implementation Progress Ledger

Status: COMPLETE

## Current State

Current Phase: Phase 25 — Agent Evaluation & Observability

Current Implementation Block: EVAL-OBS-1

Current Block Status: COMPLETE

Baseline commit: `f579d0e` (`完善项目阅读写作执行链路`).

Target migration: `0008_agent_runtime_observability`.

End state: EVAL-OBS-1 is complete in the local worktree; the final local
commit is recorded by Git after this ledger update. No remote push was made.

Actual files changed:

- `backend/alembic/versions/0008_agent_runtime_observability.py`
- `backend/app/models/execution.py`
- `backend/app/infrastructure/db/migrations.py`
- `backend/app/application/research_task_worker.py`
- `backend/app/harness/runtime/task_context.py`
- `backend/app/harness/runtime/tool_runtime.py`
- `backend/app/harness/agents/lead_agent.py`
- `backend/app/llm/client.py`
- `backend/evals/agent_runtime_metrics.py`
- `backend/evals/run_agent_runtime_report.py`
- `backend/evals/build_dashboard.py`
- `backend/evals/README.md`
- `backend/tests/test_agent_runtime_observability.py`
- `backend/tests/test_database_migrations.py`
- `backend/tests/test_research_orchestrator.py`
- `backend/tests/test_eval_dashboard.py`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Database changes: additive Alembic migration `0008_agent_runtime_observability`
adds nullable `tool_calls.task_id` and `tool_calls.skill_id`, a nullable task
foreign key with `SET NULL`, a task-step index, and durable `model_calls` with
execution/task/Skill correlation, call index, model/provider/purpose, token
counts, status, timestamps, duration, error code and optional prompt version.
Historical ToolCall and AgentExecution rows remain readable. The current
database reports `0008_agent_runtime_observability (head)` and schema preflight
`compatible: true`.

Core call-chain changes: the existing ResearchTask Worker sets task/Skill
ContextVars; task-scoped `invoke_with_retry` records prompt-free ModelCall
start/finish events; the Lead Agent records its existing tool dispatches into
the existing ToolCall table with task/Skill correlation; the generic
ToolRuntime persists rejected attempts and authoritative context fields. The
new CLI reads these existing PostgreSQL tables and produces deterministic
runtime metrics. ResearchOrchestrator, Queue, WorkerJob, TaskResult and the
Writing evaluator lifecycle were not replaced.

Metrics and coverage: the report includes execution status/duration rates,
task success/partial/failure/retry and slices by task type/Skill/executor,
Tool success/failure/timeout/input-invalid/latency/calls-per-task,
Model calls/tokens/errors/latency, budget utilization and near-budget task
lists, same-task duplicate successful actions, stable failure taxonomy and
execution/task/trace drilldown. The tested taxonomy covers argument error,
timeout, tool failure, scope violation, budget exceeded, duplicate action,
incomplete task and `UNKNOWN`. The live empty sample had
`UNKNOWN=0`; deterministic fixtures cover non-zero classifications.

Three target chains: existing deterministic integration coverage for
`READ_PAPERS`, `WRITE_SECTION` and `DISCOVER_AND_IMPORT` remains green through
the Orchestrator test scenarios (`adapter_read`, `adapter_write`,
`adapter_build`, `adapter_discover`) and the complete backend suite. This
observability block adds no new Goal lifecycle or product entry point.

Reused old capabilities: AgentExecution cumulative counters, ResearchTask,
Redis Queue/WorkerJob retry and dead-letter behavior, checkpoint/recovery,
TaskScope, Skill Runtime, existing Lead Agent, Writing workflow, Writing
trace evaluator, existing static evaluation dashboard and schema preflight.

Deleted/deprecated logic: none. No PaperQA/Citation evaluator, old execution
state, Goal lifecycle, RAG or product UI was removed.

Tests and checks:

- backend complete suite: `348 passed`;
- focused observability/migration/dashboard/runtime tests: `20 passed`;
- targeted backend Ruff: passed;
- frontend complete suite: `79 passed` across 19 files;
- frontend typecheck and lint: passed;
- frontend production build and backend/worker/frontend image builds: passed;
- real report command: generated JSON with sample size
  `executions=5, tasks=0, tool_calls=0, model_calls=0, failure_records=0`;
- migration current and schema preflight: passed.

Uncovered paths and remaining risks: instant Reader/Chat and legacy
`LLMClient.agenerate` workflow calls may remain without fine-grained ModelCall
rows by design; their existing AgentExecution counters remain available.
The local database had no ResearchTask trace rows, so live provider/model
behavior and real Lead Agent trace volume were not validated. External model
credentials were not used. No frontend Agent Runtime product UI was added.

Required report command: `cd backend && python -m evals.run_agent_runtime_report`.

Exact next action: none for EVAL-OBS-1. A future block may instrument the
remaining compatible `agenerate` paths if their trace coverage becomes a
requirement. Remote push still requires a separate Chinese description and
explicit user approval.

## Completed Block — EVAL-OBS-1

Goal achieved: the first internal Agent Evaluation & Observability block is
complete without adding a second Agent Runtime, user Agent Center, LLM judge,
chain-of-thought storage or a parallel execution lifecycle.

Last Completed Phase: Phase 25 — Agent Evaluation & Observability

Last Completed Implementation Block: EVAL-OBS-1 — Agent Evaluation &
Observability

Last Completed Implementation Commit: 当前本地提交 — 完成 Agent 运行评测与观测。
Baseline commit was `f579d0e`; exact local commit ID is the current Git HEAD.

## Completed Block — LIFE-1

Baseline commit: `90cedc1`.

Goal achieved: project Reading and Writing now enter the existing GoalExecution
/ ResearchOrchestrator lifecycle; the duplicate project-reading execution loop
was removed; the instant-interaction boundary is explicit; and project UI reads
durable GoalExecution projections.

Actual files changed:

- Backend entry and lifecycle adapters: `backend/app/application/project_execution_entrypoint.py`, `backend/app/api/projects.py`, `backend/app/application/reading_execution_service.py`, `backend/app/api/executions.py`, `backend/app/worker.py`.
- Existing task capability boundary: `backend/app/application/research_task_executors.py`.
- Instant interaction boundary: `backend/app/api/chat.py`, `backend/app/api/paper_analysis.py`, `backend/app/api/documents.py`.
- Backend tests: `backend/tests/test_project_lifecycle_closure.py`, `backend/tests/test_execution_runtime.py`, `backend/tests/test_research_orchestrator.py`.
- Frontend GoalExecution projection: `frontend/src/api/executions.ts`, `frontend/src/api/projects.ts`, `frontend/src/stores/executions.ts`, `frontend/src/stores/stores.spec.ts`, `frontend/src/components/GlobalTaskCenter.vue`, `frontend/src/components/project/WritingDocumentEditor.vue`, `frontend/src/views/ProjectPapers.vue`, `frontend/src/views/ProjectPapers.spec.ts`.
- Documentation: `docs/API.md`, `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`, `docs/spec-v2/execution/EXECUTION_INDEX.md`, `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`.

Database changes: none. Existing `AgentExecution` and `research_tasks` schema
remain unchanged; no migration was needed, and historical executions remain
readable.

Core call-chain changes:

- Project Reading compatibility endpoints now create/read/control only a
  `READ_PAPERS` GoalExecution. The old Redis reading state and direct project
  Reading Worker loop were removed. Each `READ_PAPER` remains a persisted
  ResearchTask and uses the existing TaskScope Lead Agent path; paper processing
  and indexing are reused before reading.
- `writing_generate` remains accepted at the existing execution API, but is
  resolved to `WRITE_SECTION` and initialized by ResearchOrchestrator. New
  project writing requests do not enqueue the old independent writing worker
  lifecycle. The canonical Writing editor now creates `research_goal` with
  `WRITE_SECTION` and reads its durable result/progress.
- Single-paper Q&A, summary, interpretation and selection rewrite remain
  instant Agent/Workflow paths and are explicitly classified without creating a
  GoalExecution.
- SSE and frontend streaming stop at `waiting_user`, `blocked` and `paused`,
  so the same execution can be resumed instead of leaving a page in a false
  running state.

Reused old capabilities: AgentExecution, ResearchOrchestrator, ResearchTask,
Redis Queue/WorkerJob, retry/dead-letter, checkpoint, trace, TaskScope, Skill
Runtime, paper processing/indexing, RAG/Evidence, WritingService,
WritingDocument/revision, Citation Audit and existing instant Reader/Chat
workflows. No second orchestrator, recovery manager, RAG, writing runtime or
worker system was added.

Deleted/deprecated logic: the old `handle_project_reading_execution` loop,
Redis `paperai:reading-execution:*` state and new project writes to the
independent `agent_execution_v2` writing lifecycle are gone. The historical
`agent_execution_v2` handler remains only as a compatibility adapter that
converts queued legacy rows into the unified GoalExecution path.

Tests and checks:

- Backend complete suite: `339 passed` in the rebuilt backend image.
- Frontend complete suite: `79 passed` across 19 files.
- Frontend `npm run lint`: passed.
- Frontend `npm run typecheck`: passed.
- Frontend `npm run build`: passed.
- Targeted backend Ruff check: passed.
- Python compile and `git diff --check`: passed.
- Docker backend/worker rebuild: passed.

Target chain acceptance:

- `READ_PAPERS`: indexed papers reuse existing Paper Cards; incomplete paper
  processing waits/retries through the existing processing path; no old project
  Reading lifecycle is created.
- `WRITE_SECTION`: existing Evidence skips evidence building; indexed-only
  papers create `BUILD_EVIDENCE → WRITE_SECTION → AUDIT_DRAFT`; no usable
  papers become blocked without automatic Discover.
- `DISCOVER_AND_IMPORT`: discovery remains structured and import confirmation
  resumes the same execution through `waiting_user`.
- Independent Reader/Chat/PDF/RAG/Writing regressions remain covered by the
  complete suites.

Manual acceptance: source-level call-chain inspection and deterministic
integration fixtures passed for asset reuse, TaskScope reading, retry,
interruption/recovery, duplicate queue delivery, partial output, cancel,
pause/resume, blocked, waiting-user response and old execution compatibility.
Live provider/model acceptance was not attempted because the local environment
does not provide the configured external credentials.

Remaining compatibility: the stable synchronous
`/projects/{project_id}/writing/agent/generate` proposal endpoint and the
frontend `createWriting` helper remain available for older callers; they are
not used by the canonical editor and do not create the old independent
`agent_execution_v2` lifecycle. They can be removed in a later compatibility
cleanup after downstream callers migrate.

Exact next action: none for LIFE-1. Remote push still requires a separate
Chinese description and explicit user approval.

## Completed Block — ORCH-1

Start commit: `479acce28a8bdb24ee786d387cbd6951d18014d0`, with pre-existing
uncommitted Reader/navigation changes preserved. End state: working tree remains
uncommitted by explicit user instruction.

Scope completed: AgentExecution was extended in place as the
ResearchExecution/GoalExecution lifecycle; durable Execution Plan and typed
ResearchTask were added; existing Redis Queue, WorkerJob, retry, dead-letter,
checkpoint, trace, pause/cancel and recovery paths were reused. GoalResolver,
ProjectStateReader, DependencyResolver, PlanBuilder, TaskDispatcher and
CompletionEvaluator now form the lifecycle layer. Existing Discovery, import,
paper processing/indexing, Lead Agent, WritingService, Evidence/RAG and citation
final-gate capabilities are adapters, not duplicated implementations.

Actual ORCH files changed:

- `backend/alembic/versions/0007_research_tasks.py`
- `backend/app/models/execution.py`
- `backend/app/research/task_contracts.py`
- `backend/app/application/research_planning.py`
- `backend/app/application/research_orchestrator.py`
- `backend/app/application/research_task_executors.py`
- `backend/app/application/research_task_worker.py`
- `backend/app/application/reading_execution_service.py`
- `backend/app/application/execution_service.py`
- `backend/app/api/executions.py`
- `backend/app/worker.py`
- `backend/app/harness/agents/lead_agent.py`
- `backend/app/harness/runtime/task_context.py`
- `backend/app/harness/runtime/task_scope.py`
- `backend/app/harness/runtime/skill_runtime.py`
- `backend/app/harness/skills/*/skill.yaml`
- `frontend/src/api/executions.ts`
- `frontend/src/stores/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- `backend/tests/test_research_orchestrator.py`
- `backend/tests/test_execution_runtime.py`
- `backend/tests/test_database_migrations.py`
- `docs/API.md`
- `docs/architecture/SKILL_RUNTIME.md`
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`

Database: additive `0007_research_tasks` adds nullable
`agent_executions.plan/progress/blockers/completion_reason`, non-null
`plan_version` with default `0`, and `research_tasks` with structured refs,
attempt/error/completion fields and execution indexes. Historical execution
rows remain readable; local PostgreSQL was upgraded from `0006_execution_io`
to `0007_research_tasks` through Alembic and schema preflight reports
`compatible: true`.

API: `research_goal` was accepted beside legacy `writing_generate` on the
existing execution endpoint. The later LIFE-1 block moved that compatibility
input onto the same GoalExecution path; Goal executions persist plans/tasks and
use `/respond` for waiting-user recovery. Public execution serialization
exposes progress/blocker projections but keeps the internal plan/DAG
server-side.

Tests and checks executed:

- backend complete suite: `333 passed`;
- focused Goal/Execution/Migration tests: included in the complete suite;
- backend targeted Ruff check: passed;
- frontend Vitest: `78 passed` across 19 files;
- frontend typecheck: passed;
- frontend ESLint: passed;
- frontend production build: passed;
- Docker builds: backend, worker, migrate and frontend passed;
- `alembic current`: `0007_research_tasks (head)`;
- `python -m scripts.check_schema_revision`: compatible;
- `git diff --check`: passed;
- live Docker health: backend, worker, PostgreSQL, Redis healthy; `/health`
  returned healthy and frontend returned HTTP 200.

Manual/chain acceptance:

- `READ_PAPERS`: indexed papers reuse ready Paper Cards; incomplete papers
  wait for the incumbent processing/index worker before the task retries;
  Lead Agent is task-scoped and returns structured Paper Card refs.
- `WRITE_SECTION`: existing Evidence skips BUILD_EVIDENCE; indexed-only
  projects execute BUILD_EVIDENCE → WRITE_SECTION → AUDIT_DRAFT; no usable
  papers persist a blocked execution and never auto-discover.
- `DISCOVER_AND_IMPORT`: DISCOVER returns normalized structured results;
  IMPORT_PAPER waits for selection by default and resumes the same execution,
  rather than importing every result.
- Duplicate queue delivery, interrupted workers, task retry, partial output,
  cancel, pause/resume, blocked dependencies, waiting-user response and
  startup recovery are covered by isolated PostgreSQL integration tests.

Deviations from spec: no separate RecoveryManager or new provider/runtime was
introduced. `paused` remains as a compatibility execution/task state.

Remaining risks: the three adapter chains are validated with deterministic
fixtures/mocked provider/model responses; live model/provider acceptance still
depends on the deployment's configured LLM credentials and provider quota.
No new external dependency was added.

Exact next action: none for ORCH-1. If the user requests a new block, start
from this ledger and keep the existing uncommitted Reader/navigation changes.

## Completed Block — READER-TRANSPORT-1

Start Commit: `4985c30` baseline plus the existing uncommitted GUIDE/NAV
working tree

End Commit: working tree (uncommitted by explicit user instruction)

Scope: make PDF delivery resilient to stale/partial range responses and make
Reader progress persistence safe during route teardown, without adding a new
Reader implementation or changing the paper/status API payload contract.

Actual files changed:

- `backend/app/api/papers.py`
- `backend/app/services/paper_files.py`
- `backend/tests/test_pdf_range.py`
- `frontend/src/components/PdfViewer.vue`
- `frontend/src/utils/pdfCache.ts`
- `frontend/src/views/PaperReader.vue`
- `frontend/src/api/paper.ts`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`

Database migrations: none.

API changes: no request/response schema changes. PDF responses now use
revalidating cache headers, explicitly advertise the full-body length, and
materialize a verified 206 range body before sending it. A file mutation while
reading a range returns a retryable 503 instead of a mismatched body.

Tests and checks executed:

- frontend typecheck: passed;
- frontend ESLint: passed;
- complete frontend suite: `69 passed` across 16 files;
- frontend production build: passed;
- `node --check` on the generated PDF worker and PdfViewer chunks: passed;
- `python3 -m py_compile` on changed backend modules/tests: passed;
- `docker compose build backend worker frontend`: passed;
- targeted tests in the rebuilt backend image (`test_pdf_range.py`,
  `test_app.py`, `test_paper_router_structure.py`): `10 passed`;
- `git diff --check`: passed;

Manual acceptance:

- PDF.js keeps range loading as the fast path and automatically retries once
  with a cache-busted complete PDF when a range/network response fails;
- the manual PDF cache uses a new namespace, rejects non-PDF cached bytes and
  no longer stores a hand-written `Content-Length` header;
- the Reader adds a stable transport-version query parameter to invalidate
  old immutable browser cache entries;
- reading progress uses a dedicated 8-second timeout, reuses an in-flight
  save during unmount and falls back to localStorage without logging a teardown
  timeout as an application error.

Deviations from spec: none.

Remaining risks: the new images are built, but the currently running backend,
worker and frontend containers still reference the previous image IDs because
services were not recreated in this session. No browser network trace was
available. The deployed environment must recreate the three services once,
then verify a PDF request's 200/206 `Content-Length` against the received byte
count.

Historical handoff action completed by PDF-PERF-1: Docker images were rebuilt,
the three services were recreated, and the running Reader transport was
verified from the new backend/frontend images.

## Completed Block — PDF-PERF-1

Start Commit: `4985c30` baseline plus the existing uncommitted GUIDE/NAV and
Reader transport working tree

End Commit: working tree (uncommitted by explicit user instruction)

Block Status: COMPLETE

Scope: restore a reusable PDF cache fast path (including safe legacy-cache
migration), keep the range path resilient while reducing avoidable requests,
remove access tokens from new PDF URLs, expose client first-page timing to the
backend, add server timing/request logs, and recreate the services with the
current source.

Target files:

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
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Database migrations: none planned.

API changes: add the authenticated, best-effort
`POST /api/v1/papers/{paper_id}/pdf/telemetry` log-only endpoint for client
load metrics. Existing PDF request and response contracts remain compatible.

Tests and checks executed:

- frontend PDF cache tests: `5 passed`;
- complete frontend suite: `74 passed` across 17 files;
- frontend ESLint: passed;
- frontend typecheck: passed;
- frontend production build: passed;
- backend complete suite: `308 passed`;
- backend PDF/route targeted suite: `7 passed`;
- backend changed-file `py_compile`: passed;
- Docker image build for `backend worker frontend`: passed;
- `docker compose config --quiet`: passed;
- running frontend `nginx -t`: passed;
- running backend OpenAPI contains the telemetry route: passed;
- PDF route smoke returned `Server-Timing`;
- `git diff --check`: passed.

Manual acceptance:

- backend, worker and frontend were force-recreated from the new images;
- all three application services are running, and backend/worker healthchecks
  report healthy; database, Redis and data volumes were preserved;
- the PDF URL now stays stable and contains no access token; PDF.js sends the
  token through `Authorization` headers;
- valid v1 Cache Storage entries remain readable and are promoted to v2;
  invalid entries are removed; network PDFs are warmed during idle time after
  the first page is usable;
- PDF.js keeps a resilient 2 MiB range path, reports real loading progress,
  and emits cache/document/first-page timings;
- backend logs expose `pdf_request` app latency and
  `pdf_client_load` user-visible latency; Nginx logs expose request and
  upstream durations without query strings.

Deviations from spec: none. Telemetry is internal log-only observability and
does not create a new product surface or durable data model.

Remaining risks: browser-level visual interaction was not automated because
the available Chromium image lacks a required system library. Cache Storage
may still be unavailable on an insecure non-localhost origin; the existing
browser HTTP cache and PDF.js range path remain the fallback. The repository's
optional targeted `ruff check` still reports its pre-existing E402/F401/F541
violations outside this block.

Exact next action: hard-refresh the browser once, open one Project Paper twice,
and inspect the second open for `pdf_client_load ... source=cache`; use
`docker compose logs -f backend frontend` to watch `app_ms`, `request_time`,
`upstream_time` and `total_ms` without exposing URL tokens.

## Completed Block — NAV-2

Start Commit: `4985c30` baseline plus the existing uncommitted working tree

Scope: separate the global Home entry from the Project/Independent Reading
workspace navigation, keep Recent Projects as contextual navigation, remove
the duplicate Independent Reading footer link, and preserve collapsed-sidebar
behavior and route semantics.

Actual files changed:

- `frontend/src/components/project/ProjectShell.vue`
- `frontend/src/components/project/ProjectShell.spec.ts`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Database migrations: none.

API changes: none.

Tests and checks executed:

- focused ProjectShell test: `2 passed`;
- complete frontend suite: `76 passed` across 18 files;
- frontend typecheck: passed;
- frontend ESLint: passed;
- frontend production build: passed;
- `git diff --check`: passed;
- frontend Docker image build and forced container recreation: passed;
- running frontend `nginx -t`: passed;
- runtime smoke checks: frontend HTTP 200; backend, database, Redis and worker
  healthy.

Manual acceptance:

- 首页 is now a standalone global entry;
- 项目 and 独立阅读 are grouped under 工作区;
- 最近项目 remains contextual to the project workspace;
- the duplicate footer 独立阅读 entry is removed;
- route targets, current-project highlighting and collapsed-sidebar behavior
  remain unchanged.

Deviations from spec: none. No API or database changes.

Remaining risks: browser-level visual interaction was not automated because
the available Chromium image lacks a required system library. Source tests,
production build and the rebuilt running frontend container passed.

Exact next action: hard-refresh the browser and inspect the updated Project
Shell sidebar once.

## Completed Block — NAV-1

Start Commit: `4985c30` baseline plus the uncommitted GUIDE-4/5/6/7 working tree

End Commit: working tree (uncommitted by explicit user instruction)

Scope: establish explicit Standalone Reader and Project Reader navigation
contexts while keeping one `PaperReader.vue` implementation; make Back and
breadcrumb inputs typed Vue Router locations; preserve project identity and
Project-only actions; keep legacy `/paper/:id` deep links compatible; and make
local PDF upload from Project Papers upload and attach the paper in the active
Project instead of redirecting to `/library`.

Actual files changed:

- `frontend/src/router/index.ts`
- `frontend/src/router/reader.ts`
- `frontend/src/components/ProductHeader.vue`
- `frontend/src/components/ProductHeader.spec.ts`
- `frontend/src/components/PaperUploadModal.vue`
- `frontend/src/components/PaperUploadModal.spec.ts`
- `frontend/src/components/project/ProjectHeader.vue`
- `frontend/src/components/project/ProjectShell.vue`
- `frontend/src/components/project/WritingProposalCard.vue`
- `frontend/src/components/project/WritingProposalCard.spec.ts`
- `frontend/src/components/project/WritingDocumentEditor.vue`
- `frontend/src/views/PaperList.vue`
- `frontend/src/views/PaperReader.vue`
- `frontend/src/views/ProjectPapers.vue`
- `frontend/src/views/ProjectPapers.spec.ts`
- `frontend/src/views/ProjectOverview.vue`
- `frontend/src/views/ResearchProjectList.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- `frontend/src/api/paper.ts`
- `frontend/src/router/routes.spec.ts`
- `docs/spec-v2/frontend/UI_SYSTEM.md`
- execution documents in `docs/spec-v2/execution/`

Database migrations: none.

API changes: none. The existing paper upload/task-status and
`POST /api/v1/projects/{project_id}/papers` contracts are reused.

Tests and checks executed:

- focused navigation/upload/writing link tests: `26 passed`;
- complete frontend suite: `69 passed` across 16 files;
- `npm run lint`: passed;
- `npm run typecheck`: passed;
- `npm run build`: passed;
- `git diff --check`: passed;
- Impeccable v4.1.1 detector: one pre-existing Writing editor blockquote
  `border-left` warning; no new finding in the changed navigation/upload UI;
- Docker manual check was not available because this execution account cannot
  access `/var/run/docker.sock` (`permission denied`).

Manual acceptance:

- Independent Reading enters `/paper/:id`, displays an `独立阅读 → 阅读`
  hierarchy and returns to the named `PaperList` location.
- Project Papers enters `/projects/:projectId/papers/:paperId/read`, renders
  the same Reader component, loads the project title, preserves project-only
  evidence/note/compare actions and returns to the named current Project
  Papers location.
- Legacy `/paper/:id?project_id=...` links redirect to the semantic project
  route while preserving session/message/prompt query state.
- Cross-paper citation links choose the current Reader context rather than
  opening a standalone page from a Project Reader.
- Project Papers local upload stays in the project, waits for the real task
  terminal-ready state, attaches the paper, emits a refresh and uses project
  terminology; Independent Reading reuses the same upload modal without
  changing its global context.

Deviations from spec: none.

Remaining risks: browser screenshot/manual visual verification was not run in
this container; Docker daemon access is required for container-level smoke
checks. A user navigating away before a project upload reaches ready still
needs the existing task recovery surface to reattach it, because the current
backend upload contract has no atomic project-id field.

Exact next action: review the two Reader deep links and the Project Papers
upload flow in a browser with the normal Docker/dev environment; no commit was
created.

## Completed Block — GUIDE-7

Start Commit: `4985c30` baseline plus the uncommitted GUIDE-4/5/6 working tree

End Commit: working tree (uncommitted by explicit user instruction)

Scope: fix the Guide top navigation and desktop/sidebar navigation to the
viewport, reserve their layout space, and reduce the main surface's horizontal
gutter to three pixels without changing Guide routes or content.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Tests and checks executed:

- focused Guide/router tests: `21 passed`;
- frontend ESLint: passed;
- frontend typecheck: passed;
- frontend production build: passed;
- Impeccable v4.1.1 detector: `[]` for `Guide.vue`;
- Docker frontend image build and `docker compose up -d --no-deps frontend`:
  passed;
- `GET /guide/overview` and `GET /guide/discover`: HTTP `200`.

Manual acceptance: the top navigation stays fixed at the viewport top; the
sidebar stays fixed below it on desktop and transforms into a fixed horizontal
navigation strip on smaller screens; the main document starts after the fixed
navigation stack, has square corners and keeps a three-pixel horizontal
gutter.

Database migrations: none.

API changes: none.

Deviations from spec: none.

Remaining risk: automated pixel screenshots remain unavailable because the
container Chromium lacks `libatk-1.0.so.0`; source, tests, build and live HTTP
checks passed.

Exact next action: review the fixed Guide at `/guide/overview`; no commit has
been created.

## Completed Block — GUIDE-6

Start Commit: `4985c30` baseline plus the uncommitted GUIDE-4/5 working tree

End Commit: working tree (uncommitted by explicit user instruction)

Scope: remove the Guide main area's top gray gap and rounded-card treatment so
the reading surface connects directly below the global header, while retaining
the small horizontal gutter.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Tests and checks executed:

- focused Guide/router tests: `21 passed`;
- frontend ESLint: passed;
- frontend typecheck: passed;
- frontend production build: passed;
- Impeccable v4.1.1 detector: `[]` for `Guide.vue`;
- Docker frontend image build and `docker compose up -d --no-deps frontend`:
  passed;
- `GET /guide/overview` and `GET /guide/writing`: HTTP `200`.

Manual acceptance: the Guide begins immediately beneath the global header,
the main document has square corners and no card shadow, and the six-pixel
horizontal gutter remains on desktop and mobile.

Database migrations: none.

API changes: none.

Deviations from spec: none.

Remaining risk: automated pixel screenshots remain unavailable because the
container Chromium lacks `libatk-1.0.so.0`; source, tests, build and live HTTP
checks passed.

Exact next action: review the updated Guide in the browser; no commit has been
created.

## Completed Block — GUIDE-5

Start Commit: `4985c30` baseline plus the uncommitted GUIDE-4 working tree

End Commit: working tree (uncommitted by explicit user instruction)

Scope: increase the visual distinction between sidebar group headings and
chapter links, and reduce the desktop Guide main surface's horizontal gutter to
only a few pixels while preserving responsive behavior.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Tests and checks executed:

- focused Guide/router tests: `21 passed`;
- frontend ESLint: passed;
- frontend typecheck: passed;
- frontend production build: passed;
- Impeccable v4.1.1 detector: `[]` for `Guide.vue`;
- Docker frontend image build and `docker compose up -d --no-deps frontend`:
  passed;
- `GET /guide/overview` and `GET /guide/writing`: HTTP `200`.

Manual acceptance: desktop sidebar group titles now have stronger typography
and a neutral divider, chapter links are visibly indented beneath them, and
the main document runs almost edge-to-edge with a six-pixel horizontal gutter.

Database migrations: none.

API changes: none.

Deviations from spec: none.

Remaining risk: automated pixel screenshots remain unavailable because the
container Chromium lacks `libatk-1.0.so.0`; source, tests, build and live HTTP
checks passed.

Exact next action: review the updated Guide in the browser; no commit has been
created.

## Completed Block — GUIDE-4

Start Commit: `4985c30`

End Commit: working tree (uncommitted by explicit user instruction)

Scope: replace the same-page Guide anchor list with distinct documentation
routes and an edge-aligned full-height sidebar. Rewrite each module as a
task-oriented page with entry point, ordered actions, expected result and
recovery/limitations guidance.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `frontend/src/router/index.ts`
- `frontend/src/views/PublicGuidance.spec.ts`
- `frontend/src/router/routes.spec.ts`
- `docs/spec-v2/execution/EXECUTION_INDEX.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`

Tests and checks executed:

- focused Guide/router tests: `21 passed`;
- complete frontend suite: `63 passed` across 13 files;
- frontend ESLint: passed;
- frontend typecheck: passed;
- frontend production build: passed;
- Impeccable v4.1.1 detector: `[]` for `Guide.vue`;
- Docker frontend image build and `docker compose up -d --no-deps frontend`:
  passed;
- `GET /guide` and `GET /guide/discover`: HTTP `200`.

Manual acceptance: desktop navigation is flush with the left viewport edge and
fills the area below the global header; Overview, Discover, Papers, Writing,
PDF Reader, Evidence/task status and Troubleshooting each have a distinct URL;
sidebar and previous/next links navigate between pages; page content explains
where to enter, what to do, what success looks like and how to recover.

Database migrations: none.

API changes: none.

Deviations from spec: none.

Remaining risk: automated pixel screenshots remain unavailable because the
container Chromium lacks `libatk-1.0.so.0`; source, tests, build and live HTTP
checks passed.

Exact next action: review `/guide/overview`, `/guide/discover`,
`/guide/papers` and `/guide/writing` in the browser; commit only if the user
explicitly requests it or this work is promoted to a larger refactor.

## Completed Block — GUIDE-3

Start Commit: `88709b1`

End Commit: `8d70d4a`

Scope: remediate the five verified Guide audit findings covering heading
semantics, reduced motion, coarse-pointer target size, design tokens and
current-section orientation.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `frontend/src/router/index.ts`
- `frontend/src/views/PublicGuidance.spec.ts`
- `frontend/src/router/routes.spec.ts`
- Phase 16 execution documents

Tests and checks executed:

- focused Guide/router tests: `12 passed`;
- complete frontend suite: `54 passed` across 13 files;
- frontend ESLint: passed;
- frontend typecheck and production build: passed;
- Impeccable v4.1.1 detector: only the verified false-positive warning for the
  project-required incumbent Inter font remains;
- Docker frontend image build and container recreation: passed;
- `GET http://127.0.0.1:5173/guide`: HTTP `200`.

Manual acceptance: page-level `h1` is available to assistive technology
without restoring a visual hero; reduced-motion anchor navigation is instant;
coarse-pointer Guide links are at least 44px high; surfaces and shadows use
existing design tokens; the visible section is reflected by sidebar styling
and `aria-current="location"`.

Re-audit result: all five verified findings are resolved. Accessibility,
performance, responsive design, theming and implementation integrity now score
`20/20` for the audited Guide scope.

Deviations from spec: none.

Remaining risk: automated screenshot capture remains unavailable in this
container because the bundled Chromium lacks `libatk-1.0.so.0`; compile,
component, source and live HTTP checks passed.

Exact next action: review the rebuilt Guide in the browser and proceed to a new
bounded block only if visual feedback identifies another concrete issue.

Target files:

- `frontend/src/views/Guide.vue`
- `frontend/src/router/index.ts`
- `frontend/src/views/PublicGuidance.spec.ts`
- `frontend/src/router/routes.spec.ts`
- Phase 16 execution documents

Database migrations: none.

API changes: none.


## Completed Block — GUIDE-2

Start Commit: `f2a9141`

End Commit: `d7faf9f`

Scope: remove the redundant Guide introduction/path selector, flatten module
content and restore the calmer visual structure of the pre-Phase-14 Guide.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- Phase 15 execution documents

Tests and checks executed:

- focused public guidance component tests: `2 passed`;
- frontend ESLint: passed;
- frontend typecheck and production build: passed;
- Docker frontend image build and container recreation: passed;
- `GET http://127.0.0.1:5173/guide`: HTTP `200`.

Manual acceptance: removed the complete top introduction/path selector and the
bottom CTA group; navigation now contains labels only; module content uses one
reading column with restrained notes and definition rows; current Project,
Discover, Papers, Writing, Reader, Evidence and task-status guidance remains.

Deviations from spec: none.

Remaining risk: none specific to this Block.

Exact next action: review the rebuilt Guide at port `5173` and collect further
visual feedback before changing its information density again.

Target files:

- `frontend/src/views/Guide.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- Phase 15 execution documents

Database migrations: none.

API changes: none.


## Completed Block — GUIDE-1

Start Commit: `9b8a389`

End Commit: `dbe7a32`

Completed scope: replaced the Reader-only Guide structure with module-specific V1
guidance and aligned the public homepage with the same two-mode product model and
implemented quality/traceability capabilities.

Target files:

- `frontend/src/views/Guide.vue`
- `frontend/src/views/Home.vue`
- focused frontend content tests
- Phase 14 execution documents

Database migrations: none.

API changes: none.

Actual files changed:

- `frontend/src/views/Guide.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/PublicGuidance.spec.ts`
- Phase 14 execution documents

Tests and checks executed:

- focused public guidance component tests: `2 passed`;
- complete frontend suite: `53 passed` across 13 files;
- frontend ESLint: passed;
- frontend typecheck and production build: passed.

Manual acceptance: Guide now separates Project Overview, Discover, Project
Papers, Writing, Independent PDF Reading, Evidence/task status and
troubleshooting; homepage presents both supported modes and the canonical
four-stage Project workflow; all calls to action target existing routes; no
Tool, Skill, raw events or chain-of-thought are exposed.

Visual smoke limitation: automated screenshots could not run because the
container Chromium binary is missing `libatk-1.0.so.0`. Responsive structure,
focus states and reduced-motion behavior were inspected in source and covered
by successful compilation, but pixel-level browser review remains optional.

Deviations from spec: none.

Remaining risk: only the pixel-level browser screenshot pass remains unexecuted
in this container; no functional acceptance item is blocked.

Exact next action: optionally run desktop, 768px and 390px browser screenshots
in an environment with Chromium system libraries, then capture the updated
homepage and Guide for interview/demo material.

## Completed Block — SK-1

Start Commit: `3db54b6`

End Commit: `2c7d982`

Scope: extend the shared Skill Runtime with durable activation and typed,
deterministic completion evaluation; add the versioned Writing Skill and run
its completion fixtures through evaluator logic.

Database migrations: none expected.

API changes: none expected.

Actual files changed:

- `backend/app/harness/runtime/skill_runtime.py`
- `backend/app/harness/runtime/__init__.py`
- `backend/app/harness/skills/writing_evidence_generation/`
- `backend/tests/test_skill_runtime.py`
- `backend/tests/test_agent_runtime_quality.py`
- Phase 13 execution documents

Tests executed: Skill Runtime and runtime quality tests, `10 passed`.

Manual acceptance: completion evaluation rejects unknown/missing criteria and
required metadata; five Writing Skill fixtures execute evaluator logic and
cover pass, repaired pass, reviewer failure, unsupported citation and missing
metadata.

## Completed Block — SK-2

Start Commit: `2c7d982`

End Commits: `7d09836` (Reviewer implementation) and `a4929fa` (contract closeout)

Scope: add the typed Writing Reviewer and exactly one reviewer-directed repair
to paragraph generation before Evidence persistence.

Actual files changed:

- `backend/app/application/writing_service.py`
- `backend/tests/test_writing_documents.py`
- `docs/API.md`
- Phase 13 execution documents

Tests executed: Writing and execution runtime targeted tests, `38 passed`.

Manual acceptance: Reviewer pass produces no repair; repair verdict produces
exactly one additional model call before Evidence persistence; invalid repaired
output raises `WRITING_REVIEW_ERROR` after that single attempt.

## Completed Block — SK-3

Start Commit: `a4929fa`

Scope: activate the Writing Skill in durable execution, persist review/repair
and completion-eval evidence, require Skill completion in Completion Gate and
run complete Phase acceptance.

Actual files changed:

- `backend/app/worker.py`
- `backend/app/application/execution_service.py`
- Writing Skill definition/evals
- execution and Skill Runtime tests
- `frontend/src/api/documents.ts`
- `frontend/src/api/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- `docs/architecture/SKILL_RUNTIME.md`
- `docs/API.md`

Tests and checks executed:

- Phase-targeted Skill/Writing/execution tests: `50 passed`;
- complete backend suite: `305 passed`;
- complete frontend suite: `51 passed` across 12 files;
- frontend build and ESLint: passed;
- backend, worker and frontend Docker images: built successfully;
- recreated services: backend and worker healthy; database and Redis healthy;
- frontend root served successfully.

Manual acceptance: durable Writing activates the versioned Skill; Reviewer
pass/repair stages and Skill completion are replayable events; result payload
persists proposal, Skill completion report and Completion Gate report; failed
Skill completion prevents terminal success; task details show Skill completion
without raw review reasoning.

Deviations from spec: none. Reviewer is a bounded workflow decision inside the
single Writing/Research runtime, not a new general SubAgent platform.

Remaining risk: real provider-backed Reviewer quality still requires configured
LLM/embedding credentials and a parsed Project paper. Deterministic contracts,
failure handling and repair bounds are fully tested without provider calls.

Exact next action: configure provider credentials and capture one pass path and
one reviewer-repair path as interview demo evidence.


## Completed Block — OBS-1

Start Commit: `2f81cb8`

End Commit: `342a11e`

Scope: derive an ownership-checked, privacy-safe execution trace report from
durable AgentExecution and AgentEvent records, including ordered stage spans,
latency, control transitions, budgets and Completion Gate summary.

Target files:

- `backend/app/application/execution_service.py`
- `backend/app/api/executions.py`
- `backend/tests/test_execution_runtime.py`
- `docs/API.md`
- Phase 12 execution documents

Database migrations: none expected; reuse existing durable execution/event
records.

API changes: expected — add a read-only execution trace projection endpoint.

Actual files changed:

- `backend/app/application/execution_service.py`
- `backend/app/api/executions.py`
- `backend/tests/test_execution_runtime.py`
- `docs/API.md`
- Phase 12 execution documents

Database migrations: none.

API changes: added `GET /api/v1/executions/{execution_id}/trace`.

Tests executed: execution runtime trace coverage is included in the rebuilt
OBS-2 run (`14 passed` total; 8 pre-evaluation runtime cases).

Manual acceptance: trace spans are ordered with non-negative durations;
quality, budget and control summaries are present; private instruction, nearby
text, model output and provider payload values are absent from the projection.

## Completed Block — OBS-2

Start Commit: `342a11e`

End Commit: `9bd41f0`

Scope: add a deterministic, explainable quality rubric over execution trace
reports and cover success, weak, unsupported, invalid and interrupted cases.

Actual files changed:

- `backend/app/application/execution_service.py`
- `backend/app/api/executions.py`
- `backend/tests/test_execution_runtime.py`
- `docs/API.md`

API changes: added `GET /api/v1/executions/{execution_id}/evaluation`.

Tests executed: execution runtime tests, `14 passed` after rebuilding the
backend image to avoid stale-container results.

Manual acceptance: deterministic scenarios cover fully verified, weak,
unsupported, missing/invalid completion, interrupted and budget-overrun traces.

## Completed Block — OBS-3

Start Commit: `9bd41f0`

Scope: present trace/evaluation summaries in the existing task details and run
the complete Phase 12 regression/deployment acceptance.

Actual files changed:

- `frontend/src/api/executions.ts`
- `frontend/src/stores/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- Phase 12 execution documents

API consumption: task details load the ownership-checked trace and evaluation
endpoints; no raw trace payload is stored or rendered.

Tests and checks executed:

- complete backend suite: `297 passed`;
- complete frontend suite: `51 passed` across 12 files;
- frontend production build and Docker image build: passed;
- frontend ESLint: passed;
- backend/frontend services recreated;
- backend health: database, Redis and worker healthy;
- frontend root served successfully.

Manual acceptance: task details display total latency, verified/total Citation
count, model-call budget, overall score/verdict and six named quality checks;
the existing event timeline remains available and no prompt, nearby document
text, model output, provider payload or chain-of-thought is exposed.

Deviations from spec: none.

Remaining risk: evaluation is deliberately deterministic and validates system
contracts, not subjective prose quality. Provider-backed semantic quality still
requires the real smoke test already recorded after Phase 11.

Exact next action: run one credential-backed Writing Generate task and capture
the task timeline plus quality panel as interview evidence; subjective prose
quality can later be measured with a separately approved golden-set Phase.


## Completed Block — EX-1

Start Commit: `b68ed88`

End Commit: `c77d65b`

Completed scope: replaced the mock durable execution handler with a real
`writing_generate` workflow, persist structured public events and output
metadata, support safe checkpoint resume/control, and require deterministic
completion checks before marking the execution complete.

Actual files changed:

- `backend/app/models/execution.py`
- `backend/app/application/execution_service.py`
- `backend/app/application/writing_service.py`
- `backend/app/api/executions.py`
- `backend/app/worker.py`
- `backend/alembic/versions/0006_execution_io_add_execution_input_and_result.py`
- `backend/app/infrastructure/db/migrations.py`
- `backend/tests/test_database_migrations.py`
- `backend/tests/test_execution_runtime.py`
- `backend/tests/test_writing_documents.py`
- `docs/API.md` for real contract changes
- Phase 11 execution documents

Database migrations: `0006_execution_io` adds durable `input_payload` and
`result_payload` JSON columns to `agent_executions`.

API changes: execution creation now accepts only `writing_generate` with a
typed `input`; execution serialization includes durable input/result payloads.

Tests executed:

- targeted execution, writing and migration tests: `33 passed`;
- Alembic upgraded from `0005_evidence_verification` to
  `0006_execution_io (head)`;
- schema revision check: compatible, no missing or unexpected schema objects;
- backend and worker images built successfully.

Manual acceptance: deterministic Completion Gate accepts verified/weak
structured proposals and rejects unsupported citations; progress callback emits
ordered context, generation, Evidence and Citation Verification stages.

Deviations from spec: none.

Remaining risks: real-provider/model validation still depends on configured LLM,
embedding and Project paper data; current acceptance uses mocked service
boundaries and the existing local PostgreSQL/Redis services.

## Completed Block — EX-2

Start Commit: `c77d65b`

End Commit: `b3f326b`

Scope: connect the Writing Agent UI to durable execution creation and render a
user-readable replayable/SSE timeline with working pause, resume and cancel
controls.

Actual files changed:

- `frontend/src/api/executions.ts`
- `frontend/src/stores/executions.ts`
- `frontend/src/components/GlobalTaskCenter.vue`
- `frontend/src/components/project/WritingDocumentEditor.vue`

Tests executed:

- frontend production build: passed;
- Writing Workspace component tests: `5 passed`;
- frontend ESLint: passed.

Manual acceptance: Writing Generate creates a durable execution; replayed/SSE
events render as a user-readable timeline; pause/resume/cancel controls invoke
the existing ownership-checked execution API; completed output is still shown
as an explicit proposal and never silently changes editor content.

## Completed Block — EX-3

Start Commit: `b3f326b`

Scope: Phase 11 regression, deployment rebuild and health acceptance.

Tests and checks executed:

- complete backend suite: `289 passed`;
- complete frontend suite: `51 passed` across 12 files;
- frontend production build: passed locally and in the Docker image;
- frontend ESLint: passed;
- Alembic current: `0006_execution_io (head)`;
- schema revision check: compatible;
- production source scan: no `mock_agent` or `mock_agent_completed` remains;
- backend, worker and frontend images rebuilt and services recreated;
- backend health: database, Redis and worker all healthy;
- frontend root served successfully.

Manual acceptance: durable execution input/output, SQL event replay, SSE live
updates, safe-boundary pause/resume/cancel, Completion Gate, readable timeline
and explicit proposal application are connected end to end at the application
contract level.

Deviations from spec: none.

Remaining risk: a real provider-backed Writing Generate run requires valid LLM
and embedding credentials plus a Project containing parsed/indexed papers. The
current environment does not expose the required provider credentials, so this
external validation was not used to claim provider-level production readiness.

Exact next action: configure the required LLM/embedding credentials and run one
real Project Writing Generate smoke test with an imported, parsed paper; then
capture the execution timeline and verified proposal as interview evidence.

## Latest Documentation Maintenance

Date: 2026-08-30

Baseline Commit: `ccbb986`

Maintenance Commit: this active-document consolidation commit (see git history)

Scope: remove completed refactor, migration, Phase, implementation-component,
DTO-example and acceptance-process content from active specifications; merge
overlapping architecture and frontend documents into current-state contracts.

Actual files changed:

- `AGENTS.md`
- `README.md`
- `docs/API.md`
- `docs/ARCHITECTURE.md` (merged into the active system architecture)
- `docs/SMOKE_TESTS.md`
- `docs/architecture/SKILL_RUNTIME.md`
- `docs/archive/README.md`
- `docs/archive/migrations/ALEMBIC_BASELINE_PLAN.md`
- `docs/migrations/ALEMBIC_BASELINE_PLAN.md` (archived)
- `docs/spec-v2/README.md`
- `docs/spec-v2/product/PRODUCT_SCOPE.md`
- `docs/spec-v2/architecture/TARGET_ARCHITECTURE.md` (retired)
- `docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/spec-v2/features/PROJECT_CONTEXT_AND_EVIDENCE.md`
- `docs/spec-v2/features/LITERATURE_DISCOVERY.md`
- `docs/spec-v2/features/WRITING_WORKSPACE.md`
- `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`
- `docs/spec-v2/frontend/DESIGN_SYSTEM_AND_PAGES.md` (retired)
- `docs/spec-v2/frontend/UI_DESIGN_BASELINE.md` (retired)
- `docs/spec-v2/frontend/UI_SYSTEM.md`
- `docs/TODO_OR_RISKS.md`
- `docs/archive/spec-v2/README.md`

Database migrations: none.

API changes: none.

Tests executed: active-document path, stale-reference, content-scope and
repository-diff checks only; no runtime code changed.

Manual acceptance: active product and feature documents now describe current
behavior only; the target/current architecture duplicates are merged; the two
frontend redesign documents are replaced by one UI system contract; completed
implementation details remain available through archive records and Git.

Deviations from spec: none.

Remaining risks: the concise contracts intentionally defer endpoint inventories
to `docs/API.md`, exact visual values to frontend tokens and implementation
details to code/tests. Future changes must keep those sources aligned.

Next action: wait for an approved next Phase, then update
`IMPLEMENTATION_PLAN.md`, `EXECUTION_INDEX.md` and this ledger before
implementation begins.

## Completed Implementation History

- Archive index:
  `docs/archive/spec-v2/README.md`
- Phase 0–9:
  `docs/archive/spec-v2/08_IMPLEMENTATION_PROGRESS_PHASE_0_9.md`
- Phase 10:
  `docs/archive/spec-v2/08_IMPLEMENTATION_PROGRESS_PHASE_10.md`

Archived progress is historical only and must not be read during normal
implementation unless historical context is explicitly required.

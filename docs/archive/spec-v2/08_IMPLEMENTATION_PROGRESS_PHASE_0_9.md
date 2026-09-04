# Archived

Status: COMPLETED / HISTORICAL

This document records completed PaperAI V1 implementation work.
It is no longer an active implementation authority.

Do not use this document for current implementation decisions unless
historical context is explicitly required.

# PaperAI V1 Implementation Progress

> 文档状态：ARCHIVED / HISTORICAL
> 版本：v2.0-template
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文不是设计规范，而是 PaperAI V1 实施过程的**唯一持续进度账本**。
> 每个 Phase 开始、阻塞、恢复、完成时必须更新本文。
> 新 Codex 会话必须先读取本文，再继续施工。

---

# 0. 使用规则

本文必须满足：

1. 记录事实，不写愿景。
2. 只记录已经完成、正在做、明确阻塞的内容。
3. 不允许把“计划做”写成“已完成”。
4. 每个 Phase 必须记录 Start commit 和最终 End commit。
5. 每个 Phase 必须拆分并记录其 Implementation Blocks。
6. 一个 Implementation Block 只有在完整实现、相关测试通过、Block 验收通过后才记录对应 commit。
7. 小改动、调试修复、单个 DTO、单个测试、单个样式调整不单独记录为完成 Block。
8. 开发过程中允许按需执行 targeted Development Check，但它们不等于正式 Block Acceptance。
9. 所有数据库 migration、API 变化和正式验收测试必须可追溯。
10. 如果实际实现偏离 `spec-v2`，必须记录。
11. 新会话不得依赖聊天历史判断当前进度，应以本文为准。
12. 每次更新保持简洁，但信息必须足以让下一位 Agent 接手。

测试与提交节奏：

```text
Implementation Block
→ complete implementation
→ concentrated relevant tests
→ block acceptance
→ one meaningful commit

All Phase Blocks complete
→ broader Phase regression
→ Phase DONE
```

不要记录 `edit → test → commit` 式 micro-progress。

# 1. Overall Status

```text
Project: PaperAI
Target: V1 Research Workspace
Branch: agent-rearchitecture-v1
Current Phase: Phase 9
Current Status: DONE
Current Implementation Block: Phase 9 final regression / Final V1 Acceptance Board
Current Block Status: DONE
Block Start Commit: 2c1027f
Block Commit: this Phase 9 final-acceptance commit (see the commit containing this record)
Last Updated: 2026-08-29
Last Commit: this post-V1 paper-processing retry commit (see the commit containing this record)
```

---


# 1.1 Implementation Block Status

Allowed Block Status:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
BLOCKED_BY_USER
DONE
```

`BLOCKED_BY_USER` 只用于必须由用户完成的外部动作，例如 API key、第三方账号、billing、console configuration 或授权。

如果 Block 代码实现已经完成，但真实外部服务尚未验证，在 Block notes 中记录：

```text
IMPLEMENTATION_COMPLETE_EXTERNAL_VALIDATION_BLOCKED
```

这种情况下 Block / Phase 不得因为 mock tests 通过就被视为真实集成完成。

一个 Block 只有在：

```text
implementation complete
+
relevant tests pass
+
block acceptance passes
```

之后才能标记 `DONE` 并填写 `Block Commit`。

不要为 Block 内的单个 DTO、helper、样式、测试或小修复更新独立 commit。

Development Check 可以在开发过程中按需运行，但只需要在它发现重要问题或影响 Block 设计时记录；正式测试结果记录在 Block Acceptance 和 Phase Acceptance 中。

# 2. Phase Status Board

| Phase | Name | Status | Start Commit | End Commit | Ready for Next |
|---|---|---|---|---|---|
| 0 | Documentation Authority & Baseline | DONE | daef553 | this Phase 0 completion commit | YES |
| 1 | Project Foundation & Navigation | DONE | 13c3844 | this Block 1B completion commit (see the commit containing this record) | YES |
| 2 | Literature Discovery Backend | DONE | e6f33eb | this Block 2C completion commit | YES |
| 3 | Literature Discovery Frontend | DONE | ab0bf813 | this Block 3B completion commit | YES |
| 4 | Project Context & Paper Profile | DONE | a8cc28e | this Block 4C completion commit | YES |
| 5 | Citation Verification Backend | DONE | 1dc42a7 | this Block 5B / Phase 5 completion commit (see the commit containing this record) | YES |
| 6 | Writing Backend | DONE | f6081aa | this Block 6B / Phase 6 completion commit (see the commit containing this record) | YES |
| 7 | Writing Frontend | DONE | e6c5cb14af362e64d937e50a3e99ff72b3d56237 | ddbb71d878008add7435a645edf0cebe1f2f573b | YES |
| 8 | End-to-End Integration | DONE | ddbb71d878008add7435a645edf0cebe1f2f573b | d956c5d | YES |
| 9 | Cleanup & Long-term Docs | DONE | d956c5d | this Phase 9 final-acceptance commit | YES |

Allowed status:

```text
NOT_STARTED
IN_PROGRESS
PARTIAL
BLOCKED
DONE
```

---

# 3. Current Architecture Decisions

只记录已经实际决定、且会影响后续施工的决定。

示例：

```markdown
## ADR-PROGRESS-001 — Academic Search Primary Provider

Status: PENDING

Decision:
<fill>

Reason:
<fill>

Constraints:
<fill>

Date:
<fill>
```

---

## ADR-PROGRESS-001 — V1 Academic Search Primary Provider

Status: ACCEPTED

Decision:
Semantic Scholar Academic Graph API is the V1 primary literature-discovery provider using unauthenticated access first. Crossref REST API is the bounded metadata-enrichment provider. The existing arXiv integration remains the normalized preprint and approved downloadable full-text source.

Reason:
Semantic Scholar is already used for citation/reference metadata and exposes the V1 paper-search fields. Crossref provides public structured DOI metadata and abstracts without signup. arXiv preserves the existing preprint/full-text path.

Constraints:
Language filtering is declared unsupported rather than silently approximated. Year, field and publication-type filters are mapped only when the selected provider declares support. Anonymous Semantic Scholar throttling is a typed, bounded provider state; `SEMANTIC_SCHOLAR_API_KEY` is an optional rate-limit enhancement and is not required to start V1.

Date: 2026-08-23

# 3.1 External Dependency Decisions

只记录会影响施工的外部依赖。

模板：

```markdown
## EXT-001 — <service>

Phase / Block:
Status: NOT_NEEDED / READY / BLOCKED_BY_USER / VERIFIED

Provider / Service:
Purpose:

Credential required:
Environment variable:

Already configured:
YES / NO / UNKNOWN

User action required:
- ...

Implementation possible without credential:
- ...

Real validation command / procedure:
- ...

Decision:
- do not switch provider unless this decision is explicitly reopened
```

当状态为 `BLOCKED_BY_USER` 时，不要在后续 Codex 会话中重新探索其它 Provider，除非用户明确要求重新选型。

## EXT-001 — Semantic Scholar Academic Graph API

Phase / Block: Phase 2 / Block 2A
Status: READY — anonymous access is the V1 path; API key is an optional enhancement

Provider / Service: Semantic Scholar Academic Graph API
Purpose: V1 primary academic metadata search; existing citation/reference capability remains compatible.

Credential required: none for V1 anonymous access; `SEMANTIC_SCHOLAR_API_KEY` is optional for a dedicated rate limit.
Environment variable: `ACADEMIC_SEARCH_PRIMARY_PROVIDER=semantic_scholar`, optional `SEMANTIC_SCHOLAR_API_KEY`, and centralized `SEARCH_*` limits in root `.env`; `docker-compose.yml` forwards them to backend and worker.

Already configured: optional key is not configured; this does not block V1.

User action required:
- none for V1; optionally request a key later and set `SEMANTIC_SCHOLAR_API_KEY=<key>` in the repository-root `.env`.

Implementation possible without credential:
- yes; adapter, normalization, deterministic error handling, mocked contract tests, and the code commit are complete.

Real validation command / procedure:
- use the anonymous adapter path with bounded 429 handling; if a key is added later, repeat the same smoke with the `x-api-key` header.

Decision:
- do not switch primary provider unless this decision is explicitly reopened; an API key is not a V1 prerequisite.

## EXT-002 — Crossref REST API

Phase / Block: Phase 2 / Block 2A
Status: VERIFIED — public REST smoke passed without credentials

Provider / Service: Crossref REST API
Purpose: bounded metadata and abstract enrichment for DOI-registered works.

Credential required: none; optional `CROSSREF_MAILTO` identifies the client for the polite pool.
Environment variable: optional `CROSSREF_MAILTO` in root `.env`; `docker-compose.yml` forwards it to backend and worker.

Already configured: no mailto is configured; anonymous public access is supported.

User action required:
- none.

Implementation possible without credential:
- yes; public adapter, deterministic filters, error handling and mocked tests are complete.

Real validation command / procedure:
- one bounded public `/v1/works` search returned one normalized real paper with DOI and metadata.

Decision:
- use only as metadata enrichment; do not turn it into a replacement primary search provider or a full-text importer.

---

## EXT-003 — Qwen / DashScope Compatible LLM

Phase / Block: Phase 8 / Block 8A
Status: VERIFIED — user authorization granted; real-paper acceptance passed

Provider / Service: Qwen through the DashScope-compatible OpenAI API
Purpose: generate the selected existing paper's bounded Paper Profile and one-paragraph Writing proposal, then exercise Evidence persistence and Citation Verification.

Credential required: an existing configured LLM credential is present; the remaining gate is user authorization to send project-paper-derived text, project context and retrieved evidence to this third-party service.
Environment variable: `LLM_PROVIDER=qwen`, `OPENAI_BASE_URL`, and `OPENAI_API_KEY` in the repository-root `.env`; the key value is never recorded here.

Already configured: YES — non-secret provider, endpoint host, Writing V2 flag and timeout were verified.

User action required:
- none for this acceptance; authorization was granted on 2026-08-24.

Implementation possible without credential or authorization:
- Reader HTTP smoke, deterministic paper/section/element ownership checks and existing unit/contract tests are complete; Profile/Writing calls require the recorded data-sharing authorization, which is now granted and verified.

Real validation command / procedure:
- queue one Paper Profile for the selected existing paper, wait for Worker status `ready`, call the existing one-paragraph Writing endpoint, verify durable Evidence rows and Citation Verification statuses, and confirm the document remains unchanged until the user accepts the proposal.

Validation result:
- PASS — Worker generated a `ready` Profile through Qwen; Writing returned `200 / ready`, persisted 4 Evidence rows, returned 4 structured citations with 4 `verified` statuses, and left the document revision unchanged.

Decision:
- keep the already-configured Qwen/DashScope path; do not switch providers or fabricate Profile/Evidence content to bypass this gate.

---

# 4. Current Known Risks

只记录当前真实存在的风险。

当前风险索引（完整说明见 `docs/TODO_OR_RISKS.md`）：

```text
RISK-001
lead_agent.py responsibilities are too broad.

RISK-002
literature_research.py responsibilities are too broad.

RISK-003
ProjectWorkspace.vue exposes too many non-V1 product surfaces.

RISK-004
Primary provider is finalized; anonymous-provider rate limits require bounded error handling and optional enrichment fallback.

RISK-005
Current citation audit is not sufficient as final semantic support verification.

RISK-006
Project Context may regress into one oversized prompt instead of typed, staged context.
```

每项使用：

```markdown
### RISK-XXX — <title>

Status: OPEN / MITIGATED / CLOSED

Impact:
...

Mitigation:
...

Owner / Phase:
...
```

---

# 5. Phase 0 — Documentation Authority & Baseline

## Implementation Blocks

### Block 0A — Documentation Authority Migration

Status: DONE

Includes:

- add `docs/spec-v2/`
- create `docs/archive/`
- archive legacy Agent documents
- replace / update current authority documents
- initialize this Progress document

Block acceptance:

- [x] spec-v2 exists
- [x] archive exists
- [x] AGENTS.md authority points to spec-v2
- [x] archived docs cannot override current specs
- [x] no business runtime code changed
- [x] `git diff --check` passes

Block Commit:

```text
this Phase 0 completion commit (see the commit containing this record)
```


Status: DONE

## Goal

建立唯一文档权威关系，并记录施工基线。

## Spec References

- `docs/spec-v2/00_PRODUCT_SCOPE.md`
- `docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md`
- `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`

## Baseline

```text
Start commit: daef553
Start date: 2026-08-19
Codex session: Phase 0 documentation authority migration; finalized 2026-08-23
```

## Target Files

```text
AGENTS.md
docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md
docs/PROJECT_AGENT_UPGRADE_CONTEXT.md
docs/ARCHITECTURE.md
docs/TODO_OR_RISKS.md
docs/spec-v2/*
docs/archive/*
```

## Planned Changes

- [x] Create `docs/spec-v2/`
- [x] Create `docs/archive/`
- [x] Add all current spec-v2 documents
- [x] Archive legacy implementation specification
- [x] Archive legacy upgrade context
- [x] Update AGENTS.md authority order
- [x] Mark ARCHITECTURE.md partially outdated during migration
- [x] Update current risks

## Implementation Result

Status: DONE

### Files Changed

```text
AGENTS.md
docs/API.md
docs/ARCHITECTURE.md
docs/DEV_NOTES.md
docs/TODO_OR_RISKS.md
docs/architecture/SKILL_RUNTIME.md
docs/archive/PROJECT_AGENT_IMPLEMENTATION_SPEC_V1.md
docs/archive/PROJECT_AGENT_UPGRADE_CONTEXT_2026-08-17.md
docs/database/SCHEMA.md
docs/migrations/ALEMBIC_BASELINE_PLAN.md
docs/spec-v2/00_PRODUCT_SCOPE.md
docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md
docs/spec-v2/02_TARGET_ARCHITECTURE.md
docs/spec-v2/03_PROJECT_CONTEXT_AND_EVIDENCE.md
docs/spec-v2/04_LITERATURE_DISCOVERY.md
docs/spec-v2/05_WRITING_WORKSPACE.md
docs/spec-v2/06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
docs/spec-v2/EXECUTION_INDEX.md
```

### Tests Executed

```text
PASS — `git diff --check`
PASS — required Phase 0 paths and archive status headers verified
PASS — diff from baseline contains documentation files only
```

### Manual Acceptance

- [x] spec-v2 exists
- [x] archive exists
- [x] AGENTS.md points to spec-v2
- [x] archived docs cannot override current specs
- [x] no business code changed

### Deviations From Spec

```text
None.
```

### Remaining Risks

```text
Phase 0 documentation-authority conflict is resolved. Product and architecture risks remain tracked in `docs/TODO_OR_RISKS.md`; no external dependency is involved in this Block.
```

### End

```text
End commit: this Phase 0 completion commit (see the commit containing this record)
End date: 2026-08-23
Next phase readiness: YES — Block 1A may start in a new implementation cycle.
```

---

# 6. Phase 1 — Project Foundation & Navigation

## Implementation Blocks

### Block 1A — Project Contract and Route Foundation

Status: DONE

Includes:

- Project metadata contract
- Project route foundation
- ownership / API compatibility
- projectStore adjustments

Block acceptance:

- [x] project create / ownership tests pass
- [x] deep routes resolve
- [x] no Reader route regression

Block Commit:

```text
this Block 1A completion commit (see the commit containing this record)
```

### Block 1B — Project Product Shell

Status: DONE

Includes:

- Projects Home
- Project Header
- Overview
- Discover shell
- Papers page
- Writing shell

Block acceptance:

- [x] four Project tabs work
- [x] default Overview works
- [x] frontend build passes
- [x] Reader still opens

Block Commit:

```text
this Block 1B completion commit (see the commit containing this record)
```


Status: DONE

## Goal

建立 V1 Project 主骨架：

```text
Overview
Discover
Papers
Writing
```

## Spec References

- `00_PRODUCT_SCOPE.md`
- `01_CODEBASE_MIGRATION_MAP.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`
- `07_CODEX_IMPLEMENTATION_PLAN.md`

## Baseline

```text
Start commit: 37612ba
Start date: 2026-08-23
```

## Current Code Facts Rechecked

施工前填写：

```text
ResearchProject current fields: title, research_topic, abstract, phase, status, memory, preferences
ProjectPaper current fields: project/paper relation, role, tags, notes, analysis_card, reading_plan, reading_priority
Current project routes: /projects list plus legacy /project/:id workspace and /project/:id/chat
Current ProjectWorkspace responsibilities: monolithic overview, research, papers, writing, resources and activity UI
Current project stores: project.ts owns current project/papers/workflow; workspace.ts owns persisted shell state
```

## Target Files

```text
backend/app/api/projects.py
backend/app/application/project_service.py
backend/tests/test_project_contracts.py
backend/tests/test_project_router_structure.py
frontend/src/api/projects.ts
frontend/src/router/index.ts
frontend/src/router/routes.spec.ts
frontend/src/stores/project.ts
frontend/src/stores/stores.spec.ts
frontend/src/views/ResearchProjectList.vue
frontend/src/components/project/ProjectHeader.vue
frontend/src/components/project/ProjectShell.vue
frontend/src/views/ProjectOverview.vue
frontend/src/views/LiteratureDiscover.vue
frontend/src/views/ProjectPapers.vue
frontend/src/views/ProjectWriting.vue
docs/API.md
```

## Planned Changes

- [x] Project metadata contract
- [x] Project routes
- [x] Project Header
- [x] Overview
- [x] Discover shell
- [x] Papers page
- [x] Writing shell
- [x] Project store cleanup

## Database Migrations

```text
none planned; optional research scope uses the existing preferences JSON compatibility field
```

## API Changes

```text
Extended existing Project create/update/detail/list contracts with typed optional research_scope metadata while preserving existing fields and routes. Added canonical deep routes while retaining legacy Project and independent Reader compatibility.
```

## Tests Planned

```text
Backend: Project DTO validation, ownership service, project paper list/route contracts.
Frontend: project store tests, canonical deep-route resolution, legacy route and Reader route compatibility, build.
```

## Implementation Result

Status: DONE — Block 1A and Block 1B complete

### Actual Files Changed

```text
backend/app/api/projects.py
backend/app/application/project_service.py
backend/tests/test_project_contracts.py
docs/API.md
frontend/src/api/projects.ts
frontend/src/router/index.ts
frontend/src/router/routes.spec.ts
frontend/src/stores/project.ts
frontend/src/stores/stores.spec.ts
frontend/src/views/ProjectWorkspace.vue
frontend/src/views/ResearchProjectList.vue
frontend/src/components/project/ProjectHeader.vue
frontend/src/components/project/ProjectShell.vue
frontend/src/views/ProjectOverview.vue
frontend/src/views/LiteratureDiscover.vue
frontend/src/views/ProjectPapers.vue
frontend/src/views/ProjectWriting.vue
```

Block 1B retained `ProjectWorkspace.vue` and its underlying Reader and writing foundations for compatibility; canonical V1 project routes no longer render the monolithic workspace.

### Tests Executed

```text
`docker compose build backend` — PASS
`docker compose run --rm backend python -m ruff check app/api/projects.py app/application/project_service.py tests/test_project_contracts.py tests/test_project_router_structure.py` — PASS
`docker compose run --rm backend python -m pytest -q tests/test_project_contracts.py tests/test_project_router_structure.py tests/test_project_retrieval.py tests/test_research_items.py tests/test_writing_documents.py` — PASS, 43 passed
`npx eslint src/api/projects.ts src/router/index.ts src/router/routes.spec.ts src/stores/project.ts src/stores/stores.spec.ts src/views/ProjectWorkspace.vue src/views/ResearchProjectList.vue` — PASS
`npm test -- --run src/router/routes.spec.ts src/stores/stores.spec.ts` — PASS, 12 passed
`npm run build` — PASS; existing chunk-size warning only
`npx eslint src/components/project/ProjectHeader.vue src/components/project/ProjectShell.vue src/router/index.ts src/router/routes.spec.ts src/views/ResearchProjectList.vue src/views/ProjectOverview.vue src/views/LiteratureDiscover.vue src/views/ProjectPapers.vue src/views/ProjectWriting.vue` — PASS
`npm run typecheck` — PASS
`npm test -- --run src/router/routes.spec.ts src/stores/stores.spec.ts` — PASS, 13 passed
`docker compose run --rm backend python -m pytest -q tests/test_project_contracts.py tests/test_project_router_structure.py tests/test_project_retrieval.py tests/test_research_items.py tests/test_writing_documents.py` — PASS, 43 passed
`git diff --check` — PASS
```

### Manual Acceptance

- [x] Create project contract and transaction boundary
- [x] Required name/topic
- [x] Default Overview route and legacy redirect
- [x] Four Project tabs
- [x] Canonical deep routes resolve and Nginx history fallback is present
- [x] Project Paper list ownership service is tested
- [x] Existing Reader route still resolves
- [x] Projects Home, fixed Project Header, Overview entrances, Discover shell, Papers table and Writing editor shell are reachable from canonical routes

### Deviations From Spec

```text
None. The existing preferences JSON compatibility path is explicitly allowed by the Phase 1 specification. The old `ProjectWorkspace.vue` remains as an underlying compatibility asset, while canonical V1 routes use separate page boundaries.
```

### End

```text
End commit: this Block 1B completion commit (see the commit containing this record)
End date: 2026-08-23
Next phase readiness: YES — Phase 2 / Block 2A may start in a new implementation cycle; no Phase 2 implementation was started in this cycle.
```

---

# 7. Phase 2 — Literature Discovery Backend

## Implementation Blocks

### Block 2A — Academic Search Foundation

Status: DONE

Includes:

- Search DTO
- Provider interface
- Primary Provider adapter
- arXiv normalization
- deterministic filter mapping
- normalization
- deduplication
- full abstract preservation

Block acceptance:

- [x] Provider tests pass
- [x] Normalize tests pass
- [x] Dedup tests pass
- [x] Filter tests pass
- [x] Full abstract is preserved
- [x] Crossref public real smoke passes without credentials
- [x] Semantic Scholar anonymous 429 handling is bounded and typed; API key remains optional

Block Commit:

```text
this Block 2A completion commit (see the commit containing this record)
```

### Block 2B — Discovery Workflow and API

Status: DONE

Includes:

- Search Planner
- bounded multi-round workflow
- result-quality check
- execution state
- discovery API
- error handling

Block acceptance:

- [x] max rounds enforced
- [x] partial results work
- [x] zero results work
- [x] provider failure works
- [x] no fabricated papers
- [x] API contract tests pass

Block Commit:

```text
this Block 2B completion commit (see the commit containing this record)
```

### Block 2C — Favorite and Import Integration

Status: DONE

Includes:

- favorite persistence
- favorite isolation
- import availability
- safe remote import linkage
- duplicate import handling

Block acceptance:

- [x] favorite tests pass
- [x] cross-project isolation passes
- [x] import security tests pass
- [x] duplicate import handling passes

Block Commit:

```text
this Block 2C completion commit (see the commit containing this record)
```


Status: DONE

## Goal

实现真实、结构化、受预算约束的 Academic Search backend。

## Spec References

- `02_TARGET_ARCHITECTURE.md`
- `04_LITERATURE_DISCOVERY.md`
- `07_CODEX_IMPLEMENTATION_PLAN.md`

## Baseline

```text
Start commit:
e6f33eb
```

## Provider Decision

### Primary Provider

```text
Provider:
Semantic Scholar Academic Graph API
API: `GET https://api.semanticscholar.org/graph/v1/paper/search`
Auth: public endpoint without key; optional `x-api-key` from `SEMANTIC_SCHOLAR_API_KEY`
Rate limit: bounded client handling for 429 / Retry-After; no retry loop on 401 / 403 / 429
Abstract coverage: returned when available and preserved in full
Year filter: supported and mapped deterministically
Language filter: not supported; declared capability false
Field filter: supported when Semantic Scholar accepts `fieldsOfStudy`
Publication type filter: supported when Semantic Scholar accepts `publicationTypes`
PDF/Open Access support: maps `openAccessPdf` when present; no arbitrary remote URL import
Reason selected: existing repository integration, public paper search, structured metadata coverage, and a bounded optional-key path.
```

### Secondary / Enrichment Provider

```text
Provider: Crossref REST API
API: `GET https://api.crossref.org/v1/works`
Auth: public endpoint; optional `mailto` polite-pool identification via `CROSSREF_MAILTO`
Rate limit: bounded client handling for 429 / Retry-After; no retry loop on 401 / 403 / 429
Abstract coverage: returned when deposited and preserved without UI truncation
Reason selected: public DOI metadata, abstract and citation-count enrichment without account setup.
```

### Existing arXiv Role

```text
Normalized compatibility adapter and approved remote PDF/preprint source; not the V1 primary provider.
```

## External Dependency Gate

```text
Credential required: none for V1; `SEMANTIC_SCHOLAR_API_KEY` is optional and `CROSSREF_MAILTO` is optional polite-pool identification
Existing credential detected: no academic-search credentials in root `.env`; anonymous paths are supported
User action required: none
Environment variable: `ACADEMIC_SEARCH_PRIMARY_PROVIDER`, optional `SEMANTIC_SCHOLAR_API_KEY`, optional `CROSSREF_MAILTO`, and centralized `SEARCH_*` limits
Can implementation continue without credential: yes; all Block 2A code and validation completed
Real provider validation blocked: no; Crossref public smoke passed, while Semantic Scholar anonymous 429 is handled as a bounded provider state
```

如果缺凭证：

- Provider interface / adapter / normalize / deterministic error handling 可以继续实现；
- unit / contract tests 可以使用 mock HTTP；
- 不得通过 mock 将 Real Provider Acceptance 标记为通过；
- 不得因为缺 key 连续切换 Provider；Semantic Scholar key remains an optional enhancement.

## Target Files

```text
backend/app/config.py
backend/app/research/discovery/__init__.py
backend/app/research/discovery/schemas.py
backend/app/research/discovery/normalize.py
backend/app/research/discovery/providers/base.py
backend/app/research/discovery/providers/semantic_scholar.py
backend/app/research/discovery/providers/crossref.py
backend/app/research/discovery/providers/arxiv.py
backend/app/harness/tools/external_literature.py
backend/tests/test_academic_search.py
.env.example
docker-compose.yml
```

## Planned Changes

- [x] Search DTO
- [x] Provider interface
- [x] Provider adapter
- [x] Crossref enrichment adapter
- [x] Normalize
- [x] Dedup
- [x] Search planner
- [x] max-round workflow
- [x] discovery API
- [x] favorites
- [x] safe import linkage

## Configuration Added

```text
Added: `ACADEMIC_SEARCH_PRIMARY_PROVIDER`, optional `SEMANTIC_SCHOLAR_API_KEY`, optional `CROSSREF_MAILTO`, `SEARCH_TIMEOUT_SECONDS`, `SEARCH_MAX_RETRIES`, `SEARCH_MAX_ROUNDS`, `SEARCH_MAX_QUERIES_PER_ROUND`, `SEARCH_RESULT_LIMIT`; root `.env.example` and `docker-compose.yml` document/forward the values.
```

## Database Migrations

```text
none planned
```

## API Changes

```text
Block 2B added:
- POST `/api/v1/projects/{project_id}/discovery/search`
- GET `/api/v1/projects/{project_id}/discovery/executions/{execution_id}`

Block 2C added:
- POST/GET `/api/v1/projects/{project_id}/discovery/favorites`
- DELETE `/api/v1/projects/{project_id}/discovery/favorites/{favorite_id}`
- POST `/api/v1/projects/{project_id}/discovery/import`

All routes require Bearer authentication and project ownership validation. Search responses are typed normalized paper results with execution id, round count and warnings. Favorite metadata is project-scoped JSON; import reuses the existing safe arXiv importer and worker pipeline.
```

## Tests Planned

- [x] provider normalize
- [x] full abstract preserved
- [x] filters
- [x] dedup
- [x] max rounds
- [x] zero results
- [x] partial results
- [x] provider errors
- [x] no fabricated papers
- [x] API route/OpenAPI contract
- [x] Crossref public smoke
- [x] favorites
- [x] import

## Implementation Result

Status: DONE

### Actual Files Changed

```text
.env.example
backend/app/config.py
backend/app/harness/tools/external_literature.py
backend/app/research/__init__.py
backend/app/research/discovery/__init__.py
backend/app/research/discovery/schemas.py
backend/app/research/discovery/normalize.py
backend/app/research/discovery/providers/__init__.py
backend/app/research/discovery/providers/base.py
backend/app/research/discovery/providers/semantic_scholar.py
backend/app/research/discovery/providers/crossref.py
backend/app/research/discovery/providers/arxiv.py
backend/tests/test_academic_search.py
docker-compose.yml
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Test Results

```text
PASS — `docker compose config --quiet`
PASS — `docker compose build backend`
PASS — `docker compose run --rm backend python -m ruff check app/research/discovery app/config.py app/harness/tools/external_literature.py tests/test_academic_search.py`
PASS — `docker compose run --rm backend python -m pytest -q tests/test_academic_search.py tests/test_remote_paper_import.py tests/test_project_contracts.py tests/test_project_router_structure.py` — 50 passed
PASS — `git diff --check`
PASS — one bounded Crossref public `/v1/works` smoke for `large language models` returned one normalized real paper with DOI and metadata; no credential was used.
EXPECTED_PROVIDER_STATE — one earlier Semantic Scholar anonymous smoke returned HTTP 429; the adapter reports typed rate-limit state without retrying and API key remains optional.
```

### Manual API Acceptance

```text
Search query:
`large language models`
Filters: none
Result count: Crossref returned one normalized real paper; Semantic Scholar anonymous throttling remains a handled provider state
Real papers verified: Crossref public smoke passed
Import tested: not in Block 2A; reserved for Block 2C
```

### Deviations From Spec

```text
None. Language support is explicitly declared unsupported for providers that cannot map it. Semantic Scholar anonymous access is the V1 path; its API key is optional, and Crossref is limited to metadata enrichment.
```

### End

```text
End commit: this Block 2A completion commit (see the commit containing this record)
Next phase readiness: YES — Block 2A is complete; Phase 2 continues with Block 2B only.
```

---

### Block 2B Implementation Result

Status: DONE

### Actual Files Changed

```text
backend/app/api/discovery.py
backend/app/main.py
backend/app/research/discovery/execution.py
backend/app/research/discovery/schemas.py
backend/app/research/discovery/workflow.py
backend/tests/test_discovery_router_structure.py
backend/tests/test_discovery_workflow.py
docs/API.md
docs/spec-v2/04_LITERATURE_DISCOVERY.md
docs/spec-v2/EXECUTION_INDEX.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Implementation Summary

```text
Implemented a deterministic Search Planner and bounded three-round workflow with complementary queries, provider normalization, deduplication, quality/coverage checks, partial/zero-result handling, and simple final ranking. The workflow stops early once a round has enough relevant candidates and never fabricates papers.

Added Redis-backed short-lived execution state and project-scoped search/status API routes. Primary Semantic Scholar remains unauthenticated-first; Crossref is used only as the configured metadata fallback. Provider failures are typed and bounded, with no unbounded retry or provider switching caused by the optional Semantic Scholar key.
```

### Test Results

```text
PASS — `docker compose config --quiet`
PASS — `docker compose build backend`
PASS — `docker compose run --rm backend python -m ruff check app/research/discovery app/api/discovery.py`
PASS — `docker compose run --rm backend python -m pytest -q tests/test_discovery_workflow.py tests/test_discovery_router_structure.py` — 9 passed
PASS — one bounded real workflow smoke with Semantic Scholar anonymous-first and Crossref fallback returned one real DOI result; no credential was used
PASS — no database migration required
PASS — `git diff --check`
```

### Block Acceptance

```text
PASS — round-one sufficient search stops without extra rounds
PASS — max three rounds and max three queries per round are enforced
PASS — fewer-than-target and zero-result responses remain truthful
PASS — provider rate-limit failure uses the configured fallback once per query and surfaces typed failure when no fallback succeeds
PASS — strong filters are passed unchanged to providers
PASS — API route registration and OpenAPI request/response contract pass
```

### External Dependency / Real Validation

```text
No BLOCKED_BY_USER dependency. `SEMANTIC_SCHOLAR_API_KEY` remains optional; the real smoke used the public unauthenticated path and accepted its bounded rate-limit state. Crossref public fallback returned normalized metadata without credentials.
```

### Deviations From Spec

```text
None. The planner is kept behind a SearchPlanner interface so a bounded Agent-backed planner can be introduced only if a later V1 requirement needs uncertain query decisions; this Block does not expose raw reasoning or create a second runtime.
```

### End

```text
End commit: this Block 2B completion commit (see the commit containing this record)
Next action: Block 2C completed; proceed to Phase 2 acceptance.
```

---

### Block 2C Implementation Result

Status: DONE

### Actual Files Changed

```text
backend/app/api/discovery.py
backend/app/research/discovery/favorites.py
backend/app/research/discovery/schemas.py
backend/tests/test_discovery_favorites_import.py
backend/tests/test_discovery_router_structure.py
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Implementation Summary

```text
Added project-scoped Discovery Favorite persistence using the existing ResearchProject.preferences JSON compatibility path. Favorites are normalized, bounded, idempotent by source + source_paper_id, and isolated by project; search responses now reflect favorite state without creating ProjectPaper rows.

Added typed Favorite and Import API contracts. Import accepts only source=arxiv with a valid source identifier and matching approved locator/result-id contract, then delegates to the existing safe arXiv importer, Worker queue, parser/indexer, and ProjectPaper linkage. No arbitrary URL download path was added.
```

### Test Results

```text
PASS — `docker compose build backend`
PASS — `docker compose run --rm backend python -m ruff check app/api/discovery.py app/research/discovery tests/test_discovery_favorites_import.py tests/test_discovery_router_structure.py`
PASS — Block 2C targeted tests — 19 passed
PASS — Phase 2 regression tests — 67 passed
PASS — `docker compose run --rm backend alembic current` — `0004_writing_documents (head)`
PASS — no database migration required
PASS — `git diff --check`
```

### Block Acceptance

```text
PASS — favorite and unfavorite behavior
PASS — duplicate favorite is idempotent and updates validated metadata
PASS — cross-project favorite isolation
PASS — unsupported source and oversized/raw payload rejection
PASS — import availability is limited to approved arXiv source metadata
PASS — arbitrary remote locator rejection
PASS — existing queued/processing duplicate import state is preserved
PASS — Favorite/Import routes and OpenAPI contracts pass
```

### External Dependency / Real Validation

```text
No BLOCKED_BY_USER dependency. Import uses the existing arXiv public source and current remote importer contract; no new API key, account, billing, or console action is required.
```

### Deviations From Spec

```text
None. Favorite storage extends the existing project preferences JSON compatibility path as permitted by the specification; no parallel Favorite table or second import pipeline was introduced.
```

### End

```text
End commit: this Block 2C completion commit (see the commit containing this record)
Next phase readiness: YES — Phase 2 regression passed; Phase 3 / Block 3A may start.
```

### Phase 2 Acceptance

```text
PASS — Block 2A provider/normalize/dedup acceptance remains green
PASS — Block 2B bounded workflow/API acceptance remains green
PASS — Block 2C favorite/import acceptance remains green
PASS — 67 focused Phase 2 regression tests passed
PASS — schema revision remains at Alembic head; no migration required
PASS — no external dependency blocker
```

```text
Phase 2 End commit: this Block 2C completion commit (see the commit containing this record)
Phase 2 End date: 2026-08-23
Next phase: Phase 3 — Literature Discovery Frontend / Block 3A
```

---

# 8. Phase 3 — Literature Discovery Frontend

## Implementation Blocks

### Block 3A — Requirement and Search UX

Status: DONE

Includes:

- Requirement Chat
- Search Intent ready state
- structured filters
- discoverStore state
- search execution progress

Block acceptance:

- [x] clarification flow works
- [x] Search Intent auto-fills
- [x] filters are editable
- [x] execution progress is user-readable
- [x] frontend build passes

Block Commit:

```text
this Block 3A completion commit (see the commit containing this record)
```

### Block 3B — Result Cards and Actions

Status: DONE

Includes:

- two-column grid
- PaperResultCard
- abstract clamp / expand
- PaperDetailDrawer
- favorite / download / import states
- zero / partial / error states

Block acceptance:

- [x] two-column layout works
- [x] abstract expand/collapse works
- [x] disabled actions keep layout
- [x] favorite works
- [x] import works
- [x] detail drawer works

Block Commit:

```text
this Block 3B completion commit (see the commit containing this record)
```


Status: DONE — Phase 3 complete

## Goal

完成 Discover 用户体验。

## Spec References

- `04_LITERATURE_DISCOVERY.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`

## Baseline

```text
Start commit: ab0bf813b3a7b18968708610d6bcd8badfeb610d
Start date: 2026-08-23
```

## Target Components

```text
frontend/src/api/discovery.ts
frontend/src/api/index.ts
frontend/src/stores/discover.ts
frontend/src/stores/discover.spec.ts
frontend/src/components/discover/RequirementChat.vue
frontend/src/components/discover/SearchIntentSummary.vue
frontend/src/components/discover/SearchFilterForm.vue
frontend/src/components/discover/SearchExecutionStatus.vue
frontend/src/views/LiteratureDiscover.vue
frontend/src/components/discover/PaperResultCard.vue
frontend/src/components/discover/PaperResultGrid.vue
frontend/src/components/discover/PaperDetailDrawer.vue
frontend/src/main.ts
```

## Planned Changes

- [x] requirement clarification
- [x] ready Search Intent
- [x] filters
- [x] execution state
- [x] paper card grid
- [x] detail drawer
- [x] favorite
- [x] download
- [x] import
- [x] disabled tooltip
- [x] empty/error state

## Implementation Result

Status: DONE — Block 3A and Block 3B complete

### Actual Files Changed

```text
frontend/src/api/discovery.ts
frontend/src/api/index.ts
frontend/src/stores/discover.ts
frontend/src/stores/discover.spec.ts
frontend/src/components/discover/RequirementChat.vue
frontend/src/components/discover/SearchIntentSummary.vue
frontend/src/components/discover/SearchFilterForm.vue
frontend/src/components/discover/SearchExecutionStatus.vue
frontend/src/views/LiteratureDiscover.vue
frontend/src/components/discover/PaperResultCard.vue
frontend/src/components/discover/PaperResultCard.spec.ts
frontend/src/components/discover/PaperResultGrid.vue
frontend/src/components/discover/PaperResultGrid.spec.ts
frontend/src/components/discover/PaperDetailDrawer.vue
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
frontend/src/main.ts
```

### Frontend Commands

```text
build: `npm run build` — PASS; existing chunk-size warning only
typecheck: `npm run typecheck` — PASS
lint: `npm run lint -- --no-warn-ignored` — PASS
tests: `npm test -- --run` — PASS, 27 tests in 6 files
backend contract: `docker compose run --rm backend python -m pytest -q tests/test_discovery_favorites_import.py tests/test_discovery_router_structure.py` — PASS, 10 passed
```

### Manual Acceptance

- [x] requirement conversation transitions from clarifying to ready_for_search
- [x] user requirement and project profile auto-fill the typed Search Intent
- [x] Search Intent fields remain editable before search
- [x] year, language, field and publication type filters are structured and editable
- [x] search request state and completion summary are user-readable; no raw tool log is exposed
- [x] two-column grid
- [x] abstract 4-line clamp
- [x] expand/collapse
- [x] detail drawer
- [x] favorite
- [x] disabled download
- [x] disabled import
- [x] import request and backend contract
- [x] zero result
- [x] partial result
- [x] requirement collapse

### Screens / Notes

```text
Block 3A and 3B now cover the Discover flow from requirement clarification through real search-result presentation. Result cards preserve full abstracts with four-line UI clamping, keep disabled actions in fixed slots with accessible tooltips, and route favorite/import actions through the existing project-scoped APIs. Import availability remains provider-declared; no arbitrary URL download path was added.
```

### End

```text
Phase 3 end commit: this Block 3B completion commit (see the commit containing this record)
Phase 3 end date: 2026-08-23
Next phase: Phase 4 — Project Context & Paper Profile / Block 4A
```

---

# 9. Phase 4 — Project Context & Paper Profile

## Implementation Blocks

### Block 4A — Typed Project Context Foundation

Status: DONE

Includes:

- Project Profile access
- Literature Memory semantics
- Context DTOs
- stop new generic memory dumping

Block acceptance:

- [x] typed Project Profile works from existing `ResearchProject` / `preferences.research_scope` storage
- [x] ordinary chat and legacy generic memory are not automatically included in new Discovery context
- [x] context ownership, bounds, typed-memory filtering and identifier projection tests pass

Block Commit:

```text
this Block 4A completion commit (see the commit containing this record)
```

### Block 4A Implementation Result

Start commit: `a8cc28e` (Phase 3 / Block 3B completion)

Actual files changed:

```text
backend/app/research/context/__init__.py
backend/app/research/context/schemas.py
backend/app/research/context/manager.py
backend/app/application/project_service.py
backend/app/api/research_items.py
backend/app/harness/tools/literature_research.py
backend/app/harness/agents/lead_agent.py
backend/tests/test_project_context.py
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Implementation:

- Added bounded `ProjectProfileContext`, `LiteratureMemoryContext` and `DiscoveryContext` DTOs.
- Added ownership-aware `ProjectContextManager.build_discovery_context`; it selects only stable Literature Memory types and projects favorite/imported identifiers without raw provider payloads.
- Reused existing structured project preferences for typed Project Profile access; no parallel 1:1 profile table or migration was added.
- Changed new `project_append_memory` writes to require an explicit stable Literature Memory type and persist `MemoryItem`; ordinary chat, raw search results and raw reasoning are rejected.
- Updated the legacy lead-agent project prompt path to consume typed profile/memory while retaining bounded paper/artifact previews for compatibility with the pre-Context-Manager runtime.
- Kept legacy `ResearchProject.memory` endpoints/read fallback for compatibility; the new Discovery context does not read that generic JSON dump.

API / schema:

- Expanded the gated Research Notes `MEMORY_TYPES` contract with `project_decision`, `literature_intent`, `literature_preference` and `literature_exclusion`.
- Documented the existing project Research Notes / Evidence routes and the typed-memory boundary in `docs/API.md`.
- No database schema change; no Alembic migration required.

Block acceptance:

```text
ruff check (Block files): PASS
python -m pytest -q tests/test_project_context.py tests/test_project_contracts.py tests/test_research_items.py tests/test_agent_routing.py tests/test_discovery_favorites_import.py: PASS (55 passed)
```

Manual acceptance:

- [x] Profile fields are read from the existing project contract and bounded.
- [x] Generic `ResearchProject.memory` and non-Literature `MemoryItem` rows do not enter Discovery context.
- [x] Favorite and successfully imported paper identifiers are projected without returning raw metadata.
- [x] Project ownership mismatch returns a non-disclosing context error.
- [x] Reader/RAG/ProjectPaper/WritingArtifact foundations remain on their existing paths.

Compatibility note (not a product redesign): legacy JSON memory routes remain available for existing clients, but new typed context access does not absorb their generic notes. Paper/artifact previews in `lead_agent.py` remain temporarily bounded until the later Paper Profile / evidence blocks replace them.

### Block 4B — Paper Profile Generation

Status: DONE

Includes:

- stable Paper Profile schema
- `analysis_card` evolution
- profile generation trigger
- retry / version / stale handling

Block acceptance:

- [x] parse/index completion schedules Project Paper profiles through the existing Worker queue
- [x] generation and scheduling failure persist Profile state without blocking Reader, Project Papers or QA
- [x] explicit regeneration and bounded retry state work
- [x] profile schema, source fingerprint, generator version and stale detection work

Block Commit:

```text
this Block 4B completion commit (see the commit containing this record)
```

### Block 4B Implementation Result

Start commit: `0d51644` (Block 4A completion)

Actual files changed:

```text
backend/app/research/context/__init__.py
backend/app/research/context/paper_profile.py
backend/app/research/context/paper_profile_generator.py
backend/app/application/project_service.py
backend/app/api/projects.py
backend/app/worker.py
backend/app/harness/tools/literature_research.py
backend/app/harness/agents/lead_agent.py
backend/tests/test_paper_profile.py
backend/tests/test_project_router_structure.py
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Implementation:

- Evolved `ProjectPaper.analysis_card` with a stable `paper_profile` subdocument; existing reading-card summary/evidence fields remain intact.
- Added the versioned `PaperProfile` contract with project/paper identity, bounded academic fields, lifecycle status, source model, schema/generator version, source fingerprint, retry count and safe failure metadata.
- Added a one-call bounded generator using title, abstract and selected Introduction/Methods/Results/Conclusion sections; it never sends the default full paper when parsed sections are available.
- Added parse/import/manual-project-link triggers using the existing reliable Worker queue. Discover-only and favorite-only records never generate profiles.
- Added non-blocking `pending → generating → ready/failed/stale` lifecycle, source/version invalidation, explicit regeneration and removed-membership acknowledgement.
- Preserved Reader, Project Papers, QA and legacy reading-card behavior when profile generation or queueing fails.

API / schema:

- Added `GET /api/v1/projects/{project_id}/papers/{paper_id}/profile`.
- Added `POST /api/v1/projects/{project_id}/papers/{paper_id}/profile/regenerate` with `202 / 409 / 503` lifecycle mapping.
- Added Worker job type `paper_profile`; no second execution runtime was created.
- No database schema change; no Alembic migration required.

Block acceptance:

```text
ruff check (Block files): PASS
python -m pytest -q tests/test_paper_profile.py tests/test_project_context.py tests/test_project_contracts.py tests/test_project_router_structure.py tests/test_paper_router_structure.py tests/test_paper_processing_services.py tests/test_remote_paper_import.py tests/test_discovery_favorites_import.py tests/test_job_queue.py: PASS (70 passed)
real Qwen structured Paper Profile smoke: PASS (HTTP 200; 11-field schema validated)
```

Manual acceptance:

- [x] only parsed Project Papers enter the generation queue
- [x] empty academic fields validate as empty values rather than fabricated content
- [x] legacy `analysis_card` data survives automatic profile generation and manual card updates
- [x] failed generation is persisted and acknowledged without failing completed parse/import
- [x] regeneration increments retry state and profile source/version changes become stale
- [x] ownership checks hide foreign project/paper membership

External dependency: existing Qwen configuration was present and the bounded real-provider smoke passed. No new credential, billing or user action is required.

### Block 4C — Candidate Papers and Evidence Retrieval

Status: DONE

Includes:

- Context Manager
- candidate paper selector
- restricted Hybrid Retrieval
- Evidence provenance

Block acceptance:

- [x] candidate paper restriction works
- [x] evidence comes from real Project Papers
- [x] cross-project isolation works
- [x] no full-project prompt dump

Block Commit:

```text
this Block 4C / Phase 4 completion commit (see the commit containing this record)
```


### Block 4C Implementation Result

Start commit: `5fb20bd` (Block 4B completion)

Actual files changed:

```text
backend/app/research/context/__init__.py
backend/app/research/context/schemas.py
backend/app/research/context/manager.py
backend/app/research/context/selectors.py
backend/app/research/evidence/__init__.py
backend/app/research/evidence/retrieval.py
backend/app/research/evidence/service.py
backend/app/rag/hybrid_retrieval.py
backend/app/rag/knowledge_base.py
backend/app/api/research_items.py
backend/app/harness/tools/literature_research.py
backend/tests/test_candidate_evidence_retrieval.py
backend/tests/test_project_retrieval.py
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Implementation:

- Added deterministic Paper Profile selection capped at five Project-owned candidates; ready profiles are preferred and stale profiles are explicitly down-ranked.
- Added `build_writing_context` and typed empty states for no imported papers, no usable profiles and no supporting evidence; generic project memory/chat is excluded.
- Added a Project-scoped Evidence retrieval service that invokes the existing `HybridPaperRetriever` only for selected candidate IDs and returns bounded, structured provenance.
- Routed the legacy `project_search_content` Tool through the new Context Manager/service boundary while preserving its structured chunk response.
- Added source locator validation and active `ProjectPaper` membership filtering for persisted Evidence; removed-project or fabricated chunk sources are rejected.
- Preserved the existing RAG, Reader, EvidenceItem, WritingDocument and execution foundations; no second retrieval or Evidence system was created.

API / schema:

- No new public endpoint. Existing Evidence creation now returns `422` for source locations that cannot be resolved inside the selected Project Paper.
- Existing Evidence reads include active ProjectPaper membership, so removed-paper evidence is not exposed as current Project evidence.
- No database schema change and no Alembic migration required; Phase 5 verification fields remain pending its own Block.

## Goal

建立 Project Profile、Literature Memory、Paper Profile、Evidence Retrieval 和 Context Manager。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `02_TARGET_ARCHITECTURE.md`

## Baseline

```text
Start commit: a8cc28e
```

## Existing Model Mapping

```text
ResearchProject.memory: legacy compatibility only; excluded from new typed Discovery context
MemoryItem: stable Literature Memory types added in Block 4A
ProjectPaper.analysis_card: legacy card fields plus versioned paper_profile subdocument
EvidenceItem: retained; Block 4C adds provenance DTO/persistence validation without parallel storage
Current retrieval filters: Paper Profile shortlist plus ProjectPaper ownership and candidate paper_id restriction around existing HybridPaperRetriever
```

## Schema Decisions

### Project Profile

```text
Storage: ResearchProject plus preferences.research_scope
Fields: project_id/title/topic/field/subject/question/goal/keywords/method/user_notes/updated_at
```

### Literature Memory

```text
Storage: MemoryItem
Allowed types: project_decision/literature_intent/literature_preference/literature_exclusion
```

### Paper Profile

```text
Storage: ProjectPaper.analysis_card.paper_profile (legacy analysis-card fields preserved)
Schema version: 1; generator version 1.0; source fingerprint and source model persisted
Generation model: existing LLMClient / configured Qwen model, one bounded structured-output call
Generation trigger: parsed Project Paper linkage, parse completion, approved arXiv import, or explicit regeneration via existing Worker queue
```

### Evidence

```text
New DTO provenance: source type, retrieval method/score, paper/chunk/section/page/element/bbox identity
Persistence: existing EvidenceItem fields; only explicitly used candidates are persisted through EvidenceService
Verification fields: transient unverified status; durable verifier fields remain pending Phase 5
Stale behavior: active reads/persistence recheck ProjectPaper membership; removed-paper evidence is rejected
```

## Target Files

```text
Blocks 4A/4B actual files are recorded in their Implementation Result sections above.
Block 4C inspected targets: context schemas/manager/selectors, existing HybridPaperRetriever,
EvidenceItem/research-items API, project retrieval tool, and directly related backend tests/docs.
```

## Database Migrations

```text
None for Phase 4. Existing ResearchProject, MemoryItem, ProjectPaper.analysis_card and EvidenceItem storage was reused.
```

## Implementation Result

Status: DONE — Blocks 4A, 4B and 4C complete; Phase 4 acceptance passed

### Tests

```text
Block 4A: Ruff PASS; focused backend suite PASS (55 passed)
Block 4B: Ruff PASS; focused backend suite PASS (70 passed); real Qwen structured Paper Profile smoke PASS
Block 4C targeted suite: PASS (26 passed, including real SQLite ProjectPaper/Section service acceptance)
Phase 4 backend regression: PASS (124 passed)
Ruff: PASS
Frontend lint/build/typecheck: PASS (existing Vite chunk-size warning only)
Alembic current: 0004_writing_documents (head)
Schema revision validator: compatible=true; no missing/unexpected tables or columns
```

### Manual Acceptance

- [x] imported parsed paper gets profile
- [x] profile failure does not break Reader
- [x] Context Manager does not dump all chats
- [x] candidate paper selection works
- [x] evidence retrieval restricted to candidate papers
- [x] cross-project isolation

### End

```text
End commit: this Block 4C / Phase 4 completion commit (see the commit containing this record)
Next phase readiness: YES
```

---

# 10. Phase 5 — Citation Verification Backend

## Implementation Blocks

### Block 5A — Deterministic Citation Integrity

Status: DONE

Includes:

- Project / Paper / Evidence integrity
- stale / missing Evidence handling
- reuse current lexical gate

Block acceptance:

- [x] wrong project rejected
- [x] wrong paper rejected
- [x] missing Evidence rejected
- [x] stale Evidence rejected

Block Commit:

```text
this Block 5A completion commit (see the commit containing this record)
```

### Block 5A Implementation Result

Start commit: `1dc42a7` (Block 4C / Phase 4 completion)

Actual files changed:

```text
backend/alembic/versions/0005_evidence_verification_add_evidence_lifecycle.py
backend/app/application/citation_verification_service.py
backend/app/api/documents.py
backend/app/api/research_items.py
backend/app/infrastructure/db/migrations.py
backend/app/models/research.py
backend/app/research/evidence/service.py
backend/tests/test_candidate_evidence_retrieval.py
backend/tests/test_citation_integrity.py
backend/tests/test_database_migrations.py
backend/tests/test_research_items.py
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Implementation:

- Added an application-layer `CitationVerificationService` and structured citation mappings/results without introducing a second Evidence or execution system.
- Enforced Project ownership, active ProjectPaper membership, Paper/Evidence identity, source-locator existence, section/element consistency and optional source-fingerprint freshness before support checks.
- Reused the existing lexical support gate through the service and preserved its API import for compatibility.
- Persisted deterministic stale, invalid, unsupported and unverified lifecycle states; a deterministic pass remains `unverified` until Block 5B semantic verification succeeds.
- Routed the existing WritingDocument citation-audit endpoint through the integrity service while preserving uncited-paragraph findings and the legacy `issues` / `passed` response fields.
- Added real SQLite ORM acceptance coverage for valid, cross-project, cross-paper, missing, removed, stale, changed-source, invalid-chunk and lexical-mismatch cases.

API / schema:

- Extended `EvidenceItem` with source lifecycle, fingerprint and verification status/reason/model/version fields plus `updated_at`.
- Added Alembic migration `0005_evidence_verification` and advanced the expected schema head.
- Existing citation-audit responses now also include typed `citation_results`; deterministic success is not reported as semantically verified.
- Updated `docs/API.md` for the Evidence lifecycle and citation-audit contract.

Block acceptance:

```text
ruff check (Block files): PASS
targeted backend suite: PASS (28 passed)
concentrated Block regression: PASS (94 passed)
backend image build: PASS
migration empty DB upgrade to 0005: PASS
migration 0005 downgrade to 0004 and re-upgrade: PASS
local database upgrade/current: PASS (0005_evidence_verification head)
schema revision validator: PASS (compatible=true; no mismatches)
```

External dependency: none. Block 5A is deterministic and requires no provider credential or real-provider call.

### Block 5B — Semantic Support Verification

Status: DONE

Includes:

- verifier schema
- verified / weak / unsupported
- bounded retry / claim adjustment

Block acceptance:

- [x] valid support verified
- [x] weak support classified
- [x] unsupported classified
- [x] correlation / causation mismatch handled
- [x] timeout handled

Block Commit:

```text
this Block 5B / Phase 5 completion commit (see the commit containing this record)
```

### Block 5B Implementation Result

Start commit: `bbbe539` (Block 5A completion)

Actual files changed:

```text
.env.example
backend/app/application/citation_semantic_verifier.py
backend/app/application/citation_verification_service.py
backend/app/api/documents.py
backend/app/config.py
backend/tests/test_citation_integrity.py
docker-compose.yml
frontend/src/api/documents.ts
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Implementation:

- Added a bounded `SemanticCitationVerifier` on the existing `LLMClient`; its strict output is `verified / weak / unsupported` with reason, confidence and an optional conservative suggested claim.
- Limited verifier context to the actual claim, one Evidence source and necessary Paper metadata; no Project/chat/full-paper prompt dump was added.
- Made semantic verification a mandatory continuation of the existing deterministic/lexical workflow for citation audit; deterministic failures never call the model.
- Added explicit timeout, invalid-response, authentication, rate-limit and unavailable results, none of which can be reported as verified.
- Added at most one opt-in conservative claim adjustment plus re-verification. The service returns original/adjusted claims explicitly and never mutates editor content.
- Persisted verifier status, reason, model and version on the existing Evidence lifecycle fields and exposed typed per-citation counts/results.

API / configuration:

- Citation audit now returns semantic `citation_results`; `weak` produces a warning and `unsupported` an error while preserving existing `issues / passed` fields.
- Added typed frontend response fields without implementing Phase 7 citation UI.
- Added optional `CITATION_VERIFIER_TIMEOUT_SECONDS` (default 30, valid 1–120) to settings, compose and `.env.example`.
- No database schema change or Alembic migration was required in Block 5B; migration `0005` from Block 5A is reused.

Block / Phase acceptance:

```text
ruff check (Block backend files): PASS
targeted backend suite: PASS (38 passed)
real Qwen verifier smoke: PASS (direct support=verified; correlation-only causal claim=unsupported; HTTP 200)
Phase 5 backend regression including Reader/RAG/export: PASS (145 passed)
backend image build: PASS
frontend typecheck: PASS
frontend lint: PASS
frontend production build: PASS (existing chunk-size warning only)
Alembic current: PASS (0005_evidence_verification head)
schema revision validator: PASS (compatible=true; no mismatches)
```

External dependency: the existing configured Qwen credential/model passed real-provider verification. No new key, account, billing, console configuration or user action is required.


Status: DONE

## Goal

建立不可绕过的真实引用验证链。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `05_WRITING_WORKSPACE.md`

## Baseline

```text
Start commit: 1dc42a7
Current citation audit: POST /api/v1/documents/{document_id}/citation-audit routed through CitationVerificationService
Current lexical gate: evidence_supports_claim() in app/application/citation_verification_service.py
```

## Verifier Decision

```text
Verifier model: existing LLMClient and configured Qwen/DeepSeek model; no vendor-specific client
Structured output: strict verified / weak / unsupported decision with reason, confidence and optional conservative suggested_claim
Timeout: dedicated bounded outer timeout; timeout never produces verified
Retry: no unbounded provider switching; at most one conservative claim adjustment and re-verification
Confidence handling: persisted for response/audit context; status remains the authority and weak/unsupported never become verified from confidence alone
```

## Block 5B Baseline

```text
Start commit: bbbe539
Existing service: backend/app/application/citation_verification_service.py
Existing LLM abstraction: backend/app/llm/client.py
Existing provider configuration: LLM_PROVIDER plus configured Qwen/DeepSeek credentials
External dependency decision: reuse the existing configured LLM service; no new account, billing, console action or credential is introduced
Target files: citation verification service/tests, document citation audit, bounded verifier configuration, API/progress documentation
```

## Planned Changes

- [x] referential integrity
- [x] lexical gate reuse
- [x] semantic verifier
- [x] weak / unsupported
- [x] claim adjustment
- [x] verifier service
- [x] tests

## Implementation Result

Status: DONE — Blocks 5A and 5B complete; Phase 5 acceptance passed

### Test Cases

```text
valid: semantic verified and provenance persisted
wrong project: rejected
wrong paper: rejected
missing evidence: rejected
weak: classified with warning and optional conservative suggested claim
unsupported: lexical and semantic unsupported persisted
causation mismatch: real Qwen smoke returned unsupported for causal claim over correlational Evidence
timeout: explicit verifier_timeout; no retry and never verified
```

### End

```text
End commit: this Block 5B / Phase 5 completion commit (see the commit containing this record)
Next phase readiness: YES
```

---

# 11. Phase 6 — Writing Backend

## Implementation Blocks

### Block 6A — Writing Service Contract

Status: DONE

Includes:

- free-form rewrite
- selection / section context
- current WritingDocument / revision / export compatibility
- structured proposal contract

Block acceptance:

- [x] plain rewrite works
- [x] citation-aware rewrite preserves mapping
- [x] revision regression passes
- [x] export regression passes

Block Commit:

```text
this Block 6A completion commit (see the commit containing this record)
```

### Block 6B — Evidence-backed Paragraph Generation

Status: DONE

Includes:

- candidate papers
- Evidence Retrieval
- paragraph generation
- Citation Mapping
- Citation Verification
- failure codes

Block acceptance:

- [x] verified paragraph generation works
- [x] no-paper error works
- [x] no-evidence error works
- [x] unsupported citation is not marked verified

Block Commit:

```text
this Block 6B / Phase 6 completion commit (see the commit containing this record)
```


Status: DONE

## Goal

把当前写作固定 Action 升级成 Context-aware Writing Agent。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `05_WRITING_WORKSPACE.md`

## Baseline

```text
Start commit: f6081aa
Current writing_service responsibilities: fixed action prompt plus plain-text LLM replacement helper
Current WritingDocument API: project document CRUD, append-only revisions, legacy /documents/{id}/ai-actions proposal, citation audit
Current revision behavior: ProseMirror JSON is authoritative; user acceptance creates a new append-only revision
Current export formats: existing artifact download keeps Markdown, LaTeX, DOCX and ZIP submission package
```

## Block 6A Target Files

```text
backend/app/application/writing_service.py
backend/app/api/documents.py
backend/tests/test_writing_documents.py
backend/tests/test_manuscript_export.py (regression only unless contract correction is required)
frontend/src/api/documents.ts (typed API contract only; Phase 7 UI is out of scope)
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

## Block 6B Baseline and Target Files

```text
Start commit: b0c5b89
Existing context path: ProjectContextManager → CandidatePaperSelector → ProjectEvidenceRetrievalService → existing HybridPaperRetriever
Existing Evidence path: EvidenceService.persist_used with project/paper/source-locator validation
Existing verification path: CitationVerificationService deterministic integrity + semantic support verification
Target files:
backend/app/application/writing_service.py
backend/app/api/documents.py
backend/tests/test_writing_documents.py
frontend/src/api/documents.ts (typed transport contract only)
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

## Planned Changes

- [x] free-form rewrite
- [x] generate paragraph
- [x] current section context
- [x] candidate papers
- [x] evidence retrieval
- [x] structured citation mapping for rewrite and generation proposals
- [x] mandatory verification for preserved and generated citations
- [x] typed rewrite conflict, context, generation and verification failure codes

## Compatibility Requirements

- [x] WritingDocument unchanged; no migration required
- [x] Revision regression protected
- [x] Existing export protected
- [x] Existing Citation Node compatible

## API Changes

```text
POST /api/v1/projects/{project_id}/writing/agent/rewrite
- project ownership and current/base revision are validated before generation
- returns a structured proposal only; never mutates the document or creates a revision
- citation mappings use immutable internal placeholders and are reverified through CitationVerificationService
- legacy document CRUD, revision, citation-audit and /documents/{id}/ai-actions routes remain compatible

POST /api/v1/projects/{project_id}/writing/agent/generate
- generates exactly one proposal paragraph from the existing Project Context → candidate → Hybrid Retrieval path
- resolves model-selected temporary Evidence keys to server-validated, persisted Evidence and real paper/evidence IDs
- requires structured citation mappings and mandatory CitationVerificationService results
- returns typed no-paper/no-relevant-paper/no-evidence/generation/verification failures and never searches the web
```

## Implementation Result

Status: DONE — Blocks 6A and 6B complete; Phase 6 acceptance passed

### Block 6A Result

```text
Start commit: f6081aa
End commit: this Block 6A completion commit (see the commit containing this record)
Database migrations: none
```

Implemented:

- Added a typed free-form selection rewrite request and structured proposal response on the existing Writing Service boundary.
- Bounded prompt context to the selected text, optional current section path and nearby text; editor content is treated as untrusted data.
- Preserved citation identity with server-validated `[[CITATION:<citation_key>]]` placeholders and exact ordered mappings rather than parsing citation IDs from prose.
- Reused the existing LLM client and completed `CitationVerificationService`; `weak` and `unsupported` citations remain explicit and are never presented as verified.
- Added one bounded structured-output repair attempt, typed 404/409/503 failures, and stale-revision rejection before any LLM call.
- Kept acceptance user-controlled: rewrite returns a proposal and performs no WritingDocument or revision write.
- Added the typed frontend transport contract only; Phase 7 UI remains out of scope.

Actual files changed:

```text
backend/app/application/writing_service.py
backend/app/api/documents.py
backend/tests/test_writing_documents.py
frontend/src/api/documents.ts
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Tests

```text
PASS: docker compose build backend
PASS: docker compose run --rm backend ruff check app/application/writing_service.py app/api/documents.py tests/test_writing_documents.py
PASS: docker compose run --rm backend python -m pytest -q tests/test_writing_documents.py tests/test_manuscript_export.py tests/test_document_layout.py tests/test_citation_integrity.py tests/test_project_router_structure.py tests/test_project_contracts.py tests/test_database_migrations.py (71 passed)
PASS: configured real Qwen structured rewrite smoke (HTTP 200; citation mapping preserved; one placeholder; no warnings)
PASS: cd frontend && npm run typecheck
PASS: cd frontend && npm run lint
PASS: cd frontend && npm run build (existing chunk-size warning only)
```

### Block 6B Result

```text
Start commit: b0c5b89
End commit: this Block 6B / Phase 6 completion commit (see the commit containing this record)
Database migrations: none
```

Implemented:

- Added the typed `generate` request/response and a one-paragraph structured generation contract on the existing Writing Service.
- Reused `ProjectContextManager → CandidatePaperSelector → ProjectEvidenceRetrievalService → HybridPaperRetriever`; no second retrieval path or web search was added.
- Exposed only bounded candidate profiles and source-traceable Evidence to the model, using temporary `E1…En` keys rather than trusting model-supplied database IDs.
- Required each generated claim to occur in the proposal content, persisted only selected Evidence through the existing provenance checks, then constructed real citation mappings server-side.
- Made existing deterministic plus semantic Citation Verification mandatory; weak/unsupported results remain explicit and unsupported citations are never marked verified.
- Added one bounded structured-output repair and typed `NO_IMPORTED_PAPERS`, `NO_RELEVANT_PAPERS`, `NO_SUPPORTING_EVIDENCE`, `GENERATION_ERROR`, and `VERIFICATION_ERROR` failures.
- Preserved proposal-only behavior, WritingDocument/revision/export, Citation Node and legacy writing APIs.

Actual files changed:

```text
backend/app/application/writing_service.py
backend/app/api/documents.py
backend/tests/test_writing_documents.py
frontend/src/api/documents.ts
docs/API.md
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

Block and Phase acceptance:

```text
PASS: docker compose build backend
PASS: Ruff for Block backend files
PASS: focused writing/context/Evidence/citation suite (38 passed)
PASS: configured real Qwen one-paragraph structured generation smoke (one E1 mapping, one placeholder, one paragraph)
PASS: full backend Phase regression on final backend image (278 passed)
PASS: frontend typecheck, lint and production build (existing chunk-size warning only)
PASS: Alembic current = 0005_evidence_verification (head)
PASS: schema revision validator compatible=true with no mismatches
```

### Manual Acceptance

- [x] plain rewrite
- [x] citation-aware rewrite
- [x] evidence-backed generation
- [x] no papers error
- [x] no evidence error
- [x] unsupported citation warning

### End

```text
End commit: this Block 6B / Phase 6 completion commit (see the commit containing this record)
Next phase readiness: YES
```

---

# 12. Phase 7 — Writing Frontend

## Implementation Blocks

### Block 7A — Writing Workspace and Editor Context

Status: DONE

Includes:

- three-column layout
- outline integration
- current section detection
- selection context
- Writing Agent panel shell

Block acceptance:

- [x] layout works at desktop target sizes
- [x] current section shows correctly
- [x] selection state is correct
- [x] frontend build passes

Block Commit:

```text
this Block 7A completion commit (see the commit containing this record)
```

### Block 7B — Proposal and Citation Interaction

Status: DONE

Includes:

- rewrite proposal
- generate proposal
- replace / copy
- stale selection guard
- citation verification status
- Evidence detail
- progress / error states

Block acceptance:

- [x] rewrite / replace works
- [x] undo works
- [x] generation / copy works
- [x] verified / weak / unsupported states render
- [x] save / export regressions pass

Block Commit:

```text
this Block 7B completion commit (see the commit containing this record)
```


Status: DONE

## Goal

完成正式三栏 Writing Workspace 与右侧 Agent。

## Spec References

- `05_WRITING_WORKSPACE.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`

## Baseline

```text
Start commit:
Current WritingDocumentEditor: canonical Project Writing editor with document list, Tiptap surface and permanent Evidence rail
Current editor extensions: StarterKit plus the existing inline Citation node
Current citation node: structured paper_id / evidence_id / citation_key attributes; preserved
Current revision UI: existing title update, immutable revision save, citation audit and export-compatible content_json
```

## Planned Changes

- [x] three-column layout
- [x] outline
- [x] selection context
- [x] right Agent shell
- [x] proposal card
- [x] replace selection
- [x] copy
- [x] progress
- [x] citation detail
- [x] verification status
- [x] panel collapse

## Implementation Result

Status: DONE

### Actual Files Changed

```text
frontend/src/components/project/WritingDocumentEditor.vue
frontend/src/components/project/WritingAgentPanel.vue
frontend/src/components/project/WritingOutlinePanel.vue
frontend/src/stores/writing.ts
frontend/src/stores/stores.spec.ts
frontend/src/utils/writingContext.ts
frontend/src/utils/writingContext.spec.ts
frontend/src/components/project/WritingWorkspace.spec.ts
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Implementation Summary

```text
Refactored the existing Project Writing editor into an Outline / Tiptap Editor / Writing Agent workspace while preserving the existing WritingDocument, revision, Citation Node, citation audit, save and evidence insertion contracts. The outline is derived from live Tiptap heading nodes, and editor selection updates a bounded writingStore context containing the current heading, section path, selected text/count and nearby blocks without copying the full document into Pinia.

Added desktop, compact-desktop, tablet drawer and mobile basic-edit responsive rules. Both the Writing Agent and the compact-desktop Outline panel have accessible collapse controls. Existing Evidence actions remain available inside the Agent panel rather than introducing a fourth permanent rail.
```

### Test / Build Results

```text
PASS — `npm run test` — 8 frontend test files, 34 tests passed
PASS — `npm run typecheck`
PASS — `npm run lint`
PASS — `npm run build` — production build passed; existing chunk-size warning only
PASS — `git diff --check`
```

### Manual Acceptance

- [x] selection detected and bounded context snapshot
- [x] current section shown from live heading hierarchy
- [x] desktop three-column and compact-desktop Outline/Agent collapse rules
- [x] tablet Agent drawer and mobile basic edit fallback
- [x] rewrite proposal
- [x] stale selection protected
- [x] replace
- [x] undo
- [x] generation
- [x] copy
- [x] verified citation
- [x] weak citation
- [x] unsupported citation
- [x] save
- [x] export

### End

```text
End commit: this Phase 7 completion commit (the Block 7B commit; see the commit containing this record)
Next phase readiness: YES — Phase 7 Block 7B and phase acceptance passed
```

---

### Block 7B Implementation Result

Status: DONE

### Actual Files Changed

```text
frontend/src/components/project/WritingDocumentEditor.vue
frontend/src/components/project/WritingAgentPanel.vue
frontend/src/components/project/WritingProposalCard.vue
frontend/src/components/project/WritingProposalCard.spec.ts
frontend/src/utils/writingProposal.ts
frontend/src/utils/writingProposal.spec.ts
frontend/src/stores/writing.ts
frontend/src/stores/stores.spec.ts
frontend/src/components/project/WritingWorkspace.spec.ts
docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
```

### Implementation Summary

```text
Connected the existing typed rewrite/generate Writing API contracts to the three-column workspace through a bounded Writing Agent composer and Pinia request state. Rewrite and generation responses remain proposals; the editor is never mutated until the user explicitly chooses an action.

Added a structured Proposal Card with verified / weak / unsupported status, warning states, citation tokens, Evidence detail (source, page, snippet, normalized claim and reason), project-scoped paper links, copy-to-plain-text and stale-selection-safe replacement. Replacement converts structured citation placeholders back into the existing Tiptap Citation Node, creates an agent revision through the existing save path, and keeps Tiptap undo available. Existing citation audit, save, export and Reader foundations remain unchanged.
```

### API / Migration / Deviation

```text
API changes: none; consumed the existing typed `/writing/agent/rewrite` and `/writing/agent/generate` contracts.
Database migrations: none.
Spec deviations: none.
External dependency: none; this Block uses existing backend contracts and requires no new credential.
```

### Test / Build Results

```text
PASS — `npm run test` — 10 frontend test files, 42 tests passed
PASS — `npm run typecheck`
PASS — `npm run lint`
PASS — `npm run build` — production build passed; existing chunk-size warning only
PASS — `git diff --check`
PASS — `docker compose run --rm backend python -m pytest -q tests/test_writing_documents.py tests/test_manuscript_export.py` — 24 passed
PASS — `docker compose run --rm backend python -m pytest -q tests/test_citation_integrity.py` — 11 passed
```

### Block / Phase Acceptance

- [x] rewrite proposal is shown without automatic document mutation
- [x] replace checks revision, range, content anchor and editor version before inserting
- [x] replacement preserves structured Citation Node attributes and remains undoable
- [x] generation is one-paragraph proposal with copy-only action
- [x] verified, weak and unsupported statuses are visibly distinct and unsupported is never labeled verified
- [x] loading and typed backend failure states are user-readable; concurrent requests are disabled
- [x] existing WritingDocument revision/save, citation audit and export regressions pass
- [x] Phase 7 frontend regression passed with typecheck, lint, production build and focused backend contracts

### End

```text
End commit: this Block 7B completion commit (see the commit containing this record)
Next action: Phase 8 / Block 8A — V1 Mainline Integration; implementation is in progress and real import-dependent acceptance remains pending.
```

---

# 13. Phase 8 — End-to-End Integration

## Implementation Blocks

### Block 8A — V1 Mainline Integration

Status: DONE

Includes:

- Project → Discover → Import
- Import → Reader
- Writing → Evidence → Citation Verification
- Selection Rewrite → Replace → Undo
- required regression fixes discovered during E2E

Block acceptance:

- [x] all four E2E journeys pass
- [x] backend suite passes
- [x] frontend build passes
- [x] Reader regression passes through the full backend suite and route contract checks
- [x] RAG regression passes through the full backend suite
- [x] export regression passes through the full backend suite
- [x] no schema change; Alembic head and schema compatibility checks pass
- [x] no API-key gate was introduced; anonymous Semantic Scholar throttling remained bounded and Crossref fallback was exercised

Block Commit:

```text
this Block 8A implementation commit (see the commit containing this record)
```


Status: DONE

## Goal

验证 V1 主链真实可用。

## Baseline

```text
Start commit: ddbb71d878008add7435a645edf0cebe1f2f573b
```

## Implementation

- Added a typed paper-task status contract and bounded Discover import monitoring. A queued/processing import is promoted to `imported` only after the Worker reports terminal `completed`; core `ready` remains visibly in progress until `ProjectPaper` attachment finishes.
- Import monitoring is capped at 400 local task-status checks with 1.5-second spacing, stops on project/result reset, and does not retry 401/403/404 responses. This covers the bounded remote download plus the existing parse/index pipeline without becoming unbounded.
- Moved approved arXiv PDF transfer from the synchronous HTTP tool call into the existing Worker job, so the API returns a task immediately instead of losing the request to the frontend's 30-second timeout.
- Made the remote-import read and whole-transfer deadlines configurable (`REMOTE_IMPORT_READ_TIMEOUT_SECONDS=45`, `REMOTE_IMPORT_TOTAL_TIMEOUT_SECONDS=300`) while preserving size, allowlist, PDF-magic and partial-file cleanup safeguards.
- Fixed the shared media-indexing tail discovered by the real import: it now derives the persisted text-vector count and obtains the existing knowledge-base instance instead of referencing undefined local variables.
- Added focused timeout and cancellation cleanup coverage for the remote importer; the bounded deadline is enforced before an import can be reported as complete.
- Fixed duplicate-import monitoring when the existing-task response contains a `task_id` but omits `paper_id`; the owned task-status response now supplies the identity needed to reach a truthful terminal state.
- Fixed hybrid retrieval's structured-image path to tolerate the current `Image` schema, which has no `bbox` column, while preserving the optional locator field for Evidence provenance.
- Updated the Playwright smoke to traverse the canonical V1 Project → Overview → Discover → Papers → Writing routes and use the existing Reader route when a seeded imported paper exists.

## Real-provider / local smoke record

```text
Health: PASS — backend/database/redis/worker healthy; root endpoint PASS.
Create Project: PASS — temporary smoke project created.
Requirement/Search: PASS — real Semantic Scholar anonymous request returned bounded 429; workflow did not retry and used the configured Crossref metadata fallback.
Real papers: PASS — 10 normalized Crossref results with full structured fields returned.
Favorite: PASS — one real Crossref result saved to the project.
arXiv source discovery: PASS — approved arXiv search returned real preprint identifiers.
Approved arXiv import: PASS — approved arXiv id `1706.03762` downloaded as a valid 2,215,244-byte PDF in 122.52 seconds under the configurable 300-second deadline, then completed the existing parse/index pipeline as paper `76e78683-4afb-4015-997c-90b2b2f74b1c` (39,621 full-text characters; 496 indexable elements).
Network diagnosis: PASS — the user's fast host curl used a loopback proxy configured in the host environment; a bounded host direct request reproduced the slower stream, while the container intentionally had no inherited proxy variables. The valid direct transfer was clipped only because the former whole-transfer deadline was hard-coded to 120 seconds.
Async import contract: PASS — the import tool now enqueues the Worker-owned download without a `file_path`; focused contract coverage proves the HTTP path does not wait for the PDF transfer.
Existing instance papers: PASS — the existing user project contains two parsed full-text papers and remains available for Reader regression context.
Existing paper Reader HTTP smoke: PASS — the selected project paper passed owned Project Papers, Paper detail, Sections and indexable Elements checks (2 project papers, 28 sections, 546 indexable elements).
Paper Profile / Writing real chain: PASS — after explicit user authorization, the selected existing parsed Project Paper generated a Qwen Profile with Worker status `ready`; the Writing endpoint returned `200 / ready`, persisted 4 Evidence rows and returned 4/4 `verified` structured citations without changing the document revision.
Writing/Reader real chain: PASS — the newly imported paper is attached to Project Papers, its stored PDF/full text/indexable elements are available, its automatic Paper Profile is `ready`, and a real knowledge-base query returned five content-bearing chunks including `Scaled Dot-Product Attention`.
```

Status note:

```text
DONE — approved arXiv real-stream and Qwen/DashScope validation both passed; no external validation blocker remains.
```

## E2E Journey A — Project → Discover → Import

```text
Project:
Search topic:
Filters:
Result count:
Paper imported:
Parse result:
```

Acceptance:

- [x] create Project
- [x] clarify
- [x] search
- [x] real papers
- [x] favorite
- [x] import — approved arXiv `1706.03762` completed through the real downloader and existing parse/index pipeline

## E2E Journey B — Import → Reader

- [x] Project Papers shows imported paper
- [x] Reader opens from the newly imported project paper
- [x] PDF is a valid stored 2,215,244-byte `%PDF-` asset for the newly imported paper
- [x] existing retrieval/QA foundation works for the newly imported paper (5 real content-bearing chunks returned)
- [x] independent Reader route and existing Reader/RAG contracts remain covered by regression tests

## E2E Journey C — Writing with Citation

```text
Document: V1 Block 8A acceptance (existing project document)
Instruction: fakshield research problem, method characteristics and contributions for related-work/method-background context
Candidate papers: 1 selected existing parsed Project Paper
Evidence count: 4
Generated citations: 4 structured mappings
Verified: 4
Weak: 0
Unsupported: 0
```

Acceptance:

- [x] real Project Paper only (selected existing parsed Project Paper)
- [x] real Evidence (4 durable Evidence rows from retrieval)
- [x] structured Citation Mapping contract
- [x] verifier executed by the existing evidence-backed generation path and regression tests
- [x] user can inspect source through the existing Evidence UI contract
- [x] copy action contract

## E2E Journey D — Rewrite

- [x] selection context contract
- [x] rewrite proposal contract
- [x] replace
- [x] revision
- [x] undo

Journey B passed against the real newly imported arXiv paper; Journey C passed against the selected existing parsed Project Paper, and no mock is counted as final mainline acceptance.

## Regression

- [x] backend suite — `283 passed in 6.47s`
- [x] RAG targeted regression — `12 passed`
- [x] frontend build — `npm run build` passed; existing chunk-size warning only
- [x] Reader — full backend regression and canonical Reader route contract
- [x] RAG — full backend regression
- [x] remote import — deterministic safety, configurable total-timeout and cancellation-cleanup tests pass; real arXiv stream acceptance passed
- [x] export — full backend regression
- [x] migration/schema — `0005_evidence_verification (head)` and compatible schema
- [x] frontend unit/type/lint — full Vitest `45 passed`; typecheck and lint pass
- [x] Playwright config — canonical smoke is listed; real browser run is unavailable because the local Chromium binary is not installed

## End

```text
End commit: this Block 8A implementation commit (see the commit containing this record)
Next phase readiness: YES — Phase 9 may begin in the next Implementation Block
```

---

# 14. Phase 9 — Cleanup & Long-term Docs

## Implementation Blocks

### Block 9C — Container Egress Proxy Configuration

Status: DONE — optional live proxy acceptance explicitly waived by the user on 2026-08-26; direct egress remains the V1 default

Scope:

- provide optional HTTP/HTTPS proxy injection for the backend and Worker containers;
- address the host-loopback versus container-network boundary with `host.docker.internal`;
- keep direct egress as the default when no proxy is configured;
- document proxy setup without committing credentials or making external proxy access a startup dependency.

Block acceptance:

- [x] Compose exposes optional proxy variables to backend and Worker;
- [x] unset proxy variables preserve direct network behavior;
- [x] host-gateway mapping is present for local Docker environments;
- [x] configuration and security guidance are documented;
- [x] existing backend/frontend regression suites remain green;
- [x] real proxied egress acceptance — N/A for V1 after the user's explicit waiver; direct egress acceptance passed.

Development and acceptance checks:

- `docker compose config --quiet` passed with and without proxy values;
- explicit Compose mapping assertions passed for backend/worker proxy variables and host-gateway entries;
- backend full regression: `283 passed in 6.10s`;
- frontend full Vitest: `47 passed`, typecheck, lint and production build passed (existing chunk-size warning only);
- direct network fallback is the accepted V1 path after the user's explicit proxy waiver;
- Worker direct Crossref smoke returned HTTP `200` / `ok`;
- one bounded direct arXiv metadata smoke returned `429`; it was not retried and does not change the provider decision;
- the earlier `host.docker.internal:7892` refusal and Mac-LAN timeout remain recorded as historical proxy-boundary evidence.

Implementation complete; optional external validation waived:

- the current host proxy listens only on `127.0.0.1:7892` / `::1:7892`;
- a container cannot reach that loopback listener through `host.docker.internal`;
- no host proxy configuration was changed automatically because enabling LAN/gateway access is a user-controlled security decision;
- the user explicitly chose to skip this optional proxy path, so no proxy setup or credential is required for V1.

Block Commit:

```text
d94fdb686759e697b246e04f90fe41aacd4680f2
```

### Block 9A — Product Surface and Dead-code Cleanup

Status: DONE

Includes:

- remove old primary product entrances
- verify references before deleting dead components / endpoints / CSS
- preserve compatibility where still required

Block acceptance:

- [x] no V1 route exposes old primary surfaces
- [x] deleted code has no remaining references
- [x] regression tests pass

Block Commit:

```text
this Block 9A implementation commit (see the commit containing this record)
```

### Block 9B — Long-term Documentation Sync

Status: DONE

Includes:

- `ARCHITECTURE.md`
- `API.md`
- `TODO_OR_RISKS.md`
- `SMOKE_TESTS.md`

Block acceptance:

- [x] long-term docs match actual final code
- [x] no future API is documented as current
- [x] archived docs remain clearly historical

Block Commit:

```text
this Block 9B documentation-sync commit (see the commit containing this record)
```


Status: DONE

## Goal

在主链稳定后删除无效产品入口和同步长期维护文档。

## Planned Cleanup

### UI

- [x] Research Map no longer exposed
- [x] Reading Plan no longer exposed
- [x] Evidence Matrix no longer exposed as primary page
- [x] Experiment Design no longer exposed
- [x] Activity no longer exposed
- [x] Project Chat no longer primary route

### Code

候选删除必须先检查引用：

```text
<fill>
```

### Docs

- [x] `ARCHITECTURE.md` matches actual system
- [x] `API.md` matches actual API
- [x] `TODO_OR_RISKS.md` current
- [x] `SMOKE_TESTS.md` includes V1 journeys
- [x] archived docs remain clearly archived

## Implementation Result

Status: DONE — Blocks 9A, 9B and 9C complete; Final V1 Acceptance Board passed

### Actual Files Changed

- `frontend/e2e/research-flow.spec.ts`: aligned the existing canonical smoke with the current login placeholders and `/home` post-login redirect; no product workflow behavior changed.
- `docs/ARCHITECTURE.md`: synced current runtime, Provider, Context, Writing/Citation and canonical route facts.
- `docs/API.md`: added current Paper, Project, Evidence, Discovery, Writing/Citation and Execution/SSE contracts; marked compatibility routes.
- `docs/TODO_OR_RISKS.md`: removed resolved provider/workspace/documentation risks and retained real residual risks.
- `docs/SMOKE_TESTS.md`: replaced the legacy project flow with the V1 Project → Discover → Papers → Writing smoke and bounded proxy check.

### Database / API / Deviation

- Database migration: none.
- API implementation: none; this Block synchronizes documentation for already implemented routes only.
- Spec deviation: none.

### Tests / Acceptance

- `frontend`: Vitest `47 passed`; `npm run typecheck`; `npm run lint`; `npm run build` passed (existing chunk-size warning only).
- `backend`: `docker compose run --rm backend python -m pytest -q` → `283 passed in 7.23s`.
- Documentation checks: `git diff --check` passed; canonical route/deleted-component reference checks passed; archived docs contain explicit historical/archive markers.
- Playwright: `PAPERAI_E2E=true npm run test:e2e` → `1 passed in 3.3s` after installing Chromium headless shell and clearing the stale frontend Vite overlay.
- Block acceptance: documentation checks and the explicitly waived optional Block 9C proxy acceptance are recorded above; no proxy credential or host-network change is required.

### End

```text
End commit: this Phase 9 final-acceptance commit (see the commit containing this record)
V1 readiness: YES
```

### Phase 9 final regression — 2026-08-26

- Backend: `docker compose run --rm backend python -m pytest -q` → `283 passed in 6.10s`.
- Backend undefined-name check: `ruff check app tests --select F821` → passed.
- Frontend: `npm run test` → `47 passed`; `npm run typecheck` → passed; `npm run lint` → passed; `npm run build` → passed with the existing chunk-size warning.
- Compose and schema: `docker compose config --quiet` → passed; Alembic current → `0005_evidence_verification (head)`; `scripts.check_schema_revision` → `compatible: true` with no missing/unexpected tables or columns.
- Runtime: backend/worker restarted with empty `PAPERAI_HTTP_PROXY` / `PAPERAI_HTTPS_PROXY`; both reported `direct`; `/health` returned healthy for database, Redis and Worker.
- Direct provider smoke: Worker → Crossref returned HTTP `200` / `ok`; one bounded Worker → arXiv metadata request returned `429` and was not retried. The approved real arXiv import had already passed in Phase 8.
- Playwright canonical V1 smoke: PASS — Chromium headless shell was downloaded with bounded resumable transfer into `/home/ddd/.cache/ms-playwright/chromium_headless_shell-1234`; user-space runtime libraries were loaded from `/tmp/pw-libs` via `LD_LIBRARY_PATH=/tmp/pw-libs/usr/lib/x86_64-linux-gnu:/tmp/pw-libs/lib/x86_64-linux-gnu`; the frontend container was restarted to clear a stale Vite overlay, and the canonical route smoke passed (`1 passed` in 3.3s).
- Phase acceptance: PASS — all Phase 9 Blocks and the Final V1 Acceptance Board are complete; the optional proxy acceptance is explicitly waived by the user.

### Post-V1 paper-processing retry maintenance — 2026-08-29

- Added an owned `POST /api/v1/papers/tasks/{task_id}/retry` contract. Failed core imports reuse the validated persisted PDF and existing `paper_process` Worker path; papers whose core text is already usable queue a media-only retry instead of rebuilding the text index.
- Media-only retry removes prior table/image database rows and derived vector chunks before rerunning the existing deterministic multimedia pipeline. Project ownership, persisted-PDF presence, retryable state and queue availability are validated server-side.
- `GET /api/v1/papers/` now returns owned pending/processing/failed import tasks that do not yet have a Paper row. The Library UI polls these tasks, shows failure messages, and exposes explicit import or media retry actions without adding a new product surface.
- Actual files changed: `backend/app/api/papers.py`, `backend/app/rag/knowledge_base.py`, `backend/app/worker.py`, `backend/tests/test_paper_retry.py`, `frontend/src/api/paper.ts`, `frontend/src/views/PaperList.vue`, `docs/API.md`, and this progress record.
- Database migration: none. API changes: one backward-compatible retry route and one backward-compatible `import_tasks` list-response field. Spec deviation: none.
- Acceptance: rebuilt backend/worker images; focused backend retry/task/processing regressions `11 passed`; full backend regression `286 passed`; backend undefined-name check passed; full frontend Vitest `51 passed`; frontend typecheck, ESLint and production build passed; `git diff --check` passed. The existing Vite chunk-size warning and pre-existing `papers.py` Ruff baseline remain informational; the new undefined-local findings were eliminated in the rebuilt image.
- Manual acceptance: no real user paper or failed task was mutated during this maintenance session; queue routing and task-state transitions are covered by automated tests. Remaining risk is limited to a future live failure-specific smoke against a disposable PDF.
- Next exact action: no further V1 block is pending; when a disposable failed import/media task is available, optionally exercise each explicit retry button once and confirm terminal task state.

---

# 15. Spec Deviation Log

任何偏离都放这里。

格式：

```markdown
## DEV-001 — <title>

Date:
Phase:
Status: PROPOSED / ACCEPTED / REJECTED

### Spec Requirement

...

### Code Reality

...

### Proposed Deviation

...

### Impact

...

### Decision

...
```

禁止在聊天里说过一次就算决策完成。

---

# 16. Database Migration Log

| Migration | Phase | Purpose | Applied Locally | Rollback Tested | Notes |
|---|---|---|---|---|---|
| `0005_evidence_verification` | 5 | Add durable Evidence lifecycle, source fingerprint and citation-verification fields | YES | YES | Empty-DB upgrade, `0005 → 0004 → 0005` round trip and schema validator passed |
| - | - | - | - | - | - |

---

# 17. API Change Log

| Phase | Method | Endpoint | Change | Backward Compatible | API.md Updated |
|---|---|---|---|---|---|
| 4 | GET | `/api/v1/projects/{project_id}/evidence`, `/api/v1/evidence/{evidence_id}` | Only expose Evidence whose Paper remains an active ProjectPaper | YES (integrity hardening) | YES |
| 4 | POST | `/api/v1/projects/{project_id}/evidence` | Reject unresolved section / element / chunk provenance with 422 | NO (invalid legacy payloads now rejected) | YES |
| 5 | POST | `/api/v1/documents/{document_id}/citation-audit` | Enforce deterministic integrity plus semantic support verification and return typed `verified / weak / unsupported` results | YES (existing `issues` / `passed` retained) | YES |
| 6 | POST | `/api/v1/projects/{project_id}/writing/agent/rewrite` | Add project-owned, revision-aware structured selection rewrite proposals with immutable citation mapping and mandatory citation re-verification | YES (new route; existing WritingDocument routes unchanged) | YES |
| 6 | POST | `/api/v1/projects/{project_id}/writing/agent/generate` | Add one-paragraph Project-paper-only generation through existing candidate/Evidence retrieval and mandatory structured citation verification | YES (new route; existing WritingDocument routes unchanged) | YES |
| Post-V1 | GET | `/api/v1/papers/` | Add owned pending/processing/failed `import_tasks` that do not yet have a Paper row | YES (additive response field) | YES |
| Post-V1 | POST | `/api/v1/papers/tasks/{task_id}/retry` | Retry a failed core import or only a failed media-enhancement stage through the existing Worker pipeline | YES (new route) | YES |
| - | - | - | - | - | - |

---

# 18. Configuration Change Log

| Phase | Variable | Required | Default | Purpose |
|---|---|---|---|---|
| 5 | `CITATION_VERIFIER_TIMEOUT_SECONDS` | NO | `30` | Bound each semantic citation-verifier call; valid range 1–120 seconds |
| - | - | - | - | - |

不得在聊天记录里新增环境变量而不写这里。

---

# 19. Removed / Deprecated Code Log

| Phase | File / API | Status | Replacement | Safe to Delete |
|---|---|---|---|---|
| - | - | - | - | - |

Status：

```text
HIDDEN
DEPRECATED
REMOVED
```

---

# 20. Test Baseline

Phase 0 / 1 期间填写真实命令。

```text
Backend test command:
Frontend build command:
Frontend test command:
Frontend lint command:
Frontend typecheck command:
```

Baseline results：

```text
<fill>
```

---

# 21. Final V1 Acceptance Board

## Product

- [x] Project creation
- [x] Overview
- [x] Discover
- [x] Project Papers
- [x] Existing Reader
- [x] Writing Workspace

## Discovery

- [x] Requirement clarification
- [x] Search Intent
- [x] Structured filters
- [x] Real Academic Search
- [x] <= 10 papers
- [x] Full abstract backend
- [x] Two-column cards
- [x] Details
- [x] Favorite
- [x] Download
- [x] Import

## Context

- [x] Project Profile
- [x] Literature Memory bounded
- [x] Paper Profile
- [x] Evidence
- [x] Context Manager

## Writing

- [x] Tiptap
- [x] Outline
- [x] Selection rewrite
- [x] Replace
- [x] Generate one paragraph
- [x] Imported papers only
- [x] Evidence retrieval
- [x] Structured citations
- [x] Citation verification
- [x] Copy
- [x] Revision
- [x] Export

## Quality

- [x] Backend tests for Phase 4 (124 passed)
- [x] Frontend build / typecheck
- [x] Reader regression
- [x] RAG regression
- [x] Export regression
- [x] E2E smoke — canonical Project → Overview → Discover → Papers → Writing route traversal passed
- [x] Docs current

---

# 22. Current Blockers

No active blocker. Phase 8 real arXiv and Qwen/DashScope validation passed; the optional Phase 9 proxy path was explicitly waived and direct egress passed. E2E-ENV-001 is resolved.

Historical resolution (`BLOCKER-001`, 2026-08-23): Semantic Scholar's anonymous HTTP 429 is now treated as a bounded, typed provider state under the updated user-approved strategy. Crossref public metadata enrichment supplies the credential-independent real-provider smoke. `SEMANTIC_SCHOLAR_API_KEY` remains optional and is not a Phase 2 blocker.

Blocker types:

```text
CODE
TEST
SPEC_DECISION
BLOCKED_BY_USER
EXTERNAL_SERVICE
```

若存在：

```markdown
## BLOCKER-001

Type:
Phase:
Block:
Detected:
Impact:
Root cause:

What was attempted:
- only bounded relevant attempts; do not log repeated random provider switching

Decision needed:

User action required:
- none / exact action

External service:
- none / provider

Required config / environment variable:
- none / ...

How to verify after unblock:

Next action:
```

## BLOCKER-002

Status: RESOLVED — real approved import passed on 2026-08-24.

Type: EXTERNAL_SERVICE
Phase: Phase 8 — End-to-End Integration
Block: Block 8A — V1 Mainline Integration
Detected: 2026-08-24
Impact: Resolved. Real import-dependent Reader acceptance passed and the existing Reader/RAG/export regressions remain passing.
Root cause: The host's fast curl used its loopback HTTP(S) proxy, while the container used a valid but slower direct route. The 2.2 MB PDF required 122.52 seconds, narrowly exceeding the former hard-coded 120-second whole-transfer deadline. The import route also performed this transfer synchronously, exceeding the frontend's 30-second request timeout.

What was attempted:
- bounded approved arXiv search and import smoke requests only;
- reproduced the proxy/direct-path difference without changing providers or weakening URL/PDF safety checks;
- made read/whole-transfer limits configurable at 45/300 seconds and moved the transfer to the existing Worker;
- completed one bounded real import of approved arXiv id `1706.03762` in 122.52 seconds and verified parsing, Project Papers attachment, Reader assets, Profile and retrieval.

Decision needed:
- none.

User action required:
- none.

External service:
- arXiv export PDF endpoint (`export.arxiv.org`)

Required config / environment variable:
- none; Semantic Scholar API key remains optional and unrelated.

How to verify after unblock:
- completed: real import produced paper `76e78683-4afb-4015-997c-90b2b2f74b1c`; Project Papers, PDF/full text/indexable elements, automatic Profile and real retrieval smoke passed.

Next action:
- no further action for this blocker; retain the same approved arXiv provider and bounded safety contract.

## BLOCKER-003

Status: RESOLVED — user authorization received and real validation passed on 2026-08-24.

Type: BLOCKED_BY_USER
Phase: Phase 8 — End-to-End Integration
Block: Block 8A — V1 Mainline Integration
Detected: 2026-08-24
Impact: Resolved. The existing-paper Writing → Evidence → Citation Verification journey passed as a real model-backed acceptance; Reader and deterministic retrieval contracts remain available.
Root cause: The selected paper's Profile and paragraph generation would send paper-derived text, project context and retrieved evidence to the configured external Qwen/DashScope endpoint. This external data-sharing authorization was not explicit in the request, so execution was stopped before the model call.

What was attempted:
- inspected non-secret LLM configuration flags; Qwen provider, DashScope-compatible base URL, Writing V2 and citation timeout are configured;
- completed the selected paper's owned Project Papers, Paper detail, Sections and indexable Elements HTTP smoke;
- did not send paper content to Qwen and did not try another model/provider.

Decision needed:
- none; authorization was granted and the configured provider was retained.

User action required:
- none; the user explicitly authorized this data sharing on 2026-08-24.

External service:
- Qwen through DashScope compatible API (`https://dashscope.aliyuncs.com/compatible-mode/v1`)

Required config / environment variable:
- existing root `.env` configuration: `LLM_PROVIDER=qwen`, `OPENAI_BASE_URL`, and `OPENAI_API_KEY`; no new key is needed if authorization is granted.

How to verify after unblock:
- queue one Paper Profile for the selected existing paper, wait for `ready`, call the existing one-paragraph Writing endpoint, verify Evidence persistence and Citation Verification statuses, then inspect the proposal without mutating the document.

Next action:
- no further action for this blocker; preserve Qwen/DashScope as configured and do not switch providers or fabricate Profile/Evidence content.

Verification result:
- PASS — Profile `ready`; Writing `200 / ready`; 4 Evidence rows; 4/4 Citation Verification statuses `verified`; document revision unchanged.

## BLOCKER-004

Status: WAIVED — implementation complete; the user explicitly waived the optional live proxied-egress acceptance on 2026-08-26.

Type: BLOCKED_BY_USER
Phase: Phase 9 — Cleanup & Long-term Docs
Block: Block 9C — Container Egress Proxy Configuration
Detected: 2026-08-24
Impact: None for V1 direct egress. The Compose wiring and direct fallback are complete; only the optional Mac-host proxy path remains unverified.
Root cause: The user's Mac proxy is healthy locally (`curl -x http://127.0.0.1:7892 https://api.crossref.org/v1/works?rows=1` returned HTTP 200), but PaperAI runs in a separate Ubuntu VM. Inside that VM, `host.docker.internal` resolves to the VM's Docker host rather than the user's Mac; the worker received `Connection refused`. After setting the Mac LAN address `192.168.101.105`, the worker received a TCP timeout, confirming the remote VM cannot route to that Mac address (network isolation or firewall).

What was completed:
- added optional proxy variables for backend and worker;
- added `host.docker.internal:host-gateway` mappings;
- documented direct fallback, security boundary and verification commands;
- Compose mapping and unset-proxy fallback checks passed.
- verified the user's Mac proxy itself with a real Crossref HTTP 200 response;
- verified the remote worker reads the configured proxy address;
- attempted one bounded worker TCP/Crossref smoke through `host.docker.internal:7892` and then `192.168.101.105:7892`; the first was refused and the second timed out.

User action required:
- none; the user chose the direct-egress path and no proxy setup is required for V1.

How to verify if this optional enhancement is reopened later:
- run the proxy smoke commands in `docs/SMOKE_TESTS.md`;
- verify backend and worker receive the proxy address without printing credentials;
- first confirm worker TCP connectivity to the proxy address/tunnel, then run one bounded arXiv/Crossref request through the Worker path.

No API key, billing, provider switch or repository secret is required.

## E2E-ENV-001

Status: RESOLVED — Chromium and its user-space runtime libraries are available; the canonical V1 E2E smoke passed on 2026-08-26.

Type: TEST
Phase: Phase 9 — Cleanup & Long-term Docs
Block: Phase 9 final regression / Final V1 Acceptance Board
Detected: 2026-08-26
Impact: Resolved. The browser-backed canonical V1 Playwright smoke passed and the Final V1 Acceptance Board is closed.
Root cause: The Playwright package is installed, but its Chromium binary is absent. A bounded `npx playwright install chromium` attempt was interrupted by the CDN closing the connection near completion.

What was completed:
- downloaded the official Chromium headless shell with a bounded resumable transfer;
- loaded the required Ubuntu runtime libraries from user-space temporary directories because sudo was unavailable;
- restarted the frontend container to clear a stale Vite error overlay;
- ran `LD_LIBRARY_PATH=/tmp/pw-libs/usr/lib/x86_64-linux-gnu:/tmp/pw-libs/lib/x86_64-linux-gnu PAPERAI_E2E=true npm run test:e2e` → `1 passed`.

User action required:
- none.

Next action:
- none; preserve the browser setup for future acceptance runs.

# 23. Handoff Summary

每次 Codex 会话结束前必须更新。

```markdown
## Latest Handoff

Date: 2026-08-29
Phase: Phase 9 — Cleanup & Long-term Docs
Status: DONE
Current Implementation Block: Phase 9 final regression / Final V1 Acceptance Board
Current Block Status: DONE
Last completed Block Commit: d94fdb686759e697b246e04f90fe41aacd4680f2 (Block 9C implementation); 38f72f9 (Block 9B docs)
Last commit: this post-V1 paper-processing retry commit (see the commit containing this record)

### What was completed

- Post-V1 paper-processing retry: failed imports now remain visible in the Library and can explicitly reuse their persisted PDF; already-readable papers can retry only failed/interrupted image and table enhancement without rebuilding the text index. Both paths preserve user ownership and run through the existing Worker/queue contracts.
- Retry acceptance: rebuilt backend/worker images; focused backend regressions `11 passed`, full backend `286 passed`, and undefined-name check passed; full frontend `51 passed`; typecheck, ESLint and production build passed; no migration or external-provider validation was required. API.md and the API Change Log include the additive list field and retry route.
- Post-V1 compact project-layout refinement: removed the redundant Writing page hero and outer workspace frame, reduced the global Project sidebar from 236px to 180px, reduced the Writing document/Agent rails to 176px/320px, expanded the editor paper to 860px, and made the workspace fill the viewport below the compact Project header.
- Post-V1 project UI density refinement: removed repeated English eyebrow labels from Overview, Discover and Papers; compacted Project header navigation, page padding, headings, overview entry cards, paper-table rows, Writing toolbar and Agent context/composer surfaces while preserving readable 16px manuscript text and coarse-pointer touch targets.
- The user-directed compact dimensions were synchronized into `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`; no Reader, Tiptap, WritingDocument, Evidence, citation or API contract was changed.
- Compact-layout acceptance: full frontend `51 passed`; typecheck, ESLint and production build passed. The existing Vite chunk-size warning remains informational. Impeccable detector reported only two known false positives for neutral 1px Writing column separators.
- Post-V1 project lifecycle maintenance: the existing owned `DELETE /api/v1/projects/{project_id}` contract is now exposed from Projects Home with a separate card action, explicit irreversible-impact confirmation, duplicate-submit protection, success removal and failure preservation. Original Library papers remain untouched because deletion removes Project-scoped associations and dependent records only.
- Post-V1 Discover defect fix: Paper detail Drawer visibility now uses `activePaper` as its single source of truth. Closing from the Drawer X, mask or Escape clears that source instead of mutating an unused parallel flag; duplicate close emission was removed. Component/store regressions cover the close request and state transition.
- Post-V1 performance diagnosis: backend/worker/database/Redis remained healthy with low CPU and memory use; the perceived UI delay was traced primarily to the frontend running the Vite development target with bind-mounted source, polling and automated probe noise. The frontend was rebuilt and recreated from the default production Compose target and now runs Nginx without source mounts.
- Post-V1 maintenance acceptance: frontend `51 passed`, ESLint passed, production build passed, project backend contracts `32 passed`, canonical production Playwright flow `1 passed`; production `/projects` HTML warm response measured about `0.5 ms` versus about `9.8 ms` from the previous development server on the same host. No schema migration or API change was required.
- Phase 9 Block 9C implementation: optional `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` injection is wired into backend and worker Compose services, with `host.docker.internal:host-gateway` support and direct access as the default.
- Phase 9 Block 9C documentation: `.env.example`, `ARCHITECTURE.md` and `SMOKE_TESTS.md` document host-loopback limitations, security boundaries and exact local verification steps; no credentials are committed.
- Phase 9 Block 9C configuration checks: explicit proxy mapping and unset-proxy direct fallback passed; the user's Mac proxy returned Crossref HTTP 200 locally, but the remote worker received `Connection refused` through `host.docker.internal:7892` and a TCP timeout through Mac LAN address `192.168.101.105:7892`. The user explicitly waived this optional proxy acceptance on 2026-08-26; the local runtime was restored to direct mode and Worker → Crossref returned HTTP 200.
- Phase 9 Block 9A acceptance: removed the unreachable legacy Project Workspace and universal Project Chat views plus their unreferenced Research Map, Reading/Experiment/Evidence/Activity UI components; legacy project chat now redirects to canonical Project Overview, Reader project comparison targets canonical Project Papers, and route/frontend/backend regressions passed.
- Phase 9 Block 9B acceptance: synchronized `ARCHITECTURE.md`, `API.md`, `TODO_OR_RISKS.md` and `SMOKE_TESTS.md` with the current code and accepted Provider decisions; removed resolved documentation/workspace/provider risks, added the V1 mainline smoke, and confirmed archived docs are explicitly historical.
- Phase 9 final acceptance: aligned the existing Playwright smoke with the current login route/placeholder contract; Chromium headless shell and user-space libraries were installed, and the canonical V1 route smoke passed.

- Completed Phase 2 Block 2A typed search DTOs, provider protocol, deterministic normalization, deduplication and full-abstract preservation.
- Semantic Scholar is the primary search provider using anonymous access first; API key support remains optional.
- Added Crossref public REST metadata enrichment with optional `CROSSREF_MAILTO` polite-pool identification.
- Preserved arXiv as the normalized preprint and approved downloadable full-text source.
- Added bounded timeout/429/Retry-After handling and provider contract tests; one real Crossref `/v1/works` smoke passed without credentials.
- Completed Block 2B bounded Search Planner → Provider → Normalize → Deduplicate → Quality/Retry → Finalize workflow.
- Added Redis-backed execution snapshots plus project-owned discovery search and execution-status API routes.
- Completed Block 2C project-scoped favorites, favorite-state projection, and safe arXiv import linkage through the existing parser/indexer pipeline.
- Phase 2 acceptance passed: 67 focused regression tests, Alembic head verification, and no external dependency blocker.
- Completed Phase 3 Block 3A: Requirement Chat, typed Search Intent editing, structured filters, discoverStore request state and user-readable search completion status.
- Block 3A frontend acceptance passed: 20 Vitest tests, typecheck, lint and production build; existing chunk-size warning only.
- Completed Phase 3 Block 3B: two-column result grid, full-abstract card expansion, detail Drawer, favorite filtering/toggling, safe download links, import states, and zero/partial/error states.
- Phase 3 acceptance passed: 27 frontend tests, frontend typecheck/lint/build, and 10 existing backend favorite/import contract tests; no schema migration was needed.
- Completed Phase 4 Block 4A: typed Project Profile and bounded Literature Memory DTOs, ownership-aware Discovery Context Manager, stable MemoryItem type policy, and typed lead-agent project context integration.
- Block 4A acceptance passed: Ruff plus 55 focused backend tests; no schema migration was needed.
- Completed Phase 4 Block 4B: stable Paper Profile schema on `ProjectPaper.analysis_card`, bounded generation, Worker triggers, retry/stale/version lifecycle and profile APIs.
- Block 4B acceptance passed: Ruff, 70 focused backend tests and one real Qwen structured-output smoke; no schema migration was needed.
- Completed Phase 4 Block 4C: deterministic five-paper shortlist, candidate-restricted Hybrid Retrieval, typed Writing Context/Evidence provenance, and active-membership/source-locator integrity.
- Phase 4 acceptance passed: Ruff, 124 backend regression tests, frontend lint/build/typecheck, Alembic head and schema validator; no schema migration was needed.
- Completed Phase 5 Block 5A: application-layer deterministic citation integrity, durable Evidence lifecycle/fingerprint fields, existing citation-audit integration and explicit unverified/unsupported outcomes.
- Block 5A acceptance passed: Ruff, 94 concentrated backend tests, backend image build, migration upgrade/downgrade/re-upgrade, local head `0005_evidence_verification` and compatible schema validation.
- Completed Phase 5 Block 5B: bounded structured semantic verifier, mandatory post-integrity verification, explicit weak/unsupported failure handling and one opt-in conservative claim adjustment/re-verification.
- Phase 5 acceptance passed: real Qwen direct-support/causation smoke, 145 backend Reader/RAG/export regression tests, frontend typecheck/lint/build, backend image build, Alembic head and schema validation.
- Completed Phase 6 Block 6A: free-form selection rewrite, bounded section/nearby context, structured proposals, stale-revision conflicts and immutable citation mappings on the existing Writing Service.
- Rewrite proposals never mutate WritingDocument or create revisions; citation-aware proposals reuse `CitationVerificationService` and preserve explicit weak/unsupported states.
- Block 6A acceptance passed: backend image and Ruff, 71 concentrated backend writing/revision/export/integrity regression tests, frontend typecheck/lint/build, and one configured real Qwen structured rewrite smoke.
- Completed Phase 6 Block 6B: one-paragraph Project-paper-only generation using the existing candidate selector, Hybrid Retrieval, Evidence persistence and mandatory Citation Verification path.
- Generated citations use model-visible temporary Evidence keys and server-resolved real paper/evidence IDs; claim-to-content, project ownership and source provenance are deterministic gates.
- Block 6B and Phase 6 acceptance passed: backend image/Ruff, 38 focused tests, real Qwen structured paragraph smoke, 278 full backend tests, frontend typecheck/lint/build, Alembic head and schema validation.
- Completed Phase 7 Block 7A: three-column Writing Workspace, live Tiptap-derived outline and current section path, bounded selection/nearby context in `writingStore`, Writing Agent context shell, accessible Agent/Outline collapse controls, and responsive desktop/tablet/mobile behavior.
- Block 7A acceptance passed: 34 frontend tests, frontend typecheck, lint, production build, and diff check; existing chunk-size warning only.
- Completed Phase 7 Block 7B: typed rewrite/generate proposal interaction, user-confirmed replace/copy actions, stale selection protection, structured Citation Node insertion, citation status and Evidence detail UI, and bounded loading/error/concurrency states.
- Block 7B and Phase 7 acceptance passed: 42 frontend tests, frontend typecheck/lint/build, 24 WritingDocument/revision/export backend tests, 11 Citation Verification tests, and diff check; existing chunk-size warning only.
- Phase 8 Block 8A implementation: Discover import returns immediately after queueing; the existing Worker owns the bounded arXiv download and parser pipeline, while the frontend keeps `ready` visibly in progress until terminal `completed` confirms Project Papers attachment.
- Phase 8 Block 8A integration smoke: canonical V1 route traversal was added to the Playwright smoke; real Crossref fallback search and favorite succeeded after bounded Semantic Scholar anonymous 429 handling.
- Phase 8 Block 8A implementation hardening: approved arXiv download has configurable 45-second read and 300-second whole-transfer deadlines plus cancellation-safe cleanup; deterministic timeout/cancellation tests pass.
- Phase 8 Block 8A integration hardening: duplicate imports with an existing `task_id` but no response `paper_id` continue polling the owned task-status endpoint; a focused store contract covers this path.
- Phase 8 Block 8A regression acceptance: full frontend `45 passed`, typecheck/lint/production build, full backend `283 passed`, undefined-variable Ruff check, backend/worker image builds, prior Alembic head/schema compatibility, health/root smoke and diff check passed.
- Phase 8 Block 8A real-paper Reader smoke: the selected existing paper passed owned Project Papers, Paper detail, Sections and indexable Elements HTTP checks.
- Phase 8 Block 8A real-paper model acceptance: after explicit user authorization, Qwen generated a `ready` Paper Profile; Writing returned `200 / ready`, persisted 4 Evidence rows, produced 4/4 `verified` citation mappings, and preserved the WritingDocument revision.
- Phase 8 Block 8A regression fix: structured image retrieval tolerates the current Image model's missing `bbox` attribute; real import also fixed two undefined media-indexing locals, and the full backend suite remains green at 283 tests.
- Phase 8 Block 8A real approved import: arXiv `1706.03762` downloaded in 122.52 seconds, parsed into paper `76e78683-4afb-4015-997c-90b2b2f74b1c`, attached to Project Papers, exposed valid Reader assets, generated a ready Profile, and returned five real retrieval chunks.

### What is currently in progress

- None. Phase 9 final regression and the Final V1 Acceptance Board are complete.
- The requested post-V1 paper-processing retry maintenance is complete; an optional live smoke may be run later against a disposable failed task.
- The requested post-V1 Project deletion UI and production-frontend performance correction are complete; no follow-up implementation is pending.
- Development and acceptance checks already run: Phase 6 Blocks 6A/6B, all Phase 7 Writing Frontend Blocks, and the non-import portions of Phase 8 are complete.
- External acceptance blockers: none. No API key, billing, provider switch or repository secret is needed.
- User action required: none. The optional Mac-host proxy path is not required.
- Real-provider validation: direct Worker → Crossref returned HTTP 200; the approved real arXiv import and Qwen/DashScope acceptance remain passed from Phase 8.
- Block note: Phase 9 and V1 readiness are complete; no new implementation Phase is opened.

### Do not redo

- Do not reimplement Block 2A provider DTOs, Crossref adapter, arXiv adapter, normalization or deduplication.
- Do not turn Crossref into the primary search provider or a full-text importer.
- Do not make `SEMANTIC_SCHOLAR_API_KEY` a V1 prerequisite or repeatedly retry anonymous 429 responses.
- Do not redo any Phase 2 provider, workflow, favorite, import, Reader, RAG, or execution work while continuing later phases.
- Do not redo the completed Phase 3 Discover frontend blocks; preserve the result card, favorite, import, Reader and existing project API contracts while starting Phase 4.
- Do not replace `ProjectPaper.analysis_card.paper_profile`, add a parallel Paper Profile table, or move generation out of the existing Worker queue.
- Do not restore direct all-project-paper retrieval in `project_search_content`; use the Context Manager → candidate selector → existing Hybrid Retrieval boundary.
- Do not add another Evidence table or treat transient retrieval chunks as verified citations.
- Do not reimplement Phase 5 integrity checks, semantic classification or migration `0005`; reuse `CitationVerificationService` and its durable status fields.
- Do not replace the completed semantic verifier, bypass it from evidence-backed writing, or treat `weak / unsupported / timeout` as verified.
- Do not redo Block 6A rewrite proposals, add automatic document writes, parse citation identity from prose, or replace the existing revision/export contracts.
- Do not redo Block 6B generation orchestration, let the frontend supply trusted paper/evidence IDs, add web search to Writing, or bypass mandatory verification.

### Next exact action

1. No further V1 implementation Block is pending.
2. If a disposable failed import/media task becomes available, optionally exercise each retry action once; do not use a real user paper for destructive failure simulation.
3. Preserve the explicit proxy waiver, direct-egress default, completed Phase 8, Block 9A, Block 9B and final E2E records.
4. Do not request a Semantic Scholar key or switch providers unless the provider decision is explicitly reopened.

### Read first next session

- `AGENTS.md`
- `docs/spec-v2/EXECUTION_INDEX.md`
- Progress: completed Phase 9, Final V1 Acceptance Board and this Handoff
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 9 only
- `01_CODEBASE_MIGRATION_MAP.md`: HIDE / REMOVE-LATER candidates only if continuing broader Phase 9 cleanup
- `ARCHITECTURE.md`, `API.md`, `TODO_OR_RISKS.md`, `SMOKE_TESTS.md`: current final-doc and proxy sections only
- `docker-compose.yml`, `.env.example`, direct-egress runtime and Compose config output
```

这是下一会话最重要的接续区。

---

# 24. Completion Rule

只有当：

```text
Phase 0–9 DONE
+
Final V1 Acceptance Board 全部满足
+
没有 P0 blocker
```

才将：

```text
V1 readiness: YES
```

否则不得在 README / Progress 中声称 V1 完成。

---

# 25. Historical Initial Handoff

```markdown
## Historical Handoff (not authoritative; see #23 Latest Handoff)

Date: 2026-08-23
Phase: Phase 1 — Project Foundation & Navigation
Status: IN_PROGRESS
Current Implementation Block: Block 1B — Project Product Shell
Current Block Status: NOT_STARTED
Last completed Block Commit: this Block 1A completion commit (see the commit containing this record)
Last commit: this Block 1A completion commit (see the commit containing this record)

### What was completed

- Block 1A added a typed Project `research_scope` contract for field, subject, question, goal, keywords, method direction and notes.
- Optional scope is compatibility-stored in existing `preferences.research_scope`; no schema migration was needed.
- Project CRUD ownership, transactions and Project paper list/add use cases now enter through `ProjectService`.
- Canonical `/projects/:projectId/{overview,discover,papers,writing}` routes resolve.
- Legacy `/project/:id` redirects to Overview and `/paper/:id` remains unchanged.
- `projectStore` exposes stable project id and typed research scope state.
- API documentation and backend/frontend contract tests were updated.

### What is currently in progress

- Current Block: Block 1B — Project Product Shell.
- Completed parts of this Block: none; Block 1A is complete.
- Remaining parts of this Block: Projects Home, Project Header, Overview, Discover shell, Papers page, Writing shell and four-tab navigation acceptance.
- Development checks already run: Block 1A backend ruff; 43 backend tests; 12 frontend tests; targeted frontend eslint; frontend production build.
- External dependency blockers: none.
- User action required: none.
- Real-provider validation pending: not applicable to Phase 1.

### Do not redo

- Do not recreate Project metadata columns; use the typed compatibility contract established in Block 1A.
- Do not replace `ProjectService` with direct API transaction logic.
- Do not recreate canonical routes or remove legacy/Reader compatibility.
- Do not rebuild Reader or Tiptap.
- Do not expose Research Map, Evidence Matrix, Experiment Design or Agent Activity as V1 primary navigation.

### Next exact action

1. Execute Phase 1 / Block 1B — Project Product Shell.
2. Replace the monolithic primary Project navigation with Overview / Discover / Papers / Writing shells while preserving underlying compatibility code.
3. Run Block 1B frontend tests/build and Reader route/opening acceptance before completing Phase 1.

### Read first next session

- `AGENTS.md`
- `docs/spec-v2/EXECUTION_INDEX.md`
- `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`:
  - current Phase / Block
  - Current Blockers
  - this Latest Handoff
- `00_PRODUCT_SCOPE.md`: Project navigation and Overview / Discover / Papers / Writing only
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Global shell, Projects Home, Project Header, Overview, Project Papers and Writing shell only
- `01_CODEBASE_MIGRATION_MAP.md`: ProjectWorkspace, ResearchProjectList, PaperReader and WritingDocumentEditor only
- `07_CODEX_IMPLEMENTATION_PLAN.md`:
  - Phase 1 / Block 1B only
- Directly related router, ProjectWorkspace, ResearchProjectList, project components, WritingDocumentEditor and frontend tests
```

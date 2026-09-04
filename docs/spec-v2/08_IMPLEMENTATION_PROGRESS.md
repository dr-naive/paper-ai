# PaperAI V1 Implementation Progress

> 文档状态：ACTIVE / LIVING DOCUMENT
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
Current Phase: Phase 8
Current Status: IN_PROGRESS
Current Implementation Block: Block 8A — V1 Mainline Integration
Current Block Status: NOT_STARTED
Block Start Commit: -
Block Commit: -
Last Updated: 2026-08-24
Last Commit: this Block 7B completion commit (see the commit containing this record)
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
| 7 | Writing Frontend | IN_PROGRESS | e6c5cb14af362e64d937e50a3e99ff72b3d56237 | - | NO |
| 8 | End-to-End Integration | NOT_STARTED | - | - | NO |
| 9 | Cleanup & Long-term Docs | NOT_STARTED | - | - | NO |

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
Next action: Phase 8 / Block 8A — V1 Mainline Integration; do not implement it in this session.
```

---

# 13. Phase 8 — End-to-End Integration

## Implementation Blocks

### Block 8A — V1 Mainline Integration

Status: NOT_STARTED

Includes:

- Project → Discover → Import
- Import → Reader
- Writing → Evidence → Citation Verification
- Selection Rewrite → Replace → Undo
- required regression fixes discovered during E2E

Block acceptance:

- [ ] all four E2E journeys pass
- [ ] backend suite passes
- [ ] frontend build passes
- [ ] Reader regression passes
- [ ] RAG regression passes
- [ ] export regression passes

Block Commit:

```text
<fill after the complete integration Block passes>
```


Status: NOT_STARTED

## Goal

验证 V1 主链真实可用。

## Baseline

```text
Start commit:
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

- [ ] create Project
- [ ] clarify
- [ ] search
- [ ] real papers
- [ ] favorite
- [ ] import

## E2E Journey B — Import → Reader

- [ ] Project Papers shows imported paper
- [ ] Reader opens
- [ ] PDF renders
- [ ] existing QA works
- [ ] independent Reader still works

## E2E Journey C — Writing with Citation

```text
Document:
Instruction:
Candidate papers:
Evidence count:
Generated citations:
Verified:
Weak:
Unsupported:
```

Acceptance:

- [ ] real Project Paper only
- [ ] real Evidence
- [ ] structured Citation Mapping
- [ ] verifier executed
- [ ] user can inspect source
- [ ] copy works

## E2E Journey D — Rewrite

- [ ] selection
- [ ] rewrite
- [ ] replace
- [ ] revision
- [ ] undo

## Regression

- [ ] backend suite
- [ ] frontend build
- [ ] Reader
- [ ] RAG
- [ ] remote import
- [ ] export

## End

```text
End commit:
Next phase readiness: NO
```

---

# 14. Phase 9 — Cleanup & Long-term Docs

## Implementation Blocks

### Block 9A — Product Surface and Dead-code Cleanup

Status: NOT_STARTED

Includes:

- remove old primary product entrances
- verify references before deleting dead components / endpoints / CSS
- preserve compatibility where still required

Block acceptance:

- [ ] no V1 route exposes old primary surfaces
- [ ] deleted code has no remaining references
- [ ] regression tests pass

Block Commit:

```text
<fill>
```

### Block 9B — Long-term Documentation Sync

Status: NOT_STARTED

Includes:

- `ARCHITECTURE.md`
- `API.md`
- `TODO_OR_RISKS.md`
- `SMOKE_TESTS.md`

Block acceptance:

- [ ] long-term docs match actual final code
- [ ] no future API is documented as current
- [ ] archived docs remain clearly historical

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

在主链稳定后删除无效产品入口和同步长期维护文档。

## Planned Cleanup

### UI

- [ ] Research Map no longer exposed
- [ ] Reading Plan no longer exposed
- [ ] Evidence Matrix no longer exposed as primary page
- [ ] Experiment Design no longer exposed
- [ ] Activity no longer exposed
- [ ] Project Chat no longer primary route

### Code

候选删除必须先检查引用：

```text
<fill>
```

### Docs

- [ ] `ARCHITECTURE.md` matches actual system
- [ ] `API.md` matches actual API
- [ ] `TODO_OR_RISKS.md` current
- [ ] `SMOKE_TESTS.md` includes V1 journeys
- [ ] archived docs remain clearly archived

## Implementation Result

Status: NOT_STARTED

### End

```text
End commit:
V1 readiness: NO
```

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

- [ ] Project creation
- [ ] Overview
- [ ] Discover
- [ ] Project Papers
- [ ] Existing Reader
- [ ] Writing Workspace

## Discovery

- [ ] Requirement clarification
- [ ] Search Intent
- [ ] Structured filters
- [ ] Real Academic Search
- [ ] <= 10 papers
- [ ] Full abstract backend
- [ ] Two-column cards
- [ ] Details
- [ ] Favorite
- [ ] Download
- [ ] Import

## Context

- [ ] Project Profile
- [ ] Literature Memory bounded
- [ ] Paper Profile
- [ ] Evidence
- [ ] Context Manager

## Writing

- [ ] Tiptap
- [ ] Outline
- [ ] Selection rewrite
- [ ] Replace
- [ ] Generate one paragraph
- [ ] Imported papers only
- [ ] Evidence retrieval
- [ ] Structured citations
- [ ] Citation verification
- [ ] Copy
- [ ] Revision
- [ ] Export

## Quality

- [x] Backend tests for Phase 4 (124 passed)
- [x] Frontend build / typecheck
- [x] Reader regression
- [x] RAG regression
- [x] Export regression
- [ ] E2E smoke
- [x] Docs current

---

# 22. Current Blockers

None.

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

# 23. Handoff Summary

每次 Codex 会话结束前必须更新。

```markdown
## Latest Handoff

Date: 2026-08-24
Phase: Phase 8 — End-to-End Integration
Status: IN_PROGRESS
Current Implementation Block: Block 8A — V1 Mainline Integration
Current Block Status: NOT_STARTED
Last completed Block Commit: this Block 7B completion commit (see the commit containing this record)
Last commit: this Block 7B completion commit (see the commit containing this record)

### What was completed

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

### What is currently in progress

- Current Block: Phase 8 / Block 8A — V1 Mainline Integration; not started.
- Development and acceptance checks already run: Phase 6 Blocks 6A/6B and all Phase 7 Writing Frontend Blocks are complete.
- External dependency blockers: none. Semantic Scholar anonymous HTTP 429 remains a handled provider state; its key is optional.
- User action required: none.
- Real-provider validation pending: none for Phase 6; configured Qwen returned valid rewrite and one-paragraph Evidence-key structured proposals.

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

1. Read only the Phase 8 headings listed in `EXECUTION_INDEX.md`: Phase 8 plan, completed-block summaries, Literature Discovery and Writing acceptance sections, `SMOKE_TESTS.md`, and relevant regression docs.
2. Inspect the actual Project → Discover → Import → Reader and Writing → Evidence → Citation Verification routes before changing code.
3. Implement only Block 8A mainline integration, then run the complete integration acceptance and create one meaningful commit.

### Read first next session

- `AGENTS.md`
- `docs/spec-v2/EXECUTION_INDEX.md`
- Progress: current Phase 8 / Block 8A, Current Blockers and this Handoff
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 8 only
- `04_LITERATURE_DISCOVERY.md`: Definition of Done / acceptance sections only
- `05_WRITING_WORKSPACE.md`: acceptance / Definition of Done sections only
- `SMOKE_TESTS.md`
- Relevant `QA_WORKFLOW.md`, `HYBRID_RETRIEVAL.md`, and export regression docs
- Existing Project, Discover, import, Reader, Writing, Evidence and Citation Verification routes; do not reread or redo completed Phase 7 frontend work
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

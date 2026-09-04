# PaperAI implementation rules

## Goal

Build PaperAI V1 as the research workflow defined by `docs/spec-v2/`, centered on:

```text
Project
→ Discover
→ Papers
→ Writing
```

without breaking the existing independent paper reader, PDF ingestion, parsing, retrieval, citation, chat, project ownership, execution, export, or deployment contracts.

The product goal is not to expose an Agent platform. Agent behavior is an internal implementation mechanism used only where uncertain reasoning is valuable.

## Source of truth

Do **not** read every long specification in full at the start of every Codex session.

For every normal implementation session, read in this order:

1. `AGENTS.md`
2. `docs/spec-v2/EXECUTION_INDEX.md`
3. `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`
   - `Overall Status`
   - current Phase / Implementation Block
   - `Current Blockers`
   - `Latest Handoff`
4. Only the current Block-specific specification sections listed by `EXECUTION_INDEX.md`
5. Only source files and tests directly related to the current Block

Read other long documents only when the current Block actually needs them.

If documents conflict, use this authority order:

1. `AGENTS.md`
2. `docs/spec-v2/EXECUTION_INDEX.md`
3. `docs/spec-v2/00_PRODUCT_SCOPE.md`
4. Relevant feature specification under `docs/spec-v2/`
5. `docs/spec-v2/02_TARGET_ARCHITECTURE.md`
6. `docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md`
7. `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`
8. `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md` for implementation state
9. Relevant long-term maintenance documents under `docs/`
10. `docs/archive/` for historical context only

`08_IMPLEMENTATION_PROGRESS.md` is authoritative for **what has actually been completed**, not for product design.

Documents under `docs/archive/` are historical context only and MUST NOT override current specifications.

Do not recursively read every document referenced by another document unless `EXECUTION_INDEX.md` explicitly requires it.

Do not rely on a referenced path unless it actually exists in the current branch.

## V1 product boundary

The Project product surface is intentionally limited to:

```text
Overview
Discover
Papers
Writing
```

Do not add or restore these as primary V1 product surfaces:

- Research Map
- Reading Plan
- Evidence Matrix
- Experiment Design
- Submission Suggestion
- Agent Activity / Agent Center
- Tool or Skill UI
- Universal Project Chat as the main Project interface

Existing underlying code may remain temporarily for compatibility, but new V1 work must not expand those product directions.

## Architecture boundaries

- API handles HTTP, validation, authentication, authorization, serialization, SSE transport, and error mapping only.
- Application services own use cases and transaction boundaries.
- Business workflows orchestrate deterministic steps and bounded Agent decisions.
- Domain and application code must not depend on Vue or frontend state.
- Agent code uses application/repository/service interfaces and must not directly operate ORM sessions.
- PostgreSQL is durable truth.
- Redis is for queueing, live state, cancellation, buffering, leases, temporary checkpoints, and short-lived cache.
- Existing deterministic PDF parsing, chunking, indexing, citation formatting, table lookup, export, and file validation remain deterministic workflows.
- Keep one primary Research Agent runtime. Do not build a general multi-agent platform.
- Existing Critique capability may remain, but do not add new SubAgents unless a current `spec-v2` document explicitly requires one.
- Do not create a second RAG, second editor, second execution runtime, or second Evidence system.

## Agent, Workflow, Tool, and Skill rules

Agent is used for uncertain decisions such as:

- clarifying research intent,
- generating complementary literature queries,
- judging whether search results are off-topic,
- deciding whether a bounded re-search is useful,
- selecting likely relevant project papers,
- deciding what evidence is needed for a writing request,
- generating or rewriting academic text.

Deterministic code handles:

- structured search filters,
- pagination,
- provider request/response normalization,
- deduplication,
- DOI normalization,
- file download safety,
- project ownership,
- retrieval filters,
- citation referential integrity,
- required verification steps,
- citation rendering,
- persistence.

Tools must remain atomic, typed, permission-classified, timeout-bound, cancellable where applicable, audited, and ownership-checked from runtime context.

Never trust model-supplied `user_id`, `project_id`, `paper_id`, or `evidence_id` without server-side ownership validation.

Do not create large workflow-shaped Tools that perform planning, search, filtering, import, analysis, and writing in one call.

Skills remain internal engineering concepts. Do not expose them as user-facing product choices.

## Project Context rules

Do not treat Project Context as one giant memory string.

Keep these concepts separate:

```text
Project Profile
Literature Memory
Paper Profile
Evidence
Writing Context
```

Ordinary conversation history is not automatically long-term Project Memory.

Do not place all project papers, all full text, all chats, all memory, and the full writing document into every Agent prompt.

Writing should narrow context in stages:

```text
Project Profile
→ relevant Paper Profiles
→ candidate papers
→ full-text retrieval
→ Evidence
```

Paper Profile helps decide which paper may be relevant.

Evidence is the source-traceable support used for writing and citation.

## Literature Discovery rules

Literature Discovery is a two-stage product flow:

```text
Requirement clarification
→ Search Intent
→ user-editable structured filters
→ real academic search
```

Structured filters must be applied deterministically whenever the provider supports them.

At minimum V1 considers:

- year range,
- language,
- field,
- publication type.

Search providers return normalized structured paper objects.

Do not return search results as prose that the frontend must parse.

The backend must preserve the full abstract returned by the provider. UI truncation belongs to the frontend.

Search is bounded. Do not perform infinite query reformulation.

If fewer than 10 valid real papers are found, return fewer than 10.

Never fabricate papers to reach a requested result count.

Favorite, Download, and Import are independent actions:

- Favorite stores metadata/links only.
- Download gives the user an available PDF.
- Import obtains approved full text and enters the existing PaperAI parse/index pipeline.

Search Provider and Remote Import Provider are separate concerns.

Do not turn the remote importer into an arbitrary URL downloader.

## Writing rules

Reuse the existing WritingDocument, revision, Tiptap, Citation Node, citation audit, and export foundations.

Do not rebuild the editor.

Writing Workspace is:

```text
Outline | Editor | Writing Agent
```

When text is selected:

```text
selection + instruction
→ proposal
→ user explicitly chooses Replace or Copy
```

The AI must never silently overwrite editor content.

When no text is selected, V1 generates one paragraph at a time.

Evidence-backed generation must use only papers that:

- belong to the current Project,
- have been formally imported,
- have completed parsing/indexing sufficiently for retrieval.

Do not cite:

- Discover-only search results,
- favorite-only metadata,
- model-memory papers,
- unverifiable web claims.

Writing Agent must not automatically search the web for new papers in V1.

Generated citations must use structured mappings, not only textual markers such as `[1]`.

Citation Verification is mandatory for evidence-backed generated claims.

Unsupported citations must not be presented as verified.

## Frontend rules

The user-facing product must not expose:

- Tool,
- Skill,
- ReAct,
- Harness,
- raw reasoning,
- chain-of-thought,
- raw provider payloads,
- raw execution event logs.

Show understandable user stages instead, such as:

- 正在明确检索需求
- 正在搜索相关论文
- 正在筛选结果
- 正在补充检索
- 正在查找支持证据
- 正在验证引用

Use Pinia for shared project/discovery/writing/workspace state as defined by the V1 specifications.

Preserve existing design tokens and reusable components where they remain valid.

Do not invent frontend-only capabilities.

No dead buttons, fake data, fake progress, fake citations, or permanently visible “coming soon” actions in core V1 flows.

The existing `PaperReader.vue` is a protected V1 asset. Make only the minimum changes required to connect Project Papers to it.

## Database rules

- Every schema change requires an Alembic migration.
- Never add startup `ALTER TABLE` statements.
- Never blindly stamp an existing database.
- Run schema preflight before applying migrations to an existing environment.
- Do not delete or rename columns without a documented compatibility migration.
- Production processes validate the current revision; a controlled migration step upgrades it.
- Prefer extending existing ResearchProject, ProjectPaper, WritingDocument, MemoryItem, EvidenceItem, and analysis-card structures over creating parallel V2 tables without evidence that extension is insufficient.

## External provider and file safety

Academic search providers and remote PDF import are separate layers.

For remote full-text import:

- preserve host allowlists,
- validate identifiers,
- validate content length,
- enforce file-size limits,
- validate PDF magic bytes,
- use temporary files and cleanup,
- do not bypass paywalls or publisher access controls,
- do not accept arbitrary user-supplied download URLs as trusted import sources.

## External Dependency Gate

External services include, for example:

- Academic Search Providers
- LLM providers
- Embedding providers
- third-party storage, conversion, or enrichment services

Before implementing against a new external service:

1. inspect existing project configuration and `.env.example`;
2. determine whether the service works without credentials;
3. determine whether an API key, account, paid quota, approval, console setup, or user authorization is required;
4. record the provider decision and required configuration in `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`.

Codex may independently:

- read official API documentation;
- compare only a small bounded set of providers already justified by the current spec;
- design provider interfaces;
- implement adapters;
- implement deterministic 401 / 403 / 429 / timeout handling;
- write unit and contract tests with mocked HTTP responses.

Codex must **not**:

- repeatedly switch providers merely because credentials are missing;
- invent credentials;
- repeatedly retry 401 / 403 / 429 responses;
- use unofficial workarounds to avoid normal provider requirements;
- weaken architecture or security to avoid asking the user for configuration;
- spend multiple implementation iterations trying arbitrary alternative services.

If implementation requires user-controlled action such as:

- registering an account;
- accepting third-party terms;
- obtaining an API key;
- entering a CAPTCHA;
- enabling billing or quota;
- configuring a third-party console;
- supplying a secret;
- granting external authorization;

then:

1. complete all code work that does not require the missing credential;
2. stop real-provider validation for that dependency;
3. record `BLOCKED_BY_USER` in `08_IMPLEMENTATION_PROGRESS.md`;
4. record provider/service, reason, exact user action, environment/config variable, configuration location, and verification method;
5. ask the user for that action;
6. do not try unrelated replacement providers unless the user or an authoritative specification explicitly reopens the provider decision.

Mocked external responses are allowed for unit tests, contract tests, and deterministic provider-error tests.

Mocks cannot satisfy:

- real-provider integration acceptance;
- end-to-end acceptance;
- production-readiness acceptance.

When code is complete but real validation is waiting on user configuration, record:

```text
IMPLEMENTATION_COMPLETE_EXTERNAL_VALIDATION_BLOCKED
```

The relevant Phase must not be marked fully `DONE` until required real-provider validation succeeds.

## Required implementation flow

All V1 implementation follows `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`.

Before a Phase starts:

1. inspect the actual current code,
2. read the relevant spec,
3. update `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`,
4. record the baseline commit and target files.

During implementation:

1. work on one coherent Implementation Block at a time,
2. batch related edits until that Block is functionally complete,
3. preserve reusable foundations,
4. add or update tests with the Block,
5. keep API contracts typed,
6. update `docs/API.md` for real API changes only,
7. record spec deviations instead of silently changing product behavior.

Before a Phase is marked complete:

1. run relevant backend tests,
2. run relevant frontend build/type/lint commands that actually exist in the repository,
3. run migration checks when schema changed,
4. verify Reader and export regressions when affected,
5. perform the Phase acceptance criteria,
6. update `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`.

Do not enter the next Phase before the current acceptance gate passes.

## Progress document rules

`docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md` is the handoff source of truth for implementation status.

Every Codex session must update it with:

- current Phase and status,
- start/end commit,
- actual files changed,
- database migrations,
- API changes,
- tests executed and results,
- manual acceptance results,
- deviations from spec,
- remaining risks,
- exact next action.

A future coding session should be able to continue from the progress document without relying on chat history.


## Development cadence

Do not use `edit → test → commit` as the unit of work.

The unit of work is a coherent **Implementation Block**.

An Implementation Block is a complete, independently understandable piece of implementation work, for example:

- Project shell and routing
- Academic search provider foundation
- Literature Discovery workflow and API
- Literature Discovery result UI
- Paper Profile generation
- Citation Verification
- Writing generation backend
- Writing Agent frontend

Individual DTOs, helper functions, single fields, small CSS changes, one endpoint, one test case, or a small bug fix inside the same block are **not** separate Implementation Blocks.

During implementation:

- batch related code changes until the current Implementation Block is functionally complete;
- targeted tests may be run when useful for debugging or validating a risky local change;
- do not run the complete relevant test suite after every small edit;
- do not create a commit after every small edit;
- once the Implementation Block is complete, run the relevant block-level tests and acceptance checks;
- fix all failures before committing;
- create one meaningful commit for the completed Implementation Block.

Broader regression tests are run at the **Phase acceptance gate**, not after every minor edit.

A complex Phase may contain several coherent Implementation-Block commits. A small Phase may contain only one.

Avoid micro-commits such as:

- add one field
- add one DTO
- fix one typo
- tweak one button
- add one test
- fix previous small change

Prefer commits such as:

```text
feat(discovery): implement normalized academic search foundation
feat(discovery): implement bounded search workflow and API
feat(writing): implement evidence-backed paragraph generation
```

Temporary debugging changes and small corrections made while completing the same block should remain part of that block rather than producing separate commits.

Development checks, acceptance tests, and commit boundaries are different concepts:

```text
Development check
= optional targeted validation while coding

Block acceptance
= relevant tests after a complete Implementation Block

Commit
= created only after the complete Block passes its acceptance checks

Phase regression
= broader regression after all Blocks in the Phase are complete
```

## Compatibility contracts to protect

Do not break without an explicit migration plan:

- existing PDF file paths and Paper IDs,
- Section / DocumentElement / Table / Image relationships,
- bbox-based citation/location behavior and PdfViewer integration,
- Hybrid/Table retrieval,
- existing LLM client abstraction,
- Redis worker and resumable execution/SSE foundations,
- AnswerTrace / RAG evaluation foundations,
- ResearchProject / ProjectPaper ownership,
- WritingDocument / revision / export foundations,
- JWT ownership,
- PostgreSQL / Redis / vector-store deployment contracts,
- legacy `/api/v1/chat` paths still used by existing Reader/chat flows.

## Baseline commands

Use repository-supported commands. Current root guidance includes:

```bash
docker compose build backend worker frontend
docker compose run --rm backend python -m pytest -q
docker compose run --rm backend alembic current
docker compose run --rm backend python -m scripts.check_schema_revision
cd frontend && npm run build
```

Before adding new required commands, verify they exist in the current repository and record them in `08_IMPLEMENTATION_PROGRESS.md`.

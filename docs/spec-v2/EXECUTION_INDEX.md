# PaperAI V1 Execution Index

> Status: ACTIVE / SESSION ENTRYPOINT
>
> Purpose: minimize repeated context loading for Codex.
>
> This file does not replace the full specifications. It tells Codex which small subset to read for the current Implementation Block.

---

# 1. Every-session reading budget

At the beginning of a normal implementation session, read:

```text
1. /AGENTS.md
2. docs/spec-v2/EXECUTION_INDEX.md
3. docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md
   - Overall Status
   - current Phase / Block
   - Current Blockers
   - Latest Handoff
4. only the current Block's spec sections listed below
5. only directly related code and tests
```

Do not automatically read all `00`–`08` documents in full.

Do not read `docs/archive/` unless historical comparison is explicitly needed.

If `Latest Handoff` lists a more precise set of headings or files, prefer that narrower set.

---

# 2. When full-document reading is justified

Read a full long specification only when:

- entering that feature family for the first time and its structure is still unclear;
- current implementation conflicts with multiple sections of the spec;
- a major architecture decision cannot be resolved from the listed sections;
- the user explicitly asks for a full audit.

Otherwise navigate by heading or search term.

---

# 3. Phase 0 — Documentation Authority

## Block 0A — Documentation Authority Migration

Read:

- `07_CODEX_IMPLEMENTATION_PLAN.md`
  - Phase 0
  - Codex session reading order
  - Context Window Discipline
- `08_IMPLEMENTATION_PROGRESS.md`
  - Overall Status
  - Phase 0
  - Current Blockers
  - Latest Handoff
- current:
  - `/AGENTS.md`
  - `docs/ARCHITECTURE.md`
  - `docs/TODO_OR_RISKS.md`
  - `docs/API.md`
  - `docs/DEV_NOTES.md`

Do not read feature specs `03`–`06` in full for this Block.

---

# 4. Phase 1 — Project Foundation & Navigation

## Block 1A — Project Contract and Route Foundation

Read:

- `00_PRODUCT_SCOPE.md`: Project creation, Project structure, V1 / non-V1 scope
- `01_CODEBASE_MIGRATION_MAP.md`: ResearchProject, ProjectPaper, projects API, routes / stores
- `02_TARGET_ARCHITECTURE.md`: API / Application boundary, Project domain
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 1 / Block 1A
- directly relevant current models, routes, stores, and tests

## Block 1B — Project Product Shell

Read:

- `00_PRODUCT_SCOPE.md`: Project navigation, Overview / Discover / Papers / Writing
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Global shell, Projects Home, Project Header, Overview, Project Papers, Writing shell only
- `01_CODEBASE_MIGRATION_MAP.md`: ProjectWorkspace, ResearchProjectList, PaperReader, WritingDocumentEditor
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 1 / Block 1B

Do not read the full Writing or Literature Discovery specs yet.

---

# 5. Phase 2 — Literature Discovery Backend

Primary feature spec: `04_LITERATURE_DISCOVERY.md`.

## Block 2A — Academic Search Foundation

Read `04` sections for:

- Search Request
- Search Budget
- Search Provider Interface
- Provider Capabilities
- V1 Provider Strategy
- Provider Result
- Normalized Result
- Abstract Rule
- Deduplication
- Testing - Provider
- Testing - Normalize
- Migration from Existing arXiv Search
- Migration from Semantic Scholar Existing Use
- Provider Configuration
- External Credential Boundary
- Rate Limit
- Security / Copyright Boundary

Also read:

- `01_CODEBASE_MIGRATION_MAP.md`: `external_literature.py`, `literature_research.py`, `remote_paper_import.py`
- `02_TARGET_ARCHITECTURE.md`: provider / normalized literature boundary
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 2 / Block 2A
- `/AGENTS.md`: External Dependency Gate

Before real-provider validation, fill Provider Decision and External Dependency fields in Progress. V1 uses Semantic Scholar unauthenticated-first, Crossref for metadata enrichment, and arXiv for preprint/approved PDF import; `SEMANTIC_SCHOLAR_API_KEY` is optional and must not block the public-path acceptance.

Do not try multiple providers indefinitely or switch providers merely because an optional key is unavailable.

## Block 2B — Discovery Workflow and API

Read `04` sections for:

- Search Workflow
- Search Planner
- Query generation rules
- Result Quality Check
- Retry Decision
- Final Selection
- Search Response
- Execution Progress
- Testing - Workflow
- Rate Limit
- Cache

Also read:

- `02_TARGET_ARCHITECTURE.md`: Workflow / Agent boundary, Execution / event mapping
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 2 / Block 2B

## Block 2C — Favorite and Import Integration

Read `04` sections for:

- Favorite
- Favorite Model
- Favorite Filter
- Download
- Download Security
- Import
- Import Security
- Testing - Favorite
- Testing - Import
- Security / Copyright Boundary

Also inspect existing `remote_paper_import.py` and its tests.

---

# 6. Phase 3 — Literature Discovery Frontend

## Block 3A — Requirement and Search UX

Read:

- `04_LITERATURE_DISCOVERY.md`: Requirement clarification, Search Intent, Structured Filters, Search Form, Execution Progress
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Discover page, forms, loading / error state, Discover responsive rules
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 3 / Block 3A

## Block 3B — Result Cards and Actions

Read:

- `04_LITERATURE_DISCOVERY.md`: Result Cards Layout, Paper Card Information Order, Abstract UI, Card Actions, Details, Favorite, Download, Import, Testing - Frontend, UI Visual Rules, Accessibility, user-visible errors
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Discover cards, Drawer, button / tooltip rules
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 3 / Block 3B

---

# 7. Phase 4 — Project Context & Paper Profile

Primary feature spec: `03_PROJECT_CONTEXT_AND_EVIDENCE.md`.

## Block 4A — Typed Project Context Foundation

Read `03` sections for Project Profile, Literature Memory, chat-history separation, Context Manager, token priority / budget.

Also read:

- `02_TARGET_ARCHITECTURE.md`: Context layer
- `01_CODEBASE_MIGRATION_MAP.md`: MemoryItem / Project model migration
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 4 / Block 4A

## Block 4B — Paper Profile Generation

Read `03` sections for Paper Profile, `analysis_card`, generation lifecycle, version / stale / retry.

Also inspect current ProjectPaper and parse-completion path.

## Block 4C — Candidate Papers and Evidence Retrieval

Read `03` sections for candidate-paper selection, retrieval, Evidence, provenance, cross-project isolation.

Also read relevant sections of `HYBRID_RETRIEVAL.md` and current retrieval tests.

---

# 8. Phase 5 — Citation Verification

Read:

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`: Citation Mapping, referential integrity, lexical gate, semantic verifier, Evidence validity
- `05_WRITING_WORKSPACE.md`: citation contract, citation status, verifier behavior
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 5 / current Block
- current citation-audit tests

---

# 9. Phase 6 — Writing Backend

## Block 6A — Writing Service Contract

Read:

- `05_WRITING_WORKSPACE.md`: rewrite selection, current section / nearby text, proposal contract, revision / export compatibility
- `01_CODEBASE_MIGRATION_MAP.md`: writing_service, WritingDocument / Revision
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 6 / Block 6A

## Block 6B — Evidence-backed Paragraph Generation

Read:

- `05_WRITING_WORKSPACE.md`: no-selection generation, Project-paper-only citation rule, Evidence retrieval, structured citation mapping, verification, failure states
- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`: candidate papers, Evidence retrieval, Citation Verification
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 6 / Block 6B

---

# 10. Phase 7 — Writing Frontend

## Block 7A — Workspace and Editor Context

Read:

- `05_WRITING_WORKSPACE.md`: three-column workspace, editor context, selection state
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Writing page layout, panel dimensions, responsive behavior
- `01_CODEBASE_MIGRATION_MAP.md`: WritingDocumentEditor
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 7 / Block 7A

## Block 7B — Proposal and Citation Interaction

Read:

- `05_WRITING_WORKSPACE.md`: Proposal Card, Replace / Copy, stale selection, citation status / details, loading / error / concurrency
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`: Writing Agent panel, citation status UI
- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 7 / Block 7B

---

# 11. Phase 8 — End-to-End Integration

Read:

- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 8 only
- `08_IMPLEMENTATION_PROGRESS.md`: completed Block summaries, Current Blockers, Latest Handoff
- `04_LITERATURE_DISCOVERY.md`: Definition of Done / acceptance sections only
- `05_WRITING_WORKSPACE.md`: acceptance / Definition of Done sections only
- `SMOKE_TESTS.md`
- relevant regression docs: `QA_WORKFLOW.md`, `HYBRID_RETRIEVAL.md`, export tests / docs

Do not reread full feature specs unless an integration failure requires it.

---

# 12. Phase 9 — Cleanup & Long-term Docs

Read:

- `07_CODEX_IMPLEMENTATION_PLAN.md`: Phase 9 only
- `08_IMPLEMENTATION_PROGRESS.md`: final implementation facts
- `01_CODEBASE_MIGRATION_MAP.md`: HIDE / REMOVE-LATER candidates
- current `ARCHITECTURE.md`, `API.md`, `TODO_OR_RISKS.md`, `SMOKE_TESTS.md`

Use actual final code as the source for long-term documentation.

Do not copy future-state wording from `spec-v2` into long-term docs if it was not actually implemented.

---

# 13. External service stop rule

If the current Block reaches a missing external credential or user-controlled setup:

```text
credential / account / billing / console / approval required
→ finish credential-independent implementation
→ record BLOCKED_BY_USER
→ ask user for exact action
→ stop real-provider validation
```

Do not do:

```text
provider A missing key
→ try provider B
→ provider B limitation
→ try provider C
→ rewrite architecture
```

unless the current Provider Decision is explicitly reopened.

Provider exploration should be bounded to candidates justified by the current spec and should end with one recorded decision.

---

# 14. Session-end rule

Before ending a session, update `Latest Handoff` with:

```text
Current Phase
Current Block
Completed
Remaining
Development checks already run
Block acceptance status
External dependency blockers
User action required
Real-provider validation pending
Exact next action
Exact spec headings next session should read
Exact code files next session should inspect
```

The handoff should become progressively narrower.

The next session should not need to rediscover the whole architecture.

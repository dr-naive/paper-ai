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
Branch: <fill>
Current Phase: Phase 0
Current Status: NOT_STARTED
Current Implementation Block: <fill>
Current Block Status: NOT_STARTED
Block Start Commit: <fill>
Block Commit: <fill after completion>
Last Updated: <fill>
Last Commit: <fill>
```

---


# 1.1 Implementation Block Status

Allowed Block Status:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
```

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
| 0 | Documentation Authority & Baseline | NOT_STARTED | - | - | NO |
| 1 | Project Foundation & Navigation | NOT_STARTED | - | - | NO |
| 2 | Literature Discovery Backend | NOT_STARTED | - | - | NO |
| 3 | Literature Discovery Frontend | NOT_STARTED | - | - | NO |
| 4 | Project Context & Paper Profile | NOT_STARTED | - | - | NO |
| 5 | Citation Verification Backend | NOT_STARTED | - | - | NO |
| 6 | Writing Backend | NOT_STARTED | - | - | NO |
| 7 | Writing Frontend | NOT_STARTED | - | - | NO |
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

# 4. Current Known Risks

只记录当前真实存在的风险。

初始建议：

```text
RISK-001
lead_agent.py responsibilities are too broad.

RISK-002
literature_research.py responsibilities are too broad.

RISK-003
ProjectWorkspace.vue exposes too many non-V1 product surfaces.

RISK-004
Academic search provider selection and rate limits are not yet finalized.

RISK-005
Current citation audit is not sufficient as final semantic support verification.

RISK-006
Legacy documentation can conflict with spec-v2 until Phase 0 is completed.
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

Status: NOT_STARTED

Includes:

- add `docs/spec-v2/`
- create `docs/archive/`
- archive legacy Agent documents
- replace / update current authority documents
- initialize this Progress document

Block acceptance:

- [ ] spec-v2 exists
- [ ] archive exists
- [ ] AGENTS.md authority points to spec-v2
- [ ] archived docs cannot override current specs
- [ ] no business runtime code changed
- [ ] `git diff --check` passes

Block Commit:

```text
<fill after the whole Block is complete>
```


Status: NOT_STARTED

## Goal

建立唯一文档权威关系，并记录施工基线。

## Spec References

- `docs/spec-v2/00_PRODUCT_SCOPE.md`
- `docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md`
- `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`

## Baseline

```text
Start commit:
Start date:
Codex session:
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

- [ ] Create `docs/spec-v2/`
- [ ] Create `docs/archive/`
- [ ] Add all current spec-v2 documents
- [ ] Archive legacy implementation specification
- [ ] Archive legacy upgrade context
- [ ] Update AGENTS.md authority order
- [ ] Mark ARCHITECTURE.md partially outdated during migration
- [ ] Update current risks

## Implementation Result

Status: NOT_STARTED

### Files Changed

```text
<fill>
```

### Tests Executed

```text
<fill>
```

### Manual Acceptance

- [ ] spec-v2 exists
- [ ] archive exists
- [ ] AGENTS.md points to spec-v2
- [ ] archived docs cannot override current specs
- [ ] no business code changed

### Deviations From Spec

```text
none / <fill>
```

### Remaining Risks

```text
<fill>
```

### End

```text
End commit:
End date:
Next phase readiness: NO
```

---

# 6. Phase 1 — Project Foundation & Navigation

## Implementation Blocks

### Block 1A — Project Contract and Route Foundation

Status: NOT_STARTED

Includes:

- Project metadata contract
- Project route foundation
- ownership / API compatibility
- projectStore adjustments

Block acceptance:

- [ ] project create / ownership tests pass
- [ ] deep routes resolve
- [ ] no Reader route regression

Block Commit:

```text
<fill>
```

### Block 1B — Project Product Shell

Status: NOT_STARTED

Includes:

- Projects Home
- Project Header
- Overview
- Discover shell
- Papers page
- Writing shell

Block acceptance:

- [ ] four Project tabs work
- [ ] default Overview works
- [ ] frontend build passes
- [ ] Reader still opens

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

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
Start commit:
Start date:
```

## Current Code Facts Rechecked

施工前填写：

```text
ResearchProject current fields:
ProjectPaper current fields:
Current project routes:
Current ProjectWorkspace responsibilities:
Current project stores:
```

## Target Files

```text
<fill after inspection>
```

## Planned Changes

- [ ] Project metadata contract
- [ ] Project routes
- [ ] Project Header
- [ ] Overview
- [ ] Discover shell
- [ ] Papers page
- [ ] Writing shell
- [ ] Project store cleanup

## Database Migrations

```text
none / migration id:
```

## API Changes

```text
<fill>
```

## Tests Planned

```text
<fill>
```

## Implementation Result

Status: NOT_STARTED

### Actual Files Changed

```text
<fill>
```

### Tests Executed

```text
command:
result:
```

### Manual Acceptance

- [ ] Create project
- [ ] Required name/topic
- [ ] Default Overview
- [ ] Four Project tabs
- [ ] Deep route refresh
- [ ] Project Papers works
- [ ] Existing Reader still works

### Deviations From Spec

```text
none / <fill>
```

### End

```text
End commit:
Next phase readiness: NO
```

---

# 7. Phase 2 — Literature Discovery Backend

## Implementation Blocks

### Block 2A — Academic Search Foundation

Status: NOT_STARTED

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

- [ ] Provider tests pass
- [ ] Normalize tests pass
- [ ] Dedup tests pass
- [ ] Filter tests pass
- [ ] Full abstract is preserved

Block Commit:

```text
<fill only after the entire Block is complete>
```

### Block 2B — Discovery Workflow and API

Status: NOT_STARTED

Includes:

- Search Planner
- bounded multi-round workflow
- result-quality check
- execution state
- discovery API
- error handling

Block acceptance:

- [ ] max rounds enforced
- [ ] partial results work
- [ ] zero results work
- [ ] provider failure works
- [ ] no fabricated papers
- [ ] API contract tests pass

Block Commit:

```text
<fill after Block completion>
```

### Block 2C — Favorite and Import Integration

Status: NOT_STARTED

Includes:

- favorite persistence
- favorite isolation
- import availability
- safe remote import linkage
- duplicate import handling

Block acceptance:

- [ ] favorite tests pass
- [ ] cross-project isolation passes
- [ ] import security tests pass
- [ ] duplicate import handling passes

Block Commit:

```text
<fill after Block completion>
```


Status: NOT_STARTED

## Goal

实现真实、结构化、受预算约束的 Academic Search backend。

## Spec References

- `02_TARGET_ARCHITECTURE.md`
- `04_LITERATURE_DISCOVERY.md`
- `07_CODEX_IMPLEMENTATION_PLAN.md`

## Baseline

```text
Start commit:
```

## Provider Decision

### Primary Provider

```text
Provider:
API:
Auth:
Rate limit:
Abstract coverage:
Year filter:
Language filter:
Field filter:
Publication type filter:
PDF/Open Access support:
Reason selected:
```

### Secondary / Enrichment Provider

```text
Provider:
Purpose:
```

### Existing arXiv Role

```text
Search / Fallback / Import / Other:
```

## Target Files

```text
<fill>
```

## Planned Changes

- [ ] Search DTO
- [ ] Provider interface
- [ ] Provider adapter
- [ ] Normalize
- [ ] Dedup
- [ ] Search planner
- [ ] max-round workflow
- [ ] discovery API
- [ ] favorites
- [ ] safe import linkage

## Configuration Added

```text
<env vars / settings>
```

## Database Migrations

```text
<fill>
```

## API Changes

```text
<fill>
```

## Tests Planned

- [ ] provider normalize
- [ ] full abstract preserved
- [ ] filters
- [ ] dedup
- [ ] max rounds
- [ ] zero results
- [ ] partial results
- [ ] provider errors
- [ ] favorites
- [ ] import

## Implementation Result

Status: NOT_STARTED

### Actual Files Changed

```text
<fill>
```

### Test Results

```text
<fill>
```

### Manual API Acceptance

```text
Search query:
Filters:
Result count:
Real papers verified:
Import tested:
```

### Deviations From Spec

```text
<fill>
```

### End

```text
End commit:
Next phase readiness: NO
```

---

# 8. Phase 3 — Literature Discovery Frontend

## Implementation Blocks

### Block 3A — Requirement and Search UX

Status: NOT_STARTED

Includes:

- Requirement Chat
- Search Intent ready state
- structured filters
- discoverStore state
- search execution progress

Block acceptance:

- [ ] clarification flow works
- [ ] Search Intent auto-fills
- [ ] filters are editable
- [ ] execution progress is user-readable
- [ ] frontend build passes

Block Commit:

```text
<fill>
```

### Block 3B — Result Cards and Actions

Status: NOT_STARTED

Includes:

- two-column grid
- PaperResultCard
- abstract clamp / expand
- PaperDetailDrawer
- favorite / download / import states
- zero / partial / error states

Block acceptance:

- [ ] two-column layout works
- [ ] abstract expand/collapse works
- [ ] disabled actions keep layout
- [ ] favorite works
- [ ] import works
- [ ] detail drawer works

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

完成 Discover 用户体验。

## Spec References

- `04_LITERATURE_DISCOVERY.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`

## Baseline

```text
Start commit:
```

## Target Components

```text
<fill>
```

## Planned Changes

- [ ] requirement clarification
- [ ] ready Search Intent
- [ ] filters
- [ ] execution state
- [ ] paper card grid
- [ ] detail drawer
- [ ] favorite
- [ ] download
- [ ] import
- [ ] disabled tooltip
- [ ] empty/error state

## Implementation Result

Status: NOT_STARTED

### Actual Files Changed

```text
<fill>
```

### Frontend Commands

```text
build:
typecheck:
lint:
tests:
```

### Manual Acceptance

- [ ] requirement conversation
- [ ] intent auto-fill
- [ ] intent editable
- [ ] structured filters
- [ ] two-column grid
- [ ] abstract 4-line clamp
- [ ] expand/collapse
- [ ] detail drawer
- [ ] favorite
- [ ] disabled download
- [ ] disabled import
- [ ] real import
- [ ] zero result
- [ ] partial result
- [ ] requirement collapse

### Screens / Notes

```text
<optional>
```

### End

```text
End commit:
Next phase readiness: NO
```

---

# 9. Phase 4 — Project Context & Paper Profile

## Implementation Blocks

### Block 4A — Typed Project Context Foundation

Status: NOT_STARTED

Includes:

- Project Profile access
- Literature Memory semantics
- Context DTOs
- stop new generic memory dumping

Block acceptance:

- [ ] typed Project Profile works
- [ ] ordinary chat is not automatically dumped into long-term context
- [ ] context tests pass

Block Commit:

```text
<fill>
```

### Block 4B — Paper Profile Generation

Status: NOT_STARTED

Includes:

- stable Paper Profile schema
- `analysis_card` evolution
- profile generation trigger
- retry / version / stale handling

Block acceptance:

- [ ] parsed imported paper gets profile
- [ ] failure does not block Reader
- [ ] regeneration works
- [ ] version metadata works

Block Commit:

```text
<fill>
```

### Block 4C — Candidate Papers and Evidence Retrieval

Status: NOT_STARTED

Includes:

- Context Manager
- candidate paper selector
- restricted Hybrid Retrieval
- Evidence provenance

Block acceptance:

- [ ] candidate paper restriction works
- [ ] evidence comes from real Project Papers
- [ ] cross-project isolation works
- [ ] no full-project prompt dump

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

建立 Project Profile、Literature Memory、Paper Profile、Evidence Retrieval 和 Context Manager。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `02_TARGET_ARCHITECTURE.md`

## Baseline

```text
Start commit:
```

## Existing Model Mapping

```text
ResearchProject.memory:
MemoryItem:
ProjectPaper.analysis_card:
EvidenceItem:
Current retrieval filters:
```

## Schema Decisions

### Project Profile

```text
Storage:
Fields:
```

### Literature Memory

```text
Storage:
Allowed types:
```

### Paper Profile

```text
Storage:
Schema version:
Generation model:
Generation trigger:
```

### Evidence

```text
New fields:
Verification fields:
Stale behavior:
```

## Target Files

```text
<fill>
```

## Database Migrations

```text
<fill>
```

## Implementation Result

Status: NOT_STARTED

### Tests

```text
<fill>
```

### Manual Acceptance

- [ ] imported parsed paper gets profile
- [ ] profile failure does not break Reader
- [ ] Context Manager does not dump all chats
- [ ] candidate paper selection works
- [ ] evidence retrieval restricted to candidate papers
- [ ] cross-project isolation

### End

```text
End commit:
Next phase readiness: NO
```

---

# 10. Phase 5 — Citation Verification Backend

## Implementation Blocks

### Block 5A — Deterministic Citation Integrity

Status: NOT_STARTED

Includes:

- Project / Paper / Evidence integrity
- stale / missing Evidence handling
- reuse current lexical gate

Block acceptance:

- [ ] wrong project rejected
- [ ] wrong paper rejected
- [ ] missing Evidence rejected
- [ ] stale Evidence rejected

Block Commit:

```text
<fill>
```

### Block 5B — Semantic Support Verification

Status: NOT_STARTED

Includes:

- verifier schema
- verified / weak / unsupported
- bounded retry / claim adjustment

Block acceptance:

- [ ] valid support verified
- [ ] weak support classified
- [ ] unsupported classified
- [ ] correlation / causation mismatch handled
- [ ] timeout handled

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

建立不可绕过的真实引用验证链。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `05_WRITING_WORKSPACE.md`

## Baseline

```text
Start commit:
Current citation audit:
Current lexical gate:
```

## Verifier Decision

```text
Verifier model:
Structured output:
Timeout:
Retry:
Confidence handling:
```

## Planned Changes

- [ ] referential integrity
- [ ] lexical gate reuse
- [ ] semantic verifier
- [ ] weak / unsupported
- [ ] claim adjustment
- [ ] verifier service
- [ ] tests

## Implementation Result

Status: NOT_STARTED

### Test Cases

```text
valid:
wrong project:
wrong paper:
missing evidence:
weak:
unsupported:
causation mismatch:
timeout:
```

### End

```text
End commit:
Next phase readiness: NO
```

---

# 11. Phase 6 — Writing Backend

## Implementation Blocks

### Block 6A — Writing Service Contract

Status: NOT_STARTED

Includes:

- free-form rewrite
- selection / section context
- current WritingDocument / revision / export compatibility
- structured proposal contract

Block acceptance:

- [ ] plain rewrite works
- [ ] citation-aware rewrite preserves mapping
- [ ] revision regression passes
- [ ] export regression passes

Block Commit:

```text
<fill>
```

### Block 6B — Evidence-backed Paragraph Generation

Status: NOT_STARTED

Includes:

- candidate papers
- Evidence Retrieval
- paragraph generation
- Citation Mapping
- Citation Verification
- failure codes

Block acceptance:

- [ ] verified paragraph generation works
- [ ] no-paper error works
- [ ] no-evidence error works
- [ ] unsupported citation is not marked verified

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

把当前写作固定 Action 升级成 Context-aware Writing Agent。

## Spec References

- `03_PROJECT_CONTEXT_AND_EVIDENCE.md`
- `05_WRITING_WORKSPACE.md`

## Baseline

```text
Start commit:
Current writing_service responsibilities:
Current WritingDocument API:
Current revision behavior:
Current export formats:
```

## Planned Changes

- [ ] free-form rewrite
- [ ] generate paragraph
- [ ] current section context
- [ ] candidate papers
- [ ] evidence retrieval
- [ ] structured citation mapping
- [ ] verification
- [ ] failure codes

## Compatibility Requirements

- [ ] WritingDocument unchanged or migrated safely
- [ ] Revision regression protected
- [ ] Existing export protected
- [ ] Existing Citation Node compatible

## API Changes

```text
<fill>
```

## Implementation Result

Status: NOT_STARTED

### Tests

```text
<fill>
```

### Manual Acceptance

- [ ] plain rewrite
- [ ] citation-aware rewrite
- [ ] evidence-backed generation
- [ ] no papers error
- [ ] no evidence error
- [ ] unsupported citation warning

### End

```text
End commit:
Next phase readiness: NO
```

---

# 12. Phase 7 — Writing Frontend

## Implementation Blocks

### Block 7A — Writing Workspace and Editor Context

Status: NOT_STARTED

Includes:

- three-column layout
- outline integration
- current section detection
- selection context
- Writing Agent panel shell

Block acceptance:

- [ ] layout works at desktop target sizes
- [ ] current section shows correctly
- [ ] selection state is correct
- [ ] frontend build passes

Block Commit:

```text
<fill>
```

### Block 7B — Proposal and Citation Interaction

Status: NOT_STARTED

Includes:

- rewrite proposal
- generate proposal
- replace / copy
- stale selection guard
- citation verification status
- Evidence detail
- progress / error states

Block acceptance:

- [ ] rewrite / replace works
- [ ] undo works
- [ ] generation / copy works
- [ ] verified / weak / unsupported states render
- [ ] save / export regressions pass

Block Commit:

```text
<fill>
```


Status: NOT_STARTED

## Goal

完成正式三栏 Writing Workspace 与右侧 Agent。

## Spec References

- `05_WRITING_WORKSPACE.md`
- `06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`

## Baseline

```text
Start commit:
Current WritingDocumentEditor:
Current editor extensions:
Current citation node:
Current revision UI:
```

## Planned Changes

- [ ] three-column layout
- [ ] outline
- [ ] selection context
- [ ] right Agent
- [ ] proposal card
- [ ] replace selection
- [ ] copy
- [ ] progress
- [ ] citation detail
- [ ] verification status
- [ ] panel collapse

## Implementation Result

Status: NOT_STARTED

### Test / Build Results

```text
<fill>
```

### Manual Acceptance

- [ ] selection detected
- [ ] current section shown
- [ ] rewrite proposal
- [ ] stale selection protected
- [ ] replace
- [ ] undo
- [ ] generation
- [ ] copy
- [ ] verified citation
- [ ] weak citation
- [ ] unsupported citation
- [ ] save
- [ ] export

### End

```text
End commit:
Next phase readiness: NO
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
| - | - | - | - | - | - |

---

# 17. API Change Log

| Phase | Method | Endpoint | Change | Backward Compatible | API.md Updated |
|---|---|---|---|---|---|
| - | - | - | - | - | - |

---

# 18. Configuration Change Log

| Phase | Variable | Required | Default | Purpose |
|---|---|---|---|---|
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

- [ ] Backend tests
- [ ] Frontend build
- [ ] Reader regression
- [ ] RAG regression
- [ ] Export regression
- [ ] E2E smoke
- [ ] Docs current

---

# 22. Current Blockers

```text
None.
```

若存在：

```markdown
## BLOCKER-001

Phase:
Detected:
Impact:
Root cause:
What was attempted:
Decision needed:
Next action:
```

---

# 23. Handoff Summary

每次 Codex 会话结束前必须更新。

```markdown
## Latest Handoff

Date:
Phase:
Status:
Current Implementation Block:
Current Block Status:
Last completed Block Commit:
Last commit:

### What was completed

- ...

### What is currently in progress

- Current Block:
- Completed parts of this Block:
- Remaining parts of this Block:
- Development checks already run:

### Do not redo

- ...

### Next exact action

1. ...
2. ...

### Files to read first next session

- ...
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

# 25. Initial Handoff

```markdown
## Latest Handoff

Date: 2026-08-19
Phase: Phase 0
Status: NOT_STARTED
Current Implementation Block: Block 0A — Documentation Authority Migration
Current Block Status: NOT_STARTED
Last completed Block Commit: none
Last commit: <fill when added to repo>

### What was completed

- Product scope has been redefined around:
  Project → Discover → Papers → Writing.
- Current codebase and legacy documents were reviewed.
- `spec-v2` documentation set was prepared.
- Legacy implementation specification was identified for archival.
- Existing Reader, RAG, Tool Runtime, WritingDocument, Tiptap, Citation Node,
  Evidence, remote import and execution foundations were identified as reusable assets.

### What is currently in progress

- No runtime code implementation has started under spec-v2.

### Do not redo

- Do not redesign the product from scratch.
- Do not rebuild Reader.
- Do not rebuild Tool Runtime.
- Do not rebuild Tiptap editor.
- Do not create a second RAG system.
- Do not continue the old Research Map / Experiment / Agent Activity product direction.

### Next exact action

1. Execute Phase 0 from `07_CODEX_IMPLEMENTATION_PLAN.md`.
2. Add `docs/spec-v2/` to the repository.
3. Archive legacy implementation documents.
4. Update `AGENTS.md` document authority.
5. Record real baseline commit and test commands here.

### Files to read first next session

- `AGENTS.md`
- `docs/spec-v2/00_PRODUCT_SCOPE.md`
- `docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md`
- `docs/spec-v2/07_CODEX_IMPLEMENTATION_PLAN.md`
- `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`
```

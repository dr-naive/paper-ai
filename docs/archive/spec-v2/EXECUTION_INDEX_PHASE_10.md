# Archived

Status: COMPLETED / HISTORICAL

This document records the completed Phase 10 execution boundaries. It is no
longer the active session entrypoint.

Do not use this document for current implementation decisions unless
historical context is explicitly required.

# Phase 10 Execution Rules

Codex must first read:

1. `/AGENTS.md`
2. this file
3. `08_IMPLEMENTATION_PROGRESS.md`

Then Codex may read only the spec sections, source files, and tests
explicitly listed for the current Implementation Block.

Do not read all `00–09` documents by default.

Do not read `docs/archive/` during normal implementation.

Archived documents are historical only.

If the current block cannot be completed because required information is
not listed here, stop and report the missing dependency instead of
broadly reading unrelated specs.

# PaperAI V1 Execution Index

> Status: COMPLETED / HISTORICAL SNAPSHOT
>
> This file is the sole entry point for deciding the current PaperAI
> Implementation Block reading boundary. It does not replace the active
> product and architecture specifications.

## Current Phase

Phase 10 — Frontend UI/UX Refinement (DONE)

Current Implementation Block:

UI-7 — Final Visual Regression and Acceptance (DONE)

## Active Authority Map

```text
00 / 02–05
→ product and business contracts

06
→ frontend information architecture and general design rules

09
→ Phase 10 exact UI implementation authority

07
→ current implementation plan

EXECUTION_INDEX
→ current Block read boundary

08
→ current execution progress

archive
→ historical only
```

## General Execution Rules

- Work on one coherent Implementation Block at a time.
- Read only the current Block's listed spec sections, source files and tests.
- Preserve existing backend contracts, database semantics, Agent architecture,
  product boundaries and protected Reader / Writing behavior.
- Do not expose Tool, Skill, ReAct, raw reasoning or raw execution events in the
  product.
- Do not introduce fake data, fake progress, fake citations or unrequested
  product surfaces.
- Run the current Block's listed acceptance checks before marking it complete.
- Record the result in `08_IMPLEMENTATION_PROGRESS.md` before starting another
  Block.

## Phase 10 — Frontend UI/UX Refinement

Phase 10 may refine the completed V1 frontend's visual quality, interaction
clarity and information hierarchy. It must not change backend contracts,
database semantics, Agent architecture or the four-page Project product scope.

### UI-1 — Design System Foundation

Read:

```text
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read sections concerning:

```text
Design Tokens
Color
Typography
Spacing
Radius
Control Height
Icons
Global Surface
Accessibility
```

Inspect source only:

```text
frontend/src/App.vue
frontend/src/main.*
frontend/src/styles/**
frontend/src/components/**  (global foundations and styles only)
frontend/package.json
```

Tests:

```text
Only existing frontend lint, typecheck and unit tests relevant to UI-1.
```

Forbidden:

```text
Do not modify business page structure.
Do not modify API contracts, Store contracts or Agent behavior.
```

### UI-2 — Global Shell and Projects

Read:

```text
00_PRODUCT_SCOPE.md
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read sections concerning:

```text
Global Navigation
Projects Page
Sidebar
Project Card
```

Inspect source only:

```text
Global Sidebar / App Shell components
Projects page
Project card components
Related scoped styles and tests
```

Forbidden:

```text
Do not modify Discover, Papers or Writing.
```

### UI-3 — Project Header and Overview

Read:

```text
00_PRODUCT_SCOPE.md
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read sections concerning:

```text
Project Navigation
Project Header
Project Overview
```

Inspect source only:

```text
ProjectShell
ProjectHeader
ProjectOverview
Related styles and tests
```

Product constraint:

```text
Overview
Literature Discovery
Project Papers
Writing
```

No fifth Project top-level page may be added.

### UI-4 — Literature Discovery

Read:

```text
04_LITERATURE_DISCOVERY.md
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read frontend display and interaction sections.

Inspect source only:

```text
LiteratureDiscover
Related discovery components
Related frontend store/client
Related tests
```

Forbidden:

```text
Do not change the literature backend contract, provider strategy or ranking
semantics.
Do not introduce a Semantic Scholar API key dependency.
```

### UI-5 — Project Papers

Read:

```text
03_PROJECT_CONTEXT_AND_EVIDENCE.md
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read sections concerning:

```text
Project Papers
Paper metadata
Reader navigation
Frontend interaction
```

Inspect source only:

```text
ProjectPapers
Related paper table / row components
Related styles and tests
```

Forbidden:

```text
Do not change paper persistence contracts.
Do not modify Reader backend behavior.
```

### UI-6 — Writing Workspace

Read:

```text
05_WRITING_WORKSPACE.md
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Only read sections concerning:

```text
Writing layout
Document editor
Outline
Writing Agent
Selection context
Proposal
Evidence
Citation
Revision
Citation audit
Quick Actions
```

Inspect source only:

```text
ProjectWriting
WritingOutlinePanel
WritingDocumentEditor
WritingAgentPanel
WritingProposalCard
Related composables, stores and clients
Related styles and tests
```

Protected semantics:

```text
proposal safety
base revision
selection conflict
citation structured nodes
evidence references
citation verification
revision protection
```

Forbidden:

```text
Do not let Agent actions overwrite正文 without confirmation.
Do not change Writing backend contracts, citation semantics or database schema.
```

### UI-7 — Final Visual Regression and Acceptance

Read:

```text
06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md
09_FRONTEND_UI_REDESIGN_IMPLEMENTATION_SPEC.md
```

Inspect only modified frontend files and frontend tests.

Validate:

```text
Projects
Overview
Discover
Papers
Writing
Sidebar
Project Header
responsive behavior
loading
empty
error
disabled
hover
focus-visible
selection
Agent proposal
Evidence
```

Run:

```text
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Do not introduce new features during UI-7.

## Phase 10 Block Completion

Before marking a Block DONE, update `08_IMPLEMENTATION_PROGRESS.md` with:

- implementation result and exact files changed;
- database migration result (normally `none` for Phase 10);
- API contract result (must remain unchanged);
- tests and acceptance results;
- manual visual checks, deviations and remaining risks;
- the exact next Block and its read boundary.

Do not begin UI-1 implementation in a documentation-cleanup session.

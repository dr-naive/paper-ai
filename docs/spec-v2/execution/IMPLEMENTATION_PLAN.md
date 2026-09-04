# PaperAI Implementation Plan

Status: COMPLETE

## Current Phase

None. Phase 16 — Guide Audit Remediation is complete.

## Current Implementation Block

None.

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

# PaperAI Execution Index

> Status: IDLE / SESSION ENTRYPOINT
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

None. Phase 16 is complete.

## Current Implementation Block

None.

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

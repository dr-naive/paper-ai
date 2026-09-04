# PaperAI Active Specifications

This directory contains current PaperAI product, architecture, feature,
frontend and execution documents. Files are grouped by responsibility rather
than implementation order.

## Session entrypoint

Every implementation session starts with:

1. [`AGENTS.md`](../../AGENTS.md)
2. [`execution/EXECUTION_INDEX.md`](execution/EXECUTION_INDEX.md)
3. [`execution/IMPLEMENTATION_PROGRESS.md`](execution/IMPLEMENTATION_PROGRESS.md)

The execution index defines the bounded reading scope for the current
Implementation Block. Do not load every specification by default.

## Structure

```text
spec-v2/
├── README.md
├── product/
│   └── PRODUCT_SCOPE.md
├── architecture/
│   └── SYSTEM_ARCHITECTURE.md
├── features/
│   ├── PROJECT_CONTEXT_AND_EVIDENCE.md
│   ├── LITERATURE_DISCOVERY.md
│   └── WRITING_WORKSPACE.md
├── frontend/
│   └── UI_SYSTEM.md
└── execution/
    ├── EXECUTION_INDEX.md
    ├── IMPLEMENTATION_PLAN.md
    └── IMPLEMENTATION_PROGRESS.md
```

## Authority by responsibility

- [`product/PRODUCT_SCOPE.md`](product/PRODUCT_SCOPE.md) defines the V1 product
  boundary and allowed surfaces.
- [`architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md)
  describes the current system and durable technical contracts.
- [`features/`](features/) contains active business workflow specifications.
- [`frontend/UI_SYSTEM.md`](frontend/UI_SYSTEM.md) combines frontend information
  architecture, visual semantics and interaction rules.
- [`execution/`](execution/) controls the current implementation phase, read
  boundary and factual handoff state.

Completed phase plans and progress records live under
[`docs/archive/spec-v2/`](../archive/spec-v2/README.md) and are historical only.

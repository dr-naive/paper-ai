# PaperAI implementation rules

## Goal

Build the Research Agent Workspace defined by `docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md` without breaking the existing paper ingestion, retrieval, citation, chat, project, or deployment contracts.

## Read before editing

1. This file.
2. `docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md` for the active phase.
3. `docs/PROJECT_AGENT_UPGRADE_CONTEXT.md` for current-system facts.
4. The relevant architecture, migration, Tool, Skill, frontend, or testing document.
5. `frontend/AGENTS.md` and `frontend/DESIGN_SYSTEM.md` before frontend work.

## Architecture boundaries

- API handles HTTP, validation, auth, serialization, and SSE only.
- Application services own use cases and transaction boundaries.
- Domain code does not depend on FastAPI, Redis, Chroma, LangChain, or Vue.
- Agent code uses application/repository interfaces and does not directly use ORM sessions.
- PostgreSQL is durable truth; Redis is queue, live state, cancellation, buffering, leases, and temporary checkpoints.
- Deterministic PDF, chunking, indexing, citation formatting, table lookup, and export remain workflows.
- Keep one ResearchAgent and the existing Critique Agent. Do not add a general multi-agent platform.

## Do not break

PDF paths and IDs; Section/DocumentElement/Table/Image; bbox citations and PdfViewer; Hybrid/Table retrieval; LLM client; Redis worker and resumable SSE; AnswerTrace and RAG evals; ResearchProject/ProjectPaper; JWT ownership; PostgreSQL/Redis/Chroma/Compose; legacy `/api/v1/chat` and existing ChatMessage reads.

## Database rules

- Every schema change requires an Alembic migration.
- Never add startup `ALTER TABLE` statements.
- Never blindly stamp an existing database. Run schema preflight first.
- Do not delete or rename columns without a documented compatibility migration.
- Production processes validate the revision; a single deployment migration job upgrades it.

## Tool and Skill rules

- Tools are atomic, typed, permission-classified, timeout-bound, cancellable, audited, and ownership-checked from runtime context.
- Never trust model-supplied `user_id`.
- Write/destructive behavior requires the policy defined in the implementation specification.
- Skills require versioned `skill.yaml`, method-oriented `SKILL.md`, allowed tools, permissions, budget, completion criteria, failure strategy, and eval cases.
- Do not add large workflow-shaped Tools or additional SubAgents.

## Frontend rules

- User copy must not expose Tool, Skill, ReAct, Harness, raw reasoning, or chain-of-thought.
- Results and evidence precede collapsed activity.
- Use Pinia for project/execution/workspace state as phases adopt it.
- Preserve existing `--pa-*` tokens and mandatory design-system behavior.
- No dead buttons, fake data, or frontend-only capabilities.

## Required quality flow

Inspect affected tests, make the smallest phase-scoped change, add/update tests, run the relevant suite, preserve RAG eval baselines, update contract docs, and report files/migrations/API/tests/compatibility/limitations. Do not enter the next phase before the current phase acceptance criteria pass.

## Commands

```bash
docker compose build backend worker frontend
docker compose run --rm backend python -m pytest -q
docker compose run --rm backend alembic current
docker compose run --rm backend python -m scripts.check_schema_revision
cd frontend && npm run build
```

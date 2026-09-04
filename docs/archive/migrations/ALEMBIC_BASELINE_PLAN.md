# Archived Alembic Baseline Plan

> Status: IMPLEMENTED / HISTORICAL IMPLEMENTATION RECORD
>
> Implemented and verified: 2026-08-17
>
> Baseline commit: `745d592` on `agent-rearchitecture-v1`
>
> This document records the completed Alembic baseline migration work.
> Its original governing specification has since been archived.
>
> Current V1 implementation authority: `docs/spec-v2/`
> Current database operating rules: `docs/database/MIGRATION_GUIDE.md`

## 1. Scope and stop boundary

This document began as the safety plan for PR-01, Baseline + Alembic. PR-01 has now been implemented without changing Agent Runtime, Tool, Skill, Redis, Chroma, or frontend business behavior. The existing PostgreSQL schema passed read-only preflight and was stamped at `0001_current_schema`; key row counts were unchanged.

The first implementation batch must stop after all of the following are true:

1. The current WIP state has a recoverable Git baseline.
2. Existing backend tests and smoke scenarios have recorded results.
3. Alembic can create the current schema in a new empty PostgreSQL database.
4. A database already matching the current schema can be inspected and stamped without running DDL.
5. Upgrade and downgrade behavior has been tested on disposable databases.
6. Runtime startup no longer silently performs schema evolution in production.

The first batch must not introduce `AgentExecution`, `AgentEvent`, `ToolCall`, `MemoryItem`, `EvidenceItem`, or Writing V2 tables. Those belong to later migrations after the baseline is established.

## 2. Current baseline facts

### 2.1 Git state

- Current branch: `main` at `894aaba` (`origin/main`).
- The working tree is not clean.
- It contains modified tracked files, deletion of the old `backend/app/skills/my_skill/` prototype, and untracked Project/Harness/backend/frontend/test files.
- Important untracked schema-bearing files include:
  - `backend/app/models/project.py`
  - `backend/app/api/projects.py`
  - `backend/app/harness/`
- `backend/app/main.py` already imports the untracked project models, so the current runtime schema is broader than the committed `main` schema.

Conclusion: the baseline revision must be generated from a named, reviewed WIP commit, not directly from an anonymous dirty tree. Otherwise the migration cannot be reproduced later.

### 2.2 Database initialization

Current startup behavior is implemented in `backend/app/database.py::init_db()` and is invoked by both the API lifespan and worker startup.

It currently performs:

1. `Base.metadata.create_all`.
2. A hand-written compatibility ALTER adding `users.role` if absent.
3. A hand-written compatibility ALTER adding `chat_sessions.project_id` if absent.
4. A PostgreSQL-only ALTER making `chat_sessions.paper_id` nullable.
5. Hand-written compatibility ALTERs adding `project_papers.analysis_card` and `project_papers.reading_plan`.

This means schema truth is currently split between ORM metadata and imperative startup inspection. A baseline generated from ORM metadata alone does not describe how every existing database reached its current shape.

### 2.3 Current ORM table set

The current working tree defines these application tables:

```text
users
papers
sections
document_elements
qa_pairs
notes
folders
tables
table_structures
table_cells
images
chat_sessions
chat_messages
summary_cache
interpret_cache
answer_traces
research_projects
project_papers
writing_artifacts
```

The future `alembic_version` table is not an application table.

### 2.4 Existing migration-related code

- No `alembic.ini`, Alembic environment, or revision directory exists.
- `backend/scripts/migrate_sqlite_to_postgres.py` migrates data between engines, but it is not a schema-version migration system.
- That script imports only a subset of current model classes. It omits at least Project models and newer document/table models from its explicit import list. It must not be used as evidence that the target schema is complete.
- Several maintenance scripts call `init_db()`, so changing startup behavior affects scripts as well as API/worker processes.

## 3. Phase 0 baseline status

### 3.1 Commands attempted

```text
git status --short
git branch --show-current
git log -8 --oneline --decorate
cd backend && pytest -q
docker compose ps --format json
```

### 3.2 Recorded result

- WIP baseline: branch `agent-rearchitecture-v1`, commit `745d592`.
- Backend tests after PR-01: `171 passed in 3.81s` using the backend container.
- Alembic tests: empty PostgreSQL upgrade, `alembic check`, downgrade, re-upgrade and head verification passed.
- Existing database: read-only preflight returned `compatible: true`; stamping changed no recorded key-table row counts.
- Drift behavior: an unexpected table in the disposable database was detected and caused a non-zero preflight result.
- Compose: the one-shot migrate service exited 0; backend, worker, PostgreSQL and Redis became healthy; frontend returned HTTP 200.
- HTTP health: `/health` reported database, Redis and worker healthy.

### 3.3 Phase 0 blocker resolution

The earlier host-level limitations (`pytest` missing and Docker socket unavailable) were resolved by running the supported container workflow after authorization. No Phase 0 blocker remains for PR-01.

## 4. Safe WIP baseline procedure

These actions are intentionally not executed by this document-generation task.

### 4.1 Review before staging

1. Confirm that deletion of `backend/app/skills/my_skill/` is intentional.
2. Confirm that all untracked Project/Harness files belong to the same WIP baseline.
3. Confirm no `.env`, database file, generated PDF, vector index, log, or secret is staged.
4. Save `git diff --stat`, `git diff`, and the untracked file list as review evidence.

### 4.2 Branch and commit

Recommended sequence after review:

```bash
git switch -c agent-rearchitecture-v1
git status --short
git add <explicit reviewed paths>
git diff --cached --check
git diff --cached --stat
git commit -m "wip: freeze research agent baseline"
```

Do not use `git add -A` until all deleted and untracked files have been reviewed. Do not squash this WIP commit into the Alembic implementation commit; the separation is valuable for diagnosis.

### 4.3 Required baseline test record

Run in the project-supported environment:

```bash
docker compose build backend worker
docker compose run --rm backend pytest -q
docker compose up -d db redis backend worker frontend
docker compose ps
```

Record:

- commit SHA;
- date and environment;
- pytest passed/failed/skipped counts and duration;
- service health output;
- any tests requiring live model credentials;
- failures already present before Alembic.

Manual smoke checklist:

```text
[ ] login
[ ] upload PDF
[ ] processing reaches ready
[ ] open PDF and outline
[ ] ask a paper question and receive citations
[ ] open project
[ ] project chat produces/resumes a response
```

Secrets must not be included in the record.

## 5. Proposed PR-01 file-level changes

The implementation PR should be limited to the following files and equivalent tests/docs.

```text
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/<revision>_baseline_current_schema.py
backend/app/database.py
backend/app/config.py                         # only migration/startup flags if required
backend/requirements.txt                     # add a pinned Alembic version
backend/tests/test_database_migrations.py
backend/scripts/check_schema_revision.py      # optional read-only preflight
docker-compose.yml                            # only an explicit migration command/service if selected
docs/migrations/ALEMBIC_BASELINE_PLAN.md
docs/database/MIGRATION_GUIDE.md
docs/database/SCHEMA.md
AGENTS.md                                     # required by the implementation spec
```

Do not move current model files into the target infrastructure directory in PR-01. Alembic adoption and large module relocation must not be combined.

## 6. Alembic environment design

### 6.1 Location and invocation

Keep Alembic under `backend/` so imports resolve consistently with the application package:

```bash
cd backend
alembic upgrade head
```

`alembic.ini` must not contain a production credential. `env.py` must read `DATABASE_URL` through the existing Settings path and override `sqlalchemy.url` at runtime.

### 6.2 Async engine

Use Alembic's async migration pattern with `async_engine_from_config` or an equivalent dedicated async engine. Do not import and reuse the application's global engine, because migration lifecycle and connection options are separate concerns.

Offline SQL generation must remain available where the dialect supports it:

```bash
alembic upgrade head --sql
```

### 6.3 Complete metadata registration

`env.py` must import every current model module before assigning:

```python
target_metadata = Base.metadata
```

At minimum:

```python
import app.models.user
import app.models.paper
import app.models.chat
import app.models.project
```

Relying on `main.py` side-effect imports is prohibited. The migration environment must be deterministic without starting FastAPI.

### 6.4 Autogenerate safeguards

Configure:

- `compare_type=True`;
- `compare_server_default=True` only after reviewing noisy differences between SQLite and PostgreSQL;
- deterministic naming for new constraints;
- an `include_object` guard that excludes Chroma/filesystem/temporary tables if any appear later.

Every generated revision must be manually reviewed. Autogenerate must never be applied directly to production.

### 6.5 PostgreSQL is the schema authority

The baseline migration is authored and tested against PostgreSQL 15, matching Compose. SQLite remains useful for isolated tests only where behavior is explicitly supported. PostgreSQL-specific JSON/UUID/default/nullability behavior must not be inferred from SQLite.

## 7. Baseline revision strategy

### 7.1 One current-schema baseline revision

Create one revision representing the entire schema frozen by the WIP commit:

```text
revision: <generated id>
down_revision: None
purpose: create the current pre-Runtime-v2 schema
```

Its `upgrade()` must create all 19 current application tables, indexes, unique constraints, and foreign keys in dependency-safe order. It must include the final intended state of the compatibility changes:

- `users.role` exists and is non-null with a safe server default for existing rows;
- `chat_sessions.project_id` exists;
- `chat_sessions.paper_id` is nullable;
- `project_papers.analysis_card` exists;
- `project_papers.reading_plan` exists.

The baseline must not replay the historical hand-written ALTER sequence on a new database. It creates the final current shape directly.

### 7.2 New empty database path

For a new database:

```text
empty database
→ alembic upgrade head
→ all current tables and indexes
→ application starts without schema DDL
```

Acceptance checks:

1. `alembic current` reports head.
2. SQLAlchemy Inspector table set matches the expected table manifest.
3. A second `alembic upgrade head` is a no-op.
4. Application and worker start successfully.
5. Existing backend tests pass.

### 7.3 Existing database path: inspect, then stamp

An existing database must never blindly run the baseline `upgrade()`, because its tables already exist.

Required operator flow:

```text
backup
→ read-only schema preflight
→ reconcile any drift with an explicit reviewed migration
→ alembic stamp <baseline_revision>
→ alembic current
→ application smoke test
```

`alembic stamp` only writes version state. It does not prove schema compatibility. The read-only preflight is mandatory.

The preflight must check at least:

- expected table presence;
- required columns and nullability;
- primary/foreign keys;
- named unique constraint `uq_project_paper`;
- important indexes;
- JSON-compatible column types;
- orphan rows that would violate expected foreign keys;
- duplicate `(project_id, paper_id)` pairs;
- null values before applying future non-null constraints.

If drift exists, do not stamp. Produce a database-specific reconciliation revision or operator script, test it on a restored copy, then stamp/upgrade.

### 7.4 Unknown older database path

The repository has no historical migration ledger, so an arbitrary old database cannot be safely inferred from version alone. Support only named, inspected starting states:

1. current WIP schema, stamp baseline;
2. known committed `main` schema, apply a reviewed reconciliation migration then stamp;
3. unknown schema, restore into a disposable database and generate a schema diff for manual classification.

Do not implement a migration that catches broad DDL exceptions or conditionally adds every missing object in one opaque revision. That would recreate the current startup-migration problem inside Alembic.

## 8. Startup transition

### 8.1 Target behavior

Production API and worker startup must validate that the database is at the expected Alembic revision and fail with an actionable message if it is not. They must not apply migrations automatically in each process.

Recommended deployment order:

```text
backup
→ one explicit `alembic upgrade head` job
→ start/restart backend
→ start/restart worker
→ health/smoke checks
```

This prevents backend and worker from racing to alter the same schema.

### 8.2 Temporary development fallback

The specification permits `create_all` only as an empty-development-database fallback. If retained temporarily, it must be explicit and default-off outside tests/local development, for example via a narrowly named setting such as `ALLOW_DEV_SCHEMA_CREATE`.

It must not:

- run hand-written ALTER statements;
- run in production by default;
- hide a missing Alembic upgrade;
- be invoked concurrently by API and worker.

The exact flag name is an implementation detail to decide in PR-01. Adding the flag must not change unrelated configuration.

### 8.3 Maintenance scripts

Scripts that currently call `init_db()` must be changed to validate schema readiness rather than create/alter it, unless a script is explicitly documented as a disposable local bootstrap tool.

Affected current files include:

- `backend/scripts/rebuild_vector_index.py`;
- `backend/scripts/backfill_table_structures.py`;
- `backend/scripts/backfill_document_elements.py`;
- `backend/app/worker.py`;
- `backend/app/main.py`.

## 9. Downgrade policy

The baseline downgrade is allowed only on a disposable database because it drops all application tables and data. It must never be presented as a production rollback mechanism.

Production rollback for PR-01 is:

1. stop new application processes;
2. deploy the prior application image;
3. leave the schema at the compatible baseline if no destructive DDL occurred;
4. restore a verified backup only if data/schema corruption occurred.

Future additive revisions should provide tested downgrades where data loss is not inherent. Any downgrade that drops data must state that explicitly in the revision docstring and migration guide.

Downgrade test for the baseline uses only a disposable database:

```text
upgrade head
→ verify schema
→ downgrade base
→ verify application tables removed
→ upgrade head again
→ verify schema recreated
```

## 10. Data risks and required mitigations

| Risk | Why it matters | Required mitigation before DDL/stamp |
|---|---|---|
| Dirty schema source | Current Project models are untracked | Freeze reviewed WIP commit and record SHA |
| `create_all` hides drift | It creates missing objects but does not evolve existing ones | Inspector-based preflight; no blind stamp |
| Hand-written startup ALTERs | Existing DBs may be at several intermediate shapes | Check each affected column/type/nullability explicitly |
| API and worker both initialize schema | Concurrent DDL/race risk | One explicit migration job; startup validation only |
| `users.role` default differences | ORM default is not necessarily DB server default | Inspect actual server default and normalize deliberately |
| `chat_sessions.paper_id` nullability | Project chat requires null paper_id | Count/validate rows and constraint before stamp |
| Project tables may be absent | They are untracked WIP additions | Detect table set; use named reconciliation path |
| JSON vs JSONB | Hand ALTER uses JSONB in PostgreSQL while ORM declares JSON | Choose canonical baseline type and test serialization/index expectations |
| UUID representation | Most IDs are `String(36)` while a GUID decorator exists | Preserve current physical types in baseline; do not normalize in PR-01 |
| Foreign-key delete behavior differs | Some FKs omit explicit `ondelete` | Reproduce current ORM contract; defer normalization |
| Duplicate indexes | `index=True` plus explicit indexes can generate overlapping indexes | Compare actual names/definitions before baseline finalization |
| SQLite divergence | SQLite cannot validate PostgreSQL ALTER/type behavior | PostgreSQL 15 is required for migration acceptance |
| SQLite migration script incomplete | Explicit imports omit current models | Update/test separately in PR-01 only if required for supported upgrade path |
| Data outside PostgreSQL | Chroma, Redis, PDF files are not covered by DB backup | Record separate backup/restore procedure; PR-01 must not mutate them |
| Model import omissions | Alembic could generate an incomplete schema | Explicit imports + expected table manifest test |
| Downgrade data loss | Baseline downgrade drops all tables | Disposable DB only; production rollback uses backup/deploy strategy |

## 11. Backup and preflight requirements

Before touching a real PostgreSQL database:

1. Create a timestamped `pg_dump` in custom format.
2. Verify the dump by listing its contents.
3. Restore it into a disposable database.
4. Run row-count and key-table checks on source and restore.
5. Preserve the Chroma directory and paper file volume separately.
6. Record current application commit and container image identifiers.

Do not place backup files in Git.

Minimum read-only inventory to save:

```text
PostgreSQL version
database name
table names
column/type/nullability/default manifest
constraints and indexes
row counts per application table
orphan/duplicate check results
```

## 12. Tests required in PR-01

### 12.1 Automated migration tests

Add tests that use a disposable PostgreSQL database and verify:

1. empty database → `upgrade head` succeeds;
2. table manifest exactly matches expected current schema plus `alembic_version`;
3. critical columns and nullability match the model contract;
4. critical unique constraints/FKs/indexes exist;
5. `upgrade head` is idempotent;
6. baseline `downgrade base` works only in the disposable test;
7. downgrade → upgrade recreates schema;
8. metadata diff after upgrade is empty or consists only of documented dialect noise;
9. a schema missing a required compatibility column is rejected by stamp preflight;
10. a matching existing schema passes preflight and can be stamped without changing row counts.

SQLite-only migration tests are insufficient.

### 12.2 Application regression tests

Run the complete existing backend suite before and after PR-01. At minimum retain explicit coverage for:

- auth/default admin;
- upload and paper processing services;
- chat/session/stream contracts;
- project contracts/retrieval;
- worker/job queue;
- security ownership tests.

### 12.3 Smoke tests

Repeat the Phase 0 manual checklist after migration. Compare behavior with the recorded baseline. No Agent answer-quality change is expected in PR-01.

## 13. Acceptance criteria

PR-01 is complete only when:

- [ ] WIP baseline commit and test record exist.
- [ ] Alembic dependency is pinned.
- [ ] Alembic config contains no credentials.
- [ ] All current models are imported deterministically.
- [ ] New PostgreSQL database upgrades from base to head.
- [ ] Existing matching database passes preflight and is stamped without DDL.
- [ ] Drifted database is rejected with a clear report.
- [ ] Upgrade/downgrade/re-upgrade passes on disposable PostgreSQL.
- [ ] API and worker do not race to mutate schema.
- [ ] Production startup refuses an out-of-date schema with an actionable error.
- [ ] Complete backend regression suite passes or pre-existing failures are explicitly recorded.
- [ ] Compose and manual smoke checks pass.
- [ ] No Paper/Chat/Project row counts change during stamp.
- [ ] No PDF, Chroma, or Redis data is modified.
- [ ] Migration guide and schema manifest are updated.

## 14. Exact next implementation slice

After the repository owner establishes the WIP baseline and a runnable test environment, the next scoped task should be:

```text
Implement PR-01 Alembic scaffolding and a current-schema baseline revision.
Add read-only schema preflight and PostgreSQL migration tests.
Replace production startup schema mutation with revision validation while retaining an explicit development-only empty-database fallback.
Do not add Execution Runtime tables and do not modify Agent, Tool, Skill, or frontend business behavior.
```

This is the only implementation slice authorized by Phase 1. Phase 2 starts only after PR-01 acceptance is recorded.

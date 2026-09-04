# Database Migration Guide

PaperAI uses Alembic for schema evolution. PostgreSQL is the authoritative production dialect.

## New database

```bash
cd backend
alembic upgrade head
```

Docker Compose runs the same command in the one-shot `migrate` service before backend and worker start.

## Existing database without `alembic_version`

Do not run the baseline upgrade over existing tables.

1. Back up PostgreSQL, Chroma, and paper files.
2. Run the read-only check:

   ```bash
   cd backend
   python -m scripts.check_schema_revision
   ```

3. Only when `compatible` is `true`, record the baseline without DDL:

   ```bash
   alembic stamp 0001_current_schema
   alembic current
   ```

4. Compare key row counts before and after stamp, then run smoke tests.

If preflight reports drift, do not stamp. Reconcile the named differences in a reviewed migration tested against a restored copy.

## Creating a revision

```bash
cd backend
alembic revision --autogenerate -m "describe the additive change"
```

Review generated DDL, ownership impact, defaults, nullability, downgrade data loss, and PostgreSQL behavior before applying it.

## Deployment

```text
backup → migrate service → backend/worker → health checks → smoke tests
```

API and worker validate the current revision and never evolve schema during startup.

## Downgrade

The baseline downgrade drops all application tables and is for disposable test databases only. Production rollback uses the previous application image and a verified backup where necessary.

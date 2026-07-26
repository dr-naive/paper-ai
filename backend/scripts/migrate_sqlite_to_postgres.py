"""Migrate PaperAI data from a local SQLite database to PostgreSQL.

Usage from the repository root:
    DATABASE_URL=postgresql+asyncpg://postgres:paperai-local@localhost:5432/paperai \
    python3 backend/scripts/migrate_sqlite_to_postgres.py --sqlite backend/paperai.db

When running against Docker Compose, publish the Postgres port first or run this
script from a container on the compose network with a DATABASE_URL using db:5432.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_SQLITE_PATH = BACKEND_DIR / "paperai.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate PaperAI SQLite data to PostgreSQL.")
    parser.add_argument(
        "--sqlite",
        default=str(DEFAULT_SQLITE_PATH),
        help="Source SQLite database path. Defaults to backend/paperai.db.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Target PostgreSQL URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete target table data before importing. Use only when the Postgres database is disposable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print source row counts; do not connect to PostgreSQL.",
    )
    return parser.parse_args()


def normalize_database_url(url: str | None) -> str:
    if not url:
        raise SystemExit("Target DATABASE_URL is required. Pass --database-url or set DATABASE_URL.")
    if url.startswith("sqlite"):
        raise SystemExit("Target DATABASE_URL must be PostgreSQL, not SQLite.")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def asyncpg_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def load_metadata() -> Any:
    from app.database import Base
    from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
    from app.models.paper import Folder, Image, Note, Paper, QAPair, Section, Table  # noqa: F401
    from app.models.user import User  # noqa: F401

    return Base.metadata


def load_sqlite_rows(sqlite_path: Path, table_name: str) -> list[sqlite3.Row]:
    with sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        exists = connection.execute(
            "select 1 from sqlite_master where type = 'table' and name = ?",
            (table_name,),
        ).fetchone()
        if not exists:
            return []
        rows = list(connection.execute(f"select * from {quote_ident(table_name)}"))
    return rows


def raw_source_counts(sqlite_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
            )
        ]
        for table_name in tables:
            counts[table_name] = connection.execute(
                f"select count(*) from {quote_ident(table_name)}"
            ).fetchone()[0]
    return counts


def model_source_counts(sqlite_path: Path, metadata: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True) as connection:
        for table in metadata.sorted_tables:
            exists = connection.execute(
                "select 1 from sqlite_master where type = 'table' and name = ?",
                (table.name,),
            ).fetchone()
            if not exists:
                counts[table.name] = 0
                continue
            counts[table.name] = connection.execute(
                f"select count(*) from {quote_ident(table.name)}"
            ).fetchone()[0]
    return counts


def sort_self_referencing_rows(table_name: str, rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    if table_name != "folders" or not rows:
        return rows

    by_id = {row["id"]: row for row in rows}
    visited: set[str] = set()
    sorted_rows: list[sqlite3.Row] = []

    def visit(row: sqlite3.Row) -> None:
        row_id = row["id"]
        if row_id in visited:
            return
        parent_id = row["parent_id"]
        if parent_id in by_id:
            visit(by_id[parent_id])
        visited.add(row_id)
        sorted_rows.append(row)

    for row in rows:
        visit(row)
    return sorted_rows


def convert_value(value: Any, column: Any) -> Any:
    from sqlalchemy import Boolean, DateTime, JSON

    if value is None:
        return None

    column_type = column.type

    if isinstance(column_type, JSON):
        if isinstance(value, (dict, list, int, float, bool)):
            return json.dumps(value, ensure_ascii=False)
        text = str(value).strip()
        if not text:
            return None
        json.loads(text)
        return text

    if isinstance(column_type, Boolean):
        return bool(value)

    if isinstance(column_type, DateTime):
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        return datetime.fromisoformat(text.replace("Z", "+00:00"))

    return value


def build_insert_sql(table: Any, columns: list[Any]) -> str:
    from sqlalchemy import JSON

    column_names = [quote_ident(column.name) for column in columns]
    placeholders = []
    for index, column in enumerate(columns, start=1):
        placeholder = f"${index}"
        if isinstance(column.type, JSON):
            placeholder += "::json"
        placeholders.append(placeholder)

    primary_keys = [column for column in columns if column.primary_key]
    if primary_keys:
        conflict_target = ", ".join(quote_ident(column.name) for column in primary_keys)
        update_columns = [column for column in columns if not column.primary_key]
        if update_columns:
            updates = ", ".join(
                f"{quote_ident(column.name)} = excluded.{quote_ident(column.name)}"
                for column in update_columns
            )
            conflict_clause = f" on conflict ({conflict_target}) do update set {updates}"
        else:
            conflict_clause = f" on conflict ({conflict_target}) do nothing"
    else:
        conflict_clause = ""

    return (
        f"insert into {quote_ident(table.name)} ({', '.join(column_names)}) "
        f"values ({', '.join(placeholders)})"
        f"{conflict_clause}"
    )


async def create_target_schema(database_url: str, metadata: Any) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
    finally:
        await engine.dispose()


async def truncate_target(connection: Any, metadata: Any) -> None:
    table_names = ", ".join(quote_ident(table.name) for table in reversed(metadata.sorted_tables))
    if table_names:
        await connection.execute(f"truncate table {table_names} restart identity cascade")


async def migrate(sqlite_path: Path, database_url: str, truncate: bool) -> None:
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    import asyncpg

    metadata = load_metadata()
    counts = model_source_counts(sqlite_path, metadata)
    print(f"Source SQLite: {sqlite_path}")
    for table_name, count in counts.items():
        print(f"{table_name}: {count} rows")

    await create_target_schema(database_url, metadata)
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        async with connection.transaction():
            if truncate:
                await truncate_target(connection, metadata)

            for table in metadata.sorted_tables:
                source_rows = sort_self_referencing_rows(table.name, load_sqlite_rows(sqlite_path, table.name))
                if not source_rows:
                    print(f"{table.name}: 0 rows")
                    continue

                source_columns = set(source_rows[0].keys())
                columns = [column for column in table.columns if column.name in source_columns]
                insert_sql = build_insert_sql(table, columns)

                imported = 0
                for row in source_rows:
                    values = [convert_value(row[column.name], column) for column in columns]
                    await connection.execute(insert_sql, *values)
                    imported += 1

                print(f"{table.name}: imported {imported} rows")
    finally:
        await connection.close()


def main() -> None:
    args = parse_args()
    sqlite_path = Path(args.sqlite)

    if args.dry_run:
        counts = raw_source_counts(sqlite_path)
        print(f"Source SQLite: {sqlite_path}")
        for table_name, count in counts.items():
            print(f"{table_name}: {count} rows")
        return

    database_url = normalize_database_url(args.database_url)
    asyncio.run(migrate(sqlite_path, database_url, args.truncate))
    print("Migration complete.")


if __name__ == "__main__":
    main()

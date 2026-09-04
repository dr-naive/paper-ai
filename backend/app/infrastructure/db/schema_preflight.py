"""Read-only comparison of an existing database with current ORM metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database import Base


@dataclass
class SchemaPreflightReport:
    compatible: bool = True
    missing_tables: list[str] = field(default_factory=list)
    unexpected_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    unexpected_columns: dict[str, list[str]] = field(default_factory=dict)
    nullability_mismatches: list[dict[str, Any]] = field(default_factory=list)
    missing_unique_constraints: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _compare_schema(sync_connection) -> SchemaPreflightReport:
    inspector = inspect(sync_connection)
    expected_tables = set(Base.metadata.tables)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    report = SchemaPreflightReport(
        missing_tables=sorted(expected_tables - actual_tables),
        unexpected_tables=sorted(actual_tables - expected_tables),
    )

    for table_name in sorted(expected_tables & actual_tables):
        model_table = Base.metadata.tables[table_name]
        expected_columns = {column.name: column for column in model_table.columns}
        actual_columns = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        missing = sorted(set(expected_columns) - set(actual_columns))
        unexpected = sorted(set(actual_columns) - set(expected_columns))
        if missing:
            report.missing_columns[table_name] = missing
        if unexpected:
            report.unexpected_columns[table_name] = unexpected

        for column_name in sorted(set(expected_columns) & set(actual_columns)):
            expected_nullable = bool(expected_columns[column_name].nullable)
            actual_nullable = bool(actual_columns[column_name].get("nullable"))
            if expected_nullable != actual_nullable:
                report.nullability_mismatches.append(
                    {
                        "table": table_name,
                        "column": column_name,
                        "expected_nullable": expected_nullable,
                        "actual_nullable": actual_nullable,
                    }
                )

        expected_uniques = {
            tuple(sorted(constraint.columns.keys()))
            for constraint in model_table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        actual_uniques = {
            tuple(sorted(item.get("column_names") or []))
            for item in inspector.get_unique_constraints(table_name)
        }
        for columns in sorted(expected_uniques - actual_uniques):
            report.missing_unique_constraints.append(
                {"table": table_name, "columns": list(columns)}
            )

    report.compatible = not any(
        (
            report.missing_tables,
            report.unexpected_tables,
            report.missing_columns,
            report.unexpected_columns,
            report.nullability_mismatches,
            report.missing_unique_constraints,
        )
    )
    return report


async def inspect_schema(engine: AsyncEngine) -> SchemaPreflightReport:
    """Inspect schema without issuing DDL or changing the Alembic revision."""
    async with engine.connect() as connection:
        return await connection.run_sync(_compare_schema)

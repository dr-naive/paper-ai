"""Guard concurrent administrator evaluations by type.

Revision ID: 0010_eval_active_guard
Revises: 0009_admin_evaluation_runs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_eval_active_guard"
down_revision: Union[str, None] = "0009_admin_evaluation_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_evaluation_runs_active_type",
        "evaluation_runs",
        ["evaluation_type"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'retrying')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'retrying')"),
    )


def downgrade() -> None:
    op.drop_index("uq_evaluation_runs_active_type", table_name="evaluation_runs")

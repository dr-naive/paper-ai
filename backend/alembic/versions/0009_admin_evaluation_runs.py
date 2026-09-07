"""Add durable administrator evaluation runs.

Revision ID: 0009_admin_evaluation_runs
Revises: 0008_agent_runtime_observability
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_admin_evaluation_runs"
down_revision: Union[str, None] = "0008_agent_runtime_observability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("report_path", sa.String(length=500), nullable=True),
        sa.Column("markdown_path", sa.String(length=500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_evaluation_runs_created", "evaluation_runs", ["created_at"], unique=False)
    op.create_index("idx_evaluation_runs_status", "evaluation_runs", ["status"], unique=False)
    op.create_index(
        "idx_evaluation_runs_type_created",
        "evaluation_runs",
        ["evaluation_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_evaluation_runs_type_created", table_name="evaluation_runs")
    op.drop_index("idx_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("idx_evaluation_runs_created", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

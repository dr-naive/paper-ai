"""add durable execution input and result payloads

Revision ID: 0006_execution_io
Revises: 0005_evidence_verification
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_execution_io"
down_revision: Union[str, None] = "0005_evidence_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_executions",
        sa.Column("input_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "agent_executions",
        sa.Column("result_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_executions", "result_payload")
    op.drop_column("agent_executions", "input_payload")

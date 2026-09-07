"""Mark papers created inside a project as project-only.

Revision ID: 0011_paper_scope
Revises: 0010_eval_active_guard
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_paper_scope"
down_revision: Union[str, None] = "0010_eval_active_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "papers",
        sa.Column(
            "is_project_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("papers", "is_project_only")

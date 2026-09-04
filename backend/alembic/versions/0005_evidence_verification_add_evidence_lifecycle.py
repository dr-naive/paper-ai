"""add evidence lifecycle and verification provenance

Revision ID: 0005_evidence_verification
Revises: 0004_writing_documents
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_evidence_verification"
down_revision: Union[str, None] = "0004_writing_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evidence_items",
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="imported_existing"),
    )
    op.add_column(
        "evidence_items",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("evidence_items", sa.Column("source_fingerprint", sa.String(length=64), nullable=True))
    op.add_column(
        "evidence_items",
        sa.Column("verification_status", sa.String(length=20), nullable=False, server_default="unverified"),
    )
    op.add_column("evidence_items", sa.Column("verification_reason", sa.Text(), nullable=True))
    op.add_column("evidence_items", sa.Column("verification_model", sa.String(length=200), nullable=True))
    op.add_column("evidence_items", sa.Column("verification_version", sa.String(length=50), nullable=True))
    op.add_column(
        "evidence_items",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_evidence_items_project_status",
        "evidence_items",
        ["project_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_evidence_items_project_status", table_name="evidence_items")
    op.drop_column("evidence_items", "updated_at")
    op.drop_column("evidence_items", "verification_version")
    op.drop_column("evidence_items", "verification_model")
    op.drop_column("evidence_items", "verification_reason")
    op.drop_column("evidence_items", "verification_status")
    op.drop_column("evidence_items", "source_fingerprint")
    op.drop_column("evidence_items", "status")
    op.drop_column("evidence_items", "source_type")

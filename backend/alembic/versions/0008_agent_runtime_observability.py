"""Add task-scoped ToolCall correlation and durable ModelCall traces."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_agent_runtime_observability"
down_revision: Union[str, None] = "0007_research_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("tool_calls", sa.Column("task_id", sa.String(36), nullable=True))
    op.add_column("tool_calls", sa.Column("skill_id", sa.String(120), nullable=True))
    op.create_foreign_key(
        "fk_tool_calls_task_id",
        "tool_calls",
        "research_tasks",
        ["task_id"],
        ["task_id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_tool_calls_task_step", "tool_calls", ["task_id", "step_index"])

    op.create_table(
        "model_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), sa.ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("skill_id", sa.String(120), nullable=True),
        sa.Column("call_index", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(160), nullable=False, server_default="unknown"),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("purpose", sa.String(120), nullable=False, server_default="agent_model_call"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("prompt_version", sa.String(120), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.task_id"], ondelete="SET NULL", name="fk_model_calls_task_id"),
    )
    op.create_index("idx_model_calls_execution_started", "model_calls", ["execution_id", "started_at"])
    op.create_index("idx_model_calls_task_started", "model_calls", ["task_id", "started_at"])
    op.create_index("idx_model_calls_skill_status", "model_calls", ["skill_id", "status"])


def downgrade():
    op.drop_index("idx_model_calls_skill_status", table_name="model_calls")
    op.drop_index("idx_model_calls_task_started", table_name="model_calls")
    op.drop_index("idx_model_calls_execution_started", table_name="model_calls")
    op.drop_table("model_calls")
    op.drop_index("idx_tool_calls_task_step", table_name="tool_calls")
    # The named migration constraint is used on a normal upgrade.  Inspecting
    # here also keeps downgrade compatible with development schemas created
    # directly from older ORM metadata, where PostgreSQL generated a name.
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys("tool_calls"):
        if foreign_key.get("referred_table") == "research_tasks" and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], "tool_calls", type_="foreignkey")
    op.drop_column("tool_calls", "skill_id")
    op.drop_column("tool_calls", "task_id")

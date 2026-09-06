"""Add goal plans and business tasks without rewriting historical executions."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0007_research_tasks'
down_revision: Union[str, None] = '0006_execution_io'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    for name in ('plan', 'progress', 'blockers'):
        op.add_column('agent_executions', sa.Column(name, sa.JSON(), nullable=True))
    op.add_column('agent_executions', sa.Column('plan_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_executions', sa.Column('completion_reason', sa.Text(), nullable=True))
    op.create_table('research_tasks',
        sa.Column('task_id', sa.String(36), primary_key=True),
        sa.Column('execution_id', sa.String(36), sa.ForeignKey('agent_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_type', sa.String(40), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        *[sa.Column(n, sa.JSON(), nullable=False, server_default=sa.text("'[]'")) for n in ('dependencies', 'input_refs', 'output_refs')],
        sa.Column('executor_type', sa.String(30), nullable=False),
        sa.Column('skill_id', sa.String(120)),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('completion_payload', sa.JSON()),
        sa.Column('blocker_reason', sa.JSON()),
        sa.Column('error_code', sa.String(80)),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
    )
    op.create_index('idx_research_tasks_execution_status', 'research_tasks', ['execution_id', 'status'])
    op.create_index('idx_research_tasks_execution_created', 'research_tasks', ['execution_id', 'created_at'])


def downgrade():
    op.drop_index('idx_research_tasks_execution_created', table_name='research_tasks')
    op.drop_table('research_tasks')
    for name in ('completion_reason', 'plan_version', 'blockers', 'progress', 'plan'):
        op.drop_column('agent_executions', name)

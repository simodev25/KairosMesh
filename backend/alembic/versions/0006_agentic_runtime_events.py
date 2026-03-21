"""agentic runtime events

Revision ID: 0006_agentic_runtime_events
Revises: 0005_agentic_runtime_storage
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

revision = '0006_agentic_runtime_events'
down_revision = '0005_agentic_runtime_storage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_runtime_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('analysis_runs.id'), nullable=False),
        sa.Column('session_key', sa.String(length=255), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('stream', sa.String(length=50), nullable=False),
        sa.Column('event_type', sa.String(length=120), nullable=False),
        sa.Column('actor', sa.String(length=120), nullable=False),
        sa.Column('turn', sa.Integer(), nullable=False),
        sa.Column('correlation_id', sa.String(length=255), nullable=True),
        sa.Column('causation_id', sa.String(length=255), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('run_id', 'seq', name='uq_agent_runtime_events_run_seq'),
    )
    op.create_index(op.f('ix_agent_runtime_events_id'), 'agent_runtime_events', ['id'], unique=False)
    op.create_index(op.f('ix_agent_runtime_events_run_id'), 'agent_runtime_events', ['run_id'], unique=False)
    op.create_index(
        'ix_agent_runtime_events_run_session_seq',
        'agent_runtime_events',
        ['run_id', 'session_key', 'seq'],
        unique=False,
    )
    op.create_index(op.f('ix_agent_runtime_events_session_key'), 'agent_runtime_events', ['session_key'], unique=False)
    op.create_index(op.f('ix_agent_runtime_events_seq'), 'agent_runtime_events', ['seq'], unique=False)
    op.create_index(op.f('ix_agent_runtime_events_stream'), 'agent_runtime_events', ['stream'], unique=False)
    op.create_index(op.f('ix_agent_runtime_events_ts'), 'agent_runtime_events', ['ts'], unique=False)
    op.create_index(op.f('ix_agent_runtime_events_created_at'), 'agent_runtime_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_runtime_events_created_at'), table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_ts'), table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_stream'), table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_seq'), table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_session_key'), table_name='agent_runtime_events')
    op.drop_index('ix_agent_runtime_events_run_session_seq', table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_run_id'), table_name='agent_runtime_events')
    op.drop_index(op.f('ix_agent_runtime_events_id'), table_name='agent_runtime_events')
    op.drop_table('agent_runtime_events')

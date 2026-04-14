"""Create governance_runs table for position monitoring

Revision ID: 0012_governance_runs
Revises: 0011_governance_position_link
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_governance_runs'
down_revision = '0011_governance_position_link'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'governance_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('position_ticket', sa.String(64), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('origin_run_id', sa.Integer(), sa.ForeignKey('analysis_runs.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('action', sa.String(20), nullable=True),
        sa.Column('new_sl', sa.Float(), nullable=True),
        sa.Column('new_tp', sa.Float(), nullable=True),
        sa.Column('conviction', sa.Float(), nullable=True),
        sa.Column('urgency', sa.String(10), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('trace', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('approval_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_error', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_governance_runs_position_ticket', 'governance_runs', ['position_ticket'])
    op.create_index('ix_governance_runs_symbol', 'governance_runs', ['symbol'])
    op.create_index('ix_governance_runs_origin_run_id', 'governance_runs', ['origin_run_id'])
    op.create_index('ix_governance_runs_created_at', 'governance_runs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_governance_runs_created_at', table_name='governance_runs')
    op.drop_index('ix_governance_runs_origin_run_id', table_name='governance_runs')
    op.drop_index('ix_governance_runs_symbol', table_name='governance_runs')
    op.drop_index('ix_governance_runs_position_ticket', table_name='governance_runs')
    op.drop_table('governance_runs')

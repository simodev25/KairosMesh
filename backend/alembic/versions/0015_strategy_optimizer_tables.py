"""Add strategy optimizer tables (campaigns + evaluations)

Revision ID: 0015_strategy_optimizer_tables
Revises: 0014_agent_skills_table
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0015_strategy_optimizer_tables'
down_revision = '0014_agent_skills_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'strategy_optimizer_campaigns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_id', sa.Integer(), sa.ForeignKey('strategies.id'), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('initial_params', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('initial_score', sa.Float(), nullable=True),
        sa.Column('best_params', sa.JSON(), nullable=True),
        sa.Column('best_score', sa.Float(), nullable=True),
        sa.Column('best_metrics', sa.JSON(), nullable=True),
        sa.Column('current_iteration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_strategy_optimizer_campaigns_id'), 'strategy_optimizer_campaigns', ['id'], unique=False)
    op.create_index(
        'ix_strategy_optimizer_campaigns_strategy_id',
        'strategy_optimizer_campaigns',
        ['strategy_id'],
        unique=False,
    )
    op.create_index(
        'ix_strategy_optimizer_campaigns_strategy_status',
        'strategy_optimizer_campaigns',
        ['strategy_id', 'status'],
        unique=False,
    )

    op.create_table(
        'strategy_optimizer_evaluations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('strategy_optimizer_campaigns.id'), nullable=False),
        sa.Column('iteration', sa.Integer(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index(op.f('ix_strategy_optimizer_evaluations_id'), 'strategy_optimizer_evaluations', ['id'], unique=False)
    op.create_index(
        'ix_strategy_optimizer_evaluations_campaign_id',
        'strategy_optimizer_evaluations',
        ['campaign_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_strategy_optimizer_evaluations_campaign_id', table_name='strategy_optimizer_evaluations')
    op.drop_index(op.f('ix_strategy_optimizer_evaluations_id'), table_name='strategy_optimizer_evaluations')
    op.drop_table('strategy_optimizer_evaluations')

    op.drop_index('ix_strategy_optimizer_campaigns_strategy_status', table_name='strategy_optimizer_campaigns')
    op.drop_index('ix_strategy_optimizer_campaigns_strategy_id', table_name='strategy_optimizer_campaigns')
    op.drop_index(op.f('ix_strategy_optimizer_campaigns_id'), table_name='strategy_optimizer_campaigns')
    op.drop_table('strategy_optimizer_campaigns')

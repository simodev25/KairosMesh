"""Add governance fields to analysis_runs and create governance_settings table

Revision ID: 0011_governance
Revises: 0010_trading_config_versions
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_governance'
down_revision = '0010_trading_config_versions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add governance columns to analysis_runs
    op.add_column('analysis_runs', sa.Column(
        'run_type', sa.String(20), nullable=False, server_default='analysis'
    ))
    op.add_column('analysis_runs', sa.Column(
        'governance_position_id', sa.String(50), nullable=True
    ))

    # Create governance_settings table (singleton row, id=1)
    op.create_table(
        'governance_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('execution_mode', sa.String(20), nullable=False, server_default='confirmation'),
        sa.Column('analysis_depth', sa.String(10), nullable=False, server_default='light'),
        sa.Column('interval_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('governance_settings')
    op.drop_column('analysis_runs', 'governance_position_id')
    op.drop_column('analysis_runs', 'run_type')

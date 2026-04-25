"""Add metaapi_position_id to execution_orders for governance position linkage

Revision ID: 0011_governance_position_link
Revises: 0010_trading_config_versions
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_governance_position_link'
down_revision = '0010_trading_config_versions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'execution_orders',
        sa.Column('metaapi_position_id', sa.String(64), nullable=True),
    )
    op.create_index(
        'ix_execution_orders_metaapi_position_id',
        'execution_orders',
        ['metaapi_position_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_execution_orders_metaapi_position_id', table_name='execution_orders')
    op.drop_column('execution_orders', 'metaapi_position_id')

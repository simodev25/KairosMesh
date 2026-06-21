"""Reconcile llm_call_logs.analysis_run_id for legacy schemas

Revision ID: 0014_gh26_llm_logs_fk
Revises: 0013_gh24_benchmark_tables
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = '0014_gh26_llm_logs_fk'
down_revision = '0013_gh24_benchmark_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column['name'] for column in inspector.get_columns('llm_call_logs')}
    if 'analysis_run_id' not in columns:
        op.add_column('llm_call_logs', sa.Column('analysis_run_id', sa.Integer(), nullable=True))

    foreign_keys = {fk.get('name') for fk in inspector.get_foreign_keys('llm_call_logs')}
    if 'fk_llm_call_logs_analysis_run_id' not in foreign_keys:
        op.create_foreign_key(
            'fk_llm_call_logs_analysis_run_id',
            'llm_call_logs',
            'analysis_runs',
            ['analysis_run_id'],
            ['id'],
        )

    indexes = {index.get('name') for index in inspector.get_indexes('llm_call_logs')}
    if 'ix_llm_call_logs_analysis_run_id' not in indexes:
        op.create_index('ix_llm_call_logs_analysis_run_id', 'llm_call_logs', ['analysis_run_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {index.get('name') for index in inspector.get_indexes('llm_call_logs')}
    if 'ix_llm_call_logs_analysis_run_id' in indexes:
        op.drop_index('ix_llm_call_logs_analysis_run_id', table_name='llm_call_logs')

    foreign_keys = {fk.get('name') for fk in inspector.get_foreign_keys('llm_call_logs')}
    if 'fk_llm_call_logs_analysis_run_id' in foreign_keys:
        op.drop_constraint('fk_llm_call_logs_analysis_run_id', 'llm_call_logs', type_='foreignkey')

    columns = {column['name'] for column in inspector.get_columns('llm_call_logs')}
    if 'analysis_run_id' in columns:
        op.drop_column('llm_call_logs', 'analysis_run_id')

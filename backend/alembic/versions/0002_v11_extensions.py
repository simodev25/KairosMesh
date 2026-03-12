"""v1.1 extensions: prompts, memory, backtests, metaapi accounts, llm logs

Revision ID: 0002_v11_extensions
Revises: 0001_initial
Create Date: 2026-03-12
"""

import os

from alembic import op
import sqlalchemy as sa

revision = '0002_v11_extensions'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'
    enable_pgvector = os.getenv('ENABLE_PGVECTOR', 'false').lower() in {'1', 'true', 'yes', 'on'}

    if is_postgres and enable_pgvector:
        available = bind.execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"),
        ).scalar()
        if available:
            op.execute('CREATE EXTENSION IF NOT EXISTS vector')
            from pgvector.sqlalchemy import Vector

            embedding_type = Vector(64)
        else:
            embedding_type = sa.JSON()
    else:
        embedding_type = sa.JSON()

    op.create_table(
        'metaapi_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('account_id', sa.String(length=120), nullable=False),
        sa.Column('region', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_metaapi_accounts_id'), 'metaapi_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_metaapi_accounts_account_id'), 'metaapi_accounts', ['account_id'], unique=True)

    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('user_prompt_template', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('agent_name', 'version', name='uq_prompt_agent_version'),
    )
    op.create_index(op.f('ix_prompt_templates_id'), 'prompt_templates', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_templates_agent_name'), 'prompt_templates', ['agent_name'], unique=False)

    op.create_table(
        'memory_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pair', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('embedding', embedding_type, nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('analysis_runs.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_memory_entries_id'), 'memory_entries', ['id'], unique=False)
    op.create_index(op.f('ix_memory_entries_pair'), 'memory_entries', ['pair'], unique=False)
    op.create_index(op.f('ix_memory_entries_timeframe'), 'memory_entries', ['timeframe'], unique=False)

    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pair', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('strategy', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('equity_curve', sa.JSON(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_backtest_runs_id'), 'backtest_runs', ['id'], unique=False)
    op.create_index(op.f('ix_backtest_runs_pair'), 'backtest_runs', ['pair'], unique=False)

    op.create_table(
        'backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('backtest_runs.id'), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('entry_time', sa.DateTime(), nullable=False),
        sa.Column('exit_time', sa.DateTime(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('pnl_pct', sa.Float(), nullable=False),
        sa.Column('outcome', sa.String(length=12), nullable=False),
    )
    op.create_index(op.f('ix_backtest_trades_id'), 'backtest_trades', ['id'], unique=False)
    op.create_index(op.f('ix_backtest_trades_run_id'), 'backtest_trades', ['run_id'], unique=False)

    op.create_table(
        'llm_call_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_llm_call_logs_id'), 'llm_call_logs', ['id'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_provider'), 'llm_call_logs', ['provider'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_call_logs_provider'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_id'), table_name='llm_call_logs')
    op.drop_table('llm_call_logs')

    op.drop_index(op.f('ix_backtest_trades_run_id'), table_name='backtest_trades')
    op.drop_index(op.f('ix_backtest_trades_id'), table_name='backtest_trades')
    op.drop_table('backtest_trades')

    op.drop_index(op.f('ix_backtest_runs_pair'), table_name='backtest_runs')
    op.drop_index(op.f('ix_backtest_runs_id'), table_name='backtest_runs')
    op.drop_table('backtest_runs')

    op.drop_index(op.f('ix_memory_entries_timeframe'), table_name='memory_entries')
    op.drop_index(op.f('ix_memory_entries_pair'), table_name='memory_entries')
    op.drop_index(op.f('ix_memory_entries_id'), table_name='memory_entries')
    op.drop_table('memory_entries')

    op.drop_index(op.f('ix_prompt_templates_agent_name'), table_name='prompt_templates')
    op.drop_index(op.f('ix_prompt_templates_id'), table_name='prompt_templates')
    op.drop_table('prompt_templates')

    op.drop_index(op.f('ix_metaapi_accounts_account_id'), table_name='metaapi_accounts')
    op.drop_index(op.f('ix_metaapi_accounts_id'), table_name='metaapi_accounts')
    op.drop_table('metaapi_accounts')

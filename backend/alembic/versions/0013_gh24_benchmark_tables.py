"""Add benchmark subsystem tables for GH-24

Revision ID: 0013_gh24_benchmark_tables
Revises: 0012_governance_runs
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = '0013_gh24_benchmark_tables'
down_revision = '0012_governance_runs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'benchmark_fixtures',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('agent_name', sa.String(length=80), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('default_scoring_weights', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_benchmark_fixtures_agent_name', 'benchmark_fixtures', ['agent_name'])
    op.create_index('ix_benchmark_fixtures_hash', 'benchmark_fixtures', ['hash'])
    op.create_index('ix_benchmark_fixtures_id', 'benchmark_fixtures', ['id'])
    op.create_index('ix_benchmark_fixtures_name', 'benchmark_fixtures', ['name'])

    op.create_table(
        'benchmark_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('benchmark_fixtures.id'), nullable=False),
        sa.Column('fixture_hash', sa.String(length=64), nullable=False),
        sa.Column('model_spec', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('scenario_type', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('repetitions', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_llm_calls', sa.Integer(), nullable=True),
        sa.Column('effective_scoring_weights', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('celery_task_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_benchmark_runs_fixture_id', 'benchmark_runs', ['fixture_id'])
    op.create_index('ix_benchmark_runs_id', 'benchmark_runs', ['id'])
    op.create_index('ix_benchmark_runs_status', 'benchmark_runs', ['status'])

    op.create_table(
        'benchmark_cases',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('benchmark_runs.id'), nullable=False),
        sa.Column('agent_name', sa.String(length=80), nullable=False),
        sa.Column('case_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('aggregate_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_benchmark_cases_id', 'benchmark_cases', ['id'])
    op.create_index('ix_benchmark_cases_run_id', 'benchmark_cases', ['run_id'])

    op.create_table(
        'benchmark_attempts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('benchmark_cases.id'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('raw_output', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('schema_validity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completeness_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tool_policy_compliance_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reference_consistency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('stability_score', sa.Float(), nullable=True),
        sa.Column('aggregate_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('llm_calls_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analysis_run_id', sa.Integer(), sa.ForeignKey('analysis_runs.id'), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_benchmark_attempts_analysis_run_id', 'benchmark_attempts', ['analysis_run_id'])
    op.create_index('ix_benchmark_attempts_case_id', 'benchmark_attempts', ['case_id'])
    op.create_index('ix_benchmark_attempts_id', 'benchmark_attempts', ['id'])

    op.add_column('llm_call_logs', sa.Column('analysis_run_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_llm_call_logs_analysis_run_id',
        'llm_call_logs',
        'analysis_runs',
        ['analysis_run_id'],
        ['id'],
    )
    op.create_index('ix_llm_call_logs_analysis_run_id', 'llm_call_logs', ['analysis_run_id'])


def downgrade() -> None:
    op.drop_index('ix_llm_call_logs_analysis_run_id', table_name='llm_call_logs')
    op.drop_constraint('fk_llm_call_logs_analysis_run_id', 'llm_call_logs', type_='foreignkey')
    op.drop_column('llm_call_logs', 'analysis_run_id')

    op.drop_index('ix_benchmark_attempts_id', table_name='benchmark_attempts')
    op.drop_index('ix_benchmark_attempts_case_id', table_name='benchmark_attempts')
    op.drop_index('ix_benchmark_attempts_analysis_run_id', table_name='benchmark_attempts')
    op.drop_table('benchmark_attempts')

    op.drop_index('ix_benchmark_cases_run_id', table_name='benchmark_cases')
    op.drop_index('ix_benchmark_cases_id', table_name='benchmark_cases')
    op.drop_table('benchmark_cases')

    op.drop_index('ix_benchmark_runs_status', table_name='benchmark_runs')
    op.drop_index('ix_benchmark_runs_id', table_name='benchmark_runs')
    op.drop_index('ix_benchmark_runs_fixture_id', table_name='benchmark_runs')
    op.drop_table('benchmark_runs')

    op.drop_index('ix_benchmark_fixtures_name', table_name='benchmark_fixtures')
    op.drop_index('ix_benchmark_fixtures_id', table_name='benchmark_fixtures')
    op.drop_index('ix_benchmark_fixtures_hash', table_name='benchmark_fixtures')
    op.drop_index('ix_benchmark_fixtures_agent_name', table_name='benchmark_fixtures')
    op.drop_table('benchmark_fixtures')

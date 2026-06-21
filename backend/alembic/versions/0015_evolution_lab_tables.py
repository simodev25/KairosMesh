"""Add evolution lab tables for GH-28

Revision ID: 0015_evolution_lab_tables
Revises: 0014_agent_skills_table
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa


revision = '0015_evolution_lab_tables'
down_revision = '0014_agent_skills_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'evolution_campaigns',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('agent_name', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('model_parameters', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('baseline_prompt_template_id', sa.Integer(), sa.ForeignKey('prompt_templates.id'), nullable=False),
        sa.Column('baseline_skill_id', sa.Integer(), sa.ForeignKey('agent_skills.id'), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False, server_default='pending'),
        sa.Column('max_iterations', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('max_candidates', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('max_llm_calls', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('budget_usd_limit', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('evaluation_config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('best_candidate_id', sa.Integer(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=128), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('consumed_budget_usd', sa.Numeric(12, 6), nullable=False, server_default='0'),
        sa.Column('llm_calls_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consumed_iterations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consumed_candidates', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_evolution_campaigns_id', 'evolution_campaigns', ['id'])
    op.create_index('ix_evolution_campaigns_agent_name', 'evolution_campaigns', ['agent_name', 'status'])
    op.create_index('ix_evolution_campaigns_created_at', 'evolution_campaigns', ['created_at'])

    op.create_table(
        'evolution_candidates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('evolution_campaigns.id'), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_candidate_id', sa.Integer(), sa.ForeignKey('evolution_candidates.id'), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('user_prompt_template', sa.Text(), nullable=False),
        sa.Column('skills', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('fitness_score', sa.Float(), nullable=True),
        sa.Column('metrics_summary', sa.JSON(), nullable=True),
        sa.Column('llm_cost_usd', sa.Numeric(12, 6), nullable=False, server_default='0'),
        sa.Column('llm_calls_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=24), nullable=False, server_default='generated'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_evolution_candidates_id', 'evolution_candidates', ['id'])
    op.create_index('ix_evolution_candidates_campaign_generation', 'evolution_candidates', ['campaign_id', 'generation'])
    op.create_index('ix_evolution_candidates_campaign_fitness', 'evolution_candidates', ['campaign_id', 'fitness_score'])

    op.create_foreign_key(
        'fk_evolution_campaigns_best_candidate_id',
        'evolution_campaigns',
        'evolution_candidates',
        ['best_candidate_id'],
        ['id'],
    )

    op.create_table(
        'evolution_candidate_evaluations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('evolution_candidates.id'), nullable=False),
        sa.Column('evaluation_type', sa.String(length=32), nullable=False),
        sa.Column('benchmark_run_id', sa.Integer(), sa.ForeignKey('benchmark_runs.id'), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('aggregate_score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_evolution_candidate_evaluations_id', 'evolution_candidate_evaluations', ['id'])
    op.create_index(
        'ix_evolution_candidate_evaluations_candidate_created_at',
        'evolution_candidate_evaluations',
        ['candidate_id', 'created_at'],
    )

    op.create_table(
        'evolution_promotions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('evolution_campaigns.id'), nullable=False),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('evolution_candidates.id'), nullable=False),
        sa.Column('prompt_template_id', sa.Integer(), sa.ForeignKey('prompt_templates.id'), nullable=True),
        sa.Column('agent_skill_id', sa.Integer(), sa.ForeignKey('agent_skills.id'), nullable=True),
        sa.Column('promoted_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            '(prompt_template_id IS NOT NULL) OR (agent_skill_id IS NOT NULL)',
            name='ck_evolution_promotions_target_not_null',
        ),
    )
    op.create_index('ix_evolution_promotions_id', 'evolution_promotions', ['id'])
    op.create_index('ix_evolution_promotions_campaign_candidate', 'evolution_promotions', ['campaign_id', 'candidate_id'])


def downgrade() -> None:
    op.drop_index('ix_evolution_promotions_campaign_candidate', table_name='evolution_promotions')
    op.drop_index('ix_evolution_promotions_id', table_name='evolution_promotions')
    op.drop_table('evolution_promotions')

    op.drop_index('ix_evolution_candidate_evaluations_candidate_created_at', table_name='evolution_candidate_evaluations')
    op.drop_index('ix_evolution_candidate_evaluations_id', table_name='evolution_candidate_evaluations')
    op.drop_table('evolution_candidate_evaluations')

    op.drop_constraint('fk_evolution_campaigns_best_candidate_id', 'evolution_campaigns', type_='foreignkey')
    op.drop_index('ix_evolution_candidates_campaign_fitness', table_name='evolution_candidates')
    op.drop_index('ix_evolution_candidates_campaign_generation', table_name='evolution_candidates')
    op.drop_index('ix_evolution_candidates_id', table_name='evolution_candidates')
    op.drop_table('evolution_candidates')

    op.drop_index('ix_evolution_campaigns_created_at', table_name='evolution_campaigns')
    op.drop_index('ix_evolution_campaigns_agent_name', table_name='evolution_campaigns')
    op.drop_index('ix_evolution_campaigns_id', table_name='evolution_campaigns')
    op.drop_table('evolution_campaigns')

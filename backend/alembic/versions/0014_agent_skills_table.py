"""Add agent_skills table and migrate legacy settings data

Revision ID: 0014_agent_skills_table
Revises: 0013_gh24_benchmark_tables
Create Date: 2026-06-21
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = '0014_agent_skills_table'
down_revision = '0013_gh24_benchmark_tables'
branch_labels = None
depends_on = None


def _normalize_skills(raw_value: object) -> list[str]:
    raw_items: list[str]
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        if text.startswith('['):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    raw_items = [str(item).strip() for item in parsed]
                else:
                    raw_items = [text]
            except json.JSONDecodeError:
                raw_items = [part.strip() for part in text.splitlines()]
        elif '\n' in text:
            raw_items = [part.strip() for part in text.splitlines()]
        elif '||' in text:
            raw_items = [part.strip() for part in text.split('||')]
        elif ';' in text:
            raw_items = [part.strip() for part in text.split(';')]
        else:
            raw_items = [text]
    elif isinstance(raw_value, (list, tuple, set)):
        raw_items = [str(item).strip() for item in raw_value]
    else:
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        cleaned = item.strip()
        if not cleaned:
            continue
        if len(cleaned) > 500:
            cleaned = cleaned[:500].rstrip()
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
        if len(deduped) >= 12:
            break
    return deduped


def upgrade() -> None:
    op.create_table(
        'agent_skills',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('skills', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('agent_name', 'version', name='uq_agent_skills_agent_version'),
    )
    op.create_index(op.f('ix_agent_skills_id'), 'agent_skills', ['id'], unique=False)
    op.create_index(op.f('ix_agent_skills_agent_name'), 'agent_skills', ['agent_name'], unique=False)
    op.create_index('ix_agent_skills_agent_name_is_active', 'agent_skills', ['agent_name', 'is_active'], unique=False)

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT settings FROM connector_configs WHERE connector_name = 'ollama' LIMIT 1"))
    row = rows.fetchone()
    settings = dict(row[0]) if row is not None and isinstance(row[0], dict) else {}
    raw_map = settings.get('agent_skills', {}) if isinstance(settings, dict) else {}

    if isinstance(raw_map, dict):
        for agent_name, raw_value in raw_map.items():
            normalized_name = str(agent_name or '').strip()
            if not normalized_name:
                continue
            skills = _normalize_skills(raw_value)
            if not skills:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO agent_skills (
                        agent_name, version, is_active, skills, notes, created_by_id, created_at, updated_at
                    ) VALUES (
                        :agent_name, 1, true, :skills, 'Migrated from connector_configs', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    'agent_name': normalized_name,
                    'skills': json.dumps(skills),
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT agent_name, skills FROM agent_skills WHERE is_active = true'))
    active_rows = rows.fetchall()
    restored_map: dict[str, list[str]] = {}
    for agent_name, raw_skills in active_rows:
        key = str(agent_name or '').strip()
        if not key:
            continue
        if isinstance(raw_skills, list):
            restored_map[key] = [str(item).strip() for item in raw_skills if str(item).strip()]
        else:
            restored_map[key] = _normalize_skills(raw_skills)

    if restored_map:
        row = bind.execute(sa.text("SELECT id, settings FROM connector_configs WHERE connector_name = 'ollama' LIMIT 1")).fetchone()
        if row is not None:
            connector_id, current_settings = row
            settings = dict(current_settings) if isinstance(current_settings, dict) else {}
            settings['agent_skills'] = restored_map
            bind.execute(
                sa.text('UPDATE connector_configs SET settings = :settings WHERE id = :connector_id'),
                {'settings': json.dumps(settings), 'connector_id': connector_id},
            )

    op.drop_index('ix_agent_skills_agent_name_is_active', table_name='agent_skills')
    op.drop_index(op.f('ix_agent_skills_agent_name'), table_name='agent_skills')
    op.drop_index(op.f('ix_agent_skills_id'), table_name='agent_skills')
    op.drop_table('agent_skills')

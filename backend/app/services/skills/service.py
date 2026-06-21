from __future__ import annotations

from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.agent_skill import AgentSkill
from app.schemas.agent_skill import MAX_AGENT_SKILL_LENGTH, MAX_AGENT_SKILLS_PER_AGENT


class AgentSkillsService:
    def _normalize_skills(self, skills: list[str], *, strict_limit: bool = True) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in skills:
            cleaned = str(item or '').strip()
            if not cleaned:
                continue
            if len(cleaned) > MAX_AGENT_SKILL_LENGTH:
                raise ValueError(f'each skill must be <= {MAX_AGENT_SKILL_LENGTH} chars')
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
            if len(normalized) > MAX_AGENT_SKILLS_PER_AGENT:
                if strict_limit:
                    raise ValueError(f'max {MAX_AGENT_SKILLS_PER_AGENT} skills allowed')
                normalized = normalized[:MAX_AGENT_SKILLS_PER_AGENT]
                break
        if not normalized:
            raise ValueError('at least one skill is required')
        return normalized

    def get_active(self, db: Session, agent_name: str) -> AgentSkill | None:
        return (
            db.query(AgentSkill)
            .filter(AgentSkill.agent_name == agent_name, AgentSkill.is_active.is_(True))
            .order_by(AgentSkill.version.desc())
            .first()
        )

    def list_versions(self, db: Session, agent_name: str, active_only: bool = False) -> list[AgentSkill]:
        query = db.query(AgentSkill).filter(AgentSkill.agent_name == agent_name)
        if active_only:
            query = query.filter(AgentSkill.is_active.is_(True))
        return query.order_by(AgentSkill.version.desc()).all()

    def create_version(
        self,
        db: Session,
        agent_name: str,
        skills: list[str],
        notes: str | None,
        created_by_id: int | None,
        activate: bool = False,
    ) -> AgentSkill:
        validated_skills = self._normalize_skills(skills)
        max_version = (
            db.query(func.max(AgentSkill.version))
            .filter(AgentSkill.agent_name == agent_name)
            .scalar()
        )
        next_version = (max_version or 0) + 1

        row = AgentSkill(
            agent_name=agent_name,
            version=next_version,
            is_active=False,
            skills=validated_skills,
            notes=notes,
            created_by_id=created_by_id,
        )
        db.add(row)
        db.flush()

        if activate:
            db.query(AgentSkill).filter(
                AgentSkill.agent_name == agent_name,
                AgentSkill.id != row.id,
                AgentSkill.is_active.is_(True),
            ).update({'is_active': False})
            row.is_active = True

        db.commit()
        db.refresh(row)
        return row

    def activate(self, db: Session, skill_id: int) -> AgentSkill | None:
        row = db.get(AgentSkill, skill_id)
        if not row:
            return None
        db.query(AgentSkill).filter(
            AgentSkill.agent_name == row.agent_name,
            AgentSkill.is_active.is_(True),
            AgentSkill.id != row.id,
        ).update({'is_active': False})
        row.is_active = True
        db.commit()
        db.refresh(row)
        return row

    def seed_defaults(self, db: Session) -> dict[str, int]:
        skills_root = Path(__file__).resolve().parents[3] / 'config' / 'skills'
        created = 0
        skipped = 0
        if not skills_root.exists():
            return {'created': 0, 'skipped': 0}

        for skill_file in skills_root.glob('*/SKILL.md'):
            agent_name = skill_file.parent.name
            exists = db.query(AgentSkill).filter(AgentSkill.agent_name == agent_name).first()
            if exists:
                skipped += 1
                continue

            raw = skill_file.read_text(encoding='utf-8')
            lines = []
            for line in raw.splitlines():
                cleaned = line.strip()
                if not cleaned:
                    continue
                if cleaned.startswith('---'):
                    continue
                if cleaned.startswith('name:') or cleaned.startswith('description:'):
                    continue
                if cleaned.startswith('# '):
                    continue
                if cleaned[0].isdigit() and '. ' in cleaned[:5]:
                    cleaned = cleaned.split('. ', 1)[1].strip()
                lines.append(cleaned)

            if not lines:
                skipped += 1
                continue

            db.add(
                AgentSkill(
                    agent_name=agent_name,
                    version=1,
                    is_active=True,
                    skills=self._normalize_skills(lines, strict_limit=False),
                    notes='seed default',
                    created_by_id=None,
                )
            )
            created += 1

        db.commit()
        return {'created': created, 'skipped': skipped}

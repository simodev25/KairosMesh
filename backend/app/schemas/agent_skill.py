from datetime import datetime

from pydantic import BaseModel, Field, field_validator


MAX_AGENT_SKILLS_PER_AGENT = 12
MAX_AGENT_SKILL_LENGTH = 500


class AgentSkillCreateRequest(BaseModel):
    skills: list[str] = Field(min_length=1, max_length=MAX_AGENT_SKILLS_PER_AGENT)
    notes: str | None = None
    activate: bool = False

    @field_validator('skills')
    @classmethod
    def validate_skills(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
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
                raise ValueError(f'max {MAX_AGENT_SKILLS_PER_AGENT} skills allowed')
        if not normalized:
            raise ValueError('at least one non-empty skill is required')
        return normalized


class AgentSkillOut(BaseModel):
    id: int
    agent_name: str
    version: int
    is_active: bool
    skills: list[str]
    notes: str | None
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class AgentSkillListOut(BaseModel):
    items: list[AgentSkillOut]

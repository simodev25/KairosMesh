from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import Role, require_roles
from app.db.models.agent_skill import AgentSkill
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.agent_skill import AgentSkillCreateRequest, AgentSkillOut
from app.services.skills.service import AgentSkillsService

router = APIRouter(prefix='/agents', tags=['agent-skills'])


@router.get('/{agent_name}/skills', response_model=list[AgentSkillOut])
def list_agent_skills(
    agent_name: str,
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST, Role.TRADER_OPERATOR)),
) -> list[AgentSkillOut]:
    service = AgentSkillsService()
    rows = service.list_versions(db, agent_name=agent_name, active_only=active_only)
    return [AgentSkillOut.model_validate(row) for row in rows]


@router.post('/{agent_name}/skills', response_model=AgentSkillOut, status_code=201)
def create_agent_skill_version(
    agent_name: str,
    payload: AgentSkillCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> AgentSkillOut:
    service = AgentSkillsService()
    try:
        row = service.create_version(
            db=db,
            agent_name=agent_name,
            skills=payload.skills,
            notes=payload.notes,
            created_by_id=user.id,
            activate=payload.activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return AgentSkillOut.model_validate(row)


@router.post('/{agent_name}/skills/{skill_id}/activate', response_model=AgentSkillOut)
def activate_agent_skill_version(
    agent_name: str,
    skill_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> AgentSkillOut:
    service = AgentSkillsService()
    row = service.activate(db, skill_id)
    if row is None or row.agent_name != agent_name:
        raise HTTPException(status_code=404, detail='Agent skill version not found')
    return AgentSkillOut.model_validate(row)


@router.get('/catalog')
def list_agents_catalog(
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST, Role.TRADER_OPERATOR)),
) -> list[dict]:
    active_rows = (
        db.query(AgentSkill)
        .filter(AgentSkill.is_active.is_(True))
        .order_by(AgentSkill.agent_name.asc())
        .all()
    )
    return [
        {
            'agent_name': row.agent_name,
            'active_version': row.version,
            'skills_count': len(row.skills or []),
        }
        for row in active_rows
    ]

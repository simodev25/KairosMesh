from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import Role, require_roles
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.prompt import PromptTemplateCreate, PromptTemplateOut
from app.services.prompts.registry import PromptTemplateService

router = APIRouter(prefix='/prompts', tags=['prompts'])


@router.get('', response_model=list[PromptTemplateOut])
def list_prompts(
    agent_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST, Role.TRADER_OPERATOR)),
) -> list[PromptTemplateOut]:
    query = db.query(PromptTemplate)
    if agent_name:
        query = query.filter(PromptTemplate.agent_name == agent_name)
    prompts = query.order_by(PromptTemplate.agent_name.asc(), PromptTemplate.version.desc()).all()
    return [PromptTemplateOut.model_validate(prompt) for prompt in prompts]


@router.post('', response_model=PromptTemplateOut)
def create_prompt(
    payload: PromptTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> PromptTemplateOut:
    service = PromptTemplateService()
    prompt = service.create_version(
        db=db,
        agent_name=payload.agent_name,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        notes=payload.notes,
        created_by_id=user.id,
    )
    return PromptTemplateOut.model_validate(prompt)


@router.post('/{prompt_id}/activate', response_model=PromptTemplateOut)
def activate_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> PromptTemplateOut:
    service = PromptTemplateService()
    prompt = service.activate(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail='Prompt not found')
    return PromptTemplateOut.model_validate(prompt)

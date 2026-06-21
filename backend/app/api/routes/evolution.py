from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Role, require_roles
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evolution_campaign import (
    EvolutionCampaignCancelResponse,
    EvolutionCampaignCreateRequest,
    EvolutionCampaignListResponse,
    EvolutionCampaignOut,
)
from app.schemas.evolution_candidate import (
    EvolutionCandidateListResponse,
    EvolutionFitnessPoint,
    EvolutionFitnessSeriesResponse,
    EvolutionPromoteRequest,
    EvolutionPromoteResponse,
)
from app.services.evolution.service import EvolutionService
from app.tasks.evolution import run_evolution_campaign

router = APIRouter(prefix='/evolution', tags=['evolution'])


@router.post('/campaigns', response_model=EvolutionCampaignOut, status_code=201)
def create_campaign(
    payload: EvolutionCampaignCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> EvolutionCampaignOut:
    service = EvolutionService()
    campaign = service.create_campaign(db, payload.model_dump(), created_by_id=user.id)

    settings = get_settings()
    task = run_evolution_campaign.apply_async(args=[campaign.id], queue=settings.celery_evolution_queue, ignore_result=True)
    campaign.celery_task_id = task.id
    db.commit()
    db.refresh(campaign)
    return EvolutionCampaignOut.model_validate(campaign)


@router.get('/campaigns', response_model=EvolutionCampaignListResponse)
def list_campaigns(
    status: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> EvolutionCampaignListResponse:
    service = EvolutionService()
    items, total = service.list_campaigns(db, status=status, agent_name=agent_name, offset=offset, limit=limit)
    return EvolutionCampaignListResponse(
        items=[EvolutionCampaignOut.model_validate(item) for item in items],
        total=total,
    )


@router.get('/campaigns/{campaign_id}', response_model=EvolutionCampaignOut)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> EvolutionCampaignOut:
    campaign = EvolutionService().get_campaign(db, campaign_id)
    return EvolutionCampaignOut.model_validate(campaign)


@router.post('/campaigns/{campaign_id}/cancel', response_model=EvolutionCampaignCancelResponse, status_code=202)
def cancel_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> EvolutionCampaignCancelResponse:
    campaign = EvolutionService().request_cancel(db, campaign_id)
    return EvolutionCampaignCancelResponse(id=campaign.id, status=campaign.status)


@router.get('/campaigns/{campaign_id}/candidates', response_model=EvolutionCandidateListResponse)
def list_candidates(
    campaign_id: int,
    sort: str = Query(default='generation'),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> EvolutionCandidateListResponse:
    if sort not in {'generation', 'fitness'}:
        raise HTTPException(status_code=400, detail='sort must be one of: generation, fitness')
    items = EvolutionService().list_candidates(db, campaign_id, sort=sort)
    from app.schemas.evolution_candidate import EvolutionCandidateOut

    return EvolutionCandidateListResponse(items=[EvolutionCandidateOut.model_validate(item) for item in items])


@router.get('/campaigns/{campaign_id}/fitness-series', response_model=EvolutionFitnessSeriesResponse)
def get_fitness_series(
    campaign_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> EvolutionFitnessSeriesResponse:
    points = EvolutionService().fitness_series(db, campaign_id)
    return EvolutionFitnessSeriesResponse(points=[EvolutionFitnessPoint(**point) for point in points])


@router.post('/candidates/{candidate_id}/promote', response_model=EvolutionPromoteResponse, status_code=201)
def promote_candidate(
    candidate_id: int,
    payload: EvolutionPromoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> EvolutionPromoteResponse:
    promotion = EvolutionService().promote_candidate(
        db,
        candidate_id,
        promote_prompt=payload.promote_prompt,
        promote_skills=payload.promote_skills,
        promoted_by_id=user.id,
    )
    return EvolutionPromoteResponse(
        promotion_id=promotion.id,
        prompt_template_id=promotion.prompt_template_id,
        agent_skill_id=promotion.agent_skill_id,
        created_at=promotion.created_at,
    )

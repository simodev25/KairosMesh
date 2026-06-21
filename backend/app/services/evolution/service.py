from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.agent_skill import AgentSkill
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.db.models.evolution_candidate_evaluation import EvolutionCandidateEvaluation
from app.db.models.evolution_promotion import EvolutionPromotion
from app.db.models.prompt_template import PromptTemplate
from app.services.prompts.registry import PromptTemplateService
from app.services.skills.service import AgentSkillsService

CAMPAIGN_STATUS_PENDING = 'pending'
CAMPAIGN_STATUS_RUNNING = 'running'
CAMPAIGN_STATUS_COMPLETED = 'completed'
CAMPAIGN_STATUS_CANCELLED = 'cancelled'
CAMPAIGN_STATUS_FAILED = 'failed'

CAMPAIGN_MUTABLE_STATUS = {CAMPAIGN_STATUS_PENDING}
CAMPAIGN_TERMINAL_STATUS = {CAMPAIGN_STATUS_COMPLETED, CAMPAIGN_STATUS_CANCELLED, CAMPAIGN_STATUS_FAILED}
VALID_AGENT_NAMES = {
    'technical-analyst',
    'news-analyst',
    'market-context-analyst',
    'bullish-researcher',
    'bearish-researcher',
    'trader-agent',
    'risk-manager',
    'execution-manager',
    'governance-trader',
}


class EvolutionService:
    def __init__(self) -> None:
        self.prompt_service = PromptTemplateService()
        self.skill_service = AgentSkillsService()

    @staticmethod
    def _validate_bounds(*, max_iterations: int, max_candidates: int, max_llm_calls: int, budget_usd_limit: float) -> None:
        if max_iterations <= 0:
            raise HTTPException(status_code=400, detail='max_iterations must be > 0')
        if max_candidates <= 0:
            raise HTTPException(status_code=400, detail='max_candidates must be > 0')
        if max_llm_calls <= 0:
            raise HTTPException(status_code=400, detail='max_llm_calls must be > 0')
        if budget_usd_limit < 0:
            raise HTTPException(status_code=400, detail='budget_usd_limit must be >= 0')

    @staticmethod
    def _get_campaign_or_404(db: Session, campaign_id: int) -> EvolutionCampaign:
        campaign = db.get(EvolutionCampaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail='Campaign not found')
        return campaign

    @staticmethod
    def _get_candidate_or_404(db: Session, candidate_id: int) -> EvolutionCandidate:
        candidate = db.get(EvolutionCandidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail='Candidate not found')
        return candidate

    def create_campaign(self, db: Session, payload: dict[str, Any], *, created_by_id: int | None) -> EvolutionCampaign:
        agent_name = str(payload.get('agent_name') or '').strip()
        if agent_name not in VALID_AGENT_NAMES:
            raise HTTPException(status_code=422, detail='Unsupported agent_name')

        self._validate_bounds(
            max_iterations=int(payload.get('max_iterations', 0)),
            max_candidates=int(payload.get('max_candidates', 0)),
            max_llm_calls=int(payload.get('max_llm_calls', 0)),
            budget_usd_limit=float(payload.get('budget_usd_limit', 0)),
        )

        baseline_prompt_template_id = int(payload.get('baseline_prompt_template_id'))
        prompt = db.get(PromptTemplate, baseline_prompt_template_id)
        if prompt is None:
            raise HTTPException(status_code=422, detail='Invalid baseline_prompt_template_id')

        baseline_skill_id = payload.get('baseline_skill_id')
        if baseline_skill_id is not None:
            skill = db.get(AgentSkill, int(baseline_skill_id))
            if skill is None:
                raise HTTPException(status_code=422, detail='Invalid baseline_skill_id')

        campaign = EvolutionCampaign(
            name=str(payload.get('name') or '').strip(),
            agent_name=agent_name,
            provider=str(payload.get('provider') or '').strip(),
            model_name=str(payload.get('model_name') or '').strip(),
            model_parameters=dict(payload.get('model_parameters') or {}),
            baseline_prompt_template_id=baseline_prompt_template_id,
            baseline_skill_id=int(baseline_skill_id) if baseline_skill_id is not None else None,
            status=CAMPAIGN_STATUS_PENDING,
            max_iterations=int(payload.get('max_iterations')),
            max_candidates=int(payload.get('max_candidates')),
            max_llm_calls=int(payload.get('max_llm_calls')),
            budget_usd_limit=float(payload.get('budget_usd_limit')),
            evaluation_config=dict(payload.get('evaluation_config') or {}),
            created_by_id=created_by_id,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def list_campaigns(
        self,
        db: Session,
        *,
        status: str | None = None,
        agent_name: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[EvolutionCampaign], int]:
        query = db.query(EvolutionCampaign)
        if status:
            query = query.filter(EvolutionCampaign.status == status)
        if agent_name:
            query = query.filter(EvolutionCampaign.agent_name == agent_name)
        total = query.count()
        rows = query.order_by(EvolutionCampaign.created_at.desc()).offset(offset).limit(limit).all()
        return rows, total

    def get_campaign(self, db: Session, campaign_id: int) -> EvolutionCampaign:
        return self._get_campaign_or_404(db, campaign_id)

    def request_cancel(self, db: Session, campaign_id: int) -> EvolutionCampaign:
        campaign = self._get_campaign_or_404(db, campaign_id)
        if campaign.status in CAMPAIGN_TERMINAL_STATUS:
            return campaign
        if campaign.status == CAMPAIGN_STATUS_PENDING:
            campaign.status = CAMPAIGN_STATUS_CANCELLED
            campaign.completed_at = datetime.now(timezone.utc)
        elif campaign.status == CAMPAIGN_STATUS_RUNNING:
            campaign.status = 'cancel_requested'
        db.commit()
        db.refresh(campaign)
        return campaign

    def list_candidates(self, db: Session, campaign_id: int, *, sort: str = 'generation') -> list[EvolutionCandidate]:
        self._get_campaign_or_404(db, campaign_id)
        query = db.query(EvolutionCandidate).filter(EvolutionCandidate.campaign_id == campaign_id)
        if sort == 'fitness':
            query = query.order_by(EvolutionCandidate.fitness_score.desc().nullslast(), EvolutionCandidate.id.asc())
        else:
            query = query.order_by(EvolutionCandidate.generation.asc(), EvolutionCandidate.id.asc())
        return query.all()

    def fitness_series(self, db: Session, campaign_id: int) -> list[dict[str, float | int]]:
        self._get_campaign_or_404(db, campaign_id)
        rows = (
            db.query(
                EvolutionCandidate.generation,
                func.max(EvolutionCandidateEvaluation.aggregate_score),
                func.avg(EvolutionCandidateEvaluation.aggregate_score),
            )
            .join(EvolutionCandidateEvaluation, EvolutionCandidateEvaluation.candidate_id == EvolutionCandidate.id)
            .filter(EvolutionCandidate.campaign_id == campaign_id)
            .group_by(EvolutionCandidate.generation)
            .order_by(EvolutionCandidate.generation.asc())
            .all()
        )
        return [
            {
                'generation': int(generation),
                'best': float(best or 0.0),
                'avg': float(avg or 0.0),
            }
            for generation, best, avg in rows
        ]

    def promote_candidate(
        self,
        db: Session,
        candidate_id: int,
        *,
        promote_prompt: bool,
        promote_skills: bool,
        promoted_by_id: int,
    ) -> EvolutionPromotion:
        if not promote_prompt and not promote_skills:
            raise HTTPException(status_code=400, detail='At least one promotion target is required')

        candidate = self._get_candidate_or_404(db, candidate_id)
        campaign = self._get_campaign_or_404(db, candidate.campaign_id)
        if candidate.status != 'evaluated':
            raise HTTPException(status_code=409, detail='Candidate must be evaluated before promotion')

        prompt_id: int | None = None
        skill_id: int | None = None

        if promote_prompt:
            prompt = self.prompt_service.create_version(
                db=db,
                agent_name=campaign.agent_name,
                system_prompt=candidate.system_prompt,
                user_prompt_template=candidate.user_prompt_template,
                notes=f'Promotion from evolution campaign {campaign.id} candidate {candidate.id}',
                created_by_id=promoted_by_id,
            )
            prompt_id = int(prompt.id)

        if promote_skills:
            skill = self.skill_service.create_version(
                db=db,
                agent_name=campaign.agent_name,
                skills=list(candidate.skills or []),
                notes=f'Promotion from evolution campaign {campaign.id} candidate {candidate.id}',
                created_by_id=promoted_by_id,
                activate=False,
            )
            skill_id = int(skill.id)

        promotion = EvolutionPromotion(
            campaign_id=campaign.id,
            candidate_id=candidate.id,
            prompt_template_id=prompt_id,
            agent_skill_id=skill_id,
            promoted_by_id=promoted_by_id,
        )
        candidate.status = 'promoted'
        db.add(promotion)
        db.commit()
        db.refresh(promotion)
        return promotion

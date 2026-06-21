from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.services.evolution.evaluator import BenchmarkEvaluator
from app.services.evolution.mutator import PromptMutator


class EvolutionEngine:
    def __init__(self) -> None:
        self.mutator = PromptMutator()
        self.evaluator = BenchmarkEvaluator()

    @staticmethod
    def _load_or_create_baseline(db: Session, campaign: EvolutionCampaign) -> EvolutionCandidate:
        baseline = (
            db.query(EvolutionCandidate)
            .filter(EvolutionCandidate.campaign_id == campaign.id, EvolutionCandidate.is_baseline.is_(True))
            .order_by(EvolutionCandidate.id.asc())
            .first()
        )
        if baseline is not None:
            return baseline

        from app.db.models.prompt_template import PromptTemplate
        from app.db.models.agent_skill import AgentSkill

        prompt = db.get(PromptTemplate, campaign.baseline_prompt_template_id)
        if prompt is None:
            raise RuntimeError('Missing baseline prompt template')

        skills = []
        if campaign.baseline_skill_id is not None:
            skill = db.get(AgentSkill, campaign.baseline_skill_id)
            if skill is not None:
                skills = list(skill.skills or [])

        baseline = EvolutionCandidate(
            campaign_id=campaign.id,
            generation=0,
            parent_candidate_id=None,
            system_prompt=prompt.system_prompt,
            user_prompt_template=prompt.user_prompt_template,
            skills=skills,
            is_baseline=True,
            status='generated',
        )
        db.add(baseline)
        db.commit()
        db.refresh(baseline)
        return baseline

    @staticmethod
    def _should_stop(campaign: EvolutionCampaign) -> bool:
        if int(campaign.consumed_iterations or 0) >= int(campaign.max_iterations or 0):
            return True
        if int(campaign.consumed_candidates or 0) >= int(campaign.max_candidates or 0):
            return True
        if int(campaign.llm_calls_used or 0) >= int(campaign.max_llm_calls or 0):
            return True
        if float(campaign.consumed_budget_usd or 0.0) >= float(campaign.budget_usd_limit or 0.0):
            return True
        if campaign.status == 'cancel_requested':
            return True
        return False

    def run_campaign(self, db: Session, campaign: EvolutionCampaign) -> EvolutionCampaign:
        if campaign.status in {'completed', 'cancelled', 'failed'}:
            return campaign

        campaign.status = 'running'
        campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
        db.commit()
        db.refresh(campaign)

        baseline = self._load_or_create_baseline(db, campaign)
        if baseline.status != 'evaluated':
            self.evaluator.evaluate_candidate(db, campaign=campaign, candidate=baseline)

        parent = baseline
        best_candidate = baseline
        generation = int(parent.generation or 0)

        while not self._should_stop(campaign):
            generation += 1
            campaign.consumed_iterations = int(campaign.consumed_iterations or 0) + 1
            db.commit()
            db.refresh(campaign)

            candidate = self.mutator.mutate(db, campaign=campaign, parent=parent, generation=generation)
            campaign.consumed_candidates = int(campaign.consumed_candidates or 0) + 1
            db.commit()
            db.refresh(campaign)

            if candidate.status == 'rejected':
                parent = best_candidate
                continue

            self.evaluator.evaluate_candidate(db, campaign=campaign, candidate=candidate)
            latest_cost = float(candidate.llm_cost_usd or 0.0)
            campaign.consumed_budget_usd = float(campaign.consumed_budget_usd or 0.0) + latest_cost

            best_score = float(best_candidate.fitness_score or 0.0)
            candidate_score = float(candidate.fitness_score or 0.0)
            if candidate_score >= best_score:
                best_candidate = candidate
                campaign.best_candidate_id = candidate.id

            parent = best_candidate
            db.commit()
            db.refresh(campaign)

        if campaign.status == 'cancel_requested':
            campaign.status = 'cancelled'
        elif campaign.status not in {'failed', 'cancelled'}:
            campaign.status = 'completed'
        campaign.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(campaign)
        return campaign

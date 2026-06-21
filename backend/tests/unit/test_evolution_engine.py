from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.services.evolution.engine import EvolutionEngine


class _FakeMutator:
    def __init__(self) -> None:
        self.calls = 0

    def mutate(self, db: Session, *, campaign: EvolutionCampaign, parent, generation: int):
        from app.db.models.evolution_candidate import EvolutionCandidate

        self.calls += 1
        candidate = EvolutionCandidate(
            campaign_id=campaign.id,
            generation=generation,
            parent_candidate_id=parent.id,
            system_prompt=f'mutated system {self.calls}',
            user_prompt_template='mutated user {pair}',
            skills=['Skill X'],
            status='generated',
            is_baseline=False,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        campaign.llm_calls_used = int(campaign.llm_calls_used or 0) + 1
        db.commit()
        return candidate


class _FakeEvaluator:
    def __init__(self) -> None:
        self.score = 0.3

    def evaluate_candidate(self, db: Session, *, campaign: EvolutionCampaign, candidate):
        from app.db.models.evolution_candidate_evaluation import EvolutionCandidateEvaluation

        self.score += 0.1
        candidate.status = 'evaluated'
        candidate.fitness_score = self.score
        candidate.metrics_summary = {'aggregate': self.score}
        evaluation = EvolutionCandidateEvaluation(
            candidate_id=candidate.id,
            evaluation_type='benchmark',
            benchmark_run_id=None,
            metrics={'aggregate': self.score},
            aggregate_score=self.score,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        return evaluation


def test_evolution_engine_stops_on_limits_and_sets_best_candidate() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = User(email='engine-admin@local.dev', hashed_password='x', role='admin', is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        prompt = PromptTemplate(
            agent_name='technical-analyst',
            version=1,
            is_active=True,
            system_prompt='baseline system',
            user_prompt_template='baseline user {pair}',
            notes='seed',
            created_by_id=user.id,
        )
        db.add(prompt)

        skill = AgentSkill(
            agent_name='technical-analyst',
            version=1,
            is_active=True,
            skills=['Skill A'],
            notes='seed',
            created_by_id=user.id,
        )
        db.add(skill)
        db.commit()
        db.refresh(prompt)
        db.refresh(skill)

        campaign = EvolutionCampaign(
            name='Engine Campaign',
            agent_name='technical-analyst',
            provider='openai',
            model_name='gpt-4.1-mini',
            model_parameters={'temperature': 0.5},
            baseline_prompt_template_id=prompt.id,
            baseline_skill_id=skill.id,
            status='pending',
            max_iterations=2,
            max_candidates=2,
            max_llm_calls=5,
            budget_usd_limit=10.0,
            evaluation_config={'benchmark_profile': 'standard'},
            created_by_id=user.id,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        evolution_engine = EvolutionEngine()
        evolution_engine.mutator = _FakeMutator()
        evolution_engine.evaluator = _FakeEvaluator()
        result = evolution_engine.run_campaign(db, campaign)

        assert result.status == 'completed'
        assert int(result.consumed_iterations) == 2
        assert int(result.consumed_candidates) == 2
        assert result.best_candidate_id is not None

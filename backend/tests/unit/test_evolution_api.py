from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.evolution import create_campaign
from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.schemas.evolution_campaign import EvolutionCampaignCreateRequest


class _FakeTaskResult:
    id = 'task-evolution-123'


class _FakeEvolutionTask:
    def __init__(self) -> None:
        self.calls = []

    def apply_async(self, args=None, kwargs=None, queue=None, ignore_result=None):
        self.calls.append({'args': args, 'kwargs': kwargs, 'queue': queue, 'ignore_result': ignore_result})
        return _FakeTaskResult()


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


def test_evolution_create_campaign_enqueues_task(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = User(email='api-admin@local.dev', hashed_password='x', role='admin', is_active=True)
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

        fake_task = _FakeEvolutionTask()
        monkeypatch.setattr('app.api.routes.evolution.run_evolution_campaign', fake_task)

        payload = EvolutionCampaignCreateRequest(
            name='API Campaign',
            agent_name='technical-analyst',
            provider='openai',
            model_name='gpt-4.1-mini',
            model_parameters={'temperature': 0.7},
            baseline_prompt_template_id=prompt.id,
            baseline_skill_id=skill.id,
            max_iterations=3,
            max_candidates=3,
            max_llm_calls=10,
            budget_usd_limit=5.0,
            evaluation_config={'benchmark_profile': 'standard'},
        )

        created = create_campaign(payload=payload, db=db, user=_DummyUser(user.id))
        assert created.status == 'pending'
        assert created.celery_task_id == 'task-evolution-123'
        assert len(fake_task.calls) == 1

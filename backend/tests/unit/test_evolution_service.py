from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.services.evolution.service import EvolutionService


def _seed_user_prompt_skill(db: Session) -> tuple[User, PromptTemplate, AgentSkill]:
    user = User(email='evolution-admin@local.dev', hashed_password='x', role='admin', is_active=True)
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
    return user, prompt, skill


def test_evolution_service_create_list_cancel() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    service = EvolutionService()

    with Session(engine) as db:
        user, prompt, skill = _seed_user_prompt_skill(db)
        campaign = service.create_campaign(
            db,
            {
                'name': 'TA Evolution',
                'agent_name': 'technical-analyst',
                'provider': 'openai',
                'model_name': 'gpt-4.1-mini',
                'model_parameters': {'temperature': 0.7},
                'baseline_prompt_template_id': prompt.id,
                'baseline_skill_id': skill.id,
                'max_iterations': 2,
                'max_candidates': 2,
                'max_llm_calls': 3,
                'budget_usd_limit': 10.0,
                'evaluation_config': {'benchmark_profile': 'standard'},
            },
            created_by_id=user.id,
        )

        assert campaign.status == 'pending'

        rows, total = service.list_campaigns(db)
        assert total == 1
        assert rows[0].id == campaign.id

        cancelled = service.request_cancel(db, campaign.id)
        assert cancelled.status == 'cancelled'
